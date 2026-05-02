from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_community.vectorstores import FAISS
from app.core.config import settings
from app.rag.reranker import rerank_documents


SYSTEM_PROMPT = """
You are a helpful assistant for the University of Cebu Student Manual.

Answer only from the provided context.
If the information isn’t in the given context, go ahead and provide a useful answer based on what you know. Just slip in a brief, natural note that it might not be included in the student manual, without making it sound too formal or overly emphasized.

Keep the answer clear, properly formatted, and concise.
""".strip()

def retrieve_relevant_chunks (
    vector_store: FAISS,
    question: str, 
) -> list[tuple[Document, float]]:
    if not question.strip():
        raise ValueError("Question must not be empty")
    
    candidate_documents = vector_store.similarity_search_with_score(
        question,
        k=settings.retrieval_candidate_k
    )
    
    return rerank_documents(
        question=question,
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

    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is required to generate answers.")
    
    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model_name,
        temperature=0
    )
    
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            (
                "human",
                "Question:\n{question}\n\nContext:\n{context}"
            ),
        ]
    )
    
    chain = prompt | llm
    response = chain.invoke(
        {
            "question": question,
            "context": context,
        }
    )
    
    return response.content.strip()

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
    vector_store: FAISS,
    question: str,
) -> dict:
    documents_with_scores = retrieve_relevant_chunks(
        vector_store,
        question,
    )

    context = build_context(documents_with_scores)
    answer = generate_answer(
        question,
        context,
    )
    sources = build_sources(documents_with_scores)
    
    return {
        "answer": answer,
        "sources": sources
    }
