import Link from "next/link";

import { ActiveOrdersGrid } from "@/components/dashboard/ActiveOrdersGrid";
import { backendRequest } from "@/lib/api/server";
import type { ActiveOrderDashboardRow, InventoryAlertDashboard } from "@/lib/api/types";
import { formatDateTime } from "@/lib/utils/format";

export default async function DashboardPage() {
  const [rowsRaw, alertsRaw] = await Promise.all([
    backendRequest<ActiveOrderDashboardRow[]>("/orders/active-dashboard"),
    backendRequest<InventoryAlertDashboard[]>("/orders/inventory-alerts?limit=10"),
  ]);
  const rows = Array.isArray(rowsRaw) ? rowsRaw : [];
  const alerts = Array.isArray(alertsRaw) ? alertsRaw : [];
  const lateCount = rows.filter((r) => r.order_status === "In ritardo").length;

  return (
    <div>
      <div className="panel" style={{ marginBottom: 12 }}>
        <Link className="btn primary big" href="/import/new">
          Nuovo Import
        </Link>
      </div>

      <div className="cards" style={{ marginBottom: 12 }}>
        <div className="card">
          <div className="k">PO attivi</div>
          <div className="v">{rows.length}</div>
        </div>
        <div className="card">
          <div className="k">Ordini in ritardo</div>
          <div className="v">{lateCount}</div>
        </div>
        <div className="card">
          <div className="k">Alert giacenze</div>
          <div className="v">{alerts.length}</div>
        </div>
      </div>

      {alerts.length > 0 ? (
        <div className="panel" style={{ marginBottom: 12 }}>
          <h3 style={{ marginTop: 0 }}>Notifiche giacenze</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Quando</th>
                  <th>Prodotto</th>
                  <th>Fornitore</th>
                  <th>Tipo</th>
                  <th>Soglia</th>
                  <th>Attuale</th>
                  <th>Sotto soglia</th>
                  <th>Azioni</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((a) => (
                  <tr key={a.id}>
                    <td>{formatDateTime(a.created_at)}</td>
                    <td>{a.product_style || `Prodotto #${a.product_id}`}</td>
                    <td>{a.supplier_name || "-"}</td>
                    <td>{a.stock_type === "product" ? "Prodotto" : "Packaging"}</td>
                    <td>{a.threshold_value}</td>
                    <td>{a.current_value}</td>
                    <td style={{ color: "#b42318", fontWeight: 700 }}>{a.below_by}</td>
                    <td>
                      <div style={{ display: "flex", gap: 8 }}>
                        <Link className="btn" href={`/products/${a.product_id}`}>Apri prodotto</Link>
                        {a.customer_order_id ? (
                          <Link className="btn" href={`/orders/${a.customer_order_id}`}>Apri ordine</Link>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      <ActiveOrdersGrid rows={rows} />
    </div>
  );
}
