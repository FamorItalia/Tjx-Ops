"use client";

import Link from "next/link";
import { ChangeEvent, FormEvent, useMemo, useState } from "react";

import type { SupplierDocumentRead, SupplierProductRead, SupplierRead } from "@/lib/api/types";
import { formatDateTime } from "@/lib/utils/format";

type Props = {
  initialSupplier: SupplierRead;
  initialProducts: SupplierProductRead[];
  initialDocuments: SupplierDocumentRead[];
};

type SupplierFormState = {
  ragione_sociale: string;
  indirizzo: string;
  cap: string;
  citta: string;
  provincia: string;
  paese: string;
  telefono: string;
  persona_di_contatto: string;
  emails_text: string;
  email_subject_template: string;
  email_order_template: string;
};

function toFormState(supplier: SupplierRead): SupplierFormState {
  return {
    ragione_sociale: supplier.ragione_sociale || "",
    indirizzo: supplier.indirizzo || "",
    cap: supplier.cap || "",
    citta: supplier.citta || "",
    provincia: supplier.provincia || "",
    paese: supplier.paese || "",
    telefono: supplier.telefono || "",
    persona_di_contatto: supplier.persona_di_contatto || "",
    emails_text: supplier.emails.join("\n"),
    email_subject_template: supplier.email_subject_template || "",
    email_order_template: supplier.email_order_template || "",
  };
}

function parseEmails(text: string): string[] {
  return text
    .split(/\r?\n|;|,/)
    .map((x) => x.trim())
    .filter(Boolean);
}

function formatMoney(value: number | null) {
  if (value == null) return "-";
  return new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR" }).format(value);
}

export function SupplierDetailClient({ initialSupplier, initialProducts, initialDocuments }: Props) {
  const [supplier, setSupplier] = useState(initialSupplier);
  const [form, setForm] = useState<SupplierFormState>(() => toFormState(initialSupplier));
  const [products] = useState(initialProducts);
  const [documents, setDocuments] = useState(initialDocuments);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const hasProducts = products.length > 0;

  const fullAddress = useMemo(() => {
    const parts = [
      supplier.indirizzo,
      [supplier.cap, supplier.citta, supplier.provincia].filter(Boolean).join(" "),
      supplier.paese,
    ]
      .map((x) => (x || "").trim())
      .filter(Boolean);
    return parts.join(", ");
  }, [supplier]);

  function onChange(field: keyof SupplierFormState, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function saveSupplier() {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const payload = {
        ragione_sociale: form.ragione_sociale || null,
        indirizzo: form.indirizzo || null,
        cap: form.cap || null,
        citta: form.citta || null,
        provincia: form.provincia || null,
        paese: form.paese || null,
        telefono: form.telefono || null,
        persona_di_contatto: form.persona_di_contatto || null,
        emails: parseEmails(form.emails_text),
        email_subject_template: form.email_subject_template || null,
        email_order_template: form.email_order_template || null,
      };
      const res = await fetch(`/api/backend/suppliers/${supplier.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const text = await res.text();
      const data = text ? JSON.parse(text) : {};
      if (!res.ok) throw new Error(data?.detail || "Errore salvataggio fornitore");
      setSupplier(data as SupplierRead);
      setForm(toFormState(data as SupplierRead));
      setMessage("Dati fornitore aggiornati.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore salvataggio fornitore");
    } finally {
      setSaving(false);
    }
  }

  async function onSubmitForm(e: FormEvent) {
    e.preventDefault();
    await saveSupplier();
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
      const res = await fetch(`/api/backend/suppliers/${supplier.id}/documents/upload`, {
        method: "POST",
        body: fd,
      });
      const text = await res.text();
      const data = text ? JSON.parse(text) : {};
      if (!res.ok) throw new Error(data?.detail || "Errore upload documento");
      setDocuments((prev) => [data as SupplierDocumentRead, ...prev]);
      setMessage("Documento caricato correttamente.");
      e.target.value = "";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore upload documento");
    } finally {
      setUploading(false);
    }
  }

  async function onRenameDocument(doc: SupplierDocumentRead) {
    const nextName = window.prompt("Nuovo nome file", doc.file_name);
    if (nextName == null) return;
    const clean = nextName.trim();
    if (!clean) return;

    setError(null);
    setMessage(null);
    try {
      const res = await fetch(`/api/backend/suppliers/${supplier.id}/documents/${doc.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_name: clean }),
      });
      const text = await res.text();
      const data = text ? JSON.parse(text) : {};
      if (!res.ok) throw new Error(data?.detail || "Errore rinomina documento");
      const renamed = data as SupplierDocumentRead;
      setDocuments((prev) => prev.map((item) => (item.id === renamed.id ? renamed : item)));
      setMessage("Documento rinominato.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore rinomina documento");
    }
  }

  async function onDeleteDocument(doc: SupplierDocumentRead) {
    const confirmed = window.confirm(`Sei sicuro di voler eliminare il documento \"${doc.file_name}\"?`);
    if (!confirmed) return;

    setError(null);
    setMessage(null);
    try {
      const res = await fetch(`/api/backend/suppliers/${supplier.id}/documents/${doc.id}`, {
        method: "DELETE",
      });
      const text = await res.text();
      const data = text ? JSON.parse(text) : {};
      if (!res.ok) throw new Error(data?.detail || "Errore eliminazione documento");
      setDocuments((prev) => prev.filter((item) => item.id !== doc.id));
      setMessage("Documento eliminato.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore eliminazione documento");
    }
  }

  return (
    <div className="order-page">
      <div className="page-head">
        <div>
          <h1 style={{ marginBottom: 4 }}>{supplier.fornitore}</h1>
          <div className="muted">
            <Link href="/suppliers">Fornitori</Link> / Dettaglio fornitore
          </div>
        </div>
      </div>

      {error ? <div className="panel" style={{ borderColor: "#f2c7c7", color: "#b42318" }}>{error}</div> : null}
      {message ? <div className="panel" style={{ borderColor: "#cce5d1", color: "#137333" }}>{message}</div> : null}

      <form className="panel" onSubmit={onSubmitForm}>
        <div className="page-head" style={{ marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>Dettagli anagrafici</h2>
          <button className="btn primary" type="submit" disabled={saving}>
            {saving ? "Salvataggio..." : "Salva modifiche"}
          </button>
        </div>

        <div className="grid-2">
          <div>
            <label className="muted">Ragione sociale</label>
            <input className="input" value={form.ragione_sociale} onChange={(e) => onChange("ragione_sociale", e.target.value)} />
          </div>
          <div>
            <label className="muted">Persona di contatto</label>
            <input className="input" value={form.persona_di_contatto} onChange={(e) => onChange("persona_di_contatto", e.target.value)} />
          </div>
          <div>
            <label className="muted">Indirizzo</label>
            <input className="input" value={form.indirizzo} onChange={(e) => onChange("indirizzo", e.target.value)} />
          </div>
          <div>
            <label className="muted">Telefono</label>
            <input className="input" value={form.telefono} onChange={(e) => onChange("telefono", e.target.value)} />
          </div>
          <div>
            <label className="muted">CAP</label>
            <input className="input" value={form.cap} onChange={(e) => onChange("cap", e.target.value)} />
          </div>
          <div>
            <label className="muted">Città</label>
            <input className="input" value={form.citta} onChange={(e) => onChange("citta", e.target.value)} />
          </div>
          <div>
            <label className="muted">Provincia</label>
            <input className="input" value={form.provincia} onChange={(e) => onChange("provincia", e.target.value)} />
          </div>
          <div>
            <label className="muted">Paese</label>
            <input className="input" value={form.paese} onChange={(e) => onChange("paese", e.target.value)} />
          </div>
        </div>

        <div style={{ marginTop: 12 }}>
          <label className="muted">Email destinatari (una per riga)</label>
          <textarea
            className="input"
            rows={4}
            value={form.emails_text}
            onChange={(e) => onChange("emails_text", e.target.value)}
          />
        </div>

        <div style={{ marginTop: 12 }}>
          <label className="muted">Anteprima indirizzo completo</label>
          <div className="panel" style={{ padding: 10 }}>{fullAddress || "-"}</div>
        </div>
      </form>

      <div className="panel">
        <div className="page-head" style={{ marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>Documenti / Certificazioni</h2>
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
                      <button className="btn" type="button" onClick={() => void onRenameDocument(doc)}>
                        Rinomina
                      </button>
                      <a
                        className="btn"
                        href={`/api/backend/suppliers/${supplier.id}/documents/${doc.id}/download?inline=1`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Apri
                      </a>
                      <a className="btn" href={`/api/backend/suppliers/${supplier.id}/documents/${doc.id}/download`}>
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
                    Nessun documento caricato.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <h2 style={{ marginTop: 0 }}>Prodotti associati (sola visualizzazione)</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Style</th>
                <th>Descrizione</th>
                <th>PCS x CRT</th>
                <th>Costo unitario</th>
                <th>Prezzo vendita unitario</th>
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <tr key={product.id}>
                  <td>{product.tjx_style || "-"}</td>
                  <td>{product.description || "-"}</td>
                  <td>{product.pcs_per_crt ?? "-"}</td>
                  <td>{formatMoney(product.purchase_cost_eur)}</td>
                  <td>{formatMoney(product.sale_price_eur)}</td>
                </tr>
              ))}
              {!hasProducts ? (
                <tr>
                  <td colSpan={5} className="muted">
                    Nessun prodotto associato a questo fornitore.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <div className="page-head" style={{ marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>Template email ordine (modificabile)</h2>
          <button className="btn primary" onClick={() => void saveSupplier()} disabled={saving} type="button">
            {saving ? "Salvataggio..." : "Salva template email"}
          </button>
        </div>
        <label className="muted">Template oggetto</label>
        <input
          className="input"
          value={form.email_subject_template}
          onChange={(e) => onChange("email_subject_template", e.target.value)}
          placeholder="Es: ORDINE TJX - PO# {{po}} - {{brand}}"
          style={{ marginBottom: 10 }}
        />
        <div className="muted" style={{ marginBottom: 8 }}>
          Placeholder disponibili: {`{{po}}`} {`{{brand}}`} {`{{supplier}}`} {`{{fornitore}}`} {`{{start_ship_date}}`} {`{{cancel_ship_date}}`} {`{{contact_name}}`} {`{{supplier_company}}`}
        </div>
        <label className="muted">Template corpo</label>
        <textarea
          className="input"
          rows={8}
          value={form.email_order_template}
          onChange={(e) => onChange("email_order_template", e.target.value)}
          placeholder={"Inserisci il testo base email. Puoi usare placeholder, es:\nGentile {{contact_name}},\nin allegato inviamo ordine PO {{po}}."}
        />
      </div>
    </div>
  );
}
