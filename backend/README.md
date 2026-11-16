# AI Service Desk Backend

FastAPI backend for DeskAI. Chat generation uses Groq. Knowledge-base documents
are chunked and embedded locally with Sentence Transformers, then stored in a
persistent ChromaDB collection for semantic retrieval.

## Requirements

- Python 3.10 or newer
- A Groq API key
- Internet access on first use to download the configured embedding model if it
  is not already cached (no Hugging Face API key is required)

## Setup (Windows PowerShell)

From the `backend` directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set `GROQ_API_KEY`. The default Groq model is
`openai/gpt-oss-20b`. RAG settings are:

| Variable | Default | Description |
| --- | --- | --- |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local document and query embedding model |
| `CHROMA_PERSIST_DIRECTORY` | `./chroma_db` | Persistent vector database directory, relative to `backend` |
| `CHROMA_COLLECTION_NAME` | `deskai_knowledge` | Chroma collection |
| `RAG_RELEVANCE_THRESHOLD` | `0.35` | Minimum LangChain cosine relevance score returned in search results |
| `HF_HOME` | Hugging Face default | Hugging Face cache root; snapshots are stored under `hub` |
| `TRANSFORMERS_CACHE` | Hugging Face default | Optional Transformers cache directory |
| `SENTENCE_TRANSFORMERS_HOME` | Sentence Transformers default | Optional Sentence Transformers cache directory |
| `ADMIN_API_KEY` | unset | Required to enable the protected model warm-up endpoint |

No OpenAI embedding key or Hugging Face key is used. The API starts without
loading the embedding model; it is loaded once per backend process on the first
document-ingestion or semantic-search request and reused afterward. The first
RAG request may take longer while the model is loaded or downloaded.
Existing comma-separated `CORS_ORIGINS` configuration is unchanged.

## Embedding model cache and warm-up

The first model use checks the configured local model path, then performs an
offline Hugging Face cache lookup. On a miss, the backend downloads the model
and logs cache lookup, download, model initialization, and total model-load
times separately. Subsequent requests reuse the in-memory model. Cache
directory precedence is `HF_HUB_CACHE`, `SENTENCE_TRANSFORMERS_HOME`,
`TRANSFORMERS_CACHE`, then `HF_HOME/hub`; without these settings, the Hugging
Face default cache is used.

Pre-download the model during image or deployment preparation, rather than
making production requests wait for a network download:

```powershell
python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='sentence-transformers/all-MiniLM-L6-v2', local_dir='models/all-MiniLM-L6-v2')"
```

Then set `EMBEDDING_MODEL=./models/all-MiniLM-L6-v2`. The local model path is
resolved relative to the backend directory. Mount that directory read-only in
production. To prohibit Hub network access, set `HF_HUB_OFFLINE=1`; the backend
will fail explicitly if the local model files are missing.

Backend startup launches a daemon thread that loads the model and runs a sample
embedding. Startup does not wait for this work. The performance endpoint and UI
report whether the RAG engine is warming, ready, or unavailable. The UI keeps
uploads enabled while warming; uploaded files are queued and indexed when
warm-up finishes.

To explicitly run or verify warm-up after deployment, set a private
`ADMIN_API_KEY` and call the protected endpoint:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/admin/warmup `
  -Headers @{ "X-Admin-Key" = $env:ADMIN_API_KEY }
```

The model remains in memory for the lifetime of that worker process. Each
Uvicorn worker process has its own model instance.

Groq requests use TLS certificate verification with the operating system's
trusted CA certificates. If your organization intercepts outbound TLS and its
root CA is not in the system trust store, add that organization's PEM CA
certificate to the system trust store or set `GROQ_CA_BUNDLE` in `.env` to the
certificate file path (for example, `C:/certs/corporate-root-ca.pem`). Restart
the backend after changing the trust store or `.env`. Do not disable
certificate verification.

Run the API from the `backend` directory:

```powershell
python -m uvicorn app.main:app --reload --reload-dir app
```

Run this after activating the virtual environment above so Uvicorn uses the
same Python interpreter where `requirements.txt` was installed.

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

### `GET /api/debug/performance`

Returns warm-up state, timestamps, configured model, and indexed-document count.
It does not initialize the model:

```json
{
  "warming": true,
  "embedding_model_loaded": false,
  "warmup_started_at": "2026-11-16T05:30:00+00:00",
  "warmup_completed_at": null,
  "warmup_status": "warming",
  "warmup_error": null,
  "model": "sentence-transformers/all-MiniLM-L6-v2",
  "model_loaded": false,
  "model_name": "sentence-transformers/all-MiniLM-L6-v2",
  "documents_indexed": 5
}
```

The frontend displays **RAG Engine Warming Up** or **RAG Engine Ready** from
these fields. While warming, uploads are saved and queued without starting
indexing; the upload response is:

```json
{
  "status": "warming",
  "message": "Embedding model is still warming up. Please wait."
}
```

### `POST /api/admin/warmup`

Verifies embedding generation using the existing singleton. The endpoint is
disabled unless `ADMIN_API_KEY` is configured and requires that value in the
`X-Admin-Key` header.

### `GET /`

Returns the service health:

```json
{
  "status": "running",
  "service": "AI Service Desk Backend"
}
```

### `GET /api/health`

Returns backend readiness and whether this process has loaded the embedding
model. Checking health does not load the model:

```json
{
  "backend": "ready",
  "embedding_model_loaded": false
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
  "response": "AI generated response",
  "classification": {
    "issue": "VPN connection failure",
    "category": "Network",
    "subcategory": "VPN",
    "priority": "High",
    "impact": "Single User",
    "assigned_group": "Network Support",
    "confidence_score": 0.95
  }
}
```

Every chat response includes the incident classification. Chat classification
uses Groq structured JSON output validated against a Pydantic schema; the
assistant response still uses indexed knowledge-base context. An empty or
whitespace-only message is rejected with HTTP 422. If the Groq API key is
missing, the endpoint responds with HTTP 503; upstream Groq failures respond
with HTTP 502.

### `POST /api/agent/chat`

Runs the LangGraph service-desk workflow: supervisor routing, incident
classification, Chroma knowledge retrieval, and context-grounded
troubleshooting. The supervisor can skip agents that are not needed.

Request:

```json
{
  "message": "My VPN is not connecting"
}
```

The response contains the existing classification fields (including
`confidence_score` and the `confidence` alias), unique knowledge source names,
structured troubleshooting, and a formatted response:

```json
{
  "classification": {
    "category": "Network",
    "subcategory": "VPN",
    "priority": "High",
    "impact": "Single User",
    "assigned_group": "Network Support",
    "confidence": 0.95
  },
  "knowledge_sources": ["VPN Guide.pdf"],
  "troubleshooting": {
    "likely_cause": "The VPN client is disconnected.",
    "troubleshooting_steps": ["Restart the VPN client."],
    "escalation_recommendation": "Contact Network Support if the issue continues."
  },
  "response": "Likely cause: ...\nTroubleshooting steps:\n..."
}
```

### `POST /api/classify`

Classifies an incident without generating a knowledge-base answer.

Request:

```json
{
  "message": "My VPN is not connecting and I have a client meeting in 30 minutes."
}
```

Response:

```json
{
  "issue": "VPN connection failure",
  "category": "Network",
  "subcategory": "VPN",
  "priority": "High",
  "impact": "Single User",
  "assigned_group": "Network Support",
  "confidence_score": 0.95
}
```

The supported categories are Network, Software, Hardware, Email, Access
Management, Security, Database, Cloud, and Collaboration Tools. Priority is
Critical, High, Medium, or Low. Confidence is a model-estimated score from 0
to 1, not a calibrated probability. Invalid structured output or an upstream
failure returns HTTP 502.

### `POST /api/documents/upload`

Upload a PDF, DOCX, or TXT file as multipart form data using the `file` field.
The backend saves the file and schedules indexing in the background. It returns
HTTP 201 without waiting for extraction or embedding:

```json
{
  "document_id": "generated-uuid",
  "status": "processing",
  "stage": "queued",
  "error": null
}
```

Empty files and unsupported file extensions are rejected with HTTP 400.

### `GET /api/documents`

Returns document metadata and each document's ingestion status, current stage,
indexed chunk count, and any indexing error.

### `GET /api/documents/{document_id}/status`

Returns `document_id`, `status` (`uploaded`, `processing`, `completed`, or
`failed`), `stage`, and `error`. A failed response includes the failing stage
and the error message, for example:

```json
{
  "document_id": "generated-uuid",
  "status": "failed",
  "stage": "embedding_generation",
  "error": "The local embedding model is unavailable: ..."
}
```

### `DELETE /api/documents/{document_id}`

Deletes the uploaded document and its vectors. If vector deletion fails, the
document files are retained and the endpoint returns an error.

### `POST /api/knowledge-base/{document_id}/ingest`

Schedules indexing for an already-uploaded PDF, TXT, or DOCX file and returns
HTTP 202. Repeated requests while processing do not schedule duplicate work.
To explicitly re-index a completed document, use `?force=true`.

### `POST /api/knowledge-base/search`

Request:

```json
{
  "query": "My VPN is not connecting and authentication keeps failing",
  "top_k": 4
}
```

Response results include chunk text, filename, document ID, chunk ID, and the
actual LangChain cosine relevance score:

```json
{
  "query": "My VPN is not connecting and authentication keeps failing",
  "results": [
    {
      "content": "VPN troubleshooting steps...",
      "metadata": {
        "filename": "VPN_Troubleshooting.pdf",
        "document_id": "123",
        "chunk_id": "123_chunk_1"
      },
      "score": 0.85
    }
  ]
}
```

Only scores meeting `RAG_RELEVANCE_THRESHOLD` are returned. Empty or
unsupported queries can return an empty `results` array; model or database
failures return HTTP 503 rather than fabricated results.

### `GET /api/knowledge-base/stats`

Returns indexed document and chunk counts, the collection name, and vector
database availability. Counts are `null` when the database is unavailable.

### `DELETE /api/knowledge-base/{document_id}/vectors`

Deletes all vectors for an uploaded document but keeps the original file and
resets its ingestion status to `Uploaded`.

## Ingestion and persistence

The existing upload endpoint remains the only upload mechanism and schedules
indexing after saving the file. LangChain loaders extract PDF, TXT, and DOCX text;
`RecursiveCharacterTextSplitter` creates 1000-character chunks with
200-character overlap. The local `HuggingFaceEmbeddings` integration loads once
per process and embeds document chunks in batches. Chroma uses local persistent
storage at `backend/chroma_db` by default, with anonymized telemetry disabled.
FastAPI background tasks keep indexing out of the upload request; status is
persisted with the document metadata and the frontend polls while processing.
Jobs interrupted by a restart are marked failed with a retryable status.

FastAPI background tasks are in-process and are not a durable queue. For
multi-worker production deployments or guaranteed recovery after a process
restart, move indexing to a persistent task queue.

To confirm indexed vectors exist, call `GET /api/knowledge-base/stats` and
check `total_indexed_chunks`, or inspect the Chroma SQLite files under
`backend/chroma_db`. Restart FastAPI and call the stats endpoint or repeat a
semantic search; the collection and vectors should remain available.

Run the backend tests with:

```powershell
python -m unittest discover -s tests -v
```
