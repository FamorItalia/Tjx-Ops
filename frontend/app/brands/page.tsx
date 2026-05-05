import Link from "next/link";
import Image from "next/image";

import { backendRequest } from "@/lib/api/server";
import type { BrandSummary } from "@/lib/api/types";

function formatCurrency(value: number) {
  return new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR" }).format(value || 0);
}

type BrandLogoConfig = {
  src: string;
  alt: string;
};

const BRAND_LOGOS: Record<string, BrandLogoConfig> = {
  SIERRA: { src: "/brands/sierra.jpg", alt: "Sierra" },
  TJMAXX: { src: "/brands/tj-maxx.png", alt: "TJ Maxx" },
  MARSHALLS: { src: "/brands/marshalls.png", alt: "Marshalls" },
  HOMEGOODS: { src: "/brands/homegoods.png", alt: "HomeGoods" },
  HOMESENSE: { src: "/brands/homesense.png", alt: "Home Sense" },
  CANMARSH: { src: "/brands/canadian-marshalls.png", alt: "Canadian Marshalls" },
  WINNERS: { src: "/brands/winners.png", alt: "Winners" },
};

export default async function BrandsPage() {
  const brands = await backendRequest<BrandSummary[]>("/brands");
  const periodStart = brands[0]?.period_start || null;
  const periodEnd = brands[0]?.period_end || null;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 style={{ marginBottom: 4 }}>Insegne</h1>
          <div className="muted">
            Totali ultimi 12 mesi
            {periodStart && periodEnd ? ` (${periodStart} - ${periodEnd})` : ""}
          </div>
        </div>
      </div>

      <div className="brand-logo-grid" style={{ marginBottom: 12 }}>
        {brands.map((brand) => (
          <Link key={brand.key} className="brand-logo-link" href={`/brands/${brand.key}`} aria-label={`Apri pagina ${brand.label}`}>
            <div className="brand-logo-card">
              <Image
                src={BRAND_LOGOS[brand.key]?.src ?? "/brands/marshalls.png"}
                alt={BRAND_LOGOS[brand.key]?.alt ?? brand.label}
                width={250}
                height={78}
                className="brand-logo-image"
              />
            </div>
          </Link>
        ))}
      </div>

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>Recap ordini lavorati ultimi 12 mesi</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Insegna</th>
                <th>Totali nell'anno</th>
                <th>Spediti</th>
                <th>Da spedire</th>
                <th>Fatturato annuo (vendita)</th>
              </tr>
            </thead>
            <tbody>
              {brands.map((brand) => (
                <tr key={`sum-${brand.key}`}>
                  <td style={{ fontWeight: 600 }}>
                    <Link href={`/brands/${brand.key}`}>{brand.label}</Link>
                  </td>
                  <td>{brand.total_orders_year}</td>
                  <td>{brand.archived_orders_year}</td>
                  <td>{brand.to_ship_orders_year}</td>
                  <td>{formatCurrency(brand.annual_revenue_eur)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
