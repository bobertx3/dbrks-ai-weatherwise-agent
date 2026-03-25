#!/bin/bash
set -euo pipefail

# ============================================================
# WeatherWise Agent Demo - SQL Warehouse Setup
# ============================================================
# Sets up a SQL warehouse for the Dashboard and Genie features:
#   1. Finds an existing warehouse or creates a new serverless one
#   2. Grants CAN_USE to the app's service principal
#   3. Updates .env and databricks.yml with the warehouse ID
#
# Usage:
#   ./genie/setup_sql_warehouse.sh
#   ./genie/setup_sql_warehouse.sh --warehouse-id <id>
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WAREHOUSE_ID=""

# ── Parse arguments ──────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --warehouse-id)
      WAREHOUSE_ID="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: ./genie/setup_sql_warehouse.sh [--warehouse-id <id>]"
      exit 1
      ;;
  esac
done

# ── Load environment variables ───────────────────────────────
load_env() {
  local env_file=""
  if [[ -f "$PROJECT_DIR/.env" ]]; then
    env_file="$PROJECT_DIR/.env"
  elif [[ -f "$PROJECT_DIR/_env" ]]; then
    env_file="$PROJECT_DIR/_env"
  else
    echo "ERROR: No .env or _env file found in $PROJECT_DIR"
    exit 1
  fi

  echo "Loading environment from $env_file"
  set -a
  while IFS= read -r line; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    eval "$line" 2>/dev/null || true
  done < "$env_file"
  set +a
}

# ── Find or create SQL warehouse ────────────────────────────
resolve_warehouse() {
  # Use provided warehouse ID
  if [[ -n "$WAREHOUSE_ID" ]]; then
    echo "Using specified warehouse: $WAREHOUSE_ID"
    return
  fi

  # Use configured warehouse ID
  if [[ -n "${DATABRICKS_SQL_WAREHOUSE_ID:-}" ]]; then
    WAREHOUSE_ID="$DATABRICKS_SQL_WAREHOUSE_ID"
    echo "Using configured warehouse from .env: $WAREHOUSE_ID"
    return
  fi

  # Try to find an existing serverless warehouse
  echo "Looking for an existing SQL warehouse..."
  WAREHOUSE_ID=$(databricks warehouses list --output json 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
warehouses = data if isinstance(data, list) else data.get('warehouses', [])
# Prefer serverless, then any warehouse
for w in warehouses:
    wtype = w.get('warehouse_type', '')
    if wtype == 'PRO' and w.get('enable_serverless_compute', False):
        print(w['id'])
        break
else:
    for w in warehouses:
        print(w['id'])
        break
" 2>/dev/null || echo "")

  if [[ -n "$WAREHOUSE_ID" ]]; then
    local wname
    wname=$(databricks warehouses get "$WAREHOUSE_ID" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('name',''))" 2>/dev/null || echo "")
    echo "  Found warehouse: $wname ($WAREHOUSE_ID)"
    return
  fi

  # Create a new serverless warehouse
  echo "  No existing warehouse found. Creating a new serverless warehouse..."
  WAREHOUSE_ID=$(databricks warehouses create --json "{
    \"name\": \"weatherwise-dashboard\",
    \"cluster_size\": \"2X-Small\",
    \"warehouse_type\": \"PRO\",
    \"enable_serverless_compute\": true,
    \"auto_stop_mins\": 10,
    \"max_num_clusters\": 1
  }" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")

  if [[ -z "$WAREHOUSE_ID" ]]; then
    echo "ERROR: Failed to create SQL warehouse."
    echo "  Create one manually in the Databricks UI and pass --warehouse-id <id>"
    exit 1
  fi

  echo "  Created warehouse: weatherwise-dashboard ($WAREHOUSE_ID)"
}

# ── Grant permissions to the app service principal ──────────
grant_permissions() {
  echo ""
  echo "Checking app service principal permissions..."

  # Get the app's service principal
  local app_sp_id
  app_sp_id=$(databricks apps get weatherwise-chat-agent --output json 2>/dev/null | python3 -c "
import sys, json
app = json.load(sys.stdin)
sp = app.get('service_principal', {})
print(sp.get('id', sp.get('application_id', '')))
" 2>/dev/null || echo "")

  if [[ -z "$app_sp_id" ]]; then
    echo "  WARNING: Could not find app service principal."
    echo "  The app 'weatherwise-chat-agent' may not be deployed yet."
    echo "  After deploying, grant CAN_USE on warehouse $WAREHOUSE_ID to the app's SP."
    return
  fi

  echo "  App service principal ID: $app_sp_id"
  echo "  Granting CAN_USE on warehouse $WAREHOUSE_ID..."

  # Grant CAN_USE permission via the Permissions API
  databricks api patch "/api/2.0/permissions/warehouses/$WAREHOUSE_ID" --json "{
    \"access_control_list\": [
      {
        \"service_principal_name\": \"$app_sp_id\",
        \"all_permissions\": [
          {
            \"permission_level\": \"CAN_USE\"
          }
        ]
      }
    ]
  }" 2>/dev/null && echo "  Warehouse permission granted." || echo "  WARNING: Could not grant warehouse permission. Will be set via bundle deploy."

  # Grant Unity Catalog permissions using SP client ID
  local app_sp_client_id
  app_sp_client_id=$(databricks apps get weatherwise-chat-agent --output json 2>/dev/null | python3 -c "
import sys, json
print(json.load(sys.stdin).get('service_principal_client_id', ''))
" 2>/dev/null || echo "")

  if [[ -n "$app_sp_client_id" ]]; then
    echo "  Granting Unity Catalog permissions to SP ($app_sp_client_id)..."

    local catalog="${TARGET_CATALOG:-bx4}"
    local schema="${TARGET_SCHEMA:-agentbricks_weatherwise}"

    for grant in \
      "GRANT USE CATALOG ON CATALOG $catalog TO \`$app_sp_client_id\`" \
      "GRANT USE SCHEMA ON SCHEMA $catalog.$schema TO \`$app_sp_client_id\`" \
      "GRANT SELECT ON SCHEMA $catalog.$schema TO \`$app_sp_client_id\`"; do
      local result
      result=$(databricks api post /api/2.0/sql/statements --json "{
        \"warehouse_id\": \"$WAREHOUSE_ID\",
        \"statement\": \"$grant\",
        \"wait_timeout\": \"30s\"
      }" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',{}).get('state','UNKNOWN'))" 2>/dev/null)
      if [[ "$result" == "SUCCEEDED" ]]; then
        echo "    OK: ${grant%% TO *}"
      else
        echo "    WARN: Failed — ${grant%% TO *}"
      fi
    done
  fi
}

# ── Update configuration files ──────────────────────────────
update_config() {
  echo ""
  echo "Updating configuration..."

  # Update .env
  local env_file="$PROJECT_DIR/.env"
  [[ ! -f "$env_file" ]] && env_file="$PROJECT_DIR/_env"

  if grep -q "^DATABRICKS_SQL_WAREHOUSE_ID=" "$env_file" 2>/dev/null; then
    # Update existing value
    if [[ "$(uname)" == "Darwin" ]]; then
      sed -i '' "s/^DATABRICKS_SQL_WAREHOUSE_ID=.*/DATABRICKS_SQL_WAREHOUSE_ID=$WAREHOUSE_ID/" "$env_file"
    else
      sed -i "s/^DATABRICKS_SQL_WAREHOUSE_ID=.*/DATABRICKS_SQL_WAREHOUSE_ID=$WAREHOUSE_ID/" "$env_file"
    fi
    echo "  Updated DATABRICKS_SQL_WAREHOUSE_ID in $env_file"
  else
    echo "" >> "$env_file"
    echo "# SQL Warehouse for Dashboard and Genie" >> "$env_file"
    echo "DATABRICKS_SQL_WAREHOUSE_ID=$WAREHOUSE_ID" >> "$env_file"
    echo "  Added DATABRICKS_SQL_WAREHOUSE_ID to $env_file"
  fi

  # Update databricks.yml default
  local bundle_file="$PROJECT_DIR/databricks.yml"
  if [[ -f "$bundle_file" ]] && grep -q "sql_warehouse_id:" "$bundle_file"; then
    if [[ "$(uname)" == "Darwin" ]]; then
      sed -i '' "s/default: \".*\"  # sql_warehouse_id/default: \"$WAREHOUSE_ID\"  # sql_warehouse_id/" "$bundle_file" 2>/dev/null || true
    fi
    echo "  Updated sql_warehouse_id default in databricks.yml"
  fi
}

# ── Main ─────────────────────────────────────────────────────
main() {
  echo "============================================================"
  echo "  WeatherWise - SQL Warehouse Setup"
  echo "============================================================"

  load_env
  resolve_warehouse
  grant_permissions
  update_config

  echo ""
  echo "============================================================"
  echo "  SQL Warehouse Setup Complete!"
  echo "============================================================"
  echo ""
  echo "  Warehouse ID: $WAREHOUSE_ID"
  echo ""
  echo "  Next steps:"
  echo "    1. Deploy to apply resource permissions:"
  echo "       databricks bundle deploy -t dev"
  echo "    2. Redeploy the app:"
  echo "       databricks apps deploy weatherwise-chat-agent \\"
  echo "         --source-code-path /Workspace/Users/\$(databricks current-user me | python3 -c \"import sys,json;print(json.load(sys.stdin)['userName'])\")/weatherwise-agent-demo/files/chatapp"
  echo ""
}

main
