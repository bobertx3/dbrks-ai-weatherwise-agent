import type { ReactNode } from 'react';
import { ShipmentTable } from './shipment-table';
import { SupplierCards } from './supplier-card';
import { InventoryTable } from './inventory-table';
import { WeatherCard } from './weather-card';

/**
 * Attempts to parse tool output and return a rich renderer.
 * Returns null if the tool isn't recognized or data can't be parsed,
 * so the caller can fall back to raw display.
 */
export function renderToolOutput(
  toolName: string,
  output: unknown,
): ReactNode | null {
  try {
    const data =
      typeof output === 'string' ? JSON.parse(output) : output;

    if (data == null) return null;

    switch (toolName) {
      case 'get_shipments':
      case 'bldemos__agentbricks_weatherwise__get_shipments': {
        const items = Array.isArray(data) ? data : [data];
        if (items.length > 0 && items[0].shipment_id) {
          return <ShipmentTable data={items} />;
        }
        return null;
      }

      case 'get_supplier_details':
      case 'bldemos__agentbricks_weatherwise__get_supplier_details': {
        const items = Array.isArray(data) ? data : [data];
        if (items.length > 0 && items[0].supplier_id) {
          return <SupplierCards data={items} />;
        }
        return null;
      }

      case 'get_backup_inventory':
      case 'bldemos__agentbricks_weatherwise__get_backup_inventory': {
        const items = Array.isArray(data) ? data : [data];
        if (items.length > 0 && items[0].site_id) {
          return <InventoryTable data={items} />;
        }
        return null;
      }

      case 'check_weather': {
        if (
          typeof data === 'object' &&
          (data.temperature !== undefined ||
            data.temperature_f !== undefined)
        ) {
          return <WeatherCard data={data} />;
        }
        return null;
      }

      default:
        return null;
    }
  } catch {
    return null;
  }
}
