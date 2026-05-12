import re

from app.core.config import settings
from app.llm.factory import create_llm_provider
from app.schemas.chat import ChatMessage


def get_last_user_question(history: list[ChatMessage]) -> str:
    for message in reversed(history):
        if message.role == "user" and message.content and message.content.strip():
            return message.content.strip()

    return ""


DEPENDENT_FOLLOW_UP_PATTERNS = (
    r"^(what|how)\s+about\s+(it|them|that|those|these)\??$",
    r"^(what|how)\s+about\s+(the\s+)?(requirements|documents|process|procedure|steps|fees|schedule|deadline|deadlines|rules|policy|policies|qualifications?)\??$",
    r"^(and|also|then)\s+(what|how|when|where|why)\b.*$",
    r"^(and|also|then)\s+(the\s+)?(requirements|documents|process|procedure|steps|fees|schedule|deadline|deadlines|rules|policy|policies|qualifications?)\??$",
)


def should_use_previous_question(question: str, previous_user_question: str) -> bool:
    normalized_question = " ".join(question.lower().strip().split())

    if not normalized_question:
        return False

    if not previous_user_question.strip():
        return (
            normalized_question.startswith("what about")
            or normalized_question.startswith("how about")
            or len(normalized_question.split()) <= 4
        )

    return any(
        re.match(pattern, normalized_question)
        for pattern in DEPENDENT_FOLLOW_UP_PATTERNS
    )


def rewrite_query_for_retrieval(
    question: str,
    history: list[ChatMessage] | None = None,
) -> str:
    if not question.strip():
        raise ValueError("Question must not be empty")

    previous_user_question = get_last_user_question(history or [])

    if not settings.enable_query_rewrite:
        return question

    if not should_use_previous_question(question, previous_user_question):
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
