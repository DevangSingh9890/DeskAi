import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import file_service
from app.services.rag_service import recover_interrupted_ingestions


class KnowledgeBaseRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.uploads_patch = patch(
            "app.services.file_service.UPLOADS_DIR",
            Path(self.temporary_directory.name) / "uploads",
        )
        self.uploads_dir = Path(self.temporary_directory.name) / "uploads"
        self.uploads_patch.start()
        self.worker_patch = patch("app.routes.knowledge_base.process_document_ingestion")
        self.worker_mock = self.worker_patch.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.worker_patch.stop()
        self.uploads_patch.stop()
        self.temporary_directory.cleanup()

    def test_upload_list_and_delete_document(self) -> None:
        upload_response = self.client.post(
            "/api/documents/upload",
            files={"file": ("VPN_Guide.PDF", b"pdf content", "application/pdf")},
        )

        self.assertEqual(upload_response.status_code, 201)
        uploaded = upload_response.json()
        self.assertEqual(uploaded["status"], "processing")
        self.assertTrue(uploaded["document_id"])
        self.worker_mock.assert_called_once_with(uploaded["document_id"])

        list_response = self.client.get("/api/documents")
        listed_document = list_response.json()[0]

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(listed_document["id"], uploaded["document_id"])
        self.assertEqual(listed_document["filename"], "VPN_Guide.PDF")
        self.assertEqual(listed_document["size"], len(b"pdf content"))
        self.assertEqual(listed_document["ingestion_status"], "Processing")
        self.assertEqual(listed_document["indexed_chunks"], 0)
        self.assertEqual(listed_document["processing_stage"], "queued")
        self.assertIsNone(listed_document["processing_error"])

        status_response = self.client.get(
            f"/api/documents/{uploaded['document_id']}/status"
        )
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "processing")
        self.assertEqual(status_response.json()["stage"], "queued")

        with patch("app.services.rag_service.delete_document_vectors", return_value=0):
            delete_response = self.client.delete(
                f"/api/documents/{uploaded['document_id']}"
            )

        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(
            delete_response.json(),
            {"message": "Document deleted successfully"},
        )
        self.assertEqual(self.client.get("/api/documents").json(), [])

    def test_upload_is_saved_and_queued_while_embedding_warms(self) -> None:
        with patch(
            "app.routes.knowledge_base.is_embedding_model_warming",
            return_value=True,
        ):
            response = self.client.post(
                "/api/documents/upload",
                files={"file": ("queued.txt", b"document content", "text/plain")},
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json(),
            {
                "status": "warming",
                "message": "Embedding model is still warming up. Please wait.",
            },
        )
        self.worker_mock.assert_called_once()
        listed = self.client.get("/api/documents").json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["ingestion_status"], "Processing")
        self.assertEqual(listed[0]["processing_stage"], "queued")

    def test_upload_rejects_unsupported_extension(self) -> None:
        response = self.client.post(
            "/api/documents/upload",
            files={"file": ("notes.exe", b"not allowed")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Only PDF, DOCX, and TXT files are supported.",
        )

    def test_interrupted_indexing_is_reported_as_failed(self) -> None:
        upload_response = self.client.post(
            "/api/documents/upload",
            files={"file": ("notes.txt", b"document content")},
        )
        document_id = upload_response.json()["document_id"]

        recover_interrupted_ingestions()
        response = self.client.get(f"/api/documents/{document_id}/status")

        self.assertEqual(response.json()["status"], "failed")
        self.assertEqual(response.json()["stage"], "queued")
        self.assertIn("backend restart", response.json()["error"])

    def test_missing_stored_file_does_not_block_recovery_of_other_documents(
        self,
    ) -> None:
        missing_file_upload = self.client.post(
            "/api/documents/upload",
            files={"file": ("missing.txt", b"document content")},
        )
        pending_upload = self.client.post(
            "/api/documents/upload",
            files={"file": ("pending.txt", b"document content")},
        )
        missing_id = missing_file_upload.json()["document_id"]
        pending_id = pending_upload.json()["document_id"]
        (self.uploads_dir / f"{missing_id}.txt").unlink()

        with self.assertLogs(file_service.logger, level="WARNING") as logs:
            recover_interrupted_ingestions()

        self.assertIn("Skipping orphan document metadata", "\n".join(logs.output))
        pending_status = self.client.get(f"/api/documents/{pending_id}/status")
        self.assertEqual(pending_status.json()["status"], "failed")
        listed_documents = self.client.get("/api/documents").json()
        self.assertEqual([document["id"] for document in listed_documents], [pending_id])

    def test_upload_accepts_docx_and_txt(self) -> None:
        for filename in ("guide.docx", "notes.txt"):
            with self.subTest(filename=filename):
                response = self.client.post(
                    "/api/documents/upload",
                    files={"file": (filename, b"document content")},
                )

                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json()["status"], "processing")
                self.assertTrue(response.json()["document_id"])

    def test_upload_rejects_empty_file(self) -> None:
        response = self.client.post(
            "/api/documents/upload",
            files={"file": ("empty.txt", b"")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "The uploaded file is empty.")
        self.assertEqual(self.client.get("/api/documents").json(), [])

    def test_delete_returns_not_found_for_unknown_document(self) -> None:
        response = self.client.delete(
            "/api/documents/00000000-0000-0000-0000-000000000000"
        )

        self.assertEqual(response.status_code, 404)

    def test_upload_directory_is_created_automatically(self) -> None:
        uploads_directory = Path(self.temporary_directory.name) / "uploads"

        self.assertFalse(uploads_directory.exists())
        response = self.client.get("/api/documents")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(uploads_directory.is_dir())


if __name__ == "__main__":
    unittest.main()
