from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.parser import ParserTestRequest, ParserTestResponse
from app.schemas.sierra_parser import SierraParseRequest, SierraParseResponse
from app.schemas.tjx_canada_parser import TjxCanadaParseRequest, TjxCanadaParseResponse
from app.schemas.tjx_usa_parser import TjxUsaParseRequest, TjxUsaParseResponse
from app.services.orders_service import OrdersService
from app.services.file_catalog import FileCatalogService
from app.services.parser.mock_parser import MockPdfParserService
from app.services.parser.tjx_canada_parser import TjxCanadaPdfParserService
from app.services.parser.sierra_parser import SierraPdfParserService
from app.services.parser.tjx_usa_parser import TjxUsaPdfParserService

router = APIRouter(prefix="/parser", tags=["parser"])


@router.post("/test", response_model=ParserTestResponse)
def parser_test(payload: ParserTestRequest) -> ParserTestResponse:
    catalog = FileCatalogService()
    file_info = catalog.find_pdf_by_name(payload.file_name)
    if file_info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File non trovato: {payload.file_name}",
        )

    sierra_parser = SierraPdfParserService()
    if sierra_parser.is_sierra_document(file_info.file_name):
        sierra_result = sierra_parser.parse_file(file_info.absolute_path)
        notes = [
            "Parser reale SIERRA eseguito.",
            f"PO raw: {sierra_result.po_raw or 'N/D'}",
            f"PO normalizzato: {sierra_result.po_normalized or 'N/D'}",
            f"Righe trovate: {len(sierra_result.lines)}",
            f"Warning: {len(sierra_result.warnings)}",
        ]
        return ParserTestResponse(
            parser_family=sierra_result.document_family,
            file_name=sierra_result.source_file,
            po_number_guess=sierra_result.po_normalized or sierra_result.po_raw,
            brand_guess=sierra_result.document_family,
            notes=notes,
        )

    parser = MockPdfParserService()
    return parser.parse_test(file_name=file_info.file_name)


@router.post("/sierra/test", response_model=SierraParseResponse)
def sierra_parser_test(
    payload: SierraParseRequest,
    save: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> SierraParseResponse:
    catalog = FileCatalogService()
    file_info = catalog.find_pdf_by_name(payload.file_name)
    if file_info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File non trovato: {payload.file_name}",
        )

    sierra_parser = SierraPdfParserService()
    if not sierra_parser.is_sierra_document(file_info.file_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Il file indicato non e un PDF SIERRA.",
        )

    parsed = sierra_parser.parse_file(file_info.absolute_path)

    if save:
        orders_service = OrdersService(db)
        parsed.saved_order_id = orders_service.save_sierra_parse(
            parsed=parsed,
            source_pdf_path=str(file_info.absolute_path),
        )

    return parsed


@router.post("/tjx_usa/test", response_model=TjxUsaParseResponse)
def tjx_usa_parser_test(
    payload: TjxUsaParseRequest,
    save: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> TjxUsaParseResponse:
    catalog = FileCatalogService()
    file_info = catalog.find_pdf_by_name(payload.file_name)
    if file_info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File non trovato: {payload.file_name}",
        )

    parser = TjxUsaPdfParserService()
    parsed = parser.parse_file(file_info.absolute_path)

    if save:
        orders_service = OrdersService(db)
        parsed.saved_order_id = orders_service.save_tjx_usa_parse(
            parsed=parsed,
            source_pdf_path=str(file_info.absolute_path),
        )

    return parsed


@router.post("/tjx_canada/test", response_model=TjxCanadaParseResponse)
def tjx_canada_parser_test(
    payload: TjxCanadaParseRequest,
    save: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> TjxCanadaParseResponse:
    catalog = FileCatalogService()
    file_info = catalog.find_pdf_by_name(payload.file_name)
    if file_info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File non trovato: {payload.file_name}",
        )

    parser = TjxCanadaPdfParserService()
    parsed = parser.parse_file(file_info.absolute_path)

    if save:
        orders_service = OrdersService(db)
        parsed.saved_order_id = orders_service.save_tjx_canada_parse(
            parsed=parsed,
            source_pdf_path=str(file_info.absolute_path),
        )

    return parsed
