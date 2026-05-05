export type ProductRead = {
  id: number;
  supplier_name: string | null;
  tjx_style: string | null;
  tjx_style_key: string | null;
  description: string | null;
  pcs_per_crt: number | null;
  strat_x_pl: number | null;
  strat_x_plt: number | null;
  cartons_per_layer: number | null;
  cartons_per_pallet: number | null;
  carton_width_cm: number | null;
  carton_depth_cm: number | null;
  carton_height_cm: number | null;
  vol: number | null;
  peso_lordo: number | null;
  peso_netto: number | null;
  pallet_width_cm: number | null;
  pallet_depth_cm: number | null;
  purchase_cost_eur: number | null;
  sale_price_eur: number | null;
  inventory_tracking_enabled: boolean;
  stock_product_units: number | null;
  stock_packaging_units: number | null;
  product_usage_per_unit: number | null;
  packaging_usage_per_unit: number | null;
  product_alert_threshold: number | null;
  packaging_alert_threshold: number | null;
  document_dle: boolean;
  document_packing_list: boolean;
  document_sfarinati: boolean;
  document_p2: boolean;
};

export type ProductDocumentRead = {
  id: number;
  product_id: number;
  file_name: string;
  content_type: string | null;
  size_bytes: number | null;
  uploaded_at: string;
};

export type ProductInventoryMovementRead = {
  id: number;
  customer_order_id: number | null;
  order_number: string | null;
  movement_type: "order" | "manual";
  note: string | null;
  consumed_pieces: number;
  consumed_product_stock: number;
  consumed_packaging_stock: number;
  stock_product_after: number | null;
  stock_packaging_after: number | null;
  applied_at: string;
};

export type ProductInventoryAlertRead = {
  id: number;
  customer_order_id: number | null;
  stock_type: string;
  threshold_value: number;
  current_value: number;
  email_sent: boolean;
  email_error: string | null;
  created_at: string;
};

export type ProductInventoryHistoryRead = {
  product_id: number;
  inventory_tracking_enabled: boolean;
  stock_product_units: number | null;
  stock_packaging_units: number | null;
  movements: ProductInventoryMovementRead[];
  alerts: ProductInventoryAlertRead[];
};

export type OrderListItem = {
  id: number;
  document_family: string;
  brand: string | null;
  supplier?: string | null;
  source_file: string;
  start_ship_date: string | null;
  cancel_ship_date: string | null;
  total_cartons?: number | null;
  distribution_center: string | null;
  po_raw: string | null;
  po_normalized: string | null;
  import_po_number: string | null;
  is_archived: boolean;
  archived_at: string | null;
  created_at: string;
};

export type DistributionCenterDetail = {
  dc_code: string;
  dc_name: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  zip_code: string | null;
  country: string | null;
};

export type OrderLine = {
  id: number;
  vendor_style: string | null;
  item_code: string | null;
  description: string | null;
  original_units: number | null;
  operational_units: number | null;
  total_units: number | null;
  distribution_center: string | null;
  nest_code: string | null;
  original_units_per_dc: Record<string, number>;
  operational_units_per_dc: Record<string, number>;
  units_per_dc: Record<string, number>;
  carton_profile: string | null;
  mixed_carton_group: string | null;
  vend_pack: number | null;
  store_ready_pack_size: number | null;
  distribution_center_detail: DistributionCenterDetail | null;
  units_per_dc_details: Record<string, DistributionCenterDetail>;
};

export type OrderDetail = OrderListItem & {
  lines: OrderLine[];
};

export type PdfFileInfo = {
  file_name: string;
  absolute_path: string;
  source_folder: string;
  size_bytes: number;
};

export type PdfListResponse = {
  total: number;
  files: PdfFileInfo[];
};

export type PdfUploadResponse = {
  file_name: string;
  absolute_path: string;
  source_folder: string;
  size_bytes: number;
  parser_hint: "sierra" | "tjx_usa" | "tjx_canada" | null;
};

export type ParserWarning = {
  code: string;
  message: string;
  page?: number | null;
  context?: Record<string, string>;
};

export type ParserPreview = {
  document_family: string;
  brand?: string | null;
  source_file: string;
  po_raw?: string | null;
  po_normalized?: string | null;
  start_ship_date?: string | null;
  cancel_ship_date?: string | null;
  lines: Array<Record<string, unknown>>;
  warnings: ParserWarning[];
  saved_order_id?: number | null;
};

export type PurchaseOrderPreview = {
  id: number;
  customer_order_id: number | null;
  document_family: string | null;
  brand: string | null;
  supplier: string | null;
  po: string | null;
  po_raw: string | null;
  po_normalized: string | null;
  start_ship_date: string | null;
  cancel_ship_date: string | null;
  adjustment_percent: number;
  total_lines: number;
  total_quantity_base: number;
  total_quantity_final: number;
  lines: Array<{
    id: number | null;
    vendor_style: string | null;
    item_code: string | null;
    description: string | null;
    nest_code: string | null;
    units_per_dc: Record<string, number>;
    quantity_base: number | null;
    quantity_final: number | null;
  }>;
};

export type PackingListBatch = {
  purchase_order_id: number;
  customer_order_id: number | null;
  po_number: string | null;
  brand: string | null;
  packing_lists: Array<{
    id: number;
    dc_code: string | null;
    total_pieces: number;
    total_cartons: number;
    total_gross_weight: number;
    total_net_weight: number;
    total_cubic_meters: number;
    warnings: Array<Record<string, unknown>>;
  }>;
};

export type OrderDocument = {
  document_type: string;
  level: "PO" | "DC";
  dc_code: string | null;
  format: string;
  file_name: string;
  file_path: string;
  generated_at: string | null;
};

export type OrderPackingList = {
  id: number;
  dc_code: string | null;
  invoice_number: string | null;
  document_date: string | null;
  total_pieces: number | null;
  total_cartons: number | null;
  total_gross_weight: number | null;
  total_net_weight: number | null;
  total_cubic_meters: number | null;
  total_pallets: number | null;
  totals_manually_overridden: boolean;
  created_at: string | null;
};

export type LogisticsGroupProduct = {
  line_id: number | null;
  vendor_style: string | null;
  item_code: string | null;
  description: string | null;
  units: number;
  cartons: number;
  master_carton: number | null;
  store_ready_pack_size: number | null;
};

export type LogisticsGroup = {
  nest_code: string | null;
  type: "mono" | "nested";
  cartons: number;
  pcs_per_carton: number;
  carton_size: string | null;
  gross_weight_per_carton: number | null;
  net_weight_per_carton: number | null;
  total_gross_weight: number | null;
  total_net_weight: number | null;
  total_volume: number | null;
  total_pallets: number | null;
  warnings: Array<Record<string, unknown>>;
  products: LogisticsGroupProduct[];
};

export type LogisticsDcSummary = {
  dc_code: string;
  total_pieces: number;
  total_cartons: number;
  total_volume: number | null;
  total_gross_weight: number | null;
  total_net_weight: number | null;
  total_pallets: number | null;
  groups: LogisticsGroup[];
};

export type LogisticsScopeSummary = {
  total_pieces: number;
  total_cartons: number;
  total_volume: number | null;
  total_gross_weight: number | null;
  total_net_weight: number | null;
  total_pallets: number | null;
  dcs: LogisticsDcSummary[];
};

export type OrderLogisticsSummary = {
  order_id: number;
  received: LogisticsScopeSummary;
  operational: LogisticsScopeSummary;
};

export type DocumentOption = {
  document_type: string;
  label: string;
  level: "ORDER" | "DC";
  enabled: boolean;
  formats: string[];
  reason: string | null;
};

export type DocumentDcOptions = {
  dc_code: string;
  options: DocumentOption[];
};

export type OrderDocumentOptions = {
  order_id: number;
  has_sfarinati: boolean;
  has_p2: boolean;
  order_level_options: DocumentOption[];
  dc_level_options: DocumentDcOptions[];
};

export type ActiveOrderDashboardRow = {
  id: number;
  po: string | null;
  customer: string | null;
  supplier: string | null;
  start_ship_date: string | null;
  cancel_ship_date: string | null;
  order_status: "Programmato" | "Pronto al ritiro" | "In ritardo";
  is_late: boolean;
  total_cartons: number | null;
  dc_preview: Array<{
    dc_code: string;
    quantity: number;
    cartons: number | null;
  }>;
};

export type InventoryAlertDashboard = {
  id: number;
  product_id: number;
  product_style: string | null;
  supplier_name: string | null;
  stock_type: string;
  threshold_value: number;
  current_value: number;
  below_by: number;
  customer_order_id: number | null;
  created_at: string;
};

export type BrandSummary = {
  key: string;
  label: string;
  total_orders_year: number;
  archived_orders_year: number;
  to_ship_orders_year: number;
  annual_revenue_eur: number;
  period_start: string;
  period_end: string;
};

export type BrandOrderRow = {
  order_id: number;
  po: string | null;
  supplier: string | null;
  created_at: string | null;
  start_ship_date: string | null;
  cancel_ship_date: string | null;
  order_status: "Programmato" | "Pronto al ritiro" | "In ritardo";
  is_archived: boolean;
  total_pieces: number;
  total_cartons: number | null;
  total_volume_cubic_meters: number | null;
  order_total_sale_eur: number;
};

export type SupplierRead = {
  id: number;
  fornitore: string;
  ragione_sociale: string | null;
  indirizzo: string | null;
  cap: string | null;
  citta: string | null;
  provincia: string | null;
  paese: string | null;
  telefono: string | null;
  persona_di_contatto: string | null;
  emails: string[];
  email_subject_template: string | null;
  email_order_template: string | null;
  is_active: boolean;
};

export type SupplierDocumentRead = {
  id: number;
  supplier_id: number;
  file_name: string;
  content_type: string | null;
  size_bytes: number | null;
  uploaded_at: string;
};

export type SupplierProductRead = {
  id: number;
  tjx_style: string | null;
  description: string | null;
  pcs_per_crt: number | null;
  purchase_cost_eur: number | null;
  sale_price_eur: number | null;
};

export type ProductImportResponse = {
  file_name: string;
  imported_at: string;
  total_rows_read: number;
  inserted_count: number;
  updated_count: number;
  skipped_count: number;
  warnings: string[];
};

export type SupplierImportResponse = {
  file_name: string;
  imported_at: string;
  total_rows_read: number;
  inserted_count: number;
  updated_count: number;
  skipped_count: number;
  warnings: string[];
};

export type AuthUser = {
  id: number;
  username: string;
  full_name: string;
  role: "admin" | "operatore" | "viewer";
};

export type AuditLogRead = {
  id: number;
  user_id: number | null;
  username: string | null;
  method: string;
  path: string;
  payload_json: string | null;
  created_at: string;
};
