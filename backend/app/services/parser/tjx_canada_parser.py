import re
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader

from app.schemas.sierra_parser import ParserWarning
from app.schemas.tjx_canada_parser import TjxCanadaOrderLine, TjxCanadaParseResponse


class TjxCanadaPdfParserService:
    FAMILY_NAME = "TJX_CANADA"

    def is_tjx_canada_document(self, file_name: str, text: str) -> bool:
        upper = text.upper()
        if "IMPORT PO NUMBER" in upper and "START SHIP DATE" in upper and "VEND PACK" in upper:
            return True
        upper_name = file_name.upper()
        return any(token in upper_name for token in ["HOME SENSE", "CANADIAN MARSHALL", "CM", "WINNERS"])

    def parse_file(self, file_path: Path) -> TjxCanadaParseResponse:
        reader = PdfReader(str(file_path))
        page_texts = [(page.extract_text() or "") for page in reader.pages]
        full_text = "\n".join(page_texts)
        header_text = page_texts[0] if page_texts else ""
        lines_text = "\n".join(page_texts[1:]) if len(page_texts) > 1 else header_text

        warnings: list[ParserWarning] = []
        if not self.is_tjx_canada_document(file_path.name, full_text):
            warnings.append(
                ParserWarning(
                    code="DOCUMENT_RECOGNITION_WARNING",
                    message="Il file non rispetta pienamente i marker TJX CANADA; parsing tentato comunque.",
                )
            )

        brand = self._detect_brand_from_content(header_text)
        if brand is None:
            brand = self._detect_brand_from_filename(file_path.name)
            if brand:
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
                        message="Insegna Canada non riconosciuta.",
                    )
                )

        po_raw = self._extract_po(header_text, warnings)
        import_po = self._extract_import_po(header_text, warnings)
        start_ship_date, cancel_ship_date = self._extract_dates(header_text, warnings)
        total_units = self._extract_total_units(header_text, warnings)
        lines = self._extract_lines(lines_text, warnings)

        return TjxCanadaParseResponse(
            document_family=self.FAMILY_NAME,
            brand=brand,
            source_file=file_path.name,
            po_raw=po_raw,
            po_normalized=po_raw,
            import_po_number=import_po,
            start_ship_date=start_ship_date,
            cancel_ship_date=cancel_ship_date,
            total_units=total_units,
            lines=lines,
            warnings=warnings,
        )

    @staticmethod
    def _detect_brand_from_content(text: str) -> str | None:
        upper = text.upper()
        if "HOMESENSE" in upper or "HOME SENSE" in upper:
            return "HOME SENSE"
        if re.search(r"\bCM\b", upper) or "CANADIAN MARSHALL" in upper or "CAN MARSH" in upper:
            return "CAN MARSH"
        if "WINNERS" in upper:
            return "WINNERS"
        return None

    @staticmethod
    def _detect_brand_from_filename(file_name: str) -> str | None:
        upper = file_name.upper()
        if "HOME SENSE" in upper or "HOMESENSE" in upper:
            return "HOME SENSE"
        if "CANADIAN MARSHALL" in upper or "CAN MARSH" in upper or re.search(r"\bCM\b", upper):
            return "CAN MARSH"
        if "WINNERS" in upper:
            return "WINNERS"
        return None

    @staticmethod
    def _extract_po(text: str, warnings: list[ParserWarning]) -> str | None:
        match = re.search(r"PO:\s*([0-9]{5,10})", text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
        warnings.append(
            ParserWarning(
                code="PO_NOT_FOUND",
                message="PO non trovato nella testata Canada.",
            )
        )
        return None

    @staticmethod
    def _extract_import_po(text: str, warnings: list[ParserWarning]) -> str | None:
        match = re.search(
            r"Import PO Number:\s*([0-9]{2}\s+[0-9]{5,10})",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            return " ".join(match.group(1).split())
        warnings.append(
            ParserWarning(
                code="IMPORT_PO_NOT_FOUND",
                message="Import PO Number non trovato nella testata Canada.",
            )
        )
        return None

    @staticmethod
    def _extract_dates(
        text: str,
        warnings: list[ParserWarning],
    ) -> tuple[datetime.date | None, datetime.date | None]:
        match = re.search(
            r"DEAL CREATE DATE START SHIP DATE.*?([A-Z]{3}-\d{2}-\d{4})\s+([A-Z]{3}-\d{2}-\d{4})\s+([A-Z]{3}-\d{2}-\d{4})",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            warnings.append(
                ParserWarning(
                    code="DATES_NOT_FOUND",
                    message="Start Ship Date e/o Cancel Ship Date non trovate in testata Canada.",
                )
            )
            return None, None
        start_ship = datetime.strptime(match.group(2).upper(), "%b-%d-%Y").date()
        cancel_ship = datetime.strptime(match.group(3).upper(), "%b-%d-%Y").date()
        return start_ship, cancel_ship

    @staticmethod
    def _extract_total_units(text: str, warnings: list[ParserWarning]) -> int | None:
        match = re.search(r"Total Units:\s*\|?\s*([0-9]{1,9})", text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
        warnings.append(
            ParserWarning(
                code="TOTAL_UNITS_NOT_FOUND",
                message="Total Units non trovato in testata Canada.",
            )
        )
        return None

    def _extract_lines(
        self,
        text: str,
        warnings: list[ParserWarning],
    ) -> list[TjxCanadaOrderLine]:
        normalized = " ".join(text.split())
        raw_lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        lines: list[TjxCanadaOrderLine] = []
        seen_pgln: set[str] = set()

        # Standard case: row begins with PG/LN marker.
        pattern_start = re.compile(
            r"(\d+-\d+)\s*\|?\s*(\d{4})\s+(\d{5,6})\s+\d+\s+([A-Z0-9]+)\s+(.*?)\s+(\d+)\s+(\d+)\s+\d+\s+\d+\s+\d+",
            flags=re.IGNORECASE,
        )
        for m in pattern_start.finditer(normalized):
            row = self._build_line_from_match(
                pg_ln=m.group(1),
                item_code=m.group(3),
                vendor_style=m.group(4),
                description_raw=m.group(5),
                units=m.group(6),
                vend_pack=m.group(7),
            )
            if row.pg_ln and row.pg_ln not in seen_pgln:
                seen_pgln.add(row.pg_ln)
                lines.append(row)

        # Recovery case: marker appears at the end of row fragment.
        pattern_end = re.compile(
            r"(\d{4})\s+(\d{5,6})\s+\d+\s+([A-Z0-9]+)\s+(.*?)\s+(\d+)\s+(\d+)\s+\d+\s+\d+\s+\d+\s*\|\s*(\d+-\d+)",
            flags=re.IGNORECASE,
        )
        for m in pattern_end.finditer(normalized):
            pg_ln = m.group(7)
            if pg_ln in seen_pgln:
                continue
            row = self._build_line_from_match(
                pg_ln=pg_ln,
                item_code=m.group(2),
                vendor_style=m.group(3),
                description_raw=m.group(4),
                units=m.group(5),
                vend_pack=m.group(6),
            )
            seen_pgln.add(pg_ln)
            lines.append(row)

        # Recovery case: row data line without PG/LN, marker appears on a later line.
        pattern_no_pg = re.compile(
            r"^\s*(\d{4})\s+(\d{5,6})\s+\d+\s+([A-Z0-9]+)\s+(.*?)\s+(\d+)\s+(\d+)\s+\d+\s+\d+\s+\d+\s*$",
            flags=re.IGNORECASE,
        )
        for idx, line in enumerate(raw_lines):
            m = pattern_no_pg.match(line)
            if not m:
                continue
            pg_ln = self._find_nearby_pgln(raw_lines, idx)
            if not pg_ln or pg_ln in seen_pgln:
                continue
            row = self._build_line_from_match(
                pg_ln=pg_ln,
                item_code=m.group(2),
                vendor_style=m.group(3),
                description_raw=m.group(4),
                units=m.group(5),
                vend_pack=m.group(6),
            )
            seen_pgln.add(pg_ln)
            lines.append(row)

        lines.sort(key=lambda x: self._pgln_sort_key(x.pg_ln))

        if not lines:
            warnings.append(
                ParserWarning(
                    code="LINES_NOT_FOUND",
                    message="Nessuna riga prodotto Canada trovata nelle pagine successive.",
                )
            )
            return []

        expected = self._expected_pgln_sequence(lines)
        if expected and len(expected) != len(lines):
            warnings.append(
                ParserWarning(
                    code="ROWS_GAP_WARNING",
                    message="Possibile perdita righe: sequenza PG/LN non continua.",
                    context={"found_pgln": ",".join(x.pg_ln or "" for x in lines)},
                )
            )
        return lines

    @staticmethod
    def _find_nearby_pgln(lines: list[str], row_idx: int) -> str | None:
        for look_ahead in range(1, 10):
            probe = row_idx + look_ahead
            if probe >= len(lines):
                break
            m = re.match(r"^\s*(\d+-\d+)\s*$", lines[probe])
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _build_line_from_match(
        pg_ln: str,
        item_code: str,
        vendor_style: str,
        description_raw: str,
        units: str,
        vend_pack: str,
    ) -> TjxCanadaOrderLine:
        clean_desc = re.sub(r"\s+", " ", description_raw).strip()
        return TjxCanadaOrderLine(
            pg_ln=pg_ln,
            vendor_style=re.sub(r"[^A-Z0-9]", "", vendor_style.upper()),
            item_code=item_code,
            detailed_description=clean_desc,
            description=clean_desc,
            units=int(units),
            total_units=int(units),
            vend_pack=int(vend_pack),
        )

    @staticmethod
    def _pgln_sort_key(pg_ln: str | None) -> tuple[int, int]:
        if not pg_ln:
            return (999, 999)
        m = re.match(r"(\d+)-(\d+)", pg_ln)
        if not m:
            return (999, 999)
        return (int(m.group(1)), int(m.group(2)))

    @staticmethod
    def _expected_pgln_sequence(lines: list[TjxCanadaOrderLine]) -> list[str]:
        pgln_nums = []
        for line in lines:
            if not line.pg_ln:
                continue
            m = re.match(r"(\d+)-(\d+)", line.pg_ln)
            if not m:
                continue
            pgln_nums.append((int(m.group(1)), int(m.group(2))))
        if not pgln_nums:
            return []
        page = pgln_nums[0][0]
        min_ln = min(ln for pg, ln in pgln_nums if pg == page)
        max_ln = max(ln for pg, ln in pgln_nums if pg == page)
        return [f"{page}-{i}" for i in range(min_ln, max_ln + 1)]
