# CONTEXT.md — RAG Knowledge Platform

## Glossary

### Document
An admin-uploaded PDF artifact. The unit of admin management: upload, delete, re-index. Has a title and an ingestion status lifecycle. Persisted in Postgres. Not a text chunk.

### Chunk
A single text segment produced by splitting a Document during ingestion. The unit stored as a Pinecone vector and retrieved during a query. Called `Document` inside LangChain internals — do not confuse with the domain term.

### Knowledge Base
The live pool of Chunks stored in the `shared_kb` Pinecone namespace. Admins manage it by uploading and deleting Documents. Users query against it. Distinct from the Benchmark Corpus.

### Benchmark Corpus
The frozen pool of Chunks stored in the `benchmark` Pinecone namespace, re-embedded from `student_manual_2019.pdf`. Used exclusively by the eval pipeline. Admin uploads never touch this namespace — eval integrity depends on it.

### Message
A single exchange unit within a Conversation: either a user turn or an assistant turn. Has a role (`user` | `assistant`) and text content. The schema-level name is `ChatMessage`.

### Conversation
The persisted, server-side container for an ordered sequence of Messages, scoped to an authenticated user. Has an ID, a user owner, and a creation timestamp. The unit of CHAT management: list, resume, delete.

### History
The in-request list of prior Messages sent by the client with each query so the backend can resolve follow-up questions. A request-scoping concept — not a stored entity. Distinct from a Conversation.

### User
An authenticated account that can query the Knowledge Base and manage their own Conversations. The base role.

### Admin
A User with elevated privileges. Can do everything a User can (query, Conversations) plus manage Documents in the Knowledge Base (upload, list, delete, re-index). Admin is a strict superset of User — no separate non-chatting admin-only persona exists.

### Ingestion
The full async pipeline that makes an uploaded Document queryable: parse PDF → chunk text → embed Chunks via Voyage → upsert into Pinecone `shared_kb`. Status lifecycle: `queued → processing → indexed → failed`. On failure, all partially-upserted Chunks are deleted from Pinecone before the Document is marked `failed` (see ADR-0001). A `failed` Document is always a zero-vector clean slate.

### Question
The raw text the user submits. What arrives in the `ChatRequest.question` field. Never modified.

### Query
The text sent to Pinecone for retrieval. Either equal to the Question (for standalone questions) or a rewritten version of it (for follow-up questions). The output of the query transformer. The distinction matters: retrieval quality depends on the Query, not the Question.

### Source
A citation attached to an answer, pointing to the specific Chunk that contributed to it. User-facing fields: Document title, one-based page number, and a short text excerpt. The reranker score is internal and not exposed to the user. Raw filesystem paths are not Sources — a Source always identifies a Document by title.

### Retrieval
The first stage of the Retrieval Pipeline: fast approximate nearest-neighbour search against Pinecone that returns a broad candidate set of Chunks (k=15). Do not use "search" as a synonym.

### Reranking
The second stage of the Retrieval Pipeline: scoring the candidate Chunks with a cross-encoder or Voyage reranker to select the top-k most relevant. Improves precision over raw vector similarity alone.

### Retrieval Pipeline
The two-stage process: Retrieval → Reranking. Together they produce the ranked Chunks passed to the LLM for answer generation. The shape of this pipeline is preserved across the FAISS→Pinecone and local→Voyage migrations.

### Answer
The LLM-generated text that responds to a Question. The streamed content. Text only — does not include Sources.

### Response
The full envelope delivered to the client: Answer text + Sources. What `ChatResponse` represents at the schema level. When streaming, the Answer tokens arrive first and Sources are delivered in a final frame.

### Provider
A swappable implementation of a capability behind a Protocol interface. Not a vendor — the vendor (e.g. Voyage, Anthropic, Groq) is what a Provider wraps. Three provider families exist: `LlmProvider` (answer generation + query rewriting), `EmbeddingProvider` (text → vector), `RerankerProvider` (Chunk scoring). A factory selects the active Provider per capability from config.
