#!/usr/bin/env bash
#
# One-time (idempotent) setup of the identity the deployed agent uses for its LLM calls
# through the Unity AI Gateway model service.
#
#   ./scripts/setup_agent_llm_sp.sh [PROFILE] [--rotate]
#
# Why: Model Serving's automatic auth passthrough covers the agent's tools (model
# endpoint, Vector Search) but not Unity AI Gateway model services in this workspace,
# so the agent calls the model service as a dedicated service principal instead.
#
# Creates the service principal, mints an OAuth secret for it and stores the client ID +
# secret in a secret scope. The secret is piped straight into the scope and never printed.
# The workflow then:
#   - agent_src/setup_ai_gateway grants the SP USE CATALOG / USE SCHEMA / EXECUTE on the model service
#   - agent_eval_notebook injects LLM_HOST + LLM_CLIENT_ID/SECRET as {{secrets/...}} references
#     so only the agent's LLM calls (Unity AI Gateway model service) run as this SP; tools
#     keep Model Serving automatic auth passthrough via the declared resources.
#
# Requires workspace admin. Re-running reuses the SP and scope; a secret is only minted if
# the scope has none. Pass --rotate to mint a fresh secret (then rerun the workflow).
# Override defaults with env vars: SP_NAME, SECRET_SCOPE, SECRET_LIFETIME (seconds).
#
set -euo pipefail

PROFILE="DEFAULT"
ROTATE=false
for arg in "$@"; do
  case "$arg" in
    --rotate) ROTATE=true ;;
    *)        PROFILE="$arg" ;;
  esac
done

SP_NAME="${SP_NAME:-weatherwise-agent-llm-sp}"
SECRET_SCOPE="${SECRET_SCOPE:-weatherwise-agent}"
SECRET_LIFETIME="${SECRET_LIFETIME:-63072000}"   # 2 years (maximum)

db() { databricks "$@" --profile "$PROFILE"; }

echo "▶ service principal  ($SP_NAME)"
SP_ID=$(db service-principals list --filter "displayName eq \"$SP_NAME\"" -o json \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'] if d else '', end='')")
if [ -z "$SP_ID" ]; then
  SP_ID=$(db service-principals create --display-name "$SP_NAME" --active -o json \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['id'], end='')")
  echo "  ✓ created (id=$SP_ID)"
else
  echo "  ✓ exists  (id=$SP_ID)"
fi
APP_ID=$(db service-principals get "$SP_ID" -o json | python3 -c "import sys,json; print(json.load(sys.stdin)['applicationId'], end='')")
echo "  application id: $APP_ID"

echo "▶ secret scope  ($SECRET_SCOPE)"
if db secrets list-scopes -o json | python3 -c "import sys,json; sys.exit(0 if any(s['name']=='$SECRET_SCOPE' for s in json.load(sys.stdin)) else 1)"; then
  echo "  ✓ exists"
else
  db secrets create-scope "$SECRET_SCOPE"
  echo "  ✓ created"
fi

echo "▶ OAuth credentials  ($SECRET_SCOPE/sp-client-id, $SECRET_SCOPE/sp-client-secret)"
HAS_SECRET=$(db secrets list-secrets "$SECRET_SCOPE" -o json \
  | python3 -c "import sys,json; print(any(s['key']=='sp-client-secret' for s in (json.load(sys.stdin) or [])), end='')")
printf '%s' "$APP_ID" | db secrets put-secret "$SECRET_SCOPE" sp-client-id
if [ "$HAS_SECRET" = "True" ] && [ "$ROTATE" = false ]; then
  echo "  ✓ secret already stored (pass --rotate to mint a new one)"
else
  db service-principal-secrets-proxy create "$SP_ID" --lifetime "${SECRET_LIFETIME}s" -o json \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['secret'], end='')" \
    | db secrets put-secret "$SECRET_SCOPE" sp-client-secret
  echo "  ✓ new secret stored (lifetime ${SECRET_LIFETIME}s)"
fi

echo
echo "Done. Next: databricks bundle run agent_eval  (setup_ai_gateway task grants the SP EXECUTE on the model service)"
