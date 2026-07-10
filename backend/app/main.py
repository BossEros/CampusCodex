from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.rag.chat_service import answer_questions
from app.rag.vector_store import (
    create_pinecone_client,
    describe_vector_store_runtime,
    load_runtime_vector_store,
)
from app.schemas.chat import ChatRequest, ChatResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    pinecone_client = create_pinecone_client()
    app.state.pinecone_client = pinecone_client
    app.state.vector_store = load_runtime_vector_store(pinecone_client)
    yield
    
app = FastAPI(
    title="Student Manual RAG Chatbot",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/api/index/status")
def get_index_status(request: Request) -> dict:
    vector_store = getattr(request.app.state, "vector_store", None)
    runtime_details = (
        describe_vector_store_runtime(vector_store)
        if vector_store is not None
        else None
    )

    return {
        "index_loaded": vector_store is not None,
        "pdf_path": settings.pdf_path,
        "vector_store_provider": runtime_details.provider_name if runtime_details else None,
        "vector_store_namespace": runtime_details.namespace if runtime_details else None,
        "pinecone_index_name": runtime_details.index_name if runtime_details else settings.pinecone_index_name,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.voyage_embedding_model_name,
        "retrieval_candidate_k": settings.retrieval_candidate_k,
        "reranked_top_k": settings.reranked_top_k,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model_name,
        "reranker_provider": settings.reranker_provider,
        "reranker_model": settings.voyage_reranker_model_name,
        "enable_query_rewrite": settings.enable_query_rewrite,
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: Request, payload: ChatRequest) -> ChatResponse:
    vector_store = getattr(request.app.state, "vector_store", None)
    if vector_store is None:
        raise HTTPException(status_code=503, detail="Vector store is not loaded.")

    try:
        result = answer_questions(
            vector_store=vector_store,
            question=payload.question,
            history=payload.history,
        )
        return ChatResponse(**result)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail="Failed to process chat request.") from error
