from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_community.vectorstores import FAISS
from app.core.config import settings


SYSTEM_PROMPT = """
You are a helpful assistant for the University of Cebu Student Manual.

Answer only from the provided context.
If the answer is not in the context, say:
"The student manual does not provide enough information to answer that."

Keep the answer clear and concise.
""".strip()


def retrieve_relevant_chunks (
    vector_store: FAISS,
    question: str, 
) -> list[tuple[Document, float]]:
    if not question.strip():
        raise ValueError("Question must not be empty")
    
    return vector_store.similarity_search_with_score(question, k=settings.retrieval_top_k)

def build_context(documents_with_scores: list[tuple[Document, float]]) -> str: 
    context_parts: list[str] = []
    
    for index, (document, _) in enumerate(documents_with_scores, start=1):
        context_parts.append(f"Context {index}:\n{document.page_content}")
        
    return "\n\n".join(context_parts)

def generate_answer(
    question: str, 
    context: str,
) -> str:
    if not question.strip():
        raise ValueError("Question must not be empty")
    
    if not context.strip():
        raise "The student manual does not provide enough information to answer that."
    
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
                "score": float(score)
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