from typing import Protocol


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed document chunks for storage or retrieval workflows."""

    def embed_query(self, text: str) -> list[float]:
        """Embed a query string for retrieval workflows."""
