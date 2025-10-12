from typing import Any, Generator, Optional, Sequence, Union
import os
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
from langchain_core.language_models import LanguageModelLike
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_core.tools import BaseTool
from langgraph.graph import END, StateGraph
from langgraph.graph.graph import CompiledGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt.tool_node import ToolNode
from mlflow.langchain.chat_agent_langgraph import ChatAgentState, ChatAgentToolNode
from mlflow.pyfunc import ChatAgent
from mlflow.types.agent import (
    ChatAgentChunk,
    ChatAgentMessage,
    ChatAgentResponse,
    ChatContext,
)

# Optional: global default (ok to keep even if not strictly necessary)
try:
    from langgraph.config import set_config
    set_config({"recursion_limit": 60})
except Exception:
    pass


mlflow.langchain.autolog()

client = DatabricksFunctionClient(disable_notice=True)
set_uc_function_client(client)

############################################
# Define your LLM endpoint
############################################
llm = ChatDatabricks(endpoint=LLM_ENDPOINT_NAME)

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
Tool: `agentbricks__med_tech_supply_chain_agent__get_shipments`

---

METEOROLOGIST  
Role: Weather and risk classification specialist  
Goal: Use current and forecasted temperatures to calculate the temperature gap and classify shipment risk levels  
Tools:  
- `check_weather` – returns current and forecast temps (°F) for ETA window  
- `agentbricks__med_tech_supply_chain_agent__temp_gap` – returns ambient – allowable (°F)

---

SUPPLIER RESEARCHER  
Role: Escalation intelligence analyst  
Goal: Retrieve supplier details, backup inventory, and SOPs relevant to at-risk shipments  
Tools:  
- `agentbricks__med_tech_supply_chain_agent__get_supplier_details`  
- `agentbricks__med_tech_supply_chain_agent__get_backup_inventory`  
- `search_supplier_sops`

---

EMAIL COPYWRITER  
Role: Communication specialist for escalation messaging  
Goal: Draft and send concise, structured escalation emails including cause, data, and recommended next steps  
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
    "agentbricks.med_tech_supply_chain_agent.*"
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

def create_tool_calling_agent(
    model: LanguageModelLike,
    tools: Union[Sequence[BaseTool], ToolNode],
    system_prompt: Optional[str] = None,
) -> CompiledGraph:
    model = model.bind_tools(tools)

    # Define the function that determines which node to go to
    def should_continue(state: ChatAgentState):
        messages = state["messages"]
        last_message = messages[-1]
        # If there are function calls, continue. else, end
        if last_message.get("tool_calls"):
            return "continue"
        else:
            return "end"

    if system_prompt:
        preprocessor = RunnableLambda(
            lambda state: [{"role": "system", "content": system_prompt}]
            + state["messages"]
        )
    else:
        preprocessor = RunnableLambda(lambda state: state["messages"])
    model_runnable = preprocessor | model

    def call_model(
        state: ChatAgentState,
        config: RunnableConfig,
    ):
        response = model_runnable.invoke(state, config)
        return {"messages": [response]}

    workflow = StateGraph(ChatAgentState)

    workflow.add_node("agent", RunnableLambda(call_model))
    workflow.add_node("tools", ChatAgentToolNode(tools))

    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "tools",
            "end": END,
        },
    )
    workflow.add_edge("tools", "agent")

    return workflow.compile()


class LangGraphChatAgent(ChatAgent):
    def __init__(self, agent: CompiledStateGraph):
        self.agent = agent

    def predict(
        self,
        messages: list[ChatAgentMessage],
        context: Optional[ChatContext] = None,
        custom_inputs: Optional[dict[str, Any]] = None,
    ) -> ChatAgentResponse:
        request = {"messages": self._convert_messages_to_dict(messages)}

        messages_accum: list[ChatAgentMessage] = []
        # ⬇️ Apply recursion_limit at execution time (no other logic changed)
        for event in self.agent.stream(request, config={"recursion_limit": 60}, stream_mode="updates"):
            for node_data in event.values():
                messages_accum.extend(
                    ChatAgentMessage(**msg) for msg in node_data.get("messages", [])
                )
        return ChatAgentResponse(messages=messages_accum)

    def predict_stream(
        self,
        messages: list[ChatAgentMessage],
        context: Optional[ChatContext] = None,
        custom_inputs: Optional[dict[str, Any]] = None,
    ) -> Generator[ChatAgentChunk, None, None]:
        request = {"messages": self._convert_messages_to_dict(messages)}
        # ⬇️ Apply recursion_limit at execution time (no other logic changed)
        for event in self.agent.stream(request, config={"recursion_limit": 60}, stream_mode="updates"):
            for node_data in event.values():
                yield from (
                    ChatAgentChunk(**{"delta": msg}) for msg in node_data["messages"]
                )

# Create the agent object, and specify it as the agent object to use when
# loading the agent back for inference via mlflow.models.set_model()
agent = create_tool_calling_agent(llm, tools, system_prompt)
AGENT = LangGraphChatAgent(agent)
mlflow.models.set_model(AGENT)