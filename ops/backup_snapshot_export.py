#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from pathlib import Path

from openpyxl import Workbook


TABLES = [
    "customer_orders",
    "customer_order_lines",
    "purchase_orders",
    "purchase_order_lines",
    "packing_lists",
    "packing_list_lines",
    "suppliers",
    "products",
    "distribution_centers",
]


def export_table_csv(conn: sqlite3.Connection, table: str, out_dir: Path) -> tuple[str, int]:
    cur = conn.execute(f"SELECT * FROM {table}")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()

    out_path = out_dir / f"{table}.csv"
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    return str(out_path), len(rows)


def _get_table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return {str(r[1]) for r in cur.fetchall()}


def export_received_pdf_registry(conn: sqlite3.Connection, out_path: Path) -> int:
    available = _get_table_columns(conn, "customer_orders")
    preferred = [
        "id",
        "order_number",
        "customer_name",
        "supplier_name",
        "source_pdf_path",
        "created_at",
        "updated_at",
    ]
    selected = [c for c in preferred if c in available]
    if "source_pdf_path" not in selected:
        selected.append("source_pdf_path")
    query = (
        f"SELECT {', '.join(selected)} FROM customer_orders "
        "WHERE source_pdf_path IS NOT NULL AND TRIM(source_pdf_path) <> '' "
        "ORDER BY id DESC"
    )
    rows = conn.execute(query).fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "pdf_registry"
    ws.append(selected + ["pdf_exists_now"])

    for row in rows:
        values = [row[c] for c in selected]
        raw_path = row["source_pdf_path"] if "source_pdf_path" in selected else ""
        exists_now = "YES" if raw_path and Path(str(raw_path)).is_file() else "NO"
        ws.append(values + [exists_now])

    wb.save(out_path)
    return len(rows)


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: backup_snapshot_export.py <sqlite_db_path> <backup_run_dir>")
        return 2

    db_path = Path(sys.argv[1]).resolve()
    run_dir = Path(sys.argv[2]).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    snapshot_dir = run_dir / "snapshot"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    pdf_registry_xlsx = run_dir / "received_order_pdf_registry.xlsx"

    if not db_path.exists():
        print(f"DB not found: {db_path}")
        return 3

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        exported: dict[str, int] = {}
        for table in TABLES:
            _, count = export_table_csv(conn, table, snapshot_dir)
            exported[table] = count
        tracked_pdfs = export_received_pdf_registry(conn, pdf_registry_xlsx)
    finally:
        conn.close()

    manifest = {
        "db_path": str(db_path),
        "snapshot_tables": exported,
        "received_pdfs_tracked": tracked_pdfs,
        "received_pdf_registry_xlsx": str(pdf_registry_xlsx),
    }
    (run_dir / "snapshot_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
