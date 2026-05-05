import { backendRequest } from "@/lib/api/server";
import type { SupplierRead } from "@/lib/api/types";
import { SuppliersListClient } from "@/components/suppliers/SuppliersListClient";

export default async function SuppliersPage() {
  const suppliers = await backendRequest<SupplierRead[]>("/suppliers");
  return <SuppliersListClient initialSuppliers={suppliers} />;
}
