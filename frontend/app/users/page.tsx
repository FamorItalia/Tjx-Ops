import { backendRequest } from "@/lib/api/server";
import type { AuditLogRead, AuthUser } from "@/lib/api/types";
import { UsersClient } from "@/components/users/UsersClient";

export default async function UsersPage() {
  try {
    const [users, audit] = await Promise.all([
      backendRequest<AuthUser[]>("/auth/users"),
      backendRequest<AuditLogRead[]>("/auth/audit"),
    ]);
    return <UsersClient initialUsers={users} initialAudit={audit} />;
  } catch (e) {
    const message = e instanceof Error ? e.message : "Errore caricamento utenti";
    const forbidden = /403|Permesso negato|Accesso negato/i.test(message);
    return <UsersClient initialUsers={[]} initialAudit={[]} forbidden={forbidden} backendError={message} />;
  }
}
