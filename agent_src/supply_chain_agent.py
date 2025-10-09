from typing import Any, Generator, Optional, Sequence, Union
import os

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

# WORKSHOP_CATALOG = os.environ["WORKSHOP_CATALOG"]
# WORKSHOP_SCHEMA = os.environ["WORKSHOP_SCHEMA"]
# USER_SCHEMA = os.environ["USER_SCHEMA"]
WORKSHOP_CATALOG = "agentbricks"
WORKSHOP_SCHEMA = "med_tech_supply_chain_agent"
USER_SCHEMA = "med_tech_supply_chain_agent"


mlflow.langchain.autolog()

client = DatabricksFunctionClient(disable_notice=True)
set_uc_function_client(client)

############################################
# Define your LLM endpoint and system prompt
############################################
LLM_ENDPOINT_NAME = "databricks-claude-3-7-sonnet"
llm = ChatDatabricks(endpoint=LLM_ENDPOINT_NAME)

system_prompt = """
You are a MedTech Supply Chain Escalation Agent.

Your goal is to ensure that temperature-sensitive medical products are delivered safely and on time.
Use the available tools to retrieve data, assess risks, and recommend or initiate escalation steps.

Follow this reasoning process:
1. Retrieve current shipments and temperature logs from Unity Catalog tables.
2. Use the weather tool to check current or forecasted conditions at shipment destinations.
3. Compare the current weather temperature to each shipment’s max allowable temperature using the temp_gap() function.
4. If the temp gap is greater than a 20 degree difference (> 5), the shipment is at risk.
5. Look up supplier with get_supplier_details, and escalation SOPs using vector search or embedded product documentation.
6. If escalation is required, summarize the issue, the escalation steps, and send an email using the email tool

Guidelines:
- Always explain *why* a shipment is or isn’t at risk.
- Combine structured data (tables) with unstructured context (SOP text) in your reasoning.
- Be concise, factual, and action-oriented.
- Never return only a raw tool output — provide a short, professional summary first.
- Do not fabricate data; if uncertain, state that explicitly.
- If you can't find knowledge in your vector search, don't return generic information, just state nothing found.

Example tone:
“Shipment SHP-20417 from Zimmer Biotech is at risk due to ambient temperatures exceeding safe range by 12°F. 
Escalation to Tier-2 supplier contact is recommended per SOP section 4.2.”

"""

###############################################################################
## Define tools for your agent, enabling it to retrieve data or take actions
## beyond text generation
## To create and see usage examples of more tools, see
## https://docs.databricks.com/generative-ai/agent-framework/agent-tool.html
###############################################################################
tools = []

uc_toolkit = UCFunctionToolkit(function_names=[
    "agentbricks.med_tech_supply_chain_agent.*"
])
tools.extend(uc_toolkit.tools)

# Add your custom Python tools
from tools.custom_tools.tool_send_email import send_email
from tools.custom_tools.tool_check_weather import check_weather
tools.extend([send_email, check_weather])

# # You can use UDFs in Unity Catalog as agent tools
# if os.environ.get("IS_WORKSHOP_SETUP") == "TRUE":
#     # Default workshop setup
#     uc_tool_names = [f"{WORKSHOP_CATALOG}.{WORKSHOP_SCHEMA}.*"]
# else:
#     uc_tool_names = [f"{WORKSHOP_CATALOG}.{USER_SCHEMA}.*"]
# uc_toolkit = UCFunctionToolkit(function_names=uc_tool_names)
# tools.extend(uc_toolkit.tools)


# # Add custom tools
# from tools.tool_send_email import send_email
# from tools.tool_check_weather import check_weather
# tools.extend([send_email, check_weather])


# # Use Databricks vector search index as tool
# # See https://docs.databricks.com/generative-ai/agent-framework/unstructured-retrieval-tools.html
# # for details

# Add in a tool to retrieve from our Vector Search Index
# num_results is an important input as it dictates how many results are returned
retriever_tool = VectorSearchRetrieverTool(
  index_name=f"{WORKSHOP_CATALOG}.{WORKSHOP_SCHEMA}.supplier_sops_vs_index",
  tool_name="search_supplier_sops",
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

        messages = []
        for event in self.agent.stream(request, stream_mode="updates"):
            for node_data in event.values():
                messages.extend(
                    ChatAgentMessage(**msg) for msg in node_data.get("messages", [])
                )
        return ChatAgentResponse(messages=messages)

    def predict_stream(
        self,
        messages: list[ChatAgentMessage],
        context: Optional[ChatContext] = None,
        custom_inputs: Optional[dict[str, Any]] = None,
    ) -> Generator[ChatAgentChunk, None, None]:
        request = {"messages": self._convert_messages_to_dict(messages)}
        for event in self.agent.stream(request, stream_mode="updates"):
            for node_data in event.values():
                yield from (
                    ChatAgentChunk(**{"delta": msg}) for msg in node_data["messages"]
                )


# Create the agent object, and specify it as the agent object to use when
# loading the agent back for inference via mlflow.models.set_model()
agent = create_tool_calling_agent(llm, tools, system_prompt)
AGENT = LangGraphChatAgent(agent)
mlflow.models.set_model(AGENT)
