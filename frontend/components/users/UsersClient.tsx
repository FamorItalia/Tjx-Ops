"use client";

import { useMemo, useState } from "react";
import type { AuditLogRead, AuthUser } from "@/lib/api/types";
import { formatDateTime } from "@/lib/utils/format";

type Props = {
  initialUsers: AuthUser[];
  initialAudit: AuditLogRead[];
  forbidden?: boolean;
  backendError?: string | null;
};

async function callApi<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/backend/${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  if (!res.ok) throw new Error(data.detail || `${res.status} ${res.statusText}`);
  return data as T;
}

export function UsersClient({ initialUsers, initialAudit, forbidden, backendError }: Props) {
  const [users, setUsers] = useState<AuthUser[]>(initialUsers);
  const [audit, setAudit] = useState<AuditLogRead[]>(initialAudit);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(backendError || null);
  const [createdOk, setCreatedOk] = useState<string | null>(null);

  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<"admin" | "operatore" | "viewer">("operatore");
  const [password, setPassword] = useState("");

  const [selectedUserId, setSelectedUserId] = useState<number | "">("");
  const [newPassword, setNewPassword] = useState("");

  async function refreshAll() {
    const [nextUsers, nextAudit] = await Promise.all([
      callApi<AuthUser[]>("auth/users"),
      callApi<AuditLogRead[]>("auth/audit"),
    ]);
    setUsers(nextUsers);
    setAudit(nextAudit);
  }

  async function createUser() {
    setBusy(true);
    setError(null);
    setCreatedOk(null);
    try {
      const row = await callApi<AuthUser>("auth/users", {
        method: "POST",
        body: JSON.stringify({
          username: username.trim(),
          full_name: fullName.trim(),
          role,
          password,
        }),
      });
      setCreatedOk(`Utente creato: ${row.username}`);
      setUsername("");
      setFullName("");
      setPassword("");
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore creazione utente");
    } finally {
      setBusy(false);
    }
  }

  async function changePassword() {
    if (!selectedUserId || !newPassword.trim()) return;
    setBusy(true);
    setError(null);
    setCreatedOk(null);
    try {
      await callApi(`auth/users/${selectedUserId}/password`, {
        method: "PATCH",
        body: JSON.stringify({ password: newPassword }),
      });
      setCreatedOk("Password aggiornata.");
      setNewPassword("");
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore cambio password");
    } finally {
      setBusy(false);
    }
  }

  const usersById = useMemo(() => {
    const map = new Map<number, AuthUser>();
    for (const u of users) map.set(u.id, u);
    return map;
  }, [users]);

  if (forbidden) {
    return (
      <div className="panel">
        <h3>Utenti</h3>
        <p style={{ color: "#b42318" }}>Accesso negato: questa pagina è disponibile solo per admin.</p>
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <section className="panel">
        <h3 style={{ marginTop: 0 }}>Crea utente</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(160px, 1fr))", gap: 10 }}>
          <input className="input" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
          <input className="input" placeholder="Nome completo" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          <select className="input" value={role} onChange={(e) => setRole(e.target.value as any)}>
            <option value="admin">admin</option>
            <option value="operatore">operatore</option>
            <option value="viewer">viewer</option>
          </select>
          <input className="input" type="password" placeholder="Password iniziale" value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <div style={{ marginTop: 10, display: "flex", gap: 10, alignItems: "center" }}>
          <button className="btn primary" disabled={busy || !username || !password} onClick={createUser}>Aggiungi utente</button>
          <button className="btn" disabled={busy} onClick={() => void refreshAll()}>Aggiorna</button>
          {createdOk ? <span style={{ color: "#067647", fontWeight: 600 }}>{createdOk}</span> : null}
          {error ? <span style={{ color: "#b42318", fontWeight: 600 }}>{error}</span> : null}
        </div>
      </section>

      <section className="panel">
        <h3 style={{ marginTop: 0 }}>Cambio password</h3>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 2fr auto", gap: 10 }}>
          <select className="input" value={selectedUserId} onChange={(e) => setSelectedUserId(e.target.value ? Number(e.target.value) : "")}>
            <option value="">Seleziona utente</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name} ({u.username}) - {u.role}
              </option>
            ))}
          </select>
          <input className="input" type="password" placeholder="Nuova password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
          <button className="btn" disabled={busy || !selectedUserId || !newPassword} onClick={changePassword}>Aggiorna password</button>
        </div>
      </section>

      <section className="panel">
        <h3 style={{ marginTop: 0 }}>Elenco utenti</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Username</th>
                <th>Nome</th>
                <th>Ruolo</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.id}</td>
                  <td>{u.username}</td>
                  <td>{u.full_name}</td>
                  <td>{u.role}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <h3 style={{ marginTop: 0 }}>Audit modifiche</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Quando</th>
                <th>Utente</th>
                <th>Metodo</th>
                <th>Path</th>
                <th>Payload</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((a) => (
                <tr key={a.id}>
                  <td>{formatDateTime(a.created_at)}</td>
                  <td>{a.username || (a.user_id ? usersById.get(a.user_id)?.username : "-") || "-"}</td>
                  <td>{a.method}</td>
                  <td>{a.path}</td>
                  <td style={{ maxWidth: 420, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{a.payload_json || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
