# bx_repo_scaffolding — Scaffold a bobertx3 Demo Project

Scaffold a new Databricks agent demo project following the bobertx3 standard layout. This creates the full repo structure, configs, and placeholder files for a polished, demo-ready Databricks App.

## Usage

`/bx_repo_scaffolding <project-name> <domain-description>`

Example: `/bx_repo_scaffolding pharma_compliance "Pharmaceutical compliance monitoring agent that checks FDA regulations"`

---

## Step 1: Gather Context

Ask the user for:
1. **Project name** (snake_case, e.g., `weatherwise`, `pharma_compliance`)
2. **Domain description** (one sentence: what the agent does)
3. **Target catalog** (Unity Catalog name, default: `bx4`)
4. **Target schema** (default: `agentbricks_<project_name>`)
5. **LLM endpoint** (default: `databricks-gpt-5-4`)
6. **Agent personas** (list of 3-6 specialist roles the agent embodies)
7. **Tools needed**:
   - UC Functions (SQL-backed queries)
   - Vector Search (RAG over documents)
   - Custom Python tools (external API integrations)
8. **Demo data entities** (e.g., shipments, suppliers, inventory)
9. **External APIs** (e.g., weather, email/Mailgun, SMS/Twilio)

---

## Step 2: Create Directory Structure

Create this exact layout:

```
<project_name>/
├── agent_src/
│   ├── <project_name>_agent.py
│   ├── agent_eval_notebook.ipynb
│   └── tools/
│       ├── __init__.py
│       ├── uc_tools/
│       │   ├── __init__.py
│       │   ├── tool_uc_functions.ipynb
│       │   └── tool_uc_vector_index.ipynb
│       └── custom_tools/
│           ├── __init__.py
│           └── (one .py file per custom tool)
├── chatapp/
│   ├── app.yaml
│   ├── databricks.yml          (optional, for nested DAB)
│   ├── package.json
│   ├── client/
│   │   └── src/
│   │       ├── App.tsx
│   │       ├── main.tsx
│   │       ├── index.css
│   │       ├── pages/
│   │       │   ├── ChatPage.tsx
│   │       │   ├── NewChatPage.tsx
│   │       │   ├── DashboardPage.tsx
│   │       │   └── GeniePage.tsx
│   │       ├── layouts/
│   │       │   ├── RootLayout.tsx
│   │       │   └── ChatLayout.tsx
│   │       ├── components/
│   │       │   ├── chat.tsx
│   │       │   ├── messages.tsx
│   │       │   ├── message.tsx
│   │       │   ├── chat-header.tsx
│   │       │   ├── app-sidebar.tsx
│   │       │   ├── agent-flow-modal.tsx
│   │       │   ├── multimodal-input.tsx
│   │       │   ├── follow-up-actions.tsx
│   │       │   ├── greeting.tsx
│   │       │   ├── animation-assistant-icon.tsx
│   │       │   ├── tool-renderers/
│   │       │   │   ├── index.tsx
│   │       │   │   └── (one .tsx per tool renderer)
│   │       │   ├── dashboard/
│   │       │   │   ├── status-cards.tsx
│   │       │   │   └── (domain-specific dashboard components)
│   │       │   ├── genie/
│   │       │   │   └── genie-result.tsx
│   │       │   ├── elements/
│   │       │   │   ├── tool.tsx
│   │       │   │   ├── mcp-tool.tsx
│   │       │   │   └── code-block.tsx
│   │       │   └── ui/           (shadcn/ui primitives)
│   │       ├── contexts/
│   │       │   ├── SessionContext.tsx
│   │       │   └── AppConfigContext.tsx
│   │       ├── hooks/
│   │       │   ├── useMessages.tsx
│   │       │   ├── use-scroll-to-bottom.tsx
│   │       │   └── useChatData.ts
│   │       └── lib/
│   │           ├── utils.ts
│   │           └── ChatTransport.ts
│   ├── server/
│   │   └── src/
│   │       ├── index.ts
│   │       ├── env.ts
│   │       ├── routes/
│   │       │   ├── chat.ts
│   │       │   ├── dashboard.ts
│   │       │   ├── genie.ts
│   │       │   ├── session.ts
│   │       │   ├── config.ts
│   │       │   ├── history.ts
│   │       │   ├── messages.ts
│   │       │   └── feedback.ts
│   │       └── middleware/
│   │           └── auth.ts
│   ├── packages/
│   │   ├── core/               (shared schemas, AI provider, types)
│   │   ├── auth/               (Databricks OAuth)
│   │   ├── utils/              (host utilities)
│   │   ├── ai-sdk-providers/   (AI SDK config)
│   │   └── db/                 (Drizzle ORM, migrations)
│   └── scripts/                (DB migrations, startup)
├── data/
│   ├── setup_data.ipynb
│   └── *.csv                   (one CSV per demo entity)
├── genie/                      (Genie Space setup scripts)
├── img/
│   ├── agent_flow.png
│   ├── arch.png
│   ├── manual_flow.png
│   └── 01_*.png, 02_*.png...  (numbered screenshots)
├── tests/
│   └── manually_test_tools.ipynb
├── .env                        (.gitignored, real secrets)
├── _env                        (committed template with placeholders)
├── .gitignore
├── setup.sh
├── databricks.yml
├── SKILL.md                    (project design patterns doc)
└── README.md
```

---

## Step 3: Create Core Config Files

### `_env` (Template)

```bash
# Databricks
TARGET_CATALOG="<your_catalog>"
TARGET_SCHEMA="agentbricks_<project_name>"
LLM_ENDPOINT_NAME="databricks-gpt-5-4"
MLFLOW_EXPERIMENT="<project_name>_agent_tests"
VS_INDEX_BASE_TABLE="<vector_search_source_table>"
VS_INDEX="<vector_search_index_name>"
RETRIEVER_TOOL_NAME="search_<domain>_docs"
AGENT_NAME="<project_name>"
APP_NAME="<project_name>_chat_agent"

# External APIs (if needed)
# MAILGUN_API_URL="https://api.mailgun.net/v3/<domain>/messages"
# MAILGUN_API_KEY="<your_key>"
# SENDER="<sender_email>"
# RECIPIENT="<default_recipient>"
# SMS_ACCOUNT_SID="<twilio_sid>"
# SMS_AUTH_TOKEN="<twilio_token>"
```

### `databricks.yml`

```yaml
bundle:
  name: <project-name>-demo

workspace:
  root_path: /Workspace/Users/${workspace.current_user.userName}/<project-name>-demo

variables:
  serving_endpoint_name:
    description: "Agent model serving endpoint"
    default: "agents_<catalog>-<schema>-<agent_name>"
  sql_warehouse_id:
    description: "SQL warehouse for dashboard and Genie"
    default: "<warehouse_id>"
  resource_name_suffix:
    description: "Environment suffix for resource names"

resources:
  apps:
    <project_name>_chatapp:
      name: <project-display-name>-${var.resource_name_suffix}
      source_code_path: ./chatapp
      resources:
        - name: serving-endpoint
          serving_endpoint:
            name: ${var.serving_endpoint_name}
            permission: CAN_QUERY
        - name: sql-warehouse
          sql_warehouse:
            id: ${var.sql_warehouse_id}
            permission: CAN_USE

targets:
  dev:
    mode: development
    default: true
    variables:
      resource_name_suffix: dev-${workspace.current_user.short_name}
  staging:
    mode: production
    variables:
      resource_name_suffix: staging
  prod:
    mode: production
    variables:
      resource_name_suffix: prod
```

### `chatapp/app.yaml`

```yaml
command: ["npm", "run", "start"]
runtime: nodejs20

env:
  - name: DATABRICKS_SERVING_ENDPOINT
  - name: DATABRICKS_SQL_WAREHOUSE_ID
  - name: DATABRICKS_GENIE_SPACE_ID
    value: "<genie_space_id>"
```

### `setup.sh`

Create a comprehensive bash script that:
1. Validates Databricks CLI and auth
2. Loads `.env` or `_env`
3. Creates catalog, schema, volume in Unity Catalog
4. Loads CSV data to Delta tables
5. Creates UC SQL functions (runs `tool_uc_functions.ipynb`)
6. Creates Vector Search endpoint and index (runs `tool_uc_vector_index.ipynb`)
7. Runs agent eval notebook (logs, registers, deploys)
8. Outputs serving endpoint URL

Support flags: `--cluster-id <id>` and `--manual` (just import notebooks).

### `.gitignore`

```
.env
.DS_Store
node_modules/
dist/
.venv/
venv/
__pycache__/
*.pyc
*.egg-info/
.databricks/
```

---

## Step 4: Create Data Files

### `data/setup_data.ipynb`

Notebook that:
1. Creates `{catalog}.{schema}` if not exists
2. Creates managed volume `{catalog}.{schema}.data`
3. Grants permissions: `USE SCHEMA, SELECT, EXECUTE, READ VOLUME` to all account users
4. Uploads each CSV to volume, then loads to Delta table with `COPY INTO` or `spark.read.csv`
5. Enables Change Data Feed on the vector search source table
6. Creates the Vector Search endpoint (waits for ONLINE status)

### CSV Files

Create one CSV per demo entity with 10+ realistic records. Use domain-appropriate IDs (e.g., `SHP-30001`, `SUP-2041`), realistic names, dates near today, and varied statuses.

---

## Step 5: Verify Completeness

Run through the bobertx3 checklist:
- [ ] `data/` with CSVs and `setup_data.ipynb`
- [ ] `img/` directory created (screenshots added later)
- [ ] `agent_src/` with agent file, eval notebook, and tools subdirs
- [ ] `chatapp/` scaffolded with app.yaml
- [ ] `setup.sh` with full automation
- [ ] `_env` template committed, `.env` in `.gitignore`
- [ ] `databricks.yml` with app + serving endpoint + warehouse resources
- [ ] `tests/manually_test_tools.ipynb` placeholder
- [ ] `README.md` skeleton with standard sections
- [ ] `SKILL.md` documenting project patterns

---

## Key Conventions

- **`_env`** is committed. **`.env`** is gitignored with real secrets.
- **Agent name** is the project name in snake_case.
- **UC schema** follows `agentbricks_<project_name>` pattern.
- **img/** always includes `agent_flow.png`, `arch.png`, `manual_flow.png`, plus numbered screenshots.
- **All environment variables** are loaded via `python-dotenv` in agent code and via `process.env` in Node.js.
- **Monorepo chatapp** uses npm workspaces with packages: core, auth, utils, ai-sdk-providers, db.
- **React frontend** uses Vite + TailwindCSS + shadcn/ui + Framer Motion.
- **Express backend** uses TypeScript with route files per feature domain.
