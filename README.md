# CampusCodex

A source-cited RAG chatbot for the University of Cebu Student Manual — built as a production-style evolution of a simple document Q&A demo, with a managed retrieval stack, a provider-agnostic LLM layer, and citation-backed answers.

## Why this exists

Most RAG demos hardcode a local vector index and a single LLM call. This project is built the way a real retrieval system would be: retrieval and generation are behind swappable provider interfaces, the vector store is a managed service instead of an in-memory index, and the eval corpus is isolated from the runtime corpus so answer-quality benchmarking stays meaningful as the knowledge base grows.

## Key Features

- **Source-cited answers** — every answer links back to the exact document, page, and excerpt it was grounded in
- **Two-stage retrieval** — fast approximate search (Pinecone) followed by cross-query reranking (Voyage) for precision
- **Provider-agnostic architecture** — LLM, embedding, and reranker providers are each behind a `Protocol` + factory, selected purely by config (`LLM_PROVIDER`, `EMBEDDING_PROVIDER`, `RERANKER_PROVIDER`); swap Anthropic for Groq or Gemini without touching the RAG pipeline
- **Follow-up aware retrieval** — vague or context-dependent questions ("what about that?") are rewritten against chat history before retrieval
- **Eval-safe corpus isolation** — the benchmark corpus and the live/demo corpus live in separate Pinecone namespaces (`benchmark` vs `shared_kb`) in the same index, so nothing ever leaks between "what we measure" and "what users query"

## Architecture

```text
                       ┌─────────────────────┐
 User question ───────▶│   FastAPI backend    │
                       └──────────┬───────────┘
                                  │
                     optional query rewrite (LLM)
                                  │
                                  ▼
                    ┌──────────────────────────┐
                    │  Pinecone similarity      │  candidate chunks (top-k)
                    │  search (shared_kb ns)    │
                    └──────────────┬────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────┐
                    │  Voyage reranking          │  reranked top-n
                    └──────────────┬────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────┐
                    │  Configured LLM provider   │  answer + citations
                    │  (Anthropic / Groq / Gemini)│
                    └──────────────┬────────────┘
                                   │
                                   ▼
                          Answer + page-linked sources
```

**Offline corpus seeding** (`seed_pinecone_corpus.py`): PDF → page-level documents → overlapping chunks → Voyage embeddings → upserted into Pinecone, into the `benchmark` and/or `shared_kb` namespace.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, Vite |
| Backend | FastAPI, Uvicorn, Pydantic / pydantic-settings |
| Vector store | Pinecone (serverless, 1024-dim, cosine) |
| Embeddings & reranking | Voyage AI (`voyage-3.5`, `rerank-2.5`) |
| LLM | Anthropic Claude (default), Groq, or Gemini — swappable via config |
| PDF ingestion | LangChain `PDFPlumberLoader` + `RecursiveCharacterTextSplitter` |

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js LTS
- API keys: [Pinecone](https://www.pinecone.io/), [Voyage AI](https://www.voyageai.com/), and one of Anthropic / Groq / Gemini

### 1. Backend setup

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # then fill in your API keys
```

Minimum `.env` values for the default Anthropic setup:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
LLM_PROVIDER=anthropic
LLM_MODEL_NAME=claude-haiku-4-5

VOYAGE_API_KEY=your_voyage_api_key_here
PINECONE_API_KEY=your_pinecone_api_key_here
```

See `backend/.env.example` for the full list of supported variables (alternate LLM providers, namespace names, retrieval/reranking tuning knobs).

### 2. Seed the knowledge base

The backend requires a populated Pinecone index — there is no local fallback.

```bash
python app/scripts/seed_pinecone_corpus.py
```

This loads `data/raw/student_manual_2019.pdf`, chunks it, embeds it with Voyage, and upserts the vectors into both the `benchmark` and `shared_kb` namespaces by default. Pass `--namespaces shared_kb` (or `benchmark`) to target just one.

### 3. Run the backend

```bash
uvicorn app.main:app --reload
```

API available at `http://localhost:8000` — see `GET /health` and `GET /api/index/status` for a quick sanity check.

### 4. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

UI available at `http://localhost:5173`.

## API Reference

### `POST /api/chat`

Request:

```json
{
  "question": "What are the requirements for transfer students?",
  "history": [
    { "role": "user", "content": "Tell me about admissions." },
    { "role": "assistant", "content": "Admissions cover..." }
  ]
}
```

Response:

```json
{
  "answer": "Transfer students must submit...",
  "sources": [
    {
      "excerpt": "A short preview of a retrieved chunk...",
      "score": 0.83,
      "title": "Student Manual 2019",
      "page_number": 24,
      "source": "data/raw/student_manual_2019.pdf"
    }
  ]
}
```

`history` is optional and only needed for follow-up questions. `score` is the reranker's relevance score, not a raw similarity distance.

### `GET /api/index/status`

Reports the active retrieval configuration — vector store provider/namespace, embedding/reranker/LLM model names, and retrieval tuning parameters. Useful for confirming the deployed backend is actually pointed at Pinecone and not misconfigured.

## Testing

```bash
cd backend
pytest
```

The suite covers provider factory selection, the retrieval seam, Pinecone metadata mapping into citations, and query-rewrite behavior — all against fakes/mocks, no live API calls required.

## Project Structure

```text
CampusCodex/
  backend/
    app/
      main.py                      # FastAPI app, lifespan, routes
      core/config.py                # Centralized settings (env-backed)
      llm/                          # LlmProvider protocol + Anthropic/Groq/Gemini adapters
      embeddings/                   # EmbeddingProvider protocol + Voyage adapter
      reranking/                    # RerankerProvider protocol + Voyage adapter
      rag/
        pdf_loader.py                # PDF -> page-level documents
        text_chunker.py              # Chunking
        vector_store.py              # VectorStore seam + Pinecone adapter
        chat_service.py              # Retrieval -> rerank -> context -> answer
        query_transformer.py         # Follow-up question rewriting
      schemas/chat.py                # Request/response contracts
      scripts/seed_pinecone_corpus.py
    requirements.txt
    .env.example
  frontend/                        # React/Vite chat UI
  data/raw/                        # Source PDF
```

## Roadmap

This is an actively evolving portfolio project. Planned next steps include async request handling, persistent auth-scoped chat history, multi-document admin ingestion, token-by-token streaming, and a RAGAS-based answer-quality evaluation harness over the frozen benchmark corpus.
