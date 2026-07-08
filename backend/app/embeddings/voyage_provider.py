import voyageai

from app.core.config import settings


class VoyageEmbeddingProvider:
    def __init__(self) -> None:
        self._client = voyageai.Client(api_key=settings.voyage_api_key)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        response = self._client.embed(
            texts,
            model=settings.voyage_embedding_model_name,
            input_type="document",
        )
        return [list(embedding) for embedding in response.embeddings]

    def embed_query(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Query text must not be empty")

        response = self._client.embed(
            [text],
            model=settings.voyage_embedding_model_name,
            input_type="query",
        )
        return list(response.embeddings[0])
