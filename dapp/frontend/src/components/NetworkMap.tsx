import { useEffect, useMemo, useState, type ReactNode } from "react";
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, useMap } from "react-leaflet";
import type { LatLngBoundsExpression, LatLngExpression } from "leaflet";
import "leaflet/dist/leaflet.css";
import { AlertTriangle, Building2, Hospital, Stethoscope, Thermometer, Truck, Warehouse, X } from "lucide-react";
import { getJSON, type MapFacility, type MapRoute, type MapSite, type NetworkMap as MapData } from "../api";

// Theme colors (mirror styles.css variables; Leaflet paths need literal values)
const C = {
  teal: "#4fd1c5",
  blue: "#6f9cf2",
  coral: "#f2725e",
  amber: "#e6ab4b",
  ok: "#7fd1a8",
  soft: "#9db0c2",
  dim: "#4a5f73",
};

const VIEWS: Record<string, { label: string; bounds: LatLngBoundsExpression }> = {
  us: { label: "United States", bounds: [[24.5, -125], [49.5, -66.5]] },
  ne: { label: "Northeast", bounds: [[38.6, -80.5], [43.2, -70.5]] },
  nyc: { label: "NYC metro", bounds: [[40.5, -74.3], [41.1, -73.5]] },
};

type Layers = {
  supply: boolean;
  dc: boolean;
  hospital: boolean;
  clinic: boolean;
  routes: "off" | "risk" | "all";
};

type Selected =
  | { kind: "site"; item: MapSite }
  | { kind: "facility"; item: MapFacility }
  | { kind: "route"; item: MapRoute }
  | null;

const nf = new Intl.NumberFormat("en-US");

function facilityColor(f: MapFacility) {
  if (f.excursions > 0 || f.procedures_at_risk > 0) return C.coral;
  if (f.delayed > 0) return C.amber;
  return C.ok;
}

function routeColor(r: MapRoute) {
  if (r.excursion || r.misses_procedure) return C.coral;
  if (r.status === "Delayed") return C.amber;
  return C.teal;
}

function isRisk(r: MapRoute) {
  return r.status === "Delayed" || r.excursion || r.misses_procedure;
}

function FitView({ view }: { view: string }) {
  const map = useMap();
  useEffect(() => {
    map.flyToBounds(VIEWS[view].bounds, { duration: 0.8, padding: [20, 20] });
  }, [view, map]);
  return null;
}

/** Leaflet caches its size; re-measure when the container changes (e.g. the assistant drawer opens). */
function AutoResize() {
  const map = useMap();
  useEffect(() => {
    const ro = new ResizeObserver(() => map.invalidateSize({ animate: false }));
    ro.observe(map.getContainer());
    return () => ro.disconnect();
  }, [map]);
  return null;
}

function FlyTo({ target }: { target: LatLngExpression | null }) {
  const map = useMap();
  useEffect(() => {
    if (target) map.flyTo(target, Math.max(map.getZoom(), 11), { duration: 0.8 });
  }, [target, map]);
  return null;
}

export default function NetworkMap({ warehouseOk }: { warehouseOk: boolean | null }) {
  const [data, setData] = useState<MapData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState("us");
  const [layers, setLayers] = useState<Layers>({ supply: true, dc: true, hospital: true, clinic: true, routes: "risk" });
  const [selected, setSelected] = useState<Selected>(null);
  const [flyTarget, setFlyTarget] = useState<LatLngExpression | null>(null);

  useEffect(() => {
    if (warehouseOk === null) return;
    getJSON<MapData>("/api/map")
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, [warehouseOk]);

  const routes = useMemo(() => {
    if (!data || layers.routes === "off") return [];
    return layers.routes === "all" ? data.routes : data.routes.filter(isRisk);
  }, [data, layers.routes]);

  const facilityById = useMemo(
    () => Object.fromEntries((data?.facilities ?? []).map((f) => [f.facility_id, f])),
    [data],
  );

  const hotList = useMemo(
    () =>
      (data?.routes ?? [])
        .filter((r) => r.misses_procedure || (r.excursion && r.priority !== "Routine"))
        .sort((a, b) => Number(b.misses_procedure) - Number(a.misses_procedure) || a.procedure_date.localeCompare(b.procedure_date)),
    [data],
  );

  const toggle = (k: Exclude<keyof Layers, "routes">) => setLayers((l) => ({ ...l, [k]: !l[k] }));
  const s = data?.summary;

  return (
    <div className="netmap">
      <aside className="netmap-side">
        <div>
          <div className="lbl teal">NETWORK MAP</div>
          <h2 className="netmap-title">Supply centers &amp; care sites</h2>
        </div>

        {error && <div className="notice">Map data unavailable: {error}</div>}

        <div className="netmap-kpis">
          <MiniKpi icon={<Warehouse size={13} />} label="Supply centers" value={s?.supply_centers} tone="teal" />
          <MiniKpi icon={<Building2 size={13} />} label="Distribution" value={s?.distribution_centers} tone="blue" />
          <MiniKpi icon={<Hospital size={13} />} label="Hospitals" value={s?.hospitals} />
          <MiniKpi icon={<Stethoscope size={13} />} label="Clinics" value={s?.clinics} />
          <MiniKpi icon={<Truck size={13} />} label="Delayed" value={s?.delayed} tone="amber" />
          <MiniKpi icon={<Thermometer size={13} />} label="Excursions" value={s?.excursions} tone="coral" />
        </div>

        <div className="card tight">
          <div className="lbl">VIEW</div>
          <div className="seg">
            {Object.entries(VIEWS).map(([k, v]) => (
              <button key={k} className={view === k ? "on" : ""} onClick={() => setView(k)}>
                {v.label}
              </button>
            ))}
          </div>

          <div className="lbl" style={{ marginTop: 12 }}>LAYERS</div>
          <div className="layer-list">
            <LayerToggle on={layers.supply} onClick={() => toggle("supply")} color={C.teal} square label="Supply centers" />
            <LayerToggle on={layers.dc} onClick={() => toggle("dc")} color={C.blue} square label="Distribution centers" />
            <LayerToggle on={layers.hospital} onClick={() => toggle("hospital")} color={C.soft} label="Hospitals" />
            <LayerToggle on={layers.clinic} onClick={() => toggle("clinic")} color={C.soft} small label="Clinics" />
          </div>

          <div className="lbl" style={{ marginTop: 12 }}>SHIPMENT ROUTES</div>
          <div className="seg">
            {(["off", "risk", "all"] as const).map((k) => (
              <button key={k} className={layers.routes === k ? "on" : ""} onClick={() => setLayers((l) => ({ ...l, routes: k }))}>
                {k === "off" ? "Hide" : k === "risk" ? "At risk" : "All active"}
              </button>
            ))}
          </div>

          <div className="legend">
            <span><i style={{ background: C.coral }} /> Excursion / surgery at risk</span>
            <span><i style={{ background: C.amber }} /> Delayed</span>
            <span><i style={{ background: C.ok }} /> On track</span>
          </div>
        </div>

        {selected ? (
          <Details sel={selected} facilityById={facilityById} onClose={() => setSelected(null)} />
        ) : (
          <div className="card tight">
            <div className="lbl coral">
              <AlertTriangle size={11} style={{ verticalAlign: -1 }} /> SURGERIES AT RISK
            </div>
            {!data ? (
              <div className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>Loading…</div>
            ) : hotList.length === 0 ? (
              <div className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>No procedure-critical risks.</div>
            ) : (
              <ul className="hot-list">
                {hotList.slice(0, 8).map((r) => (
                  <li
                    key={r.shipment_id}
                    onClick={() => {
                      setSelected({ kind: "route", item: r });
                      setFlyTarget([r.destination_latitude, r.destination_longitude]);
                    }}
                  >
                    <div className="hl-top">
                      <span className="mono">{r.shipment_id}</span>
                      <span className={`pill ${r.priority === "STAT" ? "stat" : ""}`}>{r.priority}</span>
                    </div>
                    <div className="hl-main">{r.product_name} → {facilityById[r.destination_facility_id]?.facility_name ?? r.destination}</div>
                    <div className="hl-sub">
                      {r.misses_procedure ? `ETA ${r.eta_date} · surgery ${r.procedure_date}` : `${r.last_recorded_temp_f}°F sensor · max ${r.temperature_max_f}°F`}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </aside>

      <div className="netmap-canvas">
        <MapContainer bounds={VIEWS.us.bounds} zoomControl={true} preferCanvas={true} style={{ height: "100%", width: "100%" }}>
          {/* Esri dark gray canvas: keyless (CARTO now requires an API key from browsers) */}
          <TileLayer
            attribution="Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors"
            url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
            maxZoom={16}
          />
          <TileLayer
            url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
            maxZoom={16}
          />
          <AutoResize />
          <FitView view={view} />
          <FlyTo target={flyTarget} />

          {routes.map((r) => (
            <Polyline
              key={r.shipment_id}
              positions={[[r.origin_latitude, r.origin_longitude], [r.destination_latitude, r.destination_longitude]]}
              pathOptions={{
                color: routeColor(r),
                weight: isRisk(r) ? 2.2 : 1.2,
                opacity: isRisk(r) ? 0.8 : 0.35,
                dashArray: r.status === "Delayed" ? "6 6" : undefined,
              }}
              eventHandlers={{ click: () => setSelected({ kind: "route", item: r }) }}
            >
              <Tooltip sticky>{r.shipment_id} · {r.product_name} · {r.status}</Tooltip>
            </Polyline>
          ))}

          {data?.facilities
            .filter((f) => (f.facility_type === "Hospital" ? layers.hospital : layers.clinic))
            .map((f) => (
              <CircleMarker
                key={f.facility_id}
                center={[f.latitude, f.longitude]}
                radius={f.facility_type === "Hospital" ? 7 : 4.5}
                pathOptions={{ color: facilityColor(f), fillColor: facilityColor(f), fillOpacity: 0.85, weight: f.procedures_at_risk ? 3 : 1 }}
                eventHandlers={{ click: () => setSelected({ kind: "facility", item: f }) }}
              >
                <Tooltip direction="top" offset={[0, -6]}>
                  <b>{f.facility_name}</b>
                  <br />
                  {f.facility_type} · {f.inbound} inbound{f.delayed ? ` · ${f.delayed} delayed` : ""}
                </Tooltip>
              </CircleMarker>
            ))}

          {data?.sites
            .filter((st) => (st.site_type === "Supply Center" ? layers.supply : layers.dc))
            .map((st) => {
              const color = st.site_type === "Supply Center" ? C.teal : C.blue;
              return (
                <CircleMarker
                  key={st.site_id}
                  center={[st.latitude, st.longitude]}
                  radius={st.site_type === "Supply Center" ? 10 : 8}
                  pathOptions={{ color, fillColor: "#0a1017", fillOpacity: 0.9, weight: 3 }}
                  eventHandlers={{ click: () => setSelected({ kind: "site", item: st }) }}
                >
                  <Tooltip direction="top" offset={[0, -8]}>
                    <b>{st.site_name}</b>
                    <br />
                    {st.site_type} · {nf.format(st.on_hand_units)} units on hand
                  </Tooltip>
                </CircleMarker>
              );
            })}
        </MapContainer>
      </div>
    </div>
  );
}

function MiniKpi({ icon, label, value, tone }: { icon: ReactNode; label: string; value?: number; tone?: string }) {
  return (
    <div className="mini-kpi">
      <div className={`lbl ${tone ?? ""}`}>{icon} {label}</div>
      <div className={`v ${tone ?? ""}`}>{value == null ? "—" : nf.format(value)}</div>
    </div>
  );
}

function LayerToggle({ on, onClick, color, label, square, small }: { on: boolean; onClick: () => void; color: string; label: string; square?: boolean; small?: boolean }) {
  return (
    <button className={`layer ${on ? "" : "off"}`} onClick={onClick}>
      <i
        style={{
          borderColor: color,
          background: square ? "transparent" : color,
          borderRadius: square ? 3 : 999,
          width: small ? 8 : 12,
          height: small ? 8 : 12,
        }}
      />
      {label}
    </button>
  );
}

function Row({ k, v, tone }: { k: string; v: ReactNode; tone?: string }) {
  return (
    <div className="kv">
      <span className="muted">{k}</span>
      <span className={tone}>{v}</span>
    </div>
  );
}

function Details({ sel, facilityById, onClose }: { sel: NonNullable<Selected>; facilityById: Record<string, MapFacility>; onClose: () => void }) {
  return (
    <div className="card tight details">
      <button className="close" onClick={onClose} aria-label="Close">
        <X size={14} />
      </button>
      {sel.kind === "site" && (
        <>
          <div className={`lbl ${sel.item.site_type === "Supply Center" ? "teal" : ""}`}>{sel.item.site_type.toUpperCase()} · {sel.item.site_id}</div>
          <h3>{sel.item.site_name}</h3>
          <Row k="Location" v={`${sel.item.city}, ${sel.item.state}`} />
          <Row k="On hand" v={`${nf.format(sel.item.on_hand_units)} units`} />
          <Row k="Active routes via site" v={sel.item.routed_shipments} />
          <Row k="Tomorrow" v={sel.item.forecast_high_f != null ? `${sel.item.forecast_high_f}° / ${sel.item.forecast_low_f}°F` : "—"} />
          {sel.item.weather_alert && <Row k="Alert" v={sel.item.weather_alert} tone="amber" />}
          <Row k="Products" v={sel.item.products.join(", ")} />
          {sel.item.low_stock_products.length > 0 && <Row k="Low stock (≤4)" v={sel.item.low_stock_products.join(", ")} tone="coral" />}
        </>
      )}
      {sel.kind === "facility" && (
        <>
          <div className="lbl">{sel.item.facility_type.toUpperCase()} · {sel.item.facility_id}</div>
          <h3>{sel.item.facility_name}</h3>
          <Row k="Location" v={`${sel.item.city}, ${sel.item.state}`} />
          {sel.item.beds > 0 && <Row k="Beds" v={nf.format(sel.item.beds)} />}
          <Row k="Operating rooms" v={sel.item.operating_rooms} />
          <Row k="Served by" v={sel.item.serving_site_id} />
          <Row k="Inbound shipments" v={sel.item.inbound} />
          <Row k="Delayed" v={sel.item.delayed} tone={sel.item.delayed ? "amber" : undefined} />
          <Row k="Temp excursions" v={sel.item.excursions} tone={sel.item.excursions ? "coral" : undefined} />
          <Row k="Surgeries at risk" v={sel.item.procedures_at_risk} tone={sel.item.procedures_at_risk ? "coral" : undefined} />
          <Row k="Tomorrow" v={sel.item.forecast_high_f != null ? `${sel.item.forecast_high_f}° / ${sel.item.forecast_low_f}°F` : "—"} />
          {sel.item.weather_alert && <Row k="Alert" v={sel.item.weather_alert} tone="amber" />}
        </>
      )}
      {sel.kind === "route" && (
        <>
          <div className="lbl">SHIPMENT · {sel.item.priority}</div>
          <h3>
            {sel.item.shipment_id} · {sel.item.product_name}
          </h3>
          <Row k="Route" v={`${sel.item.origin} → ${facilityById[sel.item.destination_facility_id]?.facility_name ?? sel.item.destination}`} />
          <Row k="Carrier" v={sel.item.carrier} />
          <Row k="Status" v={sel.item.status} tone={sel.item.status === "Delayed" ? "amber" : undefined} />
          {sel.item.delay_reason && <Row k="Delay" v={`${sel.item.delay_reason} (+${sel.item.delay_hours}h)`} tone="amber" />}
          <Row k="ETA" v={sel.item.eta_date === sel.item.original_eta_date ? sel.item.eta_date : `${sel.item.eta_date} (was ${sel.item.original_eta_date})`} />
          <Row k="Surgery" v={sel.item.procedure_date} tone={sel.item.misses_procedure ? "coral" : undefined} />
          <Row
            k="Sensor"
            v={`${sel.item.last_recorded_temp_f}°F (max ${sel.item.temperature_max_f}°F)`}
            tone={sel.item.excursion ? "coral" : undefined}
          />
          <Row k="Distance" v={`${nf.format(sel.item.route_miles)} mi`} />
        </>
      )}
    </div>
  );
}
