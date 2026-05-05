import Link from "next/link";
import { notFound } from "next/navigation";

import { backendRequest } from "@/lib/api/server";
import type { BrandOrderRow, BrandSummary } from "@/lib/api/types";
import { BrandOrdersClient } from "@/components/brands/BrandOrdersClient";

type PageProps = {
  params: { brand: string };
};

export default async function BrandDetailPage({ params }: PageProps) {
  const brandKey = (params.brand || "").toUpperCase();
  const brands = await backendRequest<BrandSummary[]>("/brands");
  const current = brands.find((b) => b.key === brandKey);
  if (!current) {
    notFound();
  }
  const rows = await backendRequest<BrandOrderRow[]>(`/brands/${brandKey}/orders`);

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 style={{ marginBottom: 4 }}>{current.label}</h1>
          <div className="muted">
            <Link href="/brands">Insegne</Link> / {current.label}
          </div>
          <div className="muted">
            Ordini ultimi 12 mesi ({current.period_start} - {current.period_end})
          </div>
        </div>
      </div>

      <BrandOrdersClient brandLabel={current.label} initialRows={rows} />
    </div>
  );
}
