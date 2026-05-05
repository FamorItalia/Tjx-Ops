import { notFound } from "next/navigation";

import { backendRequest } from "@/lib/api/server";
import type { ProductDocumentRead, ProductInventoryHistoryRead, ProductRead } from "@/lib/api/types";
import { ProductDetailClient } from "@/components/products/ProductDetailClient";

type PageProps = {
  params: { id: string };
};

export default async function ProductDetailPage({ params }: PageProps) {
  const productId = Number(params.id);
  if (!Number.isFinite(productId) || productId <= 0) notFound();

  try {
    const [product, documents, inventoryHistory] = await Promise.all([
      backendRequest<ProductRead>(`/products/${productId}`),
      backendRequest<ProductDocumentRead[]>(`/products/${productId}/documents`),
      backendRequest<ProductInventoryHistoryRead>(`/products/${productId}/inventory-history`),
    ]);
    return (
      <ProductDetailClient
        initialProduct={product}
        initialDocuments={documents}
        initialInventoryHistory={inventoryHistory}
      />
    );
  } catch {
    notFound();
  }
}
