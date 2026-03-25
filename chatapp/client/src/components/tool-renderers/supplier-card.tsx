import { cn } from '@/lib/utils';

interface Supplier {
  supplier_id: string;
  supplier_name: string;
  contact_name: string;
  contact_email: string;
  phone: string;
  tier: string;
}

const tierColors: Record<string, { bg: string; text: string }> = {
  'Tier-1': { bg: 'bg-green-500/15', text: 'text-green-400' },
  'Tier-2': { bg: 'bg-yellow-500/15', text: 'text-yellow-400' },
  'Tier-3': { bg: 'bg-red-500/15', text: 'text-red-400' },
};

function SupplierItem({ supplier }: { supplier: Supplier }) {
  const tierStyle = tierColors[supplier.tier] ?? tierColors['Tier-3'];
  return (
    <div className="rounded-lg border p-3">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-sm font-semibold">{supplier.supplier_name}</span>
        <span
          className={cn(
            'rounded-full px-2 py-0.5 text-[10px] font-semibold',
            tierStyle.bg,
            tierStyle.text,
          )}
        >
          {supplier.tier}
        </span>
      </div>
      <div className="text-xs text-muted-foreground space-y-0.5">
        <div>{supplier.contact_name}</div>
        <div>{supplier.contact_email}</div>
        <div>{supplier.phone}</div>
      </div>
    </div>
  );
}

export function SupplierCards({ data }: { data: Supplier | Supplier[] }) {
  const suppliers = Array.isArray(data) ? data : [data];
  if (suppliers.length === 0) return null;

  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {suppliers.map((s) => (
        <SupplierItem key={s.supplier_id} supplier={s} />
      ))}
    </div>
  );
}
