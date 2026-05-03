from app.core.config import settings
from app.llm.factory import create_llm_provider


def rewrite_query_for_retrieval(question: str) -> str:
    if not question.strip():
        raise ValueError("Question must not be empty")

    if not settings.enable_query_rewrite:
        return question

    llm_provider = create_llm_provider()
    rewritten_query = llm_provider.rewrite_query(question)

    return rewritten_query.strip() or question
