from pathlib import Path
import mimetypes

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.core.paths import template_paths
from app.schemas.files import PdfListResponse, PdfUploadResponse
from app.services.file_catalog import FileCatalogService

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/pdfs", response_model=PdfListResponse)
def list_pdf_files() -> PdfListResponse:
    service = FileCatalogService()
    files = service.list_all_pdfs()
    return PdfListResponse(total=len(files), files=files)


@router.post("/upload-pdf", response_model=PdfUploadResponse)
async def upload_pdf(file: UploadFile = File(...)) -> PdfUploadResponse:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome file mancante.",
        )
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato non supportato. Carica un file PDF.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File vuoto.",
        )

    service = FileCatalogService()
    saved = service.save_uploaded_pdf(file.filename, content)
    return PdfUploadResponse(
        file_name=saved.file_name,
        absolute_path=saved.absolute_path,
        source_folder=saved.source_folder,
        size_bytes=saved.size_bytes,
        parser_hint=service.detect_parser_family(saved),
    )


@router.get("/download")
def download_file(
    path: str = Query(..., description="Percorso assoluto file da aprire/scaricare"),
    disposition: str = Query("attachment", pattern="^(attachment|inline)$"),
) -> FileResponse:
    target = Path(path).expanduser().resolve()
    allowed_roots = [
        (Path.cwd() / "output").resolve(),
        Path(template_paths.root).resolve(),
    ]

    if not target.exists() or not target.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File non trovato.",
        )

    if not any(str(target).startswith(str(root)) for root in allowed_roots):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Percorso non consentito.",
        )

    media_type, _ = mimetypes.guess_type(str(target))
    response = FileResponse(
        path=target,
        filename=target.name,
        media_type=media_type or "application/octet-stream",
    )
    response.headers["Content-Disposition"] = f'{disposition}; filename="{target.name}"'
    return response
