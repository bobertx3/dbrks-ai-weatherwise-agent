from typing import Any, Generator, Optional
import os
import json
import uuid
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Load environment variables
TARGET_CATALOG = os.environ.get("TARGET_CATALOG")
TARGET_SCHEMA = os.environ.get("TARGET_SCHEMA")
VS_INDEX = os.environ.get("VS_INDEX")
RETRIEVER_TOOL_NAME = os.environ.get("RETRIEVER_TOOL_NAME")
# Model Serving LLM endpoint path is disabled while this demo uses AI Gateway.
# LLM_ENDPOINT_NAME = os.environ.get("LLM_ENDPOINT_NAME")
AI_GATEWAY_MODEL = os.environ.get("AI_GATEWAY_MODEL")
AI_GATEWAY_BASE_URL = os.environ.get("AI_GATEWAY_BASE_URL")

import mlflow
from databricks_langchain import (
    # ChatDatabricks,
    VectorSearchRetrieverTool,
    DatabricksFunctionClient,
    UCFunctionToolkit,
    set_uc_function_client,
)
from langchain_core.messages import ToolMessage
from mlflow.models import set_model
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)

mlflow.langchain.autolog()

client = DatabricksFunctionClient(disable_notice=True)
set_uc_function_client(client)

############################################
# Define your LLM endpoint
############################################
# AI_GATEWAY_MODEL is a Unity AI Gateway model service (catalog.schema.service, created by
# agent_src/setup_ai_gateway) or a system.ai model. LLM_DESTINATION_MODEL names the model the
# service routes to (used only to pick model-specific request options).
LLM_DESTINATION_MODEL = os.environ.get("LLM_DESTINATION_MODEL", "")
# On the serving endpoint, LLM calls run as a dedicated service principal
# (scripts/setup_agent_llm_sp.sh) with EXECUTE on the model service: automatic auth
# passthrough doesn't cover model services. Locally / in notebooks the default auth is used.
LLM_CLIENT_ID = os.environ.get("LLM_CLIENT_ID")
LLM_CLIENT_SECRET = os.environ.get("LLM_CLIENT_SECRET")
LLM_HOST = os.environ.get("LLM_HOST")


def _get_databricks_host() -> str:
    host = (
        LLM_HOST
        or os.environ.get("DATABRICKS_HOST")
        or os.environ.get("DATABRICKS_WORKSPACE_URL")
        or os.environ.get("DATABRICKS_HOST_URL")
    )
    if not host:
        raise ValueError(
            "AI_GATEWAY_MODEL is set, but no Databricks host was found. "
            "Set DATABRICKS_HOST (or AI_GATEWAY_BASE_URL), e.g. https://<workspace>.cloud.databricks.com."
        )
    host = host.rstrip("/")
    return host if host.startswith("http") else f"https://{host}"


def _llm_workspace_client():
    from databricks.sdk import WorkspaceClient

    if LLM_CLIENT_ID and LLM_CLIENT_SECRET:
        return WorkspaceClient(
            host=_get_databricks_host(),
            client_id=LLM_CLIENT_ID,
            client_secret=LLM_CLIENT_SECRET,
            auth_type="oauth-m2m",
        )
    return WorkspaceClient()


def _bearer(ws) -> str:
    auth_result = ws.config.authenticate()
    headers = auth_result if isinstance(auth_result, dict) else {}
    if callable(auth_result):
        auth_result(headers)
    auth_header = headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise ValueError("Databricks auth did not return a bearer token for the AI Gateway call.")
    return auth_header


def _gateway_http_clients():
    """httpx clients that attach a fresh Databricks bearer token to every request.

    OAuth tokens (service principal or notebook identity) expire after ~1h, so a static
    api_key would break a long-running endpoint. The SDK caches and refreshes the token.
    """
    import httpx

    ws = _llm_workspace_client()

    class _DatabricksAuth(httpx.Auth):
        def auth_flow(self, request):
            request.headers["Authorization"] = _bearer(ws)
            yield request

    auth = _DatabricksAuth()
    return httpx.Client(auth=auth, timeout=120), httpx.AsyncClient(auth=auth, timeout=120)


def _create_llm():
    if not AI_GATEWAY_MODEL:
        raise ValueError("Set AI_GATEWAY_MODEL before importing the agent.")
    from langchain_openai import ChatOpenAI

    base_url = AI_GATEWAY_BASE_URL or f"{_get_databricks_host()}/ai-gateway/mlflow/v1"
    chat_kwargs = {"model": AI_GATEWAY_MODEL, "base_url": base_url}
    if os.environ.get("DATABRICKS_TOKEN") and not LLM_CLIENT_ID:
        chat_kwargs["api_key"] = os.environ["DATABRICKS_TOKEN"]  # local runs with a PAT
    else:
        http_client, http_async_client = _gateway_http_clients()
        chat_kwargs.update(api_key="databricks-oauth", http_client=http_client, http_async_client=http_async_client)
    if "gpt-5" in f"{AI_GATEWAY_MODEL} {LLM_DESTINATION_MODEL}":
        # GPT-5-family models reject function tools with reasoning_effort on
        # /chat/completions unless it is explicitly disabled.
        chat_kwargs["reasoning_effort"] = "none"
    return ChatOpenAI(**chat_kwargs)


llm = _create_llm()

############################################
# Define your system prompt
############################################
system_prompt = """
You are the MedTech Supply Chain Escalation Crew of Agents.

GOAL
Ensure temperature-sensitive MedTech shipments are delivered safely and on time by detecting weather-driven risk and executing SOP-aligned escalation actions.

---

SQL ANALYST
Role: Data analyst focused on MedTech shipment logistics
Goal: Retrieve shipments (optionally filtered by destination and/or status) and expose the maximum allowable temperatures needed for risk evaluation
Tool: `get_shipments` – also returns carrier, priority, procedure_date, destination_facility_name, original_eta_date, delay_hours, delay_reason and last_recorded_temp_f
Use them:
- Sensor excursion (already out of spec, regardless of weather): last_recorded_temp_f above temperature_max_f or below temperature_min_f → escalate first.
- Surgery at risk: eta_date > procedure_date → name the hospital/clinic and the procedure date.
- Priority STAT = needed for a scheduled procedure; rank STAT ahead of ROUTINE at the same risk level.
- For delays, cite delay_hours and delay_reason.

---

METEOROLOGIST
Role: Weather and risk classification specialist
Goal: Use current and forecasted temperatures to calculate the temperature gap and classify shipment risk levels
Tools:
- `check_weather` – returns the current temperature AND a 7-day daily forecast (high/low °F) for a city
- `temp_gap` – returns ambient – allowable (°F)
How to use them:
- Call `check_weather` once per destination city (not once per shipment).
- For each shipment, use the forecast HIGH for its `eta_date` (if the ETA is past or beyond the forecast, use the nearest forecast day and say which day you used). Use the current temperature only for shipments arriving today.
- Each product has its OWN range (`temperature_min_f`–`temperature_max_f`); compute both gaps and classify with the DECISION POLICY:
  heat gap = `temp_gap(forecast_high, temperature_max_f)`, cold gap = `temp_gap(temperature_min_f, forecast_low)`.
- Frozen products (`temperature_max_f` below 32 °F, e.g. fibrin sealant, bone allograft) ship on dry ice, so outside weather does not apply: judge them on the sensor reading and delay only (delay_hours > 24 = dry-ice risk).

---

SUPPLIER RESEARCHER
Role: Escalation intelligence analyst
Goal: Retrieve supplier details, backup inventory, and SOPs relevant to at-risk shipments
- Only call these tools when the user asks for backups, suppliers, SOPs or escalation steps, or when drafting an escalation email/SMS. A plain "what's at risk?" question does NOT need them.
- Search backup inventory only for shipments that are AT_RISK or already out of range, never for all products.
- Pass the destination state to `get_backup_inventory` so the closest sites come first; name the product and site (not the product ID).
- Lot expiry is inventory housekeeping, not temperature risk: mention it only when the user asks about expiry/lots.
Tools:
- `get_supplier_details`
- `get_backup_inventory`
- `search_supplier_sops`

---

EMAIL COPYWRITER
Role: Communication specialist for escalation messaging
Goal: Draft and send concise, structured escalation emails including cause, data, and recommended next steps.
Tool: `send_email(recipient, subject, summary, call_to_action, message)`
Keep it short enough to read on a phone in 20 seconds:
- `subject`: under 70 characters, e.g. "3 NYC STAT shipments at risk for Nov 20 surgeries".
- `summary`: 1–2 plain sentences: how many shipments, what is wrong, what happens next.
- `call_to_action`: the one person to call first: the supplier contact's name, company and phone from `get_supplier_details` (for the most urgent shipment), e.g. "Call Felix Romero (CardioNova) at +1-602-555-0144". It is shown highlighted.
- `message` (details, HTML): one line per shipment (`<b>SHP-ID</b> product → hospital: reading vs limit, issue, surgery impact`), at most 4 shipments (STAT first, then "+N more"), then "Next steps" with at most 3 short SOP-based bullets. No paragraphs, no methodology, no repeated numbers.
- Recipient: only pass `recipient` if the user typed an email address in this conversation. Otherwise leave it empty: the tool sends to the default recipient. NEVER ask the user who to send it to or ask for confirmation, just send it.

---

TEXTER
Role: Rapid-response notifier
Goal: Send a short, TL;DR-style SMS summarizing the risk status or resolution. If no number is provided, send the SMS to 3019085817 without asking.
Tool: `send_sms()` (the greeting is added automatically; don't repeat it)
SMS style (executive audience): plain text, no markdown, no shipment IDs, no jargon ("excursion", "FREEZE", "+21.4°F"), at most 5 lines:
  line 1: how many shipments need attention, in plain words
  then one "• " line per problem, grouping products with the same issue (say "too warm", "too cold", "starting to thaw", "heat spike on arrival"; include the reading only when it helps)
  last line: "Next:" the action, and who to call: the supplier contact's NAME and PHONE from `get_supplier_details` (call it for the most urgent shipment's supplier before texting). End with "Details in your email." when an email was also sent.
Example:
  4 NYC shipments need attention.
  • 2 cardiac stent kits are too warm (85–87°F, limit 77°F)
  • 1 frozen bone graft is starting to thaw
  • 1 heart valve faces a heat spike on arrival
  Next: quarantine affected stock, ship replacements from the Bronx. Call Dylan Kim (OrthoCore) +1-708-555-0133. Details in your email.

---

NETWORKER
Role: Event networking assistant (Databricks AI World Tour / DAIWT NYC)
Goal: When the user's request is social or networking, e.g. "great meeting you at Databricks World Tour", "great meeting you at DAIWT NYC", "let's connect", "send me your LinkedIn", send a greeting text with the LinkedIn QR code image. If no number is provided, send it to 3019085817. Optionally pass a short personal `note` drawn from the user's message. Then reply with one friendly sentence confirming it was sent.
Tool: `send_connect_sms(to_number, note)`
Routing:
- Networking/greeting requests → `send_connect_sms` only. Do NOT run shipment, weather, supplier, or email tools for them.
- Weather, shipment, risk, supplier, or escalation requests → the crew above (use `send_sms` for any SMS summary, never `send_connect_sms`).
- If a request mixes both, do the shipment/weather work as usual and also call `send_connect_sms`.

---

ANSWER STYLE (executive audience)
- Answer only what was asked. "At risk" / "risk" questions = temperature excursions only: sensor readings outside the product range, or a forecast HEAT/FREEZE risk at the ETA, plus any surgery the delay puts at risk. Do not add backups, suppliers, SOPs, inventory or lot-expiry details unless asked.
- Format: one headline sentence with the count, then at most 4 bullets (STAT first), one line each:
  `**SHP-30001** Aortic Valve → Upper East Side Heart Institute: 31.4°F vs 50–77°F (FREEZE) · misses Nov 19 surgery`
  If there are more, end with "+N more" and offer the full list. Then one short "Next step:" line.
- No preamble, no restating the question, no methodology unless asked.

---

OPERATING PRINCIPLES
- Be concise, factual, and action-oriented. Always explain *why* using numeric evidence (temperature gaps, limits, etc.).
- Never output raw tool results without a professional summary.
- Do not fabricate data. If required data (ETA, destination, or weather) is missing, mark `risk_level = INSUFFICIENT_DATA` and list missing fields.
- If `search_supplier_sops` returns nothing, state “No relevant SOP found.”
- Never tell the user to "verify" or "check" something your tools can check (e.g. the forecast); check it yourself first.
- If nothing is at risk, say so plainly and stop: no speculative follow-ups.
- Default to °F; if a tool returns °C, convert and show both once.

---

DECISION POLICY
Use the larger of the heat gap and the cold gap (see METEOROLOGIST); a negative gap means inside the range.
• AT_RISK → gap ≥ 20 °F
• BORDERLINE → 10–19 °F
• NOT_AT_RISK → < 10 °F
• INSUFFICIENT_DATA → any key value missing
• A sensor reading already outside the range (excursion) is AT_RISK regardless of weather.
• Say which way the risk goes: HEAT (above max) or FREEZE/COLD (below min).
• Below 0 °F, say "warmer" / "colder" than the limit, never "above" / "below" (e.g. "−30.7°F, 9.3°F warmer than its −40°F limit (thawing)"). For frozen products, a reading above the max means the product is thawing.

---

GUARDRAILS
- Use only data from the defined tools.
- Never fabricate SOPs, suppliers, or contacts.
- Keep answers short (see ANSWER STYLE); say “No relevant SOP found” when applicable.
"""

###############################################################################
## Define tools for your agent, enabling it to retrieve data or take actions
## https://docs.databricks.com/generative-ai/agent-framework/agent-tool.html
###############################################################################
tools = []

uc_toolkit = UCFunctionToolkit(function_names=[
    f"{TARGET_CATALOG}.{TARGET_SCHEMA}.*"
])
tools.extend(uc_toolkit.tools)

# Add your custom Python tools
from custom_tools.tool_send_email import send_email
from custom_tools.tool_send_sms import send_sms, send_connect_sms
from custom_tools.tool_check_weather import check_weather
tools.extend([send_email, send_sms, send_connect_sms, check_weather])

# Add in a tool to retrieve from our Vector Search Index
retriever_tool = VectorSearchRetrieverTool(
  index_name=f"{TARGET_CATALOG}.{TARGET_SCHEMA}.{VS_INDEX}",
  tool_name=RETRIEVER_TOOL_NAME,
  tool_description="Use this tool to search for supplier SOPs and escalations.",
  num_results=3,
  disable_notice=True
)
tools.append(retriever_tool)

#####################
## Define agent logic
#####################
# A simple, dependency-light tool-calling loop around ChatDatabricks. We avoid
# langgraph entirely so the agent has no langgraph version constraints (it only
# needs databricks-langchain + mlflow). The MLflow Responses helpers handle the
# request/response item conversion.

_MODEL = llm.bind_tools(tools)
_TOOLS_BY_NAME = {t.name: t for t in tools}
_MAX_TURNS = 60


def _to_text(obs: Any) -> str:
    if isinstance(obs, str):
        return obs
    try:
        return json.dumps(obs, default=str)
    except Exception:
        return str(obs)


def _message_text(ai_message) -> str:
    """Extract plain assistant text from an AIMessage.

    Reasoning models served via the Responses API return ``content`` as a list of
    typed blocks (reasoning, text, ...). We concatenate the text blocks and skip
    reasoning/other blocks.
    """
    content = getattr(ai_message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") in ("text", "output_text") and isinstance(
                    block.get("text"), str
                ):
                    parts.append(block["text"])
        return "".join(parts)
    return str(content) if content is not None else ""


def _responses_input_to_chat_messages(input_items) -> list[dict[str, str]]:
    """Convert ResponsesAgent input items into LangChain chat messages.

    Some MLflow runtimes do not expose ``to_chat_completions_input``, so keep the
    conversion local and limited to the message shapes this agent receives.
    """
    messages = []
    for item in input_items:
        data = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        role = data.get("role", "user")
        content = data.get("content", "")
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, str):
                    text_parts.append(part)
                elif isinstance(part, dict) and isinstance(part.get("text"), str):
                    text_parts.append(part["text"])
            content = "".join(text_parts)
        messages.append({"role": role, "content": content or ""})
    return messages


class ToolCallingResponsesAgent(ResponsesAgent):
    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        outputs = [
            event.item
            for event in self.predict_stream(request)
            if event.type == "response.output_item.done"
        ]
        return ResponsesAgentResponse(
            output=outputs, custom_outputs=request.custom_inputs
        )

    def predict_stream(
        self,
        request: ResponsesAgentRequest,
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        # Convert Responses input items into chat-completions style messages
        cc_msgs = _responses_input_to_chat_messages(request.input)
        # The model has no clock: give it today's date so "tomorrow" maps to the right forecast day.
        from datetime import datetime
        from zoneinfo import ZoneInfo

        today = datetime.now(ZoneInfo(os.environ.get("AGENT_TIMEZONE", "America/New_York")))
        date_line = f"\n\nTODAY is {today:%A, %Y-%m-%d}; tomorrow is the next calendar day."
        messages = [{"role": "system", "content": system_prompt + date_line}] + cc_msgs

        for _ in range(_MAX_TURNS):
            ai_message = _MODEL.invoke(messages)
            messages.append(ai_message)

            # Emit assistant text (if any)
            text = _message_text(ai_message)
            if text:
                yield ResponsesAgentStreamEvent(
                    type="response.output_item.done",
                    item=self.create_text_output_item(text=text, id=uuid.uuid4().hex),
                )

            tool_calls = getattr(ai_message, "tool_calls", None)
            if not tool_calls:
                return

            # Emit the function-call items, then run the tools and emit their outputs
            for call in tool_calls:
                yield ResponsesAgentStreamEvent(
                    type="response.output_item.done",
                    item=self.create_function_call_item(
                        id=uuid.uuid4().hex,
                        call_id=call.get("id"),
                        name=call.get("name"),
                        arguments=json.dumps(call.get("args", {})),
                    ),
                )

            for call in tool_calls:
                name = call.get("name")
                tool = _TOOLS_BY_NAME.get(name)
                try:
                    obs = tool.invoke(call.get("args", {})) if tool else f"Unknown tool: {name}"
                except Exception as e:  # surface tool errors back to the model
                    obs = f"Error calling tool {name}: {e}"
                obs = _to_text(obs)
                messages.append(
                    ToolMessage(content=obs, name=name, tool_call_id=call.get("id"))
                )
                yield ResponsesAgentStreamEvent(
                    type="response.output_item.done",
                    item=self.create_function_call_output_item(
                        call_id=call.get("id"), output=obs
                    ),
                )


AGENT = ToolCallingResponsesAgent()
set_model(AGENT)
