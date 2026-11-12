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
from app.services.groq_service import (
    GroqConfigurationError,
    GroqServiceError,
    _create_tls_context,
    generate_response,
)


class ChatRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

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

    def test_startup_logs_configuration_without_key_value(self) -> None:
        output = StringIO()

        with redirect_stdout(output):
            with TestClient(app):
                pass

        self.assertIn(
            f"GROQ_API_KEY loaded: {'YES' if settings.GROQ_API_KEY else 'NO'}",
            output.getvalue(),
        )
        self.assertIn(f"GROQ_MODEL: {settings.GROQ_MODEL}", output.getvalue())
        if settings.GROQ_API_KEY:
            self.assertNotIn(settings.GROQ_API_KEY, output.getvalue())

    @patch("app.routes.chat.generate_response", return_value="Try reconnecting.")
    def test_chat_returns_generated_response(
        self, generate_response_mock: MagicMock
    ) -> None:
        response = self.client.post(
            "/api/chat",
            json={"message": "My VPN is not connecting"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"response": "Try reconnecting."})
        generate_response_mock.assert_called_once_with("My VPN is not connecting")

    def test_chat_rejects_empty_message(self) -> None:
        response = self.client.post("/api/chat", json={"message": "  "})

        self.assertEqual(response.status_code, 422)

    @patch(
        "app.routes.chat.generate_response",
        side_effect=GroqConfigurationError("Missing API key"),
    )
    def test_chat_reports_missing_configuration(
        self, _generate_response_mock: MagicMock
    ) -> None:
        response = self.client.post("/api/chat", json={"message": "Help"})

        self.assertEqual(response.status_code, 503)

    @patch(
        "app.routes.chat.generate_response",
        side_effect=GroqServiceError("Upstream request failed"),
    )
    def test_chat_reports_upstream_failure(
        self, _generate_response_mock: MagicMock
    ) -> None:
        response = self.client.post("/api/chat", json={"message": "Help"})

        self.assertEqual(response.status_code, 502)

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

    @patch("app.services.groq_service.Groq")
    @patch("app.services.groq_service.httpx.Client")
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

        response = generate_response("My VPN is not connecting")

        self.assertEqual(response, "Try reconnecting.")
        call = groq_client.chat.completions.create.call_args.kwargs
        self.assertEqual(
            call["model"],
            settings.GROQ_MODEL,
        )
        self.assertEqual(
            call["messages"],
            [{"role": "user", "content": "My VPN is not connecting"}],
        )

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
            generate_response("Help")


if __name__ == "__main__":
    unittest.main()
