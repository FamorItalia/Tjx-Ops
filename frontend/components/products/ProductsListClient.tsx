"use client";

import Link from "next/link";
import { useMemo, useRef, useState } from "react";

import type { ProductImportResponse, ProductRead } from "@/lib/api/types";

type Props = {
  initialProducts: ProductRead[];
};

function formatMoney(value: number | null) {
  if (value == null) return "-";
  return new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR" }).format(value);
}

export function ProductsListClient({ initialProducts }: Props) {
  const [products, setProducts] = useState<ProductRead[]>(initialProducts);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [newProduct, setNewProduct] = useState({
    supplier_name: "",
    tjx_style: "",
    description: "",
    pcs_per_crt: "",
    purchase_cost_eur: "",
    sale_price_eur: "",
  });

  async function refreshProducts() {
    const res = await fetch("/api/backend/products", { cache: "no-store" });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.detail || "Errore aggiornamento prodotti");
    setProducts(data as ProductRead[]);
  }

  async function onImportExcel(file: File) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch("/api/backend/products/import", {
        method: "POST",
        body: formData,
      });
      const data = (await res.json()) as ProductImportResponse | { detail?: string };
      if (!res.ok) {
        throw new Error((data as { detail?: string }).detail || "Errore import prodotti");
      }
      const payload = data as ProductImportResponse;
      await refreshProducts();
      const warn = payload.warnings?.length ? ` - warning: ${payload.warnings.length}` : "";
      setMessage(
        `Import completato: inseriti ${payload.inserted_count}, aggiornati ${payload.updated_count}, saltati ${payload.skipped_count}${warn}.`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore import prodotti");
    } finally {
      setBusy(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function onCreateProduct() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const payload = {
        supplier_name: newProduct.supplier_name,
        tjx_style: newProduct.tjx_style,
        description: newProduct.description || null,
        pcs_per_crt: newProduct.pcs_per_crt ? Number(newProduct.pcs_per_crt) : null,
        purchase_cost_eur: newProduct.purchase_cost_eur ? Number(newProduct.purchase_cost_eur.replace(",", ".")) : null,
        sale_price_eur: newProduct.sale_price_eur ? Number(newProduct.sale_price_eur.replace(",", ".")) : null,
      };
      const res = await fetch("/api/backend/products", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Errore creazione prodotto");
      await refreshProducts();
      setAdding(false);
      setNewProduct({
        supplier_name: "",
        tjx_style: "",
        description: "",
        pcs_per_crt: "",
        purchase_cost_eur: "",
        sale_price_eur: "",
      });
      setMessage("Prodotto creato correttamente.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore creazione prodotto");
    } finally {
      setBusy(false);
    }
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return products;
    return products.filter((p) =>
      [p.tjx_style, p.description, p.supplier_name]
        .map((v) => (v || "").toLowerCase())
        .some((v) => v.includes(q)),
    );
  }, [products, query]);

  return (
    <div>
      <div className="page-head">
        <h1>Prodotti</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <input
            className="input"
            style={{ maxWidth: 360 }}
            placeholder="Cerca per style, descrizione, fornitore"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <a className="btn" href="/api/backend/products/export/excel">
            Export Excel
          </a>
          <button className="btn" disabled={busy} onClick={() => fileInputRef.current?.click()}>
            {busy ? "Import in corso..." : "Import Excel"}
          </button>
          <button className="btn primary" disabled={busy} onClick={() => setAdding((v) => !v)}>
            {adding ? "Chiudi" : "Aggiungi Prodotto"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx,.xlsm"
            style={{ display: "none" }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void onImportExcel(file);
            }}
          />
        </div>
      </div>
      {adding ? (
        <div className="panel" style={{ marginBottom: 10 }}>
          <div className="grid-2">
            <div>
              <label className="muted">Fornitore *</label>
              <input
                className="input"
                value={newProduct.supplier_name}
                onChange={(e) => setNewProduct((p) => ({ ...p, supplier_name: e.target.value }))}
              />
            </div>
            <div>
              <label className="muted">TJX Style *</label>
              <input
                className="input"
                value={newProduct.tjx_style}
                onChange={(e) => setNewProduct((p) => ({ ...p, tjx_style: e.target.value.toUpperCase() }))}
              />
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <label className="muted">Descrizione</label>
              <input
                className="input"
                value={newProduct.description}
                onChange={(e) => setNewProduct((p) => ({ ...p, description: e.target.value }))}
              />
            </div>
            <div>
              <label className="muted">PCS per CRT</label>
              <input
                className="input"
                type="number"
                min={0}
                value={newProduct.pcs_per_crt}
                onChange={(e) => setNewProduct((p) => ({ ...p, pcs_per_crt: e.target.value }))}
              />
            </div>
            <div>
              <label className="muted">Costo acquisto</label>
              <input
                className="input"
                value={newProduct.purchase_cost_eur}
                onChange={(e) => setNewProduct((p) => ({ ...p, purchase_cost_eur: e.target.value }))}
              />
            </div>
            <div>
              <label className="muted">Prezzo vendita</label>
              <input
                className="input"
                value={newProduct.sale_price_eur}
                onChange={(e) => setNewProduct((p) => ({ ...p, sale_price_eur: e.target.value }))}
              />
            </div>
          </div>
          <div style={{ marginTop: 10 }}>
            <button
              className="btn primary"
              disabled={busy || !newProduct.supplier_name.trim() || !newProduct.tjx_style.trim()}
              onClick={() => void onCreateProduct()}
            >
              Salva prodotto
            </button>
          </div>
        </div>
      ) : null}
      {message ? <div className="panel"><div className="muted">{message}</div></div> : null}
      {error ? <div className="panel"><div style={{ color: "#b42318" }}>{error}</div></div> : null}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>TJX Style</th>
              <th>Descrizione</th>
              <th>Fornitore</th>
              <th>PCS/CRT</th>
              <th>Costo</th>
              <th>Vendita</th>
              <th>Giacenza prodotto</th>
              <th>Giacenza packaging</th>
              <th>Dettaglio</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((p) => (
              <tr key={p.id}>
                <td>{p.id}</td>
                <td style={{ fontWeight: 600 }}>{p.tjx_style || "-"}</td>
                <td>{p.description || "-"}</td>
                <td>{p.supplier_name || "-"}</td>
                <td>{p.pcs_per_crt ?? "-"}</td>
                <td>{formatMoney(p.purchase_cost_eur)}</td>
                <td>{formatMoney(p.sale_price_eur)}</td>
                <td>{p.stock_product_units ?? "-"}</td>
                <td>{p.stock_packaging_units ?? "-"}</td>
                <td>
                  <Link className="btn" href={`/products/${p.id}`}>
                    Apri
                  </Link>
                </td>
              </tr>
            ))}
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={10} className="muted">
                  Nessun prodotto trovato.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
