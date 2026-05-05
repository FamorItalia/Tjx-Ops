"use client";

import Link from "next/link";
import { Fragment, useEffect, useMemo, useState } from "react";

import type { ActiveOrderDashboardRow, OrderDetail } from "@/lib/api/types";
import { formatDate } from "@/lib/utils/format";
import { StatusBadge } from "@/components/ui/StatusBadge";

type ProductPreviewRow = {
  key: string;
  vendor_style: string;
  description: string;
  total_pieces: number;
  by_dc: Record<string, { quantity: number; cartons: number | null }>;
};

type ExpandedPreview = {
  dcCodes: string[];
  lines: ProductPreviewRow[];
};

async function fetchOrderDetail(orderId: number): Promise<OrderDetail> {
  const res = await fetch(`/api/backend/orders/${orderId}`, { cache: "no-store" });
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  if (!res.ok) throw new Error(data.detail || `${res.status} ${res.statusText}`);
  return data as OrderDetail;
}

function computeCartons(qty: number, denominator: number | null): number | null {
  if (!denominator || denominator <= 0) return null;
  return Math.ceil(qty / denominator);
}

function buildExpandedPreview(detail: OrderDetail): ExpandedPreview {
  const dcSet = new Set<string>();
  const lines: ProductPreviewRow[] = [];

  for (const line of detail.lines) {
    const byDc: Record<string, { quantity: number; cartons: number | null }> = {};
    const denom = line.nest_code ? line.store_ready_pack_size : line.vend_pack;

    for (const [dc, qty] of Object.entries(line.operational_units_per_dc || {})) {
      const quantity = Number(qty || 0);
      if (quantity <= 0) continue;
      dcSet.add(dc);
      byDc[dc] = {
        quantity,
        cartons: computeCartons(quantity, denom),
      };
    }

    const hasDcSplit = Object.keys(byDc).length > 0;
    const fallbackTotalPieces = Number(line.operational_units ?? line.total_units ?? 0);
    lines.push({
      key: `${line.id}`,
      vendor_style: line.vendor_style || "-",
      description: line.description || "-",
      total_pieces: hasDcSplit
        ? Object.values(byDc).reduce((acc, cell) => acc + cell.quantity, 0)
        : fallbackTotalPieces,
      by_dc: byDc,
    });
  }

  return {
    dcCodes: Array.from(dcSet).sort(),
    lines,
  };
}

export function ActiveOrdersGrid({ rows }: { rows: ActiveOrderDashboardRow[] }) {
  const initialRows = Array.isArray(rows) ? rows : [];
  const [tableRows, setTableRows] = useState<ActiveOrderDashboardRow[]>(initialRows);
  const [query, setQuery] = useState("");
  const [openIds, setOpenIds] = useState<Set<number>>(new Set());
  const [previews, setPreviews] = useState<Record<number, ExpandedPreview>>({});
  const [loadingPreviewIds, setLoadingPreviewIds] = useState<Set<number>>(new Set());
  const [previewErrors, setPreviewErrors] = useState<Record<number, string>>({});
  const [archivingIds, setArchivingIds] = useState<Set<number>>(new Set());
  const [deletingIds, setDeletingIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    setTableRows(Array.isArray(rows) ? rows : []);
  }, [rows]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return tableRows;
    return tableRows.filter((row) =>
      [row.po, row.customer, row.supplier].some((v) => String(v ?? "").toLowerCase().includes(q)),
    );
  }, [tableRows, query]);

  async function toggleRow(orderId: number) {
    setOpenIds((prev) => {
      const next = new Set(prev);
      if (next.has(orderId)) {
        next.delete(orderId);
      } else {
        next.add(orderId);
      }
      return next;
    });

    if (previews[orderId] || loadingPreviewIds.has(orderId)) return;

    setLoadingPreviewIds((prev) => new Set(prev).add(orderId));
    try {
      const detail = await fetchOrderDetail(orderId);
      const preview = buildExpandedPreview(detail);
      setPreviews((prev) => ({ ...prev, [orderId]: preview }));
      setPreviewErrors((prev) => {
        const next = { ...prev };
        delete next[orderId];
        return next;
      });
    } catch (e) {
      setPreviewErrors((prev) => ({
        ...prev,
        [orderId]: e instanceof Error ? e.message : "Errore caricamento preview ordine",
      }));
    } finally {
      setLoadingPreviewIds((prev) => {
        const next = new Set(prev);
        next.delete(orderId);
        return next;
      });
    }
  }

  function statusTone(status: ActiveOrderDashboardRow["order_status"]): "ok" | "warn" | "err" {
    if (status === "In ritardo") return "err";
    if (status === "Programmato") return "warn";
    return "ok";
  }

  async function archiveRow(orderId: number) {
    const confirmed = window.confirm("Sei sicuro di voler segnare questo ordine come spedito?");
    if (!confirmed) return;

    setArchivingIds((prev) => new Set(prev).add(orderId));
    try {
      const res = await fetch(`/api/backend/orders/${orderId}/archive`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_archived: true }),
      });
      const text = await res.text();
      const payload = text ? JSON.parse(text) : {};
      if (!res.ok) {
        throw new Error(payload?.detail || "Errore aggiornamento ordine");
      }
      setTableRows((prev) => prev.filter((row) => row.id !== orderId));
      setOpenIds((prev) => {
        const next = new Set(prev);
        next.delete(orderId);
        return next;
      });
      setPreviews((prev) => {
        const next = { ...prev };
        delete next[orderId];
        return next;
      });
      setPreviewErrors((prev) => {
        const next = { ...prev };
        delete next[orderId];
        return next;
      });
    } catch (e) {
      const message = e instanceof Error ? e.message : "Errore aggiornamento ordine";
      setPreviewErrors((prev) => ({ ...prev, [orderId]: message }));
    } finally {
      setArchivingIds((prev) => {
        const next = new Set(prev);
        next.delete(orderId);
        return next;
      });
    }
  }

  async function deleteRow(orderId: number) {
    const confirmed = window.confirm("Sei sicuro di voler eliminare definitivamente questo ordine?");
    if (!confirmed) return;
    setDeletingIds((prev) => new Set(prev).add(orderId));
    try {
      const res = await fetch(`/api/backend/orders/${orderId}`, { method: "DELETE" });
      if (!res.ok) {
        const text = await res.text();
        const payload = text ? JSON.parse(text) : {};
        throw new Error(payload?.detail || "Errore eliminazione ordine");
      }
      setTableRows((prev) => prev.filter((row) => row.id !== orderId));
      setOpenIds((prev) => {
        const next = new Set(prev);
        next.delete(orderId);
        return next;
      });
    } catch (e) {
      const message = e instanceof Error ? e.message : "Errore eliminazione ordine";
      setPreviewErrors((prev) => ({ ...prev, [orderId]: message }));
    } finally {
      setDeletingIds((prev) => {
        const next = new Set(prev);
        next.delete(orderId);
        return next;
      });
    }
  }

  return (
    <div className="panel">
      <div className="page-head">
        <h2>Ordini Attivi</h2>
        <input
          className="input"
          style={{ maxWidth: 320 }}
          placeholder="Filtra per PO, customer, fornitore"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th style={{ width: 48 }}>+</th>
              <th>PO</th>
              <th>Customer</th>
              <th>Fornitore</th>
              <th>Start Ship Date</th>
              <th>Cancel Date</th>
              <th>Stato</th>
              <th>Totale cartoni</th>
              <th>Azioni</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => {
              const isOpen = openIds.has(row.id);
              const isLoading = loadingPreviewIds.has(row.id);
              const preview = previews[row.id];
              const previewError = previewErrors[row.id];

              return (
                <Fragment key={row.id}>
                  <tr>
                    <td>
                      <button className="btn" style={{ padding: "2px 8px" }} onClick={() => void toggleRow(row.id)}>
                        {isOpen ? "-" : "+"}
                      </button>
                    </td>
                    <td>
                      <a href={`/orders/${row.id}`} style={{ fontWeight: 600 }}>
                        {row.po || `#${row.id}`}
                      </a>
                    </td>
                    <td>{row.customer || "-"}</td>
                    <td>{row.supplier || "-"}</td>
                    <td>{formatDate(row.start_ship_date)}</td>
                    <td>{formatDate(row.cancel_ship_date)}</td>
                    <td>
                      <StatusBadge tone={statusTone(row.order_status)} label={row.order_status} />
                    </td>
                    <td>{row.total_cartons ?? "-"}</td>
                    <td>
                      <div style={{ display: "flex", gap: 8 }}>
                        <a href={`/orders/${row.id}`} className="btn">
                          Apri
                        </a>
                        <button
                          className="btn"
                          onClick={() => void archiveRow(row.id)}
                          disabled={archivingIds.has(row.id)}
                          title="Segna ordine come spedito"
                        >
                          {archivingIds.has(row.id) ? "Invio..." : "Segna spedito"}
                        </button>
                        <button
                          className="btn"
                          onClick={() => void deleteRow(row.id)}
                          disabled={deletingIds.has(row.id)}
                          title="Elimina ordine"
                        >
                          {deletingIds.has(row.id) ? "Elimino..." : "Elimina"}
                        </button>
                      </div>
                    </td>
                  </tr>

                  {isOpen ? (
                    <tr className="row-preview">
                      <td />
                      <td colSpan={8}>
                        <div style={{ padding: "8px 0" }}>
                          <div style={{ fontWeight: 600, marginBottom: 6 }}>Preview ordine (prodotti x DC)</div>

                          {isLoading ? <div className="muted">Caricamento preview...</div> : null}
                          {previewError ? <StatusBadge tone="err" label={previewError} /> : null}

                          {!isLoading && !previewError ? (
                            <div className="table-wrap" style={{ borderRadius: 8 }}>
                              <table style={{ minWidth: 720 }}>
                                <thead>
                                  <tr>
                                    <th>Codice</th>
                                    <th>Descrizione</th>
                                    <th>Pz totali</th>
                                    {preview?.dcCodes.map((dc) => (
                                      <th key={`${row.id}-h-${dc}`}>{dc}</th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {preview && preview.lines.length > 0 ? (
                                    preview.lines.map((line) => (
                                      <tr key={`${row.id}-${line.key}`}>
                                        <td style={{ fontWeight: 600 }}>{line.vendor_style}</td>
                                        <td>{line.description}</td>
                                        <td>{line.total_pieces}</td>
                                        {preview.dcCodes.map((dc) => {
                                          const cell = line.by_dc[dc];
                                          return (
                                            <td key={`${row.id}-${line.key}-${dc}`}>
                                              {cell ? cell.quantity : <span className="muted">-</span>}
                                            </td>
                                          );
                                        })}
                                      </tr>
                                    ))
                                  ) : (
                                    <tr>
                                      <td colSpan={(preview?.dcCodes.length || 0) + 3} className="muted">
                                        Nessuna riga prodotto disponibile.
                                      </td>
                                    </tr>
                                  )}
                                </tbody>
                              </table>
                            </div>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}

            {filtered.length === 0 ? (
              <tr>
                <td colSpan={9} className="muted">
                  Nessun ordine attivo.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
