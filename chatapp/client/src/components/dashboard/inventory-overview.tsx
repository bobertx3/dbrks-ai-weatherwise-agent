interface InventoryItem {
  site_id: string;
  site_name: string;
  city: string;
  state: string;
  product_id: string;
  sku: string;
  product_name: string;
  supplier_id: string;
  on_hand_qty: number;
  lot_expiry: string;
}

export function InventoryOverview({
  inventory,
}: {
  inventory: InventoryItem[];
}) {
  return (
    <div className="rounded-lg border">
      <div className="border-b px-4 py-3">
        <h3 className="text-sm font-semibold">Inventory by Site</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b bg-muted/30">
              <th className="px-4 py-2 text-left font-medium">Site</th>
              <th className="px-4 py-2 text-left font-medium">Location</th>
              <th className="px-4 py-2 text-left font-medium">Product</th>
              <th className="px-4 py-2 text-left font-medium">SKU</th>
              <th className="px-4 py-2 text-right font-medium">On Hand</th>
              <th className="px-4 py-2 text-left font-medium">Lot Expiry</th>
            </tr>
          </thead>
          <tbody>
            {inventory.map((item, i) => {
              const isLowStock = Number(item.on_hand_qty) < 15;
              return (
                <tr
                  key={`${item.site_id}-${i}`}
                  className="border-b last:border-0 transition-colors hover:bg-muted/20"
                >
                  <td className="px-4 py-2 font-medium">{item.site_name}</td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {item.city}, {item.state}
                  </td>
                  <td className="px-4 py-2">{item.product_name}</td>
                  <td className="px-4 py-2 font-mono">{item.sku}</td>
                  <td
                    className={`px-4 py-2 text-right font-mono ${isLowStock ? 'text-red-400 font-semibold' : ''}`}
                  >
                    {item.on_hand_qty}
                  </td>
                  <td className="px-4 py-2">{item.lot_expiry}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
