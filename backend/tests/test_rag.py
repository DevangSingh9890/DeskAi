from concurrent.futures import ThreadPoolExecutor
import os
import tempfile
from threading import Event
from time import perf_counter
from time import sleep
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
        self.real_get_embeddings = rag_service._get_embeddings
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

    def test_health_reports_embedding_model_state_without_loading_it(self) -> None:
        with patch.object(rag_service.EmbeddingService, "_model", None):
            response = self.client.get("/api/health")

        self.assertEqual(
            response.json(),
            {"backend": "ready", "embedding_model_loaded": False},
        )

        with patch.object(rag_service.EmbeddingService, "_model", object()):
            response = self.client.get("/api/health")

        self.assertEqual(
            response.json(),
            {"backend": "ready", "embedding_model_loaded": True},
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
            patch.object(rag_service.EmbeddingService, "_instance", None),
            patch.object(rag_service.EmbeddingService, "_model", None),
            patch.object(rag_service.EmbeddingService, "_load_error", None),
            patch.object(rag_service.EmbeddingService, "_load_attempted", False),
            patch.object(
                rag_service,
                "_resolve_embedding_model_source",
                return_value=("C:/cached/model", None, "cache"),
            ),
            patch("langchain_huggingface.HuggingFaceEmbeddings") as constructor,
        ):
            constructor.side_effect = lambda **_: (sleep(0.05), object())[1]
            with self.assertLogs(rag_service.logger, level="INFO") as logs:
                service = rag_service.EmbeddingService()
                second_service = rag_service.EmbeddingService()
                self.assertIs(service, second_service)
                with ThreadPoolExecutor(max_workers=8) as executor:
                    models = list(executor.map(lambda _: service.get_model(), range(8)))

        constructor.assert_called_once()
        self.assertTrue(all(model is models[0] for model in models))
        self.assertIn(
            "Loading embedding model for first time",
            "\n".join(logs.output),
        )
        self.assertIn("Embedding model loaded successfully", "\n".join(logs.output))
        self.assertIn("Reusing existing embedding model", "\n".join(logs.output))
        self.assertIn("Model initialization time:", "\n".join(logs.output))
        self.assertIn("Model load time:", "\n".join(logs.output))

    def test_ingestion_logs_embedding_chroma_and_total_timings(self) -> None:
        document_id = self._upload_text()

        with self.assertLogs(rag_service.logger, level="INFO") as logs:
            response = self.client.post(
                f"/api/knowledge-base/{document_id}/ingest?force=true"
            )

        self.assertEqual(response.status_code, 202)
        output = "\n".join(logs.output)
        self.assertIn("Extraction:", output)
        self.assertIn("Chunking:", output)
        self.assertIn("Embedding:", output)
        self.assertIn("Chroma Insert:", output)
        self.assertIn("Total Indexing:", output)

    def test_document_upload_logs_save_time(self) -> None:
        with self.assertLogs("app.services.file_service", level="INFO") as logs:
            self._upload_text()

        self.assertIn("Save:", "\n".join(logs.output))

    def test_uploads_reuse_the_loaded_model(self) -> None:
        with (
            patch.object(rag_service.EmbeddingService, "_model", self.embedding),
            patch.object(rag_service.EmbeddingService, "_load_error", None),
            patch.object(
                rag_service,
                "_get_embeddings",
                side_effect=self.real_get_embeddings,
            ) as get_embeddings,
            patch("langchain_huggingface.HuggingFaceEmbeddings") as constructor,
        ):
            self._upload_text("first.txt")
            self._upload_text("second.txt")

        constructor.assert_not_called()
        self.assertEqual(get_embeddings.call_count, 2)

    def test_embedding_model_warmup_generates_a_query_embedding(self) -> None:
        model = MagicMock()
        model.embed_query.return_value = [0.1] * 384
        with (
            patch.object(rag_service.EmbeddingService, "_model", model),
            patch.object(
                rag_service,
                "_get_embeddings",
                side_effect=self.real_get_embeddings,
            ),
            self.assertLogs(rag_service.logger, level="INFO") as logs,
        ):
            rag_service.warm_up_embedding_service()

        model.embed_query.assert_called_once_with("DeskAI embedding model warm-up")
        self.assertIn("Model warm-up embedding time:", "\n".join(logs.output))

    def test_background_warmup_loads_once_and_updates_status(self) -> None:
        constructor_entered = Event()
        allow_constructor_to_finish = Event()
        model = MagicMock()
        model.embed_query.return_value = [0.1] * 384

        def construct_model(**_: object) -> MagicMock:
            constructor_entered.set()
            allow_constructor_to_finish.wait(timeout=2)
            return model

        initial_status = {
            "warming": False,
            "embedding_model_loaded": False,
            "warmup_started_at": None,
            "warmup_completed_at": None,
            "warmup_status": "not_started",
            "warmup_error": None,
        }
        with (
            patch.object(rag_service, "_warmup_thread_started", False),
            patch.object(rag_service, "_warmup_thread", None),
            patch.object(rag_service, "_warmup_state", initial_status),
            patch.object(rag_service, "_pending_ingestions", {}),
            patch.object(rag_service.EmbeddingService, "_instance", None),
            patch.object(rag_service.EmbeddingService, "_model", None),
            patch.object(rag_service.EmbeddingService, "_load_error", None),
            patch.object(rag_service.EmbeddingService, "_load_attempted", False),
            patch.object(
                rag_service,
                "_get_embeddings",
                side_effect=self.real_get_embeddings,
            ),
            patch.object(
                rag_service,
                "_resolve_embedding_model_source",
                return_value=("C:/cached/model", None, "cache"),
            ),
            patch(
                "langchain_huggingface.HuggingFaceEmbeddings",
                side_effect=construct_model,
            ) as constructor,
        ):
            with self.assertLogs(rag_service.logger, level="INFO") as logs:
                start = perf_counter()
                rag_service.start_background_embedding_warmup()
                start_duration = perf_counter() - start
                thread = rag_service._warmup_thread
                try:
                    self.assertTrue(constructor_entered.wait(timeout=1))
                    self.assertLess(start_duration, 0.5)
                    self.assertTrue(thread.is_alive())
                    self.assertTrue(thread.daemon)
                    self.assertTrue(
                        rag_service.get_embedding_warmup_status()["warming"]
                    )
                finally:
                    allow_constructor_to_finish.set()
                    thread.join(timeout=5)

            constructor.assert_called_once()
            model.embed_query.assert_called_once_with(
                "DeskAI embedding model warm-up"
            )
            status = rag_service.get_embedding_warmup_status()
            self.assertFalse(status["warming"])
            self.assertTrue(status["embedding_model_loaded"])
            self.assertEqual(status["warmup_status"], "ready")
            self.assertIsNotNone(status["warmup_started_at"])
            self.assertIsNotNone(status["warmup_completed_at"])
            output = "\n".join(logs.output)
            self.assertIn("Background embedding warmup started", output)
            self.assertIn("Embedding model loaded successfully", output)
            self.assertIn("Warmup completed", output)

    def test_ingestion_is_deferred_and_drained_after_warmup(self) -> None:
        state = {
            "warming": True,
            "embedding_model_loaded": False,
            "warmup_started_at": "2026-11-16T00:00:00+00:00",
            "warmup_completed_at": None,
            "warmup_status": "warming",
            "warmup_error": None,
        }
        pending: dict[str, bool] = {}
        with (
            patch.object(rag_service, "_warmup_state", state),
            patch.object(rag_service, "_pending_ingestions", pending),
        ):
            rag_service.process_document_ingestion("deferred-doc", force=True)
            self.assertEqual(pending, {"deferred-doc": True})

            with patch.object(rag_service, "process_document_ingestion") as process:
                rag_service._finish_background_embedding_warmup(success=True)

        process.assert_called_once_with("deferred-doc", force=True)
        self.assertFalse(state["warming"])
        self.assertEqual(state["warmup_status"], "ready")

    def test_model_cache_settings_are_supported(self) -> None:
        with tempfile.TemporaryDirectory() as cache_root:
            variables = (
                "HF_HUB_CACHE",
                "SENTENCE_TRANSFORMERS_HOME",
                "TRANSFORMERS_CACHE",
                "HF_HOME",
            )
            for variable in variables:
                environment = {name: "" for name in variables}
                environment[variable] = cache_root
                with patch.dict(os.environ, environment):
                    cache_directory, source = (
                        rag_service._embedding_cache_configuration()
                    )

                expected_directory = Path(cache_root)
                if variable == "HF_HOME":
                    expected_directory /= "hub"
                self.assertEqual(cache_directory, expected_directory)
                self.assertEqual(source, variable)

    def test_model_cache_miss_is_logged_before_downloading(self) -> None:
        from huggingface_hub.errors import LocalEntryNotFoundError

        with tempfile.TemporaryDirectory() as cache_root:
            snapshot_directory = Path(cache_root) / "snapshot"
            environment = {
                "HF_HUB_CACHE": "",
                "SENTENCE_TRANSFORMERS_HOME": "",
                "TRANSFORMERS_CACHE": "",
                "HF_HOME": cache_root,
            }
            with (
                patch.dict(os.environ, environment),
                patch(
                    "huggingface_hub.snapshot_download",
                    side_effect=[
                        LocalEntryNotFoundError("cache miss"),
                        str(snapshot_directory),
                    ],
                ) as download,
                self.assertLogs(rag_service.logger, level="INFO") as logs,
            ):
                model_path, cache_directory, source = (
                    rag_service._resolve_embedding_model_source(
                        "sentence-transformers/all-MiniLM-L6-v2"
                    )
                )

        self.assertEqual(model_path, str(snapshot_directory))
        self.assertEqual(cache_directory, Path(cache_root) / "hub")
        self.assertEqual(source, "download")
        self.assertEqual(download.call_count, 2)
        self.assertTrue(download.call_args_list[0].kwargs["local_files_only"])
        self.assertFalse(download.call_args_list[1].kwargs["local_files_only"])
        output = "\n".join(logs.output)
        self.assertIn("Model cache lookup result=miss", output)
        self.assertIn("Model download started", output)
        self.assertIn("Model download completed", output)

    def test_model_cache_hit_skips_download(self) -> None:
        with tempfile.TemporaryDirectory() as cache_root:
            snapshot_directory = Path(cache_root) / "snapshot"
            environment = {
                "HF_HUB_CACHE": "",
                "SENTENCE_TRANSFORMERS_HOME": "",
                "TRANSFORMERS_CACHE": "",
                "HF_HOME": cache_root,
            }
            with (
                patch.dict(os.environ, environment),
                patch(
                    "huggingface_hub.snapshot_download",
                    return_value=str(snapshot_directory),
                ) as download,
                self.assertLogs(rag_service.logger, level="INFO") as logs,
            ):
                model_path, cache_directory, source = (
                    rag_service._resolve_embedding_model_source(
                        "sentence-transformers/all-MiniLM-L6-v2"
                    )
                )

        self.assertEqual(model_path, str(snapshot_directory))
        self.assertEqual(cache_directory, Path(cache_root) / "hub")
        self.assertEqual(source, "cache")
        download.assert_called_once()
        self.assertTrue(download.call_args.kwargs["local_files_only"])
        self.assertIn("Model cache lookup result=hit", "\n".join(logs.output))

    def test_model_local_path_skips_hugging_face_download(self) -> None:
        with tempfile.TemporaryDirectory() as model_directory:
            with patch("huggingface_hub.snapshot_download") as download:
                model_path, _, source = rag_service._resolve_embedding_model_source(
                    model_directory
                )

        self.assertEqual(model_path, str(Path(model_directory).resolve()))
        self.assertEqual(source, "local_path")
        download.assert_not_called()


if __name__ == "__main__":
    unittest.main()
