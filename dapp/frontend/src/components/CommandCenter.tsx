import { useEffect, useMemo, useRef, useState } from "react";
import { Bot } from "lucide-react";
import { getJSON, type MapRoute, type NetworkMap as MapData, type Overview } from "../api";
import NetworkMap from "./NetworkMap";
import { callClass, tempCall } from "../tempCall";
import InventoryGrid from "./InventoryGrid";
import { Kpi, Skeleton } from "./Dashboard";

const STATUS_ORDER = ["In-Transit", "Delayed", "Out-for-Delivery", "Label-Create", "Delivered"];
const STATUS_TONE: Record<string, string> = { "In-Transit": "var(--teal)", Delayed: "var(--coral)", "Out-for-Delivery": "var(--blue)", "Label-Create": "var(--soft)", Delivered: "var(--muted)" };
const nf = new Intl.NumberFormat("en-US");
const ROW_LIMIT = 12; // riskiest first; the rest behind "Show all"

/** Risk first: sensor already out of range, then delayed (longer weather exposure); then soonest ETA. */
const PRI: Record<string, number> = { STAT: 0, Urgent: 1, Routine: 2 };
function riskRank(r: MapRoute) {
  return (r.excursion ? 0 : r.status === "Delayed" ? 10 : 20) + (PRI[r.priority] ?? 3);
}


function askFor(r: MapRoute): string {
  const call = tempCall(r);
  const why = call
    ? `Its sensor reads ${r.last_recorded_temp_f}°F (${call}; range ${r.temperature_min_f}–${r.temperature_max_f}°F).`
    : r.status === "Delayed"
      ? `It is delayed ${r.delay_hours}h${r.delay_reason ? ` (${r.delay_reason})` : ""}.`
      : "";
  return `Assess shipment ${r.shipment_id} (${r.product_name}, ${r.origin} → ${r.destination}). ${why} Is it at weather or temperature risk on arrival (sensor and destination forecast)? What does the supplier SOP say, and is there backup stock nearby? No email or SMS.`;
}

export default function CommandCenter({
  catalog,
  warehouseOk,
  onAsk,
}: {
  catalog: string;
  warehouseOk: boolean | null;
  onAsk: (prompt: string) => void;
}) {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [map, setMap] = useState<MapData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [focus, setFocus] = useState<MapRoute | null>(null);
  const [showAll, setShowAll] = useState(false);
  const mapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (warehouseOk === null) return;
    if (!warehouseOk) {
      setError("SQL warehouse is not configured for this app.");
      return;
    }
    setError(null);
    getJSON<Overview>("/api/overview").then(setOverview).catch((e: Error) => setError(e.message));
    getJSON<MapData>("/api/map").then(setMap).catch((e: Error) => setError(e.message));
  }, [warehouseOk]);

  const routes = map?.routes ?? [];
  const chips = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of routes) counts.set(r.status, (counts.get(r.status) ?? 0) + 1);
    const ordered = [...counts.keys()].sort(
      (a, b) => (STATUS_ORDER.indexOf(a) + 1 || 99) - (STATUS_ORDER.indexOf(b) + 1 || 99) || a.localeCompare(b),
    );
    return ordered.map((s) => ({ status: s, count: counts.get(s) ?? 0 }));
  }, [routes]);

  const rows = useMemo(
    () =>
      routes
        .filter((r) => !status || r.status === status)
        .slice()
        .sort((a, b) => riskRank(a) - riskRank(b) || a.eta_date.localeCompare(b.eta_date)),
    [routes, status],
  );

  const kpi = overview?.kpi;
  const statusTiles = useMemo(
    () =>
      (overview?.status_mix ?? [])
        .slice()
        .sort((a, b) => (STATUS_ORDER.indexOf(a.status) + 1 || 99) - (STATUS_ORDER.indexOf(b.status) + 1 || 99)),
    [overview],
  );

  function pick(r: MapRoute) {
    setFocus({ ...r }); // new object so re-picking the same row re-flies
    mapRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  return (
    <>
      <div className="pane-head">
        <div>
          <div className="lbl teal">COMMAND CENTER · LIVE SUPPLY CHAIN</div>
          <h2>Temperature-controlled logistics network &amp; shipments</h2>
        </div>
        <div className="lbl">{catalog}</div>
      </div>

      {error && <div className="notice">Dashboard data unavailable: {error}</div>}

      {/* Status is the headline: total + one tile per status. Active-status tiles apply the chip filter. */}
      <div className="kpis">
        <Kpi label="Shipments" value={kpi?.total_shipments} caption="all statuses" />
        {statusTiles.map((t) => {
          const active = chips.some((c) => c.status === t.status);
          return (
            <button
              key={t.status}
              className={`kpi kpi-btn ${status === t.status ? "on" : ""}`}
              disabled={!active}
              onClick={() => setStatus((s) => (s === t.status ? null : t.status))}
              title={active ? `Filter to ${t.status}` : undefined}
            >
              <div className="lbl" title={t.status}>{t.status.replace(/-/g, " ").toUpperCase()}</div>
              <div className="v" style={{ color: STATUS_TONE[t.status] ?? "var(--text)" }}>{nf.format(t.shipments)}</div>
              <div className="cap">{active ? (status === t.status ? "filtering · click to clear" : "click to filter") : "complete"}</div>
            </button>
          );
        })}
      </div>

      <div className="cc-map" ref={mapRef}>
        <NetworkMap warehouseOk={warehouseOk} data={map} statusFilter={status} focus={focus} embedded onAskRoute={(r) => onAsk(askFor(r))} />
      </div>

      <div className="card cc-table">
        <div className="cc-table-head">
          <div>
            <div className="lbl">ACTIVE SHIPMENTS</div>
            <h3>Riskiest first · click a row to see it on the map</h3>
          </div>
          <div className="chips" role="group" aria-label="Filter by status">
            <button className={`chip ${status === null ? "on" : ""}`} onClick={() => setStatus(null)}>
              All <b>{routes.length}</b>
            </button>
            {chips.map((c) => (
              <button
                key={c.status}
                className={`chip ${status === c.status ? "on" : ""} ${c.status === "Delayed" ? "warn" : ""}`}
                onClick={() => setStatus((s) => (s === c.status ? null : c.status))}
              >
                {c.status} <b>{c.count}</b>
              </button>
            ))}
          </div>
        </div>

        {!map ? (
          <Skeleton />
        ) : (
          <div className="table-wrap cc-rows">
            <table>
              <thead>
                <tr>
                  <th>Shipment</th>
                  <th>Product · route</th>
                  <th>Status</th>
                  <th className="col-pri" title="STAT ships first, then Urgent">Priority</th>
                  <th className="col-eta">ETA</th>
                  <th className="num">Sensor °F</th>
                  <th aria-label="Ask agent" />
                </tr>
              </thead>
              <tbody>
                {(showAll ? rows : rows.slice(0, ROW_LIMIT)).map((r) => (
                  <tr key={r.shipment_id} className={focus?.shipment_id === r.shipment_id ? "sel" : ""} onClick={() => pick(r)}>
                    <td className="mono teal">{r.shipment_id}{r.priority === "STAT" && <span className="stat-dot" title="STAT"> ●</span>}</td>
                    <td className="prod" title={`${r.product_name}\n${r.origin} → ${r.destination}`}>
                      <div className="p-name">{r.product_name}</div>
                      <div className="p-route">{r.origin} → {r.destination}</div>
                    </td>
                    <td className="status">
                      <span className={`tag ${r.status === "Delayed" ? "delayed" : r.status === "In-Transit" ? "transit" : ""}`}>{r.status}</span>
                      {r.status === "Delayed" && r.delay_hours > 0 && <span className="muted small"> +{r.delay_hours}h</span>}
                    </td>
                    <td className="col-pri">
                      <span className={`pill ${r.priority === "STAT" ? "stat" : ""}`} title={r.priority === "STAT" ? "STAT: highest shipping priority" : undefined}>
                        {r.priority}
                      </span>
                    </td>
                    <td className="mono col-eta">{String(r.eta_date).slice(0, 10)}</td>
                    <td className={`num ${r.excursion ? "hot" : "mono"}`}>
                      {r.last_recorded_temp_f ?? "—"}
                      {tempCall(r) && <span className={`risk-badge ${callClass(tempCall(r)!)} tbl`}>{tempCall(r)}</span>}
                    </td>
                    <td>
                      <button
                        className="row-ask"
                        data-keep-assist
                        title="Ask the WeatherWise agent about this shipment"
                        onClick={(e) => {
                          e.stopPropagation();
                          pick(r); // highlight it on the map while the agent works
                          onAsk(askFor(r));
                        }}
                      >
                        <Bot size={13} /> Ask
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length > ROW_LIMIT && (
              <button className="show-all" onClick={() => setShowAll((v) => !v)}>
                {showAll ? `Show top ${ROW_LIMIT}` : `Show all ${rows.length} shipments`}
              </button>
            )}
          </div>
        )}
      </div>

      {!overview ? <div className="card"><Skeleton /></div> : <InventoryGrid cells={overview.inventory_matrix ?? []} />}
    </>
  );
}
