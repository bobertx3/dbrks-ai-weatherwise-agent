import { useEffect, useState } from "react";
import { getJSON, type AtRiskShipment, type Overview } from "../api";

const nf = new Intl.NumberFormat("en-US");

// warehouseOk is null until /api/health has answered; don't judge config before then.
export default function Dashboard({ catalog, warehouseOk }: { catalog: string; warehouseOk: boolean | null }) {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [atRisk, setAtRisk] = useState<AtRiskShipment[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (warehouseOk === null) return;
    if (!warehouseOk) {
      setError("SQL warehouse is not configured for this app.");
      return;
    }
    setError(null);
    Promise.all([getJSON<Overview>("/api/overview"), getJSON<AtRiskShipment[]>("/api/shipments/at-risk")])
      .then(([o, r]) => {
        setOverview(o);
        setAtRisk(r);
      })
      .catch((e: Error) => setError(e.message));
  }, [warehouseOk]);

  const kpi = overview?.kpi;
  const statusMax = Math.max(1, ...(overview?.status_mix.map((s) => s.shipments) ?? [1]));
  const siteMax = Math.max(1, ...(overview?.inventory_by_site.map((s) => s.on_hand_units) ?? [1]));

  return (
    <>
      <div className="pane-head">
        <div>
          <div className="lbl teal">LIVE SUPPLY CHAIN</div>
          <h2>Shipments &amp; inventory</h2>
        </div>
        <div className="lbl">{catalog}</div>
      </div>

      {error && <div className="notice">Dashboard data unavailable: {error}</div>}

      <div className="kpis">
        <Kpi label="Shipments" value={kpi?.total_shipments} caption="tracked in the window" />
        <Kpi label="In transit" value={kpi?.in_transit} caption="on the road now" tone="teal" />
        <Kpi label="Delayed" value={kpi?.delayed} caption="need escalation" tone="coral" />
        <Kpi label="Temp excursions" value={kpi?.temp_excursions} caption="sensor above SOP max" tone="amber" />
        <Kpi label="On hand units" value={kpi?.on_hand} caption="across all sites" />
        <Kpi label="Lots expiring" value={kpi?.expiring_90d} caption="within 90 days" tone="amber" />
      </div>

      <div className="grid2">
        <div className="card">
          <div className="lbl">STATUS MIX</div>
          <h3>Shipments by status</h3>
          {!overview ? (
            <Skeleton />
          ) : (
            <div className="bars">
              {overview.status_mix.map((s) => (
                <BarRow
                  key={s.status}
                  name={s.status}
                  value={s.shipments}
                  max={statusMax}
                  color={s.status === "Delayed" ? "var(--coral)" : s.status === "In-Transit" ? "var(--teal)" : "var(--blue)"}
                />
              ))}
            </div>
          )}
        </div>
        <div className="card">
          <div className="lbl">INVENTORY</div>
          <h3>On-hand units by site</h3>
          {!overview ? (
            <Skeleton />
          ) : (
            <div className="bars">
              {overview.inventory_by_site.map((s) => (
                <BarRow key={s.site_name} name={s.site_name} value={s.on_hand_units} max={siteMax} color="var(--teal)" />
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="lbl coral">AT RISK</div>
        <h3>Delayed or temperature excursion</h3>
        {!atRisk ? (
          <Skeleton />
        ) : atRisk.length === 0 ? (
          <p className="muted">No shipments at risk right now.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Shipment</th>
                  <th>Product</th>
                  <th>Route</th>
                  <th>Carrier</th>
                  <th>Status</th>
                  <th>ETA</th>
                  <th>Sensor °F</th>
                </tr>
              </thead>
              <tbody>
                {atRisk.map((r) => (
                  <tr key={r.shipment_id}>
                    <td className="mono teal">{r.shipment_id}</td>
                    <td>{r.product_name}</td>
                    <td>
                      {r.origin} → {r.destination}
                    </td>
                    <td>{r.carrier}</td>
                    <td>
                      <span className={`tag ${r.status === "Delayed" ? "delayed" : r.status === "In-Transit" ? "transit" : ""}`}>
                        {r.status}
                      </span>
                    </td>
                    <td className="mono">{String(r.eta_date).slice(0, 10)}</td>
                    <td className={r.last_recorded_temp_f != null && r.temperature_max_f != null && r.last_recorded_temp_f > r.temperature_max_f ? "hot" : "mono"}>
                      {r.last_recorded_temp_f ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}

function Kpi({ label, value, caption, tone }: { label: string; value?: number; caption: string; tone?: "teal" | "coral" | "amber" }) {
  const color = tone === "teal" ? "var(--teal)" : tone === "coral" ? "var(--coral)" : tone === "amber" ? "var(--amber)" : "var(--text)";
  return (
    <div className="kpi">
      <div className="lbl">{label}</div>
      <div className="v" style={{ color }}>
        {value == null ? <span className="skel" style={{ display: "inline-block", width: 60, height: 22 }} /> : nf.format(value)}
      </div>
      <div className="cap">{caption}</div>
    </div>
  );
}

function BarRow({ name, value, max, color }: { name: string; value: number; max: number; color: string }) {
  return (
    <div className="bar-row">
      <div className="name" title={name}>{name}</div>
      <div className="bar-track">
        <div className="bar-fill" style={{ width: `${(value / max) * 100}%`, background: color }} />
      </div>
      <div className="num">{nf.format(value)}</div>
    </div>
  );
}

function Skeleton() {
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {[0, 1, 2].map((i) => (
        <div key={i} className="skel" style={{ height: 14 }} />
      ))}
    </div>
  );
}
