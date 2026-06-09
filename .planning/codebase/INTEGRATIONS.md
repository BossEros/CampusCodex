# External Integrations

**Analysis Date:** 2026-06-09

## APIs & External Services

**LLM Providers (pluggable via `llm_provider` setting):**

- **Groq** — default LLM provider; used for text generation and query rewriting
  - SDK/Client: `langchain-groq 1.1.2` → `langchain_groq.ChatGroq`
  - Implementation: `backend/app/llm/groq_provider.py`
  - Auth: `GROQ_API_KEY` env var
  - Default model: `llama-3.1-8b-instant` (configurable via `llm_model_name`)
  - Called via: LangChain LCEL chain (`prompt | self.llm`)

- **Anthropic** — optional LLM provider; used for text generation and query rewriting
  - SDK/Client: `anthropic 0.97.0` → `anthropic.Anthropic`
  - Implementation: `backend/app/llm/anthropic_provider.py`
  - Auth: `ANTHROPIC_API_KEY` env var
  - Called via: `client.messages.create()` (raw SDK, not LangChain)
  - Max tokens: 1024 for answers, 128 for query rewriting

- **Google Gemini** — optional LLM provider; used for text generation and query rewriting
  - SDK/Client: `google-genai 1.74.0` → `google.genai.Client`
  - Implementation: `backend/app/llm/gemini_provider.py`
  - Auth: `GEMINI_API_KEY` env var
  - Called via: `client.models.generate_content()` with `GenerateContentConfig`
  - Max tokens: 1024 for answers, 128 for query rewriting

**Provider Selection:**
- Factory pattern: `backend/app/llm/factory.py` → `create_llm_provider()`
- Selected by `settings.llm_provider` at call time (not cached at startup)
- Protocol interface: `backend/app/llm/provider.py` → `LlmProvider` (structural subtyping via `typing.Protocol`)

**HuggingFace Hub (implicit, via sentence-transformers):**
- Embedding model: `sentence-transformers/multi-qa-MiniLM-L6-cos-v1` — downloaded on first use, cached locally
- Reranker model: `cross-encoder/ms-marco-MiniLM-L6-v2` — downloaded on first use, cached locally
- No API key required (public models)
- Used in: `backend/app/rag/vector_store.py` (embeddings), `backend/app/rag/reranker.py` (reranker)

## Data Storage

**Vector Store:**
- Type: FAISS (Facebook AI Similarity Search) — local file-based index
  - Client: `langchain-community` FAISS wrapper (`langchain_community.vectorstores.FAISS`)
  - Index path: `data/indexes/faiss_student_manual/` (configurable via `faiss_index_path`)
  - Persistence: saved/loaded from local filesystem
  - Built offline via: `backend/app/scripts/build_index.py`
  - Loaded at API startup in `backend/app/main.py` lifespan handler

**Source Documents:**
- Type: Local PDF file
  - Path: `data/raw/student_manual_2019.pdf`
  - Parser: `pdfplumber` via `langchain_community.document_loaders.PDFPlumberLoader`
  - Used during: FAISS index build only (not during query serving)

**Relational Database:**
- Not applicable — no relational database is used.

**File Storage:**
- Local filesystem only (`data/` directory at project root)

**Caching:**
- In-process module-level singleton for the CrossEncoder reranker model (`backend/app/rag/reranker.py`, `reranker_model` global)
- FAISS vector store held as a module-level global in `backend/app/main.py` (`vector_store` global)
- No external cache layer (Redis, Memcached, etc.)

## Authentication & Identity

**Auth Provider:**
- None — the API has no user authentication or session management.
- CORS is restricted to `http://localhost:5173` and `http://127.0.0.1:5173` only (`backend/app/main.py` lines 24–27); `allow_credentials` is `False`.

## Monitoring & Observability

**Error Tracking:**
- None detected — no Sentry, Datadog, or similar SDK present.

**Logs:**
- FastAPI/Uvicorn default stdout logging only.
- No structured logging library (e.g., `loguru`, `structlog`) is used.

## CI/CD & Deployment

**Hosting:**
- Not configured — no Dockerfile, `docker-compose.yml`, Heroku Procfile, or cloud platform manifest found in the repository.

**CI Pipeline:**
- Not configured — no `.github/workflows/`, `.gitlab-ci.yml`, or equivalent detected.

## Environment Configuration

**Required env vars (must be set in `backend/.env`):**
- `GROQ_API_KEY` — required when `llm_provider=groq` (default)
- `ANTHROPIC_API_KEY` — required when `llm_provider=anthropic`
- `GEMINI_API_KEY` — required when `llm_provider=gemini`

**Optional env vars (all have defaults in `backend/app/core/config.py`):**
- `LLM_PROVIDER` — selects active LLM backend (default: `"groq"`)
- `LLM_MODEL_NAME` — model identifier passed to the active provider (default: `"llama-3.1-8b-instant"`)
- `EMBEDDING_MODEL_NAME` — HuggingFace embedding model (default: `"sentence-transformers/multi-qa-MiniLM-L6-cos-v1"`)
- `FAISS_INDEX_PATH` — path to FAISS index directory
- `PDF_PATH` — path to source PDF
- `RETRIEVAL_CANDIDATE_K` — number of candidates retrieved before reranking (default: `15`)
- `RERANKED_TOP_K` — top documents passed to LLM after reranking (default: `5`)
- `RERANKER_MODEL_NAME` — HuggingFace cross-encoder model (default: `"cross-encoder/ms-marco-MiniLM-L6-v2"`)
- `ENABLE_QUERY_REWRITE` — enable LLM-based follow-up query rewriting (default: `True`)

**Frontend:**
- `VITE_API_BASE_URL` — overrides the backend URL (default: `http://127.0.0.1:8000`)

**Secrets location:**
- `backend/.env` (not committed; loaded by pydantic-settings at startup)

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

---

*Integration audit: 2026-06-09*
