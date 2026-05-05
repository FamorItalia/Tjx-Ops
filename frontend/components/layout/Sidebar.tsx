"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/orders/archive", label: "Ordini Spediti" },
  { href: "/suppliers", label: "Fornitori" },
  { href: "/products", label: "Prodotti" },
  { href: "/users", label: "Utenti" },
  { href: "/brands", label: "Insegne" },
  { href: "/errors", label: "Errori" },
];

export function Sidebar() {
  const pathname = usePathname() || "";

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <img src="/tjfamro.jpg" alt="TJX Ops Hub" className="sidebar-logo" />
        <h1 style={{ margin: 0 }}>TJX Ops Hub</h1>
      </div>
      <nav className="menu">
        {items.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link key={item.href} href={item.href} className={active ? "active" : ""}>
              {item.label}
            </Link>
          );
        })}
        <Link href="/import/new" className={pathname === "/import/new" ? "active" : ""}>
          Nuovo Import
        </Link>
      </nav>
    </aside>
  );
}
