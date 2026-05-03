# Student Manual RAG Chatbot

RAG chatbot for the University of Cebu Student Manual 2019 PDF.

This project has two major parts:
- `backend/`: FastAPI API, RAG pipeline, FAISS index loading, provider-based answer generation
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
- HuggingFace Embeddings
- FAISS
- Groq API, Anthropic Claude API, or Gemini API

### Models
- Embedding model: `sentence-transformers/multi-qa-MiniLM-L6-cos-v1`
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
      scripts/build_index.py
    requirements.txt
    .env.example
  frontend/
  data/
    raw/student_manual_2019.pdf
    indexes/faiss_student_manual/
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

### 2. Install dependencies

```powershell
pip install -r requirements.txt
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

## Build the FAISS Index

Before running the API, build the local FAISS index from the student manual PDF.

Expected PDF location:

```text
data/raw/student_manual_2019.pdf
```

From `backend/`:

```powershell
python app/scripts/build_index.py
```

What this does:
- loads the PDF as page-level documents with page metadata
- splits it into overlapping chunks
- embeds the chunks
- builds the FAISS index
- saves it to `data/indexes/faiss_student_manual/`

## Run the Backend

From `backend/`:

```powershell
uvicorn app.main:app --reload
```

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
- FAISS retrieves candidate chunks first, then a CrossEncoder reranks the best sources.
- The FAISS index is built offline and loaded once on backend startup.

For architecture details and module responsibilities, see [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md).
