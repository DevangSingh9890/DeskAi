import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class KnowledgeBaseRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.uploads_patch = patch(
            "app.services.file_service.UPLOADS_DIR",
            Path(self.temporary_directory.name) / "uploads",
        )
        self.uploads_patch.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.uploads_patch.stop()
        self.temporary_directory.cleanup()

    def test_upload_list_and_delete_document(self) -> None:
        upload_response = self.client.post(
            "/api/documents/upload",
            files={"file": ("VPN_Guide.PDF", b"pdf content", "application/pdf")},
        )

        self.assertEqual(upload_response.status_code, 201)
        uploaded = upload_response.json()
        self.assertEqual(uploaded["filename"], "VPN_Guide.PDF")
        self.assertEqual(uploaded["size"], len(b"pdf content"))
        self.assertTrue(uploaded["id"])
        self.assertTrue(uploaded["uploaded_at"])

        list_response = self.client.get("/api/documents")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            list_response.json(),
            [
                {
                    "id": uploaded["id"],
                    "filename": "VPN_Guide.PDF",
                    "size": len(b"pdf content"),
                    "uploaded_at": uploaded["uploaded_at"],
                }
            ],
        )

        delete_response = self.client.delete(f"/api/documents/{uploaded['id']}")

        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(
            delete_response.json(),
            {"message": "Document deleted successfully"},
        )
        self.assertEqual(self.client.get("/api/documents").json(), [])

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

    def test_upload_accepts_docx_and_txt(self) -> None:
        for filename in ("guide.docx", "notes.txt"):
            with self.subTest(filename=filename):
                response = self.client.post(
                    "/api/documents/upload",
                    files={"file": (filename, b"document content")},
                )

                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json()["filename"], filename)

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
