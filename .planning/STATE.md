# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-10)

**Core value:** Trustworthy, source-cited answers from a managed document knowledge base — answer quality that is *measurably* good, served through a secure, deployable, real-world system.
**Current focus:** Phase 4 — Pinecone + Voyage Migration is complete. Phases 1–3 (Async Foundation, Postgres Persistence, Auth & RBAC) remain unstarted per the roadmap's original sequencing — **this divergence has not been resolved, only surfaced; confirm with the team whether Phases 1–3 were intentionally deferred or this state is simply stale.**

## Current Position

Phase: 4 of 9 (Pinecone + Voyage Migration) — **complete**, out of the roadmap's original sequence (Phases 1–3 not yet started)
Plan: 1 of 1 in Phase 4 (`04-01-PLAN.md`), all 5 sub-phases complete
Status: Phase 4 done; next step is either resuming Phases 1–3 in original order or proceeding to Phase 5 (First Hosted Authed Slice) — needs a decision, not assumed
Last activity: 2026-07-09 — Phase 4 fully completed: Pinecone runtime cutover verified live (Phase 3), benchmark/shared_kb corpus seeded and 4 representative chat scenarios verified live (Phase 4), heavy local ML deps (faiss-cpu/sentence-transformers/torch/langchain-huggingface) removed and verified absent, docs swept clean of FAISS references (Phase 5)

Progress: [██░░░░░░░░] ~1/9 phases complete (Phase 4 only; Phases 1-3 still open)

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Migration (Phase 4) sequenced BEFORE the first hosted deploy (Phase 5). The deploy-early target moved from ~phase 2–3 to phase 5 so the first deploy runs on the slim API-based stack AND demos core value (cited RAG). Pre-accepted per hard constraint #5.
- [Roadmap]: Eval namespace isolation (`benchmark` vs `shared_kb`) created at Pinecone index time in Phase 4 — exists before uploads ship in Phase 6, guaranteeing eval integrity.
- [Roadmap]: Sync→async migration is Phase 1 (foundational); async DB and streaming both depend on it. Building sync-then-async is documented rework.
- [Phase 4 baseline]: Phase 4 is locked as a retrieval migration only — Pinecone + Voyage + benchmark isolation + heavy dependency removal. Admin upload/list/delete/re-index remains deferred to Phase 6.

### Pending Todos

- Phase 4 (`04-01-PLAN.md`) is fully complete (Phases 0-5 of that plan). Decide next step: resume the roadmap's original order (Phase 1: Async Foundation & App Factory) or proceed directly to Phase 5 (First Hosted Authed Slice), which depends on Phase 4 and is now unblocked.
- `GROQ_API_KEY` in `backend/.env` is a literal placeholder value (`your_groq_api_key_here`), not a real key — `LLM_PROVIDER=groq` will fail with `groq.AuthenticationError` until a real key is added. Discovered during Phase 4 live verification; not fixed since it's a credentials issue outside this migration's scope.

### Blockers/Concerns

- Requirement count: 37 (OPS-01, OPS-02, OPS-05 removed 2026-06-14 as unnecessary complexity). PROJECT.md prose still reads "37" — now accurate by coincidence; confirm at next milestone review.
- Pinecone index `dimension=1024` / `metric=cosine` is fixed at creation (Phase 4) — locking it wrong forces a full re-embed. No migration from the old 384-dim local vectors; the benchmark must be re-embedded.
- Free-tier numbers (Pinecone RU/WU, Voyage tokens, Render cold start, Neon autosuspend) are MEDIUM confidence — re-verify at signup.
- BackgroundTasks ingestion is coupled to the web dyno (Phase 6); a restart mid-ingest can leave a stuck `processing` row — acceptable for a demo, note in README.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-07-09
Stopped at: Phase 4 (`04-01-PLAN.md`) fully complete — all 5 sub-phases (seam, provider abstractions, Pinecone cutover, benchmark seeding, dependency cleanup) done and live-verified
Resume file: `.planning/phases/04-pinecone-voyage-migration/04-01-PLAN.md` (reference only, not resumable — complete); next action is a roadmap-sequencing decision, not a specific file
