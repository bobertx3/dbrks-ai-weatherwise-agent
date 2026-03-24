#!/bin/bash
set -euo pipefail

# ============================================================
# WeatherWise Agent Demo - Setup Script
# ============================================================
# This script sets up all dependencies and deploys the agent:
#   1. Creates catalog, schema, volume, and Delta tables
#   2. Creates UC SQL functions (get_shipments, get_supplier_details, etc.)
#   3. Creates Vector Search endpoint and index
#   4. Logs, registers, and deploys the agent to Model Serving
#
# Usage:
#   ./setup.sh                         # Auto-detect cluster or fall back to manual
#   ./setup.sh --cluster-id <id>       # Use a specific cluster
#   ./setup.sh --manual                # Just import notebooks, print instructions
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_SETUP_PATH=""
CLUSTER_ID=""
MANUAL_MODE=false

# ── Parse arguments ──────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cluster-id)
      CLUSTER_ID="$2"
      shift 2
      ;;
    --manual)
      MANUAL_MODE=true
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: ./setup.sh [--cluster-id <id>] [--manual]"
      exit 1
      ;;
  esac
done

# ── Load environment variables ───────────────────────────────
load_env() {
  local env_file=""
  if [[ -f "$SCRIPT_DIR/.env" ]]; then
    env_file="$SCRIPT_DIR/.env"
  elif [[ -f "$SCRIPT_DIR/_env" ]]; then
    env_file="$SCRIPT_DIR/_env"
  else
    echo "ERROR: No .env or _env file found in $SCRIPT_DIR"
    echo "Copy _env to .env and fill in your values first."
    exit 1
  fi

  echo "Loading environment from $env_file"
  # Source env file, stripping comments and empty lines
  set -a
  while IFS= read -r line; do
    # Skip comments and empty lines
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    eval "$line" 2>/dev/null || true
  done < "$env_file"
  set +a

  # Validate required variables
  for var in TARGET_CATALOG TARGET_SCHEMA VS_INDEX_BASE_TABLE VS_INDEX AGENT_NAME LLM_ENDPOINT_NAME; do
    if [[ -z "${!var:-}" ]]; then
      echo "ERROR: Required variable $var is not set in $env_file"
      exit 1
    fi
  done

  echo "  TARGET_CATALOG=$TARGET_CATALOG"
  echo "  TARGET_SCHEMA=$TARGET_SCHEMA"
  echo "  VS_INDEX_BASE_TABLE=$VS_INDEX_BASE_TABLE"
  echo "  VS_INDEX=$VS_INDEX"
}

# ── Validate prerequisites ───────────────────────────────────
check_prerequisites() {
  echo ""
  echo "Checking prerequisites..."

  if ! command -v databricks &>/dev/null; then
    echo "ERROR: Databricks CLI not found. Install it first:"
    echo "  brew install databricks"
    exit 1
  fi
  echo "  Databricks CLI: OK"

  if ! databricks auth describe &>/dev/null; then
    echo "ERROR: Databricks CLI not authenticated. Run:"
    echo "  databricks auth login"
    exit 1
  fi

  local user
  user=$(databricks current-user me 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['userName'])" 2>/dev/null || echo "")
  if [[ -z "$user" ]]; then
    echo "ERROR: Could not determine current user. Check your Databricks auth."
    exit 1
  fi
  echo "  Authenticated as: $user"

  WORKSPACE_SETUP_PATH="/Workspace/Users/$user/weatherwise_setup"
}

# ── Find or validate cluster ─────────────────────────────────
resolve_cluster() {
  if [[ "$MANUAL_MODE" == "true" ]]; then
    return
  fi

  if [[ -n "$CLUSTER_ID" ]]; then
    echo ""
    echo "Validating cluster $CLUSTER_ID..."
    local state
    state=$(databricks clusters get "$CLUSTER_ID" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('state','UNKNOWN'))" 2>/dev/null || echo "ERROR")
    if [[ "$state" == "ERROR" ]]; then
      echo "ERROR: Could not find cluster $CLUSTER_ID"
      exit 1
    fi
    echo "  Cluster state: $state"
    if [[ "$state" == "TERMINATED" ]]; then
      echo "  Starting cluster..."
      databricks clusters start "$CLUSTER_ID" 2>/dev/null
      echo "  Waiting for cluster to start..."
      while true; do
        state=$(databricks clusters get "$CLUSTER_ID" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('state','UNKNOWN'))" 2>/dev/null || echo "UNKNOWN")
        if [[ "$state" == "RUNNING" ]]; then
          echo "  Cluster is running."
          break
        elif [[ "$state" == "ERROR" || "$state" == "UNKNOWN" ]]; then
          echo "  ERROR: Cluster failed to start (state: $state)"
          exit 1
        fi
        sleep 10
      done
    fi
    return
  fi

  # Auto-detect: find a running cluster
  echo ""
  echo "Looking for a running cluster..."
  CLUSTER_ID=$(databricks clusters list --output json 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
clusters = data if isinstance(data, list) else data.get('clusters', [])
for c in clusters:
    if c.get('state') == 'RUNNING' and c.get('cluster_source') != 'JOB':
        print(c['cluster_id'])
        break
" 2>/dev/null || echo "")

  if [[ -n "$CLUSTER_ID" ]]; then
    local name
    name=$(databricks clusters get "$CLUSTER_ID" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('cluster_name',''))" 2>/dev/null || echo "")
    echo "  Found running cluster: $name ($CLUSTER_ID)"
  else
    echo "  No running cluster found."
    echo "  Will fall back to manual instructions."
    MANUAL_MODE=true
  fi
}

# ── Upload a file to workspace (as a file, not notebook) ─────
upload_workspace_file() {
  local ws_path="$1"
  local local_path="$2"
  # Delete any existing notebook with the same name (stored without .py extension)
  local ws_path_no_ext="${ws_path%.py}"
  databricks workspace delete "$ws_path_no_ext" 2>/dev/null || true
  databricks workspace delete "$ws_path" 2>/dev/null || true
  # Use the REST API with RAW format — the CLI's --format RAW still creates notebooks for .py
  databricks api post /api/2.0/workspace/import --json "{
    \"path\": \"$ws_path\",
    \"format\": \"RAW\",
    \"content\": \"$(base64 < "$local_path")\",
    \"overwrite\": true
  }" >/dev/null 2>&1
}

# ── Import notebooks to workspace ────────────────────────────
import_notebooks() {
  echo ""
  echo "Importing notebooks to $WORKSPACE_SETUP_PATH..."

  databricks workspace mkdirs "$WORKSPACE_SETUP_PATH" 2>/dev/null || true

  # Import setup_data notebook
  echo "  Importing setup_data..."
  databricks workspace import "$WORKSPACE_SETUP_PATH/setup_data" \
    --file "$SCRIPT_DIR/data/setup_data.ipynb" \
    --format JUPYTER \
    --language PYTHON \
    --overwrite 2>/dev/null

  # Import UC functions notebook
  echo "  Importing tool_uc_functions..."
  databricks workspace import "$WORKSPACE_SETUP_PATH/tool_uc_functions" \
    --file "$SCRIPT_DIR/agent_src/tools/uc_tools/tool_uc_functions.ipynb" \
    --format JUPYTER \
    --language PYTHON \
    --overwrite 2>/dev/null

  # Import agent_eval_notebook and its dependencies (agent code + tools)
  echo "  Importing agent_eval_notebook..."
  databricks workspace import "$WORKSPACE_SETUP_PATH/agent_eval_notebook" \
    --file "$SCRIPT_DIR/agent_src/agent_eval_notebook.ipynb" \
    --format JUPYTER \
    --language PYTHON \
    --overwrite 2>/dev/null

  echo "  Uploading agent source code as workspace files..."
  # Must upload as files (not notebooks) so Python can import them
  upload_workspace_file "$WORKSPACE_SETUP_PATH/weatherwise_agent.py" "$SCRIPT_DIR/agent_src/weatherwise_agent.py"

  # Upload custom tools as files
  databricks workspace mkdirs "$WORKSPACE_SETUP_PATH/tools/custom_tools" 2>/dev/null || true
  for tool_file in "$SCRIPT_DIR/agent_src/tools/custom_tools/"*.py; do
    local fname=$(basename "$tool_file")
    upload_workspace_file "$WORKSPACE_SETUP_PATH/tools/custom_tools/$fname" "$tool_file"
  done

  # Upload .env file so notebooks can read it
  echo "  Uploading .env..."
  local env_file="$SCRIPT_DIR/.env"
  [[ ! -f "$env_file" ]] && env_file="$SCRIPT_DIR/_env"
  databricks workspace import "$WORKSPACE_SETUP_PATH/.env" \
    --file "$env_file" \
    --format AUTO \
    --overwrite 2>/dev/null || true

  # Upload CSV data files
  echo "  Uploading CSV data files..."
  for csv in "$SCRIPT_DIR/data/"*.csv; do
    local fname=$(basename "$csv")
    databricks workspace import "$WORKSPACE_SETUP_PATH/$fname" \
      --file "$csv" \
      --format AUTO \
      --overwrite 2>/dev/null || true
  done

  echo "  Notebooks imported successfully."
}

# ── Run a notebook as a one-time job ─────────────────────────
run_notebook() {
  local notebook_path="$1"
  local notebook_name="$2"
  local params="$3"

  echo ""
  echo "Running $notebook_name..."

  local run_id
  run_id=$(databricks jobs submit --no-wait --json "{
    \"run_name\": \"weatherwise_setup_${notebook_name}\",
    \"tasks\": [
      {
        \"task_key\": \"${notebook_name}\",
        \"existing_cluster_id\": \"$CLUSTER_ID\",
        \"notebook_task\": {
          \"notebook_path\": \"$notebook_path\",
          \"base_parameters\": $params
        }
      }
    ]
  }" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])" 2>/dev/null)

  if [[ -z "$run_id" ]]; then
    echo "  ERROR: Failed to submit job for $notebook_name"
    return 1
  fi

  echo "  Submitted run $run_id. Waiting for completion..."

  # Poll for completion
  local state="PENDING"
  local last_state=""
  while true; do
    state=$(databricks jobs get-run "$run_id" --output json 2>/dev/null | python3 -c "
import sys, json
run = json.load(sys.stdin)
state = run.get('state', {})
life_cycle = state.get('life_cycle_state', 'UNKNOWN')
result = state.get('result_state', '')
if life_cycle in ('TERMINATED', 'SKIPPED', 'INTERNAL_ERROR'):
    print(f'{life_cycle}:{result}')
else:
    print(life_cycle)
" 2>/dev/null || echo "UNKNOWN")

    if [[ "$state" != "$last_state" ]]; then
      echo "  Status: $state"
      last_state="$state"
    fi

    case "$state" in
      TERMINATED:SUCCESS)
        echo "  $notebook_name completed successfully!"
        return 0
        ;;
      TERMINATED:FAILED|TERMINATED:TIMEDOUT|TERMINATED:CANCELED|SKIPPED*|INTERNAL_ERROR*)
        echo "  ERROR: $notebook_name failed with state: $state"
        echo "  Check the run at: $(databricks jobs get-run "$run_id" --output json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('run_page_url',''))" 2>/dev/null)"
        return 1
        ;;
    esac

    sleep 10
  done
}

# ── Create vector search index via API ───────────────────────
create_vector_search_index() {
  local index_name="$TARGET_CATALOG.$TARGET_SCHEMA.$VS_INDEX"
  local source_table="$TARGET_CATALOG.$TARGET_SCHEMA.$VS_INDEX_BASE_TABLE"
  local endpoint_name="$TARGET_CATALOG"

  echo ""
  echo "Checking vector search index: $index_name..."

  # Check if index already exists
  local existing
  existing=$(databricks api get "/api/2.0/vector-search/indexes/$index_name" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('name',''))" 2>/dev/null || echo "")

  if [[ "$existing" == "$index_name" ]]; then
    echo "  Vector search index already exists. Skipping."
    return 0
  fi

  echo "  Creating vector search index..."
  databricks api post /api/2.0/vector-search/indexes --json "{
    \"name\": \"$index_name\",
    \"endpoint_name\": \"$endpoint_name\",
    \"primary_key\": \"product_id\",
    \"index_type\": \"DELTA_SYNC\",
    \"delta_sync_index_spec\": {
      \"source_table\": \"$source_table\",
      \"pipeline_type\": \"TRIGGERED\",
      \"embedding_source_columns\": [
        {
          \"name\": \"product_doc\",
          \"embedding_model_endpoint_name\": \"databricks-gte-large-en\"
        }
      ]
    }
  }" 2>/dev/null

  echo "  Vector search index creation initiated."
  echo "  Note: Index sync may take a few minutes to complete."
}

# ── Print manual instructions ────────────────────────────────
print_manual_instructions() {
  echo ""
  echo "============================================================"
  echo "  MANUAL SETUP INSTRUCTIONS"
  echo "============================================================"
  echo ""
  echo "Notebooks have been imported to your workspace at:"
  echo "  $WORKSPACE_SETUP_PATH"
  echo ""
  echo "Run them in this order on a cluster with the Databricks Runtime:"
  echo ""
  echo "  1. setup_data"
  echo "     - Creates schema, volume, Delta tables, and vector search endpoint"
  echo "     - Parameters: TARGET_CATALOG=$TARGET_CATALOG, TARGET_SCHEMA=$TARGET_SCHEMA"
  echo "       VS_INDEX_BASE_TABLE=$VS_INDEX_BASE_TABLE, VS_INDEX=$VS_INDEX"
  echo ""
  echo "  2. tool_uc_functions"
  echo "     - Creates UC SQL functions (get_shipments, get_supplier_details, etc.)"
  echo "     - Parameters: TARGET_CATALOG=$TARGET_CATALOG, TARGET_SCHEMA=$TARGET_SCHEMA"
  echo ""
  echo "  3. agent_eval_notebook"
  echo "     - Logs agent to MLflow, registers in Unity Catalog, deploys to Model Serving"
  echo "     - Runs evaluation with LLM judges"
  echo "     - Note: Vector search index will be created automatically if needed"
  echo ""
  echo "After running the notebooks, deploy the chat app with:"
  echo "  databricks bundle deploy --target dev"
  echo "  databricks bundle run weatherwise_chatapp"
  echo "============================================================"
}

# ── Main ─────────────────────────────────────────────────────
main() {
  echo "============================================================"
  echo "  WeatherWise Agent Demo - Setup"
  echo "============================================================"

  load_env
  check_prerequisites
  resolve_cluster
  import_notebooks

  if [[ "$MANUAL_MODE" == "true" ]]; then
    print_manual_instructions
    exit 0
  fi

  # Run notebooks in order
  local setup_params="{
    \"TARGET_CATALOG\": \"$TARGET_CATALOG\",
    \"TARGET_SCHEMA\": \"$TARGET_SCHEMA\",
    \"VS_INDEX_BASE_TABLE\": \"$VS_INDEX_BASE_TABLE\",
    \"VS_INDEX\": \"$VS_INDEX\"
  }"

  local uc_params="{
    \"TARGET_CATALOG\": \"$TARGET_CATALOG\",
    \"TARGET_SCHEMA\": \"$TARGET_SCHEMA\"
  }"

  if ! run_notebook "$WORKSPACE_SETUP_PATH/setup_data" "setup_data" "$setup_params"; then
    echo ""
    echo "Setup data failed. Fix the issue and re-run, or use --manual mode."
    exit 1
  fi

  if ! run_notebook "$WORKSPACE_SETUP_PATH/tool_uc_functions" "tool_uc_functions" "$uc_params"; then
    echo ""
    echo "UC functions setup failed. Fix the issue and re-run, or use --manual mode."
    exit 1
  fi

  # Create vector search index via API
  create_vector_search_index

  # Run agent eval notebook (logs, registers, and deploys the agent)
  local agent_params="{
    \"TARGET_CATALOG\": \"$TARGET_CATALOG\",
    \"TARGET_SCHEMA\": \"$TARGET_SCHEMA\",
    \"VS_INDEX\": \"${VS_INDEX:-}\",
    \"LLM_ENDPOINT_NAME\": \"${LLM_ENDPOINT_NAME:-}\",
    \"MLFLOW_EXPERIMENT\": \"${MLFLOW_EXPERIMENT:-}\",
    \"RETRIEVER_TOOL_NAME\": \"${RETRIEVER_TOOL_NAME:-}\",
    \"AGENT_NAME\": \"${AGENT_NAME:-}\"
  }"

  if ! run_notebook "$WORKSPACE_SETUP_PATH/agent_eval_notebook" "agent_eval_notebook" "$agent_params"; then
    echo ""
    echo "Agent evaluation/deployment failed. Fix the issue and re-run, or use --manual mode."
    exit 1
  fi

  echo ""
  echo "============================================================"
  echo "  Setup Complete!"
  echo "============================================================"
  echo ""
  echo "  Catalog:   $TARGET_CATALOG"
  echo "  Schema:    $TARGET_SCHEMA"
  echo "  Tables:    shipments, suppliers, inventory, $VS_INDEX_BASE_TABLE"
  echo "  Functions: get_shipments, get_supplier_details, get_backup_inventory, temp_gap"
  echo "  VS Index:  $TARGET_CATALOG.$TARGET_SCHEMA.$VS_INDEX"
  echo "  Agent:     $TARGET_CATALOG.$TARGET_SCHEMA.${AGENT_NAME:-weatherwise_agent}"
  echo ""
  echo "Next steps:"
  echo "  Deploy the chat app:"
  echo "    databricks bundle deploy --target dev"
  echo "    databricks bundle run weatherwise_chatapp"
  echo ""
}

main
