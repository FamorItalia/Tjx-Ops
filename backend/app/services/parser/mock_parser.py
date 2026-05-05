import re

from app.schemas.parser import ParserTestResponse


class MockPdfParserService:
    @staticmethod
    def _detect_family(file_name: str) -> tuple[str, str | None]:
        upper = file_name.upper()
        if "SIERRA" in upper:
            return "SIERRA", "SIERRA"
        if "TJMAXX" in upper or "TJ MAXX" in upper:
            return "TJX_USA", "TJ MAXX"
        if "MARSHALLS" in upper:
            return "TJX_USA", "MARSHALLS"
        if "HOMEGOODS" in upper:
            return "TJX_USA", "HOMEGOODS"
        if "HOME SENSE" in upper:
            return "TJX_CANADA", "HOME SENSE"
        if "CAN MARSH" in upper:
            return "TJX_CANADA", "CAN MARSH"
        if "WINNERS" in upper:
            return "TJX_CANADA", "WINNERS"
        return "UNKNOWN", None

    @staticmethod
    def _guess_po(file_name: str) -> str | None:
        po_patterns = [
            r"PO#\s*([A-Z0-9]+)",
            r"PO\s*#\s*([A-Z0-9]+)",
            r"_([0-9]{6,9})_",
        ]
        for pattern in po_patterns:
            match = re.search(pattern, file_name, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def parse_test(self, file_name: str) -> ParserTestResponse:
        family, brand = self._detect_family(file_name=file_name)
        po = self._guess_po(file_name=file_name)
        notes = [
            "Mock parser iniziale: riconoscimento basato sul nome file.",
            "Nel prossimo step il parser usera contenuto PDF reale (testo + OCR fallback).",
        ]
        return ParserTestResponse(
            parser_family=family,
            file_name=file_name,
            po_number_guess=po,
            brand_guess=brand,
            notes=notes,
        )

