from typing import Protocol


class LlmProvider(Protocol):
    def generate_answer(self, question: str, context: str) -> str:
        """Generate an answer using the provided question and retrieved context."""
        ...
        
    def rewrite_query(self, question: str) -> str:
        """Rewrite a vague student question into a clearer retrieval query."""
        ...
