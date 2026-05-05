"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import type {
  ActiveOrderDashboardRow,
  DocumentOption,
  LogisticsDcSummary,
  OrderLogisticsSummary,
  OrderDetail,
  OrderDocument,
  OrderDocumentOptions,
  OrderLine,
  OrderPackingList,
  PackingListBatch,
  ProductRead,
  PurchaseOrderPreview,
} from "@/lib/api/types";
import { formatDate, formatDateTime, sum, uniq } from "@/lib/utils/format";
import { StatusBadge } from "@/components/ui/StatusBadge";

type Mode = "received" | "operational";

type DraftMap = Record<number, { total?: number; byDc: Record<string, number> }>;
type IdentityDraftMap = Record<number, string>;

type ItemRow = {
  line: OrderLine;
  line_id: number;
  vendor_style: string;
  description: string;
  nest_code: string;
  master_carton: number | null;
  unit_cost: number | null;
  unit_price: number | null;
  qty_by_dc: Record<string, number>;
  total_pieces: number;
  total_cartons: number | null;
};

type DcLogisticRow = {
  dc_code: string;
  total_pieces: number | null;
  total_cartons: number | null;
  total_cubic_meters: number | null;
  total_gross_weight: number | null;
  total_net_weight: number | null;
  pallets: number | null;
  invoice_number: string | null;
  document_date: string | null;
  packing_list_id: number | null;
};

type EmailDraftResponse = {
  to: string;
  cc: string[];
  subject: string;
  body: string;
  attachments: string[];
};

async function callApi<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/backend/${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  if (!res.ok) throw new Error(data.detail || `${res.status} ${res.statusText}`);
  return data as T;
}

function styleKey(value: string | null | undefined): string {
  return (value || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
}

function formatNumber(value: number | null | undefined, decimals = 0): string {
  if (value === null || value === undefined) return "-";
  return value.toLocaleString("it-IT", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return value.toLocaleString("it-IT", { style: "currency", currency: "EUR" });
}

function formatDecimalInput(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) return "";
  return Number(value).toLocaleString("it-IT", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function statusTone(status: ActiveOrderDashboardRow["order_status"] | undefined): "ok" | "warn" | "err" {
  if (status === "In ritardo") return "err";
  if (status === "Programmato") return "warn";
  return "ok";
}

export function OrderDetailClient({ initial }: { initial: OrderDetail }) {
  const [order, setOrder] = useState<OrderDetail>(initial);
  const [products, setProducts] = useState<ProductRead[]>([]);
  const [documents, setDocuments] = useState<OrderDocument[]>([]);
  const [packingLists, setPackingLists] = useState<OrderPackingList[]>([]);
  const [logisticsSummary, setLogisticsSummary] = useState<OrderLogisticsSummary | null>(null);
  const [poPreview, setPoPreview] = useState<PurchaseOrderPreview | null>(null);
  const [statusInfo, setStatusInfo] = useState<Pick<ActiveOrderDashboardRow, "order_status"> | null>(null);
  const [documentOptions, setDocumentOptions] = useState<OrderDocumentOptions | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [savingReceived, setSavingReceived] = useState(false);
  const [savingOperational, setSavingOperational] = useState(false);

  const [receivedDraft, setReceivedDraft] = useState<DraftMap>({});
  const [operationalDraft, setOperationalDraft] = useState<DraftMap>({});
  const [vendorStyleDraft, setVendorStyleDraft] = useState<IdentityDraftMap>({});
  const [nestCodeDraft, setNestCodeDraft] = useState<IdentityDraftMap>({});
  const [manualNestEnabled, setManualNestEnabled] = useState(false);
  const [commonInvoiceDate, setCommonInvoiceDate] = useState("");
  const [progressiveInvoiceSeed, setProgressiveInvoiceSeed] = useState("");
  const [orderDocFormat, setOrderDocFormat] = useState("pdf");
  const [dcDocSelection, setDcDocSelection] = useState<Record<string, { documentType: string; format: string }>>({});

  const fallbackDc = order.distribution_center || "QTY";

  const productMap = useMemo(() => {
    const out: Record<string, ProductRead> = {};
    for (const p of products) {
      if (p.tjx_style_key) out[p.tjx_style_key] = p;
    }
    return out;
  }, [products]);

  const inferredDocFlags = useMemo(() => {
    let hasSfarinati = false;
    let hasP2 = false;
    for (const line of order.lines) {
      const keys = [styleKey(line.vendor_style), styleKey(line.item_code)].filter(Boolean);
      const product = keys.map((k) => productMap[k]).find(Boolean);
      if (!product) continue;
      if (product.document_sfarinati) hasSfarinati = true;
      if (product.document_p2) hasP2 = true;
      if (hasSfarinati && hasP2) break;
    }
    return { hasSfarinati, hasP2 };
  }, [order.lines, productMap]);

  const fallbackDcDocOptions = useMemo<DocumentOption[]>(() => {
    const hasSfarinatiFlag = documentOptions?.has_sfarinati ?? inferredDocFlags.hasSfarinati;
    const hasP2Flag = documentOptions?.has_p2 ?? inferredDocFlags.hasP2;
    const options: DocumentOption[] = [
      {
        document_type: "packing_list",
        label: "Packing List",
        level: "DC",
        enabled: true,
        formats: ["pdf", "excel"],
        reason: null,
      },
      {
        document_type: "dle",
        label: "DLE",
        level: "DC",
        enabled: false,
        formats: [],
        reason: "Generatore DLE non ancora disponibile nel backend.",
      },
    ];
    if (hasSfarinatiFlag) {
      options.push({
        document_type: "sfarinati",
        label: "Sfarinati",
        level: "DC",
        enabled: false,
        formats: [],
        reason: "Generatore Sfarinati non ancora disponibile nel backend.",
      });
    }
    if (hasP2Flag) {
      options.push({
        document_type: "p2",
        label: "P2",
        level: "DC",
        enabled: false,
        formats: [],
        reason: "Generatore P2 non ancora disponibile nel backend.",
      });
    }
    return options;
  }, [documentOptions?.has_p2, documentOptions?.has_sfarinati, inferredDocFlags.hasP2, inferredDocFlags.hasSfarinati]);

  const dcColumns = useMemo(() => {
    const all = order.lines.flatMap((l) => [
      ...Object.keys(l.original_units_per_dc || {}),
      ...Object.keys(l.operational_units_per_dc || {}),
    ]);
    const unique = uniq(all).sort();
    return unique.length > 0 ? unique : [fallbackDc];
  }, [order.lines, fallbackDc]);

  const dcCardCodes = useMemo(() => {
    const fromLogistics = (logisticsSummary?.operational.dcs || [])
      .map((d) => d.dc_code)
      .filter((x) => !!x && x.trim() !== "");
    if (fromLogistics.length > 0) return uniq(fromLogistics).sort();

    const fromPacking = (packingLists || [])
      .map((p) => p.dc_code || "")
      .filter((x) => !!x && x.trim() !== "");
    if (fromPacking.length > 0) return uniq(fromPacking).sort();

    const fromDocOptions = (documentOptions?.dc_level_options || [])
      .map((d) => d.dc_code)
      .filter((x) => !!x && x.trim() !== "");
    if (fromDocOptions.length > 0) return uniq(fromDocOptions).sort();

    return [] as string[];
  }, [logisticsSummary, packingLists, documentOptions]);

  function lineQtyMap(line: OrderLine, mode: Mode): Record<string, number> {
    const source = mode === "received" ? line.original_units_per_dc : line.operational_units_per_dc;
    if (source && Object.keys(source).length > 0) {
      const out: Record<string, number> = {};
      for (const [dc, qty] of Object.entries(source)) out[dc] = Number(qty || 0);
      return out;
    }
    const fallbackQty = mode === "received"
      ? Number(line.original_units ?? line.total_units ?? 0)
      : Number(line.operational_units ?? line.total_units ?? 0);
    return { [fallbackDc]: fallbackQty };
  }

  function draftValue(mode: Mode, lineId: number, dc: string, fallback: number): number {
    const draft = mode === "received" ? receivedDraft[lineId] : operationalDraft[lineId];
    if (!draft) return fallback;
    if (draft.byDc[dc] !== undefined) return draft.byDc[dc];
    return fallback;
  }

  function lineCartonsFromSummary(mode: Mode, lineId: number): number | null {
    const scope = mode === "received" ? logisticsSummary?.received : logisticsSummary?.operational;
    if (!scope) return null;
    let cartons = 0;
    let found = false;
    for (const dc of scope.dcs) {
      for (const g of dc.groups) {
        for (const p of g.products) {
          if (Number(p.line_id) === Number(lineId)) {
            cartons += p.cartons;
            found = true;
          }
        }
      }
    }
    return found ? cartons : null;
  }

  const buildRows = (mode: Mode): ItemRow[] => {
    return order.lines
      .map((line) => {
        const effectiveStyle = vendorStyleDraft[line.id] ?? line.vendor_style;
        const effectiveNest = nestCodeDraft[line.id] ?? line.nest_code ?? "MONO";
        const p = productMap[styleKey(effectiveStyle)];
        const master = line.vend_pack ?? p?.pcs_per_crt ?? null;
        const baseMap = lineQtyMap(line, mode);
        const qtyMap: Record<string, number> = {};
        for (const dc of dcColumns) {
          qtyMap[dc] = draftValue(mode, line.id, dc, Number(baseMap[dc] || 0));
        }
        const totalPieces = sum(Object.values(qtyMap));
        const summaryCartons = lineCartonsFromSummary(mode, line.id);
        let fallbackCartons: number | null = null;
        if (summaryCartons === null && master && master > 0 && totalPieces >= 0 && totalPieces % master === 0) {
          fallbackCartons = totalPieces / master;
        }
        const totalCartons = summaryCartons ?? fallbackCartons;
        return {
          line,
          line_id: line.id,
          vendor_style: effectiveStyle ?? "",
          description: line.description || "-",
          nest_code: effectiveNest || "MONO",
          master_carton: master,
          unit_cost: p?.purchase_cost_eur ?? null,
          unit_price: p?.sale_price_eur ?? null,
          qty_by_dc: qtyMap,
          total_pieces: totalPieces,
          total_cartons: totalCartons,
        };
      })
      .sort((a, b) => (a.nest_code || "").localeCompare(b.nest_code || "") || a.vendor_style.localeCompare(b.vendor_style));
  };

  const receivedRows = useMemo(() => buildRows("received"), [order.lines, products, receivedDraft, dcColumns, logisticsSummary, vendorStyleDraft, nestCodeDraft]);
  const operationalRows = useMemo(() => buildRows("operational"), [order.lines, products, operationalDraft, dcColumns, logisticsSummary, vendorStyleDraft, nestCodeDraft]);

  const groupedReceived = useMemo(
    () => groupByNest(receivedRows, logisticsSummary?.received.dcs || []),
    [receivedRows, logisticsSummary],
  );
  const groupedOperational = useMemo(
    () => groupByNest(operationalRows, logisticsSummary?.operational.dcs || []),
    [operationalRows, logisticsSummary],
  );

  const logisticsByDc = useMemo<DcLogisticRow[]>(() => {
    const opScope = logisticsSummary?.operational;
    const opByDc: Record<string, { pieces: number; cartons: number; volume: number | null; gross: number | null; net: number | null; pallets: number | null }> = {};
    if (opScope) {
      for (const dc of Array.isArray(opScope.dcs) ? opScope.dcs : []) {
        opByDc[dc.dc_code] = {
          pieces: dc.total_pieces,
          cartons: dc.total_cartons,
          volume: dc.total_volume,
          gross: dc.total_gross_weight,
          net: dc.total_net_weight,
          pallets: dc.total_pallets,
        };
      }
    }
    const plMap: Record<string, OrderPackingList> = {};
    for (const p of packingLists) if (p.dc_code) plMap[p.dc_code] = p;

    return dcCardCodes.map((dc) => {
      const pl = plMap[dc];
      const op = opByDc[dc];
      const useManualTotals = !!pl?.totals_manually_overridden;
      return {
        dc_code: dc,
        total_pieces: op?.pieces ?? pl?.total_pieces ?? null,
        total_cartons: op?.cartons ?? pl?.total_cartons ?? null,
        total_cubic_meters: useManualTotals ? (pl?.total_cubic_meters ?? op?.volume ?? null) : (op?.volume ?? pl?.total_cubic_meters ?? null),
        total_gross_weight: useManualTotals ? (pl?.total_gross_weight ?? op?.gross ?? null) : (op?.gross ?? pl?.total_gross_weight ?? null),
        total_net_weight: useManualTotals ? (pl?.total_net_weight ?? op?.net ?? null) : (op?.net ?? pl?.total_net_weight ?? null),
        pallets: useManualTotals ? (pl?.total_pallets ?? op?.pallets ?? null) : (op?.pallets ?? pl?.total_pallets ?? null),
        invoice_number: pl?.invoice_number ?? null,
        document_date: pl?.document_date ?? null,
        packing_list_id: pl?.id ?? null,
      };
    });
  }, [packingLists, dcCardCodes, logisticsSummary]);

  const documentOptionsByDc = useMemo(() => {
    const map: Record<string, DocumentOption[]> = {};
    for (const row of documentOptions?.dc_level_options || []) {
      map[row.dc_code] = row.options;
    }
    return map;
  }, [documentOptions]);

  function getDcDocOptions(dcCode: string): DocumentOption[] {
    const backend = documentOptionsByDc[dcCode] || [];
    if (backend.length === 0) return fallbackDcDocOptions;

    const byType: Record<string, DocumentOption> = {};
    for (const opt of fallbackDcDocOptions) byType[opt.document_type] = opt;
    for (const opt of backend) byType[opt.document_type] = opt;
    return Object.values(byType);
  }

  const recap = useMemo(() => {
    const receivedPieces = logisticsSummary?.received.total_pieces ?? null;
    const receivedCartons = logisticsSummary?.received.total_cartons ?? null;
    const operationalPieces = logisticsSummary?.operational.total_pieces ?? null;
    const operationalCartons = logisticsSummary?.operational.total_cartons ?? null;

    const volume = logisticsSummary?.operational.total_volume ?? null;
    const gross = logisticsSummary?.operational.total_gross_weight ?? null;
    const net = logisticsSummary?.operational.total_net_weight ?? null;
    const pallets = logisticsSummary?.operational.total_pallets ?? null;

    const revenueTotal = receivedRows.reduce((acc, x) => acc + Number((x.unit_price ?? 0) * x.total_pieces), 0);
    const costTotal = operationalRows.reduce((acc, x) => acc + Number((x.unit_cost ?? 0) * x.total_pieces), 0);
    const hasRevenue = receivedRows.some((x) => x.unit_price !== null);
    const hasCost = operationalRows.some((x) => x.unit_cost !== null);
    const margin = hasRevenue || hasCost ? revenueTotal - costTotal : null;
    const marginPct = margin !== null && revenueTotal > 0 ? (margin / revenueTotal) * 100 : null;

    return {
      receivedPieces,
      receivedCartons,
      operationalPieces,
      operationalCartons,
      volume,
      gross,
      net,
      pallets,
      costTotal: hasCost ? costTotal : null,
      revenueTotal: hasRevenue ? revenueTotal : null,
      margin,
      marginPct,
    };
  }, [receivedRows, operationalRows, logisticsSummary]);

  useEffect(() => {
    void refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [order.id]);

  async function refreshAll() {
    try {
      setError(null);
      const [docs, pls, prods, dashboard, logistics, docOpts] = await Promise.all([
        callApi<OrderDocument[]>(`orders/${order.id}/documents`),
        callApi<OrderPackingList[]>(`orders/${order.id}/packing-lists`),
        callApi<ProductRead[]>("products"),
        callApi<ActiveOrderDashboardRow[]>("orders/active-dashboard"),
        callApi<OrderLogisticsSummary>(`orders/${order.id}/logistics-summary`),
        callApi<OrderDocumentOptions>(`orders/${order.id}/documents/options`),
      ]);
      setDocuments(docs);
      setPackingLists(pls);
      setProducts(prods);
      setLogisticsSummary(logistics);
      setDocumentOptions(docOpts);
      setDcDocSelection((prev) => {
        const next: Record<string, { documentType: string; format: string }> = { ...prev };
        for (const row of docOpts.dc_level_options) {
          if (!next[row.dc_code]) {
            const preferred = row.options.find((opt) => opt.document_type === "packing_list") || row.options[0];
            next[row.dc_code] = {
              documentType: preferred?.document_type || "packing_list",
              format: preferred?.formats?.[0] || "pdf",
            };
          }
        }
        return next;
      });
      const current = dashboard.find((x) => x.id === order.id) || null;
      setStatusInfo(current ? { order_status: current.order_status } : null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore caricamento pagina ordine");
    }
  }

  async function refreshOrder() {
    const fresh = await callApi<OrderDetail>(`orders/${order.id}`);
    setOrder(fresh);
  }

  function onQtyChange(mode: Mode, lineId: number, dc: string, value: string) {
    const n = Number(value);
    const safe = Number.isFinite(n) && n >= 0 ? n : 0;
    if (mode === "received") {
      setReceivedDraft((prev) => ({
        ...prev,
        [lineId]: {
          total: prev[lineId]?.total,
          byDc: { ...(prev[lineId]?.byDc || {}), [dc]: safe },
        },
      }));
      return;
    }
    setOperationalDraft((prev) => ({
      ...prev,
      [lineId]: {
        total: prev[lineId]?.total,
        byDc: { ...(prev[lineId]?.byDc || {}), [dc]: safe },
      },
    }));
  }

  function onVendorStyleChange(lineId: number, value: string) {
    setVendorStyleDraft((prev) => ({ ...prev, [lineId]: value.toUpperCase() }));
  }

  function onNestCodeChange(lineId: number, value: string) {
    const normalized = (value || "").toUpperCase().trim();
    setNestCodeDraft((prev) => ({ ...prev, [lineId]: normalized || "MONO" }));
  }

  async function saveTable(mode: Mode) {
    const draft = mode === "received" ? receivedDraft : operationalDraft;
    const hasVendorStyleChanges = Object.entries(vendorStyleDraft).some(([lineId, value]) => {
      const current = order.lines.find((line) => line.id === Number(lineId))?.vendor_style ?? "";
      return (value || "").trim() !== (current || "").trim();
    });
    const hasNestChanges = Object.entries(nestCodeDraft).some(([lineId, value]) => {
      const current = order.lines.find((line) => line.id === Number(lineId))?.nest_code ?? "MONO";
      const currentNorm = (current || "MONO").toUpperCase().trim();
      const nextNorm = (value || "MONO").toUpperCase().trim();
      return currentNorm !== nextNorm;
    });
    if (Object.keys(draft).length === 0 && !hasVendorStyleChanges && !hasNestChanges) return;
    if (mode === "received") setSavingReceived(true);
    if (mode === "operational") setSavingOperational(true);
    setBusy(true);
    setError(null);
    try {
      const identityLineIds = uniq([
        ...Object.keys(vendorStyleDraft).map((x) => Number(x)),
        ...Object.keys(nestCodeDraft).map((x) => Number(x)),
      ]);
      for (const lineId of identityLineIds) {
        const draftStyle = vendorStyleDraft[lineId];
        const draftNest = nestCodeDraft[lineId];
        const line = order.lines.find((x) => x.id === lineId);
        if (!line) continue;
        const nextStyle = (draftStyle || "").trim();
        const currentStyle = (line.vendor_style || "").trim();
        const nextNestNorm = (draftNest || "").trim().toUpperCase();
        const currentNestNorm = ((line.nest_code || "MONO").trim() || "MONO").toUpperCase();
        const styleChanged = !!nextStyle && nextStyle !== currentStyle;
        const nestChanged = !!nextNestNorm && nextNestNorm !== currentNestNorm;
        if (!styleChanged && !nestChanged) continue;
        await callApi(`orders/${order.id}/lines/${lineId}/identity`, {
          method: "PATCH",
          body: JSON.stringify({
            vendor_style: styleChanged ? nextStyle : undefined,
            nest_code: nestChanged ? (nextNestNorm === "MONO" ? null : nextNestNorm) : undefined,
          }),
        });
      }

      for (const line of order.lines) {
        const pending = draft[line.id];
        if (!pending) continue;
        const baseMap = lineQtyMap(line, mode);
        const hasDcMap = Object.keys(baseMap).length > 1 || (Object.keys(baseMap).length === 1 && Object.keys(baseMap)[0] !== fallbackDc);

        if (hasDcMap) {
          for (const [dc, newQty] of Object.entries(pending.byDc)) {
            const oldQty = Number(baseMap[dc] || 0);
            if (newQty === oldQty) continue;
            if (mode === "received") {
              await callApi(`orders/${order.id}/lines/${line.id}/dc/${dc}/original-units`, {
                method: "PATCH",
                body: JSON.stringify({ original_dc_units: newQty }),
              });
            } else {
              await callApi(`orders/${order.id}/lines/${line.id}/dc/${dc}/operational-units`, {
                method: "PATCH",
                body: JSON.stringify({ operational_dc_units: newQty }),
              });
            }
          }
        } else {
          const dc = Object.keys(baseMap)[0] || fallbackDc;
          const newQty = pending.byDc[dc];
          if (newQty === undefined) continue;
          const oldQty = Number(baseMap[dc] || 0);
          if (newQty === oldQty) continue;
          if (mode === "received") {
            await callApi(`orders/${order.id}/lines/${line.id}/original-units`, {
              method: "PATCH",
              body: JSON.stringify({ original_units: newQty }),
            });
          } else {
            await callApi(`orders/${order.id}/lines/${line.id}/operational-units`, {
              method: "PATCH",
              body: JSON.stringify({ operational_units: newQty }),
            });
          }
        }
      }

      const updated = await callApi<OrderDetail>(`orders/${order.id}`);
      setOrder(updated);
      if (mode === "received") setReceivedDraft({});
      if (mode === "operational") setOperationalDraft({});
      setVendorStyleDraft({});
      setNestCodeDraft({});
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore salvataggio tabella");
    } finally {
      setBusy(false);
      if (mode === "received") setSavingReceived(false);
      if (mode === "operational") setSavingOperational(false);
    }
  }

  async function ensurePackingData() {
    let poId = poPreview?.id;
    if (!poId) {
      const po = await callApi<PurchaseOrderPreview>("purchase-orders/preview", {
        method: "POST",
        body: JSON.stringify({ customer_order_id: order.id, adjustment_percent: 2 }),
      });
      setPoPreview(po);
      poId = po.id;
    }

    await callApi<PackingListBatch>("packing-lists/preview", {
      method: "POST",
      body: JSON.stringify({ purchase_order_id: poId }),
    });
    await refreshAll();
  }

  async function generateOrderSupplierDocument() {
    setBusy(true);
    setError(null);
    try {
      await callApi<OrderDocument[]>(`orders/${order.id}/documents/generate-item`, {
        method: "POST",
        body: JSON.stringify({
          level: "ORDER",
          document_type: "purchase_order",
          format: orderDocFormat,
        }),
      });
      const po = await callApi<PurchaseOrderPreview>("purchase-orders/preview", {
        method: "POST",
        body: JSON.stringify({ customer_order_id: order.id, adjustment_percent: 2 }),
      });
      setPoPreview(po);
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore generazione ordine fornitore");
    } finally {
      setBusy(false);
    }
  }

  async function sendOrderToSupplier() {
    setBusy(true);
    setError(null);
    try {
      let poId = poPreview?.id;
      if (!poId) {
        const po = await callApi<PurchaseOrderPreview>("purchase-orders/preview", {
          method: "POST",
          body: JSON.stringify({ customer_order_id: order.id, adjustment_percent: 2 }),
        });
        setPoPreview(po);
        poId = po.id;
      }

      await callApi(`purchase-orders/${poId}/pdf`, { method: "POST" });
      const draft = await callApi<EmailDraftResponse>(`email/prepare/${poId}`, { method: "POST" });

      const ccAll = Array.from(
        new Set([...(draft.cc || []), "operations@famoritalia.com"].filter((x) => !!x && x.trim() !== ""))
      );
      const encodeMailto = (value: string) => encodeURIComponent(value);
      const qs =
        `to=${encodeMailto(draft.to || "")}` +
        `&cc=${encodeMailto(ccAll.join(";"))}` +
        `&subject=${encodeMailto(draft.subject || "")}` +
        `&body=${encodeMailto(draft.body || "")}`;
      const mailtoUrl = `mailto:?${qs}`;
      window.location.href = mailtoUrl;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore invio ordine a fornitore");
    } finally {
      setBusy(false);
    }
  }

  async function applyAutoIncrease2Percent() {
    setBusy(true);
    setError(null);
    try {
      const updated = await callApi<OrderDetail>(`orders/${order.id}/operational/apply-auto-increase`, {
        method: "POST",
        body: JSON.stringify({ percent: 2.0 }),
      });
      setOrder(updated);
      setOperationalDraft({});
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore applicazione aumento automatico +2%");
    } finally {
      setBusy(false);
    }
  }

  async function resetOperationalToOriginal() {
    setBusy(true);
    setError(null);
    try {
      const updated = await callApi<OrderDetail>(`orders/${order.id}/operational/reset-to-original`, {
        method: "POST",
      });
      setOrder(updated);
      setOperationalDraft({});
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore ripristino quantità operative");
    } finally {
      setBusy(false);
    }
  }

  async function resetReceivedToImported() {
    const confirmed = window.confirm("Ripristinare le quantità ordine ricevuto ai valori originali di import?");
    if (!confirmed) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await callApi<OrderDetail>(`orders/${order.id}/received/reset-to-imported`, {
        method: "POST",
      });
      setOrder(updated);
      setReceivedDraft({});
      setVendorStyleDraft({});
      setNestCodeDraft({});
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore ripristino ordine originale");
    } finally {
      setBusy(false);
    }
  }

  async function normalizeReceivedQuantities() {
    const confirmed = window.confirm(
      "Aggiustare le quantità ordine ricevuto ai multipli corretti (master/store-ready), il più vicino possibile?"
    );
    if (!confirmed) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await callApi<OrderDetail>(`orders/${order.id}/received/normalize-quantities`, {
        method: "POST",
      });
      setOrder(updated);
      setReceivedDraft({});
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore aggiustamento quantità ordine");
    } finally {
      setBusy(false);
    }
  }

  async function generateDcDocument(dcCode: string) {
    const selection = dcDocSelection[dcCode];
    if (!selection) return;
    setBusy(true);
    setError(null);
    try {
      await callApi<OrderDocument[]>(`orders/${order.id}/documents/generate-item`, {
        method: "POST",
        body: JSON.stringify({
          level: "DC",
          dc_code: dcCode,
          document_type: selection.documentType,
          format: selection.format,
        }),
      });
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : `Errore generazione documento DC ${dcCode}`);
    } finally {
      setBusy(false);
    }
  }

  async function applyCommonDateToAllDc() {
    if (!commonInvoiceDate) return;
    setBusy(true);
    setError(null);
    try {
      await ensurePackingData();
      const rows = await callApi<OrderPackingList[]>(`orders/${order.id}/packing-lists`);
      for (const pl of rows) {
        await callApi(`packing-lists/${pl.id}`, {
          method: "PATCH",
          body: JSON.stringify({ document_date: commonInvoiceDate }),
        });
      }
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore applicazione data fattura comune");
    } finally {
      setBusy(false);
    }
  }

  function parseProgressiveInvoiceSeed(value: string): { start: number; year: string } | null {
    const match = value.match(/^\s*(\d{1,5})\s*\/\s*EM\s*\/\s*(\d{4})\s*$/i);
    if (!match) return null;
    const start = Number(match[1]);
    const year = match[2];
    if (!Number.isFinite(start) || start <= 0) return null;
    return { start, year };
  }

  async function applyProgressiveInvoiceNumbers(seedRaw: string) {
    const parsed = parseProgressiveInvoiceSeed(seedRaw);
    if (!parsed) {
      setError("Formato numero fattura progressivo non valido. Usa: 378/EM/2026");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await ensurePackingData();
      const rows = await callApi<OrderPackingList[]>(`orders/${order.id}/packing-lists`);
      const byDc = new Map(rows.map((r) => [r.dc_code || "", r]));
      const orderedRows = dcCardCodes
        .map((dc) => byDc.get(dc))
        .filter((x): x is OrderPackingList => !!x && !!x.id);

      for (let i = 0; i < orderedRows.length; i++) {
        const row = orderedRows[i];
        const invoiceNumber = `${parsed.start + i}/EM/${parsed.year}`;
        await callApi(`packing-lists/${row.id}`, {
          method: "PATCH",
          body: JSON.stringify({ invoice_number: invoiceNumber }),
        });
      }
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore applicazione numero fattura progressivo");
    } finally {
      setBusy(false);
    }
  }

  async function saveDcInvoice(
    dc: string,
    invoice: string,
    dateValue: string | null,
    totals: { gross: number | null; net: number | null; volume: number | null; pallets: number | null },
  ) {
    setBusy(true);
    setError(null);
    try {
      let target = logisticsByDc.find((x) => x.dc_code === dc) || null;
      if (!target?.packing_list_id) {
        await ensurePackingData();
        const rows = await callApi<OrderPackingList[]>(`orders/${order.id}/packing-lists`);
        const found = rows.find((x) => x.dc_code === dc) || null;
        target = found
          ? {
              dc_code: found.dc_code || dc,
              total_pieces: found.total_pieces,
              total_cartons: found.total_cartons,
              total_cubic_meters: found.total_cubic_meters,
              total_gross_weight: found.total_gross_weight,
              total_net_weight: found.total_net_weight,
              pallets: found.total_pallets,
              invoice_number: found.invoice_number,
              document_date: found.document_date,
              packing_list_id: found.id,
            }
          : null;
      }
      if (!target?.packing_list_id) throw new Error(`Packing list non trovata per DC ${dc}`);
      await callApi(`packing-lists/${target.packing_list_id}`, {
        method: "PATCH",
        body: JSON.stringify({
          invoice_number: invoice || null,
          document_date: dateValue || null,
          total_gross_weight: totals.gross,
          total_net_weight: totals.net,
          total_cubic_meters: totals.volume,
          total_pallets: totals.pallets,
        }),
      });
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore salvataggio fattura DC");
    } finally {
      setBusy(false);
    }
  }

  async function resetDcTotalsToCalculated() {
    setBusy(true);
    setError(null);
    try {
      await callApi<OrderPackingList[]>(`orders/${order.id}/packing-lists/reset-calculated`, {
        method: "POST",
      });
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore ripristino totali DC calcolati");
    } finally {
      setBusy(false);
    }
  }

  async function toggleArchive() {
    setBusy(true);
    setError(null);
    try {
      const updated = await callApi<OrderDetail>(`orders/${order.id}/archive`, {
        method: "PATCH",
        body: JSON.stringify({ is_archived: !order.is_archived }),
      });
      setOrder(updated);
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore aggiornamento stato ordine");
    } finally {
      setBusy(false);
    }
  }

  async function deleteOrder() {
    const confirmed = window.confirm("Sei sicuro di voler eliminare definitivamente questo ordine?");
    if (!confirmed) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/backend/orders/${order.id}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const text = await res.text();
        const payload = text ? JSON.parse(text) : {};
        throw new Error(payload?.detail || "Errore eliminazione ordine");
      }
      window.location.href = "/dashboard";
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore eliminazione ordine");
      setBusy(false);
    }
  }

  return (
    <div className="order-page">
      <section className="panel order-header">
        <div className="order-header-top">
          <h1>Dettaglio Ordine PO {order.po_normalized || order.po_raw || "-"}</h1>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="btn" onClick={refreshOrder} disabled={busy}>Aggiorna</button>
            <button className="btn" onClick={toggleArchive} disabled={busy}>
              {order.is_archived ? "Riporta da spedire" : "Segna spedito"}
            </button>
            <button className="btn" onClick={deleteOrder} disabled={busy}>Elimina ordine</button>
          </div>
        </div>
        <div className="order-head-grid">
          <InfoCell label="PO" value={order.po_normalized || order.po_raw || "-"} />
          <InfoCell label="Customer" value={order.brand || "-"} />
          <InfoCell label="Fornitore" value={order.supplier || "-"} />
          <InfoCell label="Start Ship Date" value={formatDate(order.start_ship_date)} />
          <InfoCell label="Cancel Date" value={formatDate(order.cancel_ship_date)} />
          <InfoCell
            label="Stato"
            value={<StatusBadge tone={statusTone(statusInfo?.order_status)} label={statusInfo?.order_status || "Pronto al ritiro"} />}
          />
        </div>
      </section>

      {error ? <div className="panel"><StatusBadge tone="err" label={error} /></div> : null}

      <section className="panel">
        <div className="order-header-top">
          <h3 style={{ margin: 0 }}>Ordine ricevuto</h3>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <button className="btn" onClick={resetReceivedToImported} disabled={busy}>
              Ripristina ordine originale
            </button>
            <button className="btn" onClick={normalizeReceivedQuantities} disabled={busy}>
              Aggiusta qty ordine
            </button>
            <label className="muted" style={{ fontSize: 13, display: "inline-flex", alignItems: "center", gap: 6 }}>
              <input
                type="checkbox"
                checked={manualNestEnabled}
                onChange={(e) => setManualNestEnabled(e.target.checked)}
              />
              Nest manuali
            </label>
            <button className="btn primary" onClick={() => void saveTable("received")} disabled={busy || savingReceived}>
              {savingReceived ? "Salvataggio..." : "Salva modifiche"}
            </button>
          </div>
        </div>
        <ItemsTable
          mode="received"
          groups={groupedReceived}
          dcColumns={dcColumns}
          nestEditable={manualNestEnabled}
          onVendorStyleChange={onVendorStyleChange}
          onNestCodeChange={onNestCodeChange}
          onQtyChange={(lineId, dc, v) => onQtyChange("received", lineId, dc, v)}
        />
      </section>

      <section className="panel">
        <div className="order-header-top">
          <h3 style={{ margin: 0 }}>Ordine da inviare al fornitore</h3>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <button className="btn" onClick={applyAutoIncrease2Percent} disabled={busy}>
              Applica aumento automatico +2%
            </button>
            <button className="btn" onClick={resetOperationalToOriginal} disabled={busy}>
              Ripristina = ordine cliente
            </button>
            <button className="btn primary" onClick={() => void saveTable("operational")} disabled={busy || savingOperational}>
              {savingOperational ? "Salvataggio..." : "Salva modifiche"}
            </button>
            <label className="muted" style={{ fontSize: 12 }}>Formato</label>
            <select
              className="input"
              value={orderDocFormat}
              onChange={(e) => setOrderDocFormat(e.target.value)}
              style={{ width: 110 }}
            >
              <option value="pdf">PDF</option>
              <option value="excel">Excel</option>
            </select>
            <button className="btn" onClick={generateOrderSupplierDocument} disabled={busy}>
              Genera ordine fornitore
            </button>
            <button className="btn" onClick={sendOrderToSupplier} disabled={busy}>
              Invia ordine a fornitore
            </button>
          </div>
        </div>
        <ItemsTable
          mode="operational"
          groups={groupedOperational}
          dcColumns={dcColumns}
          nestEditable={manualNestEnabled}
          onVendorStyleChange={onVendorStyleChange}
          onNestCodeChange={onNestCodeChange}
          onQtyChange={(lineId, dc, v) => onQtyChange("operational", lineId, dc, v)}
        />
      </section>

      <section className="panel">
        <h3>Recap logistico ordine</h3>
        <div className="cards" style={{ gridTemplateColumns: "repeat(3, minmax(120px, 1fr))" }}>
          <MetricCard label="Totale pezzi" value={formatNumber(recap.operationalPieces)} />
          <MetricCard label="Totale cartoni" value={formatNumber(recap.operationalCartons)} />
          <MetricCard label="Volume totale" value={recap.volume !== null ? `${formatNumber(recap.volume, 3)} m³` : "-"} />
          <MetricCard label="Peso lordo totale" value={recap.gross !== null ? `${formatNumber(recap.gross, 2)} kg` : "-"} />
          <MetricCard label="Peso netto totale" value={recap.net !== null ? `${formatNumber(recap.net, 2)} kg` : "-"} />
          <MetricCard label="Pallets totali" value={formatNumber(recap.pallets)} />
        </div>
      </section>

      <section className="panel">
        <h3>Recap economico ordine</h3>
        <div className="cards" style={{ gridTemplateColumns: "repeat(4, minmax(120px, 1fr))" }}>
          <MetricCard label="Costo totale acquisto" value={formatCurrency(recap.costTotal)} />
          <MetricCard label="Ricavo totale vendita" value={formatCurrency(recap.revenueTotal)} />
          <MetricCard label="Margine totale" value={formatCurrency(recap.margin)} />
          <MetricCard label="Margine %" value={recap.marginPct !== null ? `${formatNumber(recap.marginPct, 2)}%` : "-"} />
        </div>
      </section>

      <section className="panel">
        <h3>Riepilogo per DC</h3>
        <div style={{ display: "flex", alignItems: "end", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
          <div style={{ minWidth: 220 }}>
            <label className="muted" style={{ display: "block", marginBottom: 4 }}>Data fattura comune</label>
            <input className="input" type="date" value={commonInvoiceDate} onChange={(e) => setCommonInvoiceDate(e.target.value)} />
          </div>
          <button className="btn" style={{ minWidth: 170 }} disabled={busy || !commonInvoiceDate} onClick={() => void applyCommonDateToAllDc()}>
            Applica data a tutti i DC
          </button>
          <div style={{ minWidth: 240 }}>
            <label className="muted" style={{ display: "block", marginBottom: 4 }}>Numero fattura progressivo</label>
            <input
              className="input"
              type="text"
              placeholder="es. 378/EM/2026"
              value={progressiveInvoiceSeed}
              onChange={(e) => setProgressiveInvoiceSeed(e.target.value)}
              onBlur={() => {
                if (progressiveInvoiceSeed.trim()) {
                  void applyProgressiveInvoiceNumbers(progressiveInvoiceSeed.trim());
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && progressiveInvoiceSeed.trim()) {
                  e.preventDefault();
                  void applyProgressiveInvoiceNumbers(progressiveInvoiceSeed.trim());
                }
              }}
            />
          </div>
          <a className="btn" style={{ minWidth: 170, textAlign: "center" }} href={`/api/backend/orders/${order.id}/documents/download-all?format=pdf`}>
            Scarica tutto PDF
          </a>
          <a className="btn" style={{ minWidth: 170, textAlign: "center" }} href={`/api/backend/orders/${order.id}/documents/download-all?format=excel`}>
            Scarica tutto Excel
          </a>
          <button className="btn" style={{ minWidth: 210 }} disabled={busy} onClick={() => void resetDcTotalsToCalculated()}>
            Ripristina totali calcolati
          </button>
        </div>
        {logisticsByDc.length === 0 ? (
          <div className="card">
            <div className="k">Riepilogo DC</div>
            <div className="v" style={{ fontSize: 15, fontWeight: 500 }}>
              Nessun Distribution Center disponibile per questo ordine.
            </div>
            <p className="muted" style={{ marginTop: 6, marginBottom: 0 }}>
              Il documento non contiene una distribuzione per DC: vengono mantenute solo le azioni a livello ordine/PO.
            </p>
          </div>
        ) : (
          <div className="dc-grid">
            {logisticsByDc.map((dc) => (
        <DcCard
                key={dc.dc_code}
              row={dc}
              busy={busy}
          onSave={saveDcInvoice}
              docOptions={getDcDocOptions(dc.dc_code)}
              docSelection={dcDocSelection[dc.dc_code] || { documentType: "packing_list", format: "pdf" }}
              onDocSelectionChange={(next) =>
                setDcDocSelection((prev) => ({ ...prev, [dc.dc_code]: next }))
              }
              onGenerateDocument={() => generateDcDocument(dc.dc_code)}
              />
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <div className="order-header-top">
          <h3 style={{ margin: 0 }}>Documenti</h3>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Tipo documento</th>
                <th>Livello</th>
                <th>DC</th>
                <th>Formato</th>
                <th>Nome file</th>
                <th>Data generazione</th>
                <th>Azioni</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc, idx) => {
                const openHref = `/api/backend/files/download?path=${encodeURIComponent(doc.file_path)}&disposition=inline`;
                const downloadHref = `/api/backend/files/download?path=${encodeURIComponent(doc.file_path)}&disposition=attachment`;
                return (
                  <tr key={`${doc.file_path}-${idx}`}>
                    <td>{doc.document_type}</td>
                    <td>{doc.level}</td>
                    <td>{doc.dc_code || "-"}</td>
                    <td>{doc.format.toUpperCase()}</td>
                    <td>{doc.file_name}</td>
                    <td>{formatDateTime(doc.generated_at)}</td>
                    <td>
                      <div style={{ display: "flex", gap: 8 }}>
                        <a className="btn" href={openHref} target="_blank" rel="noreferrer">Apri</a>
                        <a className="btn" href={downloadHref}>Scarica</a>
                      </div>
                    </td>
                  </tr>
                );
              })}
              {documents.length === 0 ? (
                <tr><td colSpan={7} className="muted">Nessun documento disponibile.</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function groupByNest(
  rows: ItemRow[],
  dcSummaries: LogisticsDcSummary[],
): Array<{ nest: string; rows: ItemRow[]; cartons: number | null; pieces: number | null; warnings: string[] }> {
  const aggregateByNest: Record<string, { cartons: number; pieces: number; warnings: string[] }> = {};
  for (const dc of Array.isArray(dcSummaries) ? dcSummaries : []) {
    for (const g of Array.isArray(dc.groups) ? dc.groups : []) {
      const key = g.nest_code || "MONO";
      if (!aggregateByNest[key]) {
        aggregateByNest[key] = { cartons: 0, pieces: 0, warnings: [] };
      }
      aggregateByNest[key].cartons += g.cartons;
      aggregateByNest[key].pieces += (Array.isArray(g.products) ? g.products : []).reduce((acc, product) => acc + product.units, 0);
      for (const w of Array.isArray(g.warnings) ? g.warnings : []) {
        const msg = typeof w?.message === "string" ? w.message : null;
        if (msg && !aggregateByNest[key].warnings.includes(msg)) {
          aggregateByNest[key].warnings.push(msg);
        }
      }
    }
  }

  const map: Record<string, ItemRow[]> = {};
  for (const row of rows) {
    const key = row.nest_code || "MONO";
    if (!map[key]) map[key] = [];
    map[key].push(row);
  }
  return Object.keys(map)
    .sort()
    .map((key) => ({
      nest: key,
      rows: map[key],
      cartons: aggregateByNest[key]?.cartons ?? null,
      pieces: aggregateByNest[key]?.pieces ?? null,
      warnings: aggregateByNest[key]?.warnings ?? [],
    }));
}

function ItemsTable({
  mode,
  groups,
  dcColumns,
  nestEditable,
  onVendorStyleChange,
  onNestCodeChange,
  onQtyChange,
}: {
  mode: Mode;
  groups: Array<{ nest: string; rows: ItemRow[]; cartons: number | null; pieces: number | null; warnings: string[] }>;
  dcColumns: string[];
  nestEditable: boolean;
  onVendorStyleChange: (lineId: number, value: string) => void;
  onNestCodeChange: (lineId: number, value: string) => void;
  onQtyChange: (lineId: number, dc: string, value: string) => void;
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Vendor Style</th>
            <th>Master Carton</th>
            <th>Descrizione</th>
            <th>Nest Code</th>
            {dcColumns.map((dc) => <th key={`${mode}-h-${dc}`}>{dc}</th>)}
            <th>Totale PCS / prodotto</th>
            <th>Totale CS / prodotto</th>
            {mode === "received" ? (
              <>
                <th>Prezzo vendita unitario</th>
                <th>Ricavo totale</th>
              </>
            ) : (
              <>
                <th>Costo unitario</th>
                <th>Costo totale</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {groups.map((group) => (
            <NestedGroupRows
              key={`${mode}-${group.nest}`}
              mode={mode}
              group={group}
              dcColumns={dcColumns}
              nestEditable={nestEditable}
              onVendorStyleChange={onVendorStyleChange}
              onNestCodeChange={onNestCodeChange}
              onQtyChange={onQtyChange}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function NestedGroupRows({
  mode,
  group,
  dcColumns,
  nestEditable,
  onVendorStyleChange,
  onNestCodeChange,
  onQtyChange,
}: {
  mode: Mode;
  group: { nest: string; rows: ItemRow[]; cartons: number | null; pieces: number | null; warnings: string[] };
  dcColumns: string[];
  nestEditable: boolean;
  onVendorStyleChange: (lineId: number, value: string) => void;
  onNestCodeChange: (lineId: number, value: string) => void;
  onQtyChange: (lineId: number, dc: string, value: string) => void;
}) {
  const groupPieces = group.pieces;
  const groupCartons = group.cartons;
  const isNestedGroup = group.nest !== "MONO" && group.rows.length > 1;

  return (
    <>
      <tr className="row-preview">
        <td colSpan={4 + dcColumns.length + 4}>
          <b>Gruppo Nest: {group.nest}</b>
          <span className="muted" style={{ marginLeft: 12 }}>
            PCS gruppo: {formatNumber(groupPieces)} | CS gruppo: {formatNumber(groupCartons)}
          </span>
          {group.nest !== "MONO" && group.warnings.length > 0 ? (
            <span
              style={{
                marginLeft: 12,
                display: "inline-flex",
                alignItems: "center",
                padding: "2px 8px",
                borderRadius: 999,
                fontSize: 12,
                fontWeight: 600,
                background: "#fff6e9",
                color: "#b54708",
                border: "1px solid #f7d89f",
              }}
              title={group.warnings.join(" | ")}
            >
              Attenzione dati gruppo
            </span>
          ) : null}
        </td>
      </tr>
      {group.rows.map((row, index) => {
        const lineRevenue = row.unit_price !== null ? row.unit_price * row.total_pieces : null;
        const lineCost = row.unit_cost !== null ? row.unit_cost * row.total_pieces : null;
        const rowCartons = isNestedGroup ? (index === 0 ? groupCartons : null) : row.total_cartons;
        return (
          <tr key={`${mode}-${row.line_id}`}>
            <td style={{ fontWeight: 600 }}>
              <input
                className="input"
                style={{ maxWidth: 170, padding: "6px 8px", fontWeight: 600 }}
                value={row.vendor_style || ""}
                onChange={(e) => onVendorStyleChange(row.line_id, e.target.value)}
              />
            </td>
            <td>{formatNumber(row.master_carton)}</td>
            <td>{row.description}</td>
            <td>
              {nestEditable ? (
                <input
                  className="input"
                  style={{ maxWidth: 90, padding: "6px 8px", textTransform: "uppercase" }}
                  value={row.nest_code || "MONO"}
                  onChange={(e) => onNestCodeChange(row.line_id, e.target.value)}
                  placeholder="MONO/A..."
                />
              ) : (
                row.nest_code
              )}
            </td>
            {dcColumns.map((dc) => (
              <td key={`${mode}-${row.line_id}-${dc}`}>
                <input
                  className="input"
                  style={{ maxWidth: 80, padding: "6px 8px" }}
                  type="number"
                  min={0}
                  value={row.qty_by_dc[dc] || 0}
                  onChange={(e) => onQtyChange(row.line_id, dc, e.target.value)}
                />
              </td>
            ))}
            <td>{formatNumber(row.total_pieces)}</td>
            <td>{formatNumber(rowCartons)}</td>
            {mode === "received" ? (
              <>
                <td>{formatCurrency(row.unit_price)}</td>
                <td>{formatCurrency(lineRevenue)}</td>
              </>
            ) : (
              <>
                <td>{formatCurrency(row.unit_cost)}</td>
                <td>{formatCurrency(lineCost)}</td>
              </>
            )}
          </tr>
        );
      })}
    </>
  );
}

function DcCard({
  row,
  busy,
  onSave,
  docOptions,
  docSelection,
  onDocSelectionChange,
  onGenerateDocument,
}: {
  row: DcLogisticRow;
  busy: boolean;
  onSave: (
    dc: string,
    invoice: string,
    dateValue: string | null,
    totals: { gross: number | null; net: number | null; volume: number | null; pallets: number | null },
  ) => Promise<void>;
  docOptions: DocumentOption[];
  docSelection: { documentType: string; format: string };
  onDocSelectionChange: (next: { documentType: string; format: string }) => void;
  onGenerateDocument: () => Promise<void> | void;
}) {
  const effectiveDocOptions: DocumentOption[] = docOptions.length > 0
    ? docOptions
    : [
        {
          document_type: "packing_list",
          label: "Packing List",
          level: "DC",
          enabled: true,
          formats: ["pdf", "excel"],
          reason: null,
        },
      ];
  const [invoice, setInvoice] = useState(row.invoice_number || "");
  const [docDate, setDocDate] = useState(row.document_date || "");
  const [gross, setGross] = useState(formatDecimalInput(row.total_gross_weight, 2));
  const [net, setNet] = useState(formatDecimalInput(row.total_net_weight, 2));
  const [volume, setVolume] = useState(row.total_cubic_meters !== null ? String(row.total_cubic_meters) : "");
  const [pallets, setPallets] = useState(row.pallets !== null ? String(row.pallets) : "");
  const selectedOption = effectiveDocOptions.find((opt) => opt.document_type === docSelection.documentType) || null;
  const availableFormats = selectedOption?.formats?.length ? selectedOption.formats : [];
  const hasDocOptions = effectiveDocOptions.length > 0;
  const canGenerate = !!selectedOption?.enabled && hasDocOptions;

  useEffect(() => {
    setInvoice(row.invoice_number || "");
    setDocDate(row.document_date || "");
    setGross(formatDecimalInput(row.total_gross_weight, 2));
    setNet(formatDecimalInput(row.total_net_weight, 2));
    setVolume(row.total_cubic_meters !== null ? String(row.total_cubic_meters) : "");
    setPallets(row.pallets !== null ? String(row.pallets) : "");
  }, [row.invoice_number, row.document_date, row.total_gross_weight, row.total_net_weight, row.total_cubic_meters, row.pallets]);

  function parseFloatOrNull(v: string): number | null {
    const normalized = (v || "").replace(",", ".").trim();
    if (!normalized) return null;
    const num = Number(normalized);
    return Number.isFinite(num) ? num : null;
  }

  function parseIntOrNull(v: string): number | null {
    const normalized = (v || "").trim();
    if (!normalized) return null;
    const num = Number(normalized);
    if (!Number.isFinite(num)) return null;
    return Math.max(0, Math.round(num));
  }

  return (
    <div className="panel dc-card">
      <h4 style={{ marginTop: 0, marginBottom: 8 }}>DC {row.dc_code}</h4>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 12 }}>
        <small><span className="muted">Pezzi</span><br /><b>{formatNumber(row.total_pieces)}</b></small>
        <small><span className="muted">Cartoni</span><br /><b>{formatNumber(row.total_cartons)}</b></small>
        <label>
          <span className="muted">Volume (m³)</span>
          <input className="input" type="text" inputMode="decimal" value={volume} onChange={(e) => setVolume(e.target.value)} style={{ marginTop: 4 }} />
        </label>
        <label>
          <span className="muted">Peso lordo (kg)</span>
          <input className="input" type="text" inputMode="decimal" value={gross} onChange={(e) => setGross(e.target.value)} style={{ marginTop: 4 }} />
        </label>
        <label>
          <span className="muted">Peso netto (kg)</span>
          <input className="input" type="text" inputMode="decimal" value={net} onChange={(e) => setNet(e.target.value)} style={{ marginTop: 4 }} />
        </label>
        <label>
          <span className="muted">Pallets</span>
          <input className="input" type="number" min={0} step={1} value={pallets} onChange={(e) => setPallets(e.target.value)} style={{ marginTop: 4 }} />
        </label>
      </div>
      <div style={{ display: "grid", gap: 8 }}>
        <input className="input" placeholder="Numero fattura" value={invoice} onChange={(e) => setInvoice(e.target.value)} />
        <input className="input" type="date" value={docDate} onChange={(e) => setDocDate(e.target.value)} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <select
            className="input"
            value={docSelection.documentType}
            disabled={!hasDocOptions}
            onChange={(e) =>
              onDocSelectionChange({
                documentType: e.target.value,
                format: (effectiveDocOptions.find((x) => x.document_type === e.target.value)?.formats?.[0] || "pdf"),
              })
            }
          >
            {effectiveDocOptions.length === 0 ? (
              <option value="">Nessun documento</option>
            ) : effectiveDocOptions.map((opt) => (
              <option key={opt.document_type} value={opt.document_type}>
                {opt.label}
              </option>
            ))}
          </select>
          <select
            className="input"
            value={docSelection.format}
            disabled={!hasDocOptions}
            onChange={(e) => onDocSelectionChange({ ...docSelection, format: e.target.value })}
          >
            {(availableFormats.length > 0 ? availableFormats : ["pdf"]).map((fmt) => (
              <option key={fmt} value={fmt}>{fmt.toUpperCase()}</option>
            ))}
          </select>
        </div>
        {!hasDocOptions ? (
          <small className="muted">Nessun documento DC disponibile per questo ordine.</small>
        ) : null}
        {!canGenerate && selectedOption?.reason ? (
          <small className="muted">{selectedOption.reason}</small>
        ) : null}
        <button className="btn" disabled={busy || !canGenerate} onClick={() => void onGenerateDocument()}>
          Genera
        </button>
        <button
          className="btn"
          disabled={busy}
          onClick={() =>
            void onSave(row.dc_code, invoice, docDate || null, {
              gross: parseFloatOrNull(gross),
              net: parseFloatOrNull(net),
              volume: parseFloatOrNull(volume),
              pallets: parseIntOrNull(pallets),
            })
          }
        >
          Salva DC
        </button>
      </div>
    </div>
  );
}
function InfoCell({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="card">
      <div className="k">{label}</div>
      <div className="v" style={{ fontSize: 20 }}>{value}</div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="card">
      <div className="k">{label}</div>
      <div className="v">{value}</div>
    </div>
  );
}


