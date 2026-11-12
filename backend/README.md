# AI Service Desk Backend

Phase 1 FastAPI backend for an AI-powered IT service desk. The chat endpoint
sends messages to Groq and returns the generated response.

## Requirements

- Python 3.10 or newer
- A Groq API key

## Setup (Windows PowerShell)

From the `backend` directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Set `GROQ_API_KEY` in `.env`. The default model is
`openai/gpt-oss-20b`; optionally set `GROQ_MODEL` and comma-separated
`CORS_ORIGINS` there. The default CORS origins allow the Vite development
frontend at `http://localhost:5173` and `http://127.0.0.1:5173`.

Groq requests use TLS certificate verification with the operating system's
trusted CA certificates. If your organization intercepts outbound TLS and its
root CA is not in the system trust store, add that organization's PEM CA
certificate to the system trust store or set `GROQ_CA_BUNDLE` in `.env` to the
certificate file path (for example, `C:/certs/corporate-root-ca.pem`). Restart
the backend after changing the trust store or `.env`. Do not disable
certificate verification.

Run the API from the `backend` directory:

```powershell
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`. Interactive API documentation
is at `http://127.0.0.1:8000/docs`.

## Endpoints

### `GET /api/debug/config`

Returns whether a Groq API key is configured and the active model. The key
itself is never returned:

```json
{
  "groq_key_loaded": true,
  "model": "openai/gpt-oss-20b"
}
```

### `GET /`

Returns the service health:

```json
{
  "status": "running",
  "service": "AI Service Desk Backend"
}
```

### `POST /api/chat`

Request:

```json
{
  "message": "My VPN is not connecting"
}
```

Successful response:

```json
{
  "response": "AI generated response"
}
```

An empty or whitespace-only message is rejected with HTTP 422. If the Groq API
key is missing, the endpoint responds with HTTP 503; upstream Groq failures
respond with HTTP 502.

Run the backend tests with:

```powershell
python -m unittest discover -s tests -v
```
