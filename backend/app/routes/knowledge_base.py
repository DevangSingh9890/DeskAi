from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.models.document import Document, DocumentDeleteResponse, DocumentSummary
from app.services.file_service import (
    DocumentNotFoundError,
    DocumentStorageError,
    InvalidDocumentError,
    delete_document,
    list_documents,
    save_document,
)

router = APIRouter()


@router.post(
    "/upload",
    response_model=Document,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(file: UploadFile = File(...)) -> Document:
    try:
        return save_document(file)
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
