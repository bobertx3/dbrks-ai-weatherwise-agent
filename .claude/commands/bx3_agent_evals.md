# bx3_agent_evals — Build Agents & Evaluation Notebooks

Build a LangGraph agent with MLflow integration and a comprehensive evaluation notebook following the bobertx3 standard. Covers agent architecture, tool definitions, system prompts, and the full eval lifecycle: test, evaluate, register, deploy.

## Usage

`/bx3_agent_evals <action>`

Actions:
- `/bx3_agent_evals agent` — Build the main agent file
- `/bx3_agent_evals tools` — Create tool definitions (UC, Vector Search, Custom)
- `/bx3_agent_evals eval-notebook` — Build the evaluation notebook
- `/bx3_agent_evals full` — Build everything end-to-end

---

## Part 1: Agent Architecture

### File: `agent_src/<agent_name>_agent.py`

The agent follows this exact structure:

```python
# ── Imports ──────────────────────────────────────────────
import os
import mlflow
from dotenv import load_dotenv, find_dotenv
from databricks_langchain import ChatDatabricks, UCFunctionToolkit, VectorSearchRetrieverTool
from langchain_core.tools import tool, BaseTool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt.tool_node import ToolNode
from mlflow.pyfunc import ChatAgent
from mlflow.langchain.chat_agent_langgraph import ChatAgentState, ChatAgentToolNode

# ── Environment ──────────────────────────────────────────
load_dotenv(find_dotenv())

TARGET_CATALOG = os.getenv("TARGET_CATALOG", "")
TARGET_SCHEMA = os.getenv("TARGET_SCHEMA", "")
LLM_ENDPOINT_NAME = os.getenv("LLM_ENDPOINT_NAME", "databricks-gpt-5-4")
VS_INDEX = os.getenv("VS_INDEX", "")
RETRIEVER_TOOL_NAME = os.getenv("RETRIEVER_TOOL_NAME", "")
# ... all env vars needed by tools

# ── LLM ──────────────────────────────────────────────────
llm = ChatDatabricks(endpoint=LLM_ENDPOINT_NAME)

# ── System Prompt ────────────────────────────────────────
system_prompt = """..."""  # See System Prompt section below

# ── Tools ────────────────────────────────────────────────
tools: list[BaseTool] = []

# 1. UC Functions
uc_toolkit = UCFunctionToolkit(function_names=[f"{TARGET_CATALOG}.{TARGET_SCHEMA}.*"])
tools.extend(uc_toolkit.tools)

# 2. Vector Search Retriever
retriever_tool = VectorSearchRetrieverTool(
    index_name=f"{TARGET_CATALOG}.{TARGET_SCHEMA}.{VS_INDEX}",
    tool_name=RETRIEVER_TOOL_NAME,
    tool_description="Use this tool to search for [domain docs].",
    num_results=3,
    disable_notice=True,
)
tools.append(retriever_tool)

# 3. Custom Python Tools
from tools.custom_tools.tool_check_weather import check_weather
from tools.custom_tools.tool_send_email import send_email
from tools.custom_tools.tool_send_sms import send_sms
tools.extend([check_weather, send_email, send_sms])

# ── Graph ────────────────────────────────────────────────
# See Graph section below

# ── MLflow Registration ──────────────────────────────────
agent = create_tool_calling_agent(llm, tools, system_prompt)
AGENT = LangGraphChatAgent(agent)
mlflow.models.set_model(AGENT)
```

### System Prompt Pattern

```
You are the [Domain] [Role] Crew of Agents.

GOAL
[High-level mission — 1-2 sentences]

---

[PERSONA 1: e.g., SQL Analyst]
Role: [What this persona does]
Goal: [Specific objective]
Tools: [List of tools this persona uses]

---

[PERSONA 2: e.g., Meteorologist]
Role: ...
Goal: ...
Tools: ...

---

[PERSONA N]
...

---

OPERATING PRINCIPLES
- Be concise, factual, and action-oriented
- Never output raw tool results without a professional summary
- Do not fabricate data — only report what tools return
- Always include specific IDs, names, and numbers from tool results

---

DECISION POLICY
[Domain-specific classification logic, e.g.:]
Compute temp_gap_f = forecast_peak_temp - max_allowable_temp
  AT_RISK: gap >= 20°F
  BORDERLINE: 10-19°F
  NOT_AT_RISK: < 10°F
  INSUFFICIENT_DATA: missing values

---

GUARDRAILS
- Stay within [domain] scope
- Do not provide [medical/legal/financial] advice
- If a tool fails, report the failure — do not guess
```

**Key rules:**
- 3-6 personas per agent
- Each persona has explicit Role, Goal, and Tools
- Decision Policy uses concrete thresholds (numbers, not vague terms)
- Guardrails define scope boundaries

### Graph Architecture

```python
def create_tool_calling_agent(model, tools, system_prompt):
    """Create a LangGraph tool-calling agent."""

    model_with_tools = model.bind_tools(tools)

    def should_continue(state: ChatAgentState):
        messages = state["messages"]
        last_message = messages[-1]
        if isinstance(last_message, dict):
            if last_message.get("tool_calls"):
                return "tools"
        elif hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return END

    def call_model(state: ChatAgentState):
        messages = state["messages"]
        # Prepend system prompt
        if not messages or messages[0].get("role") != "system":
            messages = [{"role": "system", "content": system_prompt}] + messages
        response = model_with_tools.invoke(messages)
        return {"messages": [response]}

    workflow = StateGraph(ChatAgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ChatAgentToolNode(tools))
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    workflow.add_edge("tools", "agent")

    return workflow.compile()
```

### LangGraphChatAgent Wrapper

```python
class LangGraphChatAgent(ChatAgent):
    def __init__(self, agent):
        self.agent = agent

    def predict(self, messages, context=None, custom_inputs=None):
        request = {"messages": self._convert_messages(messages)}
        result = self.agent.invoke(request, config={"recursion_limit": 60})
        return self._build_response(result)

    def predict_stream(self, messages, context=None, custom_inputs=None):
        request = {"messages": self._convert_messages(messages)}
        for event in self.agent.stream(request, config={"recursion_limit": 60}):
            yield self._build_chunk(event)
```

**Recursion limit: always 60.**

---

## Part 2: Tool Definitions

### Category 1: UC Functions (`tools/uc_tools/tool_uc_functions.ipynb`)

SQL UDFs registered in Unity Catalog. Each function:
- Lives in `{catalog}.{schema}`
- Uses `CREATE OR REPLACE FUNCTION`
- Has typed parameters and return type (TABLE or scalar)
- Includes `COMMENT` for LLM tool description
- Supports flexible matching (case-insensitive, wildcards)

**Pattern:**
```sql
CREATE OR REPLACE FUNCTION {catalog}.{schema}.get_entities(
  filter_param STRING DEFAULT NULL
)
RETURNS TABLE (id STRING, name STRING, status STRING, ...)
COMMENT 'Retrieves entities filtered by [param]. Returns: id, name, status, ...'
RETURN
  SELECT * FROM {catalog}.{schema}.entities
  WHERE (filter_param IS NULL OR LOWER(column) LIKE CONCAT('%', LOWER(filter_param), '%'));
```

**Standard UC tools per project:**
1. **Primary query** — Get main entities (e.g., `get_shipments`)
2. **Detail lookup** — Get entity details (e.g., `get_supplier_details`)
3. **Secondary query** — Get related data (e.g., `get_backup_inventory`)
4. **Calculation** — Domain-specific computation (e.g., `temp_gap`)

### Category 2: Vector Search (`tools/uc_tools/tool_uc_vector_index.ipynb`)

```python
retriever_tool = VectorSearchRetrieverTool(
    index_name=f"{TARGET_CATALOG}.{TARGET_SCHEMA}.{VS_INDEX}",
    tool_name=RETRIEVER_TOOL_NAME,
    tool_description="Use this tool to search for [domain documents/SOPs/policies].",
    num_results=3,
    disable_notice=True,
)
```

**Setup notebook creates:**
- DELTA_SYNC index on source table
- Embedding model: `databricks-gte-large-en` (managed)
- Pipeline type: TRIGGERED
- Enable Change Data Feed on source table first

### Category 3: Custom Python Tools (`tools/custom_tools/`)

Each tool is a separate `.py` file using the `@tool` decorator:

```python
from langchain_core.tools import tool

@tool("tool_name")
def tool_name(param1: str, param2: str = "default") -> str:
    """One-line description for the LLM to understand when to use this tool."""
    try:
        # Implementation
        result = external_api_call(param1, param2)
        return f"Success: {result}"
    except Exception as e:
        return f"Error: {str(e)}"
```

**Conventions:**
- One file per tool: `tool_<name>.py`
- Always return strings (LLM-readable)
- Graceful error handling — return error message, don't raise
- Load credentials from environment variables
- Include a descriptive docstring (the LLM uses this)

---

## Part 3: Evaluation Notebook

### File: `agent_src/agent_eval_notebook.ipynb`

This notebook handles the FULL agent lifecycle. Follow this exact cell sequence:

---

### Cell 0: Header (Markdown)

Document the Mosaic AI Core APIs used:
- MLflow model lifecycle (`log_model`, `register_model`, `load_model`)
- MLflow GenAI evaluation (`mlflow.genai.evaluate`, scorers)
- Databricks Agent Framework (`agents.deploy`)
- Unity Catalog tools (`UCFunctionToolkit`)
- Vector Search (`VectorSearchRetrieverTool`)

---

### Cell 1: Install & Setup

```python
%pip install -U -qqqq mlflow-skinny[databricks] langgraph==0.3.4 databricks-langchain databricks-agents twilio python-dotenv
dbutils.library.restartPython()
```

Then:
```python
%load_ext autoreload
%autoreload 2

import sys
sys.path.append("./tools")
```

---

### Cell 2: Load Environment & Verify Tools

```python
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import <agent_name>_agent

# Print all available tools
tool_names = [t.name for t in <agent_name>_agent.tools]
print(f"Tools ({len(tool_names)}): {tool_names}")

# Load and print redacted env vars
def redact(val, show=4):
    if not val: return "(not set)"
    return val[:show] + "..." if len(val) > show else val

# Print each env var with redaction for secrets
for var in ["TARGET_CATALOG", "TARGET_SCHEMA", "LLM_ENDPOINT_NAME", ...]:
    val = os.getenv(var, "")
    is_secret = any(s in var.lower() for s in ["key", "token", "sid", "password"])
    print(f"  {var}: {redact(val) if is_secret else val}")
```

---

### Cell 3: Create MLflow Experiment

```python
import mlflow

user = spark.sql("select current_user()").first()[0]
exp_path = f"/Users/{user}/{MLFLOW_EXPERIMENT}"
mlflow.end_run()  # end any stray runs
mlflow.set_experiment(exp_path)
print(f"Experiment: {exp_path}")
```

---

### Cell 4: Unit Test (Full Automation Query)

```python
from <agent_name>_agent import AGENT

response = AGENT.predict({
    "messages": [{
        "role": "user",
        "content": "<COMPREHENSIVE QUERY THAT EXERCISES ALL TOOLS AND PERSONAS>"
    }]
})

# Display the response
for msg in response.messages:
    print(f"\n[{msg.role}] {msg.content[:500]}")
```

**The test query MUST trigger ALL agent capabilities in one shot.** Example:
> "I heard the weather in New York is going to be hot tomorrow. Which in-transit shipments are at risk of temperature excursions, and what supplier escalation steps should I take? Also is there a backup supplier nearby? Email me a full report and send me a super concise SMS message."

---

### Cell 5: Log Model to MLflow

```python
import datetime
from mlflow.models.resources import DatabricksFunction, DatabricksServingEndpoint, DatabricksVectorSearchIndex

# Auto-discover resources from tools
resources = [DatabricksServingEndpoint(endpoint_name=LLM_ENDPOINT_NAME)]
for t in <agent_name>_agent.tools:
    if hasattr(t, "resources"):         # VectorSearchRetrieverTool
        resources.extend(t.resources)
    if hasattr(t, "uc_function_name"):  # UnityCatalogTool
        resources.append(DatabricksFunction(function_name=t.uc_function_name))

input_example = {
    "messages": [{
        "role": "user",
        "content": "<representative query>"
    }]
}

with mlflow.start_run(run_name=f"{AGENT_NAME}-ut-{datetime.datetime.now():%Y%m%d}"):
    logged_agent_info = mlflow.pyfunc.log_model(
        name=AGENT_NAME,
        python_model="<agent_name>_agent.py",
        input_example=input_example,
        resources=resources,
        code_paths=["tools/custom_tools/"],
        extra_pip_requirements=["databricks-connect"],
    )
```

**Key patterns:**
- Run name: `{agent}-ut-{YYYYMMDD}`
- Auto-discover resources by checking tool attributes
- `code_paths` includes custom tools directory

---

### Cell 6: Create Prediction Wrapper

```python
logged_model_uri = f"runs:/{logged_agent_info.run_id}/{AGENT_NAME}"
loaded_model = mlflow.pyfunc.load_model(logged_model_uri)

def predict_wrapper(query: str) -> str:
    """Simplified predict for eval — string in, string out."""
    model_input = {"messages": [{"role": "user", "content": query}]}
    response = loaded_model.predict(model_input)
    return response["messages"][-1]["content"]
```

---

### Cell 7: Define Eval Dataset

```python
import pandas as pd

cases = [
    {
        "request": "What is [specific entity]'s escalation policy?",
        "expected_facts": [
            "fact about the entity",
            "specific detail that must appear",
            "another verifiable fact",
        ],
    },
    # ... 10-15 cases covering ALL tools and personas
]

eval_data = [
    {
        "inputs": {"query": row["request"]},
        "expectations": {"expected_facts": row["expected_facts"]},
    }
    for _, row in pd.DataFrame(cases).iterrows()
]
```

**Eval dataset rules:**
- Use `expected_facts` (list of strings), NOT `expected_response`
- 10-15 cases minimum
- Cover EVERY tool at least once
- Cover EVERY persona at least once
- Include product-specific, entity-specific, and cross-cutting queries
- Include edge cases (unknown entities, missing data)
- Each case has 3-6 expected facts

---

### Cell 8: Define LLM Judges (Scorers)

```python
from mlflow.genai.scorers import Correctness, Safety, RelevanceToQuery, Guidelines

scorers = [
    Correctness(),           # Factual accuracy vs expected_facts
    Safety(),                # No harmful/off-policy content
    RelevanceToQuery(),      # Response relevance to input query
    Guidelines(              # Domain-specific tone and style
        name="<domain>_tone",
        guidelines="""Professional and concise:
        - No chit-chat, clarifying questions, or filler
        - No raw logs, JSON dumps, or system metadata
        - Clear, factual, action-oriented language
        Pass if the response is structured and professional.
        Fail if casual, wordy, or includes raw data dumps.""",
    ),
]
```

**ALWAYS include all four scorers.** The Guidelines scorer is customized per domain.

---

### Cell 9: Run Evals

```python
print("Running evaluation...")
with mlflow.start_run(run_name=f"{AGENT_NAME}-evals-{datetime.datetime.now():%Y%m%d}"):
    results = mlflow.genai.evaluate(
        data=eval_data,
        predict_fn=predict_wrapper,
        scorers=scorers,
    )
```

---

### Cell 10: Iterate (Markdown)

> **Iteration checkpoint.** Review eval results above. Based on scores:
> - Low Correctness → Make system prompt more specific, add examples
> - Low Relevance → Tighten guardrails, reduce scope
> - Low Guidelines → Remove marketing fluff, add "be concise" instructions
> - Safety failures → Add explicit guardrails
>
> Go back to the agent `.py` file, update the prompt, re-run from Cell 4.

---

### Cell 11: Register to Unity Catalog

```python
uc_model_name = f"{TARGET_CATALOG}.{TARGET_SCHEMA}.{AGENT_NAME}"
uc_registered_model_info = mlflow.register_model(
    model_uri=logged_agent_info.model_uri,
    name=uc_model_name,
)

# Clickable link to UC model page
workspace_url = spark.conf.get("spark.databricks.workspaceUrl")
from IPython.display import HTML, display
display(HTML(
    f'<a href="https://{workspace_url}/explore/data/models/{TARGET_CATALOG}/{TARGET_SCHEMA}/{AGENT_NAME}" '
    f'target="_blank">View in Unity Catalog</a>'
))
```

---

### Cell 12: Deploy to Model Serving

```python
from databricks import agents

deployment = agents.deploy(
    model_name=uc_model_name,
    model_version=uc_registered_model_info.version,
    scale_to_zero=True,
    environment_vars={
        "TARGET_CATALOG": TARGET_CATALOG,
        "TARGET_SCHEMA": TARGET_SCHEMA,
        "LLM_ENDPOINT_NAME": LLM_ENDPOINT_NAME,
        "VS_INDEX": VS_INDEX,
        "RETRIEVER_TOOL_NAME": RETRIEVER_TOOL_NAME,
        # ... ALL env vars the agent needs at serving time
        # Including API keys for custom tools
    },
    tags={"endpointSource": AGENT_NAME},
)

print(f"Endpoint: {deployment.endpoint_name}")
print(f"Version: {deployment.model_version}")
```

**Key patterns:**
- `scale_to_zero=True` always
- Pass ALL environment variables (UC config, LLM endpoint, API keys)
- Tag with `endpointSource` for traceability
- Print the endpoint name for reference

---

## Eval Notebook Cell Summary

| Step | Cell Type | Purpose |
|------|-----------|---------|
| 0 | Markdown | API reference cheatsheet |
| 1 | Code | pip install + restart + autoreload |
| 2 | Code | Load env, verify tools (print names + redacted vars) |
| 3 | Code | Create MLflow experiment |
| 4 | Code | Unit test (full automation query hitting ALL tools) |
| 5 | Code | Log model with auto-discovered resources |
| 6 | Code | Create predict_wrapper (string → string) |
| 7 | Code | Define eval dataset (10-15 cases with expected_facts) |
| 8 | Code | Define 4 scorers (Correctness, Safety, Relevance, Guidelines) |
| 9 | Code | Run mlflow.genai.evaluate |
| 10 | Markdown | Pause — iterate on prompt based on scores |
| 11 | Code | Register to Unity Catalog + clickable link |
| 12 | Code | Deploy via agents.deploy with all env vars |

---

## Testing Notebook (`tests/manually_test_tools.ipynb`)

Before running the full agent, test each tool individually:

```python
# Cell 1: Setup
%pip install -U -qqqq python-dotenv twilio
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# Cell 2: Test Weather API
from tools.custom_tools.tool_check_weather import check_weather
result = check_weather.invoke({"city": "New York"})
print(result)

# Cell 3: Test Email
from tools.custom_tools.tool_send_email import send_email
result = send_email.invoke({"subject": "Test", "message": "Testing"})
print(result)

# Cell 4: Test SMS
from tools.custom_tools.tool_send_sms import send_sms
result = send_sms.invoke({"to_number": "+1234567890", "message": "Test"})
print(result)

# Cell 5: Test UC Functions (via SQL)
display(spark.sql(f"SELECT * FROM {catalog}.{schema}.get_shipments('New York', NULL)"))
```
