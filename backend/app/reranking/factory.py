from app.core.config import settings
from app.reranking.provider import RerankerProvider


def create_reranker_provider() -> RerankerProvider:
    provider_name = settings.reranker_provider.lower().strip()

    if provider_name == "cross_encoder":
        from app.reranking.cross_encoder_provider import CrossEncoderRerankerProvider

        return CrossEncoderRerankerProvider()

    if provider_name == "voyage":
        from app.reranking.voyage_provider import VoyageRerankerProvider

        return VoyageRerankerProvider()

    raise ValueError(f"Unsupported reranker provider: {settings.reranker_provider}")
