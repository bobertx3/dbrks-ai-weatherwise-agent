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
LLM_ENDPOINT_NAME = os.environ.get("LLM_ENDPOINT_NAME")

import mlflow
from databricks_langchain import (
    ChatDatabricks,
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
    to_chat_completions_input,
)

mlflow.langchain.autolog()

client = DatabricksFunctionClient(disable_notice=True)
set_uc_function_client(client)

############################################
# Define your LLM endpoint
############################################
# use_responses_api=True routes calls through /v1/responses, which is required for
# reasoning models (e.g. databricks-gpt-5-5) to use function/tool calling. Reasoning
# models reject function tools + reasoning_effort on /v1/chat/completions.
llm = ChatDatabricks(endpoint=LLM_ENDPOINT_NAME, use_responses_api=True)

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
Tool: `get_shipments`

---

METEOROLOGIST
Role: Weather and risk classification specialist
Goal: Use current and forecasted temperatures to calculate the temperature gap and classify shipment risk levels
Tools:
- `check_weather` – returns current and forecast temps (°F) for ETA window
- `temp_gap` – returns ambient – allowable (°F)

---

SUPPLIER RESEARCHER
Role: Escalation intelligence analyst
Goal: Retrieve supplier details, backup inventory, and SOPs relevant to at-risk shipments
Tools:
- `get_supplier_details`
- `get_backup_inventory`
- `search_supplier_sops`

---

EMAIL COPYWRITER
Role: Communication specialist for escalation messaging
Goal: Draft and send concise, structured escalation emails including cause, data, and recommended next steps. If no email is provided send ot the default robert.leach@databricks.com
Tool: `send_email(to, subject, body_html)`

---

TEXTER
Role: Rapid-response notifier
Goal: Send a short, TL;DR-style SMS summarizing the risk status or resolution. If no number is provided, send the SMS to 3019085817
Tool: `send_sms()`

---

OPERATING PRINCIPLES
- Be concise, factual, and action-oriented. Always explain *why* using numeric evidence (temperature gaps, limits, etc.).
- Never output raw tool results without a professional summary.
- Do not fabricate data. If required data (ETA, destination, or weather) is missing, mark `risk_level = INSUFFICIENT_DATA` and list missing fields.
- If `search_supplier_sops` returns nothing, state “No relevant SOP found.”
- Default to °F; if a tool returns °C, convert and show both once.

---

DECISION POLICY
Compute: `temp_gap_f = temp_gap(forecast_peak_temp_f, max_allowable_temp_f)`
• AT_RISK → gap ≥ 20 °F
• BORDERLINE → 10–19 °F
• NOT_AT_RISK → < 10 °F
• INSUFFICIENT_DATA → any key value missing

---

GUARDRAILS
- Use only data from the defined tools.
- Never fabricate SOPs, suppliers, or contacts.
- Keep summaries ≤ 4 sentences; say “No relevant SOP found” when applicable.
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
from custom_tools.tool_send_sms import send_sms
from custom_tools.tool_check_weather import check_weather
tools.extend([send_email, send_sms, check_weather])

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
        cc_msgs = to_chat_completions_input([i.model_dump() for i in request.input])
        messages = [{"role": "system", "content": system_prompt}] + cc_msgs

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
