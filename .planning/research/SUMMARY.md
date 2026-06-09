# Project Research Summary

**Project:** RAG Knowledge Platform
**Domain:** Production multi-user RAG / document-QA platform (hosted, authed, evaluated) — brownfield additions to an existing FastAPI + React single-doc RAG app
**Researched:** 2026-06-10
**Confidence:** HIGH

## Executive Summary

This milestone turns a working single-PDF, locally-embedded FAISS RAG chatbot into a production-grade, multi-user platform: managed vectors (Pinecone), API embeddings + reranking (Voyage AI), Postgres-backed auth/RBAC/chat history, admin document management, token-by-token streaming, a RAGAS evaluation pipeline, and a clickable free-tier hosted demo. The guiding principle from PROJECT.md is **extend, don't rewrite** — reuse the proven `LlmProvider` Protocol+factory pattern for the new embedding and reranking providers, keep the layered architecture, and fix the two flagged anti-patterns (per-request provider instantiation, import-time settings binding) as a natural side effect of the work.

All four research dimensions converged on the same load-bearing conclusion: **the sync→async migration is the foundational first step, not part of the streaming phase.** STACK flagged it as a hard dependency (async SQLAlchemy + asyncpg + SSE all require `async def`); ARCHITECTURE made it explicit build step 0; PITFALLS raised it to Critical #3/#4 (a sync Voyage call inside `async def` re-blocks the event loop and silently undoes the migration); and FEATURES gated streaming and the entire async DB layer on it. Doing the Postgres layer on top of sync handlers and re-asyncing later is rework — async comes first. The second convergent conclusion is **eval integrity via Pinecone namespace isolation**: a frozen `benchmark` namespace (the canonical `student_manual` corpus, eval-only, never written by uploads) separate from `shared_kb` (admin uploads, user queries). This is the structural guarantee for the PROJECT constraint that uploads must never move eval scores — and it must exist before uploads ship, or eval integrity is silently violated.

The dominant risk theme is **free-tier footguns that only appear when deployed**: Render cold starts (~1 min after 15-min idle), Neon autosuspend killing pooled connections (needs `pool_pre_ping`), slowapi keying on the proxy IP instead of the user (defeats the per-user cap), and SSE buffering through Render's static-site rewrite. Mitigation is to **deploy a thin authed slice early** (Key Decision: ~phase 2-3, not last) so these surface on real infrastructure before full feature build-out. Vendor decisions are locked and defensible: single-vendor Voyage (`voyage-3.5` @ 1024 dims + `rerank-2.5`) for its 200M free tokens (Cohere's trial caps at ~1k calls/month — one recruiter session exhausts it); Pinecone at 1024/cosine fixed at index creation (no migration from the old 384-dim local vectors — a full re-embed is required); and PyJWT + pwdlib for auth (python-jose and passlib are abandoned/broken).

## Key Findings

### Recommended Stack

The stack is API-first to fit free-tier hosting: the heavy local ML stack (FAISS + sentence-transformers + local cross-encoder + torch) is **deleted**, not migrated — the free-tier image-size win only materializes once those leave the image. Versions were verified live against PyPI on the research date (HIGH); a few vendor free-tier numbers are MEDIUM (re-verify at signup). See `.planning/research/STACK.md` for full detail.

**Core technologies:**
- **Pinecone** (`pinecone` SDK v5+): managed vector store replacing FAISS — recruiter-recognizable, 2GB free serverless tier. `dimension=1024` + `metric=cosine` locked at creation.
- **Voyage AI** (`voyageai` 0.4.0): single vendor for embeddings (`voyage-3.5` @ 1024 dims, Matryoshka) + reranking (`rerank-2.5`) — 200M free tokens vs Cohere's ~1k calls/month cap.
- **SQLAlchemy 2.x async + asyncpg + Alembic**: async ORM for users/roles/conversations/messages/doc metadata — first-class async, industry standard.
- **PyJWT 2.13 + pwdlib[argon2,bcrypt] 0.3.0**: JWT + password hashing — python-jose is abandoned, passlib breaks on bcrypt 5.x; these are FastAPI's current documented path.
- **Neon** (Postgres), **Render** (API), **Vercel** (frontend): the only no-credit-card free-tier topology in 2026.
- **ragas 0.4.x + structlog + sentry-sdk + slowapi + pytest/pytest-asyncio/httpx**: eval, structured logging, error capture, rate limiting, and the (currently missing) test runner.

### Expected Features

The feature set is pre-defined in PROJECT.md; FEATURES.md maps it to table stakes vs differentiators and records dependencies for ordering. "Table stakes" = without it the system doesn't read as production-grade to a hiring manager. See `.planning/research/FEATURES.md`.

**Must have (table stakes):**
- JWT email/password auth + RBAC (admin/user) — "production multi-user" is meaningless without it
- Postgres persistence (users, roles, conversations, messages, doc metadata) — the keystone; gates almost everything multi-user
- Admin document management (upload → ingestion status → list → delete → re-index) — the "managed" in managed KB
- Multi-document retrieval with per-document citations — replaces the hardcoded single PDF
- Streaming answers, chat history persistence, rate limiting/daily cap, pytest suite, Docker/compose, CI/CD, structured logging, live hosted demo + seeded account, polished README

**Should have (competitive differentiators):**
- **RAGAS eval pipeline + golden Q/A set on the fixed benchmark corpus** — the headline differentiator; measurable answer quality is the strongest hire signal and is rare in portfolios
- Eval results surfaced as a README report/badge (CI gate is a stretch — judge variance makes hard thresholds flaky; start report-only)
- Embedding + reranker provider abstractions mirroring `LlmProvider` — the clean DRY/SOLID design narrative

**Defer (v2+):**
- Observability/tracing dashboards (Langfuse/LangSmith), OAuth/social login, per-user private/shared collections, managed auth providers, additional file formats, eval CI gate with thresholds

### Architecture Approach

Extend the existing layered `backend/app/` design: split the monolithic `main.py` into an app factory + lifespan + `api/routers/`, add sibling domains (`auth/`, `db/`, `documents/`, `embeddings/`, `reranking/`, `eval/`) that mirror the existing per-concern package style. `Depends()` becomes the DI backbone (auth, per-request `AsyncSession`, RBAC gates, rate limiting). Expensive clients (Pinecone, Voyage, LLM providers, `async_sessionmaker`) are lifespan-initialized singletons on `app.state` — this single change fixes both flagged anti-patterns. See `.planning/research/ARCHITECTURE.md`.

**Major components:**
1. **`api/routers/*` + `api/deps.py`** — thin async HTTP layer; shared `Depends` (`get_db_session`, `get_current_user`, `require_admin`, `rate_limit`)
2. **`auth/` + `db/`** — pwdlib/PyJWT security; SQLAlchemy 2.x async models, session factory, Alembic migrations
3. **`embeddings/` + `reranking/`** — Protocol+factory adapters over a shared Voyage client (mirrors `llm/`)
4. **`documents/ingestion_service`** — chunk→embed→upsert to `shared_kb` via `BackgroundTasks` with a `documents.status` lifecycle (no Celery/Redis on free tier)
5. **`eval/`** — offline/CI RAGAS harness reading **only** the frozen `benchmark` namespace
6. **Data layer** — Postgres (Neon) for relational data + Pinecone (two namespaces: `benchmark`, `shared_kb`); deterministic vector IDs `{document_id}:{chunk_index}` mean no separate `chunks` table

### Critical Pitfalls

Top items from `.planning/research/PITFALLS.md` (13 documented, each hooked to a concrete codebase concern or chosen stack component):

1. **Eval/KB contamination** — uploads pollute the benchmark → RAGAS scores drift. Avoid: dedicated frozen `benchmark` namespace; eval is its only reader; make namespace a required, non-defaulted provider argument.
2. **Pinecone dimension lock-in + 384→1024 re-embed** — dim/metric fixed at creation, no migration path. Avoid: lock 1024/cosine up front; assert `len(embedding) == index.dimension` before upsert; re-embed benchmark as a one-time scripted step.
3. **Async migration regression** — `voyageai.Client` is **synchronous**; calling it inside `async def` re-blocks the loop. Avoid: wrap sync calls in `asyncio.to_thread`; use async LLM SDKs; add a concurrency load test that fails on linear latency scaling.
4. **Neon autosuspend kills pooled connections** — first request after 5-min idle 500s. Avoid: `pool_pre_ping=True` + conservative `pool_recycle`; warm a connection on startup.
5. **Multi-tenant data leakage (IDOR)** — conversation fetch filtered by id only. Avoid: `WHERE user_id = current_user.id` in the data layer; server-side RBAC dependency on every admin route; explicit cross-user test.
6. **JWT misuse + secrets in a public repo** — `jwt.decode()` without pinned `algorithms` enables `alg:none`/confusion attacks; committed keys get scraped. Avoid: hardcoded `algorithms=["HS256"]`, short access + rotating refresh tokens; `.env` gitignored from the first commit, dashboard env vars, gitleaks in CI, rotate on leak.
7. **Deployed-only footguns: slowapi proxy IP + SSE buffering + cold start** — slowapi keyed on Render's proxy IP throttles everyone as one client; SSE buffers through static-site rewrites; cold start looks broken to recruiters. Avoid: key slowapi on authenticated user id; point Vercel directly at the Render API URL with `text/event-stream` + `X-Accel-Buffering: no`; keep-warm ping or a clear "waking up" UI state.

## Implications for Roadmap

Both the emphasis brief and ARCHITECTURE.md's "Suggested Build Order" independently produced the same 9-step sequence. It is treated as authoritative and mapped directly to phases below. Each phase's pitfall avoidance is drawn from PITFALLS.md's pitfall-to-phase mapping.

### Phase 1: Sync→Async Migration + App Factory
**Rationale:** Keystone. Async DB and streaming both require `async def`; building a sync DB layer and re-asyncing later is rework. All four dimensions agree this is step 0.
**Delivers:** `async def` handlers, app-factory + lifespan, settings read inside function bodies (not at import).
**Addresses:** Fixes anti-patterns #1 (per-request provider) and #2 (import-time binding).
**Avoids:** Pitfall 3 (async loop blocking) and Pitfall 4 (sync/async DB mixing) at the foundation.

### Phase 2: Postgres + db/ Layer + Alembic + Structured Logging
**Rationale:** Foundation for users, chat, and document metadata — the keystone everything multi-user depends on. Already needs the async foundation from Phase 1.
**Delivers:** SQLAlchemy 2.x async models, `async_sessionmaker`, Alembic migrations, structlog JSON logging.
**Uses:** SQLAlchemy[asyncio] 2.0.50, asyncpg 0.31.0, Alembic 1.18.4, structlog.
**Implements:** `db/` domain; `core/logging.py`.
**Avoids:** Pitfall 4 (engine built in lifespan, not at import); Pitfall 5 (configure `pool_pre_ping` for Neon now).

### Phase 3: Auth + RBAC
**Rationale:** Everything user/admin-scoped depends on identity; the `Depends` DI backbone is established here.
**Delivers:** register/login/refresh, `get_current_user`, `require_admin`, password hashing, JWT.
**Uses:** PyJWT 2.13, pwdlib[argon2,bcrypt] 0.3.0.
**Implements:** `auth/`, `api/deps.py`.
**Avoids:** Pitfall 6 (multi-tenant leakage — ownership checks), Pitfall 7 (JWT algorithm pinning, refresh rotation).

### Phase 4: Early Hosted Authed Slice (Render + Vercel + Neon)
**Rationale:** Key Decision — deploy early (~phase 2-3) to de-risk free-tier deploy before full feature build-out. Surfaces the deployed-only footguns on real infrastructure.
**Delivers:** Login + a hosted slice wired across Render/Vercel/Neon, CORS configured to the Vercel origin.
**Avoids:** Early detection of Pitfall 5 (Neon stale connections), Pitfall 10 (slowapi proxy IP), Pitfall 13 (cold start) on real infra. **See sequencing tension below — the RAG path may not be functional hosted until Phase 5.**

### Phase 5: Pinecone + Voyage Migration (delete FAISS/ST/cross-encoder)
**Rationale:** Swap the retrieval substrate behind the new `embeddings/` + `reranking/` providers; the free-tier hosting win materializes only once the heavy local deps are deleted. Rebuild the `benchmark` namespace.
**Delivers:** Pinecone-backed `vector_store`, Voyage providers, deleted FAISS/sentence-transformers/cross-encoder/torch, re-embedded benchmark corpus.
**Uses:** pinecone SDK, voyageai.
**Avoids:** Pitfall 1 (define `benchmark` vs `shared_kb` namespaces now), Pitfall 2 (lock 1024/cosine, length assert), Pitfall 3 (`to_thread` around sync Voyage calls).

### Phase 6: Multi-Document Ingestion + Admin Document Management
**Rationale:** Needs Pinecone (5) + auth/admin (3) + BackgroundTasks + status model. Namespace isolation must already exist (5) before uploads ship, or eval integrity is silently violated.
**Delivers:** Admin upload/list/delete/re-index, async ingestion with `queued→processing→ready→failed` status, per-document citations into `shared_kb`.
**Implements:** `documents/`, admin routers.
**Avoids:** Pitfall 1 (uploads write only `shared_kb`), Pitfall 9 (Voyage backoff/batching, request-size limits).

### Phase 7: Chat Persistence + SSE Streaming
**Rationale:** Needs async (1), db (2), the Pinecone query path (5), and a provider `stream_answer()`. Sequenced after providers stabilize to avoid double-refactoring.
**Delivers:** Conversation/message persistence (list/resume/delete), token-by-token SSE answers, `stream_answer()` on the `LlmProvider` Protocol.
**Implements:** `conversations`, `messages`, `llm/` streaming.
**Avoids:** Pitfall 6 (per-user history filtering), Pitfall 11 (SSE framing/buffering/CORS — verify on deployed URL).

### Phase 8: RAGAS Eval Harness
**Rationale:** Needs the migrated pipeline (5) querying the frozen `benchmark` namespace. Scoring a still-migrating pipeline wastes effort.
**Delivers:** Golden Q/A set, repeatable `eval` run over `benchmark` only, metrics report in README (Groq as the free judge).
**Uses:** ragas 0.4.3.
**Avoids:** Pitfall 1 (benchmark-only retrieval), Pitfall 12 (pin judge model, temp=0, report scores with judge/date context).

### Phase 9: Ops / CI / Demo Polish
**Rationale:** Docker image is now slim (post-deletion), so containerization and CI land cleanly; cross-cutting hardening completes the production story.
**Delivers:** Docker/compose, GitHub Actions (ruff + pytest + build; deploy on merge), pytest suite, slowapi caps, Sentry, seeded demo account, cold-start mitigation, polished README + arch docs.
**Avoids:** Pitfall 8 (gitleaks in CI — note `.env`/`.env.example` hygiene must be correct from the first commit), Pitfall 9/10 (caps verified), Pitfall 13 (waking-state UI + README caveat).

### Phase Ordering Rationale

- **Async first (1) is non-negotiable** — async DB (2) and streaming (7) both require it; all four research dimensions converged on this. Building sync-then-async is documented rework.
- **Postgres (2) is the keystone** — it gates auth, RBAC, chat history, and document metadata, so it lands immediately after the async foundation.
- **Deploy early (4)** is a deliberate Key Decision to de-risk free-tier hosting and expose deployed-only pitfalls before the full build.
- **Namespace isolation precedes uploads** — `benchmark` vs `shared_kb` (created in 5) must exist before ingestion (6) ships, or eval (8) is meaningless.
- **Eval last among features (8)** — it needs a settled post-migration pipeline to score.

### Research Flags

Phases likely needing deeper research during planning (`/gsd:plan-phase --research-phase`):
- **Phase 5 (Pinecone + Voyage migration):** dimension lock at creation, `input_type=document` vs `query`, eventual-consistency after upsert, the one-time re-embed script — vendor-specific gotchas that bite silently.
- **Phase 7 (Chat persistence + SSE streaming):** Render static-site-rewrite buffering, `data: ...\n\n` framing, streaming headers, CORS for the stream endpoint, persist-after-stream — must be verified against the deployed URL, not localhost.
- **Phase 8 (RAGAS eval):** judge nondeterminism, ragas version-pinning (metric APIs change between minors), judge cost/rate-limit handling, reporting scores with context.

Phases with standard patterns (skip research-phase):
- **Phase 2 (Postgres/SQLAlchemy async), Phase 3 (Auth — PyJWT/pwdlib), Phase 9 (Docker/CI):** well-documented, established FastAPI patterns; STACK/ARCHITECTURE already give the concrete approach.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions verified live against PyPI 2026-06-10; a few vendor free-tier numbers MEDIUM. |
| Features | HIGH | Scope pre-defined in PROJECT.md; "how-it-works" verified against current RAGAS docs + Onyx/Danswer. |
| Architecture | HIGH | Design synthesis over established codebase layers + locked stack; standard FastAPI patterns. |
| Pitfalls | HIGH | Anchored to concrete codebase concerns + chosen stack; PyJWT `algorithms` and Render SSE buffering independently verified. |

**Overall confidence:** HIGH

### Gaps to Address

- **Deploy-early vs migration-not-yet-done sequencing tension (most important):** Phase 4 deploys "existing chat hosted" while FAISS + sentence-transformers + torch are still in the image, but STACK.md says the free-tier hosting win materializes *only after* those are deleted in Phase 5. Render free is ~512MB RAM and the heavy ML stack likely OOMs. Resolve in roadmapping: either Phase 4 is a deploy-pipeline-only slice (auth + frontend + Neon wiring, RAG not yet functional hosted), or the Pinecone/Voyage migration must precede a working hosted RAG. The deploy-early Key Decision is deliberate — flag it, do not silently reorder.
- **Voyage commercial-use clause (LOW confidence):** not independently confirmed for the free tier — verify at signup. Does not change the vendor decision (the ~1k-calls/month Cohere cap settles it regardless).
- **Free-tier numbers (MEDIUM):** Pinecone (2GB/2M WU/1M RU), Render no-CC + 15-min spin-down, Neon 5-min autosuspend — consistent across 2026 sources but confirm at signup.
- **Render free Postgres expiry (recall, not verified):** irrelevant in practice — use Neon for the DB and Render only for the API.
- **BackgroundTasks coupling to the web dyno:** a restart mid-ingest leaves a stuck `processing` row — acceptable for a demo; mitigate with a timeout/requeue or manual retry endpoint and note the limitation in the README.

## Sources

### Primary (HIGH confidence)
- `.planning/PROJECT.md` — scope, constraints, Key Decisions (eval integrity, deploy-early, migration-as-deletion, RBAC shared-KB)
- `.planning/research/STACK.md` — locked stack, versions verified against PyPI 2026-06-10, async-migration dependency, free-tier topology
- `.planning/research/FEATURES.md` — table stakes vs differentiators, dependency graph, MVP definition (verified vs RAGAS docs + Onyx/Danswer)
- `.planning/research/ARCHITECTURE.md` — target structure, suggested build order, data model, patterns, anti-patterns
- `.planning/research/PITFALLS.md` — 13 pitfalls hooked to codebase concerns + stack; PyJWT/RFC 8725 and Render SSE buffering verified
- `.planning/codebase/` (ARCHITECTURE/CONCERNS/STRUCTURE/CONVENTIONS) — existing layers and flagged anti-patterns

### Secondary (MEDIUM confidence)
- Pinecone / Voyage / Neon / Render / Vercel / Sentry vendor docs + 2026 free-tier comparisons — tier numbers (confirm at signup)
- docs.ragas.io (stable) — current metrics: Faithfulness, Response Relevancy, Context Precision, Context Recall

### Tertiary (LOW confidence)
- Voyage commercial-use stance on the free tier — inferred, re-verify at signup (does not affect the decision)
- Render free-Postgres expiry window — recall, not verified (use Neon regardless)

---
*Research completed: 2026-06-10*
*Ready for roadmap: yes*
