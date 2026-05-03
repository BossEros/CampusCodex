# Developer Guide

## Purpose

This document explains how the Student Manual RAG Chatbot works, which technologies it uses, and what each backend module is responsible for.

Use this as the shared reference for development decisions, onboarding, and maintenance.

## System Summary

The system answers student-manual questions using Retrieval-Augmented Generation (RAG).

It works in two phases:

1. Offline indexing
   - load the PDF
   - split it into chunks
   - embed the chunks
   - save the FAISS index locally

2. Runtime question answering
   - load the saved FAISS index on backend startup
   - receive a user question
   - optionally rewrite vague questions for retrieval
   - retrieve relevant chunks
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
- HuggingFace Embeddings
- FAISS
- Groq API, Anthropic Claude API, or Gemini API

### Models
- Embedding model: `sentence-transformers/multi-qa-MiniLM-L6-cos-v1`
- Default chat model: `claude-haiku-4-5`

## Current Architecture

```text
User question
  -> FastAPI endpoint
  -> chat_service.py
  -> optional query rewrite
  -> FAISS similarity search
  -> retrieved chunks
  -> configured LLM provider
  -> answer + source excerpts
```

Offline indexing flow:

```text
student_manual_2019.pdf
  -> pdf_loader.py
  -> text_chunker.py
  -> vector_store.py
  -> saved FAISS index on disk
```

## Backend Module Responsibilities

### `backend/app/main.py`

Purpose:
- create the FastAPI app
- load the FAISS index once at startup
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
- `llm_provider`
- `llm_model_name`
- `embedding_model_name`
- `faiss_index_path`
- `pdf_path`
- `retrieval_candidate_k`
- `reranked_top_k`
- `reranker_model_name`
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
- create the embedding model
- build the FAISS vector store from chunks
- save the FAISS index to disk
- load the FAISS index from disk

Key point:
- FAISS acts as the local vector database layer for this project
- embeddings are stored and searched locally

Current embedding model:
- `sentence-transformers/multi-qa-MiniLM-L6-cos-v1`

Reason for this choice:
- better aligned with question-to-passage retrieval than a generic similarity embedding
- lightweight enough for a local project

### `backend/app/rag/chat_service.py`

Purpose:
- perform runtime retrieval and answer generation

Current responsibilities:
- validate the question
- rewrite the question for retrieval when enabled
- retrieve relevant chunks from FAISS
- build prompt context
- call the configured LLM provider
- return the answer, source excerpts, and page metadata when available

Design rule:
- no indexing logic belongs here
- this file should only handle online RAG behavior

Important note about scores:
- the returned `score` is a retrieval value from FAISS
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

### `backend/app/scripts/build_index.py`

Purpose:
- orchestrate the offline indexing workflow

Current flow:
1. load the source PDF
2. split it into chunks
3. print chunk count
4. print sample chunk previews
5. build the FAISS vector store
6. save the index to disk

When to run it:
- first-time project setup
- when the source PDF changes
- when chunking settings change
- when the embedding model changes

When not to run it:
- not on every chat request
- not as part of normal API request handling

## Data and Storage

### Source PDF

Expected path:

```text
data/raw/student_manual_2019.pdf
```

### FAISS Index

Expected path:

```text
data/indexes/faiss_student_manual/
```

The index is:
- built in memory
- saved to disk
- loaded back into memory at API startup

## Runtime Behavior

### Offline indexing phase

This happens through `backend/app/scripts/build_index.py`.

Detailed sequence:
1. `pdf_loader.py` reads the PDF
2. `text_chunker.py` splits it into chunks
3. `vector_store.py` embeds the chunks and builds FAISS
4. the FAISS index is saved locally

### Online chat phase

This happens when the FastAPI app is running.

Detailed sequence:
1. `main.py` loads the FAISS index once during startup
2. the client sends a question to `POST /api/chat`
3. `query_transformer.py` optionally rewrites vague questions for retrieval
4. `chat_service.py` retrieves and reranks the top matching chunks
5. the retrieved chunks are combined into context
6. the configured LLM provider generates an answer from that context
7. the API returns the answer and source previews

## Development Rules

- Keep module responsibilities narrow.
- Reuse existing loader, chunker, and vector-store helpers instead of duplicating logic.
- Keep secrets in `.env`, not in source files.
- Keep `main.py` thin.
- Do not rebuild the index during normal request handling.
- Keep path assumptions consistent with the actual repo structure.

## Current Constraints

- Page numbers come from PDF document metadata and should be treated as citations to extracted source pages.
- Retrieval quality depends heavily on chunking and embedding quality.
- The current frontend/backend integration assumes local development.

## Practical Commands

From `backend/`:

Install dependencies:

```powershell
pip install -r requirements.txt
```

Build the index:

```powershell
python app/scripts/build_index.py
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
