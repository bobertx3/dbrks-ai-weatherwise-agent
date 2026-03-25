interface InventoryItem {
  site_id: string;
  site_name: string;
  city: string;
  state: string;
  product_id: string;
  product_name: string;
  supplier_id: string;
  on_hand_qty: number;
  lot_expiry: string;
}

export function InventoryTable({ data }: { data: InventoryItem[] }) {
  if (!Array.isArray(data) || data.length === 0) return null;

  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-3 py-2 text-left font-medium">Site</th>
            <th className="px-3 py-2 text-left font-medium">Location</th>
            <th className="px-3 py-2 text-left font-medium">Product</th>
            <th className="px-3 py-2 text-right font-medium">On Hand</th>
            <th className="px-3 py-2 text-left font-medium">Lot Expiry</th>
          </tr>
        </thead>
        <tbody>
          {data.map((item, i) => {
            const isLowStock = item.on_hand_qty < 15;
            return (
              <tr key={`${item.site_id}-${item.product_id}-${i}`} className="border-b last:border-0">
                <td className="px-3 py-2 font-medium">{item.site_name}</td>
                <td className="px-3 py-2 text-muted-foreground">
                  {item.city}, {item.state}
                </td>
                <td className="px-3 py-2">{item.product_name}</td>
                <td className={`px-3 py-2 text-right font-mono ${isLowStock ? 'text-red-400 font-semibold' : ''}`}>
                  {item.on_hand_qty}
                </td>
                <td className="px-3 py-2">{item.lot_expiry}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
