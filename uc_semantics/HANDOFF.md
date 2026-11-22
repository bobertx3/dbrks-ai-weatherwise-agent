# Handoff: UC Semantics (Metric View + Page), 2026-11-18

Context for the next agent. The root `HANDOFF.md` covers the separate UI rebuild, so don't confuse the two. Delete this file once the work lands.

## Goal
Add **Unity Catalog semantics** for WeatherWise: a governed **Metric View** and a **Page** (Genie Ontology modeled knowledge). The idea comes from the "Genie Ontology" slide in `/Users/robert.leach/dev/vibe/DOC-JNJ-RFP-Data-Science-IM/deck/src/slides.html`, where certified pages hold the definitions and metric views hold the KPIs.

## Environment (user-confirmed)
- **CLI profile: `DEFAULT`** → `https://fevm-bobertx3-aws-fevm.cloud.databricks.com` (workspace `o=7474645374628060`). Don't pick a different profile without asking.
- Catalog/schema: `bldemos.agentbricks_weatherwise` (from `.env`; `.env` takes precedence over `_env`).
- Warehouse: use **`35670cdf44904d28`** (Serverless Starter, running). `.env` `WAREHOUSE_ID=c7a42574bb619744` (`bldemos_dev`) is stopped.
- Page domain: **Supply Chain** = `domains/b530da5f-dc5d-4833-909d-e3971e0e76bb` (given by the user).

## Files in `uc_semantics/`
| File | Purpose |
|------|---------|
| `shipment_risk_metrics.metric_view.sql` | `CREATE OR REPLACE VIEW … WITH METRICS LANGUAGE YAML`, version 1.1. Source `shipments`. Joins `dim_weather` (`weather_forecast` on `destination = concat(city, ', ', state)`, one row per city) and `dim_supplier`. 19 dimensions, 13 measures, all with comment, synonyms and format. Uses `__CATALOG__`/`__SCHEMA__` placeholders. |
| `deploy.sh` | Fills in the placeholders and runs the SQL through `/api/2.0/sql/statements`, polling until it finishes. `--dry-run` prints the rendered SQL and the Page. |
| `page_cold_chain_shipment_risk.md` | Page source. The frontmatter matches the Page editor (display_name, domain, owner, state, synonyms, description, related_assets, sources). The body has `## Definition`, `## Business use`, `## Examples`, following the docs example Page. |
| `create_page.py` | Creates the Page with `POST /api/2.0/knowledge/pages` (Beta), or updates it with PATCH plus `update_mask` if the ID is in `.page_state.json`. Then adds asset links with `POST /api/2.0/knowledge/pages/{id}/asset-link-categories/{RELATED_ASSETS\|SOURCE}/asset-links` (`ASSET_TYPE_UC_TABLE`, scope = metastore ID, asset_id = FQN). Duplicate links return the existing link, so re-running is safe. Auth goes through `databricks api` with `--profile`; no raw tokens. |
| `.page_state.json` | Cache of the created page name. Keep it, or the next run creates a duplicate draft. |

## Status
- ✅ **Page created as a DRAFT**: `pages/778b3398-ee28-4303-8b49-7f26a6fa21d9` "Cold-Chain Shipment Risk". Read back OK: domain, 6 synonyms and the 3 body sections are all there. The user chose draft. Publish from the UI, or run `create_page.py --publish` (needs MANAGE PAGES).
  - Linked: RELATED_ASSETS `shipments`, `inventory`; SOURCE `shipments`, `suppliers`, `supplier_sops`.
  - **Not linked yet** (table missing): RELATED_ASSETS `shipment_risk_metrics`, `weather_forecast`; SOURCE `weather_forecast`.
- ❌ **Metric view not created.** It failed with `TABLE_OR_VIEW_NOT_FOUND: weather_forecast`.
  - **Root cause: the workspace schema is older than the repo's `data/`.** Deployed tables: `inventory, shipments, supplier_sops, supplier_sops_vs_index, suppliers, weatherwise_payload`. `weather_forecast`, `sites` and `facilities` are missing. The deployed `shipments` has only the original 13 columns. The view also needs `priority, delay_hours, procedure_date, last_recorded_temp_f, delay_reason, destination_facility_*, route_miles`.
- Checked locally against the CSVs: 10 temperature excursions; 112 weather-at-risk active shipments (25 STAT). New York's forecast high is 62°F against a 46°F max. Every destination has a forecast row.

## Next steps
1. **Ask the user before reloading data.** `data/setup_data.ipynb` runs `CREATE OR REPLACE` on `shipments`, `suppliers`, `inventory`, `sites`, `facilities` and `weather_forecast`. The live agent and app read those tables, so the demo will change.
2. After the reload:
   ```bash
   ./uc_semantics/deploy.sh --profile DEFAULT --warehouse-id 35670cdf44904d28
   python3 uc_semantics/create_page.py --profile DEFAULT   # updates the page + adds the 3 missing links
   ```
3. Validate the view, for example
   `SELECT Destination, MEASURE(\`Weather At-Risk Shipments\`), MEASURE(\`STAT At-Risk Shipments\`), MEASURE(\`Temperature Excursions\`) FROM bldemos.agentbricks_weatherwise.shipment_risk_metrics GROUP BY ALL`.
   Expect totals of 112 / 25 / 10, provided the reload uses the current CSVs.
4. Optional: add `shipment_risk_metrics` to the Genie space (`genie/setup_genie_space.sh`), certify the Page, and mention `uc_semantics/` in the README.

## Gotchas
- `synonyms`, `display_name` and `format` in the metric view need DBR 17.3+. Every `format` block must include `type`.
- Pages API: `display_name` must be unique among *published* pages in the domain. `owner_ids` takes decimal principal IDs, not emails. Don't put PII in Pages (they're replicated account-wide).
- Nothing is committed. Commit only when the user asks.
