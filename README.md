# Student Manual RAG Chatbot

RAG chatbot for the University of Cebu Student Manual 2019 PDF.

This project has two major parts:
- `backend/`: FastAPI API, RAG pipeline, Pinecone-backed retrieval, provider-based answer generation
- `frontend/`: React/Vite client for the chat UI

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

## Project Structure

```text
RAG Project/
  backend/
    app/
      main.py
      core/config.py
      rag/
        pdf_loader.py
        text_chunker.py
        vector_store.py
        chat_service.py
      schemas/chat.py
      scripts/seed_pinecone_corpus.py
    requirements.txt
    .env.example
  frontend/
  data/
    raw/student_manual_2019.pdf
  README.md
  DEVELOPER_GUIDE.md
```

## Backend Setup

Run these commands from `backend/`.

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

For Linux / macOS (bash/zsh):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

For Linux / macOS (with the venv activated):

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

### 3. Configure environment variables

Create `backend/.env` from `backend/.env.example`.

Minimum required values for the default Claude/Anthropic setup:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
LLM_PROVIDER=anthropic
LLM_MODEL_NAME=claude-haiku-4-5
```

To use Gemini instead:

```env
GEMINI_API_KEY=your_gemini_api_key_here
LLM_PROVIDER=gemini
LLM_MODEL_NAME=gemini-2.5-flash
```

To use Groq instead, set `LLM_PROVIDER=groq`, provide `GROQ_API_KEY`, and choose a Groq-supported `LLM_MODEL_NAME`.

Current backend settings are loaded from `backend/app/core/config.py`.

## Seed the Pinecone Corpus

Before running the API against Pinecone, seed the student manual corpus into Pinecone.

Expected PDF location:

```text
data/raw/student_manual_2019.pdf
```

From `backend/`:

```powershell
python app/scripts/seed_pinecone_corpus.py
```

Note: the `python app/scripts/seed_pinecone_corpus.py` command is the same on Linux/macOS when the venv is activated.

What this does:
- loads the PDF as page-level documents with page metadata
- splits it into overlapping chunks
- embeds the chunks with the configured embedding provider (Voyage by default)
- upserts the vectors into Pinecone

By default it seeds **both** the `benchmark` namespace (the fixed eval corpus) and the `shared_kb` namespace (what `/api/chat` reads from), since this project currently has a single canonical corpus and no separate admin-uploaded content yet. Pass `--namespaces benchmark` or `--namespaces shared_kb` to seed only one.

Required Pinecone/Voyage environment variables (see `backend/.env.example`): `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, `PINECONE_SHARED_NAMESPACE`, `PINECONE_BENCHMARK_NAMESPACE`, `VOYAGE_API_KEY`, `VOYAGE_EMBEDDING_MODEL_NAME`, `VOYAGE_RERANKER_MODEL_NAME`. There is no local fallback — the backend requires a configured Pinecone index to start.

## Run the Backend

From `backend/`:

```powershell
uvicorn app.main:app --reload
```

Note: the `uvicorn app.main:app --reload` command is the same on Linux/macOS when the venv is activated.

Backend URL:

```text
http://localhost:8000
```

Useful endpoints:
- `GET /health`
- `GET /api/index/status`
- `POST /api/chat`

## Run the Frontend

From `frontend/`:

```powershell
npm install
npm run dev
```

Note: `npm install` and `npm run dev` are the same on Linux/macOS and Windows.

Frontend URL:

```text
http://localhost:5173
```

## API Contract

### `POST /api/chat`

Request:

```json
{
  "question": "What are the requirements for transfer students?"
}
```

Response:

```json
{
  "answer": "The answer grounded in the student manual.",
  "sources": [
    {
      "excerpt": "A short preview of a retrieved chunk...",
      "score": 7.42,
      "page_number": 69,
      "source": "C:\\Users\\...\\data\\raw\\student_manual_2019.pdf"
    }
  ]
}
```

## Notes

- The PDF is loaded with `PDFPlumberLoader`, which returns page-level documents.
- Page metadata is preserved through chunking and returned with retrieved sources when available.
- Vague student questions can be rewritten for retrieval when `ENABLE_QUERY_REWRITE=true`.
- Pinecone retrieves candidate chunks first, then Voyage reranks the best sources.
- The Pinecone client is created once and the vector store is loaded once on backend startup.

For architecture details and module responsibilities, see [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md).
