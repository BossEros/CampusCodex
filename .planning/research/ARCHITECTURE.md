# Architecture Research

**Domain:** Production RAG platform — brownfield additions (auth, Postgres, managed vectors/embeddings, streaming, eval) to an existing layered FastAPI + React single-doc RAG app
**Researched:** 2026-06-10
**Confidence:** HIGH (existing layers read from `.planning/codebase/`; stack locked in `.planning/research/STACK.md`; this is design synthesis over established facts, not new ecosystem research)

> **Scope:** How to STRUCTURE the new components into the existing layered design. The existing RAG flow (retrieve → rerank → generate) is kept and extended, not re-researched. The guiding principle from PROJECT.md is **extend, don't rewrite** — mirror the proven `llm/` Protocol+factory pattern, keep the layered separation, fix the two flagged anti-patterns as a side effect of going async.

---

## Headline Structural Decisions (read first)

| # | Decision | One-line rationale |
|---|----------|--------------------|
| 1 | **Sync→async migration is the foundation, not the streaming phase** | STACK.md locked async SQLAlchemy + asyncpg, so the *Postgres phase itself* needs `async def`. Do it first; sync-DB-then-async-DB is rework. |
| 2 | **Two Pinecone namespaces: `benchmark` (fixed corpus) vs `shared_kb` (admin uploads)** | Eval queries hit only the frozen `benchmark` namespace → user uploads cannot move eval scores (PROJECT eval-integrity constraint). |
| 3 | **`Depends()` becomes the DI backbone** | Auth, per-request `AsyncSession`, RBAC role-gates, and rate limiting all hang off `Depends`. The codebase currently uses zero DI. |
| 4 | **Lifespan-initialized singletons on `app.state`, injected via `Depends`** | Fixes both flagged anti-patterns (provider-per-request, import-time settings) cleanly: Pinecone/Voyage/LLM clients + `async_sessionmaker` created once at startup. |
| 5 | **Deterministic vector IDs `{document_id}:{chunk_index}` + a Postgres `documents` table** | Makes admin "delete document" a metadata-filter / id-prefix delete in Pinecone with no separate chunk-id mapping table required. |
| 6 | **Ingestion runs in `BackgroundTasks` with a `documents.status` lifecycle** | Render free tier has no Celery/Redis worker; chunk→embed(rate-limited Voyage)→upsert must not block the HTTP response. Admin polls status. |
| 7 | **Mirror `llm/` exactly for new providers: `embeddings/` and `reranking/` each get `provider.py` (Protocol) + `factory.py` + `voyage_provider.py`** | Same proven pattern; the Voyage *client* is shared via lifespan, the *abstractions* stay separate (SOLID). |
| 8 | **`LlmProvider` Protocol gains `stream_answer()`** | Streaming touches the provider layer, not only the route — each provider adapts its native async stream to a common token iterator. |

---

## Standard Architecture

### System Overview (target state)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    React/Vite Frontend (Vercel)                            │
│  Login/Register · Chat (SSE stream consumer) · Saved conversations         │
│  Admin: document upload + status list · Evidence drawer                    │
└───────────────┬──────────────────────────────────────────┬───────────────┘
                │  Bearer JWT on every call                 │  SSE (text/event-stream)
                ▼                                            ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                   FastAPI HTTP / API Layer (Render)                        │
│  app/main.py (app factory + lifespan)                                      │
│  app/api/routers/  auth · chat · conversations · documents · health        │
│  Cross-cutting via Depends: get_current_user · require_admin ·             │
│                             get_db_session · rate_limit                     │
└───┬───────────────┬───────────────┬───────────────┬───────────────┬───────┘
    ▼               ▼               ▼               ▼               ▼
┌─────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────┐
│  auth/  │  │  rag/        │  │ documents/   │  │  eval/   │  │  core/   │
│ JWT,    │  │ chat_service │  │ ingestion_   │  │ ragas    │  │ config,  │
│ pwd hash│  │ (+streaming) │  │ service      │  │ harness  │  │ logging, │
│ deps    │  │ query_xform  │  │ (chunk→embed │  │ (offline │  │ security │
│         │  │ retrieval    │  │  →upsert)    │  │  /CI)    │  │ helpers  │
└────┬────┘  └──────┬───────┘  └──────┬───────┘  └────┬─────┘  └──────────┘
     │              │                 │               │
     │              ▼                 ▼               │
     │      ┌───────────────┐ ┌───────────────┐      │
     │      │ embeddings/   │ │ reranking/    │      │   (provider layer —
     │      │ provider+     │ │ provider+     │      │    Protocol+factory,
     │      │ factory+      │ │ factory+      │      │    mirrors llm/)
     │      │ voyage_*      │ │ voyage_*      │      │
     │      └───────┬───────┘ └───────┬───────┘      │
     ▼              ▼                 ▼               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          Data / Persistence Layer                          │
│  db/  SQLAlchemy 2.x async models + AsyncSession  ──►  Postgres (Neon)      │
│  Pinecone serverless index (1024/cosine)                                   │
│     namespace "benchmark"  (frozen student_manual — eval only)             │
│     namespace "shared_kb"  (admin-uploaded multi-doc KB — user queries)    │
│  Voyage AI (embed + rerank APIs) · Groq/Anthropic/Gemini (LLM + eval judge)│
└──────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `api/routers/*` | HTTP routing, request/response validation, wire `Depends` | FastAPI `APIRouter` per resource; `async def` handlers |
| `auth/` | Password hashing, JWT issue/verify, current-user + role dependencies | pwdlib + PyJWT; `get_current_user`, `require_admin` as `Depends` |
| `db/` | Async engine, session factory, ORM models, session dependency | SQLAlchemy 2.x async, `async_sessionmaker`, Alembic migrations |
| `rag/chat_service` | Orchestrate retrieve → rerank → context → (stream) answer; query against `shared_kb` | Extend existing orchestrator; add `stream_answer` path |
| `rag/vector_store` | Pinecone query/upsert/delete (replaces FAISS) | `pinecone` SDK client from lifespan; namespace-aware |
| `documents/ingestion_service` | chunk → embed (Voyage) → upsert (Pinecone `shared_kb`); status updates | Reuse `pdf_loader` + `text_chunker`; `BackgroundTasks` |
| `embeddings/` | Embed text via API behind a Protocol | `provider.py` Protocol + `factory.py` + `voyage_provider.py` |
| `reranking/` | Rerank candidates via API behind a Protocol | `provider.py` Protocol + `factory.py` + `voyage_provider.py` |
| `eval/` | RAGAS harness over frozen `benchmark` namespace + golden Q/A | ragas 0.4.x; Groq as judge LLM; run offline / in CI |
| `core/` | Settings, structured logging, security helpers, rate-limit setup | Pydantic settings, structlog, slowapi limiter |

---

## Recommended Project Structure

Extends the existing `backend/app/` layout (per STRUCTURE.md). New dirs in **bold-equivalent** comments; existing dirs noted.

```
backend/app/
├── main.py                      # app factory + lifespan (init clients/sessionmaker on app.state)
├── api/                         # NEW — HTTP layer split out of monolithic main.py
│   ├── deps.py                  #   shared Depends: get_db_session, get_current_user, require_admin, rate_limit
│   └── routers/
│       ├── auth.py              #   POST /api/auth/register, /login, /refresh
│       ├── chat.py              #   POST /api/chat  (SSE StreamingResponse)
│       ├── conversations.py     #   GET/POST/DELETE /api/conversations (user history)
│       ├── documents.py         #   POST/GET/DELETE /api/admin/documents (admin only)
│       └── health.py            #   /health, /api/index/status
├── auth/                        # NEW — security domain
│   ├── security.py              #   pwdlib hashing, PyJWT encode/decode
│   ├── service.py               #   register/authenticate user against db
│   └── schemas.py               #   TokenPair, UserRegister, UserLogin, UserOut
├── db/                          # NEW — persistence
│   ├── session.py               #   async engine + async_sessionmaker
│   ├── base.py                  #   DeclarativeBase
│   └── models.py                #   User, Role(enum), Conversation, Message, Document
├── documents/                   # NEW — ingestion domain
│   ├── ingestion_service.py     #   load→chunk→embed→upsert (shared_kb namespace)
│   └── service.py               #   document CRUD + status, delete-by-prefix in Pinecone
├── embeddings/                  # NEW — mirrors llm/
│   ├── provider.py              #   EmbeddingProvider Protocol
│   ├── factory.py               #   create_embedding_provider()
│   └── voyage_provider.py
├── reranking/                   # NEW — mirrors llm/
│   ├── provider.py              #   RerankerProvider Protocol
│   ├── factory.py               #   create_reranker_provider()
│   └── voyage_provider.py
├── eval/                        # NEW — credibility signal
│   ├── golden_set.py            #   golden Q/A loader (fixed)
│   └── run_eval.py              #   ragas harness over benchmark namespace
├── llm/                         # EXISTING — add stream_answer() to Protocol + each provider
│   ├── provider.py  factory.py  prompts.py  *_provider.py
├── rag/                         # EXISTING — vector_store.py now wraps Pinecone, not FAISS
│   ├── chat_service.py  query_transformer.py  vector_store.py
│   ├── pdf_loader.py  text_chunker.py
│   └── (reranker.py removed — replaced by reranking/ provider)
├── core/                        # EXISTING — extend
│   ├── config.py                #   + DB url, Pinecone/Voyage keys, JWT secret, namespaces
│   ├── logging.py               # NEW — structlog JSON config
│   └── rate_limit.py            # NEW — slowapi limiter
├── schemas/                     # EXISTING — add per-domain files
│   └── chat.py  conversation.py  document.py
└── scripts/
    ├── build_index.py           # EXISTING — repurposed: embed benchmark corpus → benchmark namespace
    └── seed_admin.py            # NEW — bootstrap first admin user
alembic/                         # NEW — migrations (alembic.ini at backend root)
```

### Structure Rationale

- **`api/` split:** the current single `main.py` won't hold five resource groups cleanly. Split into routers; `main.py` becomes an app factory + lifespan. Keeps the HTTP/API layer boundary intact, just modularised.
- **`auth/`, `db/`, `documents/` as sibling domains to `rag/`:** matches the existing per-concern package style (`llm/`, `rag/`, `schemas/`). Each owns its layer slice.
- **`embeddings/` and `reranking/` separate from each other** even though Voyage serves both: SOLID interface segregation, and it keeps the "swap a vendor" story localized (e.g., move only reranking to Cohere later). The shared Voyage *client* lives on `app.state`; the *providers* are thin adapters.
- **`eval/` isolated:** runs offline / in CI, never on the request path; reads the frozen `benchmark` namespace only.
- **`reranker.py` removed:** the local cross-encoder singleton is deleted (the migration is a deletion per Key Decisions); reranking moves behind the API provider.

---

## Proposed Data Model

```
roles (enum, not a table)         User.role : Enum("admin","user")  default "user"

┌─────────────┐        ┌──────────────────┐        ┌────────────────┐
│   users     │1      *│  conversations    │1      *│   messages      │
├─────────────┤────────├──────────────────┤────────├────────────────┤
│ id (uuid PK)│        │ id (uuid PK)      │        │ id (uuid PK)    │
│ email (uniq)│        │ user_id (FK)      │        │ conversation_id │
│ pw_hash     │        │ title             │        │   (FK)          │
│ role (enum) │        │ created_at        │        │ role            │
│ created_at  │        │ updated_at        │        │  (user/asst)    │
└─────────────┘        └──────────────────┘        │ content (text)  │
                                                    │ sources (jsonb) │
┌──────────────────────────────────────┐           │ created_at      │
│  documents                            │           └────────────────┘
├──────────────────────────────────────┤
│ id (uuid PK)                          │   ── owns Pinecone vectors in
│ filename, content_type, size_bytes    │      namespace "shared_kb" with
│ uploaded_by (FK users.id)             │      ids "{document.id}:{chunk_index}"
│ status (enum: pending|processing|     │
│         ready|failed)                 │   chunk metadata (page, excerpt) lives
│ chunk_count (int, nullable)           │      in Pinecone vector metadata —
│ error (text, nullable)                │      NOT a separate Postgres table
│ created_at, updated_at                │
└──────────────────────────────────────┘
```

**Relationships & decisions:**
- `users 1—* conversations 1—* messages` — standard chat persistence; cascade delete conversations→messages.
- `messages.sources` stored as **JSONB** (the existing `ChatSource` shape: excerpt, score, page_number) so saved chats render the evidence drawer without re-querying Pinecone.
- `role` is an **enum column on `users`**, not a join table — v1 has exactly two roles (RBAC shared-KB model per PROJECT). A `roles` table is YAGNI here.
- **No `chunks` table.** Chunk-level data lives in Pinecone vector metadata. The link from a document to its vectors is the **deterministic id prefix** `{document_id}:{chunk_index}`, so delete = Pinecone delete by id-prefix / metadata filter `{document_id}`. This avoids a second source of truth to keep in sync.
- `documents.status` is the polling target for the async ingestion flow (see flow #2).
- UUID PKs throughout (avoids enumerable integer IDs on a public demo).

---

## Architectural Patterns

### Pattern 1: Provider Protocol + factory (extended to embeddings & reranking)

**What:** New `EmbeddingProvider` and `RerankerProvider` Protocols, each with a `factory.py`, exactly mirroring `llm/provider.py` + `llm/factory.py`.
**When to use:** Every external AI capability that might be swapped per-vendor.
**Trade-offs:** Slight indirection for one current vendor (Voyage); pays off as a clean "single-vendor by config" design story and a localized future swap.

**Example:**
```python
# embeddings/provider.py
from typing import Protocol
class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...

# reranking/provider.py
class RerankerProvider(Protocol):
    def rerank(self, query: str, documents: list[str], top_k: int) -> list[tuple[int, float]]: ...
```

### Pattern 2: Lifespan singletons on `app.state`, injected via `Depends` (fixes both anti-patterns)

**What:** Construct the Pinecone client, Voyage client, the selected LLM/embedding/reranker providers, and the `async_sessionmaker` once in `lifespan`; store on `app.state`; expose via `Depends`.
**When to use:** Any expensive client/connection that must not be rebuilt per request.
**Trade-offs:** Requires the app-factory pattern; eliminates per-request provider construction (current anti-pattern) and import-time settings binding (current anti-pattern in `vector_store.py`).

**Example:**
```python
# main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.engine = create_async_engine(settings.database_url)
    app.state.sessionmaker = async_sessionmaker(app.state.engine, expire_on_commit=False)
    app.state.pinecone = Pinecone(api_key=settings.pinecone_api_key).Index(settings.pinecone_index)
    app.state.llm = create_llm_provider()          # once, not per request
    app.state.embedder = create_embedding_provider()
    yield
    await app.state.engine.dispose()

# api/deps.py
async def get_db_session(request: Request) -> AsyncSession:
    async with request.app.state.sessionmaker() as session:
        yield session
```

### Pattern 3: Dependency-based auth + RBAC

**What:** `get_current_user` decodes the JWT and loads the user; `require_admin` composes it and asserts role. Routes declare what they need.
**When to use:** Every protected endpoint; admin-only document routes.
**Trade-offs:** Centralises authz in reusable dependencies; zero authz logic in handler bodies.

**Example:**
```python
async def get_current_user(token=Depends(oauth2_scheme),
                           db: AsyncSession = Depends(get_db_session)) -> User: ...
async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.admin:
        raise HTTPException(403, "Admin role required")
    return user

@router.post("/api/admin/documents")
async def upload(file: UploadFile, admin: User = Depends(require_admin)): ...
```

### Pattern 4: SSE streaming via `StreamingResponse` + an async-generator over the provider

**What:** The chat route returns `StreamingResponse(media_type="text/event-stream")` driven by `provider.stream_answer()`, yielding `data: {json}\n\n` frames; a final frame carries `sources`.
**When to use:** The token-by-token chat answer.
**Trade-offs:** Requires async provider SDKs and `async def` handlers (the migration). The double newline is mandatory or EventSource drops frames. Persistence happens after the stream completes (accumulate tokens, then write the assistant `message`).

### Pattern 5: Background ingestion with a status lifecycle (no worker infra)

**What:** Upload handler validates + persists a `documents` row (`status=pending`), enqueues `BackgroundTasks`, returns `202` immediately. The task flips to `processing`, runs chunk→embed→upsert, then `ready` (or `failed` + error). Admin UI polls `GET /api/admin/documents`.
**When to use:** Free-tier hosting with no Celery/Redis.
**Trade-offs:** Tied to the web dyno (a restart mid-ingest leaves a stuck `processing` row — mitigate with a timeout/requeue or manual retry endpoint). Acceptable for a portfolio demo; note the limitation in README.

---

## Data Flow

### Flow 1 — Authenticated streaming chat request

```
Browser (Bearer JWT) ── POST /api/chat {question, conversation_id?} ──►
  Depends: rate_limit → get_current_user → get_db_session
    chat_service.answer_questions_stream(question, history):
      query_transformer.rewrite_query (LLM, if follow-up)
      vector_store.query(namespace="shared_kb", embedder.embed_query(q), top_k=15)
      reranker.rerank(q, candidates, top_k=5)
      build_context(...)
      llm.stream_answer(question, context)  ──► async generator
  StreamingResponse: yield "data: {token}\n\n" per chunk
    ... final frame: "data: {sources}\n\n"
  on stream completion: persist user+assistant messages (with sources jsonb)
    into messages under conversation (create conversation if none)
◄── token stream consumed by EventSource/fetch reader in App.jsx
```

History for follow-up rewriting comes from the persisted conversation (or the request), not only client state.

### Flow 2 — Admin document upload + ingestion

```
Admin (Bearer JWT, role=admin) ── POST /api/admin/documents (multipart file) ──►
  Depends: require_admin → get_db_session
    validate file → insert documents row (status=pending) → commit
    background_tasks.add_task(ingest, document_id) → return 202 {document_id, status}
  [background]
    set status=processing
    pdf_loader.load → text_chunker.split
    embedder.embed_documents(chunks)            # Voyage, with retry/backoff
    vector_store.upsert(namespace="shared_kb",
        vectors=[("{document_id}:{i}", vec, {document_id, page, excerpt})])
    set status=ready, chunk_count=N   (on error: status=failed, error=...)
◄── Admin polls GET /api/admin/documents → sees status transition
DELETE /api/admin/documents/{id} → Pinecone delete by metadata {document_id}
                                  → delete documents row
```

### Flow 3 — Evaluation run (offline / CI, isolated from user data)

```
scripts/build_index.py (one-time / CI) ──► embed student_manual ──►
    Pinecone upsert namespace="benchmark"   (FROZEN — never written by uploads)

eval/run_eval.py ──►
  load golden_set (fixed Q/A)
  for each Q: retrieve from namespace="benchmark" → rerank → generate
  ragas.evaluate(faithfulness, answer_relevancy, context_precision/recall)
      judge LLM = Groq (free)
  ──► metrics report (stdout/JSON → README, CI artifact)
```

The namespace split is the structural guarantee for PROJECT's eval-integrity constraint: user uploads land in `shared_kb`; eval reads only `benchmark`.

### State Management

```
Server:  app.state singletons (engine, sessionmaker, pinecone index,
         llm/embed/rerank providers) ── created in lifespan, injected via Depends
         Per-request AsyncSession (Depends, auto-closed)
         settings singleton (read INSIDE function/lifespan bodies, never at import)
Client:  auth token (memory + storage), conversation list/messages from API,
         streaming buffer for in-flight answer
```

---

## Suggested Build Order (dependency keystones)

| Step | Phase intent | Why this order | Touches / depends on |
|------|--------------|----------------|----------------------|
| 0 | **Sync→async migration + app factory** | Keystone. Async DB + streaming both require `async def`. Do once, up front. Convert handlers, add lifespan/app-factory, move settings reads into bodies. | All routes; fixes anti-patterns #1/#2 |
| 1 | **Postgres + `db/` + Alembic + structured logging** | Foundation for users/chat/docs. Already needs async (step 0). | SQLAlchemy async, asyncpg, Alembic, structlog |
| 2 | **Auth + RBAC (`auth/`, `api/deps.py`)** | Everything user/admin-scoped depends on identity. `Depends` backbone established here. | PyJWT, pwdlib, db (step 1) |
| 3 | **Early hosted authed slice (Render + Vercel + Neon)** | De-risk free-tier deploy early (Key Decision: deploy ≈ phase 2–3, not last). Ship login + existing chat hosted. | steps 0–2; CORS, env wiring |
| 4 | **Pinecone + Voyage migration; delete FAISS/ST/cross-encoder** | Swap retrieval substrate behind the new `embeddings/`+`reranking/` providers; rebuild benchmark namespace. | `vector_store`, `embeddings/`, `reranking/`, scripts |
| 5 | **Multi-document ingestion (`documents/`, admin routes)** | Needs Pinecone (4) + auth/admin (2) + BackgroundTasks + status model. | `documents/`, Pinecone `shared_kb` |
| 6 | **Chat persistence + SSE streaming** | Needs async (0), db (1), Pinecone query path (4), provider `stream_answer()`. | `conversations`, `messages`, `llm/` stream |
| 7 | **RAGAS eval harness** | Needs the migrated pipeline (4) querying the frozen `benchmark` namespace. | `eval/`, Groq judge |
| 8 | **Ops/polish** | Docker (image now slim post-deletion), GitHub Actions CI, pytest suite, slowapi rate limits, Sentry, README. | cross-cutting |

> **Critical sequencing notes:** (a) Step 0 must precede 1 — do NOT build a sync DB layer then re-async it. (b) Namespace isolation (2 → `benchmark` vs `shared_kb`) must exist before step 5 ships uploads, or eval integrity is silently violated. (c) Pinecone index `dimension=1024` / `metric=cosine` is fixed at creation (step 4) — locking it wrong forces a full re-embed.

---

## Scaling Considerations

This is a single-instance free-tier portfolio demo. The honest ceiling is the **free-tier quotas**, not user count.

| Scale | Architecture adjustments |
|-------|--------------------------|
| Demo / recruiters (realistic) | Single Render dyno. Real limits: Pinecone Read Units/month, Voyage token budget, Render cold start. Mitigate with slowapi per-user daily cap + uptime ping. |
| If it grew (hypothetical 1k+ users) | Move ingestion to a real worker (Celery/RQ + Redis); add a paid always-on host; connection pooling tuned for Neon; cache query embeddings. |
| Beyond | Out of scope — don't build for it now. |

### Scaling Priorities (what breaks first)

1. **Free-tier quotas** (Pinecone RU, Voyage tokens) — protect with rate limiting + daily caps (already a PROJECT requirement).
2. **Render cold start** — uptime ping or accept "first load ~1 min" README caveat.
3. **BackgroundTasks coupling to the web dyno** — only matters with concurrent/large ingests; move to a worker if/when needed.

---

## Anti-Patterns (specific to these additions)

### Anti-Pattern 1: Adding async DB on top of sync handlers
**What people do:** Keep `def` handlers and call `await session...` via workarounds.
**Why it's wrong:** Async SQLAlchemy/asyncpg need an event loop; sync handlers run in a thread pool — you get blocked loops or `RuntimeError`s, and streaming can't work.
**Do this instead:** Migrate handlers to `async def` first (build step 0).

### Anti-Pattern 2: Writing uploaded docs into the eval namespace
**What people do:** One Pinecone namespace for everything.
**Why it's wrong:** User uploads then change RAGAS scores → eval metrics are meaningless (violates PROJECT eval-integrity constraint).
**Do this instead:** `benchmark` (frozen) vs `shared_kb` (uploads); eval reads only `benchmark`.

### Anti-Pattern 3: A separate `chunks` table mirroring Pinecone
**What people do:** Store every chunk's vector-id in Postgres to support deletion.
**Why it's wrong:** Two sources of truth to keep in sync; extra writes; drift risk.
**Do this instead:** Deterministic ids `{document_id}:{chunk_index}` + `document_id` in vector metadata → delete by filter; Postgres holds only document-level rows.

### Anti-Pattern 4: Provider/client constructed per request (carried over)
**What people do:** `create_llm_provider()` / new Pinecone client inside the handler.
**Why it's wrong:** Wastes connection setup; the codebase map flags exactly this.
**Do this instead:** Lifespan singletons on `app.state`, injected via `Depends`.

### Anti-Pattern 5: Blocking ingestion in the request
**What people do:** chunk→embed→upsert synchronously inside the upload handler.
**Why it's wrong:** Voyage is rate-limited; large PDFs time out the request.
**Do this instead:** `BackgroundTasks` + `documents.status` polling.

---

## Integration Points

### External Services

| Service | Integration pattern | Notes |
|---------|---------------------|-------|
| Pinecone | Client on `app.state`; namespace-scoped query/upsert/delete | dimension=1024, metric=cosine fixed at creation; two namespaces |
| Voyage AI | Shared client on `app.state`, wrapped by `embeddings/` + `reranking/` providers | retry/backoff for rate limits; tokens shared across embed+rerank |
| Neon Postgres | Async engine + `async_sessionmaker` in lifespan; per-request session via `Depends` | autosuspends ~5 min; warm a connection on startup |
| Groq/Anthropic/Gemini | Existing `llm/` providers; add `stream_answer()`; Groq doubles as eval judge | async SDK clients for streaming |
| Render / Vercel | Render hosts API (CORS → Vercel domain); Vercel serves React with `VITE_API_BASE_URL` | Render cold start caveat |
| Sentry | `sentry-sdk[fastapi]` init in app factory; structlog ERROR routing | sample events to protect free quota |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| api/routers ↔ domain services | direct async function calls, deps injected | routers stay thin; no business logic in handlers |
| rag/ ↔ embeddings/ + reranking/ | via Protocol abstractions (factory-selected) | mirrors rag/ ↔ llm/ today |
| documents/ ↔ Pinecone (`shared_kb`) | upsert/delete by deterministic id | links to `documents` rows via id prefix |
| eval/ ↔ Pinecone (`benchmark`) | read-only query | never writes; isolation guarantee |
| services ↔ db/ | `AsyncSession` via `Depends(get_db_session)` | session lifecycle owned by the dependency |

---

## Sources

- `.planning/codebase/ARCHITECTURE.md`, `STRUCTURE.md`, `CONVENTIONS.md` — existing layers, anti-patterns, conventions (HIGH — primary)
- `.planning/PROJECT.md` — constraints, Key Decisions (eval integrity, deploy-early, migration-as-deletion, RBAC shared-KB) (HIGH — primary)
- `.planning/research/STACK.md` — locked stack: Voyage 1024/rerank-2.5, Pinecone serverless 1024/cosine, SQLAlchemy 2.x async + asyncpg + Alembic, PyJWT + pwdlib, StreamingResponse SSE, async-migration dependency (HIGH)
- FastAPI patterns: app factory + lifespan, `Depends` DI, `StreamingResponse` SSE, `BackgroundTasks` (HIGH — established framework patterns)

---
*Architecture research for: production RAG platform — brownfield structural additions*
*Researched: 2026-06-10*
