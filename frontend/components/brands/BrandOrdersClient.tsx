"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import type { BrandOrderRow } from "@/lib/api/types";
import { formatDate } from "@/lib/utils/format";
import { StatusBadge } from "@/components/ui/StatusBadge";

function formatCurrency(value: number) {
  return new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR" }).format(value || 0);
}

export function BrandOrdersClient({
  brandLabel,
  initialRows,
}: {
  brandLabel: string;
  initialRows: BrandOrderRow[];
}) {
  const [rows] = useState<BrandOrderRow[]>(initialRows);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "archived">("all");
  const [monthFilter, setMonthFilter] = useState<"all" | string>("all");
  const [yearFilter, setYearFilter] = useState<"all" | string>("all");

  const yearOptions = useMemo(() => {
    const years = new Set<string>();
    rows.forEach((row) => {
      if (!row.cancel_ship_date) return;
      years.add(new Date(row.cancel_ship_date).getFullYear().toString());
    });
    return Array.from(years).sort((a, b) => Number(b) - Number(a));
  }, [rows]);

  const monthOptions = useMemo(() => {
    const months = new Set<string>();
    rows.forEach((row) => {
      if (!row.cancel_ship_date) return;
      const d = new Date(row.cancel_ship_date);
      if (yearFilter !== "all" && d.getFullYear().toString() !== yearFilter) return;
      months.add((d.getMonth() + 1).toString());
    });
    return Array.from(months).sort((a, b) => Number(a) - Number(b));
  }, [rows, yearFilter]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((row) => {
      if (statusFilter === "active" && row.is_archived) return false;
      if (statusFilter === "archived" && !row.is_archived) return false;
      if (row.cancel_ship_date) {
        const d = new Date(row.cancel_ship_date);
        if (yearFilter !== "all" && d.getFullYear().toString() !== yearFilter) return false;
        if (monthFilter !== "all" && (d.getMonth() + 1).toString() !== monthFilter) return false;
      } else if (yearFilter !== "all" || monthFilter !== "all") {
        return false;
      }
      if (!q) return true;
      const hay = `${row.po || ""} ${row.supplier || ""}`.toLowerCase();
      return hay.includes(q);
    });
  }, [rows, query, statusFilter, monthFilter, yearFilter]);

  return (
    <div className="panel">
      <div className="page-head">
        <h2 style={{ margin: 0 }}>Ordini {brandLabel}</h2>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <input
            className="input"
            style={{ maxWidth: 320 }}
            placeholder="Filtra per PO / fornitore"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <select className="input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as "all" | "active" | "archived")}>
            <option value="all">Tutti</option>
            <option value="active">Da spedire</option>
            <option value="archived">Spediti</option>
          </select>
          <select className="input" value={yearFilter} onChange={(e) => setYearFilter(e.target.value)}>
            <option value="all">Tutti gli anni</option>
            {yearOptions.map((year) => (
              <option key={year} value={year}>
                {year}
              </option>
            ))}
          </select>
          <select className="input" value={monthFilter} onChange={(e) => setMonthFilter(e.target.value)}>
            <option value="all">Tutti i mesi</option>
            {monthOptions.map((month) => (
              <option key={month} value={month}>
                {month.padStart(2, "0")}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>PO</th>
              <th>Fornitore</th>
              <th>Start Ship</th>
              <th>Cancel</th>
              <th>Stato</th>
              <th>Pz</th>
              <th>Totale € ordine</th>
              <th>Azioni</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => (
              <tr key={row.order_id}>
                <td style={{ fontWeight: 600 }}>{row.po || `#${row.order_id}`}</td>
                <td>{row.supplier || "-"}</td>
                <td>{formatDate(row.start_ship_date)}</td>
                <td>{formatDate(row.cancel_ship_date)}</td>
                <td>
                  <StatusBadge
                    tone={row.order_status === "In ritardo" ? "err" : row.order_status === "Programmato" ? "warn" : "ok"}
                    label={row.order_status}
                  />
                </td>
                <td>{row.total_pieces}</td>
                <td>{formatCurrency(row.order_total_sale_eur)}</td>
                <td>
                  <Link className="btn" href={`/orders/${row.order_id}`}>
                    Apri
                  </Link>
                </td>
              </tr>
            ))}
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="muted">
                  Nessun ordine per questa insegna.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
