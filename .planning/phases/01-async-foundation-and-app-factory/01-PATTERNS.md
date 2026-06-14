# Phase 1: Async Foundation & App Factory - Pattern Map

**Mapped:** 2026-06-14
**Files analyzed:** 10 (7 modified, 3 new)
**Analogs found:** 8 / 10

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/main.py` | app-entry / route | request-response | `backend/app/main.py` (self — current state) | self-delta |
| `backend/app/core/config.py` | config | — | `backend/app/core/config.py` (self — additive field only) | self-delta |
| `backend/app/llm/factory.py` | factory / service | request-response | `backend/app/llm/factory.py` (self — NO CHANGE) | unchanged |
| `backend/app/rag/vector_store.py` | service / utility | file-I/O | `backend/app/rag/vector_store.py` (self — single-line fix) | self-delta |
| `backend/app/rag/chat_service.py` | service | request-response | `backend/app/rag/chat_service.py` (self — signature change) | self-delta |
| `backend/app/rag/query_transformer.py` | service / utility | request-response | `backend/app/rag/query_transformer.py` (self — signature change) | self-delta |
| `backend/app/rag/reranker.py` | service / utility | request-response | `backend/app/rag/reranker.py` (self — NO CHANGE) | unchanged |
| `backend/.env.example` | config | — | `backend/.env.example` (self — additive keys) | self-delta |
| `backend/pytest.ini` | config | — | none | no analog |
| `backend/tests/test_app_factory.py` | test | request-response | `backend/tests/test_query_rewrite.py` | role-match |
| `backend/tests/test_query_rewrite.py` | test | request-response | `backend/tests/test_query_rewrite.py` (self — call site updates) | self-delta |

---

## Pattern Assignments

### `backend/app/main.py` (app-entry, request-response)

**Nature of change:** Full rewrite. Convert from module-level `app = FastAPI(...)` with a
`global vector_store` to an `create_app()` factory that owns a scoped `lifespan`, registers
routes via `APIRouter`, and attaches singletons to `app.state`.

**Current state — what is being replaced** (`main.py` lines 1-70, read in full):

```python
# BEFORE — lines 1-9: imports + module-level global
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.rag.chat_service import answer_questions
from app.rag.vector_store import load_faiss_vector_store
from app.schemas.chat import ChatRequest, ChatResponse

vector_store = None          # ← anti-pattern: module-level mutable global

# BEFORE — lines 11-15: lifespan writes to global
@asynccontextmanager
async def lifespan(app: FastAPI):
    global vector_store                                       # ← anti-pattern
    vector_store = load_faiss_vector_store(settings.faiss_index_path)
    yield

# BEFORE — lines 17-31: top-level app construction (no factory)
app = FastAPI(
    title="Student Manual RAG Chatbot",
    lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # ← hardcoded
    allow_credentials=False,
    allow_methods=["*"],     # ← too permissive
    allow_headers=["*"],     # ← too permissive
)

# BEFORE — lines 33-35: sync def route decorated on module-level @app
@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}

# BEFORE — lines 38-51: sync def route; reads module-level vector_store
@app.get("/api/index/status")
def get_index_status() -> dict:
    return {
        "index_loaded": vector_store is not None,
        ...
    }

# BEFORE — lines 54-69: sync def chat route
@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    if vector_store is None:
        raise HTTPException(status_code=503, detail="FAISS index is not loaded.")
    try:
        result = answer_questions(
            vector_store=vector_store,
            question=request.question,
            history=request.history,
        )
        return ChatResponse(**result)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail="Failed to process chat request.") from error
```

**Target pattern — app factory + lifespan + APIRouter + async routes** (from RESEARCH.md lines 456-535):

```python
# AFTER — imports block
import asyncio
from contextlib import asynccontextmanager
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.llm.factory import create_llm_provider
from app.llm.provider import LlmProvider
from app.rag.chat_service import answer_questions
from app.rag.reranker import get_reranker_model
from app.rag.vector_store import load_faiss_vector_store
from app.schemas.chat import ChatRequest, ChatResponse

# AFTER — shared router (routes must NOT be @app.post — that breaks TestClient(create_app()))
router = APIRouter()

# AFTER — lifespan: singletons on app.state, NO globals
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.llm_provider = create_llm_provider()          # CORE-02
    app.state.vector_store = load_faiss_vector_store(        # CORE-01
        settings.faiss_index_path
    )
    get_reranker_model()                                     # pre-warm; getter stays in reranker.py
    yield

# AFTER — factory function
def create_app() -> FastAPI:
    application = FastAPI(
        title="RAG Knowledge Platform",
        lifespan=lifespan,
    )
    application.include_router(router)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,              # from Settings, not hardcoded
        allow_credentials=False,
        allow_methods=["GET", "POST"],                       # narrowed
        allow_headers=["Content-Type"],                      # narrowed
    )
    return application

app = create_app()
```

**Async route pattern with `asyncio.to_thread()` — chat handler** (from RESEARCH.md lines 510-535):

```python
# AFTER — @router.post, NOT @app.post
@router.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request) -> ChatResponse:
    vector_store = req.app.state.vector_store
    llm_provider: LlmProvider = req.app.state.llm_provider

    if vector_store is None:
        raise HTTPException(status_code=503, detail="FAISS index is not loaded.")

    try:
        result = await asyncio.to_thread(         # ← wraps blocking pipeline; CRITICAL
            answer_questions,
            vector_store=vector_store,
            llm_provider=llm_provider,            # injected — not created inside pipeline
            question=request.question,
            history=request.history,
        )
        return ChatResponse(**result)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail="Failed to process chat request.") from error
```

**Async status route — reads `req.app.state`** (mirrors current `get_index_status` with Request param added):

```python
# AFTER — async def; reads app.state, not module global
@router.get("/api/index/status")
async def get_index_status(req: Request) -> dict:
    return {
        "index_loaded": req.app.state.vector_store is not None,
        "pdf_path": settings.pdf_path,
        "index_path": settings.faiss_index_path,
        "embedding_model": settings.embedding_model_name,
        "retrieval_candidate_k": settings.retrieval_candidate_k,
        "reranked_top_k": settings.reranked_top_k,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model_name,
        "reranker_model": settings.reranker_model_name,
        "enable_query_rewrite": settings.enable_query_rewrite,
    }

@router.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}
```

**Anti-patterns that must NOT appear in the rewrite:**
- `global vector_store` anywhere in main.py
- `@app.post(...)` or `@app.get(...)` — all routes must use `@router.post(...)` / `@router.get(...)`
- `async def chat(...)` calling `answer_questions(...)` directly without `asyncio.to_thread()` — this blocks the event loop
- `allow_methods=["*"]` or `allow_headers=["*"]` — narrow to explicit values

---

### `backend/app/core/config.py` (config)

**Nature of change:** Additive only. One new field `allowed_origins` so CORS origins move out
of `main.py` hardcode into `Settings`. The `settings = Settings()` singleton at module level is
correct per RESEARCH.md line 302 — do NOT move it.

**Current state** (`config.py` lines 1-36, read in full):

```python
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent

class Settings(BaseSettings):
    groq_api_key: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    llm_provider: str = "groq"
    llm_model_name: str = "llama-3.1-8b-instant"
    embedding_model_name: str = "sentence-transformers/multi-qa-MiniLM-L6-cos-v1"
    faiss_index_path: str = str(PROJECT_ROOT / "data" / "indexes" / "faiss_student_manual")
    pdf_path: str = str(PROJECT_ROOT / "data" / "raw" / "student_manual_2019.pdf")
    retrieval_candidate_k: int = 15
    reranked_top_k: int = 5
    reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    enable_query_rewrite: bool = True

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
    )

    @field_validator("faiss_index_path", "pdf_path", mode="before")
    @classmethod
    def resolve_project_relative_paths(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute():
            return str(path)
        return str((BACKEND_DIR / path).resolve())


settings = Settings()       # ← correct: Settings() singleton is fine at module level
```

**Target delta — add `allowed_origins` field after `enable_query_rewrite`:**

```python
# Add this single field to the Settings class, after enable_query_rewrite:
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
```

**Pattern to follow:** Match the existing `BaseSettings` field declaration style — `snake_case`
field name, type annotation, `list[str]` with default factory-style inline list. No
`Field(...)` needed unless description is required.

---

### `backend/app/llm/factory.py` (factory — NO CHANGE)

**Nature of change:** None. `create_llm_provider()` is called **once** from the lifespan in
`main.py`. The CORE-02 fix lives in the **call sites** inside `chat_service.py` and
`query_transformer.py`, not here.

**Current state** (unchanged, shown for reference, `factory.py` lines 1-23):

```python
from app.core.config import settings
from app.llm.provider import LlmProvider


def create_llm_provider() -> LlmProvider:
    provider_name = settings.llm_provider.lower().strip()

    if provider_name == "groq":
        from app.llm.groq_provider import GroqLlmProvider
        return GroqLlmProvider()

    if provider_name == "anthropic":
        from app.llm.anthropic_provider import AnthropicLlmProvider
        return AnthropicLlmProvider()

    if provider_name == "gemini":
        from app.llm.gemini_provider import GeminiLlmProvider
        return GeminiLlmProvider()

    raise ValueError(f"Unsupported LLM Provider: {settings.llm_provider}")
```

---

### `backend/app/rag/vector_store.py` (service, file-I/O)

**Nature of change:** Single-line fix (CORE-03). Remove `EMBEDDING_MODEL_NAME` module-level
constant; read `settings.embedding_model_name` inside `create_embedding_model()` body instead.

**Current state — the offending pattern** (`vector_store.py` lines 1-11):

```python
from pathlib import Path
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from app.core.config import settings


EMBEDDING_MODEL_NAME = settings.embedding_model_name   # ← CORE-03 violation: value bound at import

def create_embedding_model() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
```

**Target delta — before and after:**

```python
# BEFORE (lines 8-11):
EMBEDDING_MODEL_NAME = settings.embedding_model_name

def create_embedding_model() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)

# AFTER (delete constant; read at call time):
def create_embedding_model() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=settings.embedding_model_name)
```

**Verify before deleting:** Grep `from app.rag.vector_store import EMBEDDING_MODEL_NAME` across
the codebase — if any external importer uses it, provide a compatibility shim. Per RESEARCH.md
line 427, no such importer was found, but confirm before removing.

**All other functions** (`build_faiss_vector_store`, `save_faiss_vector_store`,
`load_faiss_vector_store`) are unchanged in signature and behavior.

---

### `backend/app/rag/chat_service.py` (service, request-response)

**Nature of change:** CORE-02 — inject `llm_provider: LlmProvider` into `answer_questions()`
and `generate_answer()`, removing the internal `create_llm_provider()` call at lines 56.

**Current offending pattern** (`chat_service.py` lines 46-61):

```python
# BEFORE — generate_answer creates provider per-call
def generate_answer(
    question: str,
    context: str,
) -> str:
    if not question.strip():
        raise ValueError("Question must not be empty")

    if not context.strip():
        return "The student manual does not provide enough information to answer that."

    llm_provider = create_llm_provider()         # ← CORE-02 violation: per-call instantiation

    return llm_provider.generate_answer(
        question=question,
        context=context,
    )
```

**Current `answer_questions` signature** (`chat_service.py` lines 101-106):

```python
# BEFORE
def answer_questions(
    vector_store: "FAISS",
    question: str,
    history: list[ChatMessage] | None = None,
) -> dict:
    resolved_question = rewrite_query_for_retrieval(question, history=history)
    ...
    answer = generate_answer(resolved_question, context)
    ...
```

**Target pattern — inject provider through the call chain:**

```python
# AFTER — generate_answer receives provider as param
def generate_answer(
    question: str,
    context: str,
    llm_provider: LlmProvider,               # NEW — injected from app.state via answer_questions
) -> str:
    if not question.strip():
        raise ValueError("Question must not be empty")

    if not context.strip():
        return "The student manual does not provide enough information to answer that."

    return llm_provider.generate_answer(     # use injected provider; no create_llm_provider()
        question=question,
        context=context,
    )

# AFTER — answer_questions receives and threads provider down
def answer_questions(
    vector_store: "FAISS",
    question: str,
    llm_provider: LlmProvider,               # NEW — injected from app.state in route handler
    history: list[ChatMessage] | None = None,
) -> dict:
    resolved_question = rewrite_query_for_retrieval(
        question,
        llm_provider=llm_provider,           # thread down to query_transformer
        history=history,
    )
    ...
    answer = generate_answer(
        resolved_question,
        context,
        llm_provider=llm_provider,           # thread down to generate_answer
    )
    ...
```

**Import change:** Remove `from app.llm.factory import create_llm_provider` from imports once
the internal call is eliminated. Add `from app.llm.provider import LlmProvider` for the type
annotation. The `TYPE_CHECKING` guard pattern already present in this file should be preserved.

**Import block after change** (current lines 1-12 as reference, with delta applied):

```python
from typing import TYPE_CHECKING

from langchain_core.documents import Document
from app.core.config import settings
from app.rag.reranker import rerank_documents
# REMOVE: from app.llm.factory import create_llm_provider
from app.llm.provider import LlmProvider          # ADD: type annotation for injected provider
from app.rag.query_transformer import rewrite_query_for_retrieval
from app.schemas.chat import ChatMessage

if TYPE_CHECKING:
    from langchain_community.vectorstores import FAISS
```

---

### `backend/app/rag/query_transformer.py` (service/utility, request-response)

**Nature of change:** CORE-02 — inject `llm_provider: LlmProvider` param, removing the
internal `create_llm_provider()` call at line 58.

**Current offending pattern** (`query_transformer.py` lines 43-71):

```python
# BEFORE
def rewrite_query_for_retrieval(
    question: str,
    history: list[ChatMessage] | None = None,
) -> str:
    if not question.strip():
        raise ValueError("Question must not be empty")

    previous_user_question = get_last_user_question(history or [])

    if not settings.enable_query_rewrite:
        return question

    if not should_use_previous_question(question, previous_user_question):
        return question

    llm_provider = create_llm_provider()     # ← CORE-02 violation: per-call instantiation
    ...
    rewritten_query = llm_provider.rewrite_query(rewrite_input)
    return rewritten_query.strip() or question
```

**Target pattern** (from RESEARCH.md lines 540-549):

```python
# AFTER — llm_provider injected; create_llm_provider() removed
def rewrite_query_for_retrieval(
    question: str,
    llm_provider: LlmProvider,               # NEW — required param, injected from call chain
    history: list[ChatMessage] | None = None,
) -> str:
    if not question.strip():
        raise ValueError("Question must not be empty")

    previous_user_question = get_last_user_question(history or [])

    if not settings.enable_query_rewrite:
        return question

    if not should_use_previous_question(question, previous_user_question):
        return question

    # No create_llm_provider() call — use injected provider
    if previous_user_question:
        rewrite_input = (
            "Previous student question:\n"
            f"{previous_user_question}\n\n"
            "Latest student message:\n"
            f"{question}"
        )
    else:
        rewrite_input = question

    rewritten_query = llm_provider.rewrite_query(rewrite_input)
    return rewritten_query.strip() or question
```

**Import change:** Remove `from app.llm.factory import create_llm_provider`; add
`from app.llm.provider import LlmProvider`.

---

### `backend/app/rag/reranker.py` (service/utility — NO CHANGE)

**Nature of change:** None in this file. The lazy singleton `get_reranker_model()` getter stays
exactly as-is. The only Phase 1 touch is the lifespan in `main.py` calling `get_reranker_model()`
to pre-warm the model at startup.

**Current state** (unchanged, shown for reference, `reranker.py` lines 1-14):

```python
from langchain_core.documents import Document
from sentence_transformers import CrossEncoder
from app.core.config import settings

reranker_model: CrossEncoder | None = None


def get_reranker_model() -> CrossEncoder:
    global reranker_model

    if reranker_model is None:
        reranker_model = CrossEncoder(settings.reranker_model_name)

    return reranker_model
```

---

### `backend/.env.example` (config)

**Nature of change:** Additive — add missing settings keys that exist in `config.py` but are
absent from the current `.env.example`.

**Current state** (`.env.example` lines 1-6):

```
GROQ_API_KEY=your_groq_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
LLM_PROVIDER=anthropic
LLM_MODEL_NAME=claude-haiku-4-5
ENABLE_QUERY_REWRITE=true
```

**Missing keys to add** (one per remaining `Settings` field + the new `allowed_origins`):

```
# Embeddings / retrieval
EMBEDDING_MODEL_NAME=sentence-transformers/multi-qa-MiniLM-L6-cos-v1
RERANKER_MODEL_NAME=cross-encoder/ms-marco-MiniLM-L6-v2
RETRIEVAL_CANDIDATE_K=15
RERANKED_TOP_K=5

# Paths (relative to backend dir, or absolute)
FAISS_INDEX_PATH=../data/indexes/faiss_student_manual
PDF_PATH=../data/raw/student_manual_2019.pdf

# CORS (comma-separated list or JSON array depending on pydantic-settings parsing)
ALLOWED_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
```

**Convention:** Follow the existing `UPPER_SNAKE_CASE=value` format; add an inline comment
section header for each logical group, matching `Settings` field order.

---

### `backend/pytest.ini` (config — NEW FILE)

**Nature of change:** New file. No in-repo analog exists. Test discovery and `PYTHONPATH` must
be configured so `pytest tests/` resolves `app.*` imports from the `backend/` directory.

**No analog found.** Use the standard pytest.ini pattern:

```ini
[pytest]
testpaths = tests
pythonpath = .
```

`pythonpath = .` (sets `sys.path` to `backend/`) is required because all tests import `from
app.*` — which assumes `backend/` is on the path. This is the `pytest ≥ 7` way to set pythonpath
without a conftest.

---

### `backend/tests/test_app_factory.py` (test — NEW FILE)

**Closest analog:** `backend/tests/test_query_rewrite.py` — same test class style
(`unittest.TestCase`), same mock tools (`Mock`, `patch`), same project.

**Analog: test class structure** (`test_query_rewrite.py` lines 1-16):

```python
import unittest
from unittest.mock import Mock, patch


class QueryRewriteTests(unittest.TestCase):
    def test_rewrite_query_for_retrieval_returns_original_question_when_disabled(self):
        from app.rag.query_transformer import rewrite_query_for_retrieval

        question = "What about shifting?"

        with patch("app.rag.query_transformer.settings") as settings:
            settings.enable_query_rewrite = False

            retrieval_query = rewrite_query_for_retrieval(question)

        self.assertEqual(question, retrieval_query)
```

**Analog: `patch.object` style** (`test_query_rewrite.py` lines 80-101):

```python
def test_answer_questions_retrieves_with_rewritten_query_and_answers_original_question(self):
    from app.rag import chat_service

    vector_store = Mock()
    retrieved_documents = [("document", 1.0)]

    with patch.object(chat_service, "rewrite_query_for_retrieval", return_value="rewritten query"):
        with patch.object(chat_service, "retrieve_relevant_chunks", return_value=retrieved_documents) as retrieve:
            with patch.object(chat_service, "build_context", return_value="context") as build_context:
                with patch.object(chat_service, "generate_answer", return_value="answer") as generate_answer:
                    with patch.object(chat_service, "build_sources", return_value=[]) as build_sources:
                        result = chat_service.answer_questions(vector_store, "original question")
```

**Target pattern for `test_app_factory.py`** — use `TestClient` as context manager to trigger
lifespan (from RESEARCH.md lines 553-563):

```python
import unittest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient


class AppFactoryTests(unittest.TestCase):

    def test_create_app_returns_fastapi_instance_with_lifespan(self):
        # Import inside test to avoid module-level side effects
        from app.main import create_app
        from fastapi import FastAPI

        application = create_app()
        self.assertIsInstance(application, FastAPI)

    def test_chat_endpoint_returns_503_when_vector_store_not_loaded(self):
        from app.main import create_app

        # Patch lifespan dependencies so the test does not need real FAISS/models
        with patch("app.main.load_faiss_vector_store", return_value=None):
            with patch("app.main.create_llm_provider", return_value=Mock()):
                with patch("app.main.get_reranker_model"):
                    with TestClient(create_app()) as client:   # ← context-manager triggers lifespan
                        response = client.post(
                            "/api/chat",
                            json={"question": "What is the enrollment deadline?", "history": []},
                        )

        self.assertEqual(503, response.status_code)

    def test_provider_constructed_once_not_per_request(self):
        from app.main import create_app

        mock_provider = Mock()
        mock_vector_store = Mock()

        with patch("app.main.create_llm_provider", return_value=mock_provider) as mock_factory:
            with patch("app.main.load_faiss_vector_store", return_value=mock_vector_store):
                with patch("app.main.get_reranker_model"):
                    with patch("app.main.answer_questions", return_value={"answer": "ok", "sources": []}):
                        with TestClient(create_app()) as client:
                            client.post("/api/chat", json={"question": "test", "history": []})
                            client.post("/api/chat", json={"question": "test2", "history": []})

        # Provider factory called exactly once (at lifespan), not per request
        mock_factory.assert_called_once()
```

---

### `backend/tests/test_query_rewrite.py` (test — MODIFIED)

**Nature of change:** Update 5 call sites broken by CORE-02 signature changes. No structural
changes to the test class or mock patterns.

**Impacted call sites** (from RESEARCH.md lines 631-637):

| Line | Current (broken after refactor) | Target (fixed) |
|------|---|---|
| 14 | `rewrite_query_for_retrieval(question)` | `rewrite_query_for_retrieval(question, llm_provider=Mock())` |
| 27-28 | `patch("...create_llm_provider", ...)` + bare call | Remove patch block; pass `llm_provider=Mock()` direct arg |
| 47-48 | Same patch pattern with history | Remove patch block; pass `llm_provider=Mock()` direct arg |
| 71-75 | Same patch pattern | Remove patch block; pass `llm_provider=Mock()` direct arg |
| 91 | `answer_questions(vector_store, "original question")` | `answer_questions(vector_store, "original question", llm_provider=Mock())` |

**Analog for how to pass Mock directly** (pattern from same file, line 21-22):

```python
# Existing test already uses this pattern — reuse it:
llm_provider = Mock()
llm_provider.rewrite_query.return_value = "What are the requirements for shifting courses?"
```

**After fix, tests that used `patch("...create_llm_provider", ...)` change to:**

```python
# BEFORE (lines 27-28):
with patch("app.rag.query_transformer.create_llm_provider", return_value=llm_provider):
    retrieval_query = rewrite_query_for_retrieval("What about shifting?")

# AFTER (remove patch; pass provider as arg):
retrieval_query = rewrite_query_for_retrieval("What about shifting?", llm_provider=llm_provider)
```

---

## Shared Patterns

### LlmProvider Protocol Type Annotation
**Source:** `backend/app/llm/provider.py` lines 1-11
**Apply to:** `chat_service.py`, `query_transformer.py`, `main.py`, `test_app_factory.py`

```python
from typing import Protocol


class LlmProvider(Protocol):
    def generate_answer(self, question: str, context: str) -> str:
        """Generate an answer using the provided question and retrieved context."""
        ...

    def rewrite_query(self, question: str) -> str:
        """Rewrite a vague student question into a clearer retrieval query."""
        ...
```

Import pattern to use in modified files:
```python
from app.llm.provider import LlmProvider
```

### Error Handling at Route Boundary
**Source:** `backend/app/main.py` lines 59-69 (current — preserve this pattern)
**Apply to:** All async route handlers in `main.py` after refactor

```python
try:
    result = await asyncio.to_thread(
        answer_questions,
        ...
    )
    return ChatResponse(**result)
except ValueError as error:
    raise HTTPException(status_code=400, detail=str(error)) from error
except Exception as error:
    raise HTTPException(status_code=500, detail="Failed to process chat request.") from error
```

Error mapping:
- `ValueError` → HTTP 400
- Any other `Exception` → HTTP 500 with generic message (not raw exception detail)
- `vector_store is None` → HTTP 503 (checked before try/except)

### Function Signature Convention
**Source:** All existing backend modules
**Apply to:** All modified function signatures

```python
# Multi-param functions: each parameter on its own line, closing paren on its own line
def answer_questions(
    vector_store: "FAISS",
    question: str,
    llm_provider: LlmProvider,
    history: list[ChatMessage] | None = None,
) -> dict:
```

### Module Import Order Convention
**Source:** `backend/app/rag/chat_service.py` lines 1-12 (TYPE_CHECKING pattern)
**Apply to:** Any file that would create circular imports

```python
from typing import TYPE_CHECKING
# ... regular imports ...

if TYPE_CHECKING:
    from langchain_community.vectorstores import FAISS
```

### Test Class and Import Convention
**Source:** `backend/tests/test_query_rewrite.py` lines 1-16
**Apply to:** `backend/tests/test_app_factory.py`

```python
import unittest
from unittest.mock import Mock, patch


class <Subject>Tests(unittest.TestCase):
    def test_<descriptive_name>(self):
        from app.<module> import <symbol>   # import inside test, not at module level
        ...
        self.assertEqual(expected, actual)
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/pytest.ini` | config | — | No test configuration file exists in the repo; use standard pytest.ini pattern from RESEARCH.md lines 647-649 |
| `backend/tests/test_app_factory.py` (structure for `asyncio.to_thread` + `TestClient` lifespan tests) | test | request-response | No in-repo precedent for lifespan-triggered integration tests; use RESEARCH.md lines 553-563 and code examples above |

---

## Metadata

**Analog search scope:** `backend/app/`, `backend/tests/`
**Files scanned:** 11 source files read in full
**Pattern extraction date:** 2026-06-14
**RESEARCH.md confidence:** HIGH (FastAPI 0.136.0 verified installed; asyncio stdlib; all patterns from official FastAPI docs)
