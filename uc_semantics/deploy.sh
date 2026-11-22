#!/bin/bash
set -euo pipefail

# ============================================================
# WeatherWise · Deploy UC semantics (metric view)
# ============================================================
# Substitutes TARGET_CATALOG / TARGET_SCHEMA from .env (or _env) into
# shipment_risk_metrics.metric_view.sql and runs it on a SQL warehouse.
#
# Usage:
#   ./uc_semantics/deploy.sh --profile <PROFILE> [--warehouse-id <ID>] [--dry-run]
#
# The Genie Ontology page (page_cold_chain_shipment_risk.md) is pasted
# into Genie Ontology → Add → Page. Run with --dry-run to print the
# page with catalog/schema filled in.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PROFILE=""
WAREHOUSE_ID="${DATABRICKS_SQL_WAREHOUSE_ID:-}"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)      PROFILE="$2"; shift 2 ;;
    --warehouse-id) WAREHOUSE_ID="$2"; shift 2 ;;
    --dry-run)      DRY_RUN=true; shift ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

env_file="$PROJECT_DIR/.env"; [[ -f "$env_file" ]] || env_file="$PROJECT_DIR/_env"
TARGET_CATALOG=$(grep -E '^TARGET_CATALOG=' "$env_file" | cut -d= -f2- | tr -d '"')
TARGET_SCHEMA=$(grep -E '^TARGET_SCHEMA=' "$env_file" | cut -d= -f2- | tr -d '"')
: "${WAREHOUSE_ID:=$(grep -E '^(DATABRICKS_SQL_)?WAREHOUSE_ID=' "$env_file" | head -1 | cut -d= -f2- | tr -d '"' || true)}"

render() { sed -e "s/__CATALOG__/$TARGET_CATALOG/g" -e "s/__SCHEMA__/$TARGET_SCHEMA/g" "$1"; }

SQL=$(render "$SCRIPT_DIR/shipment_risk_metrics.metric_view.sql")

if $DRY_RUN; then
  echo "$SQL"
  echo; echo "──────── Genie Ontology page ────────"; echo
  render "$SCRIPT_DIR/page_cold_chain_shipment_risk.md"
  exit 0
fi

[[ -n "$PROFILE" ]]      || { echo "ERROR: --profile is required"; exit 1; }
[[ -n "$WAREHOUSE_ID" ]] || { echo "ERROR: pass --warehouse-id or set DATABRICKS_SQL_WAREHOUSE_ID"; exit 1; }

echo "Creating $TARGET_CATALOG.$TARGET_SCHEMA.shipment_risk_metrics on warehouse $WAREHOUSE_ID ..."
payload=$(python3 -c 'import json,sys; print(json.dumps({"statement": sys.stdin.read(), "warehouse_id": sys.argv[1], "wait_timeout": "50s"}))' "$WAREHOUSE_ID" <<< "$SQL")
resp=$(databricks api post /api/2.0/sql/statements --profile "$PROFILE" --json "$payload")
parse() { python3 -c 'import json,sys; r=json.load(sys.stdin); s=r.get("status",{}); print(s.get("state"), r.get("statement_id",""), s.get("error",{}).get("message",""))'; }
read -r state stmt_id err <<< "$(parse <<< "$resp")"
while [[ "$state" == PENDING || "$state" == RUNNING ]]; do
  sleep 5
  read -r state _ err <<< "$(databricks api get "/api/2.0/sql/statements/$stmt_id" --profile "$PROFILE" | parse)"
done
state="$state $stmt_id $err"
echo "  $state"
[[ "$state" == SUCCEEDED* ]] || exit 1
