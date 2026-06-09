# Technology Stack

**Analysis Date:** 2026-06-09

## Languages

**Primary:**
- Python 3.12 - Backend API, RAG pipeline, LLM provider abstraction
- JavaScript (ES2022 modules) - Frontend React application (`frontend/src/`)

**Secondary:**
- JSX - React component templating (`frontend/src/App.jsx`, `frontend/src/main.jsx`)

## Runtime

**Environment:**
- Python 3.12.x (CPython) — backend server and index build scripts
- Node.js (LTS) — frontend dev server and build toolchain

**Package Manager:**
- pip — Python backend dependencies
  - Lockfile: Not present (requirements.txt only, no `pip freeze` lockfile)
- npm — Node frontend dependencies
  - Lockfile: `frontend/package-lock.json` (present)

## Frameworks

**Core Backend:**
- FastAPI 0.136.0 — REST API server (`backend/app/main.py`)
  - Uvicorn 0.43.0 (`standard` extras) — ASGI server for FastAPI
  - Pydantic 2.13.3 — request/response schema validation
  - pydantic-settings 2.11.0 — settings management from `.env`

**Core Frontend:**
- React 18.3.1 — UI component library (`frontend/src/App.jsx`)
- Vite 5.4.19 — dev server and production bundler (`frontend/vite.config.js`)
  - @vitejs/plugin-react 4.4.1 — JSX transform + HMR

**LangChain Ecosystem:**
- langchain 1.2.15 — core orchestration primitives
- langchain-community 0.4.1 — FAISS vector store wrapper, PDFPlumberLoader (`backend/app/rag/vector_store.py`, `backend/app/rag/pdf_loader.py`)
- langchain-text-splitters 1.1.2 — `RecursiveCharacterTextSplitter` (`backend/app/rag/text_chunker.py`)
- langchain-groq 1.1.2 — `ChatGroq` client for Groq provider (`backend/app/llm/groq_provider.py`)
- langchain-huggingface 1.2.1 — `HuggingFaceEmbeddings` wrapper (`backend/app/rag/vector_store.py`)

**Testing:**
- No test runner configuration file detected. Test files exist under `backend/tests/` but lack a `pytest.ini`, `pyproject.toml`, or `conftest.py`.

**Build/Dev:**
- Vite 5.4.19 (`frontend/vite.config.js`) — builds frontend to `frontend/dist/`
- Python script `backend/app/scripts/build_index.py` — offline FAISS index builder

## Key Dependencies

**Critical:**
- `faiss-cpu 1.13.2` — local vector similarity index; loaded at startup by `load_faiss_vector_store()` in `backend/app/rag/vector_store.py`
- `sentence-transformers 5.4.1` — embedding model (`sentence-transformers/multi-qa-MiniLM-L6-cos-v1`) and cross-encoder reranker (`cross-encoder/ms-marco-MiniLM-L6-v2`); both downloaded from HuggingFace Hub at first use
- `anthropic 0.97.0` — Anthropic Messages API client (`backend/app/llm/anthropic_provider.py`)
- `google-genai 1.74.0` — Google Gemini API client via `google.genai` (`backend/app/llm/gemini_provider.py`)
- `langchain-groq 1.1.2` — Groq API client wrapped in LangChain (`backend/app/llm/groq_provider.py`)

**Infrastructure:**
- `pypdf 6.10.0` — PDF parsing fallback; imported by LangChain community
- `pdfplumber 0.11.8` — primary PDF parser via `PDFPlumberLoader` (`backend/app/rag/pdf_loader.py`)
- `python-dotenv 1.2.2` — `.env` file loader used by pydantic-settings (`backend/app/core/config.py`)

## Configuration

**Environment:**
- All runtime settings are defined in `backend/app/core/config.py` as a `pydantic_settings.BaseSettings` subclass named `Settings`
- Settings are loaded from `backend/.env` (path resolved relative to `BACKEND_DIR`)
- Required env vars (no defaults): `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` — only the key matching the active `llm_provider` is required at runtime
- Key settings with defaults:
  - `llm_provider`: `"groq"` — selects active LLM (groq | anthropic | gemini)
  - `llm_model_name`: `"llama-3.1-8b-instant"`
  - `embedding_model_name`: `"sentence-transformers/multi-qa-MiniLM-L6-cos-v1"`
  - `faiss_index_path`: `data/indexes/faiss_student_manual` (relative to project root)
  - `pdf_path`: `data/raw/student_manual_2019.pdf`
  - `retrieval_candidate_k`: `15`
  - `reranked_top_k`: `5`
  - `reranker_model_name`: `"cross-encoder/ms-marco-MiniLM-L6-v2"`
  - `enable_query_rewrite`: `True`

**Frontend:**
- API base URL: `VITE_API_BASE_URL` environment variable, defaults to `http://127.0.0.1:8000` (`frontend/src/App.jsx` line 3–4)
- Dev server port: `5173` (`frontend/vite.config.js`)

**Build:**
- Frontend build: `npm run build` → Vite bundles to `frontend/dist/`
- FAISS index build: `python backend/app/scripts/build_index.py` (one-time offline step; requires PDF at `data/raw/student_manual_2019.pdf`)

## Platform Requirements

**Development:**
- Python 3.12+
- Node.js LTS (tested with npm lockfile from Node 18+)
- HuggingFace model cache directory (models downloaded on first run)
- Pre-built FAISS index at `data/indexes/faiss_student_manual/` before starting the API

**Production:**
- No containerization config detected (no Dockerfile, docker-compose.yml, or cloud deployment manifests found in repo)
- API server: `uvicorn app.main:app` from the `backend/` directory
- Frontend: static file hosting of `frontend/dist/` or continued use of Vite dev server

---

*Stack analysis: 2026-06-09*
