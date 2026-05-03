from app.core.config import settings
from app.llm.prompts import ANSWER_SYSTEM_PROMPT, QUERY_REWRITE_SYSTEM_PROMPT
from app.llm.provider import LlmProvider


class GeminiLlmProvider(LlmProvider):
    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise ValueError("Gemini API Key is required to generate answers.")

        from google import genai

        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model_name = settings.llm_model_name

    def generate_answer(self, question: str, context: str) -> str:
        if not question.strip():
            raise ValueError("Question must not be empty")

        if not context.strip():
            return "The student manual does not provide enough information to answer that."

        user_message = f"Question:\n{question}\n\nContext:\n{context}"
        answer = self._generate_text(
            system_instruction=ANSWER_SYSTEM_PROMPT,
            contents=user_message,
            max_output_tokens=1024,
        )

        return answer.strip()

    def rewrite_query(self, question: str) -> str:
        if not question.strip():
            raise ValueError("Question must not be empty")

        rewritten_query = self._generate_text(
            system_instruction=QUERY_REWRITE_SYSTEM_PROMPT,
            contents=f"Student question:\n{question}",
            max_output_tokens=128,
        ).strip()

        return rewritten_query or question

    def _generate_text(
        self,
        system_instruction: str,
        contents: str,
        max_output_tokens: int,
    ) -> str:
        from google.genai import types

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0,
                max_output_tokens=max_output_tokens,
            ),
        )

        return response.text or ""
