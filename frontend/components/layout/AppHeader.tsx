"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { useRouter } from "next/navigation";
import { clearAuthToken } from "@/lib/auth";

function pageTitle(pathname: string): string {
  if (pathname.startsWith("/dashboard")) return "Dashboard";
  if (pathname.startsWith("/import/new")) return "Nuovo Import";
  if (pathname.startsWith("/orders/active")) return "Ordini Attivi";
  if (pathname.startsWith("/orders/archive")) return "Ordini Spediti";
  if (pathname.startsWith("/orders/")) return "Dettaglio Ordine";
  if (pathname.startsWith("/suppliers")) return "Fornitori";
  if (pathname.startsWith("/products")) return "Prodotti";
  if (pathname.startsWith("/users")) return "Utenti";
  if (pathname.startsWith("/brands")) return "Insegne";
  return "TJX Ops Hub";
}

export function AppHeader() {
  const pathname = usePathname() || "";
  const router = useRouter();
  const [fullName, setFullName] = useState<string>("");

  useEffect(() => {
    let live = true;
    fetch("/api/backend/auth/me", { cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) return;
        const text = await res.text();
        const data = text ? JSON.parse(text) : null;
        if (!data || !live) return;
        setFullName(data.full_name || data.username || "");
      })
      .catch(() => void 0);
    return () => {
      live = false;
    };
  }, [pathname]);

  async function onLogout() {
    try {
      await fetch("/api/backend/auth/logout", { method: "POST" });
    } catch {
      // ignore
    }
    clearAuthToken();
    router.push("/login");
    router.refresh();
  }

  return (
    <header className="app-header">
      <div>
        <div className="app-header-title">{pageTitle(pathname)}</div>
        <div className="app-header-subtitle">Console operativa interna</div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div className="app-header-brand">{fullName ? `${fullName} · TJX Ops Hub` : "TJX Ops Hub"}</div>
        <button className="btn" onClick={onLogout}>Esci</button>
      </div>
    </header>
  );
}
