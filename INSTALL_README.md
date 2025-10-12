# ⚙️ INSTALLATION & SETUP: WeatherWise Supply Chain Escalation Agent

Quick guide to configure, run, and deploy the **WeatherWise Supply Chain Escalation Agent**.

---

## 🎯 PREREQUISITES

* **Databricks workspace** with **Unity Catalog** enabled.  
* **MLflow 3.0+** with **Model Serving**.

### Optional Custom Tools

* **AWS SES** — for email alerts. Refer to the AWS SES documentation to create the service and obtain API credentials.  
* **Twilio** — for SMS alerts. Refer to the Twilio documentation to create the service and obtain API credentials.

> **Note:**  
> • If you don’t plan to use Email or SMS, remove those tools from `supply_chain_agent.py` and update the system prompt accordingly.  
> • If you do plan to use them, configure AWS SES and Twilio first, then use **`tests/manually_test_tools.ipynb`** to verify the integrations before running the agent.

---

## 🗂️ REPOSITORY STRUCTURE
```
/agent_src
├── tools/                     # Tool logic
│   ├── uc_tools/              # UC SQL functions & vector index creation
│   ├── custom_tools/          # Weather, Email (SES), SMS (Twilio) tools
├── supply_chain_agent.py      # Core LangGraph agent
├── agent_eval.ipynb           # Testing, evaluation, registration, and deployment
├── data/
│   ├── setup_data.ipynb       # Data & Unity Catalog setup
│   ├── *.csv                  # Demo data files
├── tests/
│   ├── manually_test_tools.ipynb  # Manual tool testing
├── .env                       # Environment variables
```
---

## 🚀 INSTALLATION STEPS

### 1️⃣ Configure Environment

Update your **`.env`** file with all required credentials and environment variables.

---

### 2️⃣ Load Data & Initialize Assets

Run **`data/setup_data.ipynb`** to:
* Load CSV files into **Delta tables**  
* Create **Unity Catalog functions**  
* Build the **Vector Search index**  
* Apply required access grants

---

### 3️⃣ Create Tools

> **Tip:**  
> Before creating tools, inspect the system prompt in `agent_src/supply_chain_agent.py`to understand the agent’s persona, tools, and workflow.

* Open **`agent_src/tools/tool_uc_functions.ipynb`** and run each cell to create Unity Catalog tools.  
* Open **`agent_src/tools/tool_uc_vector_index.ipynb`** and run each cell to create the Vector Search index.

---

### 4️⃣ Build, Test, and Deploy the Agent

> **Tip:**  
> Review the system prompt and `LLM_ENDPOINT` in `agent_src/supply_chain_agent.py` and modify them as needed.

Open **`agent_src/agent_eval.ipynb`** and run all cells sequentially.  
This notebook handles evaluation, testing, registration, and deployment.

| Step | Description |
|------|--------------|
| **a. Setup MLflow** | Initialize experiment tracking. |
| **b. Import Agent** | Load logic from `supply_chain_agent.py`. |
| **c. Unit Tests** | Validate tools, data pipelines, and logic. |
| **d. Run Evals** | Use `mlflow.genai` for model evaluation. |
| **e. Register Model** | Register the agent to Unity Catalog. |
| **f. Deploy** | Launch the agent via Databricks **Model Serving**. |

---

© 2025 — *Authored by Bobby Leach*  