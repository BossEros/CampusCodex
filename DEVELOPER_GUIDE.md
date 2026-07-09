# Developer Guide

## Purpose

This document explains how the Student Manual RAG Chatbot works, which technologies it uses, and what each backend module is responsible for.

Use this as the shared reference for development decisions, onboarding, and maintenance.

## System Summary

The system answers student-manual questions using Retrieval-Augmented Generation (RAG).

It works in two phases:

1. Offline corpus seeding
   - load the PDF
   - split it into chunks
   - embed the chunks with Voyage
   - upsert the vectors into Pinecone (`benchmark` and `shared_kb` namespaces)

2. Runtime question answering
   - create the Pinecone client and load the vector store once on backend startup
   - receive a user question
   - optionally rewrite vague questions for retrieval
   - retrieve relevant chunks from Pinecone, then rerank with Voyage
   - send retrieved context to the configured LLM provider
   - return an answer and source previews

## Tech Stack

### Frontend
- React
- Vite
- JavaScript
- CSS

### Backend
- Python
- FastAPI
- Uvicorn
- Pydantic
- pydantic-settings

### RAG / AI
- LangChain
- PDFPlumberLoader
- RecursiveCharacterTextSplitter
- Pinecone (managed vector store)
- Voyage AI (embeddings and reranking)
- Groq API, Anthropic Claude API, or Gemini API

### Models
- Embedding model: `voyage-3.5`
- Reranker model: `rerank-2.5`
- Default chat model: `claude-haiku-4-5`

## Current Architecture

```text
User question
  -> FastAPI endpoint
  -> chat_service.py
  -> optional query rewrite
  -> Pinecone similarity search (shared_kb namespace)
  -> Voyage reranking
  -> retrieved chunks
  -> configured LLM provider
  -> answer + source excerpts
```

Offline corpus-seeding flow:

```text
student_manual_2019.pdf
  -> pdf_loader.py
  -> text_chunker.py
  -> Voyage embeddings
  -> upserted into Pinecone (benchmark + shared_kb namespaces)
```

## Backend Module Responsibilities

### `backend/app/main.py`

Purpose:
- create the FastAPI app
- create the Pinecone client and load the vector store once at startup
- expose HTTP endpoints
- delegate chat logic to the RAG service

Current routes:
- `GET /health`
- `GET /api/index/status`
- `POST /api/chat`

Design rule:
- keep `main.py` thin
- do not put PDF loading, chunking, or embedding logic here

### `backend/app/core/config.py`

Purpose:
- centralize environment-backed configuration

Current settings:
- `groq_api_key`
- `anthropic_api_key`
- `gemini_api_key`
- `voyage_api_key`
- `pinecone_api_key`
- `llm_provider`
- `llm_model_name`
- `embedding_provider`
- `voyage_embedding_model_name`
- `reranker_provider`
- `voyage_reranker_model_name`
- `pinecone_index_name`
- `pinecone_shared_namespace`
- `pinecone_benchmark_namespace`
- `pdf_path`
- `retrieval_candidate_k`
- `reranked_top_k`
- `enable_query_rewrite`

Design rule:
- secrets and environment-specific settings belong here
- do not hardcode them across service files

### `backend/app/rag/pdf_loader.py`

Purpose:
- load the source PDF into LangChain `Document` objects

Current design:
- uses `PDFPlumberLoader`
- loads the PDF as page-level LangChain `Document` objects

Reason for this choice:
- preserves page metadata for retrieved source citations
- improves extraction behavior for layout-heavy PDF content

Tradeoff:
- text continuity across page boundaries depends on chunk overlap rather than single-document extraction

### `backend/app/rag/text_chunker.py`

Purpose:
- split loaded documents into retrieval-ready chunks

Current chunking strategy:
- `RecursiveCharacterTextSplitter`
- `chunk_size=800`
- `chunk_overlap=120`

Reason for this choice:
- simple and standard baseline for RAG
- overlap preserves context around chunk boundaries
- works well for plain text extracted from PDFs

Output:
- a list of chunk-sized LangChain `Document` objects

### `backend/app/rag/vector_store.py`

Purpose:
- define the `VectorStore` retrieval seam (`search_similar_chunks`)
- create the Pinecone client and adapter
- map Pinecone query matches back into `Document` + score pairs for reranking

Key point:
- Pinecone is the managed vector database layer for this project; there is no local fallback
- `chat_service.py` depends only on the `VectorStore` protocol, not on the Pinecone SDK directly

Current embedding model:
- `voyage-3.5` (via `app/embeddings/voyage_provider.py`, selected through `app/embeddings/factory.py`)

Reason for this choice:
- managed, API-based embeddings avoid running heavy local ML models on a free-tier host
- aligned with the project's `EmbeddingProvider`/`RerankerProvider` protocol pattern, which mirrors the existing `LlmProvider` pattern

### `backend/app/rag/chat_service.py`

Purpose:
- perform runtime retrieval and answer generation

Current responsibilities:
- validate the question
- rewrite the question for retrieval when enabled
- retrieve relevant chunks from Pinecone, then rerank with the configured `RerankerProvider`
- build prompt context
- call the configured LLM provider
- return the answer, source excerpts, and page metadata when available

Design rule:
- no indexing/seeding logic belongs here
- this file should only handle online RAG behavior

Important note about scores:
- the returned `score` is the reranker's relevance score, not the raw Pinecone similarity score
- treat it as a technical retrieval metric, not a user-facing confidence guarantee

### `backend/app/schemas/chat.py`

Purpose:
- define the request and response schema for the chat API

Current models:
- `ChatRequest`
- `ChatSource`
- `ChatResponse`

Why this matters:
- keeps the API contract explicit
- supports FastAPI validation
- makes responses predictable for the frontend

### `backend/app/scripts/seed_pinecone_corpus.py`

Purpose:
- orchestrate the offline corpus-seeding workflow for Pinecone

Current flow:
1. load the source PDF
2. split it into chunks
3. print chunk count
4. embed the chunks once with the configured embedding provider (Voyage by default)
5. upsert the resulting vectors into one or more Pinecone namespaces (`benchmark` and `shared_kb` by default)

When to run it:
- first-time project setup
- when the source PDF changes
- when chunking settings change
- when the embedding model changes

When not to run it:
- not on every chat request
- not as part of normal API request handling

Note: there is no local vector-store fallback. The backend requires a configured Pinecone index (`PINECONE_API_KEY`, `PINECONE_INDEX_NAME`) to start; see `backend/.env.example`.

## Data and Storage

### Source PDF

Expected path:

```text
data/raw/student_manual_2019.pdf
```

### Pinecone Index

The corpus lives in a Pinecone serverless index (`PINECONE_INDEX_NAME`, dimension 1024, cosine metric), split across two namespaces:
- `benchmark` — fixed eval corpus, seeded from the canonical student manual only
- `shared_kb` — runtime corpus that `/api/chat` reads from

Vectors are:
- embedded offline by `seed_pinecone_corpus.py`
- upserted into Pinecone
- queried at runtime via the Pinecone client created once at API startup

## Runtime Behavior

### Offline indexing phase

This happens through `backend/app/scripts/seed_pinecone_corpus.py`.

Detailed sequence:
1. `pdf_loader.py` reads the PDF
2. `text_chunker.py` splits it into chunks
3. the configured embedding provider (Voyage) embeds the chunks
4. the vectors are upserted into Pinecone (`benchmark` and `shared_kb` namespaces by default)

### Online chat phase

This happens when the FastAPI app is running.

Detailed sequence:
1. `main.py` creates the Pinecone client and loads the vector store once during startup
2. the client sends a question to `POST /api/chat`
3. `query_transformer.py` optionally rewrites vague questions for retrieval
4. `chat_service.py` retrieves candidates from Pinecone and reranks them with Voyage
5. the retrieved chunks are combined into context
6. the configured LLM provider generates an answer from that context
7. the API returns the answer and source previews

## Development Rules

- Keep module responsibilities narrow.
- Reuse existing loader, chunker, and vector-store helpers instead of duplicating logic.
- Keep secrets in `.env`, not in source files.
- Keep `main.py` thin.
- Do not reseed Pinecone during normal request handling.
- Keep path assumptions consistent with the actual repo structure.

## Current Constraints

- Page numbers come from PDF document metadata and should be treated as citations to extracted source pages.
- Retrieval quality depends heavily on chunking and embedding quality.
- The current frontend/backend integration assumes local development.
- `benchmark` and `shared_kb` are separate Pinecone namespaces in the same index; eval scoring and app retrieval must never mix vectors between them.

## Practical Commands

From `backend/`:

Install dependencies:

```powershell
pip install -r requirements.txt
```

Seed the Pinecone corpus:

```powershell
python app/scripts/seed_pinecone_corpus.py
```

Run the API:

```powershell
uvicorn app.main:app --reload
```

From `frontend/`:

```powershell
npm install
npm run dev
```

## Future Improvement Areas

- add automated tests for indexing and chat endpoints
- improve frontend source display
- evaluate retrieval quality with a fixed question set
- consider reranking if retrieval quality becomes inconsistent
- normalize path handling and file placement if the backend layout changes
