import { useEffect, useMemo, useRef, useState } from "react";
import { Bot } from "lucide-react";
import { getJSON, type MapRoute, type NetworkMap as MapData, type Overview } from "../api";
import NetworkMap from "./NetworkMap";
import { BarRow, Kpi, Skeleton } from "./Dashboard";

const STATUS_ORDER = ["In-Transit", "Delayed", "Out-for-Delivery", "Label-Create", "Delivered"];
const STATUS_TONE: Record<string, string> = { "In-Transit": "var(--teal)", Delayed: "var(--coral)", "Out-for-Delivery": "var(--blue)", "Label-Create": "var(--soft)", Delivered: "var(--muted)" };
const nf = new Intl.NumberFormat("en-US");
const ROW_LIMIT = 12; // riskiest first; the rest behind "Show all"

/** Risk first: surgery missed, then sensor excursion, then delayed; then soonest ETA. */
function riskRank(r: MapRoute) {
  return r.misses_procedure ? 0 : r.excursion ? 1 : r.status === "Delayed" ? 2 : 3;
}

function askFor(r: MapRoute): string {
  const why = r.misses_procedure
    ? `It is due ${r.eta_date}, after the ${r.procedure_date} procedure.`
    : r.excursion
      ? `Its sensor reads ${r.last_recorded_temp_f}°F against a ${r.temperature_max_f}°F max.`
      : r.status === "Delayed"
        ? `It is delayed ${r.delay_hours}h${r.delay_reason ? ` (${r.delay_reason})` : ""}.`
        : "";
  return `Assess shipment ${r.shipment_id} (${r.product_name}, ${r.origin} → ${r.destination}). ${why} What is the risk, what does the supplier SOP say, and is there backup inventory nearby? No email or SMS.`;
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
  const siteMax = Math.max(1, ...(overview?.inventory_by_site.map((s) => s.on_hand_units) ?? [1]));

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
                  <th>Product</th>
                  <th>Route</th>
                  <th>Status</th>
                  <th title="STAT: needed for a scheduled procedure, ship immediately">Priority</th>
                  <th>ETA</th>
                  <th>Surgery</th>
                  <th className="num">Sensor °F</th>
                  <th aria-label="Ask agent" />
                </tr>
              </thead>
              <tbody>
                {(showAll ? rows : rows.slice(0, ROW_LIMIT)).map((r) => (
                  <tr key={r.shipment_id} className={focus?.shipment_id === r.shipment_id ? "sel" : ""} onClick={() => pick(r)}>
                    <td className="mono teal">{r.shipment_id}</td>
                    <td>{r.product_name}</td>
                    <td className="route">{r.origin} → {r.destination}</td>
                    <td>
                      <span className={`tag ${r.status === "Delayed" ? "delayed" : r.status === "In-Transit" ? "transit" : ""}`}>{r.status}</span>
                      {r.status === "Delayed" && r.delay_hours > 0 && <span className="muted small"> +{r.delay_hours}h</span>}
                    </td>
                    <td>
                      <span className={`pill ${r.priority === "STAT" ? "stat" : ""}`} title={r.priority === "STAT" ? "STAT: needed for a scheduled procedure, ship immediately" : undefined}>
                        {r.priority}
                      </span>
                    </td>
                    <td className="mono">{String(r.eta_date).slice(0, 10)}</td>
                    <td className={`mono ${r.misses_procedure ? "miss" : ""}`} title={r.misses_procedure ? "Arrives after the procedure" : undefined}>
                      {r.procedure_date ? String(r.procedure_date).slice(0, 10) : "—"}
                    </td>
                    <td className={`num ${r.excursion ? "hot" : "mono"}`}>{r.last_recorded_temp_f ?? "—"}</td>
                    <td>
                      <button
                        className="row-ask"
                        title="Ask the WeatherWise agent about this shipment"
                        onClick={(e) => {
                          e.stopPropagation();
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

      <div className="card">
        <div className="lbl">INVENTORY</div>
        <h3>On-hand units by site{kpi ? ` · ${nf.format(kpi.on_hand)} total` : ""}</h3>
        {!overview ? (
          <Skeleton />
        ) : (
          <div className="bars cc-bars">
            {overview.inventory_by_site.map((s) => (
              <BarRow key={s.site_name} name={s.site_name} value={s.on_hand_units} max={siteMax} color="var(--teal)" />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
