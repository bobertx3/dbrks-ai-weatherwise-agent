# Databricks notebook source
# MAGIC %md
# MAGIC # Unity AI Gateway model service for the WeatherWise agent's LLM
# MAGIC Creates (or updates) a governed **model service** in Unity Catalog that the agent calls instead of the
# MAGIC shared `system.ai` model, so this demo owns its own LLM routing, inference table and permissions.
# MAGIC
# MAGIC | Item | Value |
# MAGIC |---|---|
# MAGIC | Model service | `AI_GATEWAY_MODEL` in `.env` (e.g. `bldemos.agentbricks_weatherwise.weatherwise_llm`) |
# MAGIC | Routes to | `LLM_DESTINATION_MODEL` (default `system.ai.databricks-gpt-5-6-sol`, pay-per-token) |
# MAGIC | Inference table | `<catalog>.<schema>.<service>_payload` (appears after the first requests) |
# MAGIC | Caller identity | Service principal from `scripts/setup_agent_llm_sp.sh` (secret scope `AGENT_LLM_SECRET_SCOPE`) |
# MAGIC
# MAGIC Callers use `POST /ai-gateway/mlflow/v1/chat/completions` with `model = "<catalog>.<schema>.<service>"`.

# COMMAND ----------

# MAGIC %pip install -qqq python-dotenv "databricks-sdk>=0.81"
# MAGIC %restart_python

# COMMAND ----------

import os
from dotenv import load_dotenv, find_dotenv
from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound

load_dotenv(find_dotenv())
w = WorkspaceClient()

CATALOG = os.environ["TARGET_CATALOG"]
SCHEMA = os.environ["TARGET_SCHEMA"]
service = os.environ.get("AI_GATEWAY_MODEL", "")
if service.count(".") != 2 or service.startswith("system."):
    service = f"{CATALOG}.{SCHEMA}.weatherwise_llm"
destination = os.environ.get("LLM_DESTINATION_MODEL") or "system.ai.databricks-gpt-5-6-sol"
scope = os.environ.get("AGENT_LLM_SECRET_SCOPE") or "weatherwise-agent"
svc_catalog, svc_schema, svc_id = service.split(".")
print(f"service={service}  destination={destination}  secret scope={scope}")

# COMMAND ----------

API = "/api/2.1/unity-catalog/model-services"
routing = {"destinations": [{
    "name": destination,
    "destination_type": "DESTINATION_TYPE_PAY_PER_TOKEN_FOUNDATION_MODEL",
    "pay_per_token_config": {"model": f"models/{destination}"},
    "traffic_percentage": 100,
}]}
inference_table = {"parent": f"schemas/{svc_catalog}.{svc_schema}", "table_name_prefix": svc_id}
comment = f"WeatherWise agent LLM via Unity AI Gateway; routes to {destination}. Synthetic demo."

try:
    existing = w.api_client.do("GET", f"{API}/{service}")
except NotFound:
    w.api_client.do(
        "POST", API,
        query={"parent": f"schemas/{svc_catalog}.{svc_schema}", "model_service_id": svc_id},
        body={"comment": comment, "config": {"routing": routing, "inference_table": inference_table}},
    )
    print(f"Created model service {service} -> {destination}")
else:
    mask, config = ["comment", "config.routing.destinations"], {"routing": routing}
    if not existing.get("config", {}).get("inference_table"):  # parent is immutable once set
        mask.append("config.inference_table")
        config["inference_table"] = inference_table
    w.api_client.do("PATCH", f"{API}/{service}", query={"update_mask": ",".join(mask)},
                    body={"comment": comment, "config": config})
    print(f"Updated model service {service} -> {destination}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Grant the agent's LLM identity access

# COMMAND ----------

llm_sp = dbutils.secrets.get(scope, "sp-client-id")  # application id; not sensitive
spark.sql(f"GRANT USE CATALOG ON CATALOG `{svc_catalog}` TO `{llm_sp}`")
spark.sql(f"GRANT USE SCHEMA ON SCHEMA `{svc_catalog}`.`{svc_schema}` TO `{llm_sp}`")
w.api_client.do("PATCH", f"/api/2.1/unity-catalog/permissions/model_service/{service}",
                body={"changes": [{"principal": llm_sp, "add": ["EXECUTE"]}]})
print(f"Granted USE CATALOG, USE SCHEMA, EXECUTE on {service} to {llm_sp}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Smoke test through the gateway

# COMMAND ----------

reply = w.api_client.do("POST", "/ai-gateway/mlflow/v1/chat/completions", body={
    "model": service,
    "messages": [{"role": "user", "content": "Reply with exactly: weatherwise gateway OK"}],
    "max_tokens": 20,
})["choices"][0]["message"]["content"]
print("LLM reply:", reply)
assert reply, "Empty reply from the AI Gateway model service"
