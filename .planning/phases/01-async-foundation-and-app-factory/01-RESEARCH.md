# Phase 1: Async Foundation & App Factory - Research

**Researched:** 2026-06-14
**Domain:** FastAPI async architecture, app-factory pattern, lifespan singletons, secrets hygiene
**Confidence:** HIGH

---

## Summary

Phase 1 converts the existing synchronous FastAPI backend to an async foundation using an
app-factory + lifespan pattern, placing shared singletons on `app.state`, and fixes the two
documented anti-patterns (per-request provider instantiation in CORE-02, module-level settings
binding in CORE-03). It also verifies secrets hygiene (OPS-07) by auditing `.gitignore` and
`.env.example`.

The existing codebase already uses `lifespan` (in `main.py:11-15`) but misuses it — the
`vector_store` global is still a module-level `None` rather than state on `app`. Provider
creation (`create_llm_provider()`) is called per-request inside `generate_answer()` (line 56)
and `rewrite_query_for_retrieval()` (line 58 of `query_transformer.py`). These two call sites
are the concrete targets of CORE-02.

The most important correctness constraint for this phase: converting a route from `def` to
`async def` in FastAPI is *not* automatically safe if the underlying call is blocking.
FastAPI runs `def` routes in a threadpool automatically — converting to `async def` without
wrapping blocking work in `asyncio.to_thread()` would block the event loop, making throughput
strictly worse than the current `def` routes. The fix is `await asyncio.to_thread(answer_questions, ...)`,
not switching the providers to async SDKs (which changes the `LlmProvider` Protocol and belongs
to a later phase).

**Primary recommendation:** Use `create_app()` factory returning a configured `FastAPI` instance
with an `async def lifespan` that builds the LLM provider and pre-warms the FAISS store and
reranker, attaches them to `app.state`, includes route handlers via an `APIRouter`, and wraps
the blocking `answer_questions` call in `asyncio.to_thread()` inside the now-`async def` route
handler.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CORE-01 | Route handlers are `async def`; app boots via app-factory + lifespan; shared singletons on `app.state` | App-factory pattern + lifespan singleton section below |
| CORE-02 | LLM provider constructed once at startup, not per request | `app.state.llm_provider` pattern; call-chain refactor list below |
| CORE-03 | Settings read inside function bodies, not bound at module import time | `EMBEDDING_MODEL_NAME` anti-pattern; precise fix identified |
| OPS-07 | No keys in repo; `.gitignore` + `.env.example` correct from first commit | Audit findings below — already mostly satisfied |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| App startup / singleton init | API Layer (`main.py` lifespan) | — | Lifespan owns resource construction; singletons live on `app.state` |
| LLM provider selection | API Layer (`main.py` lifespan) | LLM Provider Layer (factory) | Provider built once in lifespan; factory still selects the implementation |
| Blocking I/O offload | API Layer (route handler) | — | `asyncio.to_thread()` wraps synchronous pipeline at the route boundary |
| Settings resolution | Configuration Layer (`config.py`) | — | `Settings()` singleton is correct; individual values must not be bound at module import |
| Vector store lifecycle | API Layer (`app.state`) | RAG Layer (`vector_store.py`) | Ownership moves from module global → lifespan; load logic stays in rag layer |
| Reranker warm-up | API Layer (lifespan) | RAG Layer (`reranker.py`) | Pre-warm call in lifespan; getter singleton stays in rag layer |
| Secrets hygiene | Ops (`.gitignore`, `.env.example`) | — | `.env` already gitignored; `.env.example` already exists; audit only |

---

## Standard Stack

### Core

No new packages are required for the core migration. All capabilities are available in the
existing stack.

| Library | Version (current) | Purpose | Notes |
|---------|-------------------|---------|-------|
| FastAPI | 0.136.0 | App factory, lifespan, `app.state`, `async def` routes | `[VERIFIED: pypi.org]` — already installed |
| Python `asyncio` | stdlib (3.12) | `asyncio.to_thread()` for blocking-call offload | stdlib, no install needed |
| Python `contextlib` | stdlib | `@asynccontextmanager` for lifespan | already used in `main.py` |

### Supporting (testing only)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.3 latest (9.0.2 installed) | Test runner | Regression tests for this phase |
| httpx | 0.28.1 | `TestClient` transport | Sync integration tests using `with TestClient(app) as client:` |

> **Scope gate:** `pytest-asyncio` and `httpx.AsyncClient` are Phase 9 machinery (OPS-04).
> Phase 1 regression tests use the synchronous `TestClient` as a context manager, which is
> sufficient to trigger lifespan and assert no regression.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `asyncio.to_thread()` at route | Switching providers to async SDKs (`AsyncAnthropic`, `AsyncGroq`) | Async SDKs require refactoring the `LlmProvider` Protocol — belongs in Phase 7 (streaming). Wrapping at the route is zero-Protocol-change and correct for now. |
| `app.state` for singletons | Module-level globals or `__new__` singleton | `app.state` is the FastAPI-idiomatic location, testable via `app.dependency_overrides`, and avoids import-time side effects. |
| Pre-warming reranker in lifespan | Keeping lazy init in `reranker.py` | Pre-warming eliminates first-request latency spike. Least-invasive: call `get_reranker_model()` in lifespan — the getter singleton stays in `reranker.py`, no signature changes needed in rag layer. |
| `create_app()` factory | Top-level `app = FastAPI(...)` | Factory enables `app.dependency_overrides` in tests and makes lifespan configurable. Required by CORE-01 success criterion 1. |

**Installation:** No new packages required for the production migration itself. For tests:

```bash
cd backend
pip install pytest httpx
```

---

## Package Legitimacy Audit

| Package | Registry | slopcheck | Disposition |
|---------|----------|-----------|-------------|
| pytest | PyPI | [OK] | Approved |
| httpx | PyPI | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
Browser
  │  POST /api/chat (async def)
  ▼
FastAPI App (created by create_app())
  │
  ├── lifespan (@asynccontextmanager)
  │     ├── create_llm_provider()       → app.state.llm_provider   [CORE-02]
  │     ├── load_faiss_vector_store()   → app.state.vector_store   [CORE-01]
  │     └── get_reranker_model()        → pre-warm only (getter stays in reranker.py)
  │
  ├── APIRouter (registered via include_router inside create_app())
  │     ├── async def chat(request, req: Request)
  │     │     ├── reads  req.app.state.vector_store
  │     │     ├── reads  req.app.state.llm_provider  (passed into pipeline)
  │     │     └── await asyncio.to_thread(answer_questions, ...)
  │     │                                ↑ blocking; runs in threadpool
  │     └── async def get_index_status(req: Request)
  │           └── reads req.app.state.vector_store (bool check)
  │
  └── Singleton thread-safety note: FAISS, CrossEncoder, and SDK HTTP clients
        are designed for concurrent read access across threads — safe to share
        across concurrent asyncio.to_thread() calls from the same process.
```

### Recommended Project Structure (changes only)

```
backend/app/
├── main.py                 # create_app() factory + lifespan + APIRouter registration
│                           # (replaces top-level app = FastAPI() + global vector_store)
├── rag/
│   ├── chat_service.py     # answer_questions() gains llm_provider param; generate_answer() too
│   ├── query_transformer.py  # rewrite_query_for_retrieval() gains llm_provider param
│   └── vector_store.py     # remove module-level EMBEDDING_MODEL_NAME binding [CORE-03]
└── llm/
    └── factory.py          # create_llm_provider() unchanged — still called once in lifespan
```

> **APIRouter note:** Routes must be declared on an `APIRouter` instance and registered with
> `application.include_router(router)` inside `create_app()`. Decorating routes directly on the
> module-level `@app.post(...)` while using an `app = create_app()` pattern means a *different*
> `FastAPI` instance owns the routes — `TestClient(create_app())` would return a fresh app with
> lifespan but no routes, producing 404 on every endpoint. The `APIRouter` pattern avoids this.

### Pattern 1: App Factory + Lifespan Singletons

**What:** `create_app()` function that defines lifespan, builds singletons, attaches to
`app.state`, registers routes via `APIRouter`, and returns the configured `FastAPI` instance.

**When to use:** Always. Enables testing via `with TestClient(create_app())` and clean DI.
The `APIRouter` is the critical ingredient — without it, routes registered on the module-level
`app` are unreachable from a fresh `create_app()` call in tests.

**Example:**
```python
# Source: https://fastapi.tiangolo.com/advanced/events/
from contextlib import asynccontextmanager
from fastapi import APIRouter, FastAPI, Request

router = APIRouter()

@router.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request) -> ChatResponse:
    ...  # see Pattern 2

@router.get("/api/index/status")
async def get_index_status(req: Request):
    ...

@asynccontextmanager
async def lifespan(app: FastAPI):
    # CORE-02: build provider once
    app.state.llm_provider = create_llm_provider()
    # CORE-01: move vector_store off global into app.state
    app.state.vector_store = load_faiss_vector_store(settings.faiss_index_path)
    # Pre-warm reranker (no signature change in reranker.py)
    get_reranker_model()
    yield
    # Shutdown cleanup (if needed in future)

def create_app() -> FastAPI:
    application = FastAPI(title="RAG Knowledge Platform", lifespan=lifespan)
    application.include_router(router)     # routes are visible to every create_app() instance
    # middleware added here
    return application

app = create_app()
```

### Pattern 2: Blocking-to-Async Offload at Route Boundary

**What:** `async def` route wraps blocking pipeline call in `asyncio.to_thread()`. The LLM
providers, FAISS search, and cross-encoder calls all remain synchronous — only the route
boundary changes.

**When to use:** Every route that calls synchronous blocking I/O (all three in Phase 1).

**Critical distinction:** FastAPI runs `def` routes in a thread pool automatically — converting
to `async def` without `asyncio.to_thread()` removes this protection and blocks the event loop.

**Example:**
```python
# Source: FastAPI docs + asyncio stdlib docs
import asyncio
from fastapi import Request

# Route decorated on the module-level APIRouter, NOT on @app.post(...)
@router.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request) -> ChatResponse:
    vector_store = req.app.state.vector_store
    llm_provider = req.app.state.llm_provider

    if vector_store is None:
        raise HTTPException(status_code=503, detail="FAISS index is not loaded.")

    try:
        result = await asyncio.to_thread(
            answer_questions,
            vector_store=vector_store,
            llm_provider=llm_provider,
            question=request.question,
            history=request.history,
        )
        return ChatResponse(**result)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail="Failed to process chat request.") from error
```

### Pattern 3: Accessing `app.state` in Handlers

**What:** FastAPI exposes `request.app.state` in any route receiving a `Request` parameter.
This is the stable, documented way to access lifespan-built singletons without global variables.

**Note:** Starlette 0.52.0 (January 2026) introduced a dict-based `lifespan state` syntax
(`request.state["key"]`). This is a Starlette-level API distinct from FastAPI's `app.state`.
Use `request.app.state.attribute` for compatibility and clarity with the current FastAPI
version (0.136.0). [ASSUMED — Starlette ≥0.52.0 compatibility with FastAPI 0.136.0 not
explicitly verified]

### Pattern 4: Provider Injection Through Pipeline Functions

**What:** Thread the provider down the call chain via function parameters, replacing the
per-call `create_llm_provider()` invocations.

**Concrete call-chain changes required for CORE-02:**

| File | Function | Change |
|------|----------|--------|
| `main.py` | `chat()` route | Read `req.app.state.llm_provider`; pass to `answer_questions()` |
| `rag/chat_service.py` | `answer_questions()` | Add `llm_provider: LlmProvider` param; pass to `generate_answer()` and `rewrite_query_for_retrieval()` |
| `rag/chat_service.py` | `generate_answer()` | Add `llm_provider: LlmProvider` param; remove `create_llm_provider()` call |
| `rag/query_transformer.py` | `rewrite_query_for_retrieval()` | Add `llm_provider: LlmProvider` param; remove `create_llm_provider()` call |
| `llm/factory.py` | `create_llm_provider()` | No change — still called once in lifespan |

**Test impact:** Every call site to both refactored functions in the test suite must be updated.
See "Existing Tests Impacted" table under Validation Architecture for the complete list.

### Pattern 5: CORE-03 Fix — Remove Module-Level Settings Binding

**What:** `EMBEDDING_MODEL_NAME = settings.embedding_model_name` at `vector_store.py:8`
binds the value at import time. Move the read inside the function body.

**Precise fix:**
```python
# BEFORE (vector_store.py:8-11)
EMBEDDING_MODEL_NAME = settings.embedding_model_name  # bound at import

def create_embedding_model() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)

# AFTER
def create_embedding_model() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=settings.embedding_model_name)  # read at call time
```

**Scope clarification:** The `settings = Settings()` singleton in `config.py:36` is **not** a
violation of CORE-03. The rule is "don't bind settings *values* at module import time" — the
`Settings` object itself is fine as a module-level singleton. Only value extraction
(`settings.embedding_model_name`) must move into function bodies.

**Only one offender:** `EMBEDDING_MODEL_NAME` in `vector_store.py`. All other modules already
read settings values inside function bodies. Do not hunt for non-existent violations.

### Anti-Patterns to Avoid

- **`async def` route without `asyncio.to_thread()`:** The FAISS, cross-encoder, and LLM calls
  are all CPU/network blocking. An `async def` route that calls them directly blocks the ASGI
  event loop — strictly worse than the current `def` route which FastAPI automatically runs in
  a threadpool. Always wrap at the route boundary.

- **Using `@app.on_event("startup")`:** Deprecated in FastAPI. Use `lifespan` context manager
  exclusively. [CITED: https://fastapi.tiangolo.com/advanced/events/]

- **Keeping `vector_store` as a module-level global:** The `global vector_store` pattern in
  the current `main.py` lifespan is the anti-pattern — it makes the app untestable without
  side effects on the module. Move to `app.state.vector_store`.

- **Decorating routes with `@app.post(...)` instead of `@router.post(...)`:** When `app` is
  created by `create_app()`, routes decorated on the module-level `app` are not present on a
  fresh `create_app()` call. `TestClient(create_app())` would produce 404 on every route.
  Always declare routes on an `APIRouter` and register with `application.include_router(router)`.

- **Migrating providers to async SDKs in this phase:** `AsyncAnthropic`, `AsyncGroq`, etc.
  require the `LlmProvider` Protocol to become async, which ripples to chat_service and every
  caller. This is scoped to Phase 7 (streaming). Do not change provider internals in Phase 1.

- **Pinecone or DB session-maker in lifespan:** Neither exists yet. CORE-01's success criterion
  mentions them in the full-system context; Phase 1 lifespan initializes only what exists today:
  LLM provider, FAISS store, reranker pre-warm. Pinecone (Phase 4) and DB session maker
  (Phase 2) are explicitly out of Phase 1 scope.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Running blocking code in async context | Custom thread executor management | `asyncio.to_thread()` (stdlib, Python 3.9+) | Built-in, correct default thread pool, no tuning needed |
| Singleton resource lifecycle | Custom init flags, `__new__` tricks | `lifespan` + `app.state` | Idiomatic FastAPI, cleaned up on shutdown, testable via TestClient context manager |
| Testing lifespan init | Mocking at module level | `with TestClient(create_app()) as client:` | Context-manager form triggers full lifespan; singletons are built and available |

**Key insight:** The `asyncio.to_thread()` + `app.state` combination is the standard FastAPI
pattern for exactly this use case — a blocking ML/API pipeline wrapped in an async server.
No third-party orchestration libraries are needed.

**Thread-safety note:** The FAISS index, CrossEncoder model, and SDK HTTP clients (Anthropic,
Groq, Google) are designed for concurrent read access across threads — it is safe to share
these singletons from `app.state` across concurrent `asyncio.to_thread()` calls in the same
process without additional locking.

---

## Common Pitfalls

### Pitfall 1: `async def` Route Without `asyncio.to_thread()` Blocks the Event Loop

**What goes wrong:** Developer converts `def chat()` to `async def chat()` and calls
`answer_questions()` directly. The FAISS similarity search, cross-encoder rerank, and LLM call
all block the single event loop thread. Under concurrent requests, they queue behind each other.
The current `def` route is actually safer because FastAPI auto-dispatches it to a threadpool.

**Why it happens:** "Convert to async" is conflated with "becomes non-blocking." In FastAPI,
`async def` means "I will await non-blocking coroutines" — not "FastAPI will make my code async."

**How to avoid:** Wrap every blocking synchronous call in an `async def` route with
`await asyncio.to_thread(blocking_fn, *args, **kwargs)`.

**Warning signs:** `async def` route with no `await` expressions inside it (or only `await`
on `asyncio.to_thread`), or any direct call to `vector_store.similarity_search_with_score()`
or LLM provider methods inside an `async def` without `to_thread`.

### Pitfall 2: Routes Decorated on Module-Level `app` Are Invisible to `TestClient(create_app())`

**What goes wrong:** Routes are defined with `@app.post(...)` where `app = create_app()` is
the module-level instance. When a test calls `TestClient(create_app())`, it gets a *new*
`FastAPI` instance with lifespan and middleware but no routes — every request returns 404.

**Why it happens:** `create_app()` constructs a fresh `FastAPI` instance each call. Routes
bound to the first instance are not on the second instance. The factory pattern only works
correctly when routes are declared on a shared `APIRouter` and registered via
`application.include_router(router)` inside `create_app()`.

**How to avoid:** Declare all routes on a module-level `router = APIRouter()` instance.
Register the router inside `create_app()` with `application.include_router(router)`.

**Warning signs:** `TestClient(create_app())` returns 404 on all routes that appear to be
defined. Routes are decorated with `@app.post(...)` rather than `@router.post(...)`.

### Pitfall 3: `test_query_rewrite.py` Patches a Call Site That No Longer Exists (and Misses All Real Call Sites)

**What goes wrong:** The CORE-02 refactor changes two function signatures:
- `rewrite_query_for_retrieval(question, ...)` gains `llm_provider: LlmProvider`
- `answer_questions(vector_store, question, ...)` gains `llm_provider: LlmProvider`

This breaks *every* call to these functions in the test suite — not just the two `patch` lines.

Specific breakage in `test_query_rewrite.py`:
- **Line 14:** `rewrite_query_for_retrieval(question)` — if `llm_provider` is non-optional, this `TypeError`s. (The `enable_query_rewrite = False` path never calls the provider, but the signature still requires the argument.)
- **Lines 27, 47, 71-75:** `patch("app.rag.query_transformer.create_llm_provider", ...)` becomes a no-op — `create_llm_provider` is no longer imported or called inside `rewrite_query_for_retrieval()`. Tests pass trivially but assert nothing meaningful.
- **Line 91:** `chat_service.answer_questions(vector_store, "original question")` — `TypeError` because `llm_provider` is missing from the call.

**Why it happens:** The refactor changes both function signatures, and the call sites in tests
were written against the old signatures. The patch lines are the most visible symptom, but the
missing positional/keyword argument is the underlying cause.

**How to avoid:** When updating `rewrite_query_for_retrieval` and `answer_questions` signatures,
update *all* call sites in tests in the same task:
1. Replace all `patch("...create_llm_provider", ...)` blocks with `llm_provider=Mock()` passed directly
2. Add `llm_provider=Mock()` to all bare calls to `rewrite_query_for_retrieval(question)` (line 14)
3. Add `llm_provider=Mock()` to the `answer_questions(vector_store, ...)` call (line 91)

**Warning signs:** `TypeError: rewrite_query_for_retrieval() missing 1 required positional argument`
or `TypeError: answer_questions() missing 1 required positional argument` in the test output.

### Pitfall 4: Removing `EMBEDDING_MODEL_NAME` Constant Breaks Build Script

**What goes wrong:** `build_index.py` or other scripts may import `EMBEDDING_MODEL_NAME`
from `vector_store.py` directly if such an import exists.

**How to avoid:** Grep for `from app.rag.vector_store import EMBEDDING_MODEL_NAME` before
removing the constant. In the current codebase, no external importer of that constant was found
— but verify before deleting.

**Warning signs:** `ImportError` on `build_index.py` run after the fix.

### Pitfall 5: `get_index_status` Still References `vector_store` Module Global After Migration

**What goes wrong:** After moving `vector_store` to `app.state`, the `get_index_status` route
still reads the module-level `vector_store = None` (now always `None`), reporting the index as
never loaded.

**How to avoid:** Update `get_index_status` to read `req.app.state.vector_store`. This route
also needs a `Request` parameter added and must become `async def`.

### Pitfall 6: TestClient Not Used as Context Manager (Lifespan Skipped)

**What goes wrong:** `client = TestClient(app)` without `with` skips the lifespan — `app.state`
is never populated — and all routes that read singletons from `app.state` raise `AttributeError`.

**How to avoid:** Always use `with TestClient(create_app()) as client:` in tests for this
phase. The context-manager form is the documented way to trigger lifespan.
[CITED: FastAPI docs, GitHub discussion #10800]

---

## Code Examples

### App Factory with Lifespan and APIRouter

```python
# Source: https://fastapi.tiangolo.com/advanced/events/ (official pattern, adapted)
from contextlib import asynccontextmanager
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.llm.factory import create_llm_provider
from app.llm.provider import LlmProvider
from app.rag.vector_store import load_faiss_vector_store
from app.rag.reranker import get_reranker_model
from app.schemas.chat import ChatRequest, ChatResponse

# Declare routes on a shared router — not on @app.post(...) directly.
# This is required so TestClient(create_app()) sees the routes.
router = APIRouter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.llm_provider = create_llm_provider()        # CORE-02
    app.state.vector_store = load_faiss_vector_store(     # CORE-01
        settings.faiss_index_path
    )
    get_reranker_model()                                   # pre-warm singleton
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="RAG Knowledge Platform",
        lifespan=lifespan,
    )
    application.include_router(router)   # routes visible to every create_app() instance
    # CORS: narrow to explicit methods/headers (CONCERNS.md security recommendation).
    # Move allowed_origins to settings.allowed_origins in this phase so deployment
    # environments can override without touching source.
    # NOTE: settings.allowed_origins is a new Settings field added in this phase.
    # Default value: ["http://localhost:5173", "http://127.0.0.1:5173"]
    # Phase-5 work: update to Vercel origin at deploy time.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    return application


app = create_app()
```

### Async Route with `asyncio.to_thread()`

```python
import asyncio

# Note: @router.post, not @app.post — see App Factory note above.
@router.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request) -> ChatResponse:
    vector_store = req.app.state.vector_store
    llm_provider: LlmProvider = req.app.state.llm_provider

    if vector_store is None:
        raise HTTPException(status_code=503, detail="FAISS index is not loaded.")

    try:
        result = await asyncio.to_thread(
            answer_questions,
            vector_store=vector_store,
            llm_provider=llm_provider,
            question=request.question,
            history=request.history,
        )
        return ChatResponse(**result)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail="Failed to process chat request.") from error
```

### Updated `rewrite_query_for_retrieval` Signature

```python
# query_transformer.py — provider injected, not created internally
def rewrite_query_for_retrieval(
    question: str,
    llm_provider: LlmProvider,          # NEW — injected from app.state
    history: list[ChatMessage] | None = None,
) -> str:
    ...
    rewritten_query = llm_provider.rewrite_query(rewrite_input)   # use injected provider
    ...
```

### Test Pattern for Lifespan

```python
# Source: FastAPI discussion #10800
from fastapi.testclient import TestClient

def test_chat_endpoint_returns_answer():
    with TestClient(create_app()) as client:          # context-manager triggers lifespan
        response = client.post("/api/chat", json={
            "question": "What is the enrollment deadline?",
            "history": [],
        })
    assert response.status_code == 200
```

---

## OPS-07 Audit: Secrets Hygiene

### Current State (verified by inspection)

| Check | Status | Evidence |
|-------|--------|----------|
| `.env` in `.gitignore` | PASS | `.gitignore` line 4: `.env` |
| `backend/.env.example` exists | PASS | File exists with placeholder values |
| `frontend/.env.example` exists | PASS | File exists |
| No `.env` tracked in git | VERIFY | Run `git ls-files \| grep -iE '\.env$'` — expected: no output |
| `__pycache__` gitignored | PASS | `.gitignore` line 2 |
| `.venv` gitignored | PASS | `.gitignore` line 1 |

### Remaining Actions for OPS-07

1. **Verify**: Run `git ls-files | grep -iE '\.env$'` — confirm no `.env` files are tracked.
   If any are tracked, `git rm --cached` them.

2. **Minor update to `.env.example`**: Current `backend/.env.example` shows `LLM_PROVIDER`
   and `LLM_MODEL_NAME` but is missing the other settings fields defined in `config.py`
   (`EMBEDDING_MODEL_NAME`, `FAISS_INDEX_PATH`, `PDF_PATH`, `RETRIEVAL_CANDIDATE_K`,
   `RERANKED_TOP_K`, `RERANKER_MODEL_NAME`, `ENABLE_QUERY_REWRITE`). Recommend adding all
   settings keys with placeholder or default values. Low priority for correctness; improves
   onboarding.

3. **CORS origins**: Currently hardcoded in `main.py`. Moving to `settings.allowed_origins`
   (new `list[str]` field with default `["http://localhost:5173", "http://127.0.0.1:5173"]`)
   is a low-risk change that removes a hardcoded value and sets up Phase 5 (deploy-time override).

**OPS-07 summary:** The critical requirements (`.env` gitignored, `.env.example` committed with
placeholders, no real secrets tracked) are already satisfied. Phase 1 work is verification +
minor completeness improvement, not a from-scratch setup.

---

## Validation Architecture

> `workflow.nyquist_validation: true` in `.planning/config.json` — section required.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 (9.0.2 installed) |
| Config file | None — Wave 0 must create `backend/pytest.ini` |
| Quick run command | `cd backend && python -m pytest tests/ -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| CORE-01 | App boots via `create_app()` with lifespan; singletons on `app.state` | integration | `pytest tests/test_app_factory.py -x` | No — Wave 0 gap |
| CORE-02 | Provider constructed exactly once; not per-request | integration | `pytest tests/test_app_factory.py::test_provider_constructed_once -x` | No — Wave 0 gap |
| CORE-03 | No module-level settings value binding | unit (static check) | `grep -n "^[A-Z_]* = settings\." backend/app/rag/vector_store.py` | Test added to Wave 0 |
| CORE-01 | Chat endpoint still answers correctly (no regression) | integration | `pytest tests/test_app_factory.py::test_chat_endpoint_regression -x` | No — Wave 0 gap |
| OPS-07 | No `.env` file tracked in git | smoke | `git ls-files \| grep -iE '\.env$'` (manual verification) | N/A (git audit) |

### Existing Tests Impacted by Phase 1 Refactor

Both `rewrite_query_for_retrieval()` and `answer_questions()` gain a required `llm_provider`
parameter. Every call site to either function in the test suite must be updated.

| Test File | Line(s) | Impact | Action Required |
|-----------|---------|--------|-----------------|
| `tests/test_query_rewrite.py` | 14 | `rewrite_query_for_retrieval(question)` — `TypeError` if `llm_provider` is non-optional | Add `llm_provider=Mock()` arg |
| `tests/test_query_rewrite.py` | 27 | `patch("...create_llm_provider", ...)` — no-op after refactor; `rewrite_query_for_retrieval("What about shifting?")` also missing new arg | Remove patch; add `llm_provider=Mock()` direct arg |
| `tests/test_query_rewrite.py` | 47 | Same pattern as line 27 with history | Remove patch; add `llm_provider=Mock()` direct arg |
| `tests/test_query_rewrite.py` | 71-75 | Same patch pattern; `rewrite_query_for_retrieval(...)` call missing new arg | Remove patch; add `llm_provider=Mock()` direct arg |
| `tests/test_query_rewrite.py` | 91 | `answer_questions(vector_store, "original question")` — `TypeError`, `llm_provider` missing | Add `llm_provider=Mock()` to call |
| `tests/test_anthropic_provider.py` | — | Tests `AnthropicLlmProvider` directly — unaffected | No change |
| `tests/test_gemini_provider.py` | — | Same — unaffected | No change |

### Sampling Rate

- **Per task commit:** `cd backend && python -m pytest tests/ -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `backend/pytest.ini` — no config file exists; test discovery path must be set
- [ ] `backend/tests/test_app_factory.py` — new integration tests covering CORE-01, CORE-02, regression
- [ ] Existing `test_query_rewrite.py` must be updated (not new — modification of existing file; all 5 impacted call sites)

---

## Security Domain

> `security_enforcement` absent from `config.json` — treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Not in Phase 1 scope (Phase 3) |
| V3 Session Management | No | Not in Phase 1 scope |
| V4 Access Control | No | Not in Phase 1 scope |
| V5 Input Validation | Yes | Pydantic `ChatRequest` (already in place) |
| V6 Cryptography | No | No crypto in this phase |

### Known Threat Patterns for FastAPI Async Migration

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Event loop starvation (blocking call in `async def`) | Denial of Service | `asyncio.to_thread()` for all blocking pipeline calls |
| Secrets in source control | Information Disclosure | `.env` gitignored (already done); verify with `git ls-files` |
| CORS wildcard methods/headers | Elevation of Privilege | Narrow to `["GET", "POST"]` and `["Content-Type"]` per CONCERNS.md recommendation |
| `/api/index/status` leaks internal paths | Information Disclosure | Out of scope for Phase 1; document for Phase 3 (auth gate) |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | All backend | Assumed — project targets 3.12 | — | None |
| FastAPI 0.136.0 | CORE-01 | Yes — installed | 0.136.0 | — |
| asyncio.to_thread | Blocking offload | Yes — stdlib Python 3.9+ | stdlib | — |
| pytest | Tests | Yes (9.0.2 installed) | 9.0.2 | — |
| httpx | TestClient | Yes (0.28.1 installed) | 0.28.1 | — |
| FAISS index files | Regression test | Yes — pre-built locally | — | Skip regression test; use mock |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `lifespan` context manager | FastAPI 0.93+ | Startup/shutdown now in one function; `@on_event` deprecated |
| `app.state` via globals | `app.state` via `request.app.state` | Starlette 0.20+ | Testable, scoped, no import-time side effects |
| Sync `def` routes (threadpool auto-dispatch) | `async def` + `asyncio.to_thread()` | Python 3.9 / ASGI adoption | Explicit, correct; old pattern also worked but hid blocking |
| `startup`/`shutdown` events | `lifespan` | FastAPI ≥ 0.93 | Both valid until FastAPI removes `on_event`; lifespan is the current standard |

**Deprecated/outdated:**
- `@app.on_event("startup")` / `@app.on_event("shutdown")`: deprecated; use `lifespan` context manager [CITED: https://fastapi.tiangolo.com/advanced/events/]
- Module-level `vector_store = None` + `global vector_store` in lifespan: replaced by `app.state.vector_store`

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Starlette ≥0.52.0 dict-based lifespan state (`request.state["key"]`) is available in FastAPI 0.136.0 | Architecture Patterns | Low — we recommend `request.app.state` (attribute access) not the dict syntax; this is only context |
| A2 | `asyncio.to_thread()` with keyword arguments works as shown for `answer_questions` | Code Examples | Low — Python 3.12 stdlib; unlikely to differ |
| A3 | The CORS hardcoded origins should move to settings | OPS-07 Audit | Low — improvement recommendation, not a blocker |

**All claims tagged `[ASSUMED]` are low-risk and do not block planning.**

---

## Open Questions

1. **Should `allowed_origins` move to `Settings` in Phase 1?**
   - What we know: CONCERNS.md recommends moving to env var; deployment origins change per environment (Phase 5)
   - What's unclear: Is this CORE-01 scope or SHIP-01 (Phase 5)?
   - Recommendation: Add `allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]` to `Settings` in Phase 1 — low-risk change that removes a hardcoded value, sets up Phase 5

2. **Should embedding model in lifespan also go to `app.state`?**
   - What we know: `create_embedding_model()` is called in `load_faiss_vector_store()` — the embedding model is embedded inside the FAISS wrapper at load time, so it's not separately needed on `app.state`
   - Recommendation: No — the embedding model singleton pattern stays in `vector_store.py`; CORE-03 fix is the only change needed there

---

## Sources

### Primary (HIGH confidence)
- https://fastapi.tiangolo.com/advanced/events/ — official lifespan documentation with `app.state` pattern and deprecation notice for `@app.on_event`
- Python 3.12 stdlib docs — `asyncio.to_thread()` (stdlib since Python 3.9)
- https://fastapi.tiangolo.com/advanced/async-tests/ — official async testing pattern

### Secondary (MEDIUM confidence)
- https://github.com/fastapi/fastapi/discussions/10800 — community discussion confirming TestClient context-manager form triggers lifespan
- https://www.starlette.io/lifespan/ — Starlette lifespan state documentation (dict-based syntax ≥0.52.0)

### Tertiary (LOW confidence)
- https://medium.com/@hieutrantrung.it/using-fastapi-like-a-pro-with-singleton-and-dependency-injection-patterns-28de0a833a52 — community article on singleton patterns
- https://shiladityamajumder.medium.com/async-apis-with-fastapi-patterns-pitfalls-best-practices-2d72b2b66f25 — community article on blocking call pitfalls

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; FastAPI 0.136.0 already installed and documented
- Architecture: HIGH — app-factory + lifespan pattern is official FastAPI documented approach
- Pitfalls: HIGH — derived from direct codebase analysis (exact line numbers identified), not inference
- Test impact: HIGH — exact test file and line numbers identified; all call sites enumerated

**Research date:** 2026-06-14
**Valid until:** 2026-07-14 (stable FastAPI ecosystem; 30-day window safe)
