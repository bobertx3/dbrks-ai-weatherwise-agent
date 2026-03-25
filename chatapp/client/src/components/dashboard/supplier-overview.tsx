import { cn } from '@/lib/utils';

interface Supplier {
  supplier_id: string;
  supplier_name: string;
  contact_name: string;
  contact_email: string;
  phone: string;
  tier: string;
}

const tierStyles: Record<string, string> = {
  'Tier-1': 'border-green-500/30 bg-green-500/10',
  'Tier-2': 'border-yellow-500/30 bg-yellow-500/10',
  'Tier-3': 'border-red-500/30 bg-red-500/10',
};

const tierBadge: Record<string, string> = {
  'Tier-1': 'bg-green-500/15 text-green-400',
  'Tier-2': 'bg-yellow-500/15 text-yellow-400',
  'Tier-3': 'bg-red-500/15 text-red-400',
};

export function SupplierOverview({
  suppliers,
}: {
  suppliers: Supplier[];
}) {
  return (
    <div className="rounded-lg border">
      <div className="border-b px-4 py-3">
        <h3 className="text-sm font-semibold">Suppliers</h3>
      </div>
      <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
        {suppliers.map((s) => (
          <div
            key={s.supplier_id}
            className={cn(
              'rounded-lg border p-3',
              tierStyles[s.tier] ?? tierStyles['Tier-3'],
            )}
          >
            <div className="flex items-center gap-2 mb-2">
              <span className="text-sm font-semibold">{s.supplier_name}</span>
              <span
                className={cn(
                  'rounded-full px-2 py-0.5 text-[10px] font-semibold',
                  tierBadge[s.tier] ?? tierBadge['Tier-3'],
                )}
              >
                {s.tier}
              </span>
            </div>
            <div className="text-xs text-muted-foreground space-y-0.5">
              <div>{s.contact_name}</div>
              <div>{s.contact_email}</div>
              <div>{s.phone}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
