"use client";

import Link from "next/link";
import { useRef, useState } from "react";

import type { SupplierImportResponse, SupplierRead } from "@/lib/api/types";

type Props = {
  initialSuppliers: SupplierRead[];
};

export function SuppliersListClient({ initialSuppliers }: Props) {
  const [suppliers, setSuppliers] = useState<SupplierRead[]>(initialSuppliers);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [newSupplier, setNewSupplier] = useState({
    fornitore: "",
    ragione_sociale: "",
    persona_di_contatto: "",
    telefono: "",
    emails: "",
  });

  async function refreshSuppliers() {
    const res = await fetch("/api/backend/suppliers", { cache: "no-store" });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.detail || "Errore aggiornamento fornitori");
    setSuppliers(data as SupplierRead[]);
  }

  async function onImportExcel(file: File) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch("/api/backend/suppliers/import", {
        method: "POST",
        body: formData,
      });
      const data = (await res.json()) as SupplierImportResponse | { detail?: string };
      if (!res.ok) {
        throw new Error((data as { detail?: string }).detail || "Errore import fornitori");
      }
      const payload = data as SupplierImportResponse;
      await refreshSuppliers();
      const warn = payload.warnings?.length ? ` - warning: ${payload.warnings.length}` : "";
      setMessage(
        `Import completato: inseriti ${payload.inserted_count}, aggiornati ${payload.updated_count}, saltati ${payload.skipped_count}${warn}.`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore import fornitori");
    } finally {
      setBusy(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function onCreateSupplier() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const payload = {
        fornitore: newSupplier.fornitore,
        ragione_sociale: newSupplier.ragione_sociale || null,
        persona_di_contatto: newSupplier.persona_di_contatto || null,
        telefono: newSupplier.telefono || null,
        emails: newSupplier.emails
          .split(/[;,]/)
          .map((x) => x.trim())
          .filter(Boolean),
      };
      const res = await fetch("/api/backend/suppliers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Errore creazione fornitore");
      await refreshSuppliers();
      setAdding(false);
      setNewSupplier({
        fornitore: "",
        ragione_sociale: "",
        persona_di_contatto: "",
        telefono: "",
        emails: "",
      });
      setMessage("Fornitore creato correttamente.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore creazione fornitore");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="page-head">
        <h1>Fornitori</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <a className="btn" href="/api/backend/suppliers/export/excel">
            Export Excel
          </a>
          <button className="btn" disabled={busy} onClick={() => fileInputRef.current?.click()}>
            {busy ? "Import in corso..." : "Import Excel"}
          </button>
          <button className="btn primary" disabled={busy} onClick={() => setAdding((v) => !v)}>
            {adding ? "Chiudi" : "Aggiungi Fornitore"}
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
                value={newSupplier.fornitore}
                onChange={(e) => setNewSupplier((p) => ({ ...p, fornitore: e.target.value }))}
              />
            </div>
            <div>
              <label className="muted">Ragione sociale</label>
              <input
                className="input"
                value={newSupplier.ragione_sociale}
                onChange={(e) => setNewSupplier((p) => ({ ...p, ragione_sociale: e.target.value }))}
              />
            </div>
            <div>
              <label className="muted">Persona di contatto</label>
              <input
                className="input"
                value={newSupplier.persona_di_contatto}
                onChange={(e) => setNewSupplier((p) => ({ ...p, persona_di_contatto: e.target.value }))}
              />
            </div>
            <div>
              <label className="muted">Telefono</label>
              <input
                className="input"
                value={newSupplier.telefono}
                onChange={(e) => setNewSupplier((p) => ({ ...p, telefono: e.target.value }))}
              />
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <label className="muted">Email (separate da ; o ,)</label>
              <input
                className="input"
                value={newSupplier.emails}
                onChange={(e) => setNewSupplier((p) => ({ ...p, emails: e.target.value }))}
              />
            </div>
          </div>
          <div style={{ marginTop: 10 }}>
            <button className="btn primary" disabled={busy || !newSupplier.fornitore.trim()} onClick={() => void onCreateSupplier()}>
              Salva fornitore
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
              <th>Fornitore</th>
              <th>Ragione Sociale</th>
              <th>Contatto</th>
              <th>Email</th>
              <th>Dettaglio</th>
            </tr>
          </thead>
          <tbody>
            {suppliers.map((s) => (
              <tr key={s.id}>
                <td>{s.id}</td>
                <td>{s.fornitore}</td>
                <td>{s.ragione_sociale || "-"}</td>
                <td>{s.persona_di_contatto || "-"} {s.telefono ? `(${s.telefono})` : ""}</td>
                <td>{s.emails.join(", ") || "-"}</td>
                <td>
                  <Link className="btn" href={`/suppliers/${s.id}`}>
                    Apri
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
