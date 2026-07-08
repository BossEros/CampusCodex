import voyageai

from app.core.config import settings
from app.reranking.provider import RankedDocumentScore


class VoyageRerankerProvider:
    def __init__(self) -> None:
        self._client = voyageai.Client(api_key=settings.voyage_api_key)

    def rerank(
        self,
        question: str,
        documents: list[str],
        top_k: int,
    ) -> list[RankedDocumentScore]:
        if not documents:
            return []

        response = self._client.rerank(
            question,
            documents,
            model=settings.voyage_reranker_model_name,
            top_k=top_k,
        )
        return [
            RankedDocumentScore(index=result.index, score=float(result.relevance_score))
            for result in response.results
        ]
