export type Health = {
  app: string;
  catalog: string;
  warehouse_configured: boolean;
  genie_configured: boolean;
  agent_configured: boolean;
  temp_ceiling_f: number;
  user: string | null;
};

export type Overview = {
  kpi: {
    total_shipments: number;
    in_transit: number;
    delayed: number;
    temp_excursions: number;
    on_hand: number;
    expiring_90d: number;
  };
  status_mix: { status: string; shipments: number }[];
  inventory_by_site: { site_name: string; city: string; state: string; on_hand_units: number }[];
  temp_ceiling_f: number;
};

export type AtRiskShipment = {
  shipment_id: string;
  product_name: string;
  origin: string;
  destination: string;
  carrier: string;
  status: string;
  eta_date: string;
  last_recorded_temp_f: number | null;
  temperature_max_f: number | null;
};

export type GenieResult = {
  conversation_id: string;
  message_id: string;
  text: string;
  sql: string | null;
  columns: string[];
  rows: unknown[][];
  suggested_questions: string[];
};

/** One agent tool call, as returned by /api/agent/chat (args/output truncated server-side). */
export type ToolStep = { name: string; args: string; output: string | null };

export type ChatMessage = { role: "user" | "assistant"; content: string; steps?: ToolStep[] };

async function errorText(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return body.detail ?? `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}

export async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(await errorText(res));
  return res.json() as Promise<T>;
}

export async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await errorText(res));
  return res.json() as Promise<T>;
}

// ── Network Map (/api/map) ───────────────────────────────────
type Forecast = { forecast_high_f: number | null; forecast_low_f: number | null; weather_alert: string | null };

export type MapSite = Forecast & {
  site_id: string;
  site_name: string;
  site_type: "Supply Center" | "Distribution Center";
  city: string;
  state: string;
  latitude: number;
  longitude: number;
  on_hand_units: number;
  products: string[];
  low_stock_products: string[];
  routed_shipments: number;
};

export type MapFacility = Forecast & {
  facility_id: string;
  facility_name: string;
  facility_type: "Hospital" | "Clinic";
  city: string;
  state: string;
  metro: string;
  latitude: number;
  longitude: number;
  serving_site_id: string;
  beds: number;
  operating_rooms: number;
  inbound: number;
  delayed: number;
  excursions: number;
  procedures_at_risk: number;
};

export type MapRoute = {
  shipment_id: string;
  product_name: string;
  origin: string;
  destination: string;
  carrier: string;
  status: string;
  priority: string;
  eta_date: string;
  original_eta_date: string;
  procedure_date: string;
  delay_hours: number;
  delay_reason: string | null;
  last_recorded_temp_f: number;
  temperature_max_f: number;
  destination_facility_id: string;
  route_miles: number;
  origin_latitude: number;
  origin_longitude: number;
  destination_latitude: number;
  destination_longitude: number;
  excursion: boolean;
  misses_procedure: boolean;
};

export type NetworkMap = {
  sites: MapSite[];
  facilities: MapFacility[];
  routes: MapRoute[];
  summary: {
    supply_centers: number;
    distribution_centers: number;
    hospitals: number;
    clinics: number;
    active_shipments: number;
    delayed: number;
    excursions: number;
    procedures_at_risk: number;
  };
};
