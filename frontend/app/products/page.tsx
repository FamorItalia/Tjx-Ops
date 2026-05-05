import { backendRequest } from "@/lib/api/server";
import type { ProductRead } from "@/lib/api/types";
import { ProductsListClient } from "@/components/products/ProductsListClient";

export default async function ProductsPage() {
  const products = await backendRequest<ProductRead[]>("/products");
  return <ProductsListClient initialProducts={products} />;
}
