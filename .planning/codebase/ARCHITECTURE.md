<!-- refreshed: 2026-06-09 -->
# Architecture

**Analysis Date:** 2026-06-09

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                         React/Vite Frontend                              │
│  `frontend/src/App.jsx`  —  Single-page chat UI + evidence drawer        │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │  HTTP  POST /api/chat
                                 │  HTTP  GET  /api/index/status
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    FastAPI Application Layer                              │
│  `backend/app/main.py`                                                   │
│  Endpoints: /health  /api/index/status  /api/chat                        │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                 ┌───────────────┴────────────────┐
                 ▼                                ▼
┌────────────────────────┐        ┌──────────────────────────────────────┐
│   LLM Provider Layer   │        │          RAG Pipeline Layer           │
│  `backend/app/llm/`    │        │  `backend/app/rag/`                   │
│                        │        │                                        │
│  provider.py (Protocol)│◄───────│  chat_service.py  (orchestrator)      │
│  factory.py            │        │  query_transformer.py                 │
│  groq_provider.py      │        │  vector_store.py                      │
│  anthropic_provider.py │        │  reranker.py                          │
│  gemini_provider.py    │        │  pdf_loader.py                        │
│  prompts.py            │        │  text_chunker.py                      │
└────────────────────────┘        └──────────────────────────────────────┘
                                                 │
                                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Data / Index Layer                                │
│  `data/raw/student_manual_2019.pdf`  (source document)                   │
│  `data/indexes/faiss_student_manual/` (persisted FAISS index)            │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| FastAPI App | HTTP routing, CORS, lifespan index loading, request/response validation | `backend/app/main.py` |
| Settings | Pydantic env-based config with path resolution | `backend/app/core/config.py` |
| chat_service | RAG pipeline orchestrator: retrieval → rerank → context → answer | `backend/app/rag/chat_service.py` |
| query_transformer | Detects follow-up questions; rewrites them via LLM for better retrieval | `backend/app/rag/query_transformer.py` |
| vector_store | FAISS index creation, persistence, loading, and similarity search | `backend/app/rag/vector_store.py` |
| reranker | Cross-encoder re-scoring of candidate chunks; lazy singleton model | `backend/app/rag/reranker.py` |
| pdf_loader | PDF ingestion via PDFPlumber with normalized page metadata | `backend/app/rag/pdf_loader.py` |
| text_chunker | RecursiveCharacterTextSplitter with chunk_size=800, overlap=120 | `backend/app/rag/text_chunker.py` |
| LlmProvider Protocol | Structural subtyping interface: `generate_answer`, `rewrite_query` | `backend/app/llm/provider.py` |
| factory | Reads `settings.llm_provider`, lazy-imports and returns provider | `backend/app/llm/factory.py` |
| GroqLlmProvider | LangChain ChatGroq chain-based implementation | `backend/app/llm/groq_provider.py` |
| AnthropicLlmProvider | Direct Anthropic SDK implementation | `backend/app/llm/anthropic_provider.py` |
| GeminiLlmProvider | Google genai SDK implementation | `backend/app/llm/gemini_provider.py` |
| prompts | Shared system prompt strings for answer generation and query rewriting | `backend/app/llm/prompts.py` |
| ChatRequest/Response | Pydantic I/O schemas for the /api/chat endpoint | `backend/app/schemas/chat.py` |
| build_index script | Offline pipeline: load PDF → chunk → embed → save FAISS index | `backend/app/scripts/build_index.py` |
| React App | Stateful chat UI, evidence drawer, starter questions | `frontend/src/App.jsx` |

## Pattern Overview

**Overall:** Retrieval-Augmented Generation (RAG) with a layered FastAPI backend and a single-page React frontend.

**Key Characteristics:**
- Two-phase pipeline: offline index building (`build_index.py`) is completely separate from the online query-serving path (`main.py`)
- Provider abstraction via Python `Protocol` (structural duck typing) — providers are never imported at module level; `factory.py` lazy-imports them on every call
- Global mutable singleton for the FAISS index (`vector_store` in `main.py`) and a lazy singleton for the reranker model (`reranker_model` in `reranker.py`)
- All configuration centralised in a single Pydantic `Settings` object (`settings` singleton from `backend/app/core/config.py`)
- Frontend holds full chat history client-side; passes it with every request so the backend can resolve follow-up questions

## Layers

**HTTP/API Layer:**
- Purpose: Accept requests, validate I/O, return structured responses
- Location: `backend/app/main.py`
- Contains: FastAPI routes, lifespan handler, CORS middleware
- Depends on: `rag/chat_service.py`, `rag/vector_store.py`, `schemas/chat.py`, `core/config.py`
- Used by: Frontend

**RAG Pipeline Layer:**
- Purpose: Orchestrate retrieval, reranking, context assembly, and answer generation
- Location: `backend/app/rag/`
- Contains: `chat_service.py`, `query_transformer.py`, `vector_store.py`, `reranker.py`, `pdf_loader.py`, `text_chunker.py`
- Depends on: `llm/` (for query rewriting and answer generation), `core/config.py`
- Used by: `main.py` (online) and `scripts/build_index.py` (offline)

**LLM Provider Layer:**
- Purpose: Abstract LLM calls behind a `Protocol`; swap providers via config without changing RAG code
- Location: `backend/app/llm/`
- Contains: `provider.py` (Protocol), `factory.py`, `groq_provider.py`, `anthropic_provider.py`, `gemini_provider.py`, `prompts.py`
- Depends on: `core/config.py`, external SDKs (groq, anthropic, google-genai)
- Used by: `rag/chat_service.py`, `rag/query_transformer.py`

**Schema Layer:**
- Purpose: Typed request/response contracts validated by Pydantic
- Location: `backend/app/schemas/chat.py`
- Contains: `ChatMessage`, `ChatRequest`, `ChatResponse`, `ChatSource`
- Depends on: nothing internal
- Used by: `main.py`, `rag/chat_service.py`, `rag/query_transformer.py`

**Configuration Layer:**
- Purpose: Single source of truth for all runtime settings; reads `.env`
- Location: `backend/app/core/config.py`
- Contains: `Settings` (Pydantic BaseSettings), `settings` singleton
- Depends on: nothing internal
- Used by: every other backend layer

**Frontend Layer:**
- Purpose: Chat UI with message history, evidence drawer, and starter questions
- Location: `frontend/src/App.jsx`, `frontend/src/main.jsx`, `frontend/src/styles.css`
- Contains: Single `App` component with all UI state
- Depends on: Backend REST API
- Used by: End users via browser

## Data Flow

### Offline Index Building (run once before server start)

1. Run `backend/app/scripts/build_index.py` directly
2. `load_pdf_documents_with_page_metadata(pdf_path)` — PDFPlumber loads `data/raw/student_manual_2019.pdf` page-by-page (`backend/app/rag/pdf_loader.py`)
3. `split_documents_into_chunks(documents)` — splits into 800-char chunks with 120-char overlap (`backend/app/rag/text_chunker.py`)
4. `build_faiss_vector_store(chunks)` — embeds all chunks with HuggingFace `multi-qa-MiniLM-L6-cos-v1` and indexes them (`backend/app/rag/vector_store.py`)
5. `save_faiss_vector_store(vector_store, index_path)` — writes index to `data/indexes/faiss_student_manual/`

### Online Chat Request Path

1. Browser POSTs `{question, history}` to `POST /api/chat` (`backend/app/main.py:55`)
2. `answer_questions(vector_store, question, history)` called (`backend/app/rag/chat_service.py:101`)
3. `rewrite_query_for_retrieval(question, history)` — checks if question is a follow-up via regex patterns; if yes, calls `llm_provider.rewrite_query()` to produce a standalone query (`backend/app/rag/query_transformer.py:43`)
4. `retrieve_relevant_chunks(vector_store, retrieval_query, reranking_question)` — FAISS `similarity_search_with_score` fetches top-15 candidates (`backend/app/rag/chat_service.py:14`)
5. `rerank_documents(question, documents_with_scores, top_k=5)` — cross-encoder (lazy-loaded singleton) re-scores and returns top-5 (`backend/app/rag/reranker.py:17`)
6. `build_context(documents_with_scores)` — assembles numbered context string with page labels (`backend/app/rag/chat_service.py:36`)
7. `generate_answer(question, context)` — calls `create_llm_provider()` → provider's `generate_answer()` with system prompt (`backend/app/rag/chat_service.py:46`)
8. `build_sources(documents_with_scores)` — builds excerpt+score+page_number list (`backend/app/rag/chat_service.py:81`)
9. Returns `{answer, sources}` → serialised as `ChatResponse` → JSON to browser

**State Management:**
- Backend: FAISS index held as a module-level global in `main.py`; reranker model held as module-level global in `reranker.py`; `settings` singleton in `core/config.py`
- Frontend: All chat messages and UI state managed via React `useState` hooks in `App.jsx`; no external state library

## Key Abstractions

**LlmProvider Protocol:**
- Purpose: Structural interface enforcing `generate_answer(question, context) -> str` and `rewrite_query(question) -> str`
- Examples: `backend/app/llm/groq_provider.py`, `backend/app/llm/anthropic_provider.py`, `backend/app/llm/gemini_provider.py`
- Pattern: Python `typing.Protocol` — no base class inheritance required; providers are selected and instantiated via `backend/app/llm/factory.py`

**Document + Metadata Convention:**
- Purpose: LangChain `Document` objects carry normalized `page` (zero-based int) and `page_number` (one-based int) metadata throughout the pipeline
- Examples: `backend/app/rag/pdf_loader.py` (normalization), `backend/app/rag/chat_service.py` (display)
- Pattern: `_attach_page_metadata()` normalizes loader output; `get_display_page_number()` handles display safely

**Retrieve-then-Rerank Pattern:**
- Purpose: Broad FAISS ANN retrieval (k=15) followed by cross-encoder reranking (top_k=5) improves precision
- Examples: `backend/app/rag/chat_service.py:retrieve_relevant_chunks`, `backend/app/rag/reranker.py`
- Pattern: Two-stage — fast approximate search then slow but accurate cross-encoder scoring

## Entry Points

**HTTP Server:**
- Location: `backend/app/main.py`
- Triggers: `uvicorn app.main:app` (or equivalent)
- Responsibilities: Loads FAISS index on startup via `lifespan`, exposes `/health`, `/api/index/status`, `/api/chat`

**Index Builder:**
- Location: `backend/app/scripts/build_index.py`
- Triggers: `python backend/app/scripts/build_index.py` (run offline before server start)
- Responsibilities: Full pipeline from PDF to persisted FAISS index

**Frontend Dev Server:**
- Location: `frontend/src/main.jsx`
- Triggers: `npm run dev` (Vite on port 5173)
- Responsibilities: Mounts React app into `#root`

## Architectural Constraints

- **Threading:** FastAPI runs in a single async event loop; all route handlers are synchronous (`def`, not `async def`) — blocking LLM and embedding calls execute on the default thread pool
- **Global state:** `vector_store` global in `backend/app/main.py`; `reranker_model` global in `backend/app/rag/reranker.py`; `settings` singleton in `backend/app/core/config.py`
- **Circular imports:** None detected. LLM providers are lazy-imported inside `factory.py` conditionals, preventing circular dependency
- **Single document corpus:** The system is hardcoded to a single PDF source (`student_manual_2019.pdf`); multi-document support would require schema and pipeline changes
- **No async LLM calls:** All provider implementations are synchronous; adding streaming would require provider refactoring and `async def` route handlers

## Anti-Patterns

### Provider instantiated on every call

**What happens:** `create_llm_provider()` is called inside `generate_answer()` and `rewrite_query_for_retrieval()` on every request, constructing a new provider object each time
**Why it's wrong:** SDK clients (Anthropic, Gemini) are created fresh per request, wasting connection setup overhead and preventing connection reuse
**Do this instead:** Instantiate the provider once at startup (e.g., in `lifespan`) and inject it, or cache it as a module-level singleton similar to `reranker_model` in `backend/app/rag/reranker.py`

### Module-level settings consumption in vector_store.py

**What happens:** `EMBEDDING_MODEL_NAME = settings.embedding_model_name` is evaluated at import time (`backend/app/rag/vector_store.py:8`)
**Why it's wrong:** The binding is fixed at import, so runtime `.env` overrides after import have no effect on this variable
**Do this instead:** Read `settings.embedding_model_name` inside the function body of `create_embedding_model()` as all other modules do

## Error Handling

**Strategy:** Raise `ValueError` for invalid inputs within pipeline functions; catch at API layer and convert to appropriate HTTP exceptions.

**Patterns:**
- Input validation raises `ValueError` with descriptive messages (e.g., `"Question must not be empty"`)
- `main.py` catches `ValueError` → HTTP 400, generic `Exception` → HTTP 500
- Missing FAISS index → HTTP 503 with `"FAISS index is not loaded."`
- Empty context short-circuits LLM call with a canned response string (in both `chat_service.py` and each provider)

## Cross-Cutting Concerns

**Logging:** None — `print()` statements only in `build_index.py` for CLI feedback; no structured logging in the API path
**Validation:** Pydantic for HTTP I/O (`schemas/chat.py`, `core/config.py`); manual `if not x.strip()` guards in pipeline functions
**Authentication:** None — no auth on any endpoint; CORS is restricted to `localhost:5173`

---

*Architecture analysis: 2026-06-09*
