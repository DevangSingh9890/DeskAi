import logging
import ssl
from pathlib import Path
from threading import Lock

import httpx
from groq import APIConnectionError, APIError, Groq

from app.core.config import ENV_FILE, settings

logger = logging.getLogger(__name__)
_client: Groq | None = None
_client_lock = Lock()


class GroqConfigurationError(RuntimeError):
    pass


class GroqServiceError(RuntimeError):
    pass


def _create_tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    if settings.GROQ_CA_BUNDLE:
        ca_bundle = Path(settings.GROQ_CA_BUNDLE).expanduser()
        if not ca_bundle.is_file():
            raise GroqConfigurationError(
                f"GROQ_CA_BUNDLE does not point to a readable CA bundle: {ca_bundle}"
            )
        try:
            context.load_verify_locations(cafile=str(ca_bundle))
        except ssl.SSLError as exc:
            raise GroqConfigurationError(
                f"GROQ_CA_BUNDLE is not a valid CA certificate file: {ca_bundle}"
            ) from exc
    return context


def _get_client() -> Groq:
    global _client

    if not settings.GROQ_API_KEY:
        raise GroqConfigurationError(
            f"GROQ_API_KEY is empty. Set it in the environment or {ENV_FILE}."
        )

    if _client is None:
        with _client_lock:
            if _client is None:
                http_client = httpx.Client(verify=_create_tls_context())
                _client = Groq(
                    api_key=settings.GROQ_API_KEY,
                    http_client=http_client,
                )

    return _client


def generate_response(message: str) -> str:
    try:
        completion = _get_client().chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": message}],
        )
    except GroqConfigurationError:
        logger.exception("Groq configuration is missing")
        raise
    except APIConnectionError as exc:
        logger.exception(
            "Could not connect to Groq. Check network/proxy connectivity and "
            "the system trusted CA store; if required, configure GROQ_CA_BUNDLE."
        )
        raise GroqServiceError(
            "Unable to establish a secure connection to Groq."
        ) from exc
    except APIError as exc:
        logger.exception("Groq API request failed")
        raise GroqServiceError("The Groq API request failed.") from exc

    if not completion.choices:
        logger.error("Groq returned a completion without any choices")
        raise GroqServiceError("The Groq API returned no response.")

    response = completion.choices[0].message.content
    if response is None or not response.strip():
        logger.error("Groq returned an empty response")
        raise GroqServiceError("The Groq API returned an empty response.")

    return response.strip()
