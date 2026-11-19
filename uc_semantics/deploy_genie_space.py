# Databricks notebook source
# MAGIC %md
# MAGIC # Deploy the WeatherWise Genie space
# MAGIC
# MAGIC Applies `genie_space.json` (tables, metric view, column configs, instructions, example SQL,
# MAGIC join specs, sample questions) to the Genie space:
# MAGIC
# MAGIC - **Updates in place** the space in `GENIE_ID` from the bundle-synced `.env` (so the app's
# MAGIC   Ask Genie drawer keeps the same space ID), or
# MAGIC - **creates** a new space when `GENIE_ID` is empty and prints the new ID to put in `.env`
# MAGIC   and in the bundle's `genie_space_id` variable.
# MAGIC
# MAGIC `__CATALOG__` / `__SCHEMA__` are replaced with `TARGET_CATALOG` / `TARGET_SCHEMA`.
# MAGIC Run after the tables and the `shipment_risk_metrics` metric view exist.
# MAGIC
# MAGIC Parameter `warehouse_id` — defaults to `WAREHOUSE_ID` / `DATABRICKS_SQL_WAREHOUSE_ID` from `.env`.

# COMMAND ----------

import json
import os
from pathlib import Path

from databricks.sdk import WorkspaceClient

dbutils.widgets.text("warehouse_id", "")

HERE = Path(os.getcwd())          # notebook directory: <bundle root>/uc_semantics
ROOT = HERE.parent


def read_env() -> dict:
    for name in (".env", "_env"):
        p = ROOT / name
        if p.exists():
            env = {}
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
            print(f"Loaded config from {p}")
            return env
    raise FileNotFoundError(f"No .env or _env found in {ROOT}")


env = read_env()
catalog, schema = env["TARGET_CATALOG"], env["TARGET_SCHEMA"]
space_id = env.get("GENIE_ID") or env.get("DATABRICKS_GENIE_SPACE_ID") or ""
warehouse_id = (dbutils.widgets.get("warehouse_id")
                or env.get("DATABRICKS_SQL_WAREHOUSE_ID") or env.get("WAREHOUSE_ID"))
assert warehouse_id, "Pass warehouse_id or set WAREHOUSE_ID in .env"

raw = ((HERE / "genie_space.json").read_text()
       .replace("__CATALOG__", catalog).replace("__SCHEMA__", schema))
cfg = json.loads(raw)
space = cfg["serialized_space"]

# COMMAND ----------

# The Genie API requires specific sort orders; enforce them so the JSON can be edited freely.
by_id = lambda x: x["id"]
ds = space.get("data_sources", {})
for key in ("tables", "metric_views"):
    if key in ds:
        ds[key].sort(key=lambda t: t["identifier"])
        for t in ds[key]:
            if "column_configs" in t:
                t["column_configs"].sort(key=lambda c: c["column_name"])
if "sample_questions" in space.get("config", {}):
    space["config"]["sample_questions"].sort(key=by_id)
ins = space.get("instructions", {})
for key in ("text_instructions", "example_question_sqls", "join_specs"):
    if key in ins:
        ins[key].sort(key=by_id)
for key in ("measures", "filters", "expressions"):
    if key in ins.get("sql_snippets", {}):
        ins["sql_snippets"][key].sort(key=by_id)
if "questions" in space.get("benchmarks", {}):
    space["benchmarks"]["questions"].sort(key=by_id)

body = {
    "title": cfg["title"],
    "description": cfg["description"],
    "warehouse_id": warehouse_id,
    "serialized_space": json.dumps(space),
}
print(f"Tables: {[t['identifier'] for t in ds.get('tables', [])]}")
print(f"Metric views: {[t['identifier'] for t in ds.get('metric_views', [])]}")
print(f"Warehouse: {warehouse_id}")

# COMMAND ----------

w = WorkspaceClient()

if space_id:
    print(f"Updating Genie space {space_id} ...")
    w.api_client.do("PATCH", f"/api/2.0/genie/spaces/{space_id}", body=body)
else:
    print("GENIE_ID is empty: creating a new Genie space ...")
    resp = w.api_client.do("POST", "/api/2.0/genie/spaces", body=body)
    space_id = resp["space_id"]
    print(f"Created space {space_id}. Set GENIE_ID={space_id} in .env and genie_space_id in databricks.yml.")

# Read back to confirm what Genie actually stored
got = w.api_client.do("GET", f"/api/2.0/genie/spaces/{space_id}", query={"include_serialized_space": "true"})
stored = json.loads(got.get("serialized_space") or "{}")
print(f"OK: '{got.get('title')}' on warehouse {got.get('warehouse_id')}")
print(f"  tables:        {len(stored.get('data_sources', {}).get('tables', []))}")
print(f"  metric views:  {len(stored.get('data_sources', {}).get('metric_views', []))}")
print(f"  sample Qs:     {len(stored.get('config', {}).get('sample_questions', []))}")
print(f"  example SQLs:  {len(stored.get('instructions', {}).get('example_question_sqls', []))}")
print(f"  join specs:    {len(stored.get('instructions', {}).get('join_specs', []))}")
dbutils.jobs.taskValues.set("genie_space_id", space_id)
