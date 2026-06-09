# Codebase Structure

**Analysis Date:** 2026-06-09

## Directory Layout

```
Rag-System/
├── backend/                         # Python FastAPI backend
│   ├── app/
│   │   ├── core/
│   │   │   └── config.py            # Pydantic settings singleton (reads .env)
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── provider.py          # LlmProvider Protocol (interface)
│   │   │   ├── factory.py           # Provider selector / factory function
│   │   │   ├── prompts.py           # Shared system prompt strings
│   │   │   ├── groq_provider.py     # Groq/LangChain implementation
│   │   │   ├── anthropic_provider.py# Anthropic SDK implementation
│   │   │   └── gemini_provider.py   # Google genai SDK implementation
│   │   ├── rag/
│   │   │   ├── chat_service.py      # RAG pipeline orchestrator
│   │   │   ├── query_transformer.py # Follow-up detection + LLM query rewrite
│   │   │   ├── vector_store.py      # FAISS build / save / load helpers
│   │   │   ├── reranker.py          # Cross-encoder reranker (lazy singleton)
│   │   │   ├── pdf_loader.py        # PDFPlumber loader + page metadata norm
│   │   │   └── text_chunker.py      # RecursiveCharacterTextSplitter wrapper
│   │   ├── schemas/
│   │   │   └── chat.py              # ChatMessage, ChatRequest, ChatResponse, ChatSource
│   │   ├── scripts/
│   │   │   └── build_index.py       # Offline: PDF → chunks → FAISS index
│   │   └── main.py                  # FastAPI app, routes, lifespan
│   ├── tests/
│   │   ├── test_anthropic_provider.py
│   │   ├── test_gemini_provider.py
│   │   └── test_query_rewrite.py
│   └── requirements.txt             # Python dependencies
├── frontend/                        # React/Vite single-page application
│   ├── src/
│   │   ├── App.jsx                  # Root component: all UI logic and state
│   │   ├── main.jsx                 # ReactDOM entry point
│   │   └── styles.css               # Global CSS
│   └── vite.config.js               # Vite config (port 5173, React plugin)
├── data/
│   ├── raw/
│   │   └── student_manual_2019.pdf  # Source document (read by build_index.py)
│   └── indexes/
│       └── faiss_student_manual/    # Generated FAISS index (created by build_index.py)
├── .planning/
│   └── codebase/                    # Codebase map documents
├── DEVELOPER_GUIDE.md
├── PLAN.md
└── README.md
```

## Directory Purposes

**`backend/app/core/`:**
- Purpose: Cross-cutting application configuration
- Contains: `config.py` — single `Settings` class (Pydantic BaseSettings) and `settings` singleton
- Key files: `backend/app/core/config.py`

**`backend/app/llm/`:**
- Purpose: Pluggable LLM provider abstraction
- Contains: Protocol interface, factory function, three concrete provider implementations, shared prompt strings
- Key files: `backend/app/llm/provider.py`, `backend/app/llm/factory.py`, `backend/app/llm/prompts.py`

**`backend/app/rag/`:**
- Purpose: All retrieval-augmented generation pipeline logic
- Contains: Orchestrator, query transformer, FAISS wrapper, cross-encoder reranker, PDF loader, text chunker
- Key files: `backend/app/rag/chat_service.py` (primary orchestrator), `backend/app/rag/vector_store.py`

**`backend/app/schemas/`:**
- Purpose: Pydantic models for API request/response contracts
- Contains: `chat.py` with `ChatMessage`, `ChatRequest`, `ChatResponse`, `ChatSource`
- Key files: `backend/app/schemas/chat.py`

**`backend/app/scripts/`:**
- Purpose: Offline utilities run outside the web server lifecycle
- Contains: `build_index.py` — one-shot script to build the FAISS vector index from the PDF
- Key files: `backend/app/scripts/build_index.py`

**`backend/tests/`:**
- Purpose: Unit and integration tests for backend components
- Contains: Provider-specific tests and query rewrite tests
- Key files: `backend/tests/test_query_rewrite.py`, `backend/tests/test_anthropic_provider.py`, `backend/tests/test_gemini_provider.py`

**`frontend/src/`:**
- Purpose: All React application source
- Contains: Single root component (`App.jsx`), entry point (`main.jsx`), global styles (`styles.css`)
- Key files: `frontend/src/App.jsx`

**`data/raw/`:**
- Purpose: Source documents for indexing
- Contains: `student_manual_2019.pdf`
- Generated: No — manually placed
- Committed: Yes (single PDF)

**`data/indexes/`:**
- Purpose: Persisted FAISS vector index (output of `build_index.py`)
- Contains: `faiss_student_manual/` directory (FAISS binary files)
- Generated: Yes — by `backend/app/scripts/build_index.py`
- Committed: Typically no (large binary)

## Key File Locations

**Entry Points:**
- `backend/app/main.py`: FastAPI application — start with `uvicorn app.main:app`
- `backend/app/scripts/build_index.py`: Offline index builder — run before server start
- `frontend/src/main.jsx`: Vite/React entry — start with `npm run dev`

**Configuration:**
- `backend/app/core/config.py`: All settings (LLM provider, model names, paths, API keys)
- `backend/.env`: Runtime secrets and env overrides (not committed)
- `frontend/vite.config.js`: Vite build/dev server config

**Core Logic:**
- `backend/app/rag/chat_service.py`: RAG pipeline orchestrator (primary logic entry)
- `backend/app/rag/query_transformer.py`: Follow-up question detection and rewriting
- `backend/app/llm/factory.py`: Provider selection logic

**Schemas:**
- `backend/app/schemas/chat.py`: All HTTP I/O types

**Prompts:**
- `backend/app/llm/prompts.py`: `ANSWER_SYSTEM_PROMPT`, `QUERY_REWRITE_SYSTEM_PROMPT`

**Testing:**
- `backend/tests/`: All Python tests

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `chat_service.py`, `query_transformer.py`)
- React files: `PascalCase.jsx` for components (`App.jsx`), `camelCase.jsx` for entry (`main.jsx`)
- Config: `snake_case.py` (`config.py`, `vite.config.js`)

**Directories:**
- Python packages: lowercase, no separators (`llm`, `rag`, `schemas`, `core`, `scripts`)
- Frontend: lowercase (`src`)
- Data: lowercase with underscores (`raw`, `indexes`)

**Python Classes:**
- Pydantic models: `PascalCase` (e.g., `ChatRequest`, `ChatResponse`, `ChatSource`)
- Provider classes: `PascalCase` + suffix (`GroqLlmProvider`, `AnthropicLlmProvider`, `GeminiLlmProvider`)

**Python Functions:**
- All `snake_case` with descriptive verb-noun names: `load_pdf_documents_with_page_metadata`, `split_documents_into_chunks`, `build_faiss_vector_store`, `rewrite_query_for_retrieval`
- Private helpers prefixed with `_`: `_attach_page_metadata`, `_extract_text`, `_generate_text`

**Python Variables/Settings:**
- Settings fields: `snake_case` (e.g., `llm_provider`, `faiss_index_path`, `reranked_top_k`)
- Module-level constants: `UPPER_SNAKE_CASE` (e.g., `ANSWER_SYSTEM_PROMPT`, `DEPENDENT_FOLLOW_UP_PATTERNS`, `EMBEDDING_MODEL_NAME`)

## Where to Add New Code

**New LLM Provider:**
- Implementation: `backend/app/llm/<name>_provider.py` — implement `LlmProvider` Protocol
- Register: Add `if provider_name == "<name>":` branch in `backend/app/llm/factory.py`
- Config: Add `<name>_api_key: str | None = None` to `Settings` in `backend/app/core/config.py`
- Tests: `backend/tests/test_<name>_provider.py`

**New RAG Pipeline Step:**
- Implementation: `backend/app/rag/<step_name>.py`
- Integrate: Add call in `backend/app/rag/chat_service.py` (the orchestrator)

**New API Endpoint:**
- Add route in `backend/app/main.py`
- Add request/response schemas to `backend/app/schemas/chat.py` (or new file in `backend/app/schemas/`)

**New Frontend Component:**
- Currently all UI lives in `frontend/src/App.jsx` as functions
- For reusable components: extract to `frontend/src/components/<ComponentName>.jsx`
- For utilities: extract to `frontend/src/utils/<name>.js`

**New Configuration Value:**
- Add field to `Settings` class in `backend/app/core/config.py`
- Access everywhere via `from app.core.config import settings`

**Shared Prompt Changes:**
- Edit `backend/app/llm/prompts.py` — `ANSWER_SYSTEM_PROMPT` or `QUERY_REWRITE_SYSTEM_PROMPT`

## Special Directories

**`.planning/codebase/`:**
- Purpose: Codebase map documents for planning and execution guidance
- Generated: Yes — by GSD map-codebase commands
- Committed: Yes

**`data/indexes/faiss_student_manual/`:**
- Purpose: Persisted FAISS vector index consumed by the FastAPI server at startup
- Generated: Yes — must be built before running the server using `build_index.py`
- Committed: No — binary/large; regenerated from the PDF

---

*Structure analysis: 2026-06-09*
