import { notFound } from "next/navigation";

import { backendRequest } from "@/lib/api/server";
import type { ProductDocumentRead, ProductInventoryHistoryRead, ProductPriceHistoryRead, ProductRead } from "@/lib/api/types";
import { ProductDetailClient } from "@/components/products/ProductDetailClient";

type PageProps = {
  params: { id: string };
};

export default async function ProductDetailPage({ params }: PageProps) {
  const productId = Number(params.id);
  if (!Number.isFinite(productId) || productId <= 0) notFound();

  try {
    const toDate = new Date();
    const fromDate = new Date();
    fromDate.setDate(toDate.getDate() - 180);
    const q = `from_date=${encodeURIComponent(fromDate.toISOString())}&to_date=${encodeURIComponent(toDate.toISOString())}`;

    const [product, documents, inventoryHistory] = await Promise.all([
      backendRequest<ProductRead>(`/products/${productId}`),
      backendRequest<ProductDocumentRead[]>(`/products/${productId}/documents`),
      backendRequest<ProductInventoryHistoryRead>(`/products/${productId}/inventory-history`),
    ]);

    let priceHistory: ProductPriceHistoryRead = {
      product_id: productId,
      from_date: fromDate.toISOString(),
      to_date: toDate.toISOString(),
      entries: [],
      chart_points: [],
    };
    try {
      priceHistory = await backendRequest<ProductPriceHistoryRead>(`/products/${productId}/price-history?${q}`);
    } catch {
      // Keep product page available even if price-history endpoint is not ready.
    }

    return (
      <ProductDetailClient
        initialProduct={product}
        initialDocuments={documents}
        initialInventoryHistory={inventoryHistory}
        initialPriceHistory={priceHistory}
      />
    );
  } catch {
    notFound();
  }
}
