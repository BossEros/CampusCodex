from sentence_transformers import CrossEncoder

from app.core.config import settings
from app.reranking.provider import RankedDocumentScore

cross_encoder_model: CrossEncoder | None = None


def get_cross_encoder_model() -> CrossEncoder:
    global cross_encoder_model

    if cross_encoder_model is None:
        cross_encoder_model = CrossEncoder(settings.reranker_model_name)

    return cross_encoder_model


class CrossEncoderRerankerProvider:
    def rerank(
        self,
        question: str,
        documents: list[str],
        top_k: int,
    ) -> list[RankedDocumentScore]:
        if not documents:
            return []

        ranked_results = get_cross_encoder_model().rank(question, documents, top_k=top_k)
        return [
            RankedDocumentScore(
                index=ranked_result["corpus_id"],
                score=float(ranked_result["score"]),
            )
            for ranked_result in ranked_results
        ]
