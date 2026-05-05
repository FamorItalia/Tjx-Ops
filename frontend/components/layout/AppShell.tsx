"use client";

import { usePathname } from "next/navigation";
import { AppHeader } from "@/components/layout/AppHeader";
import { Sidebar } from "@/components/layout/Sidebar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "";
  if (pathname.startsWith("/login")) {
    return <>{children}</>;
  }
  return (
    <div className="app-shell">
      <Sidebar />
      <main className="content">
        <AppHeader />
        <div className="content-body">{children}</div>
      </main>
    </div>
  );
}
