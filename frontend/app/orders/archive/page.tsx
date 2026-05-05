import { OrdersTable } from "@/components/orders/OrdersTable";
import { backendRequest } from "@/lib/api/server";
import type { OrderListItem } from "@/lib/api/types";

export default async function ArchiveOrdersPage() {
  const orders = await backendRequest<OrderListItem[]>("/orders/archive");

  return (
    <div>
      <div className="page-head">
        <h1>Ordini Spediti</h1>
      </div>
      {orders.length === 0 ? (
        <div className="panel">
          <p className="muted">Nessun ordine spedito.</p>
        </div>
      ) : (
        <OrdersTable orders={orders} />
      )}
    </div>
  );
}
