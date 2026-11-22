import { useEffect, useMemo, useState, type ReactNode } from "react";
import { CircleMarker, MapContainer, Marker, Polyline, TileLayer, Tooltip, ZoomControl, useMap } from "react-leaflet";
import L from "leaflet";
import type { LatLngBoundsExpression, LatLngExpression } from "leaflet";
import "leaflet/dist/leaflet.css";
import { AlertTriangle, Bot, X } from "lucide-react";
import { callClass, tempCall } from "../tempCall";
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

const VIEWS: Record<string, { label: string; short: string; bounds: LatLngBoundsExpression }> = {
  us: { label: "United States", short: "US", bounds: [[24.5, -125], [49.5, -66.5]] },
  ne: { label: "Northeast", short: "Northeast", bounds: [[38.6, -80.5], [43.2, -70.5]] },
  nyc: { label: "NYC metro", short: "NYC", bounds: [[40.5, -74.3], [41.1, -73.5]] },
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
const PRI: Record<string, number> = { STAT: 0, Urgent: 1, Routine: 2 };
// Short list on small screens so the floating card never needs its own scroll.
const HOT_LIMIT = typeof window !== "undefined" && window.innerHeight < 900 ? 3 : 4;

function facilityColor(f: MapFacility) {
  if (f.excursions > 0) return C.coral;
  if (f.delayed > 0) return C.amber;
  return C.ok;
}

function routeColor(r: MapRoute) {
  if (r.excursion) return C.coral;
  if (r.status === "Delayed") return C.amber;
  return C.teal;
}

function isRisk(r: MapRoute) {
  return r.status === "Delayed" || r.excursion;
}

/** Fit the view, leaving room on the right for the floating panel so nothing hides under it. */
function FitView({ view, rightPad }: { view: string; rightPad: number }) {
  const map = useMap();
  useEffect(() => {
    map.flyToBounds(VIEWS[view].bounds, { duration: 0.8, paddingTopLeft: [20, 56], paddingBottomRight: [rightPad, 20] });
  }, [view, rightPad, map]);
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

export default function NetworkMap({
  warehouseOk,
  data: dataProp,
  statusFilter = null,
  focus = null,
  embedded = false,
  onAskRoute,
}: {
  warehouseOk: boolean | null;
  /** Provide data from a parent (Command Center) to skip this component's own fetch. */
  data?: MapData | null;
  /** Show only routes with this status (Command Center status chips). */
  statusFilter?: string | null;
  /** Shipment picked in the table: select it and fly to its destination. */
  focus?: MapRoute | null;
  /** Embedded in the Command Center: fixed height, no duplicate KPI tiles. */
  embedded?: boolean;
  /** "Run agent" on a selected shipment (opens the assistant drawer with a prompt). */
  onAskRoute?: (r: MapRoute) => void;
}) {
  const [ownData, setData] = useState<MapData | null>(null);
  const data = dataProp !== undefined ? dataProp : ownData;
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState("us");
  const [layers, setLayers] = useState<Layers>({ supply: true, dc: true, hospital: true, clinic: true, routes: "risk" });
  const [selected, setSelected] = useState<Selected>(null);
  const [flyTarget, setFlyTarget] = useState<LatLngExpression | null>(null);

  useEffect(() => {
    if (warehouseOk === null || dataProp !== undefined) return;
    getJSON<MapData>("/api/map")
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, [warehouseOk, dataProp]);

  useEffect(() => {
    if (!focus) return;
    setSelected({ kind: "route", item: focus });
    setFlyTarget([focus.destination_latitude, focus.destination_longitude]);
  }, [focus]);

  const routes = useMemo(() => {
    if (!data) return [];
    if (statusFilter) return data.routes.filter((r) => r.status === statusFilter);
    if (layers.routes === "off") return [];
    return layers.routes === "all" ? data.routes : data.routes.filter(isRisk);
  }, [data, layers.routes, statusFilter]);
  const selectedRouteId = selected?.kind === "route" ? selected.item.shipment_id : null;
  // Focus mode: when something is selected, dim everything else and put a beacon on it.
  const focused = selected !== null;
  const focusFacilityId =
    selected?.kind === "route" ? selected.item.destination_facility_id : selected?.kind === "facility" ? selected.item.facility_id : null;
  const focusSiteId = selected?.kind === "site" ? selected.item.site_id : null;
  const beacon = useMemo((): { at: [number, number]; label: string; tone: "warm" | "cold" | "info" } | null => {
    if (!selected) return null;
    if (selected.kind === "route") {
      const r = selected.item;
      const call = tempCall(r);
      return { at: [r.destination_latitude, r.destination_longitude], label: `${r.shipment_id}${call ? ` · ${call}` : ""}`,
               tone: call ? callClass(call) : "info" };
    }
    if (selected.kind === "facility") return { at: [selected.item.latitude, selected.item.longitude], label: selected.item.facility_name, tone: "info" };
    return { at: [selected.item.latitude, selected.item.longitude], label: selected.item.site_name, tone: "info" };
  }, [selected]);
  const svgRenderer = useMemo(() => L.svg({ padding: 0.5 }), []); // focus route is SVG so it can animate

  const facilityById = useMemo(
    () => Object.fromEntries((data?.facilities ?? []).map((f) => [f.facility_id, f])),
    [data],
  );

  const hotList = useMemo(
    () =>
      (data?.routes ?? [])
        // Sensor already outside the product's range (TOO WARM / TOO COLD), highest priority first.
        .filter((r) => r.excursion && r.status !== "Delivered")
        .sort((a, b) => (PRI[a.priority] ?? 3) - (PRI[b.priority] ?? 3) || a.shipment_id.localeCompare(b.shipment_id)),
    [data],
  );

  const toggle = (k: Exclude<keyof Layers, "routes">) => setLayers((l) => ({ ...l, [k]: !l[k] }));

  const [panelOpen, setPanelOpen] = useState(true);

  return (
    <div className={`netmap ${embedded ? "embedded" : ""}`}>
      <div className="netmap-canvas">
        <MapContainer zoomSnap={0.25} zoomDelta={0.5} bounds={VIEWS.us.bounds} boundsOptions={{ paddingTopLeft: [20, 56], paddingBottomRight: [340, 20] }} zoomControl={false} preferCanvas={true} style={{ height: "100%", width: "100%" }}>
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
          <ZoomControl position="bottomright" />
          <AutoResize />
          <FitView view={view} rightPad={panelOpen || selected ? 340 : 20} />
          <FlyTo target={flyTarget} />

          {routes.map((r) => (
            <Polyline
              key={r.shipment_id}
              positions={[[r.origin_latitude, r.origin_longitude], [r.destination_latitude, r.destination_longitude]]}
              pathOptions={{
                color: routeColor(r),
                weight: r.shipment_id === selectedRouteId ? 4.5 : isRisk(r) ? 2.2 : 1.2,
                opacity: focused ? (r.shipment_id === selectedRouteId ? 0 : 0.1) : isRisk(r) ? 0.8 : 0.35,
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
                pathOptions={{
                  color: facilityColor(f), fillColor: facilityColor(f), weight: f.excursions ? 3 : 1,
                  fillOpacity: focused && f.facility_id !== focusFacilityId ? 0.15 : 0.85,
                  opacity: focused && f.facility_id !== focusFacilityId ? 0.2 : 1,
                }}
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
                  pathOptions={{
                    color, fillColor: "#0a1017", weight: 3,
                    fillOpacity: focused && st.site_id !== focusSiteId ? 0.3 : 0.9,
                    opacity: focused && st.site_id !== focusSiteId ? 0.2 : 1,
                  }}
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
          {selected?.kind === "route" && (
            <>
              <Polyline
                key={`focus-${selected.item.shipment_id}`}
                positions={[[selected.item.origin_latitude, selected.item.origin_longitude], [selected.item.destination_latitude, selected.item.destination_longitude]]}
                pathOptions={{ color: routeColor(selected.item), weight: 5, opacity: 1, className: "route-focus", renderer: svgRenderer }}
                interactive={false}
              />
              <CircleMarker
                center={[selected.item.origin_latitude, selected.item.origin_longitude]}
                radius={5}
                pathOptions={{ color: "#dbe4ec", fillColor: "#0a1017", fillOpacity: 1, weight: 2 }}
                interactive={false}
              >
                <Tooltip permanent direction="left" offset={[-6, 0]} className="focus-label origin">{selected.item.origin}</Tooltip>
              </CircleMarker>
            </>
          )}
          {beacon && (
            <Marker
              key={`beacon-${beacon.label}`}
              position={beacon.at}
              interactive={false}
              zIndexOffset={1000}
              icon={L.divIcon({ className: "", iconSize: [0, 0], html: `<div class="beacon ${beacon.tone}"><span></span><span></span><i></i></div>` })}
            >
              <Tooltip permanent direction="right" offset={[14, 0]} className={`focus-label ${beacon.tone}`}>{beacon.label}</Tooltip>
            </Marker>
          )}
        </MapContainer>

        {/* Overlays sit beside the Leaflet container (not inside it), so clicks and scrolls on them never pan the map. */}
        <div className="map-ov map-toolbar">
          <div className="ov-group">
            <span className="ov-lbl">View</span>
            <div className="seg">
              {Object.entries(VIEWS).map(([k, v]) => (
                <button key={k} className={view === k ? "on" : ""} onClick={() => setView(k)}>
                  {v.short}
                </button>
              ))}
            </div>
          </div>
          <div className="ov-group">
            <span className="ov-lbl">Routes</span>
            <div className="seg">
              {(["off", "risk", "all"] as const).map((k) => (
                <button key={k} className={!statusFilter && layers.routes === k ? "on" : ""} onClick={() => setLayers((l) => ({ ...l, routes: k }))} disabled={!!statusFilter}>
                  {k === "off" ? "Hide" : k === "risk" ? "At risk" : "All"}
                </button>
              ))}
            </div>
          </div>
          <div className="ov-group layers">
            <LayerToggle on={layers.supply} onClick={() => toggle("supply")} color={C.teal} square label="Supply" />
            <LayerToggle on={layers.dc} onClick={() => toggle("dc")} color={C.blue} square label="DCs" />
            <LayerToggle on={layers.hospital} onClick={() => toggle("hospital")} color={C.soft} label="Hospitals" />
            <LayerToggle on={layers.clinic} onClick={() => toggle("clinic")} color={C.soft} small label="Clinics" />
          </div>
          {statusFilter && <div className="ov-note">Showing {statusFilter} routes</div>}
        </div>

        <div className="map-ov map-legend">
          <span><i style={{ background: C.coral }} /> Out of temperature range</span>
          <span><i style={{ background: C.amber }} /> Delayed</span>
          <span><i style={{ background: C.ok }} /> On track</span>
        </div>

        {error && <div className="map-ov map-error">Map data unavailable: {error}</div>}

        <div className={`map-ov map-panel ${panelOpen || selected ? "" : "collapsed"}`}>
          {selected ? (
            <Details sel={selected} facilityById={facilityById} onClose={() => setSelected(null)} onAskRoute={onAskRoute} />
          ) : panelOpen ? (
            <div className="card tight">
              <button className="close" onClick={() => setPanelOpen(false)} aria-label="Hide out-of-range list">
                <X size={14} />
              </button>
              <div className="lbl coral">
                <AlertTriangle size={11} style={{ verticalAlign: -1 }} /> OUT OF RANGE NOW
              </div>
              {!data ? (
                <div className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>Loading…</div>
              ) : hotList.length === 0 ? (
                <div className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>No shipments out of range.</div>
              ) : (
                <ul className="hot-list">
                  {hotList.slice(0, HOT_LIMIT).map((r) => (
                    <li
                      key={r.shipment_id}
                      onClick={() => {
                        setSelected({ kind: "route", item: r });
                        setFlyTarget([r.destination_latitude, r.destination_longitude]);
                      }}
                    >
                      <div className="hl-top">
                        <span className="mono">{r.shipment_id}</span>
                        <span className={`pill ${r.priority === "STAT" ? "stat" : ""}`} title={r.priority === "STAT" ? "STAT: highest shipping priority" : undefined}>{r.priority}</span>
                      </div>
                      <div className="hl-main">{r.product_name} → {facilityById[r.destination_facility_id]?.facility_name ?? r.destination}</div>
                      <div className="hl-sub">
                        {tempCall(r) && <span className={`risk-badge ${callClass(tempCall(r)!)}`}>{tempCall(r)}</span>}{` ${r.last_recorded_temp_f}°F · range ${r.temperature_min_f}–${r.temperature_max_f}°F`}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              {hotList.length > HOT_LIMIT && <div className="muted" style={{ fontSize: 11.5, marginTop: 6 }}>+{hotList.length - HOT_LIMIT} more in the table below</div>}
            </div>
          ) : (
            <button className="ov-reopen" onClick={() => setPanelOpen(true)}>
              <AlertTriangle size={12} /> Out of range ({hotList.length})
            </button>
          )}
        </div>
      </div>
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

function Details({ sel, facilityById, onClose, onAskRoute }: { sel: NonNullable<Selected>; facilityById: Record<string, MapFacility>; onClose: () => void; onAskRoute?: (r: MapRoute) => void }) {
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
          <Row
            k="Sensor"
            v={`${sel.item.last_recorded_temp_f}°F (range ${sel.item.temperature_min_f}–${sel.item.temperature_max_f}°F)`}
            tone={sel.item.excursion ? "coral" : undefined}
          />
          <Row k="Distance" v={`${nf.format(sel.item.route_miles)} mi`} />
          {onAskRoute && (
            <button className="btn coral-solid run-agent" onClick={() => onAskRoute(sel.item)}>
              <Bot size={14} /> Run agent on {sel.item.shipment_id}
            </button>
          )}
        </>
      )}
    </div>
  );
}
