# RAG Knowledge Platform

## What This Is

A production-grade Retrieval-Augmented Generation platform where administrators upload documents to a shared knowledge base and authenticated users get streaming, source-cited answers with persistent chat history. Built on a FastAPI backend and React frontend, it is the production evolution of an existing single-document student-manual RAG project — re-engineered to demonstrate professional backend + AI engineering for a portfolio and live recruiter-facing demo.

## Core Value

Trustworthy, source-cited answers from a managed document knowledge base — answer quality that is *measurably* good (proven by an evaluation pipeline), served through a secure, deployable, real-world system.

## Requirements

### Validated

<!-- Inferred from existing codebase (.planning/codebase/) — already built and working. -->

- ✓ RAG query pipeline: retrieve → rerank → generate with source citations — existing
- ✓ Two-stage retrieval (broad ANN fetch → cross-encoder rerank to top-k) — existing
- ✓ Pluggable LLM provider abstraction (Groq / Anthropic / Gemini) via `Protocol` + factory — existing
- ✓ Follow-up question rewriting using chat history for better retrieval — existing
- ✓ React chat UI with evidence drawer and starter questions — existing
- ✓ Pydantic-validated request/response contracts and env-based settings — existing

### Active

<!-- This milestone: make it production-ready and portfolio-grade. -->

**Data & retrieval migration**
- [ ] Replace local FAISS index with Pinecone (managed vector DB)
- [ ] Replace local sentence-transformers embeddings with an API embedding provider (e.g. Cohere/Voyage)
- [ ] Replace local cross-encoder reranker with an API reranker (same vendor where possible)
- [ ] Remove FAISS / sentence-transformers / local cross-encoder and their heavy dependencies
- [ ] Add embedding-provider and reranker-provider abstractions mirroring the existing `LlmProvider` Protocol + factory pattern

**Persistence & data model**
- [ ] Introduce Postgres for application data: users, roles, conversations, messages, document metadata
- [ ] Persist conversation history per user (saved chats, retrievable)

**Auth & access control**
- [ ] JWT email/password authentication (hashed passwords via bcrypt/argon2, access + refresh tokens)
- [ ] Role-based access control: `admin` (manage documents) vs `user` (query, view own history)

**Document management (shared knowledge base)**
- [ ] Admin document upload + ingestion pipeline (chunk → embed → index into Pinecone)
- [ ] Multi-document support replacing the hardcoded single PDF
- [ ] Document metadata management (list, status, delete) for admins

**Answer experience**
- [ ] Streaming (token-by-token) answer responses
- [ ] Source citations preserved across the new pipeline

**Evaluation (credibility signal)**
- [ ] RAGAS-style evaluation pipeline (faithfulness, answer relevance, context precision/recall)
- [ ] Golden Q/A test set scored against the canonical `student_manual` benchmark corpus
- [ ] Repeatable eval run with reported metrics (surfaced in README)

**Production engineering**
- [ ] Docker + docker-compose for backend, frontend, and database
- [ ] CI/CD via GitHub Actions (lint + test + build; deploy on merge)
- [ ] Automated test suite (pytest: unit + API integration) with proper test config
- [ ] Structured (JSON) logging + error tracking (Sentry-style capture)
- [ ] Rate limiting / per-user daily cap to protect the public demo from abuse/cost
- [ ] Fix flagged anti-patterns: instantiate LLM provider once (not per request); read settings inside function bodies (not at import time)

**Delivery**
- [ ] Live hosted demo on a free/low-cost tier (clickable public URL)
- [ ] Polished README + architecture docs presenting the system for recruiters

### Out of Scope

<!-- Deferred to later milestones. Strong future additions, deliberately excluded from v1. -->

- Observability / distributed tracing dashboards (Langfuse/LangSmith) — pairs with eval; defer to a later milestone to keep v1 focused
- OAuth / social login (Google) — JWT email/password proves the backend security fundamentals first
- Per-user private document collections & collection sharing — shared-KB + RBAC is the v1 multi-tenancy model; private/shared collections are a larger follow-on
- Managed auth providers (Clerk/Auth0/Supabase Auth) — building auth ourselves is the point for a backend-focused portfolio

## Context

- **Origin:** This is a refactor/expansion of an existing school project (a single-PDF "student manual" RAG chatbot). The codebase is already mapped — see `.planning/codebase/` (ARCHITECTURE.md, STACK.md, STRUCTURE.md, CONCERNS.md, CONVENTIONS.md, INTEGRATIONS.md, TESTING.md).
- **Current state:** FastAPI backend (`backend/app/`) with a layered RAG pipeline (`rag/`), an `LlmProvider` Protocol abstraction (`llm/`), Pydantic settings (`core/config.py`), a React/Vite frontend (`frontend/`), an offline FAISS index builder (`scripts/build_index.py`), and local sentence-transformers models for embeddings + reranking.
- **Goal of this work:** Portfolio proof that the author can build production RAG / AI-engineering systems end to end — used as a resume centerpiece and a live demo to stand out in the job market.
- **Target audience for the artifact:** Hiring managers / interviewers for Backend / Full-stack + AI roles. Design choices should favor recognizable, defensible engineering (clean APIs, real auth, system design, measurable quality).
- **Known issues to address (from codebase map):** LLM provider re-instantiated on every request; import-time settings binding in `vector_store.py`; no structured logging; no auth; no configured test runner; hardcoded single-document corpus.

## Constraints

- **Hosting/Budget**: Must run on free or low-cost tiers — drives API-based embeddings/reranking and the removal of heavy local models — Why: a clickable live demo is required, and self-hosted ML models are expensive/hard on free tiers.
- **Tech stack**: Keep FastAPI + React + Pydantic + the existing `LlmProvider` Protocol; extend rather than rewrite — Why: reuse working foundations (DRY) and present a clean, evolutionary design story.
- **Vector store**: Pinecone (managed) for vectors; Postgres for all relational/app data — Why: recruiter-recognizable vector DB + standard relational modeling.
- **Security**: Public demo must be protected against cost/abuse (rate limits, daily caps) and use proper password hashing + JWT — Why: it's internet-facing with real API keys behind it.
- **Evaluation integrity**: The `student_manual` corpus is the *fixed* benchmark for eval; user-uploaded docs do not affect eval scores — Why: RAGAS-style metrics need a stable golden set to be meaningful.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Vertical MVP structure; deploy a live authed slice early (≈ phase 2–3), not last | Avoids the classic portfolio failure of building everything and never hosting; continuously de-risks free-tier deployment | — Pending |
| `student_manual` stays as the canonical benchmark corpus with a golden Q/A set; multi-doc upload is a separate capability that does NOT feed eval numbers | Eval needs a fixed ground truth; arbitrary uploads give the metrics nothing stable to measure | — Pending |
| Migration is a *removal*: delete FAISS + sentence-transformers + local cross-encoder and heavy deps | The free-tier hosting win only materializes if the heavy local models actually leave the image | — Pending |
| Add embedding + reranker provider abstractions mirroring the existing `LlmProvider` Protocol | Reuse the proven pattern (DRY/SOLID); makes the API-swap a clean, defensible design choice | — Pending |
| Pinecone for vectors, Postgres for app data | Recognizable managed vector DB + standard relational data modeling; both have free tiers | — Pending |
| RBAC shared-KB model (admin uploads, users query) instead of per-user private collections | Simpler v1 multi-tenancy that still demonstrates real authorization; private/shared collections deferred | — Pending |
| JWT email/password + roles instead of managed auth | Demonstrates core backend security skills hiring managers probe on | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-10 after initialization*
