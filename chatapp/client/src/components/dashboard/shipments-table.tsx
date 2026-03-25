import { cn } from '@/lib/utils';

interface Shipment {
  shipment_id: string;
  product_id: string;
  sku: string;
  product_name: string;
  supplier_id: string;
  origin: string;
  destination: string;
  ship_date: string;
  eta_date: string;
  carrier: string;
  status: string;
  temperature_max_f: number;
  temperature_min_f: number;
}

const statusStyles: Record<string, string> = {
  'In-Transit': 'bg-blue-500/15 text-blue-400',
  Delayed: 'bg-red-500/15 text-red-400',
  Delivered: 'bg-green-500/15 text-green-400',
  'Label-Create': 'bg-zinc-500/15 text-zinc-400',
};

export function ShipmentsTable({ shipments }: { shipments: Shipment[] }) {
  return (
    <div className="rounded-lg border">
      <div className="border-b px-4 py-3">
        <h3 className="text-sm font-semibold">Shipments</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b bg-muted/30">
              <th className="px-4 py-2 text-left font-medium">ID</th>
              <th className="px-4 py-2 text-left font-medium">Product</th>
              <th className="px-4 py-2 text-left font-medium">Origin</th>
              <th className="px-4 py-2 text-left font-medium">Destination</th>
              <th className="px-4 py-2 text-left font-medium">Carrier</th>
              <th className="px-4 py-2 text-left font-medium">Status</th>
              <th className="px-4 py-2 text-left font-medium">Ship Date</th>
              <th className="px-4 py-2 text-left font-medium">ETA</th>
              <th className="px-4 py-2 text-left font-medium">Temp Range (°F)</th>
            </tr>
          </thead>
          <tbody>
            {shipments.map((s) => (
              <tr
                key={s.shipment_id}
                className={cn(
                  'border-b last:border-0 transition-colors hover:bg-muted/20',
                  s.status === 'Delayed' && 'bg-red-500/5',
                )}
              >
                <td className="px-4 py-2 font-mono">{s.shipment_id}</td>
                <td className="px-4 py-2">{s.product_name}</td>
                <td className="px-4 py-2 text-muted-foreground">{s.origin}</td>
                <td className="px-4 py-2 text-muted-foreground">
                  {s.destination}
                </td>
                <td className="px-4 py-2">{s.carrier}</td>
                <td className="px-4 py-2">
                  <span
                    className={cn(
                      'inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold',
                      statusStyles[s.status] ?? statusStyles['Label-Create'],
                    )}
                  >
                    {s.status}
                  </span>
                </td>
                <td className="px-4 py-2">{s.ship_date}</td>
                <td className="px-4 py-2">{s.eta_date}</td>
                <td className="px-4 py-2 font-mono">
                  {s.temperature_min_f} – {s.temperature_max_f}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
