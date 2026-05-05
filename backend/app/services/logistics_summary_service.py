import math
from dataclasses import dataclass
import logging

from app.repositories.customer_orders_repository import CustomerOrdersRepository
from app.schemas.orders import (
    LogisticsDcSummaryRead,
    LogisticsGroupProductRead,
    LogisticsGroupRead,
    LogisticsScopeSummaryRead,
    OrderLogisticsSummaryRead,
)

logger = logging.getLogger(__name__)


@dataclass
class _LineCtx:
    line_id: int
    vendor_style: str | None
    item_code: str | None
    description: str | None
    nest_code: str | None
    units: int
    master_carton: int | None
    store_ready_pack_size: int | None
    cartons_per_pallet: int | None
    cartons_per_layer: int | None
    layers_per_pallet: int | None
    pallet_width_cm: float | None
    pallet_depth_cm: float | None
    carton_width_cm: float | None
    carton_depth_cm: float | None
    carton_height_cm: float | None
    gross_weight_per_carton: float | None
    net_weight_per_carton: float | None


class LogisticsSummaryService:
    PALLET_BASE_HEIGHT_CM = 15.0

    def __init__(self, repository: CustomerOrdersRepository):
        self.repository = repository

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
    def _normalize_nest(value: str | None) -> str | None:
        if not value:
            return None
        txt = value.strip().upper()
        if txt in {"", "MONO", "NONE", "N/A", "-"}:
            return None
        return txt

    @staticmethod
    def _normalize_dc_code(value) -> str:
        if value is None:
            return "GLOBAL"
        txt = str(value).strip()
        return txt or "GLOBAL"

    @classmethod
    def _units_from_map(cls, units_map: dict, dc_code: str) -> int:
        if not units_map:
            return 0
        normalized_dc = cls._normalize_dc_code(dc_code)

        direct = units_map.get(normalized_dc)
        if direct is not None:
            try:
                return int(direct or 0)
            except (TypeError, ValueError):
                return 0

        # Some persisted rows may store numeric keys (e.g. 882) instead of strings.
        # Match robustly without breaking leading-zero string codes.
        for key, raw in units_map.items():
            key_txt = cls._normalize_dc_code(key)
            if key_txt == normalized_dc:
                try:
                    return int(raw or 0)
                except (TypeError, ValueError):
                    return 0

        # Numeric-equivalent fallback: "0810" <-> 810.
        try:
            dc_num = int(normalized_dc)
        except (TypeError, ValueError):
            return 0
        for key, raw in units_map.items():
            try:
                if int(str(key).strip()) == dc_num:
                    return int(raw or 0)
            except (TypeError, ValueError):
                continue
        return 0

    @staticmethod
    def _effective_cartons_per_pallet(ref: _LineCtx) -> int | None:
        explicit_cpp = int(ref.cartons_per_pallet or 0)
        if explicit_cpp > 0:
            return explicit_cpp
        cpl = int(ref.cartons_per_layer or 0)
        lpp = int(ref.layers_per_pallet or 0)
        if cpl > 0 and lpp > 0:
            derived_cpp = cpl * lpp
            return derived_cpp if derived_cpp > 0 else None
        return None

    @staticmethod
    def _line_cartons_for_ctx(ctx: _LineCtx) -> float | None:
        if ctx.units <= 0:
            return 0.0
        if ctx.nest_code:
            sr = int(ctx.store_ready_pack_size or 0)
            if sr <= 0:
                return None
            return float(ctx.units) / float(sr)
        mc = int(ctx.master_carton or 0)
        if mc <= 0:
            return None
        return float(ctx.units) / float(mc)

    def _calc_pallet_volume_and_pallets(
        self,
        *,
        cartons: int,
        ref: _LineCtx,
    ) -> tuple[float | None, int | None, list[dict]]:
        warnings: list[dict] = []
        cpl = int(ref.cartons_per_layer or 0)
        lpp = int(ref.layers_per_pallet or 0)
        pw = ref.pallet_width_cm
        pd = ref.pallet_depth_cm
        ch = ref.carton_height_cm

        if cartons <= 0:
            return None, 0, warnings

        if cpl <= 0 or lpp <= 0:
            warnings.append(
                {
                    "code": "PALLET_STRUCTURE_MISSING",
                    "message": "Dati pallettizzazione incompleti (cartons_per_layer/layers_per_pallet).",
                }
            )
            cpp = int(ref.cartons_per_pallet or 0)
            fallback_pallets = int(math.ceil(cartons / cpp)) if cpp > 0 else None
            return None, fallback_pallets, warnings

        if pw is None or pd is None or ch is None:
            warnings.append(
                {
                    "code": "PALLET_DIMENSIONS_MISSING",
                    "message": "Dimensioni pallet/cartone incomplete: volume non calcolato.",
                }
            )
            layers_needed = int(math.ceil(cartons / cpl))
            full_pallets = layers_needed // lpp
            partial_layers = layers_needed % lpp
            pallets = full_pallets + (1 if partial_layers > 0 else 0)
            return None, pallets, warnings

        layers_needed = int(math.ceil(cartons / cpl))
        full_pallets = layers_needed // lpp
        partial_layers = layers_needed % lpp

        full_height = self.PALLET_BASE_HEIGHT_CM + (lpp * ch)
        full_volume_cm3 = pw * pd * full_height
        total_cm3 = full_pallets * full_volume_cm3

        if partial_layers > 0:
            partial_height = self.PALLET_BASE_HEIGHT_CM + (partial_layers * ch)
            total_cm3 += pw * pd * partial_height

        total_pallets = full_pallets + (1 if partial_layers > 0 else 0)
        return total_cm3 / 1_000_000.0, total_pallets, warnings

    def _calc_dc_aggregated_pallet_metrics(
        self,
        *,
        contexts: list[_LineCtx],
        group_pallet_basis: list[tuple[int, int | None]],
        total_cartons: int,
        dc_code: str | None = None,
    ) -> tuple[float | None, int | None]:
        """
        Compute pallets/volume at DC level allowing carton mixing across products.
        We aggregate only when pallet structure is compatible across lines.
        """
        if total_cartons <= 0:
            return None, 0

        signatures: set[tuple[int, int, float, float, float]] = set()
        cpp_values: set[int] = set()
        line_debug_rows: list[dict] = []
        occupancy_sum = 0.0
        layers_height_sum = 0.0
        has_volume_inputs = True
        has_occupancy_inputs = True
        pallet_width_values: set[float] = set()
        pallet_depth_values: set[float] = set()
        for ctx in contexts:
            cpl = int(ctx.cartons_per_layer or 0)
            lpp = int(ctx.layers_per_pallet or 0)
            pw = float(ctx.pallet_width_cm or 0)
            pd = float(ctx.pallet_depth_cm or 0)
            ch = float(ctx.carton_height_cm or 0)
            cpp = int(self._effective_cartons_per_pallet(ctx) or 0)
            line_cartons = self._line_cartons_for_ctx(ctx)
            layer_count: int | None = None
            line_height_cm: float | None = None
            occupancy_line: float | None = None
            if line_cartons is None:
                has_occupancy_inputs = False
                has_volume_inputs = False
            else:
                if cpp > 0:
                    occupancy_line = float(line_cartons) / float(cpp)
                    occupancy_sum += occupancy_line
                else:
                    has_occupancy_inputs = False
                if cpl > 0 and ch > 0:
                    layer_count = int(math.ceil(float(line_cartons) / float(cpl)))
                    line_height_cm = float(layer_count) * ch
                    layers_height_sum += line_height_cm
                else:
                    has_volume_inputs = False
            if cpp > 0:
                cpp_values.add(cpp)
            if cpl > 0 and lpp > 0 and pw > 0 and pd > 0 and ch > 0:
                signatures.add((cpl, lpp, pw, pd, ch))
            if pw > 0:
                pallet_width_values.add(pw)
            if pd > 0:
                pallet_depth_values.add(pd)

            line_debug_rows.append(
                {
                    "vendor_style": ctx.vendor_style,
                    "nest_code": ctx.nest_code,
                    "units": ctx.units,
                    "cartons": (round(line_cartons, 6) if line_cartons is not None else None),
                    "capacity_pallet": (cpp if cpp > 0 else None),
                    "occupazione": (round(occupancy_line, 6) if occupancy_line is not None else None),
                    "cartons_per_layer": (cpl if cpl > 0 else None),
                    "layers": layer_count,
                    "carton_height_cm": (ch if ch > 0 else None),
                    "height_cm": (round(line_height_cm, 4) if line_height_cm is not None else None),
                }
            )

        dc_pallets_from_occupancy: int | None = None
        if has_occupancy_inputs and occupancy_sum > 0:
            dc_pallets_from_occupancy = int(math.ceil(occupancy_sum))

        # If pallet structure is uniform across lines, aggregate by DC.
        if len(signatures) == 1:
            cpl, lpp, pw, pd, ch = next(iter(signatures))
            layers_needed = int(math.ceil(total_cartons / cpl))
            full_pallets = layers_needed // lpp
            partial_layers = layers_needed % lpp

            full_height = self.PALLET_BASE_HEIGHT_CM + (lpp * ch)
            total_cm3 = full_pallets * (pw * pd * full_height)
            if partial_layers > 0:
                partial_height = self.PALLET_BASE_HEIGHT_CM + (partial_layers * ch)
                total_cm3 += pw * pd * partial_height
            total_pallets = full_pallets + (1 if partial_layers > 0 else 0)
            return total_cm3 / 1_000_000.0, total_pallets

        # Mixed pallet structures: use DC-consolidated pallet count + consolidated height.
        # This avoids virtual-SKU volume overestimation.
        if dc_pallets_from_occupancy is not None and has_volume_inputs and layers_height_sum > 0:
            pw = max(pallet_width_values) if pallet_width_values else 0.0
            pd = max(pallet_depth_values) if pallet_depth_values else 0.0
            if pw > 0 and pd > 0:
                total_height_cm = layers_height_sum + (self.PALLET_BASE_HEIGHT_CM * dc_pallets_from_occupancy)
                total_volume = (pw * pd * total_height_cm) / 1_000_000.0
                logger.info(
                    "LOGISTICS_DC_DEBUG dc=%s rows=%s occupancy_sum=%.6f pallets_dc=%s "
                    "layers_height_sum_cm=%.4f total_height_cm=%.4f volume_m3=%.6f",
                    dc_code or "N/A",
                    line_debug_rows,
                    occupancy_sum,
                    dc_pallets_from_occupancy,
                    layers_height_sum,
                    total_height_cm,
                    total_volume,
                )
                return total_volume, dc_pallets_from_occupancy

        # Fallback (mix products on shared pallets): compute pallet utilization by
        # summing group carton occupancy fractions.
        # Example: cartons_i / cartons_per_pallet_i, then ceil(total utilization).
        occupancy = 0.0
        has_basis = False
        for cartons_i, cpp_i in group_pallet_basis:
            if cartons_i <= 0:
                continue
            if cpp_i is None or cpp_i <= 0:
                continue
            occupancy += float(cartons_i) / float(cpp_i)
            has_basis = True
        if has_basis and occupancy > 0:
            return None, int(math.ceil(occupancy))

        # Secondary fallback: if only cartons_per_pallet is uniform, aggregate pallets only.
        if len(cpp_values) == 1:
            cpp = next(iter(cpp_values))
            if cpp > 0:
                return None, int(math.ceil(total_cartons / cpp))

        # Incompatible structures: caller should fallback to sum of group values.
        return None, None

    @staticmethod
    def _is_nested_cartons_coherent(rows: list[_LineCtx]) -> bool:
        cartons: list[int] = []
        for r in rows:
            sr = int(r.store_ready_pack_size or 0)
            if sr <= 0 or r.units % sr != 0:
                return False
            cartons.append(r.units // sr)
        return len(set(cartons)) == 1 if cartons else False

    def _repair_nested_store_ready(self, rows: list[_LineCtx], group_key: str, dc_code: str) -> list[dict]:
        warnings: list[dict] = []
        if not rows:
            return warnings
        vendor_pack = rows[0].master_carton
        if vendor_pack is None or vendor_pack <= 0:
            return warnings

        missing_or_invalid = any((r.store_ready_pack_size or 0) <= 0 for r in rows)
        current_sum = sum(int(r.store_ready_pack_size or 0) for r in rows)
        sum_mismatch = current_sum != int(vendor_pack)
        # If current store-ready values are already coherent for carton math, keep them
        # even when vendor pack differs (PDF noise / source inconsistency).
        if not missing_or_invalid and sum_mismatch and self._is_nested_cartons_coherent(rows):
            warnings.append(
                {
                    "code": "NEST_VENDOR_PACK_MISMATCH_IGNORED",
                    "message": (
                        f"Nested {group_key} DC {dc_code}: sum(store_ready)={current_sum} "
                        f"!= vendor_pack={int(vendor_pack)}, mantenuto store_ready coerente per cartoni."
                    ),
                }
            )
            return warnings
        if not (missing_or_invalid or sum_mismatch):
            return warnings

        # Strategy 1: uniform split
        line_count = len(rows)
        if line_count > 0 and int(vendor_pack) % line_count == 0:
            candidate = int(vendor_pack) // line_count
            if candidate > 0:
                old = [r.store_ready_pack_size for r in rows]
                for r in rows:
                    r.store_ready_pack_size = candidate
                if self._is_nested_cartons_coherent(rows):
                    warnings.append(
                        {
                            "code": "NEST_STORE_READY_REPAIRED_UNIFORM",
                            "message": (
                                f"Nested {group_key} DC {dc_code}: store_ready corretto automaticamente a "
                                f"{candidate} (vendor_pack={int(vendor_pack)})."
                            ),
                        }
                    )
                    return warnings
                for r, prev in zip(rows, old):
                    r.store_ready_pack_size = prev

        # Strategy 2: derive by total pieces/cartons
        total_pieces = sum(int(r.units or 0) for r in rows)
        if total_pieces > 0 and total_pieces % int(vendor_pack) == 0:
            cartons = total_pieces // int(vendor_pack)
            if cartons > 0:
                old = [r.store_ready_pack_size for r in rows]
                derived: list[int] = []
                valid = True
                for r in rows:
                    if r.units % cartons != 0:
                        valid = False
                        break
                    sr = r.units // cartons
                    if sr <= 0:
                        valid = False
                        break
                    derived.append(sr)
                if valid and sum(derived) == int(vendor_pack):
                    for r, sr in zip(rows, derived):
                        r.store_ready_pack_size = sr
                    if self._is_nested_cartons_coherent(rows):
                        warnings.append(
                            {
                                "code": "NEST_STORE_READY_REPAIRED_DERIVED",
                                "message": (
                                    f"Nested {group_key} DC {dc_code}: store_ready derivato automaticamente dai pezzi."
                                ),
                            }
                        )
                        return warnings
                for r, prev in zip(rows, old):
                    r.store_ready_pack_size = prev

        if self._is_nested_cartons_coherent(rows):
            warnings.append(
                {
                    "code": "NEST_VENDOR_PACK_MISMATCH_IGNORED",
                    "message": (
                        f"Nested {group_key} DC {dc_code}: mantenuto store_ready coerente per cartoni "
                        "nonostante mismatch vendor_pack."
                    ),
                }
            )
            return warnings

        styles = [r.vendor_style or "N/A" for r in rows]
        raise ValueError(
            f"Nested group {group_key} su DC {dc_code} incoerente: store_ready non riconciliabile (vendor_style={styles})"
        )

    def _units_for_dc(self, line, dc_code: str, mode: str) -> int:
        units_map = line.original_units_per_dc if mode == "received" else line.operational_units_per_dc
        if units_map:
            return self._units_from_map(units_map, dc_code)
        scalar = line.original_units if mode == "received" else line.operational_units
        return int(scalar or 0) if dc_code == (line.distribution_center or "GLOBAL") else 0

    def _collect_dc_codes(self, order, mode: str) -> list[str]:
        codes: set[str] = set()
        for line in order.lines:
            units_map = line.original_units_per_dc if mode == "received" else line.operational_units_per_dc
            if units_map:
                for key in units_map.keys():
                    codes.add(self._normalize_dc_code(key))
            elif line.distribution_center:
                codes.add(self._normalize_dc_code(line.distribution_center))
            elif (line.original_units if mode == "received" else line.operational_units):
                codes.add("GLOBAL")
        if not codes and order.distribution_center:
            codes.add(self._normalize_dc_code(order.distribution_center))
        if not codes:
            codes.add("GLOBAL")
        return sorted(codes)

    def _build_group(self, dc_code: str, group_key: str, rows: list[_LineCtx]) -> LogisticsGroupRead:
        is_nested = group_key != "MONO"
        group_warnings: list[dict] = []
        if is_nested:
            master_values = {r.master_carton for r in rows if r.master_carton is not None}
            if len(master_values) != 1:
                styles = [r.vendor_style or "N/A" for r in rows]
                raise ValueError(
                    f"Nested group {group_key} su DC {dc_code} non valido: master_carton non uniforme ({styles})"
                )
            master_carton = next(iter(master_values))
            if master_carton is None or master_carton <= 0:
                raise ValueError(
                    f"Nested group {group_key} su DC {dc_code} non valido: master_carton non valorizzato."
                )
            if len(rows) <= 0 or int(master_carton) % len(rows) != 0:
                raise ValueError(
                    f"Nested group {group_key} su DC {dc_code} non valido: master_carton {int(master_carton)} "
                    f"non divisibile per numero SKU {len(rows)}."
                )

            # Regola business:
            # - nested valido se master uniforme e divisibile per numero SKU
            # - store_ready operativo = split uniforme del master
            # - ogni riga deve essere divisibile per store_ready (nessun mezzo cartone SKU)
            # - i pezzi di gruppo devono essere multipli del master (nessun mezzo cartone gruppo)
            inferred_store_ready = int(master_carton) // len(rows)
            for r in rows:
                if int(r.units or 0) % inferred_store_ready != 0:
                    raise ValueError(
                        f"Nested group {group_key} su DC {dc_code} incoerente: "
                        f"units {int(r.units or 0)} non divisibili per store_ready {inferred_store_ready} "
                        f"su {r.vendor_style}"
                    )
                # Uniformiamo comunque il dato operativo interno
                r.store_ready_pack_size = inferred_store_ready

            total_pieces_group = sum(int(r.units or 0) for r in rows)
            remainder = total_pieces_group % int(master_carton)
            if remainder != 0:
                raise ValueError(
                    f"Nested group {group_key} su DC {dc_code} incoerente: "
                    f"pezzi gruppo {total_pieces_group} non multipli del master {int(master_carton)} "
                    f"(resto {remainder})"
                )
            cartons = total_pieces_group // int(master_carton)
            pcs_per_carton = int(master_carton)
            product_cartons = cartons
        else:
            if len(rows) != 1:
                raise ValueError(f"Gruppo mono su DC {dc_code} non valido: righe multiple inattese")
            r = rows[0]
            mc = int(r.master_carton or 0)
            if mc <= 0:
                raise ValueError(
                    f"Gruppo mono su DC {dc_code} non valido: master_carton mancante per {r.vendor_style}"
                )
            if r.units % mc != 0:
                raise ValueError(
                    f"Gruppo mono su DC {dc_code}: units {r.units} non divisibili per master_carton {mc} su {r.vendor_style}"
                )
            cartons = r.units // mc
            pcs_per_carton = mc
            product_cartons = cartons

        ref = rows[0]
        cw = ref.carton_width_cm
        cd = ref.carton_depth_cm
        ch = ref.carton_height_cm
        carton_size = None
        if cw is not None and cd is not None and ch is not None:
            carton_size = f"{cw} x {cd} x {ch} cm"
        total_volume, total_pallets, pallet_warnings = self._calc_pallet_volume_and_pallets(
            cartons=cartons,
            ref=ref,
        )
        group_warnings.extend(pallet_warnings)

        gross = ref.gross_weight_per_carton
        net = ref.net_weight_per_carton
        total_gross = (gross * cartons) if gross is not None else None
        total_net = (net * cartons) if net is not None else None

        products = [
            LogisticsGroupProductRead(
                line_id=r.line_id,
                vendor_style=r.vendor_style,
                item_code=r.item_code,
                description=r.description,
                units=r.units,
                cartons=product_cartons,
                master_carton=r.master_carton,
                store_ready_pack_size=r.store_ready_pack_size,
            )
            for r in rows
        ]

        return LogisticsGroupRead(
            nest_code=(group_key if is_nested else None),
            type="nested" if is_nested else "mono",
            cartons=cartons,
            pcs_per_carton=pcs_per_carton,
            carton_size=carton_size,
            gross_weight_per_carton=gross,
            net_weight_per_carton=net,
            total_gross_weight=total_gross,
            total_net_weight=total_net,
            total_volume=total_volume,
            total_pallets=total_pallets,
            warnings=group_warnings,
            products=products,
        )

    def _build_scope(self, order, mode: str) -> LogisticsScopeSummaryRead:
        products_by_key = self.repository.get_products_by_styles([line.vendor_style for line in order.lines])
        dc_codes = self._collect_dc_codes(order, mode)
        dc_summaries: list[LogisticsDcSummaryRead] = []

        for dc_code in dc_codes:
            contexts: list[_LineCtx] = []
            for line in order.lines:
                units = self._units_for_dc(line, dc_code, mode)
                if units <= 0:
                    continue
                key = self.repository.style_key(line.vendor_style)
                product = products_by_key.get(key) if key else None
                contexts.append(
                    _LineCtx(
                        line_id=line.id,
                        vendor_style=line.vendor_style,
                        item_code=line.item_code,
                        description=line.description,
                        nest_code=self._normalize_nest(line.nest_code),
                        units=units,
                        master_carton=(
                            self._to_int(line.vend_pack)
                            or self._to_int(getattr(product, "pcs_per_crt", None))
                        ),
                        store_ready_pack_size=self._to_int(line.store_ready_pack_size),
                        cartons_per_pallet=self._to_int(getattr(product, "cartons_per_pallet", None)),
                        cartons_per_layer=self._to_int(getattr(product, "cartons_per_layer", None)),
                        layers_per_pallet=(
                            self._to_int(getattr(product, "layers_per_pallet", None))
                            or self._to_int(getattr(product, "strat_x_pl", None))
                        ),
                        pallet_width_cm=self._to_float(getattr(product, "pallet_width_cm", None)),
                        pallet_depth_cm=self._to_float(getattr(product, "pallet_depth_cm", None)),
                        carton_width_cm=self._to_float(getattr(product, "carton_width_cm", None)),
                        carton_depth_cm=self._to_float(getattr(product, "carton_depth_cm", None)),
                        carton_height_cm=self._to_float(getattr(product, "carton_height_cm", None)),
                        gross_weight_per_carton=self._to_float(getattr(product, "peso_lordo", None)),
                        net_weight_per_carton=self._to_float(getattr(product, "peso_netto", None)),
                    )
                )

            if not contexts:
                continue

            grouped: dict[str, list[_LineCtx]] = {}
            for ctx in contexts:
                if ctx.nest_code:
                    grouped.setdefault(ctx.nest_code, []).append(ctx)
                else:
                    grouped[f"MONO#{ctx.line_id}"] = [ctx]

            group_reads: list[LogisticsGroupRead] = []
            group_pallet_basis: list[tuple[int, int | None]] = []
            for key, rows in grouped.items():
                normalized_key = key.split("#", 1)[0] if key.startswith("MONO#") else key
                group_read = self._build_group(dc_code=dc_code, group_key=normalized_key, rows=rows)
                group_reads.append(group_read)
                cpp = int(self._effective_cartons_per_pallet(rows[0]) or 0) if rows else 0
                group_pallet_basis.append((int(group_read.cartons or 0), (cpp if cpp > 0 else None)))

            total_pieces = sum(p.units for g in group_reads for p in g.products)
            total_cartons = sum(g.cartons for g in group_reads)

            total_volume = sum((g.total_volume or 0.0) for g in group_reads)
            has_volume = any(g.total_volume is not None for g in group_reads)
            total_gross = sum((g.total_gross_weight or 0.0) for g in group_reads)
            has_gross = any(g.total_gross_weight is not None for g in group_reads)
            total_net = sum((g.total_net_weight or 0.0) for g in group_reads)
            has_net = any(g.total_net_weight is not None for g in group_reads)
            total_pallets = sum((g.total_pallets or 0) for g in group_reads)
            has_pallets = any(g.total_pallets is not None for g in group_reads)

            # DC-level pallet aggregation: allow sharing pallet capacity across products.
            dc_volume, dc_pallets = self._calc_dc_aggregated_pallet_metrics(
                contexts=contexts,
                group_pallet_basis=group_pallet_basis,
                total_cartons=total_cartons,
                dc_code=dc_code,
            )
            if dc_pallets is not None:
                total_pallets = dc_pallets
                has_pallets = True
            if dc_volume is not None:
                total_volume = dc_volume
                has_volume = True

            dc_summaries.append(
                LogisticsDcSummaryRead(
                    dc_code=dc_code,
                    total_pieces=total_pieces,
                    total_cartons=total_cartons,
                    total_volume=(round(total_volume, 6) if has_volume else None),
                    total_gross_weight=(round(total_gross, 3) if has_gross else None),
                    total_net_weight=(round(total_net, 3) if has_net else None),
                    total_pallets=(total_pallets if has_pallets else None),
                    groups=group_reads,
                )
            )

        scope_total_pieces = sum(dc.total_pieces for dc in dc_summaries)
        scope_total_cartons = sum(dc.total_cartons for dc in dc_summaries)
        scope_total_volume = sum((dc.total_volume or 0.0) for dc in dc_summaries)
        scope_has_volume = any(dc.total_volume is not None for dc in dc_summaries)
        scope_total_gross = sum((dc.total_gross_weight or 0.0) for dc in dc_summaries)
        scope_has_gross = any(dc.total_gross_weight is not None for dc in dc_summaries)
        scope_total_net = sum((dc.total_net_weight or 0.0) for dc in dc_summaries)
        scope_has_net = any(dc.total_net_weight is not None for dc in dc_summaries)
        scope_total_pallets = sum((dc.total_pallets or 0) for dc in dc_summaries)
        scope_has_pallets = any(dc.total_pallets is not None for dc in dc_summaries)

        return LogisticsScopeSummaryRead(
            total_pieces=scope_total_pieces,
            total_cartons=scope_total_cartons,
            total_volume=(round(scope_total_volume, 6) if scope_has_volume else None),
            total_gross_weight=(round(scope_total_gross, 3) if scope_has_gross else None),
            total_net_weight=(round(scope_total_net, 3) if scope_has_net else None),
            total_pallets=(scope_total_pallets if scope_has_pallets else None),
            dcs=dc_summaries,
        )

    def get_order_logistics_summary(self, order_id: int) -> OrderLogisticsSummaryRead:
        order = self.repository.get_order_by_id(order_id)
        if order is None:
            raise ValueError(f"Ordine non trovato: {order_id}")

        received = self._build_scope(order, mode="received")
        operational = self._build_scope(order, mode="operational")
        return OrderLogisticsSummaryRead(
            order_id=order_id,
            received=received,
            operational=operational,
        )
