import logging

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status

from app.models.document import (
    DocumentDeleteResponse,
    DocumentJobResponse,
    DocumentSummary,
    to_document_job_response,
)
from app.services.file_service import (
    DocumentNotFoundError,
    DocumentStorageError,
    InvalidDocumentError,
    delete_document,
    get_document,
    list_documents,
    save_document,
    update_document_ingestion,
)
from app.services.rag_service import (
    process_document_ingestion,
    queue_document_ingestion,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/upload",
    response_model=DocumentJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> DocumentJobResponse:
    try:
        document = save_document(file)
        try:
            document, should_schedule = queue_document_ingestion(document.id)
            if should_schedule:
                background_tasks.add_task(process_document_ingestion, document.id)
            return to_document_job_response(document)
        except Exception as exc:
            logger.exception("Could not queue document indexing id=%s", document.id)
            error = str(exc).strip() or type(exc).__name__
            try:
                document = update_document_ingestion(
                    document.id,
                    "Failed",
                    processing_stage="queued",
                    processing_error=error,
                )
                return to_document_job_response(document)
            except DocumentStorageError:
                logger.exception(
                    "Could not persist document queue failure id=%s", document.id
                )
                return DocumentJobResponse(
                    document_id=document.id,
                    status="failed",
                    stage="queued",
                    error=error,
                )
    except InvalidDocumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except DocumentStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    finally:
        file.file.close()


@router.get("", response_model=list[DocumentSummary])
def get_documents() -> list[DocumentSummary]:
    try:
        return list_documents()
    except DocumentStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("/{document_id}/status", response_model=DocumentJobResponse)
def get_document_status(document_id: str) -> DocumentJobResponse:
    try:
        return to_document_job_response(get_document(document_id))
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DocumentStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
)
def remove_document(document_id: str) -> DocumentDeleteResponse:
    try:
        delete_document(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DocumentStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return DocumentDeleteResponse(message="Document deleted successfully")
