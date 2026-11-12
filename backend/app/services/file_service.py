import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from pydantic import ValidationError

from app.models.document import Document, DocumentSummary

logger = logging.getLogger(__name__)

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads"
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
CHUNK_SIZE = 1024 * 1024


class InvalidDocumentError(ValueError):
    pass


class DocumentNotFoundError(LookupError):
    pass


class DocumentStorageError(RuntimeError):
    pass


def ensure_uploads_dir() -> None:
    try:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.exception("Could not create document uploads directory")
        raise DocumentStorageError("Document storage is unavailable.") from exc


def _metadata_path(document_id: str) -> Path:
    try:
        safe_id = str(UUID(document_id))
    except ValueError as exc:
        raise DocumentNotFoundError("Document not found.") from exc
    return UPLOADS_DIR / f"{safe_id}.json"


def _document_path(document: Document) -> Path:
    return UPLOADS_DIR / f"{document.id}{Path(document.filename).suffix.lower()}"


def _read_document(metadata_path: Path) -> Document:
    try:
        document = Document.model_validate_json(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError) as exc:
        logger.exception("Could not read document metadata: %s", metadata_path.name)
        raise DocumentStorageError("Document metadata could not be read.") from exc

    if metadata_path.stem != document.id:
        logger.error("Document metadata ID does not match its filename: %s", metadata_path.name)
        raise DocumentStorageError("Document metadata is invalid.")
    return document


def save_document(upload: UploadFile) -> Document:
    original_filename = (upload.filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    extension = Path(original_filename).suffix.lower()
    if not original_filename or not Path(original_filename).stem.strip():
        raise InvalidDocumentError("A filename is required.")
    if extension not in ALLOWED_EXTENSIONS:
        raise InvalidDocumentError("Only PDF, DOCX, and TXT files are supported.")

    ensure_uploads_dir()
    document_id = str(uuid4())
    document = UPLOADS_DIR / f"{document_id}{extension}"
    metadata = _metadata_path(document_id)
    temporary_metadata = UPLOADS_DIR / f".{document_id}.json.tmp"
    size = 0

    try:
        with document.open("xb") as destination:
            while chunk := upload.file.read(CHUNK_SIZE):
                destination.write(chunk)
                size += len(chunk)

        if size == 0:
            raise InvalidDocumentError("The uploaded file is empty.")

        result = Document(
            id=document_id,
            filename=original_filename,
            size=size,
            uploaded_at=datetime.now(timezone.utc),
        )
        temporary_metadata.write_text(
            result.model_dump_json(),
            encoding="utf-8",
        )
        os.replace(temporary_metadata, metadata)
    except InvalidDocumentError:
        document.unlink(missing_ok=True)
        raise
    except OSError as exc:
        document.unlink(missing_ok=True)
        temporary_metadata.unlink(missing_ok=True)
        logger.exception("Could not store uploaded document: %s", original_filename)
        raise DocumentStorageError("The document could not be stored.") from exc

    logger.info(
        "Stored document id=%s filename=%s size=%d",
        result.id,
        result.filename,
        result.size,
    )
    return result


def list_documents() -> list[DocumentSummary]:
    ensure_uploads_dir()
    documents: list[DocumentSummary] = []
    try:
        for metadata_path in UPLOADS_DIR.glob("*.json"):
            document = _read_document(metadata_path)
            if not _document_path(document).is_file():
                logger.error("Stored document file is missing: id=%s", document.id)
                raise DocumentStorageError("A stored document file is missing.")
            documents.append(
                DocumentSummary(
                    id=document.id,
                    filename=document.filename,
                    size=document.size,
                    uploaded_at=document.uploaded_at,
                )
            )
    except OSError as exc:
        logger.exception("Could not list uploaded documents")
        raise DocumentStorageError("Documents could not be listed.") from exc

    return sorted(documents, key=lambda document: document.filename.casefold())


def delete_document(document_id: str) -> None:
    ensure_uploads_dir()
    metadata_path = _metadata_path(document_id)
    if not metadata_path.is_file():
        raise DocumentNotFoundError("Document not found.")

    stored_document = _read_document(metadata_path)
    document_path = _document_path(stored_document)
    try:
        document_path.unlink()
        metadata_path.unlink()
    except FileNotFoundError as exc:
        logger.error("Stored document file is missing: id=%s", stored_document.id)
        raise DocumentNotFoundError("Document not found.") from exc
    except OSError as exc:
        logger.exception("Could not delete document: id=%s", stored_document.id)
        raise DocumentStorageError("The document could not be deleted.") from exc

    logger.info(
        "Deleted document id=%s filename=%s",
        stored_document.id,
        stored_document.filename,
    )
