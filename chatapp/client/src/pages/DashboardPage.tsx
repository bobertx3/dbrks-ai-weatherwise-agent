import { useEffect, useState } from 'react';
import { StatusCards } from '@/components/dashboard/status-cards';
import { ShipmentsTable } from '@/components/dashboard/shipments-table';
import { InventoryOverview } from '@/components/dashboard/inventory-overview';
import { SupplierOverview } from '@/components/dashboard/supplier-overview';

interface DashboardData {
  shipments: any[];
  shipmentStatusCounts: Record<string, number>;
  suppliers: any[];
  supplierTierCounts: Record<string, number>;
  inventory: any[];
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/dashboard/summary', { credentials: 'include' })
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.message ?? `HTTP ${res.status}`);
        }
        return res.json();
      })
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex items-center gap-2 text-muted-foreground">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
          <span className="text-sm">Loading dashboard...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-6 max-w-md text-center">
          <p className="text-sm font-medium text-red-400">
            Failed to load dashboard
          </p>
          <p className="text-xs text-muted-foreground mt-1">{error}</p>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-7xl px-4 py-6 space-y-6">
        <div>
          <h1 className="text-xl font-bold">Supply Chain Dashboard</h1>
          <p className="text-xs text-muted-foreground mt-1">
            Jackson & Jackson MedTech — Real-time shipment and inventory overview
          </p>
        </div>

        <StatusCards counts={data.shipmentStatusCounts} />
        <ShipmentsTable shipments={data.shipments} />

        <div className="grid gap-6 lg:grid-cols-2">
          <InventoryOverview inventory={data.inventory} />
          <SupplierOverview suppliers={data.suppliers} />
        </div>
      </div>
    </div>
  );
}
