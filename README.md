## MedTech Weatherwise Agent - Intelligent Supply Chain

The **WeatherWise Supply Chain Escalation Agent** helps MedTech operations teams **anticipate and mitigate weather-related shipment risks** using live data, predictive reasoning, and automated escalation workflows.

![Chat Landing](img/06_app_chat_landing.png)

---

### Mission
Detect and resolve **shipment disruptions** before they impact **patients, compliance, or cost**.

---

### Scenario

Business Process
![](img/manual_flow.png)

Agent Flow
![](img/agent_flow.png)

---

### Architecture

![](img/arch.png)

### Data Flow

Left to right, the same flow the app's **Data Flow** modal animates:

```mermaid
flowchart LR
  subgraph SRC["Source data (synthetic)"]
    S1[Shipments<br/>ETA · carrier · max temp]
    S2[Inventory<br/>sites · lots · expiry]
    S3[Suppliers<br/>contacts · escalation]
    S4[Supplier SOPs<br/>escalation documents]
  end

  subgraph UC["Unity Catalog · governed lakehouse (bldemos.agentbricks_weatherwise)"]
    T[Delta tables<br/>shipments · inventory · suppliers · supplier_sops]
    VS[Vector Search index<br/>supplier_sops_vs_index]
    F[UC functions<br/>get_shipments · get_backup_inventory<br/>get_supplier_details · temp_gap]
    M[Agent model<br/>weatherwise · registered]
    IT[Inference table<br/>weatherwise_payload]
    subgraph SEM["UC semantic stack"]
      D[Domains] --- PG[Pages]
      MV[Metric Views] --- W[Wikis]
    end
  end

  subgraph SERVE["Model Serving · agent"]
    A[WeatherWise agent<br/>LangGraph · ResponsesAgent]
    GW[Unity AI Gateway<br/>rate limits · usage + payload logging]
    LLM[GPT<br/>system.ai.gpt-5-6-sol]
    X[External tools<br/>check_weather · send_email · send_sms]
    A --> GW --> LLM
    A --> X
  end

  ML[MLflow<br/>evaluation · traces]
  G[Genie<br/>Supply Chain Explorer]
  APP[Databricks App<br/>dashboard · agent chat · Ask Genie]
  U((Supply chain<br/>coordinator))

  SRC -- Lakeflow Job --> UC
  F & VS --> A
  M -- serve --> SERVE
  A -.-> ML
  T --> G
  SERVE -- CAN_QUERY --> APP
  G -- CAN_RUN --> APP
  T -- SQL warehouse --> APP
  APP --> U
```

| Stage | What happens | Where |
|---|---|---|
| **Ingest** | CSVs land as Delta tables; UC functions and the SOP vector index are created | `data/setup_data.ipynb`, `agent_src/tools/uc_tools/` |
| **Build + evaluate** | Agent is unit-tested, evaluated with LLM judges, logged and registered to UC | `agent_src/agent_eval_notebook.ipynb` (Lakeflow Job `weatherwise-agent-eval`) |
| **Serve** | `agents.deploy` puts the registered version on Model Serving; the agent calls GPT through the **Unity AI Gateway** | endpoint `agents_bldemos-agentbricks_weatherwise-weatherwise` |
| **Experience** | The app reads KPIs from the SQL warehouse, chats with the agent endpoint, and asks Genie | `dapp/` (app `weatherwise-chat-agent`) |

> A person approves every escalation. All demo data is synthetic.

---

### Example Queries

| Category | Example |
|-----------|----------|
| **Full Automation** | "The weather in New York will be hot tomorrow. Which in-transit shipments are at risk, what escalation steps should I take, and is there a backup supplier nearby? Email me a report and send an SMS summary." |
| **Weather Risks** | "Which shipments are at risk due to high temperatures in NYC?" |
| **Delivery Status** | "Show in-transit implant shipments for this week." |
| **Supplier SOPs** | "What's Zimmer's escalation process for temperature exceptions?" |

---

### Business Value

#### Speed
- **Hours to seconds** for risk detection
- Automated **weather + shipment correlation**
- One-click **escalation and notification**

#### Savings
- Avoids **spoilage, delays, and SLA fines**
- Reduces **manual triage workload**
- Maximizes **on-time, in-spec delivery**

#### Compliance
- Follows **supplier SOPs automatically**
- Provides **audit-ready traceability**
- Strengthens **patient safety assurance**

---

### Escalation Crew — Agents and Tools

#### METEOROLOGIST
**Role:** Weather and risk analyst
**Goal:** Analyze forecast data and compute temperature gaps between ambient and shipment thresholds
**Tools:** `check_weather`, `temp_gap`

---

#### SQL ANALYST
**Role:** Data analyst focused on MedTech shipment logistics
**Goal:** Retrieve shipments (optionally filtered by destination and/or status) and expose the maximum allowable temperatures needed for risk evaluation
**Tools:** `get_shipments`, `get_backup_inventory`

---

#### SUPPLIER RESEARCHER
**Role:** Knowledge analyst specializing in supplier compliance and escalation workflows
**Goal:** Identify supplier-specific SOPs, escalation contacts, and nearby backup inventory
**Tools:** `get_supplier_details`, `search_supplier_sops`

---

#### EMAIL COPYWRITER
**Role:** Communications agent for detailed escalation summaries
**Goal:** Compose and send email reports summarizing affected shipments and next steps
**Tools:** `send_email` (via any email service API)

---

#### TEXTER
**Role:** Rapid notifier for short alerts
**Goal:** Send SMS notifications to field or operations teams for immediate awareness
**Tools:** `send_sms` (via any SMS service)

---

### Tools Overview

#### Unity Catalog Tools
| Tool | Description |
|------|--------------|
| `get_shipments` | Retrieve shipment, carrier, and temperature data |
| `get_backup_inventory` | Identify alternate or nearby stock locations |
| `get_supplier_details` | Retrieve supplier info and escalation contacts |
| `temp_gap` | Calculate ambient vs. threshold temperature differences |
| `search_supplier_sops` | Retrieve escalation SOPs from the vector search index |

#### Custom Tools
| Tool | Description |
|------|--------------|
| `check_weather` | Get live or forecasted weather for destination routes |
| `send_email` | Send escalation summaries via **Mailgun** (or any email service API) |
| `send_sms` | Send short alerts via **Twilio SMS** |

---

### Demo Data Sources

| File | Description |
|------|--------------|
| `shipments.csv` | Shipment details, ETA, carrier, and temperature logs |
| `suppliers.csv` | Supplier contacts and escalation references |
| `inventory.csv` | Warehouse and backup inventory data |
| `supplier_sops.csv` | Supplier SOPs and escalation documents (for RAG) |

---

## Installation & Setup

### Prerequisites

* **Databricks workspace** with **Unity Catalog** enabled
* **MLflow 3.0+** with **Model Serving**

#### Optional Custom Tools

* **Mailgun** — for email alerts. Obtain API credentials from your Mailgun account.
* **Twilio** — for SMS alerts. Obtain API credentials from your Twilio account.

> **Note:**
> If you don't plan to use Email or SMS, remove those tools from `weatherwise_agent.py` and update the system prompt accordingly.
> If you do plan to use them, configure the services first, then use `tests/manually_test_tools.ipynb` to verify the integrations before running the agent.

---

### Repository Design

```
databricks.yml                    # Bundle: the Databricks App + the agent eval Lakeflow Job
.env                              # Your config + secrets (gitignored; synced to your workspace folder)
_env                              # Template for .env (no secrets)
setup.sh                          # One-shot setup script (imports notebooks, runs them as jobs)

agent_src/
├── weatherwise_agent.py          # LangGraph ResponsesAgent; LLM via Unity AI Gateway (ChatOpenAI)
├── agent_eval_notebook.ipynb     # Unit test → log → evaluate → register (UC) → deploy (Model Serving)
└── tools/
    ├── uc_tools/                 # UC SQL functions + supplier SOP vector index notebooks
    └── custom_tools/             # check_weather (Open-Meteo), send_email (Mailgun), send_sms (Twilio)

dapp/                             # Databricks App: FastAPI backend + React frontend
├── app.py                        # /api/health · /api/overview · /api/shipments/at-risk
│                                 # /api/genie/ask · /api/agent/chat; serves the built SPA
├── app.yaml                      # Runtime env; valueFrom keys match bundle resource names
├── requirements.txt
├── frontend/                     # Vite + React 19 + lucide (no Tailwind) → builds into dapp/static
│   └── src/components/           # Dashboard · AgentChat · GenieDrawer · Modals · Markdown
└── static/                       # Built SPA (committed so the app deploys without a Node build)

data/                             # setup_data.ipynb + demo CSVs
genie/                            # Scripts to create the SQL warehouse and Genie space
tests/manually_test_tools.ipynb   # Manual tool checks (weather, email, SMS)
img/                              # README / solution-brief screenshots
```

**App layout.** Split screen: live supply-chain dashboard (KPIs, status mix, on-hand by site, at-risk shipments) on the left, WeatherWise agent chat on the right, and **Ask Genie** as a slide-out drawer. Header buttons open **Problem & Solution**, **Outcome Maps** (Life Sciences), and the animated **Data Flow**.

**Bundle resources** (`databricks.yml`, target `dev` by default):

| Resource | Name | Purpose |
|---|---|---|
| App | `weatherwise-chat-agent` | Source `./dapp`; bound to the agent endpoint (`CAN_QUERY`), SQL warehouse (`CAN_USE`), Genie space (`CAN_RUN`) |
| Job | `weatherwise-agent-eval` | Runs `agent_src/agent_eval_notebook.ipynb` on serverless |

Sync rules: `.env` is explicitly **included** (it is gitignored, but the notebook reads it in the workspace); `dapp/frontend/node_modules` is **excluded** (otherwise app deploys hang on "Downloading source code").

---

### 1. Configure Environment

Copy `_env` to `.env` and fill it in. `.env` is gitignored but uploaded to your private workspace folder by the bundle.

| Variable | Used by | Notes |
|---|---|---|
| `TARGET_CATALOG`, `TARGET_SCHEMA` | agent, notebooks | e.g. `bldemos` / `agentbricks_weatherwise` |
| `AGENT_NAME` | notebook, email tool | UC model name `<catalog>.<schema>.<AGENT_NAME>`; email sender name |
| `MLFLOW_EXPERIMENT` | notebook | Experiment under `/Users/<you>/` |
| `VS_INDEX`, `VS_INDEX_BASE_TABLE`, `RETRIEVER_TOOL_NAME` | agent, vector index notebook | SOP retrieval |
| `AI_GATEWAY_MODEL` | agent | e.g. `system.ai.gpt-5-6-sol` (required) |
| `AI_GATEWAY_BASE_URL` | agent | `https://<workspace>/ai-gateway/mlflow/v1` |
| `DATABRICKS_HOST`, `DATABRICKS_TOKEN` | agent | Gateway auth; passed to the serving endpoint at deploy |
| `MAILGUN_API_URL`, `MAILGUN_API_KEY`, `SENDER`, `RECIPIENT` | `send_email` | Optional |
| `SMS_ACCOUNT_SID`, `SMS_AUTH_TOKEN`, `SMS_ACCOUNT_ID` | `send_sms` | Optional. Either an API key (`SK…` + key secret + `SMS_ACCOUNT_ID="AC…"`) or the account SID (`AC…`) + Auth Token |
| `WAREHOUSE_ID`, `GENIE_ID` | reference | The app gets these from bundle resources (`databricks.yml`), not `.env` |

---

### 2. Load Data & Initialize Assets

Run **`data/setup_data.ipynb`** to load the CSVs into **Delta tables**, then:

* **`agent_src/tools/uc_tools/tool_uc_functions.ipynb`** — create the Unity Catalog function tools
* **`agent_src/tools/uc_tools/tool_uc_vector_index.ipynb`** — build the supplier SOP **Vector Search index**

> **Tip:** Review the system prompt in `agent_src/weatherwise_agent.py` to understand the agent's persona, tools, and workflow.

---

### 3. Deploy the Bundle

```bash
databricks bundle validate --profile <PROFILE>
databricks bundle deploy   --profile <PROFILE>
```

This uploads the repo (including `.env`) to `/Workspace/Users/<you>/weatherwise-agent-demo/files`, creates the agent eval job, and configures the app.

---

### 4. Build, Evaluate, Register, and Deploy the Agent

```bash
databricks bundle run agent_eval --profile <PROFILE>
```

The job runs `agent_src/agent_eval_notebook.ipynb` end to end:

| Step | Description |
|------|--------------|
| **a. Setup MLflow** | Set the experiment |
| **b. Import agent** | Load `weatherwise_agent.py` and its tools |
| **c. Unit test** | One full escalation request, traced |
| **d. Log** | `mlflow.pyfunc.log_model` with UC function + vector index resources |
| **e. Evaluate** | `mlflow.genai.evaluate` with Correctness, Safety, RelevanceToQuery, Guidelines |
| **f. Register** | New version of `<catalog>.<schema>.<AGENT_NAME>` in Unity Catalog |
| **g. Deploy** | `agents.deploy` → endpoint `agents_<catalog>-<schema>-<AGENT_NAME>` (15–25 min to become READY) |

You can also open the notebook in the workspace and run it interactively.

---

### 5. Deploy the App

```bash
cd dapp/frontend && npm install && npm run build && cd -   # only after UI changes
databricks bundle deploy --profile <PROFILE>
databricks bundle run weatherwise_chatapp --profile <PROFILE>
```

Local development: run `uvicorn app:app --port 8000` in `dapp/` (with `WAREHOUSE_ID`, `GENIE_SPACE_ID`, `SERVING_ENDPOINT` set) and `npm run dev` in `dapp/frontend/` (Vite proxies `/api` to port 8000).

---

© 2025 — *Authored by Bobby Leach*
