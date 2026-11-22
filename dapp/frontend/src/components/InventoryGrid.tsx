import { useMemo, useState } from "react";
import type { Overview } from "../api";

type Cell = NonNullable<Overview["inventory_matrix"]>[number];
type Scope = "Distribution Center" | "Supply Center" | "all";

const LOW = 4; // ≤ this many units = low stock
const nf = new Intl.NumberFormat("en-US");

/** Short column headers; the full product name is on hover. */
function shortName(name: string) {
  const n = name.toLowerCase();
  const map: [string, string][] = [
    ["aortic valve", "Aortic valve"], ["stent", "Coated stent"], ["balloon", "DCB catheter"],
    ["fibrin", "Fibrin sealant"], ["bone allograft", "Bone allograft"], ["thrombin", "Thrombin"],
    ["cornea", "Corneal graft"], ["skin", "Skin graft"], ["insulin", "Insulin pump"],
  ];
  return map.find(([k]) => n.includes(k))?.[1] ?? name.replace(/\s*\(.*\)$/, "");
}

export default function InventoryGrid({ cells }: { cells: Cell[] }) {
  const [scope, setScope] = useState<Scope>("Distribution Center");

  const { products, sites, grid, max, total } = useMemo(() => {
    const scoped = cells.filter((c) => scope === "all" || c.site_type === scope);
    // Group by product name: some products come from two suppliers (two IDs, same product).
    const products = [...new Set(cells.map((c) => c.product_name))].sort((a, b) => shortName(a).localeCompare(shortName(b))).map((n) => [n, n] as [string, string]);
    const bySite = new Map<string, { name: string; state: string; type: string | null; total: number }>();
    const grid = new Map<string, number>();
    for (const c of scoped) {
      const s = bySite.get(c.site_id) ?? { name: c.site_name, state: c.state, type: c.site_type, total: 0 };
      s.total += Number(c.on_hand) || 0;
      bySite.set(c.site_id, s);
      grid.set(`${c.site_id}|${c.product_name}`, (grid.get(`${c.site_id}|${c.product_name}`) ?? 0) + (Number(c.on_hand) || 0));
    }
    const sites = [...bySite.entries()].sort((a, b) => b[1].total - a[1].total);
    const max = Math.max(1, ...grid.values());
    const total = sites.reduce((n, [, s]) => n + s.total, 0);
    return { products, sites, grid, max, total };
  }, [cells, scope]);

  return (
    <div className="card inv-card">
      <div className="inv-head">
        <div>
          <div className="lbl">INVENTORY</div>
          <h3>On-hand units by product and site · {nf.format(total)} units</h3>
        </div>
        <div className="seg inv-seg">
          {(["Distribution Center", "Supply Center", "all"] as Scope[]).map((k) => (
            <button key={k} className={scope === k ? "on" : ""} onClick={() => setScope(k)}>
              {k === "all" ? "All sites" : k === "Supply Center" ? "Supply centers" : "Distribution centers"}
            </button>
          ))}
        </div>
      </div>
      <div className="inv-wrap">
        <table className="inv-grid">
          <thead>
            <tr>
              <th className="site">Site</th>
              {products.map(([id, name]) => (
                <th key={id} title={name}>{shortName(name)}</th>
              ))}
              <th className="tot">Total</th>
            </tr>
          </thead>
          <tbody>
            {sites.map(([id, s]) => (
              <tr key={id}>
                <td className="site" title={`${s.name}, ${s.state}${s.type ? ` · ${s.type}` : ""}`}>
                  {s.name} <span className="muted">{s.state}</span>
                </td>
                {products.map(([pid, pname]) => {
                  const v = grid.get(`${id}|${pid}`);
                  if (v == null) return <td key={pid} className="cell none" title={`${pname}: not stocked`}>—</td>;
                  const low = v <= LOW;
                  const a = 0.1 + 0.55 * (v / max);
                  return (
                    <td
                      key={pid}
                      className={`cell ${low ? "low" : ""}`}
                      style={low ? undefined : { background: `rgba(79, 209, 197, ${a.toFixed(2)})` }}
                      title={`${pname} at ${s.name}: ${v} units${low ? " (low stock)" : ""}`}
                    >
                      {v}
                    </td>
                  );
                })}
                <td className="tot">{nf.format(s.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="inv-legend">
        <span><i className="sw hi" /> more units</span>
        <span><i className="sw lo" /> fewer</span>
        <span><i className="sw low" /> low stock (≤{LOW})</span>
        <span className="muted">— not stocked</span>
      </div>
    </div>
  );
}
