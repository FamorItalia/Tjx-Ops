from app.db.base_class import Base
from app.db.session import engine

# Import models to register metadata
from app.db import models  # noqa: F401


def _ensure_sqlite_columns() -> None:
    if engine.dialect.name != "sqlite":
        return

    table_new_columns: dict[str, list[tuple[str, str]]] = {
        "customer_orders": [
            ("document_family", "VARCHAR(50)"),
            ("source_file", "VARCHAR(255)"),
            ("supplier_name", "VARCHAR(255)"),
            ("distribution_center", "VARCHAR(50)"),
            ("po_raw", "VARCHAR(100)"),
            ("po_normalized", "VARCHAR(100)"),
            ("import_po_number", "VARCHAR(120)"),
            ("is_archived", "BOOLEAN"),
            ("archived_at", "DATETIME"),
        ],
        "customer_order_lines": [
            ("original_total_units", "INTEGER"),
            ("operational_total_units", "INTEGER"),
            ("item_code", "VARCHAR(120)"),
            ("total_units", "INTEGER"),
            ("distribution_center", "VARCHAR(50)"),
            ("original_units_per_dc_json", "TEXT"),
            ("operational_units_per_dc_json", "TEXT"),
            ("units_per_dc_json", "TEXT"),
            ("store_ready_pack_size", "INTEGER"),
            ("carton_profile", "VARCHAR(20)"),
            ("mixed_carton_group", "VARCHAR(120)"),
        ],
        "purchase_orders": [
            ("supplier_name", "VARCHAR(255)"),
            ("document_family", "VARCHAR(50)"),
            ("brand", "VARCHAR(100)"),
            ("po_raw", "VARCHAR(100)"),
            ("po_normalized", "VARCHAR(100)"),
            ("start_ship_date", "DATE"),
            ("cancel_ship_date", "DATE"),
        ],
        "purchase_order_lines": [
            ("customer_order_line_id", "INTEGER"),
            ("vendor_style", "VARCHAR(120)"),
            ("item_code", "VARCHAR(120)"),
            ("nest_code", "VARCHAR(80)"),
            ("units_per_dc_json", "TEXT"),
            ("logistics_json", "TEXT"),
            ("quantity_base", "INTEGER"),
        ],
        "distribution_centers": [
            ("dc_name", "VARCHAR(255)"),
            ("po_prefix", "VARCHAR(50)"),
            ("city", "VARCHAR(120)"),
            ("state", "VARCHAR(120)"),
            ("zip_code", "VARCHAR(40)"),
            ("country", "VARCHAR(120)"),
            ("general_division_name", "VARCHAR(255)"),
            ("general_address_line_1", "VARCHAR(255)"),
            ("general_address_line_2", "VARCHAR(255)"),
            ("general_address_line_3", "VARCHAR(255)"),
            ("destination_merce_name", "VARCHAR(255)"),
            ("destination_merce_dc_number", "VARCHAR(80)"),
            ("destination_merce_address_line_1", "VARCHAR(255)"),
            ("destination_merce_address_line_2", "VARCHAR(255)"),
            ("destination_merce_address_line_3", "VARCHAR(255)"),
        ],
        "products": [
            ("tjx_style_key", "VARCHAR(100)"),
            ("strat_x_pl", "INTEGER"),
            ("strat_x_plt", "INTEGER"),
            ("vol", "FLOAT"),
            ("peso_lordo", "FLOAT"),
            ("peso_netto", "FLOAT"),
            ("pallet_width_cm", "FLOAT"),
            ("pallet_depth_cm", "FLOAT"),
            ("purchase_cost_eur", "FLOAT"),
            ("sale_price_eur", "FLOAT"),
            ("inventory_tracking_enabled", "BOOLEAN"),
            ("stock_product_units", "FLOAT"),
            ("stock_packaging_units", "FLOAT"),
            ("product_usage_per_unit", "FLOAT"),
            ("packaging_usage_per_unit", "FLOAT"),
            ("product_alert_threshold", "FLOAT"),
            ("packaging_alert_threshold", "FLOAT"),
            ("document_dle", "BOOLEAN"),
            ("document_packing_list", "BOOLEAN"),
            ("document_sfarinati", "BOOLEAN"),
            ("document_p2", "BOOLEAN"),
        ],
        "product_inventory_ledger": [
            ("stock_product_after", "FLOAT"),
            ("stock_packaging_after", "FLOAT"),
        ],
        "suppliers": [
            ("name_key", "VARCHAR(255)"),
            ("ragione_sociale", "VARCHAR(255)"),
            ("indirizzo", "VARCHAR(255)"),
            ("cap", "VARCHAR(30)"),
            ("citta", "VARCHAR(120)"),
            ("provincia", "VARCHAR(50)"),
            ("paese", "VARCHAR(120)"),
            ("telefono", "VARCHAR(80)"),
            ("persona_di_contatto", "VARCHAR(120)"),
            ("emails_json", "TEXT"),
            ("email_subject_template", "TEXT"),
            ("email_order_template", "TEXT"),
        ],
        "packing_lists": [
            ("dc_code", "VARCHAR(50)"),
            ("groups_json", "TEXT"),
            ("supplier_ragione_sociale", "VARCHAR(255)"),
            ("supplier_address_full", "VARCHAR(500)"),
            ("dept_no", "VARCHAR(80)"),
            ("total_pallets", "INTEGER"),
            ("totals_manually_overridden", "INTEGER"),
        ],
        "packing_list_lines": [
            ("group_key", "VARCHAR(120)"),
            ("group_type", "VARCHAR(20)"),
            ("vendor_pack_size", "INTEGER"),
            ("store_ready_pack_size", "INTEGER"),
        ],
    }

    with engine.begin() as conn:
        for table_name, columns in table_new_columns.items():
            existing_cols = {
                row[1]
                for row in conn.exec_driver_sql(f"PRAGMA table_info('{table_name}')").fetchall()
            }
            for col_name, col_sql_type in columns:
                if col_name in existing_cols:
                    continue
                conn.exec_driver_sql(
                    f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_sql_type}"
                )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_customer_orders_source_file_po_raw "
            "ON customer_orders(source_file, po_raw)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_customer_orders_is_archived "
            "ON customer_orders(is_archived)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_purchase_orders_customer_order_id "
            "ON purchase_orders(customer_order_id)"
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_distribution_centers_brand_dc_code "
            "ON distribution_centers(brand, dc_code)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_products_tjx_style_key "
            "ON products(tjx_style_key)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_product_price_history_product_id_changed_at "
            "ON product_price_history(product_id, changed_at)"
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_suppliers_name_key "
            "ON suppliers(name_key)"
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_user_accounts_username "
            "ON user_accounts(username)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_user_sessions_user_id "
            "ON user_sessions(user_id)"
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_user_sessions_token "
            "ON user_sessions(token)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at "
            "ON audit_logs(created_at)"
        )
        conn.exec_driver_sql(
            "UPDATE customer_order_lines "
            "SET original_total_units = COALESCE(original_total_units, total_units)"
        )
        conn.exec_driver_sql(
            "UPDATE customer_order_lines "
            "SET operational_total_units = COALESCE(operational_total_units, total_units, original_total_units)"
        )
        conn.exec_driver_sql(
            "UPDATE customer_order_lines "
            "SET original_units_per_dc_json = COALESCE(original_units_per_dc_json, units_per_dc_json)"
        )
        conn.exec_driver_sql(
            "UPDATE customer_order_lines "
            "SET operational_units_per_dc_json = COALESCE(operational_units_per_dc_json, units_per_dc_json, original_units_per_dc_json)"
        )
        conn.exec_driver_sql(
            "UPDATE customer_orders "
            "SET is_archived = COALESCE(is_archived, 0)"
        )
        conn.exec_driver_sql(
            "UPDATE packing_lists "
            "SET totals_manually_overridden = COALESCE(totals_manually_overridden, 0)"
        )
        conn.exec_driver_sql(
            "UPDATE products "
            "SET inventory_tracking_enabled = COALESCE(inventory_tracking_enabled, 0), "
            "product_usage_per_unit = COALESCE(product_usage_per_unit, 0), "
            "packaging_usage_per_unit = COALESCE(packaging_usage_per_unit, 0), "
            "document_dle = COALESCE(document_dle, 1), "
            "document_packing_list = COALESCE(document_packing_list, 1), "
            "document_sfarinati = COALESCE(document_sfarinati, 0), "
            "document_p2 = COALESCE(document_p2, 0)"
        )


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()
