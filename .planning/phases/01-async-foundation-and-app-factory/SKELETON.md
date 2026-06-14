# Walking Skeleton: Async Foundation & App Factory

**Phase:** 1 — Async Foundation & App Factory
**Type:** Brownfield migration — Walking Skeleton proves the async refactor works end-to-end
**Definition:** App boots via `create_app()` factory, lifespan fires, singletons attach to `app.state`, and `/api/chat` returns a valid cited response — all without regression.

---

## Architectural Decisions (Non-Negotiable for Future Phases)

These decisions are locked by Phase 1. Future phases extend them without renegotiating.

### 1. App-Factory Pattern

**Decision:** The FastAPI app is created by `create_app() -> FastAPI`, never by a module-level `app = FastAPI(...)` directly consumed by tests or alternate entry points.

**Rationale:** Factory pattern enables `with TestClient(create_app()) as client:` in tests (fresh app per test, lifespan triggered), and supports `app.dependency_overrides` for Phase 3 auth testing. Top-level `app = create_app()` is the uvicorn entry point.

**Contract for future phases:**
- New capabilities (DB session maker in Phase 2, Pinecone client in Phase 4) are initialized in the `lifespan` body and attached to `app.state`
- New route groups are declared on `router = APIRouter()` (or new routers) and registered with `application.include_router(...)` inside `create_app()`
- No route is ever decorated with `@app.post(...)` — always `@router.post(...)`

### 2. Lifespan Singletons on `app.state`

**Decision:** All shared, long-lived, startup-initialized resources live on `app.state`. Route handlers access them via `req.app.state.<name>`.

**Current singletons (after Phase 1):**
| `app.state` attribute | Type | Built by |
|---|---|---|
| `app.state.llm_provider` | `LlmProvider` | `create_llm_provider()` in lifespan |
| `app.state.vector_store` | `FAISS` | `load_faiss_vector_store(settings.faiss_index_path)` in lifespan |

**Future singletons (added in later phases):**
| Phase | `app.state` attribute | What adds it |
|---|---|---|
| Phase 2 | `app.state.db_sessionmaker` | `async_sessionmaker` from async SQLAlchemy engine |
| Phase 4 | `app.state.pinecone_index` | Pinecone serverless index client |
| Phase 4 | `app.state.voyage_client` | Voyage embeddings/reranking API client |

**Rationale:** `app.state` is the FastAPI-idiomatic singleton store — testable, scoped to app lifetime, no import-time side effects, no global mutation. Module-level mutable globals (`global vector_store`) are eliminated by this phase.

### 3. Blocking I/O Offload Boundary: `asyncio.to_thread()` at Route

**Decision:** All route handlers are `async def`. Blocking synchronous pipeline calls (FAISS similarity search, cross-encoder rerank, LLM provider calls) are wrapped in `await asyncio.to_thread(blocking_fn, **kwargs)` at the route boundary.

**Rationale:** FastAPI auto-runs `def` routes in a threadpool. `async def` routes do NOT get this protection. Wrapping at the route boundary keeps the event loop unblocked without changing the `LlmProvider` Protocol (which would cascade to all providers and belongs in Phase 7 streaming). The providers, FAISS index, and cross-encoder are all safe for concurrent read access across threads.

**Contract for future phases:**
- Phase 7 (SSE Streaming) will switch providers to async SDKs (`AsyncAnthropic`, `AsyncGroq`, etc.) and refactor the `LlmProvider` Protocol. At that point, `asyncio.to_thread()` at the route is replaced by direct `await` calls.
- Until Phase 7, all new route handlers that call blocking I/O must use `asyncio.to_thread()`.

### 4. Provider Injection Through Call Chain (No Per-Call Instantiation)

**Decision:** The LLM provider is constructed exactly once in `lifespan` and stored on `app.state.llm_provider`. Route handlers pass it down through the call chain as a function parameter. No function below the route layer calls `create_llm_provider()` internally.

**Call chain after Phase 1:**
```
lifespan → create_llm_provider() → app.state.llm_provider
route handler → reads req.app.state.llm_provider
  → answer_questions(llm_provider=...) → generate_answer(llm_provider=...) ← uses injected
                                       → rewrite_query_for_retrieval(llm_provider=...) ← uses injected
```

**Rationale:** Per-request provider instantiation (the pre-Phase-1 anti-pattern) creates a new SDK client on every request — wasted connections, wasted memory, no connection reuse. The factory `create_llm_provider()` is unchanged; only its call site moves from inside the pipeline to the lifespan.

### 5. Settings Values Read at Call Time, Not Import Time

**Decision:** `settings = Settings()` at module level in `config.py` is correct and unchanged. Individual settings *values* (e.g., `settings.embedding_model_name`) must NOT be bound to module-level constants at import time. They must be read inside function bodies.

**Only offender in the current codebase:** `EMBEDDING_MODEL_NAME = settings.embedding_model_name` in `vector_store.py` line 8. Deleted in Phase 1.

**Rationale:** Import-time binding prevents test-time overrides of individual settings values (e.g., `patch("...settings.embedding_model_name", "test-model")` would work but the constant is already frozen). Function-body reads reflect the current settings state at call time.

### 6. CORS Configured from Settings

**Decision:** CORS `allow_origins` comes from `settings.allowed_origins` (a new `list[str]` field in `Settings` added in Phase 1). Methods are narrowed to `["GET", "POST"]`, headers to `["Content-Type"]`.

**Default value:** `["http://localhost:5173", "http://127.0.0.1:5173"]`

**Rationale:** Hardcoded origins in source (`main.py` pre-Phase-1) prevent Phase 5 deployment-time override via env var. Wildcard `allow_methods=["*"]` and `allow_headers=["*"]` are unnecessarily permissive for a JSON API.

**Phase 5 extension:** Set `ALLOWED_ORIGINS=["https://your-app.vercel.app"]` in Render env at deploy time.

### 7. Test Infrastructure

**Decision:** `backend/pytest.ini` with `testpaths = tests` and `pythonpath = .` is the test runner config. All tests use `unittest.TestCase` style. Integration tests use `with TestClient(create_app()) as client:` (context-manager form to trigger lifespan).

**Phase 9 extension:** `pytest-asyncio` and `httpx.AsyncClient` are added in Phase 9 (OPS-04) for async integration tests and CI.

---

## Directory Layout After Phase 1

```
backend/
├── app/
│   ├── core/
│   │   └── config.py          # +allowed_origins field
│   ├── llm/
│   │   ├── factory.py         # unchanged
│   │   ├── provider.py        # unchanged (Protocol)
│   │   ├── groq_provider.py   # unchanged
│   │   ├── anthropic_provider.py  # unchanged
│   │   └── gemini_provider.py # unchanged
│   ├── rag/
│   │   ├── chat_service.py    # +llm_provider param on answer_questions, generate_answer
│   │   ├── query_transformer.py  # +llm_provider param on rewrite_query_for_retrieval
│   │   ├── vector_store.py    # -EMBEDDING_MODEL_NAME constant (CORE-03)
│   │   └── reranker.py        # unchanged
│   ├── schemas/
│   │   └── chat.py            # unchanged
│   └── main.py                # full rewrite: create_app() + lifespan + APIRouter + async routes
├── tests/
│   ├── test_app_factory.py    # NEW: integration tests for CORE-01, CORE-02
│   ├── test_query_rewrite.py  # MODIFIED: 5 call sites updated for new signatures
│   ├── test_anthropic_provider.py  # unchanged
│   └── test_gemini_provider.py    # unchanged
├── pytest.ini                 # NEW: test runner config
└── .env.example               # EXTENDED: all Settings fields + ALLOWED_ORIGINS
```

---

## What This Skeleton Proves

1. The app boots via `create_app()` with a working async lifespan
2. LLM provider and FAISS vector store are initialized exactly once at startup and available on `app.state`
3. The async `chat` route offloads to `asyncio.to_thread()` — no event-loop blocking
4. The existing chat endpoint produces a valid cited answer after the migration (no regression)
5. Secrets hygiene is verified: no `.env` in git, `.env.example` covers all settings fields

This skeleton is the foundation all future phases extend. Phase 2 adds the DB sessionmaker to `app.state` in the same lifespan. Phase 4 adds Pinecone/Voyage clients. The factory, lifespan, and `app.state` patterns are fixed from this point forward.
