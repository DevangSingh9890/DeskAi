from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

IngestionStatus = Literal["Uploaded", "Processing", "Indexed", "Failed"]
IngestionStage = Literal[
    "queued",
    "text_extraction",
    "chunking",
    "embedding_generation",
    "chroma_insert",
    "indexing",
]
JobStatus = Literal["uploaded", "processing", "completed", "failed"]


class Document(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    filename: str
    size: int
    uploaded_at: datetime
    ingestion_status: IngestionStatus = "Uploaded"
    indexed_chunks: int = Field(default=0, ge=0)
    processing_stage: IngestionStage | None = None
    processing_error: str | None = None


class DocumentSummary(BaseModel):
    id: str
    filename: str
    size: int
    uploaded_at: datetime
    ingestion_status: IngestionStatus = "Uploaded"
    indexed_chunks: int = Field(default=0, ge=0)
    processing_stage: IngestionStage | None = None
    processing_error: str | None = None


class DocumentJobResponse(BaseModel):
    document_id: str
    status: JobStatus
    stage: IngestionStage | None = None
    error: str | None = None


def to_document_job_response(document: Document) -> DocumentJobResponse:
    status_by_ingestion_status: dict[IngestionStatus, JobStatus] = {
        "Uploaded": "uploaded",
        "Processing": "processing",
        "Indexed": "completed",
        "Failed": "failed",
    }
    return DocumentJobResponse(
        document_id=document.id,
        status=status_by_ingestion_status[document.ingestion_status],
        stage=document.processing_stage,
        error=document.processing_error,
    )


class DocumentDeleteResponse(BaseModel):
    message: str
