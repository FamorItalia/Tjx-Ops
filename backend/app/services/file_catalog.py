from pathlib import Path
import re

from app.core.paths import template_paths
from app.schemas.files import PdfFileInfo


class FileCatalogService:
    @staticmethod
    def guess_parser_family(file_name: str) -> str:
        name = file_name.upper()
        if any(k in name for k in ["HOME SENSE", "WINNERS", "CAN MARSH", "CANADIAN MARSHALLS"]):
            return "tjx_canada"
        if any(k in name for k in ["TJMAXX", "TJ MAXX", "MARSHALLS", "HOMEGOODS"]):
            return "tjx_usa"
        return "sierra"

    def detect_parser_family(self, file_info: PdfFileInfo) -> str:
        # First pass from file name (fast heuristic)
        guessed = self.guess_parser_family(file_info.file_name)
        if guessed != "sierra":
            return guessed

        # Second pass from PDF content (robust for Canada file names like 24_63_...).
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(file_info.absolute_path))
            sample_text = "\n".join((p.extract_text() or "") for p in reader.pages[:3])
        except Exception:
            return guessed

        try:
            from app.services.parser.tjx_canada_parser import TjxCanadaPdfParserService
            from app.services.parser.tjx_usa_parser import TjxUsaPdfParserService
            from app.services.parser.sierra_parser import SierraPdfParserService

            canada = TjxCanadaPdfParserService()
            if canada.is_tjx_canada_document(file_info.file_name, sample_text):
                return "tjx_canada"

            usa = TjxUsaPdfParserService()
            if usa.is_tjx_usa_document(file_info.file_name, sample_text):
                return "tjx_usa"

            sierra = SierraPdfParserService()
            if sierra.is_sierra_document(file_info.file_name, sample_text):
                return "sierra"
        except Exception:
            return guessed

        return guessed

    @staticmethod
    def _safe_file_name(file_name: str) -> str:
        base = Path(file_name).name
        if not base:
            return "upload.pdf"
        stem = Path(base).stem
        suffix = Path(base).suffix or ".pdf"
        safe_stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", stem).strip(" ._")
        if not safe_stem:
            safe_stem = "upload"
        return f"{safe_stem}{suffix}"

    def save_uploaded_pdf(self, file_name: str, content: bytes) -> PdfFileInfo:
        target_dir = template_paths.pdf_ordini
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_name = self._safe_file_name(file_name)
        if not safe_name.lower().endswith(".pdf"):
            safe_name = f"{Path(safe_name).stem}.pdf"

        target = target_dir / safe_name
        if target.exists():
            stem = target.stem
            suffix = target.suffix
            idx = 1
            while True:
                candidate = target_dir / f"{stem}_{idx}{suffix}"
                if not candidate.exists():
                    target = candidate
                    break
                idx += 1

        target.write_bytes(content)
        stat = target.stat()
        return PdfFileInfo(
            file_name=target.name,
            absolute_path=target.resolve(),
            source_folder="PDF ORDINI",
            size_bytes=stat.st_size,
        )

    @staticmethod
    def _iter_pdf_files(folder: Path, source_folder: str) -> list[PdfFileInfo]:
        if not folder.exists():
            return []

        files: list[PdfFileInfo] = []
        for item in sorted(folder.iterdir(), key=lambda x: x.name.lower()):
            if item.is_file() and item.suffix.lower() == ".pdf":
                stat = item.stat()
                files.append(
                    PdfFileInfo(
                        file_name=item.name,
                        absolute_path=item.resolve(),
                        source_folder=source_folder,
                        size_bytes=stat.st_size,
                    )
                )
        return files

    def list_all_pdfs(self) -> list[PdfFileInfo]:
        return [
            *self._iter_pdf_files(template_paths.pdf_ordini, "PDF ORDINI"),
            *self._iter_pdf_files(template_paths.documenti_export, "DOCUMENTI EXPORT"),
            *self._iter_pdf_files(template_paths.ordine_fornitore, "ORDINE A FORNITORE"),
        ]

    def find_pdf_by_name(self, file_name: str) -> PdfFileInfo | None:
        for pdf in self.list_all_pdfs():
            if pdf.file_name == file_name:
                return pdf
        return None
