from pathlib import Path
import json

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = Field(default="TJX Operativita API", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    debug: bool = Field(default=True, alias="DEBUG")

    sqlite_db_path: str = Field(default="./data/tjx_operativita.db", alias="SQLITE_DB_PATH")

    templates_root: Path = Field(
        default=Path("C:/Progetti/Tjx operatività/TEMPLATES"),
        alias="TEMPLATES_ROOT",
    )
    pdf_ordini_dir: str = Field(default="PDF ORDINI", alias="PDF_ORDINI_DIR")
    documenti_export_dir: str = Field(default="DOCUMENTI EXPORT", alias="DOCUMENTI_EXPORT_DIR")
    ordine_fornitore_dir: str = Field(default="ORDINE A FORNITORE", alias="ORDINE_FORNITORE_DIR")
    supplier_aliases_json: str = Field(default="{}", alias="SUPPLIER_ALIASES_JSON")
    document_logo_path: Path = Field(
        default=Path(
            "C:/Users/Tommaso/OneDrive - FAMOR ITALIA/COMUNI/MODULI/LOGHI/FAMOR&CO/NEW 09-12-2020/Logo_Steso/FamorItalia.jpg"
        ),
        alias="DOCUMENT_LOGO_PATH",
    )
    document_dle_template_path: Path = Field(
        default=Path("C:/Progetti/TJXOPE~1/TEMPLATES/DOCUMENTI EXPORT/HG LIKING 90 - DLE.pdf"),
        alias="DOCUMENT_DLE_TEMPLATE_PATH",
    )
    document_stamp_signature_path: Path = Field(
        default=Path(
            "C:/Users/Tommaso/OneDrive - FAMOR ITALIA/COMUNI/MODULI/DOCUMENTI TOMMASO/FIRMA E TIMBRO.png"
        ),
        alias="DOCUMENT_STAMP_SIGNATURE_PATH",
    )
    inventory_alert_email_to: str = Field(default="operation@famoritalia.com", alias="INVENTORY_ALERT_EMAIL_TO")
    inventory_alert_email_from: str = Field(default="tjx-ops-hub@local", alias="INVENTORY_ALERT_EMAIL_FROM")
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=25, alias="SMTP_PORT")
    smtp_username: str = Field(default="", alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=False, alias="SMTP_USE_TLS")

    @property
    def sqlite_url(self) -> str:
        return f"sqlite:///{self.sqlite_db_path}"

    @property
    def supplier_aliases(self) -> dict[str, str]:
        try:
            raw = json.loads(self.supplier_aliases_json or "{}")
            if not isinstance(raw, dict):
                return {}
            result: dict[str, str] = {}
            for k, v in raw.items():
                key = str(k).strip()
                val = str(v).strip()
                if key and val:
                    result[key.upper()] = val
            return result
        except json.JSONDecodeError:
            return {}

    @property
    def inventory_alert_recipients(self) -> list[str]:
        raw = self.inventory_alert_email_to or ""
        return [x.strip() for x in raw.split(",") if x.strip()]


settings = Settings()
