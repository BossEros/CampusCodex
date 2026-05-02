from langchain_core.documents import Document
from sentence_transformers import CrossEncoder
from app.core.config import settings

reranker_model: CrossEncoder | None = None


def get_reranker_model() -> CrossEncoder:
    global reranker_model
    
    if reranker_model is None:
        reranker_model = CrossEncoder(settings.reranker_model_name)
        
    return reranker_model


def rerank_documents(
    question: str,
    documents_with_scores: list[tuple[Document, float]],
    top_k: int,
) -> list[tuple[Document, float]]:
    if not question.strip():
        raise ValueError("Question must not be empty")
    
    if not documents_with_scores:
        return []
    
    documents = [document for document, _ in documents_with_scores]
    document_texts = [document.page_content for document in documents]
    
    reranker = get_reranker_model()
    ranked_results = reranker.rank(question, document_texts, top_k=top_k)
    
    reranked_documents: list[tuple[Document, float]] = []
    
    for ranked_result in ranked_results:
        document_index = ranked_result["corpus_id"]
        reranker_score = ranked_result["score"]
        reranked_documents.append(
            (documents[document_index], float(reranker_score))
        )
    
    return reranked_documents

