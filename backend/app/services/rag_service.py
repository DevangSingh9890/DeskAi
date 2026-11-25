from __future__ import annotations

import logging
import os
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, RLock, Thread
from time import perf_counter, sleep
from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    from langchain_core.documents import Document as LangChainDocument

logger = logging.getLogger(__name__)

_store: Any | None = None
_chroma_client: Any | None = None
_store_lock = Lock()
_index_lock = RLock()
_warmup_lock = Lock()
_warmup_thread: Thread | None = None
_warmup_thread_started = False
_pending_ingestions: dict[str, bool] = {}
_warmup_state: dict[str, Any] = {
    "warming": False,
    "embedding_model_loaded": False,
    "warmup_started_at": None,
    "warmup_completed_at": None,
    "warmup_status": "not_started",
    "warmup_error": None,
}
WARMUP_INGESTION_MESSAGE = "Embedding model is still warming up. Please wait."

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
_TIMED_STAGE_LABELS: dict[IngestionStage, str] = {
    "text_extraction": "Extraction",
    "chunking": "Chunking",
}


class VectorStoreError(RuntimeError):
    pass


class ChromaCollectionMissingError(VectorStoreError):
    pass


class EmptyDocumentError(ValueError):
    pass


class UnsupportedDocumentError(ValueError):
    pass


class IngestionStageError(RuntimeError):
    def __init__(self, stage: IngestionStage, message: str) -> None:
        super().__init__(message)
        self.stage = stage


class EmbeddingService:
    _instance: EmbeddingService | None = None
    _model: Any | None = None
    _load_error: Exception | None = None
    _load_attempted = False
    _instance_lock = Lock()
    _model_lock = Lock()

    def __new__(cls) -> EmbeddingService:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def get_model(self) -> Any:
        cls = type(self)
        with cls._model_lock:
            if cls._model is not None:
                logger.info("Reusing existing embedding model")
                return cls._model
            if cls._load_error is not None:
                raise VectorStoreError(
                    f"The local embedding model is unavailable: {cls._load_error}"
                ) from cls._load_error
            if cls._load_attempted:
                raise VectorStoreError("The local embedding model could not be loaded.")

            cls._load_attempted = True
            load_started = perf_counter()
            logger.info("Loading embedding model...")
            try:
                model_path, cache_directory, source = _resolve_embedding_model_source(
                    settings.EMBEDDING_MODEL
                )
                initialization_started = perf_counter()
                logger.info("Model initialization started source=%s", source)
                try:
                    from langchain_huggingface import HuggingFaceEmbeddings

                    cls._model = HuggingFaceEmbeddings(
                        model_name=model_path,
                        cache_folder=(
                            str(cache_directory)
                            if cache_directory is not None
                            else None
                        ),
                        model_kwargs={"device": "cpu", "local_files_only": True},
                        encode_kwargs={"normalize_embeddings": True},
                    )
                finally:
                    logger.info(
                        "Model initialization time: %.3f seconds",
                        perf_counter() - initialization_started,
                    )
            except Exception as exc:
                cls._load_error = exc
                logger.info(
                    "Model load time: %.3f seconds", perf_counter() - load_started
                )
                logger.exception(
                    "Embedding model load failed model=%s", settings.EMBEDDING_MODEL
                )
                raise VectorStoreError(
                    f"The local embedding model is unavailable: {exc}"
                ) from exc

            logger.info(
                "Embedding model loaded successfully"
            )
            logger.info(
                "Model load time: %.3f seconds", perf_counter() - load_started
            )
            return cls._model


def _embedding_cache_configuration() -> tuple[Path | None, str]:
    for variable in (
        "HF_HUB_CACHE",
        "SENTENCE_TRANSFORMERS_HOME",
        "TRANSFORMERS_CACHE",
    ):
        value = os.getenv(variable, "").strip()
        if value:
            return Path(value).expanduser(), variable

    hf_home = os.getenv("HF_HOME", "").strip()
    if hf_home:
        return Path(hf_home).expanduser() / "hub", "HF_HOME"
    return None, "default"


def _resolve_embedding_model_source(
    model_name: str,
) -> tuple[str, Path | None, str]:
    configured_path = Path(model_name).expanduser()
    if not configured_path.is_absolute():
        configured_path = BACKEND_DIR / configured_path
    if configured_path.is_dir():
        logger.info("Model source=local_path")
        cache_directory, _ = _embedding_cache_configuration()
        return str(configured_path.resolve()), cache_directory, "local_path"

    cache_directory, cache_source = _embedding_cache_configuration()
    logger.info("Model cache lookup started cache_source=%s", cache_source)
    cache_started = perf_counter()
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    cache_arguments = {
        "repo_id": model_name,
        "cache_dir": str(cache_directory) if cache_directory is not None else None,
    }

    try:
        snapshot_path = snapshot_download(
            **cache_arguments,
            local_files_only=True,
        )
    except LocalEntryNotFoundError:
        logger.info(
            "Model cache lookup result=miss lookup_time=%.3f seconds",
            perf_counter() - cache_started,
        )
        download_started = perf_counter()
        logger.info("Model download started model=%s", model_name)
        try:
            snapshot_path = snapshot_download(
                **cache_arguments,
                local_files_only=False,
            )
        except Exception:
            logger.exception(
                "Model download failed download_time=%.3f seconds",
                perf_counter() - download_started,
            )
            raise
        logger.info(
            "Model download completed download_time=%.3f seconds",
            perf_counter() - download_started,
        )
        return str(snapshot_path), cache_directory, "download"

    logger.info(
        "Model cache lookup result=hit lookup_time=%.3f seconds",
        perf_counter() - cache_started,
    )
    return str(snapshot_path), cache_directory, "cache"


@contextmanager
def document_index_lock() -> Generator[None, None, None]:
    with _index_lock:
        yield


def _get_chroma_persist_directory() -> Path:
    persist_directory = settings.CHROMA_PERSIST_DIRECTORY
    if not persist_directory.is_absolute():
        persist_directory = BACKEND_DIR / persist_directory
    return persist_directory.resolve()


def _get_chroma_collection_names(client: Any) -> list[str]:
    return sorted(
        collection
        if isinstance(collection, str)
        else collection.name
        for collection in client.list_collections()
    )


def _get_store() -> Any:
    global _chroma_client, _store
    if _store is None:
        with _store_lock:
            if _store is None:
                initialization_started = perf_counter()
                try:
                    import chromadb
                    from chromadb.config import Settings as ChromaSettings
                    from langchain_chroma import Chroma

                    persist_directory = _get_chroma_persist_directory()
                    persist_directory.mkdir(parents=True, exist_ok=True)
                    logger.info("Chroma persist directory: %s", persist_directory)
                    logger.info(
                        "Chroma collection name: %s",
                        settings.CHROMA_COLLECTION_NAME,
                    )
                    client = chromadb.PersistentClient(
                        path=str(persist_directory),
                        settings=ChromaSettings(anonymized_telemetry=False),
                    )
                    collection_name = settings.CHROMA_COLLECTION_NAME
                    existing_names = set(_get_chroma_collection_names(client))
                    if collection_name in existing_names:
                        collection_exists = True
                        client.get_collection(name=collection_name)
                        logger.info(
                            "Loaded existing Chroma collection: %s",
                            collection_name,
                        )
                    else:
                        collection_exists = False
                        indexed_documents = [
                            document
                            for document in list_documents()
                            if document.ingestion_status == "Indexed"
                        ]
                        if existing_names or indexed_documents:
                            logger.error(
                                "Collection missing: persist_directory=%s "
                                "collection_name=%s total_collections=%d "
                                "existing_collections=%s indexed_documents=%d "
                                "vector_count=0 retriever_ready=FALSE",
                                persist_directory,
                                collection_name,
                                len(existing_names),
                                sorted(existing_names),
                                len(indexed_documents),
                            )
                            _chroma_client = client
                            raise ChromaCollectionMissingError(
                                "The configured Chroma collection is missing "
                                "while persisted index metadata exists."
                            )
                        logger.warning(
                            "Collection missing: %s; creating the initial "
                            "collection in %s",
                            collection_name,
                            persist_directory,
                        )
                    _store = Chroma(
                        client=client,
                        collection_name=collection_name,
                        collection_metadata={"hnsw:space": "cosine"},
                        create_collection_if_not_exists=not collection_exists,
                    )
                    _chroma_client = client
                    logger.info("Chroma persist directory: %s", persist_directory)
                    logger.info(
                        "Chroma initialization time: %.3f seconds",
                        perf_counter() - initialization_started,
                    )
                except VectorStoreError:
                    raise
                except Exception as exc:
                    logger.exception("Could not initialize the Chroma collection")
                    logger.info(
                        "Chroma initialization failed after %.3f seconds",
                        perf_counter() - initialization_started,
                    )
                    raise VectorStoreError(
                        f"The vector database is unavailable: {exc}"
                    ) from exc
    return _store


def get_chroma_diagnostics() -> dict[str, Any]:
    try:
        try:
            store = _get_store()
        except ChromaCollectionMissingError:
            client = _chroma_client
            if client is None:
                raise
            collection_names = _get_chroma_collection_names(client)
            indexed_documents = [
                document
                for document in list_documents()
                if document.ingestion_status == "Indexed"
            ]
            return {
                "persist_directory": str(_get_chroma_persist_directory()),
                "collection_name": settings.CHROMA_COLLECTION_NAME,
                "total_collections": len(collection_names),
                "collection_names": collection_names,
                "vector_count": 0,
                "document_count": 0,
                "embedding_model": settings.EMBEDDING_MODEL,
                "indexed_metadata_document_count": len(indexed_documents),
                "missing_vector_document_count": len(indexed_documents),
                "mismatched_chunk_document_count": len(indexed_documents),
                "retriever_status": False,
            }

        client = _chroma_client
        if client is None:
            raise VectorStoreError("The persistent Chroma client is unavailable.")

        collection = store._collection
        collection_names = _get_chroma_collection_names(client)
        vector_count = collection.count()
        stored_records = collection.get(include=["metadatas"])
        stored_document_ids = {
            metadata["document_id"]
            for metadata in stored_records["metadatas"] or []
            if metadata and metadata.get("document_id")
        }
        vector_counts_by_document: dict[str, int] = {}
        for metadata in stored_records["metadatas"] or []:
            if metadata and metadata.get("document_id"):
                document_id = metadata["document_id"]
                vector_counts_by_document[document_id] = (
                    vector_counts_by_document.get(document_id, 0) + 1
                )

        indexed_documents = [
            document
            for document in list_documents()
            if document.ingestion_status == "Indexed"
        ]
        indexed_document_ids = {document.id for document in indexed_documents}
        missing_vector_documents = indexed_document_ids - stored_document_ids
        mismatched_chunk_documents = {
            document.id
            for document in indexed_documents
            if vector_counts_by_document.get(document.id, 0)
            != document.indexed_chunks
        }

        retriever_status = False
        try:
            if vector_count:
                sample = collection.get(limit=1, include=["embeddings"])
                sample_embeddings = sample["embeddings"]
                if sample_embeddings is None or len(sample_embeddings) == 0:
                    raise ValueError("Chroma returned no embedding for a stored vector.")
                probe_embedding = sample_embeddings[0]
                if hasattr(probe_embedding, "tolist"):
                    probe_embedding = probe_embedding.tolist()
                probe = collection.query(
                    query_embeddings=[probe_embedding],
                    n_results=1,
                    include=["metadatas"],
                )
                retriever_status = bool(probe["ids"] and probe["ids"][0])
            else:
                client.heartbeat()
                collection.get(limit=1, include=["metadatas"])
                retriever_status = True
        except Exception:
            logger.exception("Chroma retriever integrity probe failed")

        diagnostics = {
            "persist_directory": str(
                _get_chroma_persist_directory()
            ),
            "collection_name": settings.CHROMA_COLLECTION_NAME,
            "total_collections": len(collection_names),
            "collection_names": collection_names,
            "vector_count": vector_count,
            "document_count": len(stored_document_ids),
            "embedding_model": settings.EMBEDDING_MODEL,
            "indexed_metadata_document_count": len(indexed_document_ids),
            "missing_vector_document_count": len(missing_vector_documents),
            "mismatched_chunk_document_count": len(mismatched_chunk_documents),
            "retriever_status": retriever_status,
        }
        return diagnostics
    except VectorStoreError:
        raise
    except Exception as exc:
        logger.exception("Could not verify Chroma persistence integrity")
        raise VectorStoreError(
            "Chroma persistence integrity could not be verified."
        ) from exc


def initialize_vector_store() -> dict[str, Any]:
    diagnostics = get_chroma_diagnostics()
    logger.info("Chroma persist directory: %s", diagnostics["persist_directory"])
    logger.info("Chroma collection name: %s", diagnostics["collection_name"])
    logger.info("Chroma total collections: %d", diagnostics["total_collections"])
    logger.info("Chroma collections: %s", diagnostics["collection_names"])
    logger.info("Chroma total vectors: %d", diagnostics["vector_count"])
    logger.info("Chroma indexed documents: %d", diagnostics["document_count"])
    logger.info("RAG embedding model: %s", diagnostics["embedding_model"])
    logger.info(
        "Indexed metadata documents: %d",
        diagnostics["indexed_metadata_document_count"],
    )
    logger.info(
        "Chroma retriever ready: %s",
        "TRUE" if diagnostics["retriever_status"] else "FALSE",
    )

    if not diagnostics["retriever_status"]:
        raise VectorStoreError("The Chroma retriever integrity probe failed.")
    if (
        diagnostics["missing_vector_document_count"]
        or diagnostics["mismatched_chunk_document_count"]
    ):
        logger.error(
            "Chroma index does not match document metadata: "
            "missing_vector_documents=%d mismatched_chunk_documents=%d",
            diagnostics["missing_vector_document_count"],
            diagnostics["mismatched_chunk_document_count"],
        )
        raise VectorStoreError(
            "The persisted Chroma index does not match indexed document metadata."
        )
    return diagnostics


def initialize_embedding_service() -> None:
    EmbeddingService().get_model()


def _get_embeddings() -> Any:
    return EmbeddingService().get_model()


def is_embedding_model_loaded() -> bool:
    return EmbeddingService._model is not None


def is_embedding_model_warming() -> bool:
    with _warmup_lock:
        return bool(_warmup_state["warming"])


def get_embedding_warmup_status() -> dict[str, Any]:
    with _warmup_lock:
        state = dict(_warmup_state)
    state["embedding_model_loaded"] = is_embedding_model_loaded()
    return state


def start_background_embedding_warmup(delay_seconds: float = 0.0) -> None:
    global _warmup_thread, _warmup_thread_started
    with _warmup_lock:
        if _warmup_thread_started:
            return
        _warmup_thread_started = True
        _warmup_state.update(
            {
                "warming": True,
                "embedding_model_loaded": is_embedding_model_loaded(),
                "warmup_started_at": datetime.now(timezone.utc).isoformat(),
                "warmup_completed_at": None,
                "warmup_status": "warming",
                "warmup_error": None,
            }
        )
        _warmup_thread = Thread(
            target=_run_background_embedding_warmup,
            args=(delay_seconds,),
            name="embedding-model-warmup",
            daemon=True,
        )
        try:
            _warmup_thread.start()
        except Exception:
            _warmup_state.update(
                {
                    "warming": False,
                    "warmup_completed_at": datetime.now(timezone.utc).isoformat(),
                    "warmup_status": "failed",
                    "warmup_error": "Embedding model warm-up could not start.",
                }
            )
            logger.exception("Could not start background embedding warmup")


def _run_background_embedding_warmup(delay_seconds: float) -> None:
    if delay_seconds > 0:
        sleep(delay_seconds)
    logger.info("Background embedding warmup started")
    try:
        warm_up_embedding_service()
    except Exception:
        logger.exception("Background embedding warmup failed")
        _finish_background_embedding_warmup(success=False)
        return

    _finish_background_embedding_warmup(success=True)


def _finish_background_embedding_warmup(*, success: bool) -> None:
    with _warmup_lock:
        _warmup_state.update(
            {
                "warming": False,
                "embedding_model_loaded": is_embedding_model_loaded(),
                "warmup_completed_at": datetime.now(timezone.utc).isoformat(),
                "warmup_status": "completed" if success else "failed",
                "warmup_error": (
                    None if success else "Embedding model warm-up failed."
                ),
            }
        )
        pending_ingestions = list(_pending_ingestions.items())
        _pending_ingestions.clear()

    if success:
        logger.info("Embedding Warmup Completed")

    for document_id, force in pending_ingestions:
        process_document_ingestion(document_id, force=force)


def _defer_ingestion_while_warming(document_id: str, *, force: bool) -> bool:
    with _warmup_lock:
        if not _warmup_state["warming"]:
            return False
        _pending_ingestions[document_id] = (
            _pending_ingestions.get(document_id, False) or force
        )
        logger.info(
            "Indexing deferred until embedding warmup completes id=%s",
            document_id,
        )
        return True


def warm_up_embedding_service() -> None:
    model = _get_embeddings()
    warmup_started = perf_counter()
    try:
        embedding = model.embed_query("DeskAI embedding model warm-up")
        if not embedding:
            raise ValueError("The embedding model returned an empty vector.")
    except Exception as exc:
        logger.exception("Embedding model warm-up failed")
        raise VectorStoreError("The embedding model warm-up failed.") from exc
    logger.info(
        "Model warm-up embedding time: %.3f seconds",
        perf_counter() - warmup_started,
    )


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
    stage_started = perf_counter()
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
    finally:
        timing_label = _TIMED_STAGE_LABELS.get(stage)
        if timing_label:
            logger.info(
                "%s: %.3fs id=%s",
                timing_label,
                perf_counter() - stage_started,
                document_id,
            )
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

        indexing_started = perf_counter()
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
                from langchain_text_splitters import RecursiveCharacterTextSplitter

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
                embedding_started = perf_counter()
                try:
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
                finally:
                    logger.info(
                        "Embedding: %.3fs id=%s",
                        perf_counter() - embedding_started,
                        document.id,
                    )

            vectors = _run_stage(
                document.id,
                "embedding_generation",
                generate_embeddings,
            )

            def insert_vectors() -> None:
                store = _get_store()
                insert_started = perf_counter()
                try:
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
                finally:
                    logger.info(
                        "Chroma Insert: %.3fs id=%s",
                        perf_counter() - insert_started,
                        document.id,
                    )

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
        finally:
            logger.info(
                "Total Indexing: %.3fs id=%s",
                perf_counter() - indexing_started,
                document.id,
            )


def process_document_ingestion(document_id: str, *, force: bool = False) -> None:
    if _defer_ingestion_while_warming(document_id, force=force):
        return
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
    retrieval_started = perf_counter()
    try:
        embeddings = _get_embeddings()
        embedding_started = perf_counter()
        try:
            embedding = embeddings.embed_query(query)
        finally:
            logger.info(
                "Embedding: %.3fs operation=query",
                perf_counter() - embedding_started,
            )
        store = _get_store()
        chroma_search_started = perf_counter()
        try:
            matches = store.similarity_search_by_vector_with_relevance_scores(
                embedding=embedding,
                k=top_k,
            )
        finally:
            logger.info(
                "Chroma retrieval time: %.3f seconds",
                perf_counter() - chroma_search_started,
            )
    except VectorStoreError:
        raise
    except Exception as exc:
        logger.exception("Semantic search failed")
        raise VectorStoreError("Semantic search is unavailable.") from exc
    finally:
        logger.info(
            "Retrieval duration seconds=%.3f", perf_counter() - retrieval_started
        )

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
