# Handoff: synthetic data, Network Map, setup job, Genie, SMS (session of 2026-11-18)

Written for the agent doing the repo refactor. It covers work done in a parallel session so it doesn't get overwritten. Read it alongside `HANDOFF.md`. **Nothing here is committed.** Commit only when the user asks.

Workspace: `DEFAULT` profile (fevm-bobertx3-aws-fevm). Data lives in `bldemos.agentbricks_weatherwise`.

---

## 1. Corrections to `HANDOFF.md`

- **Twilio SMS works now.** The "Twilio SMS is broken" bullet is out of date. The user rotated the keys in `.env`, and an SMS to +1 301-908-5817 was delivered. Use only `SMS_ACCOUNT_SID` (an `SK…` API key SID) and `SMS_AUTH_TOKEN` (its secret). No `AC…` account SID is needed.
- **Warehouse:** there is now one warehouse, `c7a42574bb619744` (`bldemos_dev`, from `WAREHOUSE_ID` in `.env`). The bundle variable `sql_warehouse_id` default was changed from `35670cdf44904d28` to it. The app resource, the setup job and the Genie space all use it.

## 2. Changes made in this session (keep these when refactoring)

### Agent code
- `agent_src/tools/custom_tools/tool_send_sms.py`: every SMS now starts with `SMS_GREETING = "Hi from the WeatherWise Agent. Welcome to DAIWT NYC!"`, then a newline, then the agent's message. The tool was tested directly, not through an agent run, and the text was delivered. **The live agent endpoint does not have this yet.** It needs an `agent_eval` job run (see §5).
- `tests/manually_test_tools.ipynb`: the Twilio cell now sends to +13019085817 from +18773559479 and checks the delivery status. It supports optional `SMS_ACCOUNT_ID` (`AC…`) and `SMS_MESSAGING_SERVICE_SID` (`MG…`).
- Pending: the user may rename the env vars to `TWILIO_API_KEY_SID` / `TWILIO_API_KEY_SECRET`. If so, update `tool_send_sms.py`, both notebooks, `_env` and `.claude/commands/bx_repo_scaffolding.md`.

### Synthetic data (`data/`)
- **`data/generate_synthetic_data.py` (new)** generates the data with seed 42 and demo date **2026-11-18**. The forecast is for 2026-11-19, with NYC at **62°F / 44°F** as given by the user. Run `python3 data/generate_synthetic_data.py`.
- Tables it writes:
  - `sites.csv` (new): 25 sites (10 supply centers, 15 distribution centers) with lat/lon. SITE-201 to 210 keep their original names.
  - `facilities.csv` (new): 60 facilities (38 hospitals, 22 clinics) with lat/lon and `serving_site_id`.
  - `weather_forecast.csv` (new).
  - `inventory.csv`: same columns as before, 105 rows, expiry dates in the future.
  - `shipments.csv`: 150 rows. The original 13 columns are unchanged, plus new columns `original_eta_date, delay_hours, delay_reason, priority, procedure_date, last_recorded_temp_f, destination_facility_id/name/type, routed_via_site_id, origin/destination lat/lon, route_miles`.
- **`suppliers.csv` and `supplier_sops.csv` are intentionally unchanged.** The user doesn't want new SOPs or suppliers. Every product/supplier pair in the generated data exists in the SOPs.
- `temperature_max_f` / `temperature_min_f` are now **46 / 36°F**, matching the SOPs. The old 25–34 values were wrong.
- NYC boroughs all use `destination = 'New York, NY'` so `get_shipments('NYC')` still matches.
- The first four shipments are planned NYC demo examples:
  - SHP-30001: aortic valve held on a warm dock at JFK, 48.7°F.
  - SHP-30002: hip implant with a reefer fault, 49.2°F.
  - SHP-30003 and SHP-30004: miss their 11-19 surgery.
- `data/setup_data.ipynb` now loads `sites`, `facilities` and `weather_forecast`, and has a note explaining how to regenerate the data.

### UC semantics + Genie (`uc_semantics/`)
- `deploy_metric_view.py` (new): job version of `deploy.sh`. It fills in `__CATALOG__`/`__SCHEMA__` from `.env` and runs the SQL on the `warehouse_id` parameter.
- `genie_space.json` (new): the Genie space config. It has 7 tables plus the `shipment_risk_metrics` metric view, column configs, one text instruction, 4 example SQLs, 6 join specs and 6 sample questions, with fixed IDs. **Use version 2 column fields only** (`enable_format_assistance`, `enable_entity_matching`). `get_example_values` / `build_value_dictionary` are rejected. Table-level `description` was removed to be safe.
- `deploy_genie_space.py` (new): sorts the JSON the way the API requires and **PATCHes the existing space `GENIE_ID`** from `.env` (`01f170fcaf40172a87ed6c9398d7f2d5`, so the ID stays the same). It POSTs a new space only if `GENIE_ID` is empty.
- `genie/setup_genie_space.sh` is now redundant. It can only create spaces and reads env var names `.env` doesn't use.

### Bundle (`databricks.yml`)
- New job **`setup`** ("weatherwise-setup", serverless). Task order: `setup_data`, then `uc_semantics` and `uc_functions` in parallel, then `genie_space` after `uc_semantics`. The two `uc_semantics` tasks receive `warehouse_id: ${var.sql_warehouse_id}`.
- The `tool_uc_vector_index.ipynb` notebook is disabled (its first cell exits), so the job doesn't include it.
- The deployed job ID is `687464134404580`. The bundle was deployed with `--profile DEFAULT`.

### App (`dapp/`)
- **New Network Map page:** `frontend/src/components/NetworkMap.tsx`, with a "Command Center | Network Map" switch in `App.tsx`. Types are in `api.ts` and styles at the end of `styles.css`.
  - It uses `leaflet` + `react-leaflet` (added to `package.json`).
  - The basemap is **Esri World_Dark_Gray (keyless)**. CARTO dark tiles now show an "API KEY REQUIRED" watermark in browsers.
  - Features: layer toggles, US/Northeast/NYC views, at-risk route lines, a "Surgeries at risk" list that flies to the facility, and detail cards.
- **`app.py`:**
  - New `GET /api/map` endpoint. Setting `MAP_CSV_DIR=../data` makes it read the CSVs for local preview.
  - **Excursion logic changed** in `/api/overview` and `/api/shipments/at-risk` to `last_recorded_temp_f > temperature_max_f`. The old `temperature_max_f > TEMP_CEILING_F(30)` would flag every row with the new data.
  - `at-risk` now returns `last_recorded_temp_f`, and the Dashboard column is "Sensor °F".
- `dapp/static` was rebuilt and the app **redeployed** (`weatherwise-chat-agent`, deployment succeeded, clean start). The UI was **not checked in a browser after deploy** because Okta MFA blocked automation. The user should check both pages.

## 3. Current live state (verified 2026-11-18)

- **Setup job run `61712134996579` succeeded.** The Genie task first failed on v1 column fields, then succeeded on repair.
- **Live tables:** 150 shipments, 37 delayed, 10 excursions, 25 sites, 60 facilities, 129 active routes with coordinates.
  - NYC forecast row: 62/44.
  - The metric view runs.
  - `get_shipments('NYC','delayed')` returns 17.
  - `account users` has schema grants.
- **Genie space `01f170fc…`:** 7 tables plus the metric view (stored under `tables`), 6 sample questions, 6 join specs, warehouse `c7a42…`. Asked "Which STAT shipments to NYC will arrive after their scheduled surgery?", it returned SHP-30003 and SHP-30004, which is correct.

## 4. Open issues: small data fixes (user wants these next)

1. **"Procedures at Risk" definitions don't match.** The metric view gives **48**, while the map and Genie give **4**.
   - The metric view (`uc_semantics/shipment_risk_metrics.metric_view.sql`) counts active shipments where the destination forecast high is above `temperature_max_f` AND `DATEDIFF(procedure_date, eta_date) <= 1`. The NYC heat (62 > 46) catches almost every NYC shipment.
   - The map (`app.py`) and Genie instructions count shipments where `eta_date > procedure_date`.
   - Agree one definition with the user, then align the metric view, `genie_space.json`, `app.py` and `uc_semantics/page_cold_chain_shipment_risk.md`.
2. **The agent can't see the new columns.** `get_shipments` in `agent_src/tools/uc_tools/tool_uc_functions.ipynb` returns only its original 8 columns. Add `delay_reason, delay_hours, priority, procedure_date, last_recorded_temp_f, destination_facility_name, original_eta_date`. Update the RETURNS TABLE, then re-run the job's `uc_functions` task.
3. **The SOP vector index may need a sync.** `supplier_sops` was rebuilt by `CREATE OR REPLACE` (content unchanged). The index notebook is disabled.
4. **`TEMP_CEILING_F=30` in `dapp/app.yaml` is now unused** for excursions (it's still returned by `/api/health`). Remove it or repurpose it.
5. **The agent's `check_weather` uses live Open-Meteo**, not the synthetic `weather_forecast` table, so the agent reports real NYC weather, not 62/44.

## 5. Other follow-ups

- **The live agent endpoint still runs the old code** (no SMS greeting). Running the `agent_eval` job logs the agent, runs the eval, registers a **new UC version (after v6)** and redeploys the endpoint, which **replaces the live demo agent**. `bundle deploy` alone never registers anything. Confirm with the user first.
- **Ask Genie / agent chat** in the app were not tested after deploy.
