from databricks.sdk.runtime import dbutils, spark
import os

## Update catalog, schema with your own values
WORKSHOP_CATALOG = "agentbricks"
WORKSHOP_SCHEMA = "med_tech_supply_chain_agent"
USER_SCHEMA = "med_tech_supply_chain_agent"

## To send emails, using AWS SES (simple email service)
# AWS_REGION = "us-east-1"
# AWS_ACCESS_KEY = "AKIAYS2NRPZA23IURJ67"
# AWS_SECRET_KEY = "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"
# SENDER = "robert@datakafe.com"

dbutils.widgets.text("WORKSHOP_CATALOG", WORKSHOP_CATALOG)
dbutils.widgets.text("WORKSHOP_SCHEMA", WORKSHOP_SCHEMA)
os.environ["WORKSHOP_CATALOG"] = WORKSHOP_CATALOG
os.environ["WORKSHOP_SCHEMA"] = WORKSHOP_SCHEMA

