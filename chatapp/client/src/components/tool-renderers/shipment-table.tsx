import { cn } from '@/lib/utils';

interface Shipment {
  shipment_id: string;
  product_name: string;
  destination: string;
  origin: string;
  carrier: string;
  status: string;
  eta_date: string;
  temperature_max_f: number;
  temperature_min_f: number;
}

const statusStyles: Record<string, { bg: string; text: string }> = {
  'In-Transit': { bg: 'bg-blue-500/15', text: 'text-blue-400' },
  Delayed: { bg: 'bg-red-500/15', text: 'text-red-400' },
  Delivered: { bg: 'bg-green-500/15', text: 'text-green-400' },
  'Label-Create': { bg: 'bg-zinc-500/15', text: 'text-zinc-400' },
};

function StatusBadge({ status }: { status: string }) {
  const style = statusStyles[status] ?? statusStyles['Label-Create'];
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold',
        style.bg,
        style.text,
      )}
    >
      {status}
    </span>
  );
}

export function ShipmentTable({ data }: { data: Shipment[] }) {
  if (!Array.isArray(data) || data.length === 0) return null;

  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-3 py-2 text-left font-medium">Shipment</th>
            <th className="px-3 py-2 text-left font-medium">Product</th>
            <th className="px-3 py-2 text-left font-medium">Route</th>
            <th className="px-3 py-2 text-left font-medium">Carrier</th>
            <th className="px-3 py-2 text-left font-medium">Status</th>
            <th className="px-3 py-2 text-left font-medium">ETA</th>
            <th className="px-3 py-2 text-left font-medium">Temp Range</th>
          </tr>
        </thead>
        <tbody>
          {data.map((s) => (
            <tr key={s.shipment_id} className="border-b last:border-0">
              <td className="px-3 py-2 font-mono">{s.shipment_id}</td>
              <td className="px-3 py-2">{s.product_name}</td>
              <td className="px-3 py-2 text-muted-foreground">
                {s.origin} → {s.destination}
              </td>
              <td className="px-3 py-2">{s.carrier}</td>
              <td className="px-3 py-2">
                <StatusBadge status={s.status} />
              </td>
              <td className="px-3 py-2">{s.eta_date}</td>
              <td className="px-3 py-2 font-mono">
                {s.temperature_min_f != null && s.temperature_max_f != null
                  ? `${s.temperature_min_f}°F – ${s.temperature_max_f}°F`
                  : s.temperature_max_f != null
                    ? `≤${s.temperature_max_f}°F`
                    : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
