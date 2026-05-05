import re
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader

from app.schemas.sierra_parser import ParserWarning, SierraOrderLine, SierraParseResponse


class SierraPdfParserService:
    FAMILY_NAME = "SIERRA"

    def is_sierra_document(self, file_name: str, page_1_text: str | None = None) -> bool:
        upper_name = file_name.upper()
        if "SIERRA" in upper_name:
            return True
        if page_1_text:
            upper_text = page_1_text.upper()
            return "SIERRATRADINGPOST" in upper_text or "VENDOR COPY REPORT" in upper_text
        return False

    def parse_file(self, file_path: Path) -> SierraParseResponse:
        reader = PdfReader(str(file_path))
        page_texts = [(page.extract_text() or "") for page in reader.pages]
        page_1 = page_texts[0] if page_texts else ""
        page_2 = page_texts[1] if len(page_texts) > 1 else ""

        warnings: list[ParserWarning] = []
        if not self.is_sierra_document(file_path.name, page_1):
            warnings.append(
                ParserWarning(
                    code="NOT_SIERRA",
                    message="Il file non sembra appartenere alla famiglia SIERRA.",
                    page=1,
                )
            )

        start_ship_date, cancel_ship_date = self._extract_ship_dates(page_1, warnings)

        distribution_center = self._extract_distribution_center(page_2 or page_1, warnings)
        dc_name, dc_address = self._extract_distribution_center_details(
            page_2 or page_1,
            distribution_center,
        )
        po_raw = self._extract_po_raw(page_2 or page_1, warnings)
        po_normalized = self._normalize_po(po_raw, warnings)

        lines = self._extract_lines_from_page_2(page_2, warnings)
        if not lines:
            warnings.append(
                ParserWarning(
                    code="LINES_NOT_FOUND",
                    message="Nessuna riga articolo valida trovata in pagina 2.",
                    page=2,
                )
            )

        return SierraParseResponse(
            document_family=self.FAMILY_NAME,
            source_file=file_path.name,
            start_ship_date=start_ship_date,
            cancel_ship_date=cancel_ship_date,
            distribution_center=distribution_center,
            distribution_center_name=dc_name,
            distribution_center_address=dc_address,
            po_raw=po_raw,
            po_normalized=po_normalized,
            lines=lines,
            warnings=warnings,
        )

    @staticmethod
    def _extract_ship_dates(text: str, warnings: list[ParserWarning]):
        pair_pattern = r"Start Ship Date\s+Cancel Ship Date.*?(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}/\d{1,2}/\d{4})"
        pair_match = re.search(pair_pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if pair_match:
            return (
                datetime.strptime(pair_match.group(1), "%m/%d/%Y").date(),
                datetime.strptime(pair_match.group(2), "%m/%d/%Y").date(),
            )

        start_match = re.search(r"Start Ship Date\s+(\d{1,2}/\d{1,2}/\d{4})", text, flags=re.IGNORECASE)
        cancel_match = re.search(r"Cancel Ship Date\s+(\d{1,2}/\d{1,2}/\d{4})", text, flags=re.IGNORECASE)

        start_ship_date = (
            datetime.strptime(start_match.group(1), "%m/%d/%Y").date() if start_match else None
        )
        cancel_ship_date = (
            datetime.strptime(cancel_match.group(1), "%m/%d/%Y").date() if cancel_match else None
        )

        if start_ship_date is None:
            warnings.append(
                ParserWarning(
                    code="DATE_NOT_FOUND",
                    message="Campo data non trovato: Start Ship Date",
                    page=1,
                    context={"field": "Start Ship Date"},
                )
            )
        if cancel_ship_date is None:
            warnings.append(
                ParserWarning(
                    code="DATE_NOT_FOUND",
                    message="Campo data non trovato: Cancel Ship Date",
                    page=1,
                    context={"field": "Cancel Ship Date"},
                )
            )

        return start_ship_date, cancel_ship_date

    @staticmethod
    def _extract_distribution_center(text: str, warnings: list[ParserWarning]) -> str | None:
        patterns = [
            r"Distribution Center\s*[\r\n ]+(\d{4})",
            r"TJX\s*-?\s*Sierra\s*DC\s+(\d{4})",
            r"DC\s*#:\s*(\d{4})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1)

        warnings.append(
            ParserWarning(
                code="DC_NOT_FOUND",
                message="Distribution Center non trovato nel PDF SIERRA.",
                page=2,
            )
        )
        return None

    @staticmethod
    def _extract_po_raw(text: str, warnings: list[ParserWarning]) -> str | None:
        patterns = [
            r"PO\s*#:\s*(\d{4})\s*([A-Z]{2})\s*(\d{5,10})",
            r"PO\s*#:\s*(\d{4}[A-Z]{2}\d{5,10})",
            r"(\d{4}[A-Z]{2}\d{5,10})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                if match.lastindex == 3:
                    return f"{match.group(1)}{match.group(2)}{match.group(3)}".upper()
                return match.group(1).upper()

        warnings.append(
            ParserWarning(
                code="PO_NOT_FOUND",
                message="PO completo non trovato nel PDF SIERRA.",
                page=2,
            )
        )
        return None

    @staticmethod
    def _extract_distribution_center_details(
        text: str,
        dc_code: str | None,
    ) -> tuple[str | None, str | None]:
        dc_name = None
        dc_address = None

        name_match = re.search(r"\b([A-Z]{3})\s*:\s*([A-Za-z ]+)", text)
        if name_match:
            dc_name = " ".join(name_match.group(2).split())

        if dc_code:
            addr_match = re.search(
                rf"DC\s*#:\s*{re.escape(dc_code)}\s*(.*?)\s*Vendor Styles",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if addr_match:
                dc_address = " ".join(addr_match.group(1).split())
            else:
                alt_match = re.search(
                    rf"DC\s*#:\s*{re.escape(dc_code)}\s*(.*)",
                    text,
                    flags=re.IGNORECASE,
                )
                if alt_match:
                    dc_address = " ".join(alt_match.group(1).split())

        return dc_name, dc_address

    @staticmethod
    def _normalize_po(po_raw: str | None, warnings: list[ParserWarning]) -> str | None:
        if not po_raw:
            return None

        match = re.search(r"^\d{4}([A-Z]{2}\d{5,10})$", po_raw)
        if not match:
            warnings.append(
                ParserWarning(
                    code="PO_NORMALIZATION_WARNING",
                    message="PO raw non nel formato atteso con prefisso DC.",
                    context={"po_raw": po_raw},
                )
            )
            return f"{po_raw} R"

        return f"{match.group(1)} R"

    def _extract_lines_from_page_2(self, page_2_text: str, warnings: list[ParserWarning]) -> list[SierraOrderLine]:
        if not page_2_text.strip():
            warnings.append(
                ParserWarning(
                    code="PAGE_2_EMPTY",
                    message="Pagina 2 vuota o non leggibile.",
                    page=2,
                )
            )
            return []

        dc_columns = re.findall(r"(\d{4})\s+Units", page_2_text)
        tokens = [line.strip() for line in page_2_text.splitlines() if line.strip()]

        try:
            header_idx = tokens.index("Vendor Styles")
        except ValueError:
            warnings.append(
                ParserWarning(
                    code="TABLE_HEADER_NOT_FOUND",
                    message="Header tabella righe non trovato in pagina 2.",
                    page=2,
                )
            )
            return []

        data_tokens = tokens[header_idx + 1 :]
        lines: list[SierraOrderLine] = []
        idx = 0

        while idx < len(data_tokens):
            if data_tokens[idx].upper() == "PAGE":
                break
            if data_tokens[idx].isdigit() and idx + 1 < len(data_tokens) and data_tokens[idx + 1].upper() == "PAGE":
                break

            if not self._looks_like_vendor_style_start(data_tokens[idx]):
                idx += 1
                continue

            row, next_idx = self._parse_row(data_tokens, idx, dc_columns, warnings)
            if row:
                lines.append(row)
                idx = next_idx
            else:
                idx += 1

        return lines

    @staticmethod
    def _looks_like_vendor_style_start(token: str) -> bool:
        return bool(re.match(r"^[A-Z0-9]{4,}$", token))

    @staticmethod
    def _is_numeric_token(token: str) -> bool:
        normalized = token.replace(",", "").strip()
        return normalized.isdigit()

    @staticmethod
    def _to_int(token: str) -> int | None:
        normalized = token.replace(",", "").strip()
        if normalized.isdigit():
            return int(normalized)
        return None

    def _parse_row(
        self,
        tokens: list[str],
        start_idx: int,
        dc_columns: list[str],
        warnings: list[ParserWarning],
    ) -> tuple[SierraOrderLine | None, int]:
        idx = start_idx

        vendor_style_raw, vendor_style_normalized, idx = self._extract_vendor_style(tokens, idx)

        item_code = None
        if idx < len(tokens) and re.match(r"^[A-Z0-9]{2,}-\d{2,}$", tokens[idx]):
            item_code = tokens[idx]
            idx += 1

        color_index = None
        for j in range(idx, len(tokens) - 3):
            if self._is_numeric_token(tokens[j]):
                continue
            if (
                self._is_numeric_token(tokens[j + 1])
                and self._is_numeric_token(tokens[j + 2])
                and self._is_numeric_token(tokens[j + 3])
            ):
                color_index = j
                break

        if color_index is None:
            warnings.append(
                ParserWarning(
                    code="ROW_PARSE_WARNING",
                    message="Riga articolo non parsata completamente.",
                    page=2,
                    context={
                        "vendor_style_raw": vendor_style_raw or tokens[start_idx],
                        "vendor_style_normalized": vendor_style_normalized or "",
                    },
                )
            )
            return None, start_idx + 1

        description = " ".join(tokens[idx:color_index]).strip() or None
        total_units = self._to_int(tokens[color_index + 1])
        dc_values = [self._to_int(tokens[color_index + 2]), self._to_int(tokens[color_index + 3])]
        units_per_dc: dict[str, int] = {}
        for dc_code, value in zip(dc_columns, dc_values):
            if value is not None:
                units_per_dc[dc_code] = value

        row = SierraOrderLine(
            vendor_style=vendor_style_normalized or None,
            item_code=item_code,
            description=description,
            total_units=total_units,
            units_per_dc=units_per_dc,
        )
        return row, color_index + 4

    def _extract_vendor_style(self, tokens: list[str], start_idx: int) -> tuple[str, str, int]:
        # Keep raw and normalized separate: raw mirrors PDF extraction,
        # normalized removes artificial separators (spaces/commas/punctuation).
        parts: list[str] = []
        idx = start_idx
        while idx < len(tokens):
            token = tokens[idx]
            if re.match(r"^[A-Z0-9]{2,}-\d{2,}$", token):
                break
            if token == ",":
                parts.append(token)
                idx += 1
                continue
            if re.match(r"^[A-Z0-9]+$", token):
                parts.append(token)
                idx += 1
                continue
            break

        raw = " ".join(part for part in parts if part != ",").strip()
        normalized = self._normalize_vendor_style(raw)
        return raw, normalized, idx

    @staticmethod
    def _normalize_vendor_style(vendor_style_raw: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", vendor_style_raw.upper())
