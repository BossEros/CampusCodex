# Phase 4 Baseline: Pinecone + Voyage Migration

## Purpose

Lock the Phase 4 migration target before implementation starts, so the team does not mix retrieval-migration work with later ingestion/admin work.

## Scope Locked In

Phase 4 covers only:

- Replacing local FAISS runtime retrieval with Pinecone
- Replacing local sentence-transformers embeddings with Voyage embeddings
- Replacing the local cross-encoder reranker with Voyage reranking
- Preserving the current cited-answer Retrieval Pipeline
- Seeding and isolating the benchmark corpus in Pinecone
- Removing heavy local ML dependencies from the backend image

Phase 4 does **not** cover:

- Admin upload UI
- Admin document list/delete/re-index flows
- Async multi-document ingestion lifecycle
- Shared-KB document management APIs

Those belong to Phase 6.

## Canonical Baseline

The migration baseline is the current single-document `student_manual` chatbot flow:

- one canonical PDF corpus
- one existing chat endpoint
- one existing query-rewrite path
- one existing rerank-then-answer path
- source citations preserved through metadata

Phase 4 upgrades the retrieval substrate beneath that flow. It does not change the product scope yet.

## Target Runtime Shape

- Vector database: Pinecone serverless
- Index dimension: `1024`
- Similarity metric: `cosine`
- Runtime namespace: `shared_kb`
- Eval namespace: `benchmark`
- Embedding model: Voyage `voyage-3.5`
- Reranker model: Voyage `rerank-2.5`

## Non-Negotiables

- Preserve the two-stage Retrieval Pipeline: `Retrieval -> Reranking`
- Preserve answer citations with document title and page metadata
- Keep `benchmark` isolated from `shared_kb`
- Re-embed the benchmark corpus; do not attempt to migrate old 384-dim local vectors
- Remove `faiss-cpu`, `sentence-transformers`, and `torch` from the backend image before Phase 4 is considered done
- Do not begin Phase 6-style admin ingestion work inside this phase

## Execution Boundary

Phase 4 is complete when:

- chat retrieval runs through Pinecone
- embeddings and reranking run through Voyage-backed provider abstractions
- citations still work
- benchmark seeding is isolated to `benchmark`
- heavy local ML dependencies are removed

Phase 4 is **not** complete merely because Pinecone is connected. The migration must also leave the backend on the slim production-oriented stack.

## Source of Truth

- Roadmap success criteria: `.planning/ROADMAP.md`
- Requirement mapping: `.planning/REQUIREMENTS.md`
- Main execution plan: `.planning/phases/04-pinecone-voyage-migration/04-01-PLAN.md`
