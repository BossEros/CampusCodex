<!-- GSD:project-start source:PROJECT.md -->
## Project

**RAG Knowledge Platform**

A production-grade Retrieval-Augmented Generation platform where administrators upload documents to a shared knowledge base and authenticated users get streaming, source-cited answers with persistent chat history. Built on a FastAPI backend and React frontend, it is the production evolution of an existing single-document student-manual RAG project — re-engineered to demonstrate professional backend + AI engineering for a portfolio and live recruiter-facing demo.

**Core Value:** Trustworthy, source-cited answers from a managed document knowledge base — answer quality that is *measurably* good (proven by an evaluation pipeline), served through a secure, deployable, real-world system.

### Constraints

- **Hosting/Budget**: Must run on free or low-cost tiers — drives API-based embeddings/reranking and the removal of heavy local models — Why: a clickable live demo is required, and self-hosted ML models are expensive/hard on free tiers.
- **Tech stack**: Keep FastAPI + React + Pydantic + the existing `LlmProvider` Protocol; extend rather than rewrite — Why: reuse working foundations (DRY) and present a clean, evolutionary design story.
- **Vector store**: Pinecone (managed) for vectors; Postgres for all relational/app data — Why: recruiter-recognizable vector DB + standard relational modeling.
- **Security**: Public demo must be protected against cost/abuse (rate limits, daily caps) and use proper password hashing + JWT — Why: it's internet-facing with real API keys behind it.
- **Evaluation integrity**: The `student_manual` corpus is the *fixed* benchmark for eval; user-uploaded docs do not affect eval scores — Why: RAGAS-style metrics need a stable golden set to be meaningful.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.12 - Backend API, RAG pipeline, LLM provider abstraction
- JavaScript (ES2022 modules) - Frontend React application (`frontend/src/`)
- JSX - React component templating (`frontend/src/App.jsx`, `frontend/src/main.jsx`)
## Runtime
- Python 3.12.x (CPython) — backend server and index build scripts
- Node.js (LTS) — frontend dev server and build toolchain
- pip — Python backend dependencies
- npm — Node frontend dependencies
## Frameworks
- FastAPI 0.136.0 — REST API server (`backend/app/main.py`)
- React 18.3.1 — UI component library (`frontend/src/App.jsx`)
- Vite 5.4.19 — dev server and production bundler (`frontend/vite.config.js`)
- langchain 1.2.15 — core orchestration primitives
- langchain-community 0.4.1 — FAISS vector store wrapper, PDFPlumberLoader (`backend/app/rag/vector_store.py`, `backend/app/rag/pdf_loader.py`)
- langchain-text-splitters 1.1.2 — `RecursiveCharacterTextSplitter` (`backend/app/rag/text_chunker.py`)
- langchain-groq 1.1.2 — `ChatGroq` client for Groq provider (`backend/app/llm/groq_provider.py`)
- langchain-huggingface 1.2.1 — `HuggingFaceEmbeddings` wrapper (`backend/app/rag/vector_store.py`)
- No test runner configuration file detected. Test files exist under `backend/tests/` but lack a `pytest.ini`, `pyproject.toml`, or `conftest.py`.
- Vite 5.4.19 (`frontend/vite.config.js`) — builds frontend to `frontend/dist/`
- Python script `backend/app/scripts/build_index.py` — offline FAISS index builder
## Key Dependencies
- `faiss-cpu 1.13.2` — local vector similarity index; loaded at startup by `load_faiss_vector_store()` in `backend/app/rag/vector_store.py`
- `sentence-transformers 5.4.1` — embedding model (`sentence-transformers/multi-qa-MiniLM-L6-cos-v1`) and cross-encoder reranker (`cross-encoder/ms-marco-MiniLM-L6-v2`); both downloaded from HuggingFace Hub at first use
- `anthropic 0.97.0` — Anthropic Messages API client (`backend/app/llm/anthropic_provider.py`)
- `google-genai 1.74.0` — Google Gemini API client via `google.genai` (`backend/app/llm/gemini_provider.py`)
- `langchain-groq 1.1.2` — Groq API client wrapped in LangChain (`backend/app/llm/groq_provider.py`)
- `pypdf 6.10.0` — PDF parsing fallback; imported by LangChain community
- `pdfplumber 0.11.8` — primary PDF parser via `PDFPlumberLoader` (`backend/app/rag/pdf_loader.py`)
- `python-dotenv 1.2.2` — `.env` file loader used by pydantic-settings (`backend/app/core/config.py`)
## Configuration
- All runtime settings are defined in `backend/app/core/config.py` as a `pydantic_settings.BaseSettings` subclass named `Settings`
- Settings are loaded from `backend/.env` (path resolved relative to `BACKEND_DIR`)
- Required env vars (no defaults): `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` — only the key matching the active `llm_provider` is required at runtime
- Key settings with defaults:
- API base URL: `VITE_API_BASE_URL` environment variable, defaults to `http://127.0.0.1:8000` (`frontend/src/App.jsx` line 3–4)
- Dev server port: `5173` (`frontend/vite.config.js`)
- Frontend build: `npm run build` → Vite bundles to `frontend/dist/`
- FAISS index build: `python backend/app/scripts/build_index.py` (one-time offline step; requires PDF at `data/raw/student_manual_2019.pdf`)
## Platform Requirements
- Python 3.12+
- Node.js LTS (tested with npm lockfile from Node 18+)
- HuggingFace model cache directory (models downloaded on first run)
- Pre-built FAISS index at `data/indexes/faiss_student_manual/` before starting the API
- No containerization config detected (no Dockerfile, docker-compose.yml, or cloud deployment manifests found in repo)
- API server: `uvicorn app.main:app` from the `backend/` directory
- Frontend: static file hosting of `frontend/dist/` or continued use of Vite dev server
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Python: `snake_case` for all module files (e.g., `chat_service.py`, `query_transformer.py`, `pdf_loader.py`)
- Python classes: `PascalCase` (e.g., `AnthropicLlmProvider`, `GeminiLlmProvider`, `ChatRequest`)
- Python test files: `test_<subject>.py` prefix (e.g., `test_anthropic_provider.py`, `test_query_rewrite.py`)
- React/JS: `PascalCase` for component files (`App.jsx`), `camelCase` for utility files
- Module-level singleton constants: `UPPER_SNAKE_CASE` (e.g., `EMBEDDING_MODEL_NAME`, `DEPENDENT_FOLLOW_UP_PATTERNS`, `ANSWER_SYSTEM_PROMPT`)
- Python: `snake_case` verbs describing what the function does (e.g., `load_pdf_documents_with_page_metadata`, `build_faiss_vector_store`, `rewrite_query_for_retrieval`)
- Private/internal helpers: single leading underscore prefix (e.g., `_attach_page_metadata`, `_extract_text`, `_generate_text`)
- React: `camelCase` with descriptive `handle*` prefix for event handlers (e.g., `handleSubmit`, `handleCloseEvidence`, `handleComposerKeyDown`)
- React async fetch utilities: bare `camelCase` nouns/verbs (e.g., `fetchJson`, `loadStatus`, `normalizeMessageContent`)
- Python: `snake_case` throughout (e.g., `resolved_index_path`, `context_parts`, `reranked_documents`)
- Python loop variables: descriptive nouns, never single letters (e.g., `document`, `ranked_result`, `content_block`)
- React state: `camelCase` noun/adjective pairs (e.g., `isEvidenceOpen`, `activeEvidenceMessageId`, `isSending`)
- React refs: `<target>Ref` suffix (e.g., `messageListRef`, `composerInputRef`)
- Python Protocol interfaces: `<Name>` (e.g., `LlmProvider` in `backend/app/llm/provider.py`)
- Provider implementations: `<Provider>LlmProvider` pattern (e.g., `AnthropicLlmProvider`, `GeminiLlmProvider`, `GroqLlmProvider`)
- Pydantic schemas: noun-only `PascalCase` (e.g., `ChatRequest`, `ChatResponse`, `ChatMessage`, `ChatSource`)
- Test classes: `<Subject>Tests` suffix (e.g., `AnthropicProviderTests`, `QueryRewriteTests`)
- Test fake objects: `Fake<Thing>` prefix (e.g., `FakeAnthropicClient`, `FakeMessagesClient`, `FakeModelsClient`)
## Code Style
- No formatter config file found (no `.prettierrc`, `pyproject.toml`, or `setup.cfg`)
- Python indentation: 4 spaces consistently
- JavaScript/JSX indentation: 2 spaces consistently
- Trailing commas used in multi-line Python data structures and function call arguments
- Multi-line function signatures: each parameter on its own line with closing paren on its own line
- No ESLint config detected in frontend
- No Flake8/Pylint/Ruff config detected in backend
- Code shows consistent adherence to PEP 8 style despite no enforced config
- All Python functions carry full return type annotations (e.g., `-> str`, `-> list[Document]`, `-> FAISS`, `-> None`)
- Union types use the modern `X | Y` syntax (`str | Path`, `int | None`, `list[ChatMessage] | None`)
- Local collection variables use explicit type hints where ambiguity exists (e.g., `text_parts: list[str] = []`)
- `TYPE_CHECKING` guard used in `backend/app/rag/chat_service.py` to avoid circular imports at runtime
## Import Organization
- Third-party SDK imports that require an API key are deferred inside `__init__` to avoid import errors when the dependency is not installed (e.g., `from anthropic import Anthropic` inside `AnthropicLlmProvider.__init__`, `from google import genai` inside `GeminiLlmProvider.__init__`)
- File: `backend/app/llm/anthropic_provider.py` lines 13-14, `backend/app/llm/gemini_provider.py` lines 11-12
- Named React hook imports first (e.g., `import { useEffect, useRef, useState } from "react"`)
- Default component export at the bottom of the file
## Error Handling
- `ValueError` → `400`
- `None` vector store → `503`
- All other exceptions → `500` (with a generic message, not the raw exception detail)
- Async functions use try/catch with a typed error handler `formatErrorMessage(error)` that normalizes `Error` instances and unknown throws
- `isMounted` flag in `useEffect` prevents state updates after unmount (see `loadStatus` in `App.jsx`)
- `void` keyword used explicitly when calling `async` functions from event handlers where the promise return value is intentionally ignored
## Logging
- No structured logging in production code paths (`backend/app/` outside scripts)
- Build script uses descriptive progress messages with counts (e.g., `f"Loaded documents: {len(documents)}"`)
## Comments
- Inline comments explain non-obvious intent, not mechanics (e.g., `# Keep a consistent zero-based page field for internal use` in `backend/app/rag/pdf_loader.py`)
- Docstrings used only on Protocol methods in `backend/app/llm/provider.py`; implementation classes do not repeat them
- No class-level docstrings on concrete implementations
- No function-level docstrings on non-Protocol functions; intent is conveyed through descriptive names and guard clauses
## Function Design
## Module Design
- No `__all__` declarations; modules export everything at module level
- `settings` singleton is created at module level in `backend/app/core/config.py` and imported directly wherever needed
- `backend/app/llm/__init__.py` is empty — no barrel aggregation used
- All imports are explicit from their source modules
- `backend/app/llm/factory.py` — `create_llm_provider()` selects and instantiates the correct provider based on `settings.llm_provider`. Provider classes are imported inside `if` branches to avoid loading unused SDK dependencies.
- `backend/app/rag/reranker.py` uses a module-level `reranker_model: CrossEncoder | None = None` and a `get_reranker_model()` getter that initializes on first call
- `backend/app/core/config.py` — `Settings(BaseSettings)` with `.env` file loading and a `@field_validator` for path resolution
- `backend/app/schemas/chat.py` — All API request/response shapes defined as `BaseModel` with `Field(...)` including descriptions
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## System Overview
```text
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
- Two-phase pipeline: offline index building (`build_index.py`) is completely separate from the online query-serving path (`main.py`)
- Provider abstraction via Python `Protocol` (structural duck typing) — providers are never imported at module level; `factory.py` lazy-imports them on every call
- Global mutable singleton for the FAISS index (`vector_store` in `main.py`) and a lazy singleton for the reranker model (`reranker_model` in `reranker.py`)
- All configuration centralised in a single Pydantic `Settings` object (`settings` singleton from `backend/app/core/config.py`)
- Frontend holds full chat history client-side; passes it with every request so the backend can resolve follow-up questions
## Layers
- Purpose: Accept requests, validate I/O, return structured responses
- Location: `backend/app/main.py`
- Contains: FastAPI routes, lifespan handler, CORS middleware
- Depends on: `rag/chat_service.py`, `rag/vector_store.py`, `schemas/chat.py`, `core/config.py`
- Used by: Frontend
- Purpose: Orchestrate retrieval, reranking, context assembly, and answer generation
- Location: `backend/app/rag/`
- Contains: `chat_service.py`, `query_transformer.py`, `vector_store.py`, `reranker.py`, `pdf_loader.py`, `text_chunker.py`
- Depends on: `llm/` (for query rewriting and answer generation), `core/config.py`
- Used by: `main.py` (online) and `scripts/build_index.py` (offline)
- Purpose: Abstract LLM calls behind a `Protocol`; swap providers via config without changing RAG code
- Location: `backend/app/llm/`
- Contains: `provider.py` (Protocol), `factory.py`, `groq_provider.py`, `anthropic_provider.py`, `gemini_provider.py`, `prompts.py`
- Depends on: `core/config.py`, external SDKs (groq, anthropic, google-genai)
- Used by: `rag/chat_service.py`, `rag/query_transformer.py`
- Purpose: Typed request/response contracts validated by Pydantic
- Location: `backend/app/schemas/chat.py`
- Contains: `ChatMessage`, `ChatRequest`, `ChatResponse`, `ChatSource`
- Depends on: nothing internal
- Used by: `main.py`, `rag/chat_service.py`, `rag/query_transformer.py`
- Purpose: Single source of truth for all runtime settings; reads `.env`
- Location: `backend/app/core/config.py`
- Contains: `Settings` (Pydantic BaseSettings), `settings` singleton
- Depends on: nothing internal
- Used by: every other backend layer
- Purpose: Chat UI with message history, evidence drawer, and starter questions
- Location: `frontend/src/App.jsx`, `frontend/src/main.jsx`, `frontend/src/styles.css`
- Contains: Single `App` component with all UI state
- Depends on: Backend REST API
- Used by: End users via browser
## Data Flow
### Offline Index Building (run once before server start)
### Online Chat Request Path
- Backend: FAISS index held as a module-level global in `main.py`; reranker model held as module-level global in `reranker.py`; `settings` singleton in `core/config.py`
- Frontend: All chat messages and UI state managed via React `useState` hooks in `App.jsx`; no external state library
## Key Abstractions
- Purpose: Structural interface enforcing `generate_answer(question, context) -> str` and `rewrite_query(question) -> str`
- Examples: `backend/app/llm/groq_provider.py`, `backend/app/llm/anthropic_provider.py`, `backend/app/llm/gemini_provider.py`
- Pattern: Python `typing.Protocol` — no base class inheritance required; providers are selected and instantiated via `backend/app/llm/factory.py`
- Purpose: LangChain `Document` objects carry normalized `page` (zero-based int) and `page_number` (one-based int) metadata throughout the pipeline
- Examples: `backend/app/rag/pdf_loader.py` (normalization), `backend/app/rag/chat_service.py` (display)
- Pattern: `_attach_page_metadata()` normalizes loader output; `get_display_page_number()` handles display safely
- Purpose: Broad FAISS ANN retrieval (k=15) followed by cross-encoder reranking (top_k=5) improves precision
- Examples: `backend/app/rag/chat_service.py:retrieve_relevant_chunks`, `backend/app/rag/reranker.py`
- Pattern: Two-stage — fast approximate search then slow but accurate cross-encoder scoring
## Entry Points
- Location: `backend/app/main.py`
- Triggers: `uvicorn app.main:app` (or equivalent)
- Responsibilities: Loads FAISS index on startup via `lifespan`, exposes `/health`, `/api/index/status`, `/api/chat`
- Location: `backend/app/scripts/build_index.py`
- Triggers: `python backend/app/scripts/build_index.py` (run offline before server start)
- Responsibilities: Full pipeline from PDF to persisted FAISS index
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
### Module-level settings consumption in vector_store.py
## Error Handling
- Input validation raises `ValueError` with descriptive messages (e.g., `"Question must not be empty"`)
- `main.py` catches `ValueError` → HTTP 400, generic `Exception` → HTTP 500
- Missing FAISS index → HTTP 503 with `"FAISS index is not loaded."`
- Empty context short-circuits LLM call with a canned response string (in both `chat_service.py` and each provider)
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



## Agent skills

### Issue tracker

Issues live in GitHub Issues (`github.com/BossEros/Rag-System`). See `docs/agents/issue-tracker.md`.

### Triage labels

Default canonical labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
