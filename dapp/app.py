# app.py — MedTech Weatherwise Agent (FastAPI backend + React SPA)
#
# API (all under /api):
#   GET  /api/health              config + signed-in user
#   GET  /api/overview            KPI tiles, status mix, on-hand by site
#   GET  /api/shipments/at-risk   delayed or temperature-excursion shipments
#   GET  /api/map                 sites, hospitals/clinics, active routes, forecast (Network Map page)
#   POST /api/genie/ask           natural-language question via the Genie space
#   POST /api/agent/chat          WeatherWise agent (serving endpoint)
#
# Everything else serves the built React app from ./static.

import json
import os
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

CATALOG = os.getenv("TARGET_CATALOG", "bldemos")
SCHEMA = os.getenv("TARGET_SCHEMA", "agentbricks_weatherwise")
WAREHOUSE_ID = os.getenv("WAREHOUSE_ID") or os.getenv("DATABRICKS_WAREHOUSE_ID")
GENIE_SPACE_ID = os.getenv("GENIE_SPACE_ID")
SERVING_ENDPOINT = os.getenv("SERVING_ENDPOINT")
TEMP_CEILING_F = float(os.getenv("TEMP_CEILING_F", "30"))

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
@app.get("/api/health")
def health(request: Request) -> Dict[str, Any]:
    return {
        "app": "MedTech Weatherwise Agent",
        "catalog": f"{CATALOG}.{SCHEMA}",
        "warehouse_configured": bool(WAREHOUSE_ID),
        "genie_configured": bool(GENIE_SPACE_ID),
        "agent_configured": bool(SERVING_ENDPOINT),
        "temp_ceiling_f": TEMP_CEILING_F,
        "user": request.headers.get("x-forwarded-email") or request.headers.get("x-forwarded-user"),
    }


@app.get("/api/overview")
def overview() -> Dict[str, Any]:
    kpi = run_sql(f"""
        SELECT COUNT(*) AS total_shipments,
               SUM(CASE WHEN status = 'In-Transit' THEN 1 ELSE 0 END) AS in_transit,
               SUM(CASE WHEN status = 'Delayed' THEN 1 ELSE 0 END) AS delayed,
               SUM(CASE WHEN last_recorded_temp_f > temperature_max_f THEN 1 ELSE 0 END) AS temp_excursions
        FROM {t('shipments')}
    """)[0]
    inv = run_sql(f"""
        SELECT COALESCE(SUM(on_hand_qty), 0) AS on_hand,
               SUM(CASE WHEN lot_expiry <= date_add(current_date(), 90) THEN 1 ELSE 0 END) AS expiring_90d
        FROM {t('inventory')}
    """)[0]
    status_mix = run_sql(f"""
        SELECT status, COUNT(*) AS shipments
        FROM {t('shipments')} GROUP BY status ORDER BY shipments DESC
    """)
    by_site = run_sql(f"""
        SELECT site_name, city, state, SUM(on_hand_qty) AS on_hand_units
        FROM {t('inventory')} GROUP BY site_name, city, state ORDER BY on_hand_units DESC
    """)
    return {
        "kpi": {**kpi, **inv},
        "status_mix": status_mix,
        "inventory_by_site": by_site,
        "temp_ceiling_f": TEMP_CEILING_F,
    }


@app.get("/api/shipments/at-risk")
def at_risk() -> List[Dict[str, Any]]:
    return run_sql(f"""
        SELECT shipment_id, product_name, origin, destination, carrier, status, eta_date,
               last_recorded_temp_f, temperature_max_f
        FROM {t('shipments')}
        WHERE status = 'Delayed' OR last_recorded_temp_f > temperature_max_f
        ORDER BY (last_recorded_temp_f > temperature_max_f) DESC, eta_date
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
        return {n: _csv(n) for n in ("sites", "facilities", "shipments", "inventory", "weather_forecast")}
    return {
        "sites": run_sql(f"SELECT * FROM {t('sites')}"),
        "facilities": run_sql(f"SELECT * FROM {t('facilities')}"),
        "shipments": run_sql(f"""
            SELECT shipment_id, product_name, sku, supplier_id, origin, destination, carrier, status,
                   CAST(eta_date AS STRING) AS eta_date, CAST(original_eta_date AS STRING) AS original_eta_date,
                   CAST(procedure_date AS STRING) AS procedure_date, priority, delay_hours, delay_reason,
                   last_recorded_temp_f, temperature_max_f, temperature_min_f,
                   destination_facility_id, routed_via_site_id,
                   origin_latitude, origin_longitude, destination_latitude, destination_longitude, route_miles
            FROM {t('shipments')} WHERE status <> 'Delivered'
        """),
        "inventory": run_sql(f"SELECT site_id, product_name, on_hand_qty, CAST(lot_expiry AS STRING) AS lot_expiry FROM {t('inventory')}"),
        "weather_forecast": run_sql(f"SELECT * FROM {t('weather_forecast')}"),
    }


@app.get("/api/map")
def network_map() -> Dict[str, Any]:
    d = _map_data()
    weather = {f"{w['city']}, {w['state']}": w for w in d["weather_forecast"]}
    active = [s for s in d["shipments"] if s["status"] != "Delivered"]

    def excursion(s: Dict[str, Any]) -> bool:
        temp, hi = s.get("last_recorded_temp_f"), s.get("temperature_max_f")
        return temp is not None and hi is not None and temp > hi

    def misses_procedure(s: Dict[str, Any]) -> bool:
        return bool(s.get("procedure_date")) and s["eta_date"] > s["procedure_date"]

    by_fac: Dict[str, List[Dict[str, Any]]] = {}
    for s in active:
        by_fac.setdefault(s["destination_facility_id"], []).append(s)

    facilities = []
    for f in d["facilities"]:
        ships = by_fac.get(f["facility_id"], [])
        wx = weather.get(f["metro"])
        facilities.append({
            **f,
            "inbound": len(ships),
            "delayed": sum(s["status"] == "Delayed" for s in ships),
            "excursions": sum(excursion(s) for s in ships),
            "procedures_at_risk": sum(misses_procedure(s) for s in ships),
            "forecast_high_f": wx["high_f"] if wx else None,
            "forecast_low_f": wx["low_f"] if wx else None,
            "weather_alert": (wx or {}).get("weather_alert") or None,
        })

    inv_by_site: Dict[str, List[Dict[str, Any]]] = {}
    for r in d["inventory"]:
        inv_by_site.setdefault(r["site_id"], []).append(r)
    sites = []
    for st in d["sites"]:
        inv = inv_by_site.get(st["site_id"], [])
        wx = weather.get(f"{st['city']}, {st['state']}")
        sites.append({
            **st,
            "on_hand_units": sum(int(r["on_hand_qty"] or 0) for r in inv),
            "products": sorted({r["product_name"] for r in inv}),
            "low_stock_products": sorted({r["product_name"] for r in inv if int(r["on_hand_qty"] or 0) <= 4}),
            "routed_shipments": sum(s["routed_via_site_id"] == st["site_id"] for s in active),
            "forecast_high_f": wx["high_f"] if wx else None,
            "forecast_low_f": wx["low_f"] if wx else None,
            "weather_alert": (wx or {}).get("weather_alert") or None,
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
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse({"detail": "Frontend not built. Run `npm run build` in dapp/frontend."}, status_code=503)
