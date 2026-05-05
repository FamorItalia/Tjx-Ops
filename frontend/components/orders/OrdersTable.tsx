"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import type { OrderListItem } from "@/lib/api/types";
import { formatDate } from "@/lib/utils/format";
import { StatusBadge } from "@/components/ui/StatusBadge";

export function OrdersTable({ orders }: { orders: OrderListItem[] }) {
  const [tableRows, setTableRows] = useState<OrderListItem[]>(orders);
  const [query, setQuery] = useState("");
  const [restoringIds, setRestoringIds] = useState<Set<number>>(new Set());
  const [deletingIds, setDeletingIds] = useState<Set<number>>(new Set());

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return tableRows;
    return tableRows.filter((o) =>
      [o.po_raw, o.po_normalized, o.brand, o.source_file].some((v) => (v || "").toLowerCase().includes(q)),
    );
  }, [tableRows, query]);

  async function restoreOrder(orderId: number) {
    setRestoringIds((prev) => new Set(prev).add(orderId));
    try {
      const res = await fetch(`/api/backend/orders/${orderId}/archive`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_archived: false }),
      });
      const text = await res.text();
      const payload = text ? JSON.parse(text) : {};
      if (!res.ok) {
        throw new Error(payload?.detail || "Errore ripristino ordine");
      }
      setTableRows((prev) => prev.filter((row) => row.id !== orderId));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Errore ripristino ordine";
      window.alert(message);
    } finally {
      setRestoringIds((prev) => {
        const next = new Set(prev);
        next.delete(orderId);
        return next;
      });
    }
  }

  async function deleteOrder(orderId: number) {
    const confirmed = window.confirm("Sei sicuro di voler eliminare definitivamente questo ordine?");
    if (!confirmed) return;
    setDeletingIds((prev) => new Set(prev).add(orderId));
    try {
      const res = await fetch(`/api/backend/orders/${orderId}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const text = await res.text();
        const payload = text ? JSON.parse(text) : {};
        throw new Error(payload?.detail || "Errore eliminazione ordine");
      }
      setTableRows((prev) => prev.filter((row) => row.id !== orderId));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Errore eliminazione ordine";
      window.alert(message);
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
        <h2>Ordini</h2>
        <input
          className="input"
          style={{ maxWidth: 320 }}
          placeholder="Filtra per PO, customer, file"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>PO</th>
              <th>Customer</th>
              <th>Date</th>
              <th>Famiglia</th>
              <th>Stato</th>
              <th>Azioni</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((order) => (
              <tr key={order.id}>
                <td>{order.id}</td>
                <td>{order.po_normalized || order.po_raw || "-"}</td>
                <td>{order.brand || "-"}</td>
                <td>
                  {formatDate(order.start_ship_date)} - {formatDate(order.cancel_ship_date)}
                </td>
                <td>{order.document_family}</td>
                <td>
                  {order.is_archived ? (
                    <StatusBadge label="Spedito" tone="warn" />
                  ) : (
                    <StatusBadge label="Da spedire" tone="ok" />
                  )}
                </td>
                <td>
                  <div style={{ display: "flex", gap: 8 }}>
                    <Link className="btn" href={`/orders/${order.id}`}>
                      Apri
                    </Link>
                    {order.is_archived ? (
                      <button
                        className="btn"
                        onClick={() => void restoreOrder(order.id)}
                        disabled={restoringIds.has(order.id)}
                        title="Riporta ordine tra i da spedire"
                      >
                        {restoringIds.has(order.id) ? "Ripristino..." : "Riporta da spedire"}
                      </button>
                    ) : null}
                    <button
                      className="btn"
                      onClick={() => void deleteOrder(order.id)}
                      disabled={deletingIds.has(order.id)}
                      title="Elimina ordine"
                    >
                      {deletingIds.has(order.id) ? "Elimino..." : "Elimina"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={7} className="muted">
                  Nessun ordine trovato.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
