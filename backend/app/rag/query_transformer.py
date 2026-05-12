from app.core.config import settings
from app.llm.factory import create_llm_provider
from app.schemas.chat import ChatMessage


def format_history_for_rewrite(history: list[ChatMessage], max_messages: int = 6) -> str:
    recent_messages = [
        message for message in history if message.content and message.content.strip()
    ][-max_messages:]

    if not recent_messages:
        return ""

    lines = [
        f"{message.role.capitalize()}: {message.content.strip()}"
        for message in recent_messages
    ]
    return "\n".join(lines)


def rewrite_query_for_retrieval(
    question: str,
    history: list[ChatMessage] | None = None,
) -> str:
    if not question.strip():
        raise ValueError("Question must not be empty")

    conversation_history = format_history_for_rewrite(history or [])

    if not settings.enable_query_rewrite:
        return question

    llm_provider = create_llm_provider()
    if conversation_history:
        rewrite_input = (
            "Conversation history:\n"
            f"{conversation_history}\n\n"
            "Latest student message:\n"
            f"{question}"
        )
    else:
        rewrite_input = question

    rewritten_query = llm_provider.rewrite_query(rewrite_input)

    return rewritten_query.strip() or question
