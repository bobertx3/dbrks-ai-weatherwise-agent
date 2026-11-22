# Handoff — WeatherWise UI rebuild (session of 2026-11-18)

Context for the next Claude Code session in this repo. Delete this file once the work lands.

## Decisions already made
- **Work on `dev`** (checked out; up to date with `origin/dev`, 1 commit ahead of `main`: "updates for unity ai gateway").
- **Replace `chatapp/` with the FastAPI + React app built last session** (user: "I like the app you built so far, so you can replace it").
- **LLM: use GPT, not Sonnet**, through the **Unity AI Gateway**.
- Exec-demo bar: dark "mission control" theme, readable from ~6 ft, no paragraphs on slides/modals.

## Where the app to port lives (source of truth)
`/Users/robert.leach/dev/repos/jnj_vision/supply-chain-e2e-bundle/jnj_vision/src/jnj_vision/mosaic_ai_weatherwise_agent_demo/`
(a stray uncommitted copy — **it was the wrong repo**; nothing there is committed.)

Copy from it:
- `dapp/` — `app.py` (FastAPI: `/api/health`, `/api/overview`, `/api/shipments/at-risk`, `/api/genie/ask`, `/api/agent/chat`), `app.yaml`, `requirements.txt`, `.databricksignore`, `model_serving_utils.py`, `frontend/` (Vite + React 19 + lucide, **no Tailwind**, builds to `dapp/static`), `static/`.
  - Do **not** copy `dapp/frontend/node_modules` — run `npm install` here.
- `resources/weatherwise_app.app.yml` — app resource with `serving-endpoint`, `sql-warehouse`, `genie-space` (names must match `valueFrom` keys in `dapp/app.yaml`).
- From its `databricks.yml`: variables `agent_endpoint_name`, `warehouse_id`, `genie_space_id`, and
  ```yaml
  sync:
    exclude:
      - dapp/frontend/node_modules
      - .env
  ```
  Without the exclude, ~2,300 node_modules files get uploaded and the app deployment hangs 10+ min on "Downloading source code".

## UI state (all built + verified in a local preview)
- Main page: split screen — dashboard (KPIs, status mix, on-hand by site, at-risk table) left, WeatherWise agent chat right; Genie is a slide-out drawer.
- Header buttons: Problem & Solution · Outcome Maps · Data Flow · Ask Genie.
- **Problem & Solution**: two big boxes + 4 large "from → to" rows. Framing = temperature-controlled medtech/pharma shipments needed for surgery (examples as subtext: implants, heart valves, biologics, vaccines). Not "weather" only.
- **Outcome Maps**: wording must match the user's Life Sciences image exactly — tab "Life Sciences"; columns: Increase R&D Productivity (Accelerate Drug Discovery, Streamline Clinical Development, Build a FAIR Data Platform) · Optimize Supply Chain & Manufacturing (Create E2E Supply Chain Visibility [highlighted "This app"], Implement Smart Manufacturing) · Improve Commercial Effectiveness (Generate Real World Evidence, Deliver Provider Next-Best-Action, Personalize Patient Engagement).
- **Data Flow** (replaced "Architecture"; user wanted a flow, not a stack): left→right Source data → Unity Catalog governed lakehouse → MLflow + Model Serving agent with tools + Genie → Databricks App → coordinator. Style inspired by the patient-AI architecture screenshot, but dark.

## Not finished
1. **Genie formatting** — answers show literal `**bold**`. A dependency-free renderer was written at `dapp/frontend/src/components/Markdown.tsx` in the source folder, but the edit wiring it into `GenieDrawer.tsx` / `AgentChat.tsx` was **not applied** (user interrupted). Plan: render Markdown in Genie + agent answers; show result tables inline when ≤25 rows; right-align/format numeric columns; prettify column names.
2. **Add a separate "Unity Gateway" box to the Data Flow modal** (between the agent and the LLM).
3. **Unity Gateway refactor** — `dev` already calls `system.ai.gpt-5-6-sol` via `/ai-gateway/mlflow/v1` (`AI_GATEWAY_MODEL` in `_env`, `ChatOpenAI` in `agent_src/weatherwise_agent.py`). Decide with the user whether to go further and create a governed **UC model service** (pattern: `/Users/robert.leach/dev/vibe/dbrks-IM-patient-AI/notebooks/02b_setup_ai_gateway.ipynb` — `POST /api/2.1/unity-catalog/model-services`, routes to a pay-per-token model, inference table, `EXECUTE` grant to the agent's SP; agent calls `model="<catalog>.<schema>.<service>"`). The model-services API works in this workspace; `bldemos.agentbricks_weatherwise` has none yet. Redeploying the agent endpoint replaces the live demo — confirm first.
4. **Commit** — nothing has been committed anywhere. Commit only when the user asks.

## Live workspace facts (DEFAULT profile → fevm-bobertx3-aws-fevm)
- Data: `bldemos.agentbricks_weatherwise` — `shipments`, `inventory`, `suppliers`, `supplier_sops`, `supplier_sops_vs_index`, `weatherwise_payload` (AI Gateway inference table); UC functions `get_shipments`, `get_backup_inventory`, `get_supplier_details`, `temp_gap`.
- Agent endpoint: `agents_bldemos-agentbricks_weatherwise-weatherwise` (READY, model `bldemos.agentbricks_weatherwise.weatherwise` v6).
- Warehouse used by the stray app: `c7a42574bb619744` (bldemos_dev). This repo's bundle defaults to `35670cdf44904d28` — reconcile.
- Genie space: `01f170fcaf40172a87ed6c9398d7f2d5` ("WeatherWise Supply Chain Explorer").
- Stray app deployed last session: `weatherwise-app-dev` (from the wrong repo's bundle `weatherwise_agent`). This repo's app is `weatherwise-chat-agent`. Decide which to keep; avoid two bundles fighting over one app.
- A browser tab is still polling an old Streamlit build (`/_stcore/stream` 403s in app logs) — close it.

## Findings to remember
- **Traces are NOT bound to Unity Catalog.** Endpoint sends traces to experiment `3010572798221570` (`/Users/robert.leach@databricks.com/weather_agent_tests`, no UC location). No `agent_traces_otel_*` tables exist; `MLFLOW_TRACING_SQL_WAREHOUSE_ID` is unset. Binding code exists in the other folder's `agent_src/uc_trace_setup.py` (`mlflow.set_experiment(..., trace_location=UnityCatalog(...))`).
- **Twilio SMS is broken:** `SMS_ACCOUNT_SID` is an API Key SID (`SK…`), not an Account SID (`AC…`) → Twilio 401 code 8011. Fix: provide the `AC…` SID + auth token, or use `Client(api_key_sid, api_key_secret, account_sid)`. Test SMS to +1 301-908-5817 has **not** succeeded yet. Local `pip` can't reach PyPI (SSL handshake failure); test via curl to the Twilio REST API instead.
- Agent tools: `get_shipments`, `get_backup_inventory`, `get_supplier_details`, `temp_gap` (UC), `search_supplier_sops` (Vector Search), `check_weather` (Open-Meteo), `send_email` (Mailgun), `send_sms` (Twilio).

## Reference repos
- Style / Genie drawer: `/Users/robert.leach/dev/vibe/dbrks-robot-predictive-maintenance-ml-ai/apx-app/src/jnj_dsp2_gold_genie/ui` (mission-control palette in `styles/globals.css`, `components/mc/*`).
- Data-flow + Unity Gateway: `/Users/robert.leach/dev/vibe/dbrks-IM-patient-AI`.
- Gateway concept slide: `/Users/robert.leach/dev/vibe/DOC-JNJ-RFP-Data-Science-IM/deck/src/slides.html` (slide 09 "Unity Gateway").
