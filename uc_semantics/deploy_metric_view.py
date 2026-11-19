# Databricks notebook source
# MAGIC %md
# MAGIC # Deploy UC semantics (metric view) — job version of `deploy.sh`
# MAGIC
# MAGIC Same steps as `./uc_semantics/deploy.sh --profile <PROFILE> --warehouse-id <ID>`, but runnable
# MAGIC as a job task: replaces `__CATALOG__` / `__SCHEMA__` in `shipment_risk_metrics.metric_view.sql`
# MAGIC with `TARGET_CATALOG` / `TARGET_SCHEMA` from the bundle-synced `.env` (falls back to `_env`),
# MAGIC then runs it on a SQL warehouse (metric views need a current warehouse / DBR 17.3+).
# MAGIC
# MAGIC Parameter `warehouse_id` — defaults to `WAREHOUSE_ID` / `DATABRICKS_SQL_WAREHOUSE_ID` from `.env`.

# COMMAND ----------

import os
import time
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

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
warehouse_id = (dbutils.widgets.get("warehouse_id")
                or env.get("DATABRICKS_SQL_WAREHOUSE_ID") or env.get("WAREHOUSE_ID"))
assert warehouse_id, "Pass warehouse_id or set WAREHOUSE_ID in .env"

sql = ((HERE / "shipment_risk_metrics.metric_view.sql").read_text()
       .replace("__CATALOG__", catalog).replace("__SCHEMA__", schema))
print(f"Creating {catalog}.{schema}.shipment_risk_metrics on warehouse {warehouse_id} ...")

# COMMAND ----------

w = WorkspaceClient()
resp = w.statement_execution.execute_statement(statement=sql, warehouse_id=warehouse_id, wait_timeout="50s")

# Warehouse may be cold-starting: poll until the statement finishes
while resp.status.state in (StatementState.PENDING, StatementState.RUNNING):
    time.sleep(5)
    resp = w.statement_execution.get_statement(resp.statement_id)

state = resp.status.state
print(f"  {state.value}")
if state != StatementState.SUCCEEDED:
    raise RuntimeError(f"Metric view deploy failed: {resp.status.error.message if resp.status.error else state}")
