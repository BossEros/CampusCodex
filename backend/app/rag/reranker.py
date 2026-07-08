from langchain_core.documents import Document
from app.reranking.factory import create_reranker_provider


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
    reranker_provider = create_reranker_provider()
    ranked_results = reranker_provider.rerank(question, document_texts, top_k=top_k)
    
    reranked_documents: list[tuple[Document, float]] = []
    
    for ranked_result in ranked_results:
        document_index = ranked_result.index
        reranker_score = ranked_result.score
        reranked_documents.append(
            (documents[document_index], float(reranker_score))
        )
    
    return reranked_documents

