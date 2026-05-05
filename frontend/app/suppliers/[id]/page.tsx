import { notFound } from "next/navigation";

import { backendRequest } from "@/lib/api/server";
import type { SupplierDocumentRead, SupplierProductRead, SupplierRead } from "@/lib/api/types";
import { SupplierDetailClient } from "@/components/suppliers/SupplierDetailClient";

type PageProps = {
  params: { id: string };
};

export default async function SupplierDetailPage({ params }: PageProps) {
  const supplierId = Number(params.id);
  if (!Number.isFinite(supplierId) || supplierId <= 0) {
    notFound();
  }

  try {
    const [supplier, products, documents] = await Promise.all([
      backendRequest<SupplierRead>(`/suppliers/${supplierId}`),
      backendRequest<SupplierProductRead[]>(`/suppliers/${supplierId}/products`),
      backendRequest<SupplierDocumentRead[]>(`/suppliers/${supplierId}/documents`),
    ]);

    return (
      <SupplierDetailClient
        initialSupplier={supplier}
        initialProducts={products}
        initialDocuments={documents}
      />
    );
  } catch {
    notFound();
  }
}
