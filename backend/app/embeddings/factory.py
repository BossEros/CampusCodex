from app.core.config import settings
from app.embeddings.provider import EmbeddingProvider


def create_embedding_provider() -> EmbeddingProvider:
    provider_name = settings.embedding_provider.lower().strip()

    if provider_name == "voyage":
        from app.embeddings.voyage_provider import VoyageEmbeddingProvider

        return VoyageEmbeddingProvider()

    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")
