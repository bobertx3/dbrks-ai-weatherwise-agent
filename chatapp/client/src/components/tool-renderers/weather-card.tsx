interface WeatherData {
  city?: string;
  temperature?: number | string;
  temperature_f?: number | string;
  wind_speed?: number | string;
  conditions?: string;
  weather_code?: number;
  [key: string]: unknown;
}

function weatherEmoji(conditions?: string, code?: number): string {
  if (code !== undefined) {
    if (code === 0) return '\u2600\uFE0F'; // sunny
    if (code <= 3) return '\u26C5'; // partly cloudy
    if (code <= 48) return '\u2601\uFE0F'; // cloudy/fog
    if (code <= 67) return '\uD83C\uDF27\uFE0F'; // rain
    if (code <= 77) return '\u2744\uFE0F'; // snow
    if (code <= 82) return '\uD83C\uDF27\uFE0F'; // rain showers
    return '\u26C8\uFE0F'; // thunderstorm
  }
  const c = (conditions ?? '').toLowerCase();
  if (c.includes('sun') || c.includes('clear')) return '\u2600\uFE0F';
  if (c.includes('cloud')) return '\u2601\uFE0F';
  if (c.includes('rain')) return '\uD83C\uDF27\uFE0F';
  if (c.includes('snow')) return '\u2744\uFE0F';
  return '\uD83C\uDF24\uFE0F';
}

export function WeatherCard({ data }: { data: WeatherData }) {
  const temp = data.temperature_f ?? data.temperature ?? '—';
  const emoji = weatherEmoji(data.conditions, data.weather_code);

  return (
    <div className="rounded-lg border p-4 max-w-sm">
      <div className="flex items-center gap-3">
        <span className="text-3xl">{emoji}</span>
        <div>
          <div className="text-lg font-bold">
            {temp}°F
          </div>
          {data.city && (
            <div className="text-sm text-muted-foreground">{data.city}</div>
          )}
        </div>
      </div>
      <div className="mt-2 flex gap-4 text-xs text-muted-foreground">
        {data.conditions && <span>{data.conditions}</span>}
        {data.wind_speed && <span>Wind: {data.wind_speed} mph</span>}
      </div>
    </div>
  );
}
