from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings


@dataclass(frozen=True)
class TemplatePaths:
    root: Path
    pdf_ordini: Path
    documenti_export: Path
    ordine_fornitore: Path

    @classmethod
    def from_settings(cls) -> "TemplatePaths":
        root = settings.templates_root
        return cls(
            root=root,
            pdf_ordini=root / settings.pdf_ordini_dir,
            documenti_export=root / settings.documenti_export_dir,
            ordine_fornitore=root / settings.ordine_fornitore_dir,
        )


template_paths = TemplatePaths.from_settings()

