from pydantic import BaseModel


class ParserTestRequest(BaseModel):
    file_name: str


class ParserTestResponse(BaseModel):
    parser_family: str
    file_name: str
    po_number_guess: str | None
    brand_guess: str | None
    notes: list[str]

