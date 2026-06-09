# Feature Research

**Domain:** Production-grade, multi-user RAG / document-QA platform (portfolio + live recruiter demo)
**Researched:** 2026-06-10
**Confidence:** HIGH (scope is pre-defined in PROJECT.md; "how-it-works" details verified against current RAGAS docs and a real OSS doc-QA platform, Onyx/Danswer)

> **Categorization note.** This is a subsequent (brownfield) milestone with a tightly-scoped requirement set already in `.planning/PROJECT.md`. This file does **not** re-derive the feature set from open-ended research — it maps the **Active** requirements into table stakes vs differentiators, treats the **Out of Scope** list as anti-features (plus a few tempting-but-skip additions), and records complexity + dependencies for roadmap ordering. "Table stakes" here means: *without it, the system does not read as production-grade to a hiring manager.*

## Feature Landscape

### Table Stakes (Reviewers Expect These to Call It "Production")

Features a Backend/Full-stack+AI reviewer assumes a "production RAG platform" has. Missing these = the project reads as a toy/demo, not production. No credit for having them; penalized for missing them.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| JWT email/password auth (access + refresh, bcrypt/argon2 hashing) | "Production + multi-user" is meaningless without real auth; the demo is internet-facing | MEDIUM | Refresh-token rotation is standard convention. Hash with argon2id or bcrypt. Store refresh token server-side or rotate via short-lived access + longer refresh. |
| Role-based access control (admin vs user) | Multi-user system needs authorization, not just authentication; admins manage docs, users query | MEDIUM | Enforce at route/dependency layer (FastAPI `Depends`). Two roles only — keep it simple. |
| Postgres persistence for users, roles, conversations, messages, doc metadata | Production app needs durable relational storage; in-memory/global state (current state) is the anti-pattern being fixed | MEDIUM | Foundational — gates almost everything else. Use SQLAlchemy + Alembic migrations (recognizable, defensible). |
| Admin document management: upload → ingestion status/progress → list → delete → re-index | A shared knowledge base with no admin CRUD is incomplete; this is the core "managed" in "managed knowledge base" | HIGH | Real OSS platforms (Onyx/Danswer) expose an **indexing-status** view per document with states like `queued → processing → indexed → failed`. Ingestion is async (chunk→embed→upsert to Pinecone); needs background task + status polling. |
| Multi-document retrieval with per-document citation/attribution | Replaces hardcoded single PDF; users must know *which* source document an answer came from | MEDIUM | Each citation needs `document_id`/title + page. Metadata travels with chunks into Pinecone (the existing page-metadata convention extends naturally). |
| Streaming (token-by-token) answers | Standard chat-UX expectation in 2026; non-streaming reads as dated | MEDIUM-HIGH | **Constraint (ARCHITECTURE.md):** all route handlers are sync `def` and all LLM providers are sync. Streaming requires async route handlers + SSE (or chunked response) **and** adding a streaming method to the `LlmProvider` Protocol. Highest-complexity table-stakes item. |
| Chat history persistence (save, list, resume, delete conversations) | Multi-user product with no saved history is incomplete; frontend currently holds history client-side only | MEDIUM | Conversation + message tables; scoped to the authenticated user. Powers "resume" and per-user RBAC on history. |
| Source citations preserved across the new (Pinecone) pipeline | Citations are the existing core value ("trustworthy, source-cited"); regressing them is unacceptable | LOW-MEDIUM | Mostly migration discipline — preserve metadata through the embed/rerank API swap. |
| Rate limiting / per-user daily cap | **Public, internet-facing demo with real API keys** — missing this reads as negligent (cost/abuse exposure) | LOW-MEDIUM | Per-user (authed) + per-IP (anon) caps. Redis or Postgres counter; `slowapi` is the recognizable FastAPI choice. *This is table stakes here precisely because the demo is public — not a differentiator.* |
| Automated test suite (pytest: unit + API integration) + configured runner | "Production engineering" claim is hollow without tests; current state has no configured runner | MEDIUM | Test the RAG pipeline with mocked providers + API integration tests with a test DB. A reviewer will look for this first. |
| Docker + docker-compose (backend, frontend, db) | Reproducible, deployable system is the definition of production-ready | MEDIUM | Multi-stage backend image. The FAISS/sentence-transformers removal is what makes a slim free-tier image possible. |
| CI/CD via GitHub Actions (lint + test + build; deploy on merge) | Production engineering signal; reviewers check the Actions tab | MEDIUM | Lint + pytest + build on PR; deploy on merge to main. |
| Structured (JSON) logging + error capture (Sentry-style) | Observability basics; `print()`-only (current state) is not production | LOW-MEDIUM | Structured JSON logs + a request/correlation id. Note: full tracing dashboards are explicitly **out of scope** (see anti-features). |
| Live hosted demo (clickable public URL) | It's a *demo*; an unhosted repo undercuts the entire portfolio goal | MEDIUM | De-risk early (PROJECT.md key decision: deploy an authed slice by ~phase 2–3, not last). Free-tier hosting drives the API-embeddings migration. |
| Seeded demo account + sensible empty states | A public demo a recruiter clicks must work in 10 seconds with zero setup; empty UIs read as broken | LOW | Pre-seeded read-only `user` account; pre-loaded benchmark corpus; helpful empty states for "no conversations yet" / "no documents yet". |
| Polished README + architecture docs | The artifact's primary job is to communicate to recruiters | LOW-MEDIUM | The narrative wrapper for everything else. |

### Differentiators (What Makes This Portfolio Piece Stand Out)

Features that separate this from the average portfolio RAG project. Aligned with PROJECT.md Core Value ("answer quality that is *measurably* good") and the target audience (Backend/Full-stack+AI hiring managers).

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **RAGAS-style evaluation pipeline + golden Q/A set on a fixed benchmark corpus** | **The headline differentiator.** Measurable answer quality is rare in portfolios and is the strongest "hire signal" for an AI role — it proves engineering rigor, not just wiring an LLM | HIGH | Current RAGAS metrics (verified, docs.ragas.io stable): **Faithfulness, Response Relevancy** (formerly answer relevancy), **Context Precision, Context Recall** — all four required by this milestone exist and are current. Faithfulness + Response Relevancy are reference-free; Context Precision/Recall use the golden set's reference answers. Golden set scored against the *fixed* `student_manual` corpus only (uploads must not affect scores — PROJECT.md constraint). RAGAS itself calls an LLM-as-judge, so eval runs cost tokens — budget/cache accordingly. |
| **Eval results surfaced as a README badge / report (and ideally a CI gate)** | Turns "I evaluated it" into a visible, continuous, defensible artifact a reviewer sees in 5 seconds | MEDIUM | Repeatable `eval` command → metrics report committed/badged. CI gate (fail build if faithfulness drops below threshold) is the strongest version — but treat the gate as a stretch; LLM-judge variance makes hard thresholds flaky, so consider a soft/report-only gate first. |
| **Embedding + reranker provider abstractions mirroring the existing `LlmProvider` Protocol** | The clean-design narrative: a defensible, DRY/SOLID architecture story (3 swappable provider families behind one consistent pattern) | MEDIUM | Reuses the proven `Protocol` + factory pattern. Makes the FAISS→Pinecone / local→API migration a *design decision*, not a hack. Secondary differentiator. |
| Two-stage retrieve→rerank already in place, preserved through API migration | Shows retrieval-quality awareness beyond naive top-k similarity | LOW (exists) | Already built; the migration to API reranker keeps it. Mention in README as a quality lever the eval pipeline measures. |
| Pluggable multi-LLM-provider support (Groq/Anthropic/Gemini) | Shows abstraction maturity and vendor-independence | LOW (exists) | Already built. Fix both flagged anti-patterns as part of this milestone: instantiate the provider **once** (not per request) and **read settings inside function bodies** (not at import time). |

### Anti-Features (Deliberately NOT Building This Milestone)

Features that seem expected but are explicitly excluded — either by PROJECT.md Out of Scope or because they contradict a project constraint. Documenting them prevents scope creep and gives a defensible "why not" answer in an interview.

| Feature | Why Requested / Tempting | Why Problematic Here | Alternative |
|---------|--------------------------|----------------------|-------------|
| Observability / distributed tracing dashboards (Langfuse/LangSmith) | Pairs naturally with eval; trendy | Large surface area; would dilute v1 focus. Structured logging already covers the basics | Defer to a later milestone (PROJECT.md). Ship structured JSON logging + error capture only. |
| OAuth / social login (Google etc.) | Users expect "Sign in with Google" | The *point* is to demonstrate backend security fundamentals; managed OAuth hides them | Self-built JWT email/password proves the skill first. Defer OAuth. |
| Per-user private document collections & sharing | Feels like the "real" multi-tenancy | A much larger data-model + authorization surface; over-scopes v1 | Shared-KB + RBAC (admin uploads, users query) is the v1 multi-tenancy model. Defer private/shared collections. |
| Managed auth providers (Clerk/Auth0/Supabase Auth) | Faster, "production-standard" | Outsources exactly the skill a backend portfolio must demonstrate | Build auth ourselves — that *is* the point. |
| Self-hosting embedding / reranker models | "More impressive / no vendor lock-in" | **Contradicts the free-tier hosting constraint** — heavy local models are the thing being *removed* to fit free tiers | API embedding + reranker providers (Cohere/Voyage). The removal is the free-tier win. |
| Building a custom vector store | Shows low-level skill | Reinventing a solved problem; not the value story; burns the budget | Pinecone (managed, recognizable, free tier). |
| Document versioning / diffing | "Documents change over time" | Adds significant data-model complexity for little demo value | Delete + re-index covers v1 needs. |
| Real-time collaborative / multi-user chat sessions | Sounds modern | Websocket/CRDT complexity with no portfolio payoff; chat is single-user per conversation | Per-user conversations + streaming responses. |
| Support for every file format (docx, pptx, html, images/OCR…) | "Real platforms ingest everything" | Each loader is a maintenance + edge-case tax; eval corpus is a fixed PDF | PDF ingestion for v1; provider/loader pattern leaves room to extend later. |
| Agentic multi-tool orchestration / web search / "deep research" | Onyx-style flagship features look impressive | Massive scope, hard to evaluate, off-mission for a *document-QA* portfolio | Keep the focused, measurable RAG loop. The eval pipeline is the differentiator instead. |
| Admin analytics/usage dashboards | "Admins want metrics" | Observability-adjacent scope creep | Rate-limit counters + structured logs suffice for v1. |

## Feature Dependencies

```
Postgres persistence (FOUNDATIONAL)
    ├──requires──> Auth (users/roles tables live in Postgres)
    │                 ├──requires──> RBAC (admin vs user)
    │                 ├──requires──> Per-user chat history (scoped to user)
    │                 ├──requires──> Seeded demo account
    │                 └──enhances──> Per-user rate limit / daily cap
    ├──requires──> Chat history persistence (conversation/message tables)
    └──requires──> Document metadata (list/status/delete)

Pinecone migration + embedding/reranker provider abstractions
    └──requires──> Multi-document support
                       ├──requires──> Admin document management (upload/ingest/list/delete/re-index)
                       │                 └──requires──> Ingestion status/progress (async background task)
                       └──requires──> Per-document citation/attribution

Streaming answers
    ├──requires──> async refactor of route handlers (currently sync def)
    └──requires──> streaming method added to LlmProvider Protocol

RAGAS eval pipeline (fixed student_manual corpus)
    ├──requires──> Golden Q/A test set
    ├──requires──> Stable retrieval pipeline (post-Pinecone migration) to score
    └──enhances──> README badge/report + (stretch) CI gate

Docker/compose ──requires──> Postgres service + slim image (after FAISS/ST removal)
CI/CD ──requires──> test suite + Docker build
Live hosted demo ──requires──> Docker + free-tier-friendly (API-based) pipeline + rate limiting + seeded account
```

### Dependency Notes

- **Postgres is the keystone.** It gates auth, RBAC, chat history, and document metadata. It must land in an early phase — almost everything multi-user depends on it.
- **Auth gates RBAC, per-user history, the seeded demo account, and per-user caps.** Ordering: Postgres → Auth → (RBAC, history, demo account) in parallel after.
- **Pinecone/embedding migration gates multi-doc, which gates admin doc management + per-doc citations.** The migration is a *removal* (delete FAISS + sentence-transformers + local cross-encoder) — the free-tier hosting win only materializes once heavy deps leave the image.
- **Ingestion status requires async background processing.** Embedding many chunks via an API is slow; a synchronous upload request would time out. Needs a background task + a status field polled by the admin UI (the Onyx/Danswer `indexing-status` pattern: `queued → processing → indexed → failed`).
- **Streaming is the cross-cutting refactor.** It touches route handlers (sync→async) AND the provider Protocol. Sequence it after the provider abstractions stabilize to avoid double-refactoring. Cite ARCHITECTURE.md's "No async LLM calls" constraint.
- **Eval requires a stable post-migration pipeline.** Scoring a pipeline that's still being migrated wastes effort; run eval against the settled Pinecone path. Eval corpus (`student_manual`) is fixed and isolated from uploads (PROJECT.md constraint).
- **Live demo depends on the most things** (Docker + free-tier pipeline + rate limit + seeded account) — but PROJECT.md mandates deploying an authed slice *early* (~phase 2–3) to de-risk hosting, so a minimal hosted slice should precede full feature completion.

## MVP Definition

> For a brownfield "production + multi-user" milestone, "MVP" = the smallest slice that reads as production-grade *and* is publicly demoable. Everything in "Launch With" is table stakes per PROJECT.md Active requirements.

### Launch With (this milestone, v1)

- [ ] Postgres + migrations — foundational; gates all multi-user features
- [ ] JWT email/password auth + RBAC (admin/user) — multi-user core
- [ ] Pinecone migration + API embedding/reranker providers (remove FAISS/ST) — unlocks free-tier hosting + multi-doc
- [ ] Multi-document support + per-document citations — replaces hardcoded PDF
- [ ] Admin document management (upload, ingestion status, list, delete, re-index) — managed KB
- [ ] Streaming answers — modern chat UX
- [ ] Chat history persistence (list/resume/delete) — multi-user expectation
- [ ] Rate limiting / per-user daily cap — required for a public demo
- [ ] RAGAS eval pipeline + golden set + README report — the differentiator; the reason this stands out
- [ ] pytest suite + Docker/compose + GitHub Actions CI/CD — production engineering proof
- [ ] Structured JSON logging + error capture — observability basics
- [ ] Live hosted demo + seeded account + empty states — the clickable artifact
- [ ] Polished README + architecture docs — the recruiter-facing wrapper

### Add After Validation (v1.x — strong near-term follow-ons)

- [ ] CI eval *gate* with thresholds — once metric variance is understood; start report-only, then gate
- [ ] Additional file formats (docx, etc.) — once PDF path is solid and a real need appears
- [ ] Observability/tracing dashboard (Langfuse/LangSmith) — once eval is in place to pair with it

### Future Consideration (v2+)

- [ ] OAuth / social login — after self-built auth has proven the fundamentals
- [ ] Per-user private + shared document collections — the larger multi-tenancy model
- [ ] Admin usage analytics dashboard — after observability lands

## Feature Prioritization Matrix

| Feature | User/Reviewer Value | Implementation Cost | Priority |
|---------|---------------------|---------------------|----------|
| Postgres persistence | HIGH | MEDIUM | P1 |
| JWT auth + RBAC | HIGH | MEDIUM | P1 |
| Pinecone + provider abstractions (migration) | HIGH | HIGH | P1 |
| Multi-doc + per-doc citations | HIGH | MEDIUM | P1 |
| Admin document management + ingestion status | HIGH | HIGH | P1 |
| Streaming answers | HIGH | MEDIUM-HIGH | P1 |
| Chat history persistence | MEDIUM | MEDIUM | P1 |
| Rate limiting / daily cap | HIGH (demo safety) | LOW-MEDIUM | P1 |
| RAGAS eval pipeline + golden set | HIGH (differentiator) | HIGH | P1 |
| Eval README badge/report | HIGH (visibility) | MEDIUM | P1 |
| Eval CI gate (thresholds) | MEDIUM | MEDIUM | P2 |
| pytest suite | HIGH | MEDIUM | P1 |
| Docker/compose | HIGH | MEDIUM | P1 |
| CI/CD (Actions) | HIGH | MEDIUM | P1 |
| Structured logging + error capture | MEDIUM | LOW-MEDIUM | P1 |
| Live hosted demo + seeded account + empty states | HIGH | MEDIUM | P1 |
| Polished README + arch docs | HIGH | LOW-MEDIUM | P1 |
| Observability/tracing dashboard | MEDIUM | HIGH | P3 (out of scope v1) |
| OAuth / social login | LOW (for this audience) | MEDIUM | P3 (out of scope v1) |
| Private/shared collections | MEDIUM | HIGH | P3 (out of scope v1) |

**Priority key:** P1 = must have for this milestone · P2 = should have, add when feasible · P3 = deferred / out of scope for v1

## Competitor / Reference Feature Analysis

| Feature | Onyx / Danswer (OSS enterprise QA) | Typical portfolio RAG project | Our Approach |
|---------|------------------------------------|-------------------------------|--------------|
| Auth + roles | User auth, admin/basic roles, full RBAC | Usually none | Self-built JWT + admin/user RBAC (the skill demo) |
| Document ingestion | 40+ connectors, incremental sync, per-doc `indexing-status` | Single hardcoded file | Admin upload + async ingestion with status states (`queued→processing→indexed→failed`) |
| Chat persistence | Yes, per-user | Usually client-side only | Postgres-backed per-user conversations |
| Streaming | Yes | Sometimes | SSE streaming + Protocol method |
| Eval / quality measurement | Internal ranking/relevance tuning, not surfaced | Almost never | **RAGAS golden-set eval surfaced as README report/badge — our differentiator** |
| Scope | Huge (agents, web search, deep research, MCP) | Tiny | Deliberately focused, *measurable* document-QA |

## Sources

- `.planning/PROJECT.md` — Active requirements, Out of Scope, Constraints, Key Decisions (HIGH — authoritative for scope)
- `.planning/codebase/ARCHITECTURE.md` — existing system, sync-handler / sync-provider constraints driving streaming complexity (HIGH — primary source)
- [Metrics | Ragas (docs.ragas.io, stable)](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/) — confirmed current metrics: Faithfulness, Response Relevancy (formerly answer relevancy), Context Precision, Context Recall (HIGH)
- [Metrics | Ragas v0.1.21](https://docs.ragas.io/en/v0.1.21/concepts/metrics/) — the four-metric framework definitions (HIGH)
- [How to Evaluate RAG Pipelines with RAGAS — INVRA](https://www.invra.co/en/rag-evaluation-with-ragas-measuring-faithfulness-context-precision-and-recall-in-production/) — metric semantics, production use (MEDIUM)
- [Onyx Documentation — Connectors Overview](https://docs.onyx.app/admins/connectors/overview) — admin doc-management UX, ingestion/indexing-status pattern, admin/basic roles, chat persistence (MEDIUM, real OSS reference)
- [onyx-dot-app/onyx (GitHub)](https://github.com/onyx-dot-app/onyx) — production-ready feature baseline: auth, role management, chat persistence (MEDIUM)
- [file connectors: Upload file · Issue #1530, danswer-ai/danswer](https://github.com/danswer-ai/danswer/issues/1530) — confirms `indexing-status` endpoint pattern for upload status (LOW-MEDIUM)

---
*Feature research for: production multi-user RAG / document-QA platform (portfolio)*
*Researched: 2026-06-10*
