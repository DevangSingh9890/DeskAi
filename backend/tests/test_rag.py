import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from langchain_core.documents import Document as LangChainDocument

from app.main import app
from app.services import rag_service
from app.services.rag_service import VectorStoreError


class FakeVectorStore:
    def __init__(self) -> None:
        self.records: dict[str, tuple[str, dict[str, object], list[float]]] = {}
        self.add_calls = 0
        self._collection = self
        self.search_results: list[tuple[LangChainDocument, float]] = []
        self.last_embedding: list[float] | None = None
        self.last_include: list[str] | None = None

    def get(
        self,
        *,
        where: dict[str, str] | None = None,
        include: list[str] | None = None,
    ) -> dict[str, list[object]]:
        self.last_include = include
        matching = {
            chunk_id: value
            for chunk_id, value in self.records.items()
            if where is None or value[1].get("document_id") == where["document_id"]
        }
        return {
            "ids": list(matching),
            "metadatas": [value[1] for value in matching.values()],
        }

    def upsert(
        self,
        *,
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, object]],
        ids: list[str],
    ) -> None:
        self.add_calls += 1
        for chunk_id, content, vector, metadata in zip(
            ids, documents, embeddings, metadatas, strict=True
        ):
            self.records[chunk_id] = (content, metadata, vector)

    def delete(self, *, ids: list[str]) -> None:
        for chunk_id in ids:
            self.records.pop(chunk_id, None)

    def similarity_search_by_vector_with_relevance_scores(
        self, *, embedding: list[float], k: int
    ) -> list[tuple[LangChainDocument, float]]:
        self.last_embedding = embedding
        return self.search_results[:k]


class RagRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.uploads_patch = patch(
            "app.services.file_service.UPLOADS_DIR",
            Path(self.temporary_directory.name) / "uploads",
        )
        self.uploads_patch.start()
        self.client = TestClient(app)
        self.store = FakeVectorStore()
        self.embedding = MagicMock()
        self.embedding.embed_documents.side_effect = lambda texts: [
            [0.1] * 384 for _ in texts
        ]
        self.embedding.embed_query.return_value = [0.1] * 384
        self.store_patch = patch.object(
            rag_service, "_get_store", return_value=self.store
        )
        self.embedding_patch = patch.object(
            rag_service, "_get_embeddings", return_value=self.embedding
        )
        self.store_patch.start()
        self.embedding_patch.start()

    def tearDown(self) -> None:
        self.embedding_patch.stop()
        self.store_patch.stop()
        self.uploads_patch.stop()
        self.temporary_directory.cleanup()

    def _upload_text(self, filename: str = "vpn.txt") -> str:
        response = self.client.post(
            "/api/documents/upload",
            files={
                "file": (
                    filename,
                    ("VPN authentication fails. " * 70).encode(),
                    "text/plain",
                )
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["document_id"]

    def test_ingestion_is_idempotent_and_search_returns_source_and_score(self) -> None:
        document_id = self._upload_text()

        first = self.client.post(f"/api/knowledge-base/{document_id}/ingest")
        second = self.client.post(f"/api/knowledge-base/{document_id}/ingest")
        document = self.client.get("/api/documents").json()[0]

        self.assertEqual(first.status_code, 202)
        self.assertEqual(first.json()["status"], "completed")
        self.assertGreater(document["indexed_chunks"], 1)
        self.assertEqual(second.json()["status"], "completed")
        self.assertEqual(self.store.add_calls, 1)
        self.assertEqual(len(self.store.records), document["indexed_chunks"])

        self.store.search_results = [
            (
                LangChainDocument(
                    page_content="VPN authentication troubleshooting steps.",
                    metadata={
                        "filename": "vpn.txt",
                        "document_id": document_id,
                        "chunk_id": f"{document_id}_chunk_1",
                    },
                ),
                0.82,
            ),
            (
                LangChainDocument(page_content="Unrelated text", metadata={}),
                0.12,
            ),
        ]
        response = self.client.post(
            "/api/knowledge-base/search",
            json={"query": "VPN sign-in keeps failing", "top_k": 4},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 1)
        result = response.json()["results"][0]
        self.assertEqual(result["metadata"]["document_id"], document_id)
        self.assertEqual(result["metadata"]["filename"], "vpn.txt")
        self.assertEqual(result["score"], 0.82)

    def test_irrelevant_results_are_filtered_and_empty_queries_rejected(self) -> None:
        self.store.search_results = [
            (LangChainDocument(page_content="No match", metadata={}), 0.1)
        ]
        response = self.client.post(
            "/api/knowledge-base/search",
            json={"query": "How do I bake bread?", "top_k": 4},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

        empty_response = self.client.post(
            "/api/knowledge-base/search",
            json={"query": "   "},
        )
        self.assertEqual(empty_response.status_code, 422)

    def test_delete_vectors_and_document_removes_indexed_content(self) -> None:
        document_id = self._upload_text()
        indexed = self.client.post(f"/api/knowledge-base/{document_id}/ingest")
        self.assertEqual(indexed.status_code, 202)

        deleted_vectors = self.client.delete(
            f"/api/knowledge-base/{document_id}/vectors"
        )
        self.assertEqual(deleted_vectors.status_code, 200)
        self.assertEqual(self.store.records, {})
        self.assertEqual(
            self.client.get("/api/documents").json()[0]["ingestion_status"],
            "Uploaded",
        )

        deleted_document = self.client.delete(f"/api/documents/{document_id}")
        self.assertEqual(deleted_document.status_code, 200)
        self.assertEqual(self.client.get("/api/documents").json(), [])

    def test_document_deletion_removes_existing_vectors(self) -> None:
        document_id = self._upload_text()
        indexed = self.client.post(f"/api/knowledge-base/{document_id}/ingest")
        self.assertEqual(indexed.status_code, 202)

        deleted_document = self.client.delete(f"/api/documents/{document_id}")

        self.assertEqual(deleted_document.status_code, 200)
        self.assertEqual(self.store.records, {})

    def test_embedding_failure_marks_document_failed(self) -> None:
        self.embedding.embed_documents.side_effect = RuntimeError(
            "model unavailable"
        )
        document_id = self._upload_text()

        response = self.client.get(f"/api/documents/{document_id}/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "failed")
        self.assertEqual(response.json()["stage"], "embedding_generation")
        self.assertIn("model unavailable", response.json()["error"])

    def test_large_documents_are_embedded_in_bounded_batches(self) -> None:
        source = LangChainDocument(page_content="x" * 40_000)
        with patch.object(rag_service, "_load_documents", return_value=[source]):
            document_id = self._upload_text()

        calls = self.embedding.embed_documents.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(len(call.args[0]) <= 32 for call in calls))
        self.assertEqual(
            self.client.get(f"/api/documents/{document_id}/status").json()["status"],
            "completed",
        )

    def test_empty_extracted_document_is_reported_as_failed(self) -> None:
        with patch.object(rag_service, "_load_documents", return_value=[]):
            document_id = self._upload_text()

        response = self.client.get(f"/api/documents/{document_id}/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "failed")
        self.assertEqual(response.json()["stage"], "chunking")
        self.assertIn("No text", response.json()["error"])

    def test_stats_report_indexed_documents_and_chunks(self) -> None:
        document_id = self._upload_text()
        indexed = self.client.post(f"/api/knowledge-base/{document_id}/ingest")
        self.assertEqual(indexed.status_code, 202)

        response = self.client.get("/api/knowledge-base/stats")
        document = self.client.get("/api/documents").json()[0]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["collection_name"], "deskai_knowledge")
        self.assertTrue(response.json()["vector_database_available"])
        self.assertEqual(response.json()["total_indexed_documents"], 1)
        self.assertEqual(
            response.json()["total_indexed_chunks"], document["indexed_chunks"]
        )

    def test_stats_expose_unavailable_vector_database(self) -> None:
        with patch.object(
            rag_service,
            "_get_store",
            side_effect=VectorStoreError("internal detail"),
        ):
            response = self.client.get("/api/knowledge-base/stats")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["vector_database_available"])
        self.assertIsNone(response.json()["total_indexed_chunks"])
        self.assertNotIn("internal detail", response.text)

    def test_chroma_uses_local_persistence_without_telemetry(self) -> None:
        from chromadb.config import Settings as ChromaSettings

        self.store_patch.stop()
        try:
            with tempfile.TemporaryDirectory() as persistence_directory:
                with patch.object(rag_service, "_store", None):
                    with patch.object(
                        rag_service,
                        "settings",
                        SimpleNamespace(
                            CHROMA_PERSIST_DIRECTORY=Path(persistence_directory),
                            CHROMA_COLLECTION_NAME="telemetry_test",
                        ),
                    ):
                        with patch(
                            "langchain_chroma.Chroma"
                        ) as chroma_constructor:
                            rag_service._get_store()
        finally:
            self.store_patch.start()

        client_settings = chroma_constructor.call_args.kwargs["client_settings"]
        self.assertEqual(
            chroma_constructor.call_args.kwargs["persist_directory"],
            persistence_directory,
        )
        self.assertIsInstance(client_settings, ChromaSettings)
        self.assertFalse(client_settings.anonymized_telemetry)
        self.store_patch.start()

    def test_embedding_model_is_initialized_once(self) -> None:
        with (
            patch.object(rag_service, "_embeddings", None),
            patch.object(rag_service, "_embedding_initialization_error", None),
            patch.object(rag_service, "_embedding_initialization_attempted", False),
            patch("langchain_huggingface.HuggingFaceEmbeddings") as constructor,
        ):
            rag_service.initialize_embedding_service()
            rag_service.initialize_embedding_service()

        constructor.assert_called_once()


if __name__ == "__main__":
    unittest.main()
