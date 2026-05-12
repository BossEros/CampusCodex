from app.core.config import settings
from app.llm.factory import create_llm_provider
from app.schemas.chat import ChatMessage


def get_last_user_question(history: list[ChatMessage]) -> str:
    for message in reversed(history):
        if message.role == "user" and message.content and message.content.strip():
            return message.content.strip()

    return ""


def rewrite_query_for_retrieval(
    question: str,
    history: list[ChatMessage] | None = None,
) -> str:
    if not question.strip():
        raise ValueError("Question must not be empty")

    previous_user_question = get_last_user_question(history or [])

    if not settings.enable_query_rewrite:
        return question

    llm_provider = create_llm_provider()
    if previous_user_question:
        rewrite_input = (
            "Previous student question:\n"
            f"{previous_user_question}\n\n"
            "Latest student message:\n"
            f"{question}"
        )
    else:
        rewrite_input = question

    rewritten_query = llm_provider.rewrite_query(rewrite_input)

    return rewritten_query.strip() or question
