"use client";

import Link from "next/link";
import { ChangeEvent, FormEvent, useState } from "react";

import type { ProductDocumentRead, ProductInventoryHistoryRead, ProductRead } from "@/lib/api/types";
import { formatDateTime } from "@/lib/utils/format";

type Props = {
  initialProduct: ProductRead;
  initialDocuments: ProductDocumentRead[];
  initialInventoryHistory: ProductInventoryHistoryRead;
};

type ProductFormState = {
  description: string;
  pcs_per_crt: string;
  strat_x_pl: string;
  strat_x_plt: string;
  cartons_per_layer: string;
  cartons_per_pallet: string;
  carton_width_cm: string;
  carton_depth_cm: string;
  carton_height_cm: string;
  vol: string;
  peso_lordo: string;
  peso_netto: string;
  pallet_width_cm: string;
  pallet_depth_cm: string;
  purchase_cost_eur: string;
  sale_price_eur: string;
  inventory_tracking_enabled: boolean;
  stock_product_units: string;
  stock_packaging_units: string;
  product_usage_per_unit: string;
  packaging_usage_per_unit: string;
  product_alert_threshold: string;
  packaging_alert_threshold: string;
};

function toFormState(product: ProductRead): ProductFormState {
  return {
    description: product.description || "",
    pcs_per_crt: product.pcs_per_crt != null ? String(product.pcs_per_crt) : "",
    strat_x_pl: product.strat_x_pl != null ? String(product.strat_x_pl) : "",
    strat_x_plt: product.strat_x_plt != null ? String(product.strat_x_plt) : "",
    cartons_per_layer: product.cartons_per_layer != null ? String(product.cartons_per_layer) : "",
    cartons_per_pallet: product.cartons_per_pallet != null ? String(product.cartons_per_pallet) : "",
    carton_width_cm: product.carton_width_cm != null ? String(product.carton_width_cm) : "",
    carton_depth_cm: product.carton_depth_cm != null ? String(product.carton_depth_cm) : "",
    carton_height_cm: product.carton_height_cm != null ? String(product.carton_height_cm) : "",
    vol: product.vol != null ? String(product.vol) : "",
    peso_lordo: product.peso_lordo != null ? String(product.peso_lordo) : "",
    peso_netto: product.peso_netto != null ? String(product.peso_netto) : "",
    pallet_width_cm: product.pallet_width_cm != null ? String(product.pallet_width_cm) : "",
    pallet_depth_cm: product.pallet_depth_cm != null ? String(product.pallet_depth_cm) : "",
    purchase_cost_eur: product.purchase_cost_eur != null ? String(product.purchase_cost_eur) : "",
    sale_price_eur: product.sale_price_eur != null ? String(product.sale_price_eur) : "",
    inventory_tracking_enabled: Boolean(product.inventory_tracking_enabled),
    stock_product_units: product.stock_product_units != null ? String(product.stock_product_units) : "",
    stock_packaging_units: product.stock_packaging_units != null ? String(product.stock_packaging_units) : "",
    product_usage_per_unit: product.product_usage_per_unit != null ? String(product.product_usage_per_unit) : "",
    packaging_usage_per_unit: product.packaging_usage_per_unit != null ? String(product.packaging_usage_per_unit) : "",
    product_alert_threshold: product.product_alert_threshold != null ? String(product.product_alert_threshold) : "",
    packaging_alert_threshold: product.packaging_alert_threshold != null ? String(product.packaging_alert_threshold) : "",
  };
}

function parseNullableFloat(value: string): number | null {
  const text = value.trim();
  if (!text) return null;
  const normalized = text.replace(",", ".");
  const n = Number(normalized);
  return Number.isFinite(n) ? n : null;
}

function parseNullableInt(value: string): number | null {
  const text = value.trim();
  if (!text) return null;
  const n = Number(text);
  return Number.isFinite(n) ? Math.round(n) : null;
}

function formatMoney(value: number | null) {
  if (value == null) return "-";
  return new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR" }).format(value);
}

export function ProductDetailClient({ initialProduct, initialDocuments, initialInventoryHistory }: Props) {
  const [product, setProduct] = useState(initialProduct);
  const [form, setForm] = useState<ProductFormState>(() => toFormState(initialProduct));
  const [documents, setDocuments] = useState(initialDocuments);
  const [inventoryHistory, setInventoryHistory] = useState(initialInventoryHistory);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [refreshingHistory, setRefreshingHistory] = useState(false);
  const [showMovements, setShowMovements] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function onChange(field: keyof ProductFormState, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function onToggle(field: keyof ProductFormState, value: boolean) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function reloadInventoryHistory() {
    setRefreshingHistory(true);
    try {
      const res = await fetch(`/api/backend/products/${product.id}/inventory-history`);
      const text = await res.text();
      const data = text ? JSON.parse(text) : {};
      if (!res.ok) throw new Error(data?.detail || "Errore caricamento storico giacenze");
      setInventoryHistory(data as ProductInventoryHistoryRead);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore caricamento storico giacenze");
    } finally {
      setRefreshingHistory(false);
    }
  }

  async function onSave(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);

    try {
      const payload = {
        description: form.description || null,
        pcs_per_crt: parseNullableInt(form.pcs_per_crt),
        strat_x_pl: parseNullableInt(form.strat_x_pl),
        strat_x_plt: parseNullableInt(form.strat_x_plt),
        cartons_per_layer: parseNullableInt(form.cartons_per_layer),
        cartons_per_pallet: parseNullableInt(form.cartons_per_pallet),
        carton_width_cm: parseNullableFloat(form.carton_width_cm),
        carton_depth_cm: parseNullableFloat(form.carton_depth_cm),
        carton_height_cm: parseNullableFloat(form.carton_height_cm),
        vol: parseNullableFloat(form.vol),
        peso_lordo: parseNullableFloat(form.peso_lordo),
        peso_netto: parseNullableFloat(form.peso_netto),
        pallet_width_cm: parseNullableFloat(form.pallet_width_cm),
        pallet_depth_cm: parseNullableFloat(form.pallet_depth_cm),
        purchase_cost_eur: parseNullableFloat(form.purchase_cost_eur),
        sale_price_eur: parseNullableFloat(form.sale_price_eur),
        inventory_tracking_enabled: form.inventory_tracking_enabled,
        stock_product_units: parseNullableFloat(form.stock_product_units),
        stock_packaging_units: parseNullableFloat(form.stock_packaging_units),
        product_usage_per_unit: parseNullableFloat(form.product_usage_per_unit),
        packaging_usage_per_unit: parseNullableFloat(form.packaging_usage_per_unit),
        product_alert_threshold: parseNullableFloat(form.product_alert_threshold),
        packaging_alert_threshold: parseNullableFloat(form.packaging_alert_threshold),
      };

      const res = await fetch(`/api/backend/products/${product.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const text = await res.text();
      const data = text ? JSON.parse(text) : {};
      if (!res.ok) throw new Error(data?.detail || "Errore salvataggio prodotto");

      setProduct(data as ProductRead);
      setForm(toFormState(data as ProductRead));
      setMessage("Prodotto aggiornato.");
      await reloadInventoryHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore salvataggio prodotto");
    } finally {
      setSaving(false);
    }
  }

  async function onUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    setMessage(null);

    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`/api/backend/products/${product.id}/documents/upload`, {
        method: "POST",
        body: fd,
      });
      const text = await res.text();
      const data = text ? JSON.parse(text) : {};
      if (!res.ok) throw new Error(data?.detail || "Errore upload documento prodotto");

      setDocuments((prev) => [data as ProductDocumentRead, ...prev]);
      setMessage("Documento prodotto caricato.");
      e.target.value = "";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore upload documento prodotto");
    } finally {
      setUploading(false);
    }
  }

  async function onDeleteDocument(doc: ProductDocumentRead) {
    const confirmed = window.confirm(`Sei sicuro di voler eliminare il documento "${doc.file_name}"?`);
    if (!confirmed) return;
    setError(null);
    setMessage(null);
    try {
      const res = await fetch(`/api/backend/products/${product.id}/documents/${doc.id}`, {
        method: "DELETE",
      });
      const text = await res.text();
      const data = text ? JSON.parse(text) : {};
      if (!res.ok) throw new Error(data?.detail || "Errore eliminazione documento prodotto");
      setDocuments((prev) => prev.filter((item) => item.id !== doc.id));
      setMessage("Documento prodotto eliminato.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore eliminazione documento prodotto");
    }
  }

  return (
    <div className="order-page">
      <div className="page-head">
        <div>
          <h1 style={{ marginBottom: 4 }}>{product.tjx_style || `Prodotto #${product.id}`}</h1>
          <div className="muted">
            <Link href="/products">Prodotti</Link> / Dettaglio prodotto
          </div>
        </div>
      </div>

      {error ? <div className="panel" style={{ borderColor: "#f2c7c7", color: "#b42318" }}>{error}</div> : null}
      {message ? <div className="panel" style={{ borderColor: "#cce5d1", color: "#137333" }}>{message}</div> : null}

      <div className="panel">
        <h2 style={{ marginTop: 0 }}>Informazioni base</h2>
        <div className="grid-2">
          <div className="card">
            <div className="k">Fornitore</div>
            <div className="v" style={{ fontSize: 18 }}>{product.supplier_name || "-"}</div>
          </div>
          <div className="card">
            <div className="k">TJX Style</div>
            <div className="v" style={{ fontSize: 18 }}>{product.tjx_style || "-"}</div>
          </div>
        </div>
      </div>

      <form className="panel" onSubmit={onSave}>
        <div className="page-head" style={{ marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>Informazioni logistiche</h2>
          <button className="btn primary" type="submit" disabled={saving}>
            {saving ? "Salvataggio..." : "Salva"}
          </button>
        </div>

        <div className="grid-2" style={{ marginBottom: 12 }}>
          <div>
            <label className="muted">Descrizione</label>
            <input className="input" value={form.description} onChange={(e) => onChange("description", e.target.value)} />
          </div>
          <div>
            <label className="muted">PCS per CRT</label>
            <input className="input" value={form.pcs_per_crt} onChange={(e) => onChange("pcs_per_crt", e.target.value)} />
          </div>
          <div>
            <label className="muted">Strat x PL</label>
            <input className="input" value={form.strat_x_pl} onChange={(e) => onChange("strat_x_pl", e.target.value)} />
          </div>
          <div>
            <label className="muted">Strat x PLT</label>
            <input className="input" value={form.strat_x_plt} onChange={(e) => onChange("strat_x_plt", e.target.value)} />
          </div>
          <div>
            <label className="muted">Cartoni per strato</label>
            <input className="input" value={form.cartons_per_layer} onChange={(e) => onChange("cartons_per_layer", e.target.value)} />
          </div>
          <div>
            <label className="muted">Cartoni per pallet</label>
            <input className="input" value={form.cartons_per_pallet} onChange={(e) => onChange("cartons_per_pallet", e.target.value)} />
          </div>
          <div>
            <label className="muted">Misura cartone larghezza (cm)</label>
            <input className="input" value={form.carton_width_cm} onChange={(e) => onChange("carton_width_cm", e.target.value)} />
          </div>
          <div>
            <label className="muted">Misura cartone profondita (cm)</label>
            <input className="input" value={form.carton_depth_cm} onChange={(e) => onChange("carton_depth_cm", e.target.value)} />
          </div>
          <div>
            <label className="muted">Misura cartone altezza (cm)</label>
            <input className="input" value={form.carton_height_cm} onChange={(e) => onChange("carton_height_cm", e.target.value)} />
          </div>
          <div>
            <label className="muted">Vol</label>
            <input className="input" value={form.vol} onChange={(e) => onChange("vol", e.target.value)} />
          </div>
          <div>
            <label className="muted">Peso lordo</label>
            <input className="input" value={form.peso_lordo} onChange={(e) => onChange("peso_lordo", e.target.value)} />
          </div>
          <div>
            <label className="muted">Peso netto</label>
            <input className="input" value={form.peso_netto} onChange={(e) => onChange("peso_netto", e.target.value)} />
          </div>
          <div>
            <label className="muted">Larghezza pallet (cm)</label>
            <input className="input" value={form.pallet_width_cm} onChange={(e) => onChange("pallet_width_cm", e.target.value)} />
          </div>
          <div>
            <label className="muted">Profondita pallet (cm)</label>
            <input className="input" value={form.pallet_depth_cm} onChange={(e) => onChange("pallet_depth_cm", e.target.value)} />
          </div>
        </div>

        <div className="panel" style={{ marginTop: 8, padding: 10 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Gestione prezzi</div>
          <div className="grid-2">
            <div>
              <label className="muted">Prezzo acquisto unitario (EUR)</label>
              <input className="input" value={form.purchase_cost_eur} onChange={(e) => onChange("purchase_cost_eur", e.target.value)} />
            </div>
            <div>
              <label className="muted">Prezzo vendita unitario (EUR)</label>
              <input className="input" value={form.sale_price_eur} onChange={(e) => onChange("sale_price_eur", e.target.value)} />
            </div>
          </div>
          <div className="grid-2" style={{ marginTop: 12 }}>
            <div className="card">
              <div className="k">Costo attuale</div>
              <div className="v" style={{ fontSize: 20 }}>{formatMoney(parseNullableFloat(form.purchase_cost_eur))}</div>
            </div>
            <div className="card">
              <div className="k">Prezzo vendita attuale</div>
              <div className="v" style={{ fontSize: 20 }}>{formatMoney(parseNullableFloat(form.sale_price_eur))}</div>
            </div>
          </div>
        </div>

        <div className="panel" style={{ marginTop: 8, padding: 10 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 8 }}>
            <div style={{ fontWeight: 600 }}>Gestione giacenze</div>
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                checked={form.inventory_tracking_enabled}
                onChange={(e) => onToggle("inventory_tracking_enabled", e.target.checked)}
              />
              Attiva gestione giacenze
            </label>
          </div>
          <div className="muted" style={{ marginBottom: 8 }}>
            Di default è disattivata. Quando attiva, usa stock, coefficienti di consumo e soglie alert.
          </div>
          <div className="grid-2">
            <div>
              <label className="muted">Prodotto in stock (unità)</label>
              <input
                className="input"
                value={form.stock_product_units}
                onChange={(e) => onChange("stock_product_units", e.target.value)}
                disabled={!form.inventory_tracking_enabled}
              />
            </div>
            <div>
              <label className="muted">Packaging in stock (unità/kg)</label>
              <input
                className="input"
                value={form.stock_packaging_units}
                onChange={(e) => onChange("stock_packaging_units", e.target.value)}
                disabled={!form.inventory_tracking_enabled}
              />
            </div>
            <div>
              <label className="muted">Coefficiente consumo prodotto / pezzo</label>
              <input
                className="input"
                value={form.product_usage_per_unit}
                onChange={(e) => onChange("product_usage_per_unit", e.target.value)}
                disabled={!form.inventory_tracking_enabled}
              />
            </div>
            <div>
              <label className="muted">Coefficiente consumo packaging / pezzo</label>
              <input
                className="input"
                value={form.packaging_usage_per_unit}
                onChange={(e) => onChange("packaging_usage_per_unit", e.target.value)}
                disabled={!form.inventory_tracking_enabled}
              />
            </div>
            <div>
              <label className="muted">Soglia alert stock prodotto</label>
              <input
                className="input"
                value={form.product_alert_threshold}
                onChange={(e) => onChange("product_alert_threshold", e.target.value)}
                disabled={!form.inventory_tracking_enabled}
              />
            </div>
            <div>
              <label className="muted">Soglia alert stock packaging</label>
              <input
                className="input"
                value={form.packaging_alert_threshold}
                onChange={(e) => onChange("packaging_alert_threshold", e.target.value)}
                disabled={!form.inventory_tracking_enabled}
              />
            </div>
          </div>
        </div>

      </form>

      <div className="panel">
        <div className="page-head" style={{ marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>Storico giacenze</h2>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn" type="button" onClick={() => setShowMovements((v) => !v)}>
              {showMovements ? "Chiudi dettagli movimentazione giacenze" : "Dettagli movimentazione giacenze"}
            </button>
            <button className="btn" type="button" onClick={() => void reloadInventoryHistory()} disabled={refreshingHistory}>
              {refreshingHistory ? "Aggiornamento..." : "Aggiorna storico"}
            </button>
          </div>
        </div>
        <div className="grid-2" style={{ marginBottom: 10 }}>
          <div className="card">
            <div className="k">Stock prodotto attuale</div>
            <div className="v">{inventoryHistory.stock_product_units ?? "-"}</div>
          </div>
          <div className="card">
            <div className="k">Stock packaging attuale</div>
            <div className="v">{inventoryHistory.stock_packaging_units ?? "-"}</div>
          </div>
        </div>

        {showMovements ? (
          <div className="table-wrap" style={{ marginBottom: 12 }}>
            <table>
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Ordine</th>
                  <th>Pezzi consumati</th>
                  <th>Consumo stock prodotto</th>
                  <th>Consumo stock packaging</th>
                  <th>Packaging post-movimento</th>
                </tr>
              </thead>
              <tbody>
                {inventoryHistory.movements.map((row) => (
                  <tr key={row.id}>
                    <td>{formatDateTime(row.applied_at)}</td>
                    <td>{row.order_number || row.customer_order_id || "-"}</td>
                    <td>{row.consumed_pieces}</td>
                    <td>{row.consumed_product_stock}</td>
                    <td>{row.consumed_packaging_stock}</td>
                    <td>{row.stock_packaging_after ?? "-"}</td>
                  </tr>
                ))}
                {inventoryHistory.movements.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="muted">
                      Nessun movimento registrato.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>

      <div className="panel">
        <div className="page-head" style={{ marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>Documenti allegati prodotto</h2>
          <label className="btn" style={{ cursor: uploading ? "not-allowed" : "pointer", opacity: uploading ? 0.6 : 1 }}>
            {uploading ? "Caricamento..." : "Carica documento"}
            <input type="file" style={{ display: "none" }} onChange={onUpload} disabled={uploading} />
          </label>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Nome file</th>
                <th>Tipo</th>
                <th>Dimensione</th>
                <th>Caricato il</th>
                <th>Azioni</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id}>
                  <td>{doc.file_name}</td>
                  <td>{doc.content_type || "-"}</td>
                  <td>{doc.size_bytes != null ? `${Math.round(doc.size_bytes / 1024)} KB` : "-"}</td>
                  <td>{formatDateTime(doc.uploaded_at)}</td>
                  <td>
                    <div style={{ display: "flex", gap: 8 }}>
                      <a
                        className="btn"
                        href={`/api/backend/products/${product.id}/documents/${doc.id}/download?inline=1`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Apri
                      </a>
                      <a className="btn" href={`/api/backend/products/${product.id}/documents/${doc.id}/download`}>
                        Scarica
                      </a>
                      <button className="btn" type="button" onClick={() => void onDeleteDocument(doc)}>
                        Elimina
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {documents.length === 0 ? (
                <tr>
                  <td colSpan={5} className="muted">
                    Nessun documento allegato a questo prodotto.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
