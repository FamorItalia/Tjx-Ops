from pydantic import BaseModel, Field


class EmailDraftResponse(BaseModel):
    to: str = ""
    cc: list[str] = Field(default_factory=list)
    subject: str
    body: str
    attachments: list[str] = Field(default_factory=list)
