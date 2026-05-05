import re
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader

from app.schemas.sierra_parser import ParserWarning
from app.schemas.tjx_usa_parser import TjxUsaOrderLine, TjxUsaParseResponse


class TjxUsaPdfParserService:
    FAMILY_NAME = "TJX_USA"

    def is_tjx_usa_document(self, file_name: str, text: str) -> bool:
        upper_text = text.upper()
        if "ROUTING AND DISTRIBUTION INSTRUCTIONS" not in upper_text:
            return False
        if self._detect_brand_from_content(text) is not None:
            return True
        upper_name = file_name.upper()
        return any(k in upper_name for k in ["TJMAXX", "TJ MAXX", "MARSHALLS", "HOMEGOODS"])

    def parse_file(self, file_path: Path) -> TjxUsaParseResponse:
        reader = PdfReader(str(file_path))
        page_texts = [(page.extract_text() or "") for page in reader.pages]
        full_text = "\n".join(page_texts)

        warnings: list[ParserWarning] = []
        if not self.is_tjx_usa_document(file_path.name, full_text):
            warnings.append(
                ParserWarning(
                    code="DOCUMENT_RECOGNITION_WARNING",
                    message="Il file non rispetta pienamente i marker TJX USA; parsing tentato comunque.",
                )
            )

        brand = self._detect_brand_from_content(full_text)
        if brand is None:
            brand = self._detect_brand_from_filename(file_path.name)
            if brand:
                # In alcuni layout reali TJX USA il logo/insegna non viene estratto come testo
                # (rimane solo il blocco "An Affiliate of The TJX Companies").
                # In questi casi il fallback da filename è atteso e non deve generare warning rumoroso.
                if not self._has_generic_tjx_header_marker(full_text):
                    warnings.append(
                        ParserWarning(
                            code="BRAND_FALLBACK_FILENAME",
                            message="Insegna non trovata in contenuto; usato fallback dal nome file.",
                            context={"brand": brand},
                        )
                    )
            else:
                warnings.append(
                    ParserWarning(
                        code="BRAND_NOT_FOUND",
                        message="Insegna non riconosciuta dal documento TJX USA.",
                    )
                )

        po_raw = self._extract_po_number(full_text, warnings)
        po_normalized = po_raw
        supplier_name = self._extract_primary_vendor(full_text, warnings)
        start_ship_date, cancel_ship_date = self._extract_ship_dates(full_text, warnings)
        dc_list = self._extract_distribution_centers(full_text, warnings)
        lines = self._extract_lines(page_texts, dc_list, warnings)

        return TjxUsaParseResponse(
            document_family=self.FAMILY_NAME,
            brand=brand,
            supplier_name=supplier_name,
            source_file=file_path.name,
            po_raw=po_raw,
            po_normalized=po_normalized,
            start_ship_date=start_ship_date,
            cancel_ship_date=cancel_ship_date,
            distribution_centers=dc_list,
            lines=lines,
            warnings=warnings,
        )

    @staticmethod
    def _detect_brand_from_content(text: str) -> str | None:
        upper = text.upper()
        if "HOMEGOODS" in upper or "HGDS" in upper:
            return "HOMEGOODS"
        if "MARSHALLS" in upper or re.search(r"\bMAR:\s", upper) or re.search(r"\bMAR\s+[A-Z]{2,}", upper):
            return "MARSHALLS"
        if "TJ MAXX" in upper or "TJMAXX" in upper or re.search(r"\bTJM\b", upper):
            return "TJ MAXX"
        return None

    @staticmethod
    def _has_generic_tjx_header_marker(text: str) -> bool:
        upper = text.upper()
        return bool(
            re.search(r"ROUTING\s+AND\s+DISTRIBUTION\s+INSTRUCTIONS", upper)
            and re.search(r"AN\s+AFFILIATE\s+OF\s+THE", upper)
            and re.search(r"\bTJX\b", upper)
            and re.search(r"C\s*O\s*M\s*P\s*A\s*N\s*I\s*E\s*S", upper)
        )

    @staticmethod
    def _detect_brand_from_filename(file_name: str) -> str | None:
        upper = file_name.upper()
        if "HOMEGOODS" in upper:
            return "HOMEGOODS"
        if "MARSHALLS" in upper:
            return "MARSHALLS"
        if "TJMAXX" in upper or "TJ MAXX" in upper:
            return "TJ MAXX"
        return None

    @staticmethod
    def _extract_po_number(text: str, warnings: list[ParserWarning]) -> str | None:
        match = re.search(r"PO\s*Number:\s*([0-9]{5,10})", text, flags=re.IGNORECASE)
        if match:
            return match.group(1)

        match = re.search(r"PO\s*#:\s*\d{2}\s+([0-9]{5,10})", text, flags=re.IGNORECASE)
        if match:
            return match.group(1)

        warnings.append(
            ParserWarning(
                code="PO_NOT_FOUND",
                message="PO numero testata non trovato.",
            )
        )
        return None

    @staticmethod
    def _extract_ship_dates(
        text: str, warnings: list[ParserWarning]
    ) -> tuple[datetime.date | None, datetime.date | None]:
        # Expected sequence near header: Order Date, Start Ship Date, Cancel Date
        pattern = (
            r"Order Date\s*Start Ship\s*Date.*?Cancel Date.*?"
            r"(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}/\d{1,2}/\d{4})"
        )
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return (
                datetime.strptime(match.group(2), "%m/%d/%Y").date(),
                datetime.strptime(match.group(3), "%m/%d/%Y").date(),
            )

        warnings.append(
            ParserWarning(
                code="DATES_NOT_FOUND",
                message="Start Ship Date e/o Cancel Date non trovate in testata.",
            )
        )
        return None, None

    @staticmethod
    def _extract_primary_vendor(text: str, warnings: list[ParserWarning]) -> str | None:
        patterns = [
            r"PRIMARY\s+VENDOR\s+ATTENTION\s+DEAL\s*#\s+CIR\s*#.*?\bF\s+([A-Z0-9&.,'\/\-\s]{3,}?)\s+D[0-9A-Z]{4,}",
            r"Primary\s+Vendor\s*:?\s*([A-Z0-9&.,'\/\-\s]{3,}?)\s+(?:Deal\s*#|CIR\s*#|Special\s+Vendor\s+Instructions)",
            r"Primary\s+Vendor\s*:?\s*([A-Z0-9&.,'\/\-\s]{3,}?)\s+Special\s+Vendor\s+Instructions",
            r"PRIMARY\s+VENDOR\s+([A-Z0-9&.,'\/\-\s]{3,}?)\s+(?:ATTENTION|WORKSHEET|CIR|W\d{6,})",
        ]
        normalized_text = re.sub(r"\s+", " ", text.upper())
        for pattern in patterns:
            match = re.search(pattern, normalized_text, flags=re.IGNORECASE | re.DOTALL)
            if not match:
                continue
            value = re.sub(r"\s+", " ", match.group(1)).strip(" -:")
            if value and value not in {"ATTENTION", "DEAL", "CIR", "PRIMARY VENDOR"}:
                return value
        warnings.append(
            ParserWarning(
                code="SUPPLIER_NOT_FOUND",
                message="Primary Vendor non trovato nel documento TJX USA.",
            )
        )
        return None

    @staticmethod
    def _extract_distribution_centers(text: str, warnings: list[ParserWarning]) -> list[str]:
        dc_list: list[str] = []
        for dc in re.findall(r"DC\s*#\s*:?\s*(\d{3,4})", text, flags=re.IGNORECASE):
            if dc not in dc_list:
                dc_list.append(dc)

        if not dc_list:
            warnings.append(
                ParserWarning(
                    code="DC_NOT_FOUND",
                    message="Nessun Distribution Center trovato nel file.",
                )
            )
        return dc_list

    def _extract_lines(
        self,
        page_texts: list[str],
        dc_list: list[str],
        warnings: list[ParserWarning],
    ) -> list[TjxUsaOrderLine]:
        row_blocks: list[str] = []
        for page_text in page_texts:
            table_text = self._extract_table_text_from_page(page_text)
            raw_lines = [ln.strip() for ln in table_text.splitlines() if ln.strip()]
            start_indexes: list[int] = [
                i for i, line in enumerate(raw_lines) if self._is_row_start_line(line)
            ]
            for pos, start in enumerate(start_indexes):
                end = start_indexes[pos + 1] if pos + 1 < len(start_indexes) else len(raw_lines)
                block = "\n".join(raw_lines[start:end])
                row_blocks.extend(self._split_inline_rows(block))

        lines: list[TjxUsaOrderLine] = []

        for block in row_blocks:
            row = self._parse_row_block(block, dc_list, warnings)
            if row is not None:
                lines.append(row)

        if not lines:
            warnings.append(
                ParserWarning(
                    code="LINES_NOT_FOUND",
                    message="Nessuna riga prodotto valida trovata.",
                )
            )
        return lines

    @staticmethod
    def _extract_table_text_from_page(page_text: str) -> str:
        text = page_text or ""
        # Robust header detection for variants like:
        # - PG/LN
        # - PG/ L N
        # - PG - LN
        # - PG/\nL N
        start_match = re.search(r"\bPG\s*[-/]?\s*L\s*N\b", text, flags=re.IGNORECASE)
        if not start_match:
            # Fallback to product-table column header when PG/LN is fragmented by extraction.
            start_match = re.search(r"\bVendor\s*Style\s*#\b", text, flags=re.IGNORECASE)
        if start_match:
            text = text[start_match.start() :]

        # Stop at footer/instructions block, accounting for OCR/text spacing variants.
        # NOTE: do not split on "ROUTING AND DISTRIBUTION INSTRUCTIONS" here:
        # when table start isn't detected, that marker appears at page top and would truncate all content.
        text = re.split(
            r"Go\s*to\s*TJX'?S\s*Logistics\s*Website|Page\s+\d+\s+of\s+\d+",
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        return text

    @staticmethod
    def _is_row_start_line(line: str) -> bool:
        if not re.match(r"^\d+(?:/|-)\d+\b", line):
            return False
        # Reject dates such as 04/08/2026.
        if line.count("/") > 1:
            return False
        return True

    @staticmethod
    def _split_inline_rows(block: str) -> list[str]:
        flat = " ".join(part.strip() for part in block.splitlines() if part.strip())
        starts = list(re.finditer(r"(?<!\d)\d+(?:/|-)\d+\s+[A-Z0-9]", flat))
        if len(starts) <= 1:
            return [block]

        segments: list[str] = []
        for i, match in enumerate(starts):
            start = match.start()
            end = starts[i + 1].start() if i + 1 < len(starts) else len(flat)
            segments.append(flat[start:end].strip())
        return segments

    def _parse_row_block(
        self,
        block: str,
        dc_list: list[str],
        warnings: list[ParserWarning],
    ) -> TjxUsaOrderLine | None:
        # Extract and drop leading PG/LN token (e.g. 1/1 or 1-1).
        lines = [part.strip() for part in block.splitlines() if part.strip()]
        if not lines:
            return None
        pg_ln_match = re.match(r"^(\d+(?:/|-)\d+)\s*", lines[0])
        pg_ln = pg_ln_match.group(1) if pg_ln_match else None
        first = re.sub(r"^\d+(?:/|-)\d+\s*", "", lines[0]).strip()
        lines[0] = first
        flat = " ".join(part for part in lines if part)
        tokens = flat.split()

        item_idx = self._find_item_code_index(tokens)
        if item_idx is None or item_idx == 0:
            warnings.append(
                ParserWarning(
                    code="ROW_PARSE_WARNING",
                    message="Impossibile identificare item_code in una riga.",
                    context={"row_fragment": flat[:200]},
                )
            )
            return None

        vendor_style_raw = " ".join(tokens[:item_idx])
        vendor_style = self._normalize_vendor_style(vendor_style_raw)
        tjx_style = tokens[item_idx]
        item_code = tjx_style

        # Expected tail: [optional pack/store-ready/nest] + total + dc units...
        tail_numeric_count = len(dc_list) + 1
        if len(tokens) < item_idx + 1 + tail_numeric_count:
            warnings.append(
                ParserWarning(
                    code="ROW_PARSE_WARNING",
                    message="Riga con colonne quantità insufficienti.",
                    context={"item_code": item_code},
                )
            )
            return None

        numeric_tail = tokens[-tail_numeric_count:]
        if not all(self._is_int_token(t) for t in numeric_tail):
            warnings.append(
                ParserWarning(
                    code="ROW_PARSE_WARNING",
                    message="Tail numerico non valido per total/DC units.",
                    context={"item_code": item_code},
                )
            )
            return None

        total_units = self._to_int(numeric_tail[0])
        dc_values = [self._to_int(v) or 0 for v in numeric_tail[1:]]
        units_per_dc = {dc: val for dc, val in zip(dc_list, dc_values, strict=False)}

        pre_total_tokens = tokens[item_idx + 1 : -tail_numeric_count]
        description, nest_code, vendor_pack_size, store_ready_pack_size = self._extract_description_and_nest(
            pre_total_tokens
        )
        normalized_nest = self._normalize_nest_code(nest_code)
        line_dc = self._infer_line_distribution_center(units_per_dc)

        return TjxUsaOrderLine(
            pg_ln=pg_ln,
            vendor_style=vendor_style or None,
            tjx_style=tjx_style,
            item_code=item_code,
            description=description or None,
            total_units=total_units,
            vendor_pack_size=vendor_pack_size,
            store_ready_pack_size=store_ready_pack_size,
            nest_code=normalized_nest,
            distribution_center=line_dc,
            units_per_dc=units_per_dc,
        )

    @staticmethod
    def _find_item_code_index(tokens: list[str]) -> int | None:
        for i, tok in enumerate(tokens):
            if re.fullmatch(r"\d{5,10}", tok):
                return i
        return None

    @staticmethod
    def _normalize_vendor_style(raw: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", raw.upper())

    @staticmethod
    def _extract_description_and_nest(tokens: list[str]) -> tuple[str, str | None, int | None, int | None]:
        # Heuristic for tail metadata near Total Units columns:
        # [description ...] [vendor_pack_size] [store_ready_pack_size] [nest_code]
        if not tokens:
            return "", None, None, None

        work = list(tokens)
        nest_candidate: str | None = None
        vendor_pack_size: int | None = None
        store_ready_pack_size: int | None = None

        # In alcuni PDF reali il Vendor Pack Size non viene estratto, mentre Store Ready + Nest sì:
        # "... <store_ready_pack> <NEST>" (es. "... 9 A").
        # Manteniamo anche il caso completo "... <vendor_pack> <store_ready_pack> <NEST>".
        if work and re.fullmatch(r"[A-Z]", work[-1]):
            nest_candidate = work.pop()

        trailing_numbers: list[int] = []
        while work and re.fullmatch(r"\d{1,4}", work[-1]) and len(trailing_numbers) < 2:
            trailing_numbers.append(int(work.pop()))
        trailing_numbers.reverse()

        if nest_candidate is not None:
            if len(trailing_numbers) == 2:
                vendor_pack_size = trailing_numbers[0]
                store_ready_pack_size = trailing_numbers[1]
            elif len(trailing_numbers) == 1:
                store_ready_pack_size = trailing_numbers[0]
        else:
            if len(trailing_numbers) == 2:
                vendor_pack_size = trailing_numbers[0]
                store_ready_pack_size = trailing_numbers[1]
            elif len(trailing_numbers) == 1:
                # Mono fallback: un solo numero in coda = pack size della riga.
                vendor_pack_size = trailing_numbers[0]

        if store_ready_pack_size is not None and store_ready_pack_size <= 0:
            store_ready_pack_size = None
        if vendor_pack_size is not None and vendor_pack_size <= 0:
            vendor_pack_size = None

        description = " ".join(work).strip()
        return description, nest_candidate, vendor_pack_size, store_ready_pack_size

    @staticmethod
    def _normalize_nest_code(nest_code: str | None) -> str | None:
        if nest_code is None:
            return None
        value = nest_code.strip().upper()
        if value in {"", "0", "-", "NA", "N/A", "NONE", "MONO", "SINGLE", "NULL", "NO"}:
            return None
        if not re.fullmatch(r"[A-Z][A-Z0-9]{0,3}", value):
            return None
        return value

    @staticmethod
    def _infer_line_distribution_center(units_per_dc: dict[str, int]) -> str | None:
        non_zero = [dc for dc, qty in units_per_dc.items() if qty > 0]
        if len(non_zero) == 1:
            return non_zero[0]
        return None

    @staticmethod
    def _is_int_token(token: str) -> bool:
        return token.replace(",", "").isdigit()

    @staticmethod
    def _to_int(token: str) -> int | None:
        cleaned = token.replace(",", "")
        return int(cleaned) if cleaned.isdigit() else None
