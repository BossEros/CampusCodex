# ADR-0001: Clean up partial Pinecone vectors on ingestion failure

**Status:** Accepted  
**Date:** 2026-06-14

## Context

During Document ingestion, Chunks are upserted into Pinecone `shared_kb` one batch at a time. If the pipeline fails mid-way (e.g., Voyage API 429, network drop), some Chunks are already in Pinecone while others are not. These orphaned Chunks belong to a Document marked `failed` — but Pinecone retrieval has no awareness of Document status, so those Chunks can still surface in user queries.

## Decision

On any ingestion failure, delete all Chunk IDs that were successfully upserted before marking the Document `failed`. Chunk IDs are generated upfront using the pattern `{document_id}#{chunk_index}`, making them enumerable for cleanup. The Document is left with zero vectors in Pinecone — a clean slate that is safe to re-index.

## Alternatives considered

**Leave orphaned vectors, mark `failed`** — simpler ingestion code, but orphaned Chunks from a failed Document can silently pollute query results. Unacceptable for a demo where answer quality is the headline.

## Consequences

- Ingestion code must track which Chunk IDs were successfully upserted and issue a delete-by-ID call on failure.
- A `failed` Document is always a zero-vector clean slate — re-indexing never needs to pre-clean.
- Slightly more complex ingestion pipeline, accepted as the right trade-off.
