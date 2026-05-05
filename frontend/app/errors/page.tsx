"use client";

import { useEffect, useMemo, useState } from "react";

type OpsHealth = {
  backend?: { status?: string; app?: string; env?: string; utc_time?: string };
  frontend?: { build_id?: string | null };
  watchdog?: {
    configured?: boolean;
    last_run_utc?: string | null;
    backend_ok?: boolean | null;
    frontend_ok?: boolean | null;
    is_stale?: boolean | null;
  };
};

function Badge({ ok, text }: { ok: boolean | null; text: string }) {
  const bg = ok === null ? "#f3f4f6" : ok ? "#e8f7ec" : "#fdecea";
  const color = ok === null ? "#475467" : ok ? "#0a7a33" : "#b42318";
  return (
    <span style={{ background: bg, color, borderRadius: 999, padding: "4px 10px", fontSize: 12, fontWeight: 700 }}>
      {text}
    </span>
  );
}

export default function ErrorsPage() {
  const [data, setData] = useState<OpsHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/backend/health/ops", { cache: "no-store" });
      const text = await res.text();
      const payload = text ? (JSON.parse(text) as OpsHealth) : {};
      if (!res.ok) throw new Error("Errore caricamento stato tecnico");
      setData(payload);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore caricamento stato tecnico");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const watchdogHealthy = useMemo(() => {
    const wd = data?.watchdog;
    if (!wd || !wd.configured) return null;
    if (wd.is_stale) return false;
    if (wd.backend_ok === false || wd.frontend_ok === false) return false;
    if (wd.backend_ok === true && wd.frontend_ok === true) return true;
    return null;
  }, [data]);

  return (
    <div>
      <div className="page-head" style={{ marginBottom: 10 }}>
        <h1>Errori / Health tecnico</h1>
        <button className="btn" onClick={() => void load()} disabled={loading}>
          {loading ? "Aggiornamento..." : "Aggiorna"}
        </button>
      </div>

      {error ? <div className="panel" style={{ borderColor: "#f2c7c7", color: "#b42318" }}>{error}</div> : null}

      <div className="grid-3">
        <div className="panel">
          <div className="muted" style={{ marginBottom: 6 }}>Backend</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <Badge ok={data?.backend?.status === "ok"} text={data?.backend?.status === "ok" ? "OK" : "KO"} />
            <strong>{data?.backend?.app || "-"}</strong>
          </div>
          <div className="muted">Env: {data?.backend?.env || "-"}</div>
          <div className="muted">UTC: {data?.backend?.utc_time || "-"}</div>
        </div>

        <div className="panel">
          <div className="muted" style={{ marginBottom: 6 }}>Frontend</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <Badge ok={!!data?.frontend?.build_id} text={data?.frontend?.build_id ? "Build OK" : "Build assente"} />
          </div>
          <div className="muted">Build ID: {data?.frontend?.build_id || "-"}</div>
        </div>

        <div className="panel">
          <div className="muted" style={{ marginBottom: 6 }}>Watchdog</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <Badge
              ok={watchdogHealthy}
              text={
                data?.watchdog?.configured
                  ? watchdogHealthy === false
                    ? "Da verificare"
                    : "Attivo"
                  : "Non configurato"
              }
            />
          </div>
          <div className="muted">Ultimo run UTC: {data?.watchdog?.last_run_utc || "-"}</div>
          <div className="muted">Check backend: {String(data?.watchdog?.backend_ok ?? "-")}</div>
          <div className="muted">Check frontend: {String(data?.watchdog?.frontend_ok ?? "-")}</div>
        </div>
      </div>

      <div className="panel">
        <h2 style={{ marginTop: 0 }}>Note</h2>
        <ul>
          <li>Questo pannello è operativo e sostituisce la vecchia pagina solo descrittiva.</li>
          <li>Lo stato watchdog è calcolato da `ops/logs/watchdog-heartbeat.json` aggiornato dal watchdog.</li>
          <li>Se il watchdog non è configurato, installarlo da `ops/setup-watchdog.ps1`.</li>
        </ul>
      </div>
    </div>
  );
}
