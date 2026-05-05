"use client";

import { useState } from "react";

import type { ParserPreview, PdfFileInfo, PdfUploadResponse } from "@/lib/api/types";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDate } from "@/lib/utils/format";

type ParserKind = "sierra" | "tjx_usa" | "tjx_canada";

function inferParser(fileName: string): ParserKind {
  const n = fileName.toUpperCase();
  if (n.includes("HOME SENSE") || n.includes("WINNERS") || n.includes("CAN MARSH") || n.includes("CANADIAN MARSHALLS")) {
    return "tjx_canada";
  }
  if (n.includes("TJMAXX") || n.includes("TJ MAXX") || n.includes("MARSHALLS") || n.includes("HOMEGOODS")) {
    return "tjx_usa";
  }
  return "sierra";
}

async function callApi<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/backend/${path}`, init);
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  if (!res.ok) throw new Error(data.detail || `${res.status} ${res.statusText}`);
  return data as T;
}

export function ImportWorkbench({ files }: { files: PdfFileInfo[] }) {
  const [selectedFile, setSelectedFile] = useState<string>(files[0]?.file_name || "");
  const [parserKind, setParserKind] = useState<ParserKind>(selectedFile ? inferParser(selectedFile) : "sierra");
  const [preview, setPreview] = useState<ParserPreview | null>(null);
  const [uploadInfo, setUploadInfo] = useState<PdfUploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function uploadPdf(file: File) {
    setBusy(true);
    setError(null);
    setPreview(null);
    try {
      const data = new FormData();
      data.append("file", file);
      const uploaded = await callApi<PdfUploadResponse>("files/upload-pdf", {
        method: "POST",
        body: data,
      });
      setUploadInfo(uploaded);
      setSelectedFile(uploaded.file_name);
      setParserKind((uploaded.parser_hint as ParserKind) || inferParser(uploaded.file_name));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore upload PDF");
    } finally {
      setBusy(false);
    }
  }

  async function parseAndPreview() {
    if (!selectedFile) return;
    setBusy(true);
    setError(null);
    try {
      const parsed = await callApi<ParserPreview>(`parser/${parserKind}/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_name: selectedFile }),
      });
      setPreview(parsed);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore preview parser");
    } finally {
      setBusy(false);
    }
  }

  async function confirmAndSave() {
    if (!selectedFile) return;
    setBusy(true);
    setError(null);
    try {
      const parsed = await callApi<ParserPreview>(`parser/${parserKind}/test?save=true`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_name: selectedFile }),
      });
      setPreview(parsed);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore salvataggio ordine");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="page-head">
        <h1>Nuovo Import</h1>
      </div>

      <div
        className="dropzone panel"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const file = e.dataTransfer.files[0];
          if (file) void uploadPdf(file);
        }}
      >
        <b>Drag & drop PDF ordine cliente</b>
        <p className="muted">Il file viene caricato in backend e preparato per l'elaborazione.</p>
        <label className="btn" style={{ display: "inline-block", marginTop: 6 }}>
          Seleziona file
          <input
            type="file"
            accept="application/pdf"
            style={{ display: "none" }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void uploadPdf(file);
            }}
          />
        </label>
      </div>

      {uploadInfo ? (
        <div className="panel">
          <h3>File caricato</h3>
          <div className="cards">
            <div className="card">
              <div className="k">File</div>
              <div className="v" style={{ fontSize: 14 }}>{uploadInfo.file_name}</div>
            </div>
            <div className="card">
              <div className="k">Parser rilevato</div>
              <div className="v" style={{ fontSize: 14 }}>{parserKind.toUpperCase()}</div>
            </div>
            <div className="card">
              <div className="k">Dimensione</div>
              <div className="v" style={{ fontSize: 14 }}>{uploadInfo.size_bytes} bytes</div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <button className="btn primary" onClick={parseAndPreview} disabled={busy}>
              Preview dati
            </button>
            <button className="btn" onClick={confirmAndSave} disabled={busy || !preview}>
              Conferma elaborazione e salva
            </button>
          </div>
        </div>
      ) : null}

      {error ? (
        <div className="panel">
          <StatusBadge tone="err" label={error} />
        </div>
      ) : null}

      {preview ? (
        <div className="panel">
          <h3>Preview ordine</h3>
          <div className="cards">
            <div className="card">
              <div className="k">PO</div>
              <div className="v" style={{ fontSize: 16 }}>{preview.po_normalized || preview.po_raw || "-"}</div>
            </div>
            <div className="card">
              <div className="k">Customer</div>
              <div className="v" style={{ fontSize: 16 }}>{preview.brand || "-"}</div>
            </div>
            <div className="card">
              <div className="k">Start Ship</div>
              <div className="v" style={{ fontSize: 16 }}>{formatDate(preview.start_ship_date || null)}</div>
            </div>
            <div className="card">
              <div className="k">Cancel Date</div>
              <div className="v" style={{ fontSize: 16 }}>{formatDate(preview.cancel_ship_date || null)}</div>
            </div>
            <div className="card">
              <div className="k">Righe</div>
              <div className="v">{preview.lines.length}</div>
            </div>
          </div>

          {preview.saved_order_id ? (
            <p style={{ marginTop: 10 }}>
              <StatusBadge tone="ok" label={`Ordine salvato (ID ${preview.saved_order_id})`} />
            </p>
          ) : null}

          <h4 style={{ marginBottom: 6 }}>Warnings parser</h4>
          {preview.warnings.length === 0 ? (
            <p className="muted">Nessun warning.</p>
          ) : (
            <div className="table-wrap">
              <table style={{ minWidth: 500 }}>
                <thead>
                  <tr>
                    <th>Codice</th>
                    <th>Messaggio</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.warnings.map((w, idx) => (
                    <tr key={idx}>
                      <td>{w.code}</td>
                      <td>{w.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
