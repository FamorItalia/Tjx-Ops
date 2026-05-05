from dataclasses import dataclass
from datetime import date
import json
import logging
import math
import re

from fastapi import HTTPException, status
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.repositories.packing_lists_repository import PackingListsRepository
from app.core.supplier_normalization import normalize_supplier_name
from app.schemas.packing_lists import (
    PackingListDestinationRead,
    PackingListGroupRead,
    PackingListGroupProductRead,
    PackingListLineRead,
    PackingListPreviewBatchRead,
    PackingListPreviewRequest,
    PackingListRead,
    PackingListUpdateRequest,
)
from app.services.purchase_orders_service import PurchaseOrdersService

logger = logging.getLogger(__name__)


@dataclass
class _LineCtx:
    po_line: object
    customer_line: object | None
    line_no: int
    pieces: int
    nest_code: str | None
    vendor_pack_size: int | None
    store_ready_pack_size: int | None
    logistics: dict[str, int | float]


class PackingListsService:
    PALLET_BASE_HEIGHT_CM = 15.0

    def __init__(self, db: Session):
        self.db = db
        self.repo = PackingListsRepository(db)
        self.po_service = PurchaseOrdersService(db)

    @staticmethod
    def _to_int(value) -> int | None:
        if value is None:
            return None
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_float(value) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _format_destination(dc: object | None) -> dict:
        if dc is None:
            return {
                "dc_code": "N/A",
                "dc_name": None,
                "address": None,
                "city": None,
                "state": None,
                "zip_code": None,
                "country": None,
                "po_prefix": None,
                "general_division_name": None,
                "general_address_line_1": None,
                "general_address_line_2": None,
                "general_address_line_3": None,
                "destination_merce_name": None,
                "destination_merce_dc_number": None,
                "destination_merce_address_line_1": None,
                "destination_merce_address_line_2": None,
                "destination_merce_address_line_3": None,
            }
        return {
            "dc_code": dc.dc_code,
            "dc_name": dc.dc_name,
            "address": dc.address,
            "city": dc.city,
            "state": dc.state,
            "zip_code": dc.zip_code,
            "country": dc.country,
            "po_prefix": dc.po_prefix,
            "general_division_name": dc.general_division_name,
            "general_address_line_1": dc.general_address_line_1,
            "general_address_line_2": dc.general_address_line_2,
            "general_address_line_3": dc.general_address_line_3,
            "destination_merce_name": dc.destination_merce_name,
            "destination_merce_dc_number": dc.destination_merce_dc_number,
            "destination_merce_address_line_1": dc.destination_merce_address_line_1,
            "destination_merce_address_line_2": dc.destination_merce_address_line_2,
            "destination_merce_address_line_3": dc.destination_merce_address_line_3,
        }

    @staticmethod
    def _destination_has_layout_data(destination: dict | None) -> bool:
        if not destination:
            return False
        keys = [
            "general_division_name",
            "general_address_line_1",
            "general_address_line_2",
            "general_address_line_3",
            "destination_merce_name",
            "destination_merce_dc_number",
            "destination_merce_address_line_1",
            "destination_merce_address_line_2",
            "destination_merce_address_line_3",
        ]
        return any(destination.get(k) for k in keys)

    @staticmethod
    def _merge_destinations(primary: dict, fallback: dict | None) -> dict:
        if not fallback:
            return primary
        merged = dict(primary)
        for key, value in fallback.items():
            if merged.get(key) in (None, "", []):
                merged[key] = value
        return merged

    def _resolve_supplier_for_packing(self, po_row, products_map: dict[str, object]):
        # Business rule (Packing List only):
        # for OLICAV orders, manufacturer block must show LIKING supplier anagrafica.
        po_supplier_norm = (normalize_supplier_name(po_row.supplier_name) or po_row.supplier_name or "").strip().upper()
        if po_supplier_norm == "OLICAV":
            liking = self.repo.get_supplier_by_name("LIKING")
            if liking is not None:
                return liking

        supplier = self.repo.get_supplier_by_name(po_row.supplier_name)
        if supplier is not None:
            return supplier
        normalized_po_supplier = normalize_supplier_name(po_row.supplier_name)
        if normalized_po_supplier and normalized_po_supplier != po_row.supplier_name:
            supplier = self.repo.get_supplier_by_name(normalized_po_supplier)
            if supplier is not None:
                return supplier
        product_suppliers: list[str] = []
        seen: set[str] = set()
        for product in products_map.values():
            name = (getattr(product, "supplier_name", None) or "").strip()
            if not name:
                continue
            key = name.upper()
            if key in seen:
                continue
            seen.add(key)
            product_suppliers.append(name)
        for candidate in product_suppliers:
            resolved = self.repo.get_supplier_by_name(candidate)
            if resolved is not None:
                return resolved
            normalized_candidate = normalize_supplier_name(candidate)
            if normalized_candidate and normalized_candidate != candidate:
                resolved = self.repo.get_supplier_by_name(normalized_candidate)
                if resolved is not None:
                    return resolved
        return None

    def _resolve_po(self, payload: PackingListPreviewRequest):
        if payload.purchase_order_id is not None:
            po_row = self.repo.get_purchase_order(payload.purchase_order_id)
            if po_row is None:
                raise ValueError(f"Ordine fornitore non trovato: {payload.purchase_order_id}")
            return po_row

        po_existing = self.repo.get_purchase_order_by_customer_order(payload.customer_order_id)
        if po_existing is not None:
            return po_existing

        created = self.po_service.generate_preview(
            customer_order_id=payload.customer_order_id,
            adjustment_percent=2.0,
        )
        po_row = self.repo.get_purchase_order(created.id)
        if po_row is None:
            raise ValueError("Impossibile costruire la packing list: ordine fornitore non disponibile.")
        return po_row

    @staticmethod
    def _extract_dept_from_source_pdf(source_pdf_path: str | None) -> tuple[str | None, dict | None]:
        if not source_pdf_path:
            return None, {
                "code": "DEPT_SOURCE_MISSING",
                "message": "Percorso PDF sorgente mancante: DEPT non estraibile.",
            }
        candidate_paths = [source_pdf_path]
        if "Tjx operatività" in source_pdf_path:
            candidate_paths.append(source_pdf_path.replace("Tjx operatività", "TJXOPE~1"))
        if "Tjx operatività" in source_pdf_path:
            candidate_paths.append(source_pdf_path.replace("Tjx operatività", "TJXOPE~1"))
        if "\\TEMPLATES\\" in source_pdf_path:
            suffix = source_pdf_path.split("\\TEMPLATES\\", 1)[1]
            candidate_paths.append(f"C:\\Progetti\\TJXOPE~1\\TEMPLATES\\{suffix}")
        candidate_paths = list(dict.fromkeys(candidate_paths))

        text_candidates: list[str] = []
        try:
            for candidate in candidate_paths:
                try:
                    reader = PdfReader(candidate)
                except Exception:
                    continue

                default_text = "\n".join((page.extract_text() or "") for page in reader.pages[:3]).strip()
                if default_text:
                    text_candidates.append(default_text)

                layout_text_parts: list[str] = []
                for page in reader.pages[:3]:
                    try:
                        layout_text_parts.append(page.extract_text(extraction_mode="layout") or "")
                    except Exception:
                        continue
                layout_text = "\n".join(layout_text_parts).strip()
                if layout_text:
                    text_candidates.append(layout_text)
                if text_candidates:
                    break
        except Exception as exc:
            return None, {
                "code": "DEPT_PARSE_ERROR",
                "message": f"Errore lettura PDF sorgente per DEPT: {exc}",
            }
        if not text_candidates:
            return None, {
                "code": "DEPT_PARSE_ERROR",
                "message": "Nessun testo estratto dal PDF sorgente per DEPT.",
            }
        numeric_patterns = [
            r"\bDEPT\s*#\s*[:\-]?\s*([0-9]{1,6})\b",
            r"\bDEPT#\s*[:\-]?\s*([0-9]{1,6})\b",
            r"\bDEPT\s*\.?\s*NO\s*[:\-]?\s*([0-9]{1,6})\b",
            r"\bDEPT\s*NO\s*[:\-]?\s*([0-9]{1,6})\b",
            r"\bDEPT\b[^0-9]{0,40}\b([0-9]{1,6})\b",
        ]
        generic_patterns = [
            r"\bDEPT\s*#\s*[:\-]?\s*([A-Z0-9]{1,20})\b",
            r"\bDEPT#\s*[:\-]?\s*([A-Z0-9]{1,20})\b",
            r"\bDEPT\s*\.?\s*NO\s*[:\-]?\s*([A-Z0-9]{1,20})\b",
            r"\bDEPT\s*NO\s*[:\-]?\s*([A-Z0-9]{1,20})\b",
        ]
        for text in text_candidates:
            normalized = re.sub(r"\s+", " ", text.upper())
            for pattern in numeric_patterns + generic_patterns:
                match = re.search(pattern, normalized, flags=re.IGNORECASE)
                if match:
                    value = (match.group(1) or "").strip()
                    if not value:
                        continue
                    if value.upper() in {"ORDER", "DATE", "START", "SHIP", "CANCEL"}:
                        continue
                    return value, None

            # Layout fallback: DEPT header followed by table columns and then values.
            for dept_match in re.finditer(r"\bDEPT(?:\s*#|\s*\.?\s*NO)?\b", normalized):
                window = normalized[dept_match.start() : dept_match.start() + 600]
                date_match = re.search(r"\b\d{1,2}/\d{1,2}/\d{4}\b", window)
                if date_match:
                    prefix = window[: date_match.start()]
                    candidates = re.findall(r"\b\d{1,4}\b", prefix)
                    if candidates:
                        return candidates[-1], None
                nearby_candidates = re.findall(r"\b\d{1,4}\b", window[:160])
                if nearby_candidates:
                    return nearby_candidates[-1], None
        logger.warning("DEPT non trovato nel PDF sorgente: %s", source_pdf_path)
        return None, {
            "code": "DEPT_NOT_FOUND",
            "message": "DEPT non trovato nel PDF sorgente (standard/layout extraction).",
        }

    def _build_dc_codes(self, po_row) -> list[str | None]:
        codes: set[str] = set()
        customer_order = self.repo.get_customer_order(po_row.customer_order_id) if po_row.customer_order_id else None
        if customer_order and customer_order.distribution_center:
            codes.add(customer_order.distribution_center)

        if customer_order:
            for l in customer_order.lines:
                if l.distribution_center:
                    codes.add(l.distribution_center)
                codes.update(l.units_per_dc.keys())

        for l in po_row.lines:
            codes.update(l.units_per_dc.keys())

        if not codes:
            return [None]
        return sorted(codes)

    def _resolve_recipient(self, destination: dict) -> tuple[str | None, str | None]:
        if not destination:
            return None, None
        name = destination.get("dc_name") or destination.get("dc_code")
        addr_parts = [destination.get("address")]
        city_line = " ".join(
            x for x in [destination.get("zip_code"), destination.get("city"), destination.get("state")] if x
        ).strip()
        if city_line:
            addr_parts.append(city_line)
        if destination.get("country"):
            addr_parts.append(destination["country"])
        return name, ", ".join(x for x in addr_parts if x) or None

    def _build_logistics(self, po_line, product_row) -> dict[str, int | float]:
        log = dict(po_line.logistics or {})
        if product_row is None:
            return log
        mapping = {
            "pcs_per_crt": product_row.pcs_per_crt,
            "cartons_per_layer": product_row.cartons_per_layer,
            "cartons_per_pallet": product_row.cartons_per_pallet,
            "layers_per_pallet": product_row.layers_per_pallet or product_row.strat_x_pl,
            "carton_height_cm": product_row.carton_height_cm,
            "carton_width_cm": product_row.carton_width_cm,
            "carton_depth_cm": product_row.carton_depth_cm,
            "pallet_width_cm": product_row.pallet_width_cm,
            "pallet_depth_cm": product_row.pallet_depth_cm,
            "peso_lordo": product_row.peso_lordo,
            "peso_netto": product_row.peso_netto,
        }
        for k, v in mapping.items():
            if k not in log and v is not None:
                log[k] = v
        return log

    def _calc_volume_m3(self, cartons: int | None, logistics: dict) -> tuple[float, int | None, int | None, list[dict], dict]:
        warnings: list[dict] = []
        if cartons is None or cartons <= 0:
            return 0.0, 0, 0, warnings, {
                "cartons_per_layer": None,
                "cartons_per_pallet": None,
                "layers_per_pallet": None,
                "carton_height_cm": None,
                "pallet_width_cm": None,
                "pallet_depth_cm": None,
            }

        cpl = self._to_int(logistics.get("cartons_per_layer"))
        cpp = self._to_int(logistics.get("cartons_per_pallet"))
        lpp = self._to_int(logistics.get("layers_per_pallet"))
        ch = self._to_float(logistics.get("carton_height_cm"))
        pw = self._to_float(logistics.get("pallet_width_cm"))
        pd = self._to_float(logistics.get("pallet_depth_cm"))

        if (not cpl or cpl <= 0) and cpp and lpp and lpp > 0:
            derived = cpp / lpp
            cpl = int(round(derived))
        if (not lpp or lpp <= 0) and cpp and cpl and cpl > 0:
            lpp = int(math.ceil(cpp / cpl))

        if not cpl or cpl <= 0 or not lpp or lpp <= 0:
            warnings.append(
                {
                    "code": "PALLET_STRUCTURE_MISSING",
                    "message": "Dati pallettizzazione incompleti (cartons_per_layer/layers_per_pallet).",
                }
            )
            return 0.0, None, None, warnings, {
                "cartons_per_layer": cpl,
                "cartons_per_pallet": cpp,
                "layers_per_pallet": lpp,
                "carton_height_cm": ch,
                "pallet_width_cm": pw,
                "pallet_depth_cm": pd,
            }

        if ch is None or pw is None or pd is None:
            warnings.append(
                {
                    "code": "PALLET_DIMENSIONS_MISSING",
                    "message": "Dimensioni pallet/cartone incomplete: volume non calcolato.",
                }
            )
            return 0.0, None, None, warnings, {
                "cartons_per_layer": cpl,
                "cartons_per_pallet": cpp,
                "layers_per_pallet": lpp,
                "carton_height_cm": ch,
                "pallet_width_cm": pw,
                "pallet_depth_cm": pd,
            }

        layers_needed = int(math.ceil(cartons / cpl))
        full_pallets = layers_needed // lpp
        partial_layers = layers_needed % lpp

        full_height = self.PALLET_BASE_HEIGHT_CM + (lpp * ch)
        full_volume_cm3 = pw * pd * full_height
        total_cm3 = full_pallets * full_volume_cm3
        if partial_layers > 0:
            partial_height = self.PALLET_BASE_HEIGHT_CM + (partial_layers * ch)
            total_cm3 += pw * pd * partial_height

        return (
            total_cm3 / 1_000_000.0,
            full_pallets,
            partial_layers,
            warnings,
            {
                "cartons_per_layer": cpl,
                "cartons_per_pallet": cpp,
                "layers_per_pallet": lpp,
                "carton_height_cm": ch,
                "pallet_width_cm": pw,
                "pallet_depth_cm": pd,
            },
        )

    def _resolve_line_quantity_for_dc(self, po_line, dc_code: str | None, customer_line_by_id: dict[int, object]) -> int:
        customer_line = customer_line_by_id.get(po_line.customer_order_line_id) if po_line.customer_order_line_id else None

        if customer_line and customer_line.operational_units_per_dc:
            if dc_code is None:
                return 0
            return int(customer_line.operational_units_per_dc.get(dc_code) or 0)

        if po_line.units_per_dc:
            if dc_code is None:
                return 0
            return int(po_line.units_per_dc.get(dc_code) or 0)

        if customer_line is not None:
            if dc_code is None:
                return int(customer_line.operational_units or 0)
            if customer_line.distribution_center == dc_code:
                return int(customer_line.operational_units or 0)
            return 0

        if dc_code is None:
            return int(po_line.quantity_final or 0)

        if customer_line and customer_line.distribution_center == dc_code:
            return int(po_line.quantity_final or 0)
        return 0

    def _build_line_contexts(self, po_row, dc_code: str | None, customer_line_by_id: dict[int, object], products_map: dict[str, object]) -> list[_LineCtx]:
        contexts: list[_LineCtx] = []

        lines_source = list(po_row.lines)
        # Hard safety: if we know customer-order lines for this PO, keep only rows
        # truly linked to this order and de-duplicate stale historical snapshots.
        if customer_line_by_id:
            valid_ids = set(customer_line_by_id.keys())
            latest_by_customer_line: dict[int, object] = {}
            for po_line in lines_source:
                cid = po_line.customer_order_line_id
                if cid is None or cid not in valid_ids:
                    continue
                current = latest_by_customer_line.get(cid)
                current_id = current.id if current and current.id is not None else -1
                line_id = po_line.id if po_line.id is not None else -1
                if current is None or line_id >= current_id:
                    latest_by_customer_line[cid] = po_line
            lines_source = list(latest_by_customer_line.values())

        sorted_lines = sorted(
            lines_source,
            key=lambda x: (
                x.customer_order_line_id if x.customer_order_line_id is not None else 10**9,
                x.id if x.id is not None else 10**9,
            ),
        )
        line_no = 0
        for po_line in sorted_lines:
            pieces = self._resolve_line_quantity_for_dc(po_line, dc_code, customer_line_by_id)
            if pieces <= 0:
                continue
            line_no += 1
            customer_line = customer_line_by_id.get(po_line.customer_order_line_id) if po_line.customer_order_line_id else None
            style_key = self.repo.style_key(po_line.vendor_style)
            product = products_map.get(style_key) if style_key else None
            logistics = self._build_logistics(po_line, product)
            explicit_vendor_pack_raw = self._to_int(getattr(customer_line, "vend_pack", None))
            explicit_vendor_pack = (
                explicit_vendor_pack_raw if explicit_vendor_pack_raw and explicit_vendor_pack_raw > 0 else None
            )
            vendor_pack_size = explicit_vendor_pack
            if vendor_pack_size is None:
                vendor_pack_size = self._to_int(logistics.get("pcs_per_crt"))
            store_ready_raw = self._to_int(getattr(customer_line, "store_ready_pack_size", None))
            store_ready_pack_size = store_ready_raw if store_ready_raw and store_ready_raw > 0 else None
            contexts.append(
                _LineCtx(
                    po_line=po_line,
                    customer_line=customer_line,
                    line_no=line_no,
                    pieces=pieces,
                    nest_code=(po_line.nest_code or None),
                    vendor_pack_size=vendor_pack_size,
                    store_ready_pack_size=store_ready_pack_size,
                    logistics=logistics,
                )
            )
        return contexts

    @staticmethod
    def _is_nested_cartons_coherent(rows: list[_LineCtx]) -> bool:
        cartons: list[int] = []
        for r in rows:
            sr = int(r.store_ready_pack_size or 0)
            if sr <= 0 or r.pieces % sr != 0:
                return False
            cartons.append(r.pieces // sr)
        return len(set(cartons)) == 1 if cartons else False

    def _try_reconcile_nested_store_ready(
        self,
        rows: list[_LineCtx],
        vendor_pack: int | None,
        nest_code: str,
    ) -> dict | None:
        if not vendor_pack or vendor_pack <= 0:
            return None

        line_count = len(rows)
        # Strategy 1: uniform split of vendor pack across SKUs (e.g. 18 with 2 SKUs -> 9+9)
        if line_count > 0 and vendor_pack % line_count == 0:
            candidate = vendor_pack // line_count
            if candidate > 0:
                old_values = [r.store_ready_pack_size for r in rows]
                for r in rows:
                    r.store_ready_pack_size = candidate
                if self._is_nested_cartons_coherent(rows):
                    return {
                        "code": "NEST_STORE_READY_REPAIRED_UNIFORM",
                        "message": (
                            f"Nest {nest_code}: store_ready_pack_size corretto automaticamente con split uniforme "
                            f"{candidate} (vendor_pack={vendor_pack}, sku={line_count})."
                        ),
                    }
                for r, old in zip(rows, old_values):
                    r.store_ready_pack_size = old

        # Strategy 2: derive cartons from total pieces and vendor pack.
        total_pieces = sum(int(r.pieces or 0) for r in rows)
        if total_pieces > 0 and total_pieces % vendor_pack == 0:
            cartons = total_pieces // vendor_pack
            if cartons > 0:
                derived: list[int] = []
                valid = True
                for r in rows:
                    if r.pieces % cartons != 0:
                        valid = False
                        break
                    sr = r.pieces // cartons
                    if sr <= 0:
                        valid = False
                        break
                    derived.append(sr)
                if valid and sum(derived) == vendor_pack:
                    old_values = [r.store_ready_pack_size for r in rows]
                    for r, sr in zip(rows, derived):
                        r.store_ready_pack_size = sr
                    if self._is_nested_cartons_coherent(rows):
                        return {
                            "code": "NEST_STORE_READY_REPAIRED_DERIVED",
                            "message": (
                                f"Nest {nest_code}: store_ready_pack_size derivato automaticamente dai pezzi "
                                f"(vendor_pack={vendor_pack}, cartons={cartons})."
                            ),
                        }
                    for r, old in zip(rows, old_values):
                        r.store_ready_pack_size = old

        return None

    def _cartons_from_ratio(self, pieces: int, denominator: int | None) -> tuple[int | None, dict | None]:
        if denominator is None or denominator <= 0:
            return None, {
                "code": "PACK_SIZE_MISSING",
                "message": "Pack size mancante o non valido per calcolo cartoni.",
            }
        raw = pieces / denominator
        cartons = int(math.ceil(raw))
        if abs(raw - round(raw)) > 1e-9:
            return cartons, {
                "code": "NON_INTEGER_CARTONS",
                "message": f"Cartoni non interi ({pieces}/{denominator}); applicato ceil a {cartons}.",
            }
        return cartons, None

    def _build_groups(self, contexts: list[_LineCtx]) -> tuple[list[dict], list[dict]]:
        warnings: list[dict] = []
        groups: list[dict] = []

        nested_buckets: dict[str, list[_LineCtx]] = {}
        mono_rows: list[_LineCtx] = []
        for ctx in contexts:
            if ctx.nest_code:
                nested_buckets.setdefault(ctx.nest_code, []).append(ctx)
            else:
                mono_rows.append(ctx)

        for ctx in mono_rows:
            groups.append(
                {
                    "group_key": f"mono:{ctx.po_line.id}",
                    "group_type": "mono",
                    "nest_code": None,
                    "vendor_pack_size": ctx.vendor_pack_size,
                    "rows": [ctx],
                }
            )

        for nest_code, rows in sorted(nested_buckets.items(), key=lambda x: x[0]):
            if len(rows) < 2:
                for ctx in rows:
                    groups.append(
                        {
                            "group_key": f"mono-fallback:{ctx.po_line.id}",
                            "group_type": "mono",
                            "nest_code": None,
                            "vendor_pack_size": ctx.vendor_pack_size,
                            "rows": [ctx],
                            "warnings_seed": [
                                {
                                    "code": "NEST_SINGLE_LINE_FALLBACK_MONO",
                                    "message": (
                                        f"Nest {nest_code}: gruppo con una sola riga, convertito automaticamente in MONO."
                                    ),
                                }
                            ],
                        }
                    )
                continue
            groups.append(
                {
                    "group_key": f"nested:{nest_code}",
                    "group_type": "nested",
                    "nest_code": nest_code,
                    "vendor_pack_size": None,
                    "rows": rows,
                }
            )
        return groups, warnings

    def _evaluate_group(self, group: dict) -> tuple[dict, list[dict], list[dict]]:
        rows: list[_LineCtx] = group["rows"]
        group_warnings: list[dict] = list(group.get("warnings_seed") or [])
        effective_vendor_pack_size = group["vendor_pack_size"]

        if group["group_type"] == "nested":
            group_warnings.extend(self._validate_nested_group_or_raise(group, rows))
            explicit_vendor_pack = next((r.vendor_pack_size for r in rows if r.vendor_pack_size is not None), None)
            if explicit_vendor_pack is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Nested group {group.get('nest_code') or 'N/A'} non valido: "
                        "master carton non disponibile su almeno una riga."
                    ),
                )
            effective_vendor_pack_size = explicit_vendor_pack

        total_pieces = sum(r.pieces for r in rows)
        if group["group_type"] == "nested":
            master = int(effective_vendor_pack_size or 0)
            if master <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Nested group {group.get('nest_code') or 'N/A'}: master carton non valido per calcolo cartoni.",
                )
            total_cartons = total_pieces // master
            remainder = total_pieces % master
            if remainder != 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Nested group {group.get('nest_code') or 'N/A'} incoerente: "
                        f"pezzi gruppo {total_pieces} non multipli del master {master} (resto {remainder})."
                    ),
                )
        else:
            cartons_candidates: list[int] = []
            for r in rows:
                denominator = r.vendor_pack_size
                cartons, warn = self._cartons_from_ratio(r.pieces, denominator)
                if warn:
                    group_warnings.append({**warn, "line_no": r.line_no, "vendor_style": r.po_line.vendor_style})
                if cartons is not None:
                    cartons_candidates.append(cartons)
            total_cartons = cartons_candidates[0] if cartons_candidates else None

        ref = rows[0]
        gross_per = self._to_float(ref.logistics.get("peso_lordo"))
        net_per = self._to_float(ref.logistics.get("peso_netto"))
        cw = self._to_float(ref.logistics.get("carton_width_cm"))
        cd = self._to_float(ref.logistics.get("carton_depth_cm"))
        ch = self._to_float(ref.logistics.get("carton_height_cm"))
        carton_size = None
        if cw is not None and cd is not None and ch is not None:
            carton_size = f"{cw} x {cd} x {ch} cm"

        for r in rows[1:]:
            g = self._to_float(r.logistics.get("peso_lordo"))
            n = self._to_float(r.logistics.get("peso_netto"))
            if gross_per is not None and g is not None and abs(g - gross_per) > 1e-9:
                group_warnings.append(
                    {"code": "GROSS_WEIGHT_MISMATCH", "message": f"Gruppo {group['group_key']}: peso lordo/cartone non uniforme."}
                )
                break
            if net_per is not None and n is not None and abs(n - net_per) > 1e-9:
                group_warnings.append(
                    {"code": "NET_WEIGHT_MISMATCH", "message": f"Gruppo {group['group_key']}: peso netto/cartone non uniforme."}
                )
                break

        line_m3, _, _, volume_warnings, vol_meta = self._calc_volume_m3(total_cartons, ref.logistics)
        group_warnings.extend(volume_warnings)

        total_gross = (total_cartons * gross_per) if total_cartons is not None and gross_per is not None else None
        total_net = (total_cartons * net_per) if total_cartons is not None and net_per is not None else None
        product_rows = []
        for r in rows:
            pcs_x_crt = r.store_ready_pack_size if group["group_type"] == "nested" else r.vendor_pack_size
            product_rows.append(
                {
                    "line_no": r.line_no,
                    "vendor_style": r.po_line.vendor_style,
                    "item_code": r.po_line.item_code,
                    "description": r.po_line.description,
                    "pieces": r.pieces,
                    "pcs_x_crt": pcs_x_crt,
                    "vendor_pack_size": r.vendor_pack_size,
                    "store_ready_pack_size": r.store_ready_pack_size,
                }
            )

        evaluated = {
            "group_key": group["group_key"],
            "group_type": group["group_type"],
            "nest_code": group["nest_code"],
            "vendor_pack_size": effective_vendor_pack_size,
            "total_pieces": total_pieces,
            "total_cartons": total_cartons,
            "carton_size": carton_size,
            "gross_weight_per_carton": gross_per,
            "net_weight_per_carton": net_per,
            "total_gross_weight": total_gross,
            "total_net_weight": total_net,
            "total_cubic_meters": line_m3,
            "products": product_rows,
            "warnings": group_warnings,
            "volume_meta": vol_meta,
        }
        return evaluated, group_warnings, product_rows

    def _validate_nested_group_or_raise(self, group: dict, rows: list[_LineCtx]) -> list[dict]:
        nest_code = group.get("nest_code") or "N/A"
        styles = [r.po_line.vendor_style or "N/A" for r in rows]
        warnings: list[dict] = []

        if len(rows) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Nested group {nest_code} non valido: gruppo con meno di 2 righe "
                    f"(vendor_style={styles})."
                ),
            )

        pack_values: set[int] = set()
        detail_rows: list[dict] = []
        for r in rows:
            pack = r.vendor_pack_size
            detail_rows.append({"vendor_style": r.po_line.vendor_style, "vendor_pack_size": pack})
            if pack is None or pack <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Nested group {nest_code} non valido: master carton mancante/non valido {detail_rows}",
                )
            pack_values.add(int(pack))

        if len(pack_values) != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Nested group {nest_code} incoerente: master carton non uniforme {detail_rows}",
            )

        master = next(iter(pack_values))
        if master % len(rows) != 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Nested group {nest_code} non valido: master carton {master} "
                    f"non divisibile per numero SKU {len(rows)}."
                ),
            )

        inferred_sr = master // len(rows)
        cartons_ratio_by_style: dict[str, float] = {}
        for r in rows:
            sr = inferred_sr
            pieces = int(r.pieces or 0)
            if sr <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Nested group {nest_code} non valido: store_ready non valido su {r.po_line.vendor_style}.",
                )
            if pieces % sr != 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Nested group {nest_code} incoerente: units {pieces} "
                        f"non divisibili per store_ready {sr} su {r.po_line.vendor_style}."
                    ),
                )
            r.store_ready_pack_size = sr
            cartons_ratio_by_style[r.po_line.vendor_style or "N/A"] = pieces / sr

        ratio_values = list(cartons_ratio_by_style.values())
        rounded = [round(v, 8) for v in ratio_values]
        if len(set(rounded)) != 1:
            details = ", ".join(f"SKU {k} produce {v:.4f} cartons teorici" for k, v in cartons_ratio_by_style.items())
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Nested group {nest_code} incoerente: {details}.",
            )
        return warnings

    def _to_read(self, row) -> PackingListRead:
        groups_raw = row.groups
        return PackingListRead(
            id=row.id,
            purchase_order_id=row.purchase_order_id,
            customer_order_id=row.customer_order_id,
            invoice_number=row.invoice_number,
            document_date=row.document_date,
            dc_code=row.dc_code,
            po_number=row.po_number,
            brand=row.brand,
            supplier_name=row.supplier_name,
            supplier_ragione_sociale=row.supplier_ragione_sociale,
            supplier_address_full=row.supplier_address_full,
            dept_no=row.dept_no,
            recipient_name=row.recipient_name,
            recipient_address=row.recipient_address,
            destinations=[PackingListDestinationRead(**x) for x in row.destinations],
            total_pieces=row.total_pieces,
            total_cartons=row.total_cartons,
            total_gross_weight=row.total_gross_weight,
            total_net_weight=row.total_net_weight,
            total_cubic_meters=row.total_cubic_meters,
            total_pallets=row.total_pallets,
            totals_manually_overridden=bool(getattr(row, "totals_manually_overridden", 0)),
            groups=[
                PackingListGroupRead(
                    group_key=g.get("group_key"),
                    group_type=g.get("group_type"),
                    nest_code=g.get("nest_code"),
                    vendor_pack_size=g.get("vendor_pack_size"),
                    total_cartons=g.get("total_cartons"),
                    carton_size=g.get("carton_size"),
                    gross_weight_per_carton=g.get("gross_weight_per_carton"),
                    net_weight_per_carton=g.get("net_weight_per_carton"),
                    total_gross_weight=g.get("total_gross_weight"),
                    total_net_weight=g.get("total_net_weight"),
                    total_cubic_meters=g.get("total_cubic_meters"),
                    products=[PackingListGroupProductRead(**p) for p in g.get("products", [])],
                    warnings=g.get("warnings", []),
                )
                for g in groups_raw
            ],
            warnings=row.warnings,
            lines=[
                PackingListLineRead(
                    id=l.id,
                    group_key=l.group_key,
                    group_type=l.group_type,
                    line_no=l.line_no,
                    vendor_style=l.vendor_style,
                    item_code=l.item_code,
                    description=l.description,
                    vendor_pack_size=l.vendor_pack_size,
                    store_ready_pack_size=l.store_ready_pack_size,
                    pcs_per_crt=l.pcs_per_crt,
                    gross_weight_per_carton=l.gross_weight_per_carton,
                    net_weight_per_carton=l.net_weight_per_carton,
                    cartons=l.cartons,
                    pieces=l.pieces,
                    cartons_per_layer=l.cartons_per_layer,
                    cartons_per_pallet=l.cartons_per_pallet,
                    layers_per_pallet=l.layers_per_pallet,
                    carton_height_cm=l.carton_height_cm,
                    pallet_width_cm=l.pallet_width_cm,
                    pallet_depth_cm=l.pallet_depth_cm,
                    full_pallets=l.full_pallets,
                    partial_layers=l.partial_layers,
                    line_cubic_meters=l.line_cubic_meters,
                    destination_dc_codes=l.destination_dc_codes,
                    warnings=l.warnings,
                )
                for l in sorted(row.lines, key=lambda x: x.line_no)
            ],
            created_at=row.created_at,
        )

    def create_previews(self, payload: PackingListPreviewRequest) -> PackingListPreviewBatchRead:
        po_row = self._resolve_po(payload)
        customer_order = self.repo.get_customer_order(po_row.customer_order_id) if po_row.customer_order_id else None
        dept_no_value, dept_warning = self._extract_dept_from_source_pdf(
            source_pdf_path=(customer_order.source_pdf_path if customer_order else None)
        )
        dept_no = dept_no_value or "-"
        customer_line_by_id = {x.id: x for x in (customer_order.lines if customer_order else [])}
        products_map = self.repo.get_products_by_styles([x.vendor_style for x in po_row.lines if x.vendor_style])
        supplier = self._resolve_supplier_for_packing(po_row=po_row, products_map=products_map)

        dc_codes = self._build_dc_codes(po_row)
        dc_map = self.repo.get_distribution_centers(po_row.brand, [x for x in dc_codes if x])
        dc_brand_rows = self.repo.list_distribution_centers_by_brand(po_row.brand)
        dc_brand_fallback = None
        if dc_brand_rows:
            def _score(dc) -> int:
                d = self._format_destination(dc)
                keys = [
                    "general_division_name",
                    "general_address_line_1",
                    "general_address_line_2",
                    "general_address_line_3",
                    "destination_merce_name",
                    "destination_merce_dc_number",
                    "destination_merce_address_line_1",
                    "destination_merce_address_line_2",
                    "destination_merce_address_line_3",
                ]
                return sum(1 for k in keys if d.get(k))
            dc_brand_fallback = max(dc_brand_rows, key=_score)
        dc_brand_fallback_dict = self._format_destination(dc_brand_fallback) if dc_brand_fallback is not None else None

        po_number = po_row.po_normalized or po_row.po_raw or po_row.po_number
        default_invoice_number = payload.invoice_number or f"DRAFT-{po_number or po_row.id}"
        default_document_date = payload.document_date or date.today()

        # Preserve per-DC document fields already edited/saved by users.
        # Key "" is used for orders without explicit DC (GLOBAL).
        existing_doc_fields: dict[str, tuple[str | None, date | None]] = {}
        for existing in self.repo.list_by_purchase_order_id(po_row.id):
            dc_key = (existing.dc_code or "").strip()
            existing_doc_fields[dc_key] = (existing.invoice_number, existing.document_date)

        supplier_address_full = None
        supplier_ragione_sociale = None
        if supplier is not None:
            supplier_ragione_sociale = supplier.ragione_sociale or supplier.name
            address_parts = [
                supplier.indirizzo,
                " ".join(
                    p for p in [supplier.cap, supplier.citta, supplier.provincia] if p
                ).strip()
                or None,
                supplier.paese,
            ]
            supplier_address_full = ", ".join(x for x in address_parts if x) or None

        self.repo.delete_by_purchase_order_id(po_row.id)
        created_rows = []

        for dc_code in dc_codes:
            destination = self._format_destination(dc_map.get(dc_code) if dc_code else None)
            if not self._destination_has_layout_data(destination):
                destination = self._merge_destinations(destination, dc_brand_fallback_dict)
            recipient_name, recipient_address = self._resolve_recipient(destination)

            contexts = self._build_line_contexts(po_row, dc_code, customer_line_by_id, products_map)
            if not contexts:
                continue

            groups_seed, warnings = self._build_groups(contexts)
            if dept_warning:
                warnings.append(dept_warning)
            groups_eval: list[dict] = []
            lines_data: list[dict] = []

            total_pieces = 0
            total_cartons = 0
            total_gross = 0.0
            total_net = 0.0
            total_m3 = 0.0
            line_id = 0

            for group in groups_seed:
                evaluated, group_warnings, products = self._evaluate_group(group)
                groups_eval.append(evaluated)
                warnings.extend(group_warnings)

                group_cartons = evaluated["total_cartons"] or 0
                group_gross = evaluated["total_gross_weight"] or 0.0
                group_net = evaluated["total_net_weight"] or 0.0
                group_m3 = evaluated["total_cubic_meters"] or 0.0

                total_pieces += evaluated["total_pieces"] or 0
                total_cartons += group_cartons
                total_gross += group_gross
                total_net += group_net
                total_m3 += group_m3

                first_in_group = True
                for p in products:
                    line_id += 1
                    lines_data.append(
                        {
                            "group_key": evaluated["group_key"],
                            "group_type": evaluated["group_type"],
                            "line_no": line_id,
                            "purchase_order_line_id": next(
                                (x.po_line.id for x in contexts if x.line_no == p["line_no"]),
                                None,
                            ),
                            "vendor_style": p["vendor_style"],
                            "item_code": p["item_code"],
                            "description": p["description"],
                            "vendor_pack_size": p["vendor_pack_size"],
                            "store_ready_pack_size": p["store_ready_pack_size"],
                            "pcs_per_crt": p["pcs_x_crt"],
                            "gross_weight_per_carton": evaluated["gross_weight_per_carton"] if first_in_group else None,
                            "net_weight_per_carton": evaluated["net_weight_per_carton"] if first_in_group else None,
                            "cartons": evaluated["total_cartons"] if first_in_group else None,
                            "pieces": p["pieces"],
                            "cartons_per_layer": evaluated["volume_meta"]["cartons_per_layer"] if first_in_group else None,
                            "cartons_per_pallet": evaluated["volume_meta"]["cartons_per_pallet"] if first_in_group else None,
                            "layers_per_pallet": evaluated["volume_meta"]["layers_per_pallet"] if first_in_group else None,
                            "carton_height_cm": evaluated["volume_meta"]["carton_height_cm"] if first_in_group else None,
                            "pallet_width_cm": evaluated["volume_meta"]["pallet_width_cm"] if first_in_group else None,
                            "pallet_depth_cm": evaluated["volume_meta"]["pallet_depth_cm"] if first_in_group else None,
                            "full_pallets": None,
                            "partial_layers": None,
                            "line_cubic_meters": evaluated["total_cubic_meters"] if first_in_group else None,
                            "destination_dc_codes_json": json.dumps([dc_code] if dc_code else []),
                            "warnings_json": json.dumps(evaluated["warnings"] if first_in_group else []),
                        }
                    )
                    first_in_group = False

            if not groups_eval:
                continue

            dc_key = (dc_code or "").strip()
            prev_invoice, prev_doc_date = existing_doc_fields.get(dc_key, (None, None))
            invoice_number = payload.invoice_number or prev_invoice or default_invoice_number
            document_date = payload.document_date or prev_doc_date or default_document_date

            row = self.repo.create_packing_list(
                data={
                    "purchase_order_id": po_row.id,
                    "customer_order_id": po_row.customer_order_id,
                    "invoice_number": invoice_number,
                    "document_date": document_date,
                    "dc_code": dc_code,
                    "po_number": po_number,
                    "brand": po_row.brand,
                    "supplier_name": supplier.name if supplier else po_row.supplier_name,
                    "supplier_ragione_sociale": supplier_ragione_sociale,
                    "supplier_address_full": supplier_address_full,
                    "dept_no": dept_no,
                    "recipient_name": recipient_name,
                    "recipient_address": recipient_address,
                    "destinations_json": json.dumps([destination]),
                    "groups_json": json.dumps(groups_eval),
                    "total_pieces": total_pieces,
                    "total_cartons": total_cartons,
                    "total_gross_weight": round(total_gross, 3),
                    "total_net_weight": round(total_net, 3),
                    "total_cubic_meters": round(total_m3, 6),
                    "total_pallets": None,
                    "totals_manually_overridden": 0,
                    "warnings_json": json.dumps(warnings),
                },
                lines_data=lines_data,
            )
            created_rows.append(self._to_read(row))

        return PackingListPreviewBatchRead(
            purchase_order_id=po_row.id,
            customer_order_id=po_row.customer_order_id,
            po_number=po_number,
            brand=po_row.brand,
            packing_lists=created_rows,
        )

    def get_packing_list(self, packing_list_id: int) -> PackingListRead | None:
        row = self.repo.get_packing_list(packing_list_id)
        if row is None:
            return None
        return self._to_read(row)

    def list_by_purchase_order_id(self, purchase_order_id: int) -> list[PackingListRead]:
        return [self._to_read(x) for x in self.repo.list_by_purchase_order_id(purchase_order_id)]

    def update_packing_list(self, packing_list_id: int, payload: PackingListUpdateRequest) -> PackingListRead:
        fields = payload.model_dump(exclude_unset=True)
        totals_keys = {"total_gross_weight", "total_net_weight", "total_cubic_meters", "total_pallets"}
        if any(k in fields for k in totals_keys) and "totals_manually_overridden" not in fields:
            fields["totals_manually_overridden"] = 1
        if "totals_manually_overridden" in fields:
            fields["totals_manually_overridden"] = 1 if fields["totals_manually_overridden"] else 0
        row = self.repo.update_packing_list_fields(packing_list_id=packing_list_id, fields=fields)
        if row is None:
            raise ValueError(f"Packing list non trovata: {packing_list_id}")
        return self._to_read(row)
