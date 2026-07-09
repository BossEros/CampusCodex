# Requirements: RAG Knowledge Platform

**Defined:** 2026-06-10
**Core Value:** Trustworthy, source-cited answers from a managed document knowledge base — answer quality that is *measurably* good, served through a secure, deployable, real-world system.

> Brownfield production milestone. The existing single-PDF RAG pipeline (retrieve→rerank→generate, source citations, follow-up rewriting, pluggable LLM providers, React chat UI) is already **Validated** (see PROJECT.md) and is the foundation these requirements build on.

## v1 Requirements

Requirements for this milestone. Each maps to a roadmap phase.

### Core / Async Foundation

- [ ] **CORE-01**: Backend runs on an async foundation — route handlers are `async def`, app uses an app-factory + lifespan with shared client singletons (LLM/embeddings/reranker/Pinecone, DB session maker) — enabling async DB, streaming, and non-blocking provider calls
- [ ] **CORE-02**: LLM provider is instantiated once (at startup/lifespan), not per request (fixes flagged anti-pattern)
- [ ] **CORE-03**: Settings are read inside function bodies, not bound at import time (fixes flagged anti-pattern in `vector_store.py`)

### Authentication & Access (AUTH)

- [ ] **AUTH-01**: User can sign up with email and password (passwords hashed with argon2/bcrypt via pwdlib)
- [ ] **AUTH-02**: User can log in and receive a JWT access token + refresh token (signed with PyJWT)
- [ ] **AUTH-03**: User session persists across browser refresh via token refresh
- [ ] **AUTH-04**: User can log out (refresh token invalidated/rotated)
- [ ] **AUTH-05**: Role-based access control enforced at the route/dependency layer — `admin` (manage documents) vs `user` (query, own history)

### Retrieval & Vector Migration (RAG)

- [ ] **RAG-01**: Vectors are served from Pinecone serverless (1024-dim, cosine); local FAISS is removed
- [ ] **RAG-02**: Embeddings are generated via an API provider (Voyage `voyage-3.5`); local sentence-transformers embeddings are removed
- [ ] **RAG-03**: Reranking is performed via an API provider (Voyage `rerank-2.5`); the local cross-encoder is removed
- [ ] **RAG-04**: Embedding-provider and reranker-provider abstractions exist, mirroring the `LlmProvider` Protocol + factory pattern
- [ ] **RAG-05**: The two-stage retrieve→rerank pipeline is preserved through the migration
- [ ] **RAG-06**: Answers cite the source document title + page, preserved through the new pipeline
- [ ] **RAG-07**: Heavy local ML dependencies (faiss-cpu, sentence-transformers, torch) are removed from the backend image

### Document Management (DOC)

- [ ] **DOC-01**: Admin can upload a PDF document to the shared knowledge base
- [ ] **DOC-02**: Document ingestion runs asynchronously with a status lifecycle (queued → processing → indexed → failed)
- [ ] **DOC-03**: Admin can list all documents with their ingestion status
- [ ] **DOC-04**: Admin can delete a document, which removes its vectors from Pinecone
- [ ] **DOC-05**: Admin can re-index a document
- [ ] **DOC-06**: Users can query across multiple documents, with answers attributed to the correct source document

### Chat Experience (CHAT)

- [ ] **CHAT-01**: User's conversations are persisted server-side (Postgres), scoped to the authenticated user
- [ ] **CHAT-02**: User can list their past conversations
- [ ] **CHAT-03**: User can resume a past conversation with full message history
- [ ] **CHAT-04**: User can delete a conversation
- [ ] **CHAT-05**: Answers stream to the UI token-by-token (SSE)

### Evaluation (EVAL)

- [ ] **EVAL-01**: A frozen benchmark corpus (`student_manual`) lives in an isolated Pinecone namespace used only by the eval pipeline; user uploads cannot affect it
- [ ] **EVAL-02**: A golden Q/A test set exists for the benchmark corpus
- [ ] **EVAL-03**: A repeatable eval command computes RAGAS metrics (faithfulness, response relevancy, context precision, context recall) and produces a metrics report
- [ ] **EVAL-04**: Eval results are surfaced in the README (report and/or badge)

### Production Engineering (OPS)

- [ ] **OPS-03**: Rate limiting / per-user daily cap protects the public demo (keyed on user id for authed, IP for anon)
- [ ] **OPS-04**: Automated test suite (pytest: unit + API integration) with a configured runner and a test database
- [ ] **OPS-06**: CI/CD via GitHub Actions (lint + test + build on PR; deploy on merge to main)
- [ ] **OPS-07**: Secrets hygiene — no keys in the repo, `.gitignore` + `.env.example` correct from the first relevant commit

### Delivery (SHIP)

- [ ] **SHIP-01**: A live hosted demo is reachable at a public URL (Render API + Vercel frontend + Neon Postgres)
- [ ] **SHIP-02**: A seeded demo account + sensible empty states let a recruiter use it within seconds
- [ ] **SHIP-03**: Polished README + architecture docs present the system for recruiters

## v2 Requirements

Acknowledged but deferred — strong near-term follow-ons, not in the current roadmap.

### Evaluation+

- **EVAL-05**: CI eval *gate* with thresholds (fail build if faithfulness drops) — start report-only, then gate once metric variance is understood

### Ingestion+

- **DOC-07**: Additional file formats (docx, pptx, html) beyond PDF

### Observability

- **OBS-01**: Tracing dashboard (Langfuse/LangSmith) paired with the eval pipeline

## Out of Scope

Explicitly excluded for this milestone. Documented to prevent scope creep and give a defensible "why not."

| Feature | Reason |
|---------|--------|
| OAuth / social login (Google) | Self-built JWT email/password proves the backend security fundamentals first |
| Per-user private + shared document collections | Shared-KB + RBAC is the v1 multi-tenancy model; private/shared collections are a much larger data-model + authz surface |
| Managed auth providers (Clerk/Auth0/Supabase Auth) | Outsources exactly the skill a backend portfolio must demonstrate |
| Self-hosting embedding/reranker models | Contradicts the free-tier hosting constraint — heavy local models are the thing being removed |
| Custom-built vector store | Reinventing a solved problem; Pinecone is the recognizable managed choice |
| Document versioning / diffing | Significant data-model complexity for little demo value; delete + re-index suffices |
| Real-time collaborative chat | Websocket/CRDT complexity with no portfolio payoff |
| Agentic multi-tool orchestration / web search | Massive scope, hard to evaluate, off-mission for a measurable document-QA portfolio |
| Admin usage analytics dashboard | Observability-adjacent scope creep; rate-limit counters + logs suffice for v1 |

## Traceability

Each v1 requirement maps to exactly one phase. See ROADMAP.md for phase details.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CORE-01 | Phase 1 | Pending |
| CORE-02 | Phase 1 | Pending |
| CORE-03 | Phase 1 | Pending |
| OPS-07 | Phase 1 | Pending |
| AUTH-01 | Phase 3 | Pending |
| AUTH-02 | Phase 3 | Pending |
| AUTH-03 | Phase 3 | Pending |
| AUTH-04 | Phase 3 | Pending |
| AUTH-05 | Phase 3 | Pending |
| RAG-01 | Phase 4 | Pending |
| RAG-02 | Phase 4 | Pending |
| RAG-03 | Phase 4 | Pending |
| RAG-04 | Phase 4 | Pending |
| RAG-05 | Phase 4 | Pending |
| RAG-06 | Phase 4 | Pending |
| RAG-07 | Phase 4 | Pending |
| EVAL-01 | Phase 4 | Pending |
| SHIP-01 | Phase 5 | Pending |
| SHIP-02 | Phase 5 | Pending |
| OPS-03 | Phase 5 | Pending |
| DOC-01 | Phase 6 | Pending |
| DOC-02 | Phase 6 | Pending |
| DOC-03 | Phase 6 | Pending |
| DOC-04 | Phase 6 | Pending |
| DOC-05 | Phase 6 | Pending |
| DOC-06 | Phase 6 | Pending |
| CHAT-01 | Phase 7 | Pending |
| CHAT-02 | Phase 7 | Pending |
| CHAT-03 | Phase 7 | Pending |
| CHAT-04 | Phase 7 | Pending |
| CHAT-05 | Phase 7 | Pending |
| EVAL-02 | Phase 8 | Pending |
| EVAL-03 | Phase 8 | Pending |
| EVAL-04 | Phase 8 | Pending |
| OPS-04 | Phase 9 | Pending |
| OPS-06 | Phase 9 | Pending |
| SHIP-03 | Phase 9 | Pending |

**Coverage:**
- v1 requirements: 37 total
- Mapped to phases: 37 (100%)
- Unmapped: 0

> Note: OPS-01 (structured JSON logging), OPS-02 (Sentry error tracking), and OPS-05 (Docker + docker-compose) were removed on 2026-06-14 as unnecessary complexity for a portfolio demo. Final count is 37 (CORE 3 + AUTH 5 + RAG 7 + DOC 6 + CHAT 5 + EVAL 4 + OPS 4 + SHIP 3).

---
*Requirements defined: 2026-06-10*
*Last updated: 2026-06-10 after roadmap creation (traceability populated; count corrected 37→40)*
