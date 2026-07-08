from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RankedDocumentScore:
    index: int
    score: float


class RerankerProvider(Protocol):
    def rerank(
        self,
        question: str,
        documents: list[str],
        top_k: int,
    ) -> list[RankedDocumentScore]:
        """Rerank candidate document texts for a question."""
