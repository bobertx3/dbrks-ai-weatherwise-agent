#!/bin/bash
set -euo pipefail

# ============================================================
# WeatherWise Agent Demo - Compute Creation
# ============================================================
# Creates (or reuses) the all-purpose cluster that setup.sh uses to run the
# data / UC-function / agent-eval notebooks.
#
# The cluster is configured for Unity Catalog work:
#   - Single-node (driver only), 16.4 LTS, m5.xlarge
#   - SINGLE_USER data security mode (required for 3-level UC names)
#   - ON_DEMAND driver (avoids spot reclaims mid-notebook)
#
# Usage:
#   ./create_compute.sh                 # create (or reuse) and wait for RUNNING
#   ./create_compute.sh --no-wait       # create and return immediately
#   ./create_compute.sh -p <profile>    # use a specific Databricks CLI profile
#
# On success it prints the cluster id (and writes it to .cluster_id).
# Pass that id to setup.sh:  ./setup.sh --cluster-id <id>
# ============================================================

CLUSTER_NAME="weather-agent-ap-compute"
SPARK_VERSION="16.4.x-scala2.12"
NODE_TYPE="m5.xlarge"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

PROFILE_ARGS=()
WAIT_FOR_RUNNING=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--profile)
      PROFILE_ARGS=(-p "$2"); shift 2 ;;
    --no-wait)
      WAIT_FOR_RUNNING=false; shift ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: ./create_compute.sh [--no-wait] [-p <profile>]"
      exit 1 ;;
  esac
done

dbx() { databricks "$@" "${PROFILE_ARGS[@]}"; }

cluster_state() {
  dbx clusters get "$1" --output json 2>/dev/null \
    | python3 -c "import sys,json;print(json.load(sys.stdin).get('state','UNKNOWN'))" 2>/dev/null \
    || echo "UNKNOWN"
}

# ── Determine current user (single_user_name for UC SINGLE_USER mode) ──
USER_NAME=$(dbx current-user me 2>/dev/null \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['userName'])" 2>/dev/null || echo "")
if [[ -z "$USER_NAME" ]]; then
  echo "ERROR: Could not determine current user. Run 'databricks auth login' first."
  exit 1
fi
echo "Authenticated as: $USER_NAME"

# ── Reuse an existing cluster with this name if present ──
EXISTING_ID=$(dbx clusters list --output json 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)
cs = d if isinstance(d, list) else d.get('clusters', [])
for c in cs:
    if c.get('cluster_name') == '$CLUSTER_NAME':
        print(c['cluster_id']); break
" 2>/dev/null || echo "")

if [[ -n "$EXISTING_ID" ]]; then
  echo "Reusing existing cluster '$CLUSTER_NAME' ($EXISTING_ID)"
  CLUSTER_ID="$EXISTING_ID"
  STATE=$(cluster_state "$CLUSTER_ID")
  if [[ "$STATE" == "TERMINATED" || "$STATE" == "UNKNOWN" ]]; then
    echo "  Starting cluster..."
    dbx clusters start "$CLUSTER_ID" >/dev/null 2>&1 || true
  fi
else
  echo "Creating cluster '$CLUSTER_NAME'..."
  CLUSTER_ID=$(dbx clusters create --json "{
    \"cluster_name\": \"$CLUSTER_NAME\",
    \"spark_version\": \"$SPARK_VERSION\",
    \"node_type_id\": \"$NODE_TYPE\",
    \"num_workers\": 0,
    \"autotermination_minutes\": 90,
    \"data_security_mode\": \"SINGLE_USER\",
    \"single_user_name\": \"$USER_NAME\",
    \"spark_conf\": {
      \"spark.databricks.cluster.profile\": \"singleNode\",
      \"spark.master\": \"local[*]\"
    },
    \"custom_tags\": { \"ResourceClass\": \"SingleNode\" },
    \"aws_attributes\": {
      \"availability\": \"ON_DEMAND\",
      \"first_on_demand\": 1,
      \"ebs_volume_type\": \"GENERAL_PURPOSE_SSD\",
      \"ebs_volume_count\": 1,
      \"ebs_volume_size\": 100
    }
  }" 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin)['cluster_id'])")
  echo "  Created: $CLUSTER_ID"
fi

# ── Optionally wait for RUNNING ──
if [[ "$WAIT_FOR_RUNNING" == "true" ]]; then
  echo "Waiting for cluster to reach RUNNING..."
  while true; do
    STATE=$(cluster_state "$CLUSTER_ID")
    case "$STATE" in
      RUNNING) echo "  Cluster is RUNNING."; break ;;
      ERROR|TERMINATED) echo "  ERROR: cluster entered state $STATE"; exit 1 ;;
      *) sleep 15 ;;
    esac
  done
fi

echo "$CLUSTER_ID" > "$SCRIPT_DIR/.cluster_id"
echo ""
echo "Cluster ID: $CLUSTER_ID  (saved to .cluster_id)"
echo "Next: ./setup.sh --cluster-id $CLUSTER_ID"
