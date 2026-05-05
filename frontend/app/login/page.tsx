"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { setAuthToken } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await fetch("/api/backend/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const text = await res.text();
      const data = text ? JSON.parse(text) : {};
      if (!res.ok) throw new Error(data.detail || "Login fallito");
      if (!data?.token) throw new Error("Token non ricevuto.");
      setAuthToken(data.token);
      router.push("/dashboard");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore login");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", background: "#f5f7fb" }}>
      <form onSubmit={onSubmit} className="panel" style={{ width: 420, maxWidth: "92vw", padding: 24 }}>
        <h1 style={{ marginTop: 0 }}>TJX Ops Hub</h1>
        <p className="muted" style={{ marginTop: -6 }}>Accesso utente</p>
        <label className="muted">Username</label>
        <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} required />
        <label className="muted" style={{ marginTop: 10 }}>Password</label>
        <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        {error ? <div style={{ marginTop: 10, color: "#b42318", fontSize: 14 }}>{error}</div> : null}
        <button className="btn primary" style={{ marginTop: 14, width: "100%" }} disabled={busy}>
          {busy ? "Accesso..." : "Entra"}
        </button>
        <p className="muted" style={{ marginTop: 10, fontSize: 12 }}>
          Primo accesso: <b>admin</b> / <b>admin123</b>
        </p>
      </form>
    </div>
  );
}
