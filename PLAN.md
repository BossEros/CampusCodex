# Student Manual RAG Chatbot Plan

## Summary
Build a local **FastAPI + React** chatbot that answers questions from the **University of Cebu Student Manual 2019 PDF** using RAG.

Architecture:
- **React/Vite frontend**: chat UI with a visible sources panel.
- **FastAPI backend**: exposes chat/status endpoints.
- **RAG pipeline**: extract the PDF as a single continuous text flow, chunk text, embed locally with `sentence-transformers/all-MiniLM-L6-v2`, store/search with FAISS, generate final answers with Groq `llama-3.3-70b-versatile`.
- **Security rule**: never hardcode `GROQ_API_KEY`; revoke the key pasted earlier and use `.env`.

## Key Interfaces
Backend API:
- `GET /health`
  - Returns `{ "status": "ok" }`.
- `GET /api/index/status`
  - Returns whether the FAISS index exists, source PDF name, chunk count, and embedding model.
- `POST /api/chat`
  - Request: `{ "question": "What are the admission requirements for transferees?" }`
  - Response:
    ```json
    {
      "answer": "Clear answer grounded only in the manual.",
      "sources": [
        {
          "excerpt": "At the time of enrollment, a transferee must submit...",
          "score": 0.42
        }
      ]
    }
    ```

Project structure:
```text
RAG Project/
  backend/
    app/
      main.py
      core/config.py
      rag/pdf_loader.py
      rag/text_chunker.py
      rag/vector_store.py
      rag/chat_service.py
      schemas/chat.py
    scripts/build_index.py
    requirements.txt
    .env.example
  frontend/
    Vite React app
  data/
    raw/student_manual_2019.pdf
    indexes/faiss_student_manual/
  group_members.txt
  README.md
```

## Step-By-Step Build
1. **Prepare the project**
   - Create `backend`, `frontend`, and `data` folders.
   - Copy the manual into `data/raw/student_manual_2019.pdf`.
   - Create `group_members.txt`.
   - Add `.gitignore` for `.env`, virtual environments, cache folders, and generated FAISS index files if you do not want to submit them.

2. **Set up the backend**
   - Create a Python virtual environment.
   - Install:
     ```bash
     pip install fastapi uvicorn python-dotenv pydantic langchain langchain-community langchain-text-splitters langchain-groq langchain-huggingface faiss-cpu sentence-transformers pypdf
     ```
   - Put `GROQ_API_KEY=your_new_key_here` in `backend/.env`.

3. **Build the RAG index**
   - Use `PyPDFLoader(mode="single")` so the manual is extracted as one continuous text flow instead of being split at page boundaries.
   - Split text with `RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)`.
   - Embed with `HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")`.
   - Save FAISS locally to `data/indexes/faiss_student_manual/`.
   - Print chunk count and sample chunks to catch wrong-file mistakes like the wrong-source result from your notebook.
   - Make it explicit that page-level citations are not preserved in this mode.

4. **Build the chat service**
   - Load the FAISS index on backend startup.
   - Retrieve top `k=4` chunks for each question.
   - Prompt Groq with: "Answer only from the provided Student Manual context. If the answer is not in the context, say the manual does not provide enough information."
   - Return both the generated answer and the retrieved source snippets.

5. **Build the React UI**
   - Scaffold with:
     ```bash
     npm create vite@latest frontend -- --template react
     ```
   - Main layout:
     - Left: chat conversation and input.
     - Right: retrieved sources with excerpts and similarity scores.
     - Header: app name, index status, model name.
   - Use clean, school-project-friendly styling: readable, responsive, not overdecorated.

6. **Connect frontend to backend**
   - Run backend at `http://localhost:8000`.
   - Run frontend at `http://localhost:5173`.
   - Configure FastAPI CORS for `http://localhost:5173`.
   - Frontend sends `POST /api/chat` and renders answer + sources.

7. **Prepare the demo**
   - Add README commands:
     ```bash
     cd backend
     uvicorn app.main:app --reload
     ```
     ```bash
     cd frontend
     npm install
     npm run dev
     ```
   - Demo questions:
     - "What are the requirements for transfer students?"
     - "What services does the Guidance and Counseling Office provide?"
     - "What happens if a student commits theft?"
     - "What is the plot?" should refuse or say the manual lacks that information.

## Test Plan
- Backend:
  - `/health` returns `ok`.
  - Index status reports the correct PDF and nonzero chunk count.
  - A known manual question retrieves relevant source chunks.
  - An unrelated question does not hallucinate.
  - Missing `GROQ_API_KEY` returns a clear startup/config error.

- Frontend:
  - Empty question cannot be submitted.
  - Loading state appears while waiting.
  - Answer and sources render together.
  - API errors show a readable message.
  - Layout works on laptop screen for recording.

- Manual verification:
  - Ask at least 5 questions from different manual sections.
  - Check that retrieved source excerpts actually support the answer.
  - Record a short video showing startup, a successful answer, visible sources, and an out-of-scope refusal.

## Assumptions And References
- Groq is used for answer generation, not embeddings. Current Groq docs show chat/responses/models endpoints and production chat models, but no embedding model endpoint.
- Local embeddings use HuggingFace Sentence Transformers through LangChain.
- FAISS is selected because it matches your notebook and is enough for a fixed-document local demo.
- Single-flow PDF extraction is selected over page-based extraction because retrieval continuity matters more than page-number traceability for this project.
- REF MCP was attempted but unavailable due account credits, so official docs were located through Exa/web search.
- References: Groq docs `https://console.groq.com/docs/quickstart`, Groq models `https://console.groq.com/docs/models`, LangChain PyPDFLoader `https://python.langchain.com/docs/integrations/document_loaders/pypdfloader/`, LangChain FAISS `https://docs.langchain.com/oss/python/integrations/vectorstores/faiss`, FastAPI CORS `https://fastapi.tiangolo.com/tutorial/cors/`, Vite React `https://vite.dev/guide/`.
