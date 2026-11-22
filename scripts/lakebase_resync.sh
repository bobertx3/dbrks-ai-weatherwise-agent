#!/usr/bin/env bash
# Re-sync the Lakebase synced tables that back the WeatherWise app (overview, at-risk, map).
# Run after the `setup` job has rebuilt the UC source tables (bldemos.agentbricks_weatherwise.*).
# Each synced table runs its own pipeline; this starts a full-refresh update per table and waits
# until each table is ONLINE again with a newer sync time.
#
# Usage: scripts/lakebase_resync.sh [--profile DEFAULT]   (default profile: DEFAULT)
set -euo pipefail

PROFILE="DEFAULT"
if [[ "${1:-}" == "--profile" ]]; then PROFILE="${2:?profile}"; fi
CATALOG="bldemos_lakebase"
SCHEMA="agentbricks_weatherwise"
TABLES="shipments_base sites facilities inventory_base"  # *_base: dates stored as days from today
TIMEOUT_S=1200

state_of() {  # prints "<detailed_state> <sync_end_time> <pipeline_id>" for a synced table
  databricks postgres get-synced-table "synced_tables/${CATALOG}.${SCHEMA}.$1" --profile "$PROFILE" -o json |
    python3 -c 'import json,sys; d=json.load(sys.stdin); s=d.get("status",{}); print(s.get("detailed_state",""), (s.get("last_sync") or {}).get("sync_end_time",""), s.get("pipeline_id",""))'
}

for t in $TABLES; do
  read -r before_state before_end pipeline_id <<<"$(state_of "$t")"
  if [[ -z "$pipeline_id" ]]; then echo "ERROR: no pipeline for $t (state: $before_state)" >&2; exit 1; fi
  printf -v "BEFORE_END_${t}" '%s' "$before_end"
  echo "[$t] starting full-refresh update on pipeline $pipeline_id (was: $before_state)"
  databricks pipelines start-update "$pipeline_id" --full-refresh --profile "$PROFILE" -o json >/dev/null
done

for t in $TABLES; do
  start=$(date +%s)
  prev_end_var="BEFORE_END_${t}"
  while true; do
    read -r st end _ <<<"$(state_of "$t")"
    # Require a new sync (sync_end_time changed) so we do not return before the update starts.
    if [[ "$st" == "SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE" && -n "$end" && "$end" != "${!prev_end_var}" ]]; then echo "[$t] online, last sync $end"; break; fi
    if (( $(date +%s) - start > TIMEOUT_S )); then echo "ERROR: $t not ONLINE after ${TIMEOUT_S}s (state: $st)" >&2; exit 1; fi
    sleep 15
  done
done
echo "Re-sync complete."
