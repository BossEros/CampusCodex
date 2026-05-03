from typing import Any

from app.core.config import settings
from app.llm.prompts import ANSWER_SYSTEM_PROMPT, QUERY_REWRITE_SYSTEM_PROMPT
from app.llm.provider import LlmProvider


class AnthropicLlmProvider(LlmProvider):
    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise ValueError("Anthropic API Key is required to generate answers.")

        from anthropic import Anthropic

        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model_name = settings.llm_model_name

    def generate_answer(self, question: str, context: str) -> str:
        if not question.strip():
            raise ValueError("Question must not be empty")

        if not context.strip():
            return "The student manual does not provide enough information to answer that."

        user_message = f"Question:\n{question}\n\nContext:\n{context}"
        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=1024,
            temperature=0,
            system=ANSWER_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": user_message,
                }
            ],
        )

        return self._extract_text(response).strip()

    def rewrite_query(self, question: str) -> str:
        if not question.strip():
            raise ValueError("Question must not be empty")

        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=128,
            temperature=0,
            system=QUERY_REWRITE_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Student question:\n{question}",
                }
            ],
        )
        rewritten_query = self._extract_text(response).strip()

        return rewritten_query or question

    def _extract_text(self, response: Any) -> str:
        text_parts: list[str] = []

        for content_block in response.content:
            if getattr(content_block, "type", None) == "text":
                text_parts.append(content_block.text)

        return "".join(text_parts)
