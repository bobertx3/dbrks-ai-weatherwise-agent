#!/bin/bash
set -euo pipefail

# ============================================================
# WeatherWise Agent Demo - Genie Space Setup
# ============================================================
# Creates a Databricks Genie Space configured with the
# WeatherWise supply chain tables for natural language SQL.
#
# Usage:
#   ./genie/setup_genie_space.sh
#
# Prerequisites:
#   - Databricks CLI authenticated
#   - .env file with TARGET_CATALOG and TARGET_SCHEMA
#   - SQL warehouse available
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

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

  for var in TARGET_CATALOG TARGET_SCHEMA; do
    if [[ -z "${!var:-}" ]]; then
      echo "ERROR: Required variable $var is not set"
      exit 1
    fi
  done
}

# ── Find a SQL warehouse ────────────────────────────────────
find_warehouse() {
  if [[ -n "${DATABRICKS_SQL_WAREHOUSE_ID:-}" ]]; then
    echo "  Using configured warehouse: $DATABRICKS_SQL_WAREHOUSE_ID"
    return
  fi

  echo "  Looking for a SQL warehouse..."
  DATABRICKS_SQL_WAREHOUSE_ID=$(databricks warehouses list --output json 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
warehouses = data if isinstance(data, list) else data.get('warehouses', [])
for w in warehouses:
    if w.get('state') == 'RUNNING':
        print(w['id'])
        break
" 2>/dev/null || echo "")

  if [[ -z "$DATABRICKS_SQL_WAREHOUSE_ID" ]]; then
    echo "ERROR: No running SQL warehouse found. Set DATABRICKS_SQL_WAREHOUSE_ID in .env"
    exit 1
  fi
  echo "  Found warehouse: $DATABRICKS_SQL_WAREHOUSE_ID"
}

# ── Create Genie Space ──────────────────────────────────────
create_genie_space() {
  local catalog="$TARGET_CATALOG"
  local schema="$TARGET_SCHEMA"

  echo ""
  echo "Creating Genie Space for $catalog.$schema..."

  # Use Python to create the space (tables must be sorted by identifier)
  local space_id
  space_id=$(python3 -c "
import json, urllib.request, ssl, subprocess, os, configparser

token_data = json.loads(subprocess.run(['databricks', 'auth', 'token'], capture_output=True, text=True).stdout)
token = token_data['access_token']

cfg = configparser.ConfigParser()
cfg.read(os.path.expanduser('~/.databrickscfg'))
host = os.environ.get('DATABRICKS_HOST', cfg.get('DEFAULT', 'host', fallback='')).rstrip('/')

cat, schema, wh = '$catalog', '$schema', '$DATABRICKS_SQL_WAREHOUSE_ID'
tables = sorted([
    {'identifier': f'{cat}.{schema}.inventory'},
    {'identifier': f'{cat}.{schema}.shipments'},
    {'identifier': f'{cat}.{schema}.supplier_sops'},
    {'identifier': f'{cat}.{schema}.suppliers'},
], key=lambda t: t['identifier'])

serialized = json.dumps({'version': 2, 'data_sources': {'tables': tables}})
payload = json.dumps({
    'title': 'WeatherWise Supply Chain Explorer',
    'description': 'Ask natural language questions about shipments, inventory, suppliers, and SOPs for Jackson & Jackson MedTech.',
    'warehouse_id': wh,
    'serialized_space': serialized
}).encode()

req = urllib.request.Request(f'{host}/api/2.0/genie/spaces', data=payload,
    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}, method='POST')
resp = urllib.request.urlopen(req, context=ssl.create_default_context())
print(json.loads(resp.read()).get('space_id', ''))
" 2>/dev/null)

  if [[ -z "$space_id" ]]; then
    echo "ERROR: Failed to create Genie Space"
    echo "  The API may have returned an error. Try manually in the Databricks UI."
    exit 1
  fi

  echo "  Genie Space created: $space_id"
  echo ""
  echo "  Add this to your .env file:"
  echo "    DATABRICKS_GENIE_SPACE_ID=$space_id"
  echo ""

  # Append to .env if not already there
  local env_file="$PROJECT_DIR/.env"
  [[ ! -f "$env_file" ]] && env_file="$PROJECT_DIR/_env"
  if ! grep -q "DATABRICKS_GENIE_SPACE_ID" "$env_file" 2>/dev/null; then
    echo "" >> "$env_file"
    echo "# Genie Space for Ask Genie tab" >> "$env_file"
    echo "DATABRICKS_GENIE_SPACE_ID=$space_id" >> "$env_file"
    echo "  (Appended to $env_file)"
  fi
}

# ── Main ─────────────────────────────────────────────────────
main() {
  echo "============================================================"
  echo "  WeatherWise - Genie Space Setup"
  echo "============================================================"

  load_env
  find_warehouse
  create_genie_space

  echo "============================================================"
  echo "  Genie Space Setup Complete!"
  echo "============================================================"
}

main
