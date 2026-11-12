from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Document(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    filename: str
    size: int
    uploaded_at: datetime


class DocumentSummary(BaseModel):
    id: str
    filename: str
    size: int


class DocumentDeleteResponse(BaseModel):
    message: str
