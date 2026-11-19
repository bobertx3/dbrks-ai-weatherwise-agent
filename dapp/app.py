# app.py — MedTech Weatherwise Agent (FastAPI backend + React SPA)
#
# API (all under /api):
#   GET  /api/health              config + signed-in user
#   GET  /api/overview            KPI tiles, status mix, on-hand by site
#   GET  /api/shipments/at-risk   delayed or temperature-excursion shipments
#   GET  /api/map                 sites, hospitals/clinics, active routes (Network Map page)
#   POST /api/genie/ask           natural-language question via the Genie space
#   POST /api/agent/chat          WeatherWise agent (serving endpoint)
#
# Everything else serves the built React app from ./static.

import datetime
import decimal
import json
import logging
import os
import threading
import time
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("weatherwise")

CATALOG = os.getenv("TARGET_CATALOG", "bldemos")
SCHEMA = os.getenv("TARGET_SCHEMA", "agentbricks_weatherwise")
WAREHOUSE_ID = os.getenv("WAREHOUSE_ID") or os.getenv("DATABRICKS_WAREHOUSE_ID")
GENIE_SPACE_ID = os.getenv("GENIE_SPACE_ID")
SERVING_ENDPOINT = os.getenv("SERVING_ENDPOINT")
TEMP_CEILING_F = float(os.getenv("TEMP_CEILING_F", "30"))

# Lakebase (optional): Postgres copies of the UC tables, kept in sync by Lakebase synced tables.
# Only the read endpoints (overview, at-risk, map) use it, and only when LAKEBASE_ENDPOINT is set.
# The `postgres` app resource injects LAKEBASE_ENDPOINT and PGHOST/PGUSER/PGDATABASE/PGPORT.
LAKEBASE_ENDPOINT = os.getenv("LAKEBASE_ENDPOINT")  # projects/<p>/branches/<b>/endpoints/<e>
LAKEBASE_SCHEMA = os.getenv("LAKEBASE_SCHEMA", SCHEMA)  # Postgres schema holding the synced tables
LAKEBASE_RETRY_S = 60  # after a Lakebase error, read from the warehouse for this long before retrying
TOKEN_REFRESH_S = 45 * 60  # OAuth database credentials are valid for 1 hour

STATIC_DIR = Path(__file__).parent / "static"
NUMERIC_TYPES = {"INT", "INTEGER", "LONG", "BIGINT", "SHORT", "SMALLINT", "TINYINT", "DOUBLE", "FLOAT", "DECIMAL"}

app = FastAPI(title="MedTech Weatherwise Agent")


def t(name: str) -> str:
    return f"{CATALOG}.{SCHEMA}.{name}"


@lru_cache(maxsize=1)
def workspace() -> WorkspaceClient:
    return WorkspaceClient()


# ──────────────────────────────────────────────────────────────────────────────
# SQL (SQL warehouse, service-principal identity)
# ──────────────────────────────────────────────────────────────────────────────
def run_sql(statement: str) -> List[Dict[str, Any]]:
    if not WAREHOUSE_ID:
        raise RuntimeError("WAREHOUSE_ID is not configured")
    resp = workspace().statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID,
        statement=statement,
        wait_timeout="30s",
    )
    state = resp.status.state if resp.status else None
    if state != StatementState.SUCCEEDED:
        detail = resp.status.error.message if resp.status and resp.status.error else state
        raise RuntimeError(f"SQL failed: {detail}")

    columns = resp.manifest.schema.columns if resp.manifest and resp.manifest.schema else []
    names = [c.name for c in columns]
    numeric = {c.name for c in columns if (c.type_text or "").split("(")[0].upper() in NUMERIC_TYPES}
    rows = resp.result.data_array if resp.result and resp.result.data_array else []

    out: List[Dict[str, Any]] = []
    for row in rows:
        rec: Dict[str, Any] = {}
        for name, value in zip(names, row):
            if value is None:
                rec[name] = None
            elif name in numeric:
                rec[name] = float(value) if "." in str(value) else int(value)
            else:
                rec[name] = value
        out.append(rec)
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Lakebase (Postgres) read path: synced tables, pooled connections, OAuth refresh
# ──────────────────────────────────────────────────────────────────────────────
_pg_lock = threading.RLock()
_pg_engine: Any = None
_pg_token: Dict[str, Any] = {"value": None, "at": 0.0}
_pg_retry_at = 0.0


def lakebase_enabled() -> bool:
    return bool(LAKEBASE_ENDPOINT)


def pt(name: str) -> str:
    """Postgres name of a synced table (schema-qualified, quoted)."""
    return f'"{LAKEBASE_SCHEMA}".{name}'


def _pg_password() -> str:
    """Current OAuth database credential; minted via the app's own identity and refreshed before expiry."""
    with _pg_lock:
        if _pg_token["value"] is None or time.time() - _pg_token["at"] > TOKEN_REFRESH_S:
            _pg_token["value"] = workspace().postgres.generate_database_credential(endpoint=LAKEBASE_ENDPOINT).token
            _pg_token["at"] = time.time()
        return _pg_token["value"]


def _pg() -> Any:
    """Lazily-built SQLAlchemy engine (psycopg 3). Small pool; the password is injected on every new connection."""
    global _pg_engine
    with _pg_lock:
        if _pg_engine is None:
            from sqlalchemy import create_engine, event
            from sqlalchemy.engine import URL

            ws = workspace()
            host = os.getenv("PGHOST") or ws.postgres.get_endpoint(name=LAKEBASE_ENDPOINT).status.hosts.host
            user = os.getenv("PGUSER") or ws.current_user.me().user_name
            url = URL.create(
                "postgresql+psycopg",
                username=user,
                host=host,
                port=int(os.getenv("PGPORT", "5432")),
                database=os.getenv("PGDATABASE", "databricks_postgres"),
                query={"sslmode": "require"},
            )
            engine = create_engine(url, pool_size=4, max_overflow=4, pool_pre_ping=True, pool_recycle=1800)

            @event.listens_for(engine, "do_connect")
            def _inject_token(dialect, conn_rec, cargs, cparams):
                cparams["password"] = _pg_password()

            _pg_engine = engine
            logger.info("Lakebase read path enabled (schema=%s)", LAKEBASE_SCHEMA)
        return _pg_engine


def _pg_value(value: Any) -> Any:
    """Shape Postgres values like run_sql() shapes warehouse values, so the JSON responses are identical."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, decimal.Decimal):
        return float(value) if "." in str(value) else int(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


def pg_query(statement: str) -> List[Dict[str, Any]]:
    from sqlalchemy import text

    with _pg().connect() as conn:
        return [{k: _pg_value(v) for k, v in row.items()} for row in conn.execute(text(statement)).mappings()]


def read_rows(pg_statement: str, sql_statement: str) -> List[Dict[str, Any]]:
    """Read from Lakebase synced tables; use the SQL warehouse if Lakebase is not configured,
    is cooling down after a failure, or the query fails."""
    global _pg_retry_at
    if lakebase_enabled() and time.time() >= _pg_retry_at:
        try:
            return pg_query(pg_statement)
        except Exception as exc:  # any Lakebase failure falls back to the warehouse
            _pg_retry_at = time.time() + LAKEBASE_RETRY_S
            logger.warning("Lakebase read failed; using SQL warehouse for %ss: %s", LAKEBASE_RETRY_S, exc)
    return run_sql(sql_statement)


logger.info(
    "Read path for overview/at-risk/map: %s. PG-style env present: %s",
    "Lakebase with SQL warehouse fallback" if lakebase_enabled() else "SQL warehouse (Lakebase not configured)",
    sorted(k for k in os.environ if k.startswith(("PG", "LAKEBASE"))),
)


# ──────────────────────────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────────────────────────
class GenieAsk(BaseModel):
    question: str
    conversation_id: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    content: str


class AgentChat(BaseModel):
    messages: List[ChatMessage]


# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────
def _genie_one_url() -> Optional[str]:
    """Genie One (workspace-wide Genie): GENIE_ONE_URL, else <DATABRICKS_HOST>/one?o=<workspace id>.

    Genie One picks the relevant Genie agent itself; it has no URL for a specific space
    (that is /genie/rooms/<id>, used by the in-app Genie tab).
    """
    explicit = os.getenv("GENIE_ONE_URL")
    if explicit:
        return explicit
    host = (os.getenv("DATABRICKS_HOST") or "").strip().rstrip("/")
    if not host:
        return None
    if not host.startswith(("https://", "http://")):
        host = "https://" + host
    ws_id = os.getenv("DATABRICKS_WORKSPACE_ID", "").strip()
    return f"{host}/one" + (f"?o={ws_id}" if ws_id else "")


@app.get("/api/health")
def health(request: Request) -> Dict[str, Any]:
    return {
        "app": "MedTech Weatherwise Agent",
        "catalog": f"{CATALOG}.{SCHEMA}",
        "warehouse_configured": bool(WAREHOUSE_ID),
        "genie_configured": bool(GENIE_SPACE_ID),
        "agent_configured": bool(SERVING_ENDPOINT),
        "temp_ceiling_f": TEMP_CEILING_F,
        "genie_one_url": _genie_one_url(),
        "user": request.headers.get("x-forwarded-email") or request.headers.get("x-forwarded-user"),
    }


@app.get("/api/overview")
def overview() -> Dict[str, Any]:
    # Postgres notes: NULLS LAST on DESC sorts to match Spark's default null ordering.
    kpi = read_rows(f"""
        SELECT COUNT(*) AS total_shipments,
               SUM(CASE WHEN status = 'In-Transit' THEN 1 ELSE 0 END) AS in_transit,
               SUM(CASE WHEN status = 'Delayed' THEN 1 ELSE 0 END) AS delayed,
               SUM(CASE WHEN (last_recorded_temp_f > temperature_max_f OR last_recorded_temp_f < temperature_min_f) THEN 1 ELSE 0 END) AS temp_excursions
        FROM {pt('shipments')}
    """, f"""
        SELECT COUNT(*) AS total_shipments,
               SUM(CASE WHEN status = 'In-Transit' THEN 1 ELSE 0 END) AS in_transit,
               SUM(CASE WHEN status = 'Delayed' THEN 1 ELSE 0 END) AS delayed,
               SUM(CASE WHEN (last_recorded_temp_f > temperature_max_f OR last_recorded_temp_f < temperature_min_f) THEN 1 ELSE 0 END) AS temp_excursions
        FROM {t('shipments')}
    """)[0]
    inv = read_rows(f"""
        SELECT COALESCE(SUM(on_hand_qty), 0) AS on_hand,
               SUM(CASE WHEN lot_expiry <= CURRENT_DATE + 90 THEN 1 ELSE 0 END) AS expiring_90d
        FROM {pt('inventory')}
    """, f"""
        SELECT COALESCE(SUM(on_hand_qty), 0) AS on_hand,
               SUM(CASE WHEN lot_expiry <= date_add(current_date(), 90) THEN 1 ELSE 0 END) AS expiring_90d
        FROM {t('inventory')}
    """)[0]
    status_mix = read_rows(f"""
        SELECT status, COUNT(*) AS shipments
        FROM {pt('shipments')} GROUP BY status ORDER BY shipments DESC
    """, f"""
        SELECT status, COUNT(*) AS shipments
        FROM {t('shipments')} GROUP BY status ORDER BY shipments DESC
    """)
    by_site = read_rows(f"""
        SELECT site_name, city, state, SUM(on_hand_qty) AS on_hand_units
        FROM {pt('inventory')} GROUP BY site_name, city, state ORDER BY on_hand_units DESC NULLS LAST, site_name, city, state
    """, f"""
        SELECT site_name, city, state, SUM(on_hand_qty) AS on_hand_units
        FROM {t('inventory')} GROUP BY site_name, city, state ORDER BY on_hand_units DESC, site_name, city, state
    """)
    # Site x product grid for the Command Center inventory card (sites carry the type).
    inv_q = """
        SELECT i.site_id, i.site_name, i.state, s.site_type, i.product_id, i.product_name,
               SUM(i.on_hand_qty) AS on_hand
        FROM {inv} i LEFT JOIN {sites} s ON s.site_id = i.site_id
        GROUP BY i.site_id, i.site_name, i.state, s.site_type, i.product_id, i.product_name
    """
    inv_matrix = read_rows(inv_q.format(inv=pt("inventory"), sites=pt("sites")),
                           inv_q.format(inv=t("inventory"), sites=t("sites")))
    return {
        "inventory_matrix": inv_matrix,
        "kpi": {**kpi, **inv},
        "status_mix": status_mix,
        "inventory_by_site": by_site,
        "temp_ceiling_f": TEMP_CEILING_F,
    }


@app.get("/api/shipments/at-risk")
def at_risk() -> List[Dict[str, Any]]:
    # Postgres ORDER BY spelled with Spark's default null ordering (DESC: nulls last; ASC: nulls first).
    return read_rows(f"""
        SELECT shipment_id, product_name, origin, destination, carrier, status, eta_date,
               last_recorded_temp_f, temperature_max_f, temperature_min_f
        FROM {pt('shipments')}
        WHERE status = 'Delayed' OR (last_recorded_temp_f > temperature_max_f OR last_recorded_temp_f < temperature_min_f)
        ORDER BY (last_recorded_temp_f > temperature_max_f OR last_recorded_temp_f < temperature_min_f) DESC NULLS LAST, eta_date ASC NULLS FIRST, shipment_id
        LIMIT 25
    """, f"""
        SELECT shipment_id, product_name, origin, destination, carrier, status, eta_date,
               last_recorded_temp_f, temperature_max_f, temperature_min_f
        FROM {t('shipments')}
        WHERE status = 'Delayed' OR (last_recorded_temp_f > temperature_max_f OR last_recorded_temp_f < temperature_min_f)
        ORDER BY (last_recorded_temp_f > temperature_max_f OR last_recorded_temp_f < temperature_min_f) DESC, eta_date, shipment_id
        LIMIT 25
    """)


@app.post("/api/genie/ask")
def genie_ask(body: GenieAsk) -> JSONResponse:
    if not GENIE_SPACE_ID:
        return JSONResponse({"detail": "GENIE_SPACE_ID is not configured"}, status_code=503)
    ws = workspace()
    if body.conversation_id:
        wait = ws.genie.create_message(
            space_id=GENIE_SPACE_ID,
            conversation_id=body.conversation_id,
            content=body.question.strip(),
        )
    else:
        wait = ws.genie.start_conversation(space_id=GENIE_SPACE_ID, content=body.question.strip())
    message = wait.result(timeout=timedelta(seconds=90))

    conversation_id = message.conversation_id or ""
    message_id = message.id or message.message_id or ""
    if not conversation_id or not message_id:
        return JSONResponse({"detail": "Genie did not return conversation/message IDs"}, status_code=502)

    texts: List[str] = []
    suggestions: List[str] = []
    sql_text: Optional[str] = None
    columns: List[str] = []
    rows: List[List[Any]] = []
    for att in message.attachments or []:
        if att.text and att.text.content:
            texts.append(att.text.content)
        if att.suggested_questions and att.suggested_questions.questions:
            suggestions.extend(att.suggested_questions.questions)
        if att.query and att.query.query:
            sql_text = att.query.query
            if att.attachment_id:
                res = ws.genie.get_message_query_result_by_attachment(
                    space_id=GENIE_SPACE_ID,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    attachment_id=att.attachment_id,
                )
                sr = res.statement_response
                if sr and sr.result and sr.result.data_array:
                    rows = [list(r) for r in sr.result.data_array]
                if sr and sr.manifest and sr.manifest.schema and sr.manifest.schema.columns:
                    columns = [str(c.name) for c in sr.manifest.schema.columns]

    return JSONResponse({
        "conversation_id": conversation_id,
        "message_id": message_id,
        "text": "\n\n".join(texts) if texts else "No text response returned.",
        "sql": sql_text,
        "columns": columns,
        "rows": rows,
        "suggested_questions": suggestions[:4],
    })


def _short(value: Any, limit: int = 600) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= limit else text[:limit] + " …"


def _extract_agent_text(res: Any) -> tuple[str, List[Dict[str, Any]]]:
    """Normalize chat / responses-style agent outputs into (text, steps).

    Each step is one tool call: {"name", "args", "output"} (args/output truncated for display).
    """
    steps: List[Dict[str, Any]] = []
    if isinstance(res, dict) and "output" in res:  # ResponsesAgent shape
        texts: List[str] = []
        by_call: Dict[str, Dict[str, Any]] = {}
        for item in res["output"] or []:
            kind = item.get("type")
            if kind == "function_call":
                step = {"name": item.get("name", "tool"), "args": _short(item.get("arguments", ""), 300), "output": None}
                steps.append(step)
                if item.get("call_id"):
                    by_call[item["call_id"]] = step
            elif kind == "function_call_output":
                step = by_call.get(item.get("call_id", ""))
                if step is not None:
                    step["output"] = _short(item.get("output", ""))
            elif kind == "message" and item.get("role") == "assistant":
                for part in item.get("content") or []:
                    if isinstance(part, dict) and part.get("text"):
                        texts.append(part["text"])
        return ("\n\n".join(texts) or "(no text)", steps)
    if isinstance(res, dict) and "messages" in res:  # ChatAgent shape
        msgs = res["messages"]
        for m in msgs:
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                steps.append({"name": fn.get("name", "tool"), "args": _short(fn.get("arguments", ""), 300), "output": None})
        final = next((m for m in reversed(msgs) if m.get("role") == "assistant" and not m.get("tool_calls")), None)
        return ((final or {}).get("content") or "(no text)", steps)
    if isinstance(res, dict) and "choices" in res:  # chat-completions shape
        content = res["choices"][0]["message"].get("content")
        if isinstance(content, list):
            content = "".join(p.get("text", "") for p in content if p.get("type") == "text")
        return (content or "(no text)", steps)
    return (json.dumps(res)[:2000], steps)


@app.post("/api/agent/chat")
def agent_chat(body: AgentChat) -> JSONResponse:
    if not SERVING_ENDPOINT:
        return JSONResponse({"detail": "SERVING_ENDPOINT is not configured"}, status_code=503)
    from mlflow.deployments import get_deploy_client

    messages = [m.model_dump() for m in body.messages]
    client = get_deploy_client("databricks")
    try:
        # ResponsesAgent ("input") first; fall back to the older ChatAgent ("messages") shape.
        try:
            res = client.predict(endpoint=SERVING_ENDPOINT, inputs={"input": messages})
        except Exception:
            res = client.predict(endpoint=SERVING_ENDPOINT, inputs={"messages": messages, "max_tokens": 700})
    except Exception as exc:
        # Surface the serving error (e.g. "endpoint is in a failed state") instead of a bare 500.
        detail = str(exc)
        if "Response text:" in detail:
            try:
                detail = json.loads(detail.split("Response text:", 1)[1]).get("message", detail)
            except ValueError:
                pass
        return JSONResponse({"detail": f"Agent endpoint error: {detail[:300]}"}, status_code=502)
    text, steps = _extract_agent_text(res)
    return JSONResponse({"content": text, "steps": steps})


def _agent_events(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """One ResponsesAgent output item -> UI events (call / output / text)."""
    kind = item.get("type")
    if kind == "function_call":
        return [{"type": "call", "id": item.get("call_id") or item.get("id"), "name": item.get("name", "tool"),
                 "args": _short(item.get("arguments", ""), 2000)}]
    if kind == "function_call_output":
        raw = item.get("output", "")
        event: Dict[str, Any] = {"type": "output", "id": item.get("call_id")}
        # UC function results are JSON {"format": "CSV"|"SCALAR", "value": ...}. Count rows on the
        # full result and shorten only the inner value, so the JSON stays parseable in the UI.
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else None
        except ValueError:
            parsed = None
        if isinstance(parsed, dict) and "value" in parsed:
            value = str(parsed.get("value") or "")
            if parsed.get("format") == "CSV":
                event["rows"] = max(0, len([ln for ln in value.split("\n") if ln.strip()]) - 1)
            parsed["value"] = _short(value, 4000)
            event["output"] = json.dumps(parsed, default=str)
        else:
            event["output"] = _short(raw, 4000)
        return [event]
    if kind == "message" and item.get("role") == "assistant":
        text = "".join(p.get("text", "") for p in item.get("content") or [] if isinstance(p, dict))
        return [{"type": "text", "text": text}] if text else []
    return []


@app.post("/api/agent/stream")
def agent_stream(body: AgentChat):
    """Stream the agent's tool calls and answer as NDJSON, one event per line.

    Events: {"type": "call", id, name, args} when a tool starts, {"type": "output", id, output}
    when it returns, {"type": "text", text} for answer text, then {"type": "done"} or
    {"type": "error", detail}. Uses the serving endpoint's SSE stream (ResponsesAgent
    predict_stream), so each step shows up as soon as it happens.
    """
    from fastapi.responses import StreamingResponse
    import requests

    if not SERVING_ENDPOINT:
        return JSONResponse({"detail": "SERVING_ENDPOINT is not configured"}, status_code=503)
    messages = [m.model_dump() for m in body.messages]

    def gen():
        w = workspace()
        url = f"{w.config.host.rstrip('/')}/serving-endpoints/{SERVING_ENDPOINT}/invocations"
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream", **w.config.authenticate()}
        try:
            with requests.post(url, headers=headers, json={"input": messages, "stream": True},
                               stream=True, timeout=(10, 600)) as r:
                if r.status_code >= 400:
                    detail = r.text[:300]
                    try:
                        detail = json.loads(r.text).get("message", detail)
                    except ValueError:
                        pass
                    yield json.dumps({"type": "error", "detail": f"Agent endpoint error: {detail}"}) + "\n"
                    return
                for raw in r.iter_lines(decode_unicode=True):
                    if not raw or not raw.startswith("data:"):
                        continue
                    data = raw[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        evt = json.loads(data)
                    except ValueError:
                        continue
                    if evt.get("type") == "response.output_item.done" and evt.get("item"):
                        for out in _agent_events(evt["item"]):
                            yield json.dumps(out, default=str) + "\n"
                    elif evt.get("error_code") or evt.get("type") == "error":
                        yield json.dumps({"type": "error", "detail": str(evt.get("message") or evt)[:300]}) + "\n"
                        return
        except Exception as exc:  # network / timeout
            yield json.dumps({"type": "error", "detail": f"Agent stream failed: {str(exc)[:300]}"}) + "\n"
            return
        yield json.dumps({"type": "done"}) + "\n"

    # X-Accel-Buffering: stop proxies from holding the stream until it ends.
    return StreamingResponse(gen(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ──────────────────────────────────────────────────────────────────────────────
# Network Map
# ──────────────────────────────────────────────────────────────────────────────
# MAP_CSV_DIR (optional, local dev only): read ../data/*.csv instead of UC tables, so the
# map can be previewed before the new tables are loaded into the workspace.
MAP_CSV_DIR = os.getenv("MAP_CSV_DIR")


def _csv(name: str) -> List[Dict[str, Any]]:
    import csv

    def conv(v: str) -> Any:
        if v == "":
            return None
        try:
            return int(v)
        except ValueError:
            try:
                return float(v)
            except ValueError:
                return v

    with open(Path(MAP_CSV_DIR) / f"{name}.csv", newline="") as f:
        return [{k: conv(v) for k, v in r.items()} for r in csv.DictReader(f)]


def _map_data() -> Dict[str, List[Dict[str, Any]]]:
    if MAP_CSV_DIR:
        return {n: _csv(n) for n in ("sites", "facilities", "shipments", "inventory")}
    # Date columns are cast to text in both dialects: the map compares ISO date strings.
    return {
        "sites": read_rows(f"SELECT * FROM {pt('sites')}", f"SELECT * FROM {t('sites')}"),
        "facilities": read_rows(f"SELECT * FROM {pt('facilities')}", f"SELECT * FROM {t('facilities')}"),
        "shipments": read_rows(f"""
            SELECT shipment_id, product_name, sku, supplier_id, origin, destination, carrier, status,
                   CAST(eta_date AS TEXT) AS eta_date, CAST(original_eta_date AS TEXT) AS original_eta_date,
                   CAST(procedure_date AS TEXT) AS procedure_date, priority, delay_hours, delay_reason,
                   last_recorded_temp_f, temperature_max_f, temperature_min_f,
                   destination_facility_id, routed_via_site_id,
                   origin_latitude, origin_longitude, destination_latitude, destination_longitude, route_miles
            FROM {pt('shipments')} WHERE status <> 'Delivered'
        """, f"""
            SELECT shipment_id, product_name, sku, supplier_id, origin, destination, carrier, status,
                   CAST(eta_date AS STRING) AS eta_date, CAST(original_eta_date AS STRING) AS original_eta_date,
                   CAST(procedure_date AS STRING) AS procedure_date, priority, delay_hours, delay_reason,
                   last_recorded_temp_f, temperature_max_f, temperature_min_f,
                   destination_facility_id, routed_via_site_id,
                   origin_latitude, origin_longitude, destination_latitude, destination_longitude, route_miles
            FROM {t('shipments')} WHERE status <> 'Delivered'
        """),
        "inventory": read_rows(
            f"SELECT site_id, product_name, on_hand_qty, CAST(lot_expiry AS TEXT) AS lot_expiry FROM {pt('inventory')}",
            f"SELECT site_id, product_name, on_hand_qty, CAST(lot_expiry AS STRING) AS lot_expiry FROM {t('inventory')}",
        ),
    }


@app.get("/api/map")
def network_map() -> Dict[str, Any]:
    d = _map_data()
    active = [s for s in d["shipments"] if s["status"] != "Delivered"]

    def excursion(s: Dict[str, Any]) -> bool:
        # Each shipment has its own range: heat/thaw above the max, freeze below the min.
        temp, hi, lo = s.get("last_recorded_temp_f"), s.get("temperature_max_f"), s.get("temperature_min_f")
        return temp is not None and ((hi is not None and temp > hi) or (lo is not None and temp < lo))

    def misses_procedure(s: Dict[str, Any]) -> bool:
        return bool(s.get("procedure_date")) and s["eta_date"] > s["procedure_date"]

    by_fac: Dict[str, List[Dict[str, Any]]] = {}
    for s in active:
        by_fac.setdefault(s["destination_facility_id"], []).append(s)

    facilities = []
    for f in d["facilities"]:
        ships = by_fac.get(f["facility_id"], [])
        facilities.append({
            **f,
            "inbound": len(ships),
            "delayed": sum(s["status"] == "Delayed" for s in ships),
            "excursions": sum(excursion(s) for s in ships),
            "procedures_at_risk": sum(misses_procedure(s) for s in ships),
        })

    inv_by_site: Dict[str, List[Dict[str, Any]]] = {}
    for r in d["inventory"]:
        inv_by_site.setdefault(r["site_id"], []).append(r)
    sites = []
    for st in d["sites"]:
        inv = inv_by_site.get(st["site_id"], [])
        sites.append({
            **st,
            "on_hand_units": sum(int(r["on_hand_qty"] or 0) for r in inv),
            "products": sorted({r["product_name"] for r in inv}),
            "low_stock_products": sorted({r["product_name"] for r in inv if int(r["on_hand_qty"] or 0) <= 4}),
            "routed_shipments": sum(s["routed_via_site_id"] == st["site_id"] for s in active),
        })

    routes = [{
        **{k: s.get(k) for k in (
            "shipment_id", "product_name", "origin", "destination", "carrier", "status", "priority",
            "eta_date", "original_eta_date", "procedure_date", "delay_hours", "delay_reason",
            "last_recorded_temp_f", "temperature_max_f", "destination_facility_id", "route_miles",
            "origin_latitude", "origin_longitude", "destination_latitude", "destination_longitude")},
        "excursion": excursion(s),
        "misses_procedure": misses_procedure(s),
    } for s in active]

    return {
        "sites": sites,
        "facilities": facilities,
        "routes": routes,
        "summary": {
            "supply_centers": sum(s["site_type"] == "Supply Center" for s in sites),
            "distribution_centers": sum(s["site_type"] == "Distribution Center" for s in sites),
            "hospitals": sum(f["facility_type"] == "Hospital" for f in facilities),
            "clinics": sum(f["facility_type"] == "Clinic" for f in facilities),
            "active_shipments": len(active),
            "delayed": sum(s["status"] == "Delayed" for s in active),
            "excursions": sum(excursion(s) for s in active),
            "procedures_at_risk": sum(misses_procedure(s) for s in active),
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# Static SPA
# ──────────────────────────────────────────────────────────────────────────────
if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.get("/{full_path:path}")
def spa(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    # Plain files from the build (e.g. talk-track.html from frontend/public); everything else is the SPA.
    if full_path:
        candidate = (STATIC_DIR / full_path).resolve()
        if candidate.is_file() and STATIC_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse({"detail": "Frontend not built. Run `npm run build` in dapp/frontend."}, status_code=503)
