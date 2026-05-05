from app.core.config import settings


DEFAULT_SUPPLIER_ALIASES = {
    "LIKING": "OLICAV SRL",
    "LIKING SRL": "OLICAV SRL",
}


def normalize_supplier_name(value: str | None) -> str | None:
    if value is None:
        return None
    txt = value.strip()
    if not txt:
        return None
    key = txt.upper()
    aliases = settings.supplier_aliases
    if key in aliases:
        return aliases[key]
    return DEFAULT_SUPPLIER_ALIASES.get(key, txt)
