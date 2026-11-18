import unittest
from contextlib import redirect_stdout
from io import StringIO
import ssl
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
from groq import APIConnectionError
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models.classification import IncidentClassification
from app.services.groq_service import (
    GroqConfigurationError,
    GroqServiceError,
    SYSTEM_PROMPT,
    _create_tls_context,
    generate_response,
)


class ChatRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.classification = IncidentClassification(
            issue="VPN connection failure",
            category="Network",
            subcategory="VPN",
            priority="High",
            impact="Single User",
            assigned_group="Network Support",
            confidence_score=0.95,
        )
        classify_patch = patch(
            "app.routes.chat.classify_incident",
            return_value=self.classification,
        )
        self.classify_mock = classify_patch.start()
        self.addCleanup(classify_patch.stop)

    def test_health_check(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "running", "service": "AI Service Desk Backend"},
        )

    def test_debug_config_does_not_expose_api_key(self) -> None:
        response = self.client.get("/api/debug/config")

        self.assertEqual(
            response.json(),
            {
                "groq_key_loaded": bool(settings.GROQ_API_KEY),
                "model": settings.GROQ_MODEL,
            },
        )
        if settings.GROQ_API_KEY:
            self.assertNotIn(settings.GROQ_API_KEY, response.text)

    def test_debug_performance_reports_model_and_document_count(self) -> None:
        with (
            patch("app.routes.chat.is_embedding_model_loaded", return_value=True),
            patch(
                "app.routes.chat.get_embedding_warmup_status",
                return_value={
                    "warming": False,
                    "embedding_model_loaded": True,
                    "warmup_started_at": "2026-11-16T00:00:00+00:00",
                    "warmup_completed_at": "2026-11-16T00:00:20+00:00",
                    "warmup_status": "ready",
                    "warmup_error": None,
                },
            ),
            patch(
                "app.routes.chat.list_documents",
                return_value=[
                    SimpleNamespace(ingestion_status="Indexed") for _ in range(5)
                ]
                + [SimpleNamespace(ingestion_status="Processing")],
            ),
        ):
            response = self.client.get("/api/debug/performance")

        self.assertEqual(
            response.json(),
            {
                "warming": False,
                "embedding_model_loaded": True,
                "warmup_started_at": "2026-11-16T00:00:00+00:00",
                "warmup_completed_at": "2026-11-16T00:00:20+00:00",
                "warmup_status": "ready",
                "warmup_error": None,
                "model": settings.EMBEDDING_MODEL,
                "model_loaded": True,
                "model_name": settings.EMBEDDING_MODEL,
                "documents_indexed": 5,
            },
        )

    def test_admin_warmup_requires_key_and_warms_model(self) -> None:
        with patch(
            "app.routes.chat.settings",
            SimpleNamespace(ADMIN_API_KEY=""),
        ):
            disabled = self.client.post("/api/admin/warmup")
        self.assertEqual(disabled.status_code, 503)

        with (
            patch(
                "app.routes.chat.settings",
                SimpleNamespace(ADMIN_API_KEY="test-admin-key"),
            ),
            patch("app.routes.chat.warm_up_embedding_service") as warmup,
        ):
            unauthorized = self.client.post("/api/admin/warmup")
            invalid_key = self.client.post(
                "/api/admin/warmup",
                headers={"X-Admin-Key": "wrong-key"},
            )
            response = self.client.post(
                "/api/admin/warmup",
                headers={"X-Admin-Key": "test-admin-key"},
            )

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(invalid_key.status_code, 401)
        self.assertEqual(
            response.json(),
            {"status": "ready", "model_loaded": True},
        )
        warmup.assert_called_once_with()

    def test_startup_logs_configuration_without_key_value(self) -> None:
        output = StringIO()

        with redirect_stdout(output):
            with patch("app.main.initialize_database") as initialize_database:
                with patch(
                    "app.services.rag_service.initialize_embedding_service"
                ) as initialize:
                    with patch(
                        "app.services.rag_service.start_background_embedding_warmup"
                    ) as start:
                        with patch(
                            "app.services.rag_service.EmbeddingService.get_model"
                        ) as get_model:
                            with patch(
                                "app.main.recover_interrupted_ingestions"
                            ) as recover:
                                with self.assertLogs("app.main", level="INFO") as logs:
                                    with TestClient(app):
                                        pass
        initialize_database.assert_called_once_with()
        initialize.assert_not_called()
        get_model.assert_not_called()
        recover.assert_called_once_with()
        start.assert_not_called()

        self.assertIn("Backend started", "\n".join(logs.output))
        self.assertIn("Backend startup complete", "\n".join(logs.output))
        self.assertIn("Embedding model not loaded yet", "\n".join(logs.output))
        self.assertIn(
            f"GROQ_API_KEY loaded: {'YES' if settings.GROQ_API_KEY else 'NO'}",
            output.getvalue(),
        )
        self.assertIn(f"GROQ_MODEL: {settings.GROQ_MODEL}", output.getvalue())
        if settings.GROQ_API_KEY:
            self.assertNotIn(settings.GROQ_API_KEY, output.getvalue())

    @patch("app.routes.chat.search_knowledge")
    @patch("app.routes.chat.generate_response", return_value="Try reconnecting.")
    def test_chat_returns_generated_response(
        self, generate_response_mock: MagicMock, search_knowledge_mock: MagicMock
    ) -> None:
        search_knowledge_mock.return_value = [
            {
                "content": "Restart the VPN client.",
                "metadata": {"filename": "VPN_Guide.pdf"},
                "score": 0.9,
            }
        ]
        response = self.client.post(
            "/api/chat",
            json={"message": "My VPN is not connecting"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "response": "Try reconnecting.\n\nSources: VPN_Guide.pdf",
                "classification": self.classification.model_dump(),
            },
        )
        search_knowledge_mock.assert_called_once_with("My VPN is not connecting")
        generate_response_mock.assert_called_once_with(
            "My VPN is not connecting",
            "Source document: VPN_Guide.pdf\nContent: Restart the VPN client.",
        )

    @patch("app.routes.chat.search_knowledge", return_value=[])
    @patch("app.routes.chat.generate_response")
    def test_chat_returns_fallback_without_relevant_context(
        self, generate_response_mock: MagicMock, search_knowledge_mock: MagicMock
    ) -> None:
        response = self.client.post("/api/chat", json={"message": "Help"})

        self.assertEqual(
            response.json(),
            {
                "response": (
                    "I could not find this information in the knowledge base."
                ),
                "classification": self.classification.model_dump(),
            },
        )
        generate_response_mock.assert_not_called()
        search_knowledge_mock.assert_called_once_with("Help")
        self.classify_mock.assert_called_once_with("Help")

    @patch(
        "app.routes.chat.search_knowledge",
        return_value=[
            {
                "content": "Some unrelated excerpt.",
                "metadata": {"filename": "VPN_Guide.pdf"},
                "score": 0.9,
            }
        ],
    )
    @patch(
        "app.routes.chat.generate_response",
        return_value="I could not find this information in the knowledge base.",
    )
    def test_chat_preserves_exact_fallback_when_context_does_not_answer(
        self, generate_response_mock: MagicMock, search_knowledge_mock: MagicMock
    ) -> None:
        response = self.client.post("/api/chat", json={"message": "Help"})

        self.assertEqual(
            response.json(),
            {
                "response": (
                    "I could not find this information in the knowledge base."
                ),
                "classification": self.classification.model_dump(),
            },
        )
        search_knowledge_mock.assert_called_once_with("Help")
        generate_response_mock.assert_called_once()

    def test_classify_endpoint_returns_structured_classification(self) -> None:
        response = self.client.post(
            "/api/classify",
            json={
                "message": (
                    "My VPN is not connecting and I have a client meeting soon."
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), self.classification.model_dump())
        self.classify_mock.assert_called_once_with(
            "My VPN is not connecting and I have a client meeting soon."
        )

    def test_classify_endpoint_works_during_embedding_warmup(self) -> None:
        response = self.client.post(
            "/api/classify",
            json={"message": "My VPN is not connecting"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), self.classification.model_dump())
        self.classify_mock.assert_called_once_with("My VPN is not connecting")

    def test_classify_endpoint_rejects_empty_message(self) -> None:
        response = self.client.post("/api/classify", json={"message": " "})

        self.assertEqual(response.status_code, 422)

    def test_chat_rejects_empty_message(self) -> None:
        response = self.client.post("/api/chat", json={"message": "  "})

        self.assertEqual(response.status_code, 422)

    @patch(
        "app.routes.chat.generate_response",
        side_effect=GroqConfigurationError("Missing API key"),
    )
    def test_chat_reports_missing_configuration(
        self, generate_response_mock: MagicMock
    ) -> None:
        with patch(
            "app.routes.chat.search_knowledge",
            return_value=[
                {
                    "content": "VPN steps.",
                    "metadata": {"filename": "VPN.pdf"},
                    "score": 0.9,
                }
            ],
        ):
            response = self.client.post("/api/chat", json={"message": "Help"})

        self.assertEqual(response.status_code, 503)
        generate_response_mock.assert_called_once()

    @patch(
        "app.routes.chat.generate_response",
        side_effect=GroqServiceError("Upstream request failed"),
    )
    def test_chat_reports_upstream_failure(
        self, generate_response_mock: MagicMock
    ) -> None:
        with patch(
            "app.routes.chat.search_knowledge",
            return_value=[
                {
                    "content": "VPN steps.",
                    "metadata": {"filename": "VPN.pdf"},
                    "score": 0.9,
                }
            ],
        ):
            response = self.client.post("/api/chat", json={"message": "Help"})

        self.assertEqual(response.status_code, 502)
        generate_response_mock.assert_called_once()

    def test_chat_allows_frontend_cors_origin(self) -> None:
        response = self.client.options(
            "/api/chat",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:5173",
        )


class GroqServiceTests(unittest.TestCase):
    def test_tls_context_keeps_certificate_verification_enabled(self) -> None:
        context = _create_tls_context()

        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    @patch("groq.Groq")
    @patch("httpx.Client")
    def test_groq_client_receives_verified_http_client(
        self, http_client_constructor: MagicMock, groq_constructor: MagicMock
    ) -> None:
        with patch("app.services.groq_service._client", None):
            from app.services.groq_service import _get_client

            _get_client()

        groq_constructor.assert_called_once()
        groq_kwargs = groq_constructor.call_args.kwargs
        self.assertEqual(groq_kwargs["api_key"], settings.GROQ_API_KEY)
        self.assertIs(groq_kwargs["http_client"], http_client_constructor.return_value)
        context = http_client_constructor.call_args.kwargs["verify"]
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    @patch("app.services.groq_service._get_client")
    def test_generate_response_uses_groq_and_trims_result(
        self, get_client_mock: MagicMock
    ) -> None:
        groq_client = get_client_mock.return_value
        groq_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="  Try reconnecting.  ")
                )
            ]
        )

        response = generate_response(
            "My VPN is not connecting",
            "Source document: VPN_Guide.pdf\nContent: Restart the VPN client.",
        )

        self.assertEqual(response, "Try reconnecting.")
        call = groq_client.chat.completions.create.call_args.kwargs
        self.assertEqual(
            call["model"],
            settings.GROQ_MODEL,
        )
        self.assertEqual(
            call["messages"],
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Context:\nSource document: VPN_Guide.pdf\n"
                        "Content: Restart the VPN client.\n\n"
                        "Question:\nMy VPN is not connecting"
                    ),
                },
            ],
        )

    @patch("app.services.groq_service._get_client")
    def test_generate_json_response_uses_json_mode(
        self, get_client_mock: MagicMock
    ) -> None:
        from app.services.groq_service import generate_json_response

        get_client_mock.return_value.chat.completions.create.return_value = (
            SimpleNamespace(
                choices=[
                    SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))
                ]
            )
        )

        result = generate_json_response("Return JSON.", "Classify this.")

        self.assertEqual(result, '{"ok": true}')
        call = get_client_mock.return_value.chat.completions.create.call_args.kwargs
        self.assertEqual(call["response_format"], {"type": "json_object"})

    @patch("app.services.groq_service._get_client")
    def test_tls_failure_is_reported_as_groq_service_error(
        self, get_client_mock: MagicMock
    ) -> None:
        get_client_mock.return_value.chat.completions.create.side_effect = (
            APIConnectionError(
                message="TLS verification failed",
                request=httpx.Request("POST", "https://api.groq.com"),
            )
        )

        with self.assertRaisesRegex(GroqServiceError, "secure connection to Groq"):
            generate_response("Help", "Available context")


if __name__ == "__main__":
    unittest.main()
