import { Router, type Request, type Response } from 'express';
import { getDatabricksToken } from '@chat-template/auth';
import { getHostUrl } from '@chat-template/utils';
import { authMiddleware, requireAuth } from '../middleware/auth';

export const dashboardRouter = Router();
dashboardRouter.use(authMiddleware);

const CATALOG = process.env.DATABRICKS_CATALOG || 'bldemos';
const SCHEMA = process.env.DATABRICKS_SCHEMA || 'agentbricks_weatherwise';

async function executeSql(sql: string): Promise<any[]> {
  const token = await getDatabricksToken();
  const host = getHostUrl();
  const warehouseId = process.env.DATABRICKS_SQL_WAREHOUSE_ID;

  if (!warehouseId) {
    throw new Error('DATABRICKS_SQL_WAREHOUSE_ID is not configured');
  }

  const response = await fetch(`${host}/api/2.0/sql/statements`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      warehouse_id: warehouseId,
      statement: sql,
      wait_timeout: '30s',
      disposition: 'INLINE',
      format: 'JSON_ARRAY',
    }),
  });

  const result = await response.json();

  if (result.status?.state === 'FAILED') {
    throw new Error(result.status.error?.message ?? 'SQL execution failed');
  }

  // Convert JSON_ARRAY format to objects
  const columns = result.manifest?.schema?.columns ?? [];
  const dataArray = result.result?.data_array ?? [];

  return dataArray.map((row: any[]) => {
    const obj: Record<string, any> = {};
    columns.forEach((col: { name: string }, i: number) => {
      obj[col.name] = row[i];
    });
    return obj;
  });
}

dashboardRouter.get(
  '/summary',
  requireAuth,
  async (_req: Request, res: Response) => {
    try {
      const [shipments, suppliers, inventory] = await Promise.all([
        executeSql(
          `SELECT * FROM ${CATALOG}.${SCHEMA}.shipments ORDER BY eta_date`,
        ),
        executeSql(
          `SELECT * FROM ${CATALOG}.${SCHEMA}.suppliers ORDER BY tier, supplier_name`,
        ),
        executeSql(
          `SELECT * FROM ${CATALOG}.${SCHEMA}.inventory ORDER BY site_name`,
        ),
      ]);

      // Compute status counts
      const shipmentStatusCounts: Record<string, number> = {};
      for (const s of shipments) {
        shipmentStatusCounts[s.status] =
          (shipmentStatusCounts[s.status] ?? 0) + 1;
      }

      // Compute tier counts
      const supplierTierCounts: Record<string, number> = {};
      for (const s of suppliers) {
        supplierTierCounts[s.tier] = (supplierTierCounts[s.tier] ?? 0) + 1;
      }

      res.json({
        shipments,
        shipmentStatusCounts,
        suppliers,
        supplierTierCounts,
        inventory,
      });
    } catch (error) {
      console.error('[dashboard] Error:', error);
      res.status(500).json({
        error: 'Failed to load dashboard data',
        message: error instanceof Error ? error.message : String(error),
      });
    }
  },
);
