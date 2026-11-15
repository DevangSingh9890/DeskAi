import logging
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from threading import Lock, RLock
from typing import Any

from chromadb.config import Settings as ChromaSettings
from langchain_core.documents import Document as LangChainDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import BACKEND_DIR, settings
from app.models.document import Document, IngestionStage
from app.services.file_service import (
    DocumentNotFoundError,
    DocumentStorageError,
    get_document,
    get_document_path,
    list_documents,
    update_document_ingestion,
)

logger = logging.getLogger(__name__)

_store: Any | None = None
_embeddings: Any | None = None
_embedding_initialization_error: Exception | None = None
_embedding_initialization_attempted = False
_store_lock = Lock()
_embedding_lock = Lock()
_index_lock = RLock()

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBEDDING_BATCH_SIZE = 32
_STAGE_LABELS: dict[IngestionStage, str] = {
    "queued": "Queueing",
    "text_extraction": "Text extraction",
    "chunking": "Chunking",
    "embedding_generation": "Embedding generation",
    "chroma_insert": "Chroma insert",
    "indexing": "Indexing",
}


class VectorStoreError(RuntimeError):
    pass


class EmptyDocumentError(ValueError):
    pass


class UnsupportedDocumentError(ValueError):
    pass


class IngestionStageError(RuntimeError):
    def __init__(self, stage: IngestionStage, message: str) -> None:
        super().__init__(message)
        self.stage = stage


@contextmanager
def document_index_lock() -> Generator[None, None, None]:
    with _index_lock:
        yield


def _get_store() -> Any:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                try:
                    from langchain_chroma import Chroma

                    persist_directory = settings.CHROMA_PERSIST_DIRECTORY
                    if not persist_directory.is_absolute():
                        persist_directory = BACKEND_DIR / persist_directory
                    persist_directory.mkdir(parents=True, exist_ok=True)
                    _store = Chroma(
                        collection_name=settings.CHROMA_COLLECTION_NAME,
                        persist_directory=str(persist_directory),
                        collection_metadata={"hnsw:space": "cosine"},
                        client_settings=ChromaSettings(anonymized_telemetry=False),
                    )
                except Exception as exc:
                    logger.exception("Could not initialize the Chroma collection")
                    raise VectorStoreError(
                        f"The vector database is unavailable: {exc}"
                    ) from exc
    return _store


def initialize_embedding_service() -> None:
    global _embeddings, _embedding_initialization_error
    global _embedding_initialization_attempted

    with _embedding_lock:
        if _embeddings is not None:
            return
        if _embedding_initialization_error is not None:
            raise VectorStoreError(
                f"The local embedding model is unavailable: "
                f"{_embedding_initialization_error}"
            ) from _embedding_initialization_error
        if _embedding_initialization_attempted:
            raise VectorStoreError("The local embedding model could not be loaded.")

        _embedding_initialization_attempted = True
        logger.info("Embedding model load started model=%s", settings.EMBEDDING_MODEL)
        try:
            from langchain_huggingface import HuggingFaceEmbeddings

            _embeddings = HuggingFaceEmbeddings(
                model_name=settings.EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        except Exception as exc:
            _embedding_initialization_error = exc
            logger.exception(
                "Embedding model load failed model=%s", settings.EMBEDDING_MODEL
            )
            raise VectorStoreError(
                f"The local embedding model is unavailable: {exc}"
            ) from exc

        logger.info("Embedding model load completed model=%s", settings.EMBEDDING_MODEL)


def _get_embeddings() -> Any:
    global _embeddings
    if _embeddings is None:
        initialize_embedding_service()
    return _embeddings


def queue_document_ingestion(
    document_id: str,
    *,
    force: bool = False,
) -> tuple[Document, bool]:
    with _index_lock:
        document = get_document(document_id)
        if document.ingestion_status == "Processing":
            return document, False
        if document.ingestion_status == "Indexed" and not force:
            return document, False

        queued = update_document_ingestion(
            document_id,
            "Processing",
            processing_stage="queued",
            processing_error=None,
        )
        logger.info("Indexing queued id=%s filename=%s", queued.id, queued.filename)
        return queued, True


def recover_interrupted_ingestions() -> None:
    for document in list_documents():
        if document.ingestion_status != "Processing":
            continue

        message = "Indexing was interrupted by a backend restart. Retry indexing."
        update_document_ingestion(
            document.id,
            "Failed",
            processing_stage=document.processing_stage or "indexing",
            processing_error=message,
        )
        logger.warning(
            "Marked interrupted indexing as failed id=%s filename=%s",
            document.id,
            document.filename,
        )


def _run_stage(
    document_id: str,
    stage: IngestionStage,
    operation: Callable[[], Any],
) -> Any:
    label = _STAGE_LABELS[stage]
    update_document_ingestion(
        document_id,
        "Processing",
        processing_stage=stage,
        processing_error=None,
    )
    logger.info("%s started id=%s", label, document_id)
    try:
        result = operation()
    except Exception as exc:
        logger.exception("%s failed id=%s", label, document_id)
        message = str(exc).strip() or type(exc).__name__
        raise IngestionStageError(stage, message) from exc
    logger.info("%s completed id=%s", label, document_id)
    return result


def _load_documents(document: Document) -> list[LangChainDocument]:
    path = get_document_path(document)
    extension = Path(document.filename).suffix.lower()
    try:
        if extension == ".pdf":
            from langchain_community.document_loaders import PyPDFLoader

            documents = PyPDFLoader(str(path)).load()
        elif extension == ".txt":
            from langchain_community.document_loaders import TextLoader

            documents = TextLoader(str(path), autodetect_encoding=True).load()
        elif extension == ".docx":
            from langchain_community.document_loaders import Docx2txtLoader

            documents = Docx2txtLoader(str(path)).load()
        else:
            raise UnsupportedDocumentError(
                "Only PDF, DOCX, and TXT documents can be indexed."
            )
    except UnsupportedDocumentError:
        raise
    except Exception as exc:
        logger.exception("Could not extract document text: id=%s", document.id)
        raise EmptyDocumentError(
            f"Text could not be extracted from the document: {exc}"
        ) from exc

    documents = [
        item for item in documents if item.page_content and item.page_content.strip()
    ]
    if not documents:
        raise EmptyDocumentError("No text could be extracted from the document.")
    return documents


def ingest_document(document: Document, *, force: bool = False) -> Document:
    with _index_lock:
        document = get_document(document.id)
        if document.ingestion_status == "Indexed" and not force:
            return document

        try:
            logger.info(
                "Indexing started id=%s filename=%s",
                document.id,
                document.filename,
            )
            source_documents = _run_stage(
                document.id,
                "text_extraction",
                lambda: _load_documents(document),
            )
            logger.info(
                "Text extraction completed id=%s pages=%d",
                document.id,
                len(source_documents),
            )

            def split_documents() -> list[LangChainDocument]:
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=CHUNK_SIZE,
                    chunk_overlap=CHUNK_OVERLAP,
                )
                chunks = [
                    chunk
                    for chunk in splitter.split_documents(source_documents)
                    if chunk.page_content and chunk.page_content.strip()
                ]
                if not chunks:
                    raise EmptyDocumentError(
                        "No text could be extracted from the document."
                    )
                return chunks

            chunks = _run_stage(document.id, "chunking", split_documents)
            logger.info(
                "Chunking completed id=%s chunks=%d", document.id, len(chunks)
            )

            chunk_ids = [
                f"{document.id}_chunk_{index + 1}" for index in range(len(chunks))
            ]
            metadatas: list[dict[str, Any]] = []
            for index, chunk in enumerate(chunks):
                metadata: dict[str, Any] = {
                    key: value
                    for key, value in chunk.metadata.items()
                    if key == "page" and isinstance(value, (str, int, float, bool))
                }
                metadata.update(
                    {
                        "filename": document.filename,
                        "document_id": document.id,
                        "chunk_id": chunk_ids[index],
                        "chunk_index": index + 1,
                        "file_size": document.size,
                        "uploaded_at": document.uploaded_at.isoformat(),
                    }
                )
                metadatas.append(metadata)

            def generate_embeddings() -> list[list[float]]:
                embeddings = _get_embeddings()
                vectors: list[list[float]] = []
                for start in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
                    texts = [
                        chunk.page_content
                        for chunk in chunks[start : start + EMBEDDING_BATCH_SIZE]
                    ]
                    vectors.extend(embeddings.embed_documents(texts))
                if len(vectors) != len(chunks):
                    raise ValueError(
                        "Embedding model returned an unexpected number of vectors."
                    )
                return vectors

            vectors = _run_stage(
                document.id,
                "embedding_generation",
                generate_embeddings,
            )

            def insert_vectors() -> None:
                store = _get_store()
                existing = store.get(
                    where={"document_id": document.id},
                    include=["metadatas"],
                )
                store._collection.upsert(
                    embeddings=vectors,
                    documents=[chunk.page_content for chunk in chunks],
                    metadatas=metadatas,
                    ids=chunk_ids,
                )

                stale_ids = set(existing["ids"]) - set(chunk_ids)
                if stale_ids:
                    store.delete(ids=sorted(stale_ids))

            _run_stage(document.id, "chroma_insert", insert_vectors)

            indexed = update_document_ingestion(
                document.id,
                "Indexed",
                indexed_chunks=len(chunks),
                processing_stage=None,
                processing_error=None,
            )
            logger.info(
                "Indexing finished id=%s filename=%s chunks=%d",
                document.id,
                document.filename,
                len(chunks),
            )
            return indexed
        except IngestionStageError as exc:
            update_document_ingestion(
                document.id,
                "Failed",
                processing_stage=exc.stage,
                processing_error=str(exc),
            )
            raise
        except (DocumentNotFoundError, DocumentStorageError):
            raise
        except Exception as exc:
            logger.exception("Document ingestion failed: id=%s", document.id)
            message = str(exc).strip() or type(exc).__name__
            update_document_ingestion(
                document.id,
                "Failed",
                processing_stage="indexing",
                processing_error=message,
            )
            raise IngestionStageError("indexing", message) from exc


def process_document_ingestion(document_id: str, *, force: bool = False) -> None:
    try:
        document = get_document(document_id)
        ingest_document(document, force=force)
    except DocumentNotFoundError:
        logger.warning("Queued document no longer exists: id=%s", document_id)
    except IngestionStageError:
        logger.error("Indexing failed id=%s", document_id)
    except Exception as exc:
        logger.exception("Unexpected indexing failure id=%s", document_id)
        try:
            update_document_ingestion(
                document_id,
                "Failed",
                processing_stage="indexing",
                processing_error=str(exc).strip() or type(exc).__name__,
            )
        except DocumentStorageError:
            logger.exception(
                "Could not persist indexing failure status id=%s", document_id
            )


def search_knowledge(query: str, top_k: int = 4) -> list[dict[str, Any]]:
    try:
        embedding = _get_embeddings().embed_query(query)
        matches = _get_store().similarity_search_by_vector_with_relevance_scores(
            embedding=embedding,
            k=top_k,
        )
    except VectorStoreError:
        raise
    except Exception as exc:
        logger.exception("Semantic search failed")
        raise VectorStoreError("Semantic search is unavailable.") from exc

    return [
        {
            "content": document.page_content,
            "metadata": {
                key: document.metadata[key]
                for key in ("filename", "document_id", "chunk_id")
                if key in document.metadata
            },
            "score": float(score),
        }
        for document, score in matches
        if score >= settings.RAG_RELEVANCE_THRESHOLD
    ]


def delete_document_vectors(document_id: str) -> int:
    with document_index_lock():
        try:
            store = _get_store()
            stored = store.get(
                where={"document_id": document_id},
                include=["metadatas"],
            )
            ids = stored["ids"]
            if ids:
                store.delete(ids=ids)
            return len(ids)
        except VectorStoreError:
            raise
        except Exception as exc:
            logger.exception("Could not delete document vectors: id=%s", document_id)
            raise VectorStoreError(
                "Document vectors could not be deleted."
            ) from exc


def get_knowledge_stats() -> dict[str, Any]:
    try:
        collection = _get_store().get(include=["metadatas"])
        metadata = collection["metadatas"] or []
        indexed_documents = {
            item.get("document_id")
            for item in metadata
            if item and item.get("document_id")
        }
        return {
            "total_indexed_documents": len(indexed_documents),
            "total_indexed_chunks": len(collection["ids"]),
            "collection_name": settings.CHROMA_COLLECTION_NAME,
            "vector_database_available": True,
        }
    except VectorStoreError:
        raise
    except Exception as exc:
        logger.exception("Could not read knowledge-base statistics")
        raise VectorStoreError(
            "Knowledge-base statistics are unavailable."
        ) from exc
