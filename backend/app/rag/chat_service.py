from typing import TYPE_CHECKING

from langchain_core.documents import Document
from app.core.config import settings
from app.rag.reranker import rerank_documents
from app.llm.factory import create_llm_provider
from app.rag.query_transformer import rewrite_query_for_retrieval
from app.schemas.chat import ChatMessage

if TYPE_CHECKING:
    from langchain_community.vectorstores import FAISS


def retrieve_relevant_chunks(
    vector_store: "FAISS",
    retrieval_query: str,
    reranking_question: str,
) -> list[tuple[Document, float]]:
    if not retrieval_query.strip():
        raise ValueError("Retrieval query must not be empty")

    if not reranking_question.strip():
        raise ValueError("Reranking question must not be empty")
    
    candidate_documents = vector_store.similarity_search_with_score(
        retrieval_query,
        k=settings.retrieval_candidate_k
    )

    return rerank_documents(
        question=reranking_question,
        documents_with_scores=candidate_documents,
        top_k=settings.reranked_top_k,
    )

def build_context(documents_with_scores: list[tuple[Document, float]]) -> str: 
    context_parts: list[str] = []
    
    for index, (document, _) in enumerate(documents_with_scores, start=1):
        page_number = get_display_page_number(document)
        page_label = f"Page {page_number}" if page_number is not None else "Page unknown"
        context_parts.append(f"Context {index} ({page_label}):\n{document.page_content}")
        
    return "\n\n".join(context_parts)

def generate_answer(
    question: str, 
    context: str,
) -> str:
    if not question.strip():
        raise ValueError("Question must not be empty")
    
    if not context.strip():
        return "The student manual does not provide enough information to answer that."

    llm_provider = create_llm_provider()
    
    return llm_provider.generate_answer(
        question=question,
        context=context,
    )
   

def get_display_page_number(document: Document) -> int | None:
    page_number = document.metadata.get("page")

    if page_number is None:
        return None

    try:
        return int(page_number) + 1
    except (TypeError, ValueError):
        return None


def build_sources(
    documents_with_scores: list[tuple[Document, float]],
    excerpt_length: int = 220
) -> list[dict]:
    sources: list[dict] = []
    
    for document, score in documents_with_scores:
        excerpt = document.page_content[:excerpt_length].replace("\n", " ").strip()
        
        sources.append(
            {
                "excerpt": excerpt,
                "score": float(score),
                "page_number": get_display_page_number(document),
                "source": document.metadata.get("source"),
            }
        )
        
    return sources

def answer_questions(
    vector_store: "FAISS",
    question: str,
    history: list[ChatMessage] | None = None,
) -> dict:
    resolved_question = rewrite_query_for_retrieval(question, history=history)
    
    documents_with_scores = retrieve_relevant_chunks(
        vector_store=vector_store,
        retrieval_query=resolved_question,
        reranking_question=resolved_question,
    )

    context = build_context(documents_with_scores)
    answer = generate_answer(
        resolved_question,
        context,
    )
    sources = build_sources(documents_with_scores)
    
    return {
        "answer": answer,
        "sources": sources
    }
