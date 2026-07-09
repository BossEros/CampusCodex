from dataclasses import dataclass
from typing import Any, Protocol

from langchain_core.documents import Document

from app.core.config import settings
from app.embeddings.factory import create_embedding_provider


PINECONE_TEXT_METADATA_KEYS = ("chunk_text", "text", "page_content", "content")


class VectorStore(Protocol):
    def search_similar_chunks(
        self,
        query: str,
        limit: int,
    ) -> list[tuple[Document, float]]:
        """Return candidate chunks and raw retrieval scores for reranking."""


@dataclass(frozen=True)
class VectorStoreRuntimeDetails:
    provider_name: str
    index_name: str | None = None
    namespace: str | None = None


class PineconeVectorStoreAdapter:
    def __init__(
        self,
        index_client: Any,
        namespace: str,
        index_name: str,
    ) -> None:
        self._index_client = index_client
        self._embedding_provider = create_embedding_provider()
        self._namespace = namespace
        self.runtime_details = VectorStoreRuntimeDetails(
            provider_name="pinecone",
            index_name=index_name,
            namespace=namespace,
        )

    def search_similar_chunks(
        self,
        query: str,
        limit: int,
    ) -> list[tuple[Document, float]]:
        if not query.strip():
            raise ValueError("Query text must not be empty")

        query_embedding = self._embedding_provider.embed_query(query)
        query_response = self._index_client.query(
            vector=query_embedding,
            top_k=limit,
            namespace=self._namespace,
            include_metadata=True,
        )

        return [
            _map_pinecone_match_to_document_score(match)
            for match in getattr(query_response, "matches", [])
        ]


def create_pinecone_client() -> Any:
    if not settings.pinecone_api_key:
        raise ValueError("Pinecone API key is required for Pinecone runtime retrieval")

    from pinecone import Pinecone

    return Pinecone(api_key=settings.pinecone_api_key)


def load_pinecone_vector_store(pinecone_client: Any) -> VectorStore:
    if not settings.pinecone_index_name:
        raise ValueError("Pinecone index name is required for Pinecone runtime retrieval")

    index_client = pinecone_client.Index(settings.pinecone_index_name)
    return PineconeVectorStoreAdapter(
        index_client=index_client,
        namespace=settings.pinecone_shared_namespace,
        index_name=settings.pinecone_index_name,
    )


def load_runtime_vector_store(pinecone_client: Any) -> VectorStore:
    return load_pinecone_vector_store(pinecone_client)


def describe_vector_store_runtime(vector_store: VectorStore) -> VectorStoreRuntimeDetails:
    runtime_details = getattr(vector_store, "runtime_details", None)
    if isinstance(runtime_details, VectorStoreRuntimeDetails):
        return runtime_details

    return VectorStoreRuntimeDetails(provider_name=type(vector_store).__name__.lower())


def _map_pinecone_match_to_document_score(match: Any) -> tuple[Document, float]:
    metadata = dict(getattr(match, "metadata", None) or {})
    page_content = _extract_chunk_text(metadata)
    normalized_metadata = _normalize_document_metadata(metadata, page_content)
    score = float(getattr(match, "score", 0.0))

    return Document(page_content=page_content, metadata=normalized_metadata), score


def _extract_chunk_text(metadata: dict[str, Any]) -> str:
    for field_name in PINECONE_TEXT_METADATA_KEYS:
        field_value = metadata.get(field_name)
        if isinstance(field_value, str) and field_value.strip():
            return field_value

    return ""


def _normalize_document_metadata(
    metadata: dict[str, Any],
    page_content: str,
) -> dict[str, Any]:
    normalized_metadata = dict(metadata)
    normalized_metadata["page_content"] = page_content

    zero_based_page = _resolve_zero_based_page(
        metadata.get("page"),
        metadata.get("page_number"),
    )
    if zero_based_page is not None:
        normalized_metadata["page"] = zero_based_page
        normalized_metadata["page_number"] = zero_based_page + 1

    return normalized_metadata


def _resolve_zero_based_page(
    page_value: Any,
    page_number_value: Any,
) -> int | None:
    if page_value is not None:
        try:
            return int(page_value)
        except (TypeError, ValueError):
            return None

    if page_number_value is not None:
        try:
            return int(page_number_value) - 1
        except (TypeError, ValueError):
            return None

    return None
