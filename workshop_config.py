from databricks.sdk.runtime import dbutils, spark
import os

## Update catalog, schema with your own values
WORKSHOP_CATALOG = "aiml_dev"
WORKSHOP_SCHEMA = "agents"
USER_SCHEMA = spark.sql("select regexp_replace(lower(split(current_user(), '@')[0]), '[ .]', '_')").collect()[0][0]

dbutils.widgets.text("WORKSHOP_CATALOG", WORKSHOP_CATALOG)
dbutils.widgets.text("WORKSHOP_SCHEMA", WORKSHOP_SCHEMA)
dbutils.widgets.text("USER_SCHEMA", USER_SCHEMA)
os.environ["WORKSHOP_CATALOG"] = WORKSHOP_CATALOG
os.environ["WORKSHOP_SCHEMA"] = WORKSHOP_SCHEMA
os.environ["USER_SCHEMA"] = USER_SCHEMA
