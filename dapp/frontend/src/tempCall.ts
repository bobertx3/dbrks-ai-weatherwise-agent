import type { MapRoute } from "./api";

export type TempCall = "TOO WARM" | "TOO COLD" | "THAWING";

/** The one-word temperature call for a shipment's latest sensor reading (null = in range). */
export function tempCall(r: Pick<MapRoute, "last_recorded_temp_f" | "temperature_max_f" | "temperature_min_f">): TempCall | null {
  const t = r.last_recorded_temp_f;
  if (t == null) return null;
  if (t > r.temperature_max_f) return r.temperature_max_f < 32 ? "THAWING" : "TOO WARM";
  if (r.temperature_min_f != null && t < r.temperature_min_f) return "TOO COLD";
  return null;
}

export const callClass = (c: TempCall) => (c === "TOO COLD" ? "cold" : "warm");
