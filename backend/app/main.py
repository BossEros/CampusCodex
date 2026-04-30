from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from app.core.config import settings
from app.rag.chat_service import answer_questions
from app.rag.vector_store import load_faiss_vector_store
from app.schemas.chat import ChatRequest, ChatResponse

vector_store = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global vector_store
    vector_store = load_faiss_vector_store(settings.faiss_index_path)
    yield
    
app = FastAPI(
    title="Student Manual RAG Chatbot",
    lifespan=lifespan
)

@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/api/index/status")
def get_index_status() -> dict:
    return {
        "index_loaded": vector_store is not None,
        "pdf_path": settings.pdf_path,
        "index_path": settings.faiss_index_path,
        "embedding_model": settings.embedding_model_name,
        "retrieval_top_k": settings.retrieval_top_k,
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    if vector_store is None:
        raise HTTPException(status_code=503, detail="FAISS index is not loaded.")

    try:
        result = answer_questions(
            vector_store=vector_store,
            question=request.question,
        )
        return ChatResponse(**result)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail="Failed to process chat request.") from error