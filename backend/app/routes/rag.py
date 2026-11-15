import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from app.core.config import settings
from app.models.document import DocumentJobResponse, to_document_job_response
from app.models.rag import (
    KnowledgeBaseStats,
    SemanticSearchResponse,
    SemanticSearchRequest,
)
from app.services.file_service import (
    DocumentNotFoundError,
    DocumentStorageError,
    get_document,
    update_document_ingestion,
)
from app.services.rag_service import (
    VectorStoreError,
    delete_document_vectors,
    document_index_lock,
    get_knowledge_stats,
    process_document_ingestion,
    queue_document_ingestion,
    search_knowledge,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/{document_id}/ingest",
    response_model=DocumentJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def ingest_uploaded_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    force: bool = Query(default=False),
) -> DocumentJobResponse:
    try:
        document, should_schedule = queue_document_ingestion(
            document_id,
            force=force,
        )
        if should_schedule:
            background_tasks.add_task(
                process_document_ingestion,
                document_id,
                force=True,
            )
        return to_document_job_response(document)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        ) from exc
    except DocumentStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/search", response_model=SemanticSearchResponse)
def semantic_search(request: SemanticSearchRequest) -> SemanticSearchResponse:
    try:
        results = search_knowledge(request.query, request.top_k)
    except VectorStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return SemanticSearchResponse(query=request.query, results=results)


@router.get("/stats", response_model=KnowledgeBaseStats)
def knowledge_base_stats() -> KnowledgeBaseStats:
    try:
        return KnowledgeBaseStats(**get_knowledge_stats())
    except VectorStoreError:
        return KnowledgeBaseStats(
            total_indexed_documents=None,
            total_indexed_chunks=None,
            collection_name=settings.CHROMA_COLLECTION_NAME,
            vector_database_available=False,
            error="The vector database is unavailable.",
        )


@router.delete("/{document_id}/vectors")
def remove_document_vectors(document_id: str) -> dict[str, int | str]:
    try:
        with document_index_lock():
            get_document(document_id)
            deleted_count = delete_document_vectors(document_id)
            update_document_ingestion(
                document_id,
                "Uploaded",
                indexed_chunks=0,
                processing_error=None,
            )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        ) from exc
    except VectorStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except DocumentStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return {"message": "Document vectors deleted.", "deleted_chunks": deleted_count}
