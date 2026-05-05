from pathlib import Path

from pydantic import BaseModel


class PdfFileInfo(BaseModel):
    file_name: str
    absolute_path: Path
    source_folder: str
    size_bytes: int


class PdfListResponse(BaseModel):
    total: int
    files: list[PdfFileInfo]


class PdfUploadResponse(BaseModel):
    file_name: str
    absolute_path: Path
    source_folder: str
    size_bytes: int
    parser_hint: str | None = None
