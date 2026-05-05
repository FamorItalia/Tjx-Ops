import { notFound } from "next/navigation";

import { OrderDetailClient } from "@/components/orders/OrderDetailClient";
import { backendRequest } from "@/lib/api/server";
import type { OrderDetail } from "@/lib/api/types";

export default async function OrderDetailPage({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  if (!Number.isFinite(id)) {
    notFound();
  }

  try {
    const order = await backendRequest<OrderDetail>(`/orders/${id}`);
    const normalized: OrderDetail = {
      ...order,
      lines: Array.isArray(order?.lines) ? order.lines : [],
    };
    return <OrderDetailClient initial={normalized} />;
  } catch {
    notFound();
  }
}
