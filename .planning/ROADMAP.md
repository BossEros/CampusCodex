# Roadmap: RAG Knowledge Platform

## Overview

This milestone evolves a working single-PDF, locally-embedded FAISS RAG chatbot into a production-grade, multi-user platform: managed vectors (Pinecone), API embeddings + reranking (Voyage), Postgres-backed auth/RBAC/chat history, admin document management, token-by-token streaming, a RAGAS evaluation pipeline, and a clickable free-tier hosted demo. The journey is a **vertical MVP**: each phase ends in something deployable or demoable end-to-end, building up the running system rather than completing horizontal technical layers. The async foundation comes first (everything multi-user and streaming depends on it), the retrieval migration to the slim API-based stack lands before the first public deploy (so the first hosted slice is both small enough for the free tier and demos the core value of cited answers), and eval/multi-doc/streaming layer onto the running deployment.

## Mode

**PROJECT_MODE = mvp (Vertical MVP).** Every phase delivers an end-to-end, deployable/demoable slice — not a horizontal technical layer.

## Sequencing Resolution (deploy-early vs. slim-stack tension)

PROJECT.md's Key Decision targets a live authed slice early (~phase 2–3) to de-risk free-tier hosting. The research synthesizer flagged that deploying the *existing* chat early would still carry FAISS + sentence-transformers + torch and risk OOM on Render's ~512MB free tier — and an auth-only deploy doesn't escape that, because the heavy deps remain in the image until RAG-07 deletes them.

**Resolution (per hard constraint #5):** sequence the Pinecone/Voyage migration (Phase 4) **before** the first hosted real-chat slice (Phase 5). The deploy-early target moves from ~phase 2–3 to **phase 5 (post-migration)**. This is a deliberate, pre-accepted tradeoff: it guarantees the first deploy runs on the already-slim API-based stack AND demonstrates the core value (cited RAG answers) end-to-end, rather than shipping a dead auth-only slice that still risks the image-size footgun. No separate ultra-early plumbing-only deploy phase is added (that would reintroduce the dead-slice problem and push past the standard granularity band).

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Async Foundation & App Factory** - Convert to async handlers + lifespan singletons, fixing both flagged anti-patterns
- [ ] **Phase 2: Postgres Persistence & Structured Logging** - Async SQLAlchemy + Alembic + JSON logging foundation for all multi-user data
- [ ] **Phase 3: Auth & RBAC** - JWT email/password auth with admin/user roles enforced at the dependency layer
- [ ] **Phase 4: Pinecone + Voyage Migration** - Replace FAISS/local models with managed vectors + API embed/rerank; lock namespaces; delete heavy deps
- [ ] **Phase 5: First Hosted Authed Slice** - Real working cited RAG chat, authed, live on Render + Vercel + Neon
- [ ] **Phase 6: Multi-Document Ingestion & Admin Management** - Admin upload/list/delete/re-index with async ingestion and multi-doc retrieval
- [ ] **Phase 7: Chat Persistence & SSE Streaming** - Saved per-user conversations plus token-by-token streamed answers
- [ ] **Phase 8: RAGAS Evaluation Harness** - Repeatable measurable answer-quality scoring over the frozen benchmark, surfaced in the README
- [ ] **Phase 9: Ops, CI/CD & Demo Polish** - Docker, GitHub Actions, test suite, error tracking, seeded demo, polished docs

## Phase Details

### Phase 1: Async Foundation & App Factory
**Goal**: The backend runs on an async foundation with an app-factory + lifespan and lifespan-initialized singletons, so async DB, streaming, and non-blocking provider calls become possible — and the two flagged anti-patterns are fixed as a side effect.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: CORE-01, CORE-02, CORE-03, OPS-07
**Success Criteria** (what must be TRUE):
  1. Every route handler is `async def` and the app boots via an app-factory + `lifespan` with shared client singletons on `app.state`
  2. The LLM provider is constructed exactly once at startup, not per request (verifiable: a request does not re-instantiate the provider)
  3. Settings are read inside function/lifespan bodies — no settings value is bound at module import time
  4. The existing single-doc chat endpoint still answers correctly after the migration (no regression), running async
  5. `.env` is gitignored and a `.env.example` with placeholder values is committed; no real secret is tracked from the first commit of this milestone
**Plans**: TBD

### Phase 2: Postgres Persistence & Structured Logging
**Goal**: A Postgres-backed async persistence layer exists (users, conversations, messages, document metadata) with migrations and request-correlated JSON logging — the keystone everything multi-user depends on.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: OPS-01
**Success Criteria** (what must be TRUE):
  1. The app connects to Postgres via a lifespan-built async engine + `async_sessionmaker`; sessions are provided per-request via a dependency (never bound at import)
  2. Alembic migrations create the schema (users, conversations, messages, documents) and run cleanly from empty
  3. The async engine is configured for Neon's autosuspend (`pool_pre_ping=True`, conservative `pool_recycle`) so the first request after idle succeeds
  4. Each request emits structured JSON logs carrying a request/correlation id across the API path
**Plans**: TBD

### Phase 3: Auth & RBAC
**Goal**: Users can securely create accounts and sign in, sessions persist and can be revoked, and admin-only capabilities are enforced server-side at the dependency layer.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05
**Success Criteria** (what must be TRUE):
  1. A user can sign up with email + password (hashed with argon2/bcrypt via pwdlib) and log in to receive a JWT access token + refresh token
  2. A session persists across browser refresh via token refresh, and logging out invalidates/rotates the refresh token
  3. JWT decode pins `algorithms=["HS256"]` and rejects an `alg:none` token
  4. An `admin` route called by a `user` returns 403, and a user cannot fetch another user's data (cross-user request returns 403/404) — enforced in a dependency/data layer, not the UI
**Plans**: TBD
**UI hint**: yes

### Phase 4: Pinecone + Voyage Migration
**Goal**: The retrieval substrate is swapped to the managed, API-based slim stack — Pinecone vectors + Voyage embeddings/reranking behind new provider abstractions — the heavy local ML deps are deleted, and the eval namespace is isolated at index creation.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: RAG-01, RAG-02, RAG-03, RAG-04, RAG-05, RAG-06, RAG-07, EVAL-01
**Success Criteria** (what must be TRUE):
  1. Queries are served from a Pinecone serverless index (1024-dim, cosine) using Voyage embeddings (`voyage-3.5`) and Voyage reranking (`rerank-2.5`); the two-stage retrieve→rerank pipeline is preserved
  2. Answers still cite the source document title + page through the new pipeline
  3. `faiss-cpu`, `sentence-transformers`, and `torch` are removed from the backend image (the free-tier hosting win)
  4. Embedding-provider and reranker-provider abstractions exist, mirroring the `LlmProvider` Protocol + factory pattern, with sync Voyage calls wrapped in `asyncio.to_thread` (no event-loop blocking under concurrency)
  5. Two Pinecone namespaces exist — a frozen `benchmark` (re-embedded `student_manual`) and `shared_kb` — created at index time; eval reads only `benchmark`
**Plans**: TBD

### Phase 5: First Hosted Authed Slice
**Goal**: A recruiter can open a public URL, log in, and get real source-cited RAG answers from the deployed system running on the slim API-based stack — the core value, live, with the public demo protected from cost/abuse.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: SHIP-01, SHIP-02, OPS-03
**Success Criteria** (what must be TRUE):
  1. The system is reachable at a public URL (Render API + Vercel frontend + Neon Postgres) and a logged-in user gets a real cited answer end-to-end on the slim stack
  2. A seeded demo account + sensible empty states let a recruiter use it within seconds
  3. Per-user rate limiting / daily cap protects the demo, keyed on authenticated user id (not the Render proxy IP) so two different users get independent limits on the deployed instance
  4. CORS is configured to the Vercel origin and the first request after Neon idle succeeds on the deployed DB
**Plans**: TBD
**UI hint**: yes

### Phase 6: Multi-Document Ingestion & Admin Management
**Goal**: An admin can manage a real shared knowledge base — upload, list, delete, and re-index documents with an async ingestion lifecycle — and users can query across multiple documents with answers attributed to the correct source.
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: DOC-01, DOC-02, DOC-03, DOC-04, DOC-05, DOC-06
**Success Criteria** (what must be TRUE):
  1. An admin can upload a PDF; ingestion runs asynchronously with a visible status lifecycle (queued → processing → indexed → failed) the admin can poll/list
  2. An admin can delete a document (removing its vectors from Pinecone `shared_kb`) and can re-index a document
  3. A user can query across multiple documents and answers are attributed to the correct source document
  4. Uploads write only to `shared_kb` and never to the `benchmark` namespace (eval integrity preserved); the Voyage provider uses backoff/batching so large uploads don't 429 mid-ingest
**Plans**: TBD
**UI hint**: yes

### Phase 7: Chat Persistence & SSE Streaming
**Goal**: Authenticated users have a real chat experience — conversations are saved, listable, resumable, and deletable, and answers stream token-by-token both locally and on the deployed URL.
**Mode:** mvp
**Depends on**: Phase 6
**Requirements**: CHAT-01, CHAT-02, CHAT-03, CHAT-04, CHAT-05
**Success Criteria** (what must be TRUE):
  1. A user's conversations are persisted server-side, scoped to the authenticated user, and they can list, resume (with full message history), and delete their conversations
  2. A user cannot list or resume another user's conversation (filtered by `user_id` server-side)
  3. Answers stream token-by-token to the UI via SSE, with sources delivered in a final frame
  4. Streaming is verified token-by-token against the deployed Render URL (not just localhost) — correct `data: ...\n\n` framing, `text/event-stream`, no proxy buffering
**Plans**: TBD
**UI hint**: yes

### Phase 8: RAGAS Evaluation Harness
**Goal**: Answer quality is measurably good and reproducible — a golden Q/A set scored against the frozen benchmark with RAGAS metrics via a repeatable command, surfaced in the README as the headline credibility signal.
**Mode:** mvp
**Depends on**: Phase 7
**Requirements**: EVAL-02, EVAL-03, EVAL-04
**Success Criteria** (what must be TRUE):
  1. A golden Q/A test set exists for the `student_manual` benchmark corpus
  2. A single repeatable command computes RAGAS metrics (faithfulness, response relevancy, context precision, context recall) over the `benchmark` namespace only and produces a metrics report
  3. The judge LLM is pinned (Groq, temperature 0 where supported) so scores are interpretable, with backoff for rate limits
  4. Eval results are surfaced in the README (report and/or badge) alongside judge model + date + corpus context
**Plans**: TBD

### Phase 9: Ops, CI/CD & Demo Polish
**Goal**: The production story is complete and the demo is recruiter-ready — containerized, CI-gated, tested, error-tracked, with cold-start mitigation and polished docs that present the system for hiring managers.
**Mode:** mvp
**Depends on**: Phase 8
**Requirements**: OPS-02, OPS-04, OPS-05, OPS-06, SHIP-03
**Success Criteria** (what must be TRUE):
  1. Docker + docker-compose run backend, frontend, and database locally with parity; the backend image is slim post-deletion
  2. GitHub Actions runs lint + tests + build on PR (with a gitleaks secret scan) and deploys on merge to main
  3. An automated pytest suite (unit + API integration) runs against a configured test database, including a concurrency check (no async loop blocking) and a cross-user authorization test
  4. Error tracking (Sentry-style, sampled to protect free quota) captures backend errors, and the cold-start window shows a clear "waking up" state rather than an error
  5. A polished README + architecture docs present the system for recruiters
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Async Foundation & App Factory | 0/TBD | Not started | - |
| 2. Postgres Persistence & Structured Logging | 0/TBD | Not started | - |
| 3. Auth & RBAC | 0/TBD | Not started | - |
| 4. Pinecone + Voyage Migration | 0/TBD | Not started | - |
| 5. First Hosted Authed Slice | 0/TBD | Not started | - |
| 6. Multi-Document Ingestion & Admin Management | 0/TBD | Not started | - |
| 7. Chat Persistence & SSE Streaming | 0/TBD | Not started | - |
| 8. RAGAS Evaluation Harness | 0/TBD | Not started | - |
| 9. Ops, CI/CD & Demo Polish | 0/TBD | Not started | - |
