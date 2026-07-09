import sys
import types
import unittest
from unittest.mock import patch


class FakeVoyageEmbedResponse:
    def __init__(self, embeddings):
        self.embeddings = embeddings


class FakeVoyageRerankItem:
    def __init__(self, index: int, relevance_score: float) -> None:
        self.index = index
        self.relevance_score = relevance_score


class FakeVoyageRerankResponse:
    def __init__(self, results):
        self.results = results


class FakeVoyageClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.embed_calls = []
        self.rerank_calls = []

    def embed(self, texts, model: str, input_type: str):
        self.embed_calls.append(
            {
                "texts": texts,
                "model": model,
                "input_type": input_type,
            }
        )
        return FakeVoyageEmbedResponse([[0.1, 0.2], [0.3, 0.4]][: len(texts)])

    def rerank(self, query: str, documents: list[str], model: str, top_k: int):
        self.rerank_calls.append(
            {
                "query": query,
                "documents": documents,
                "model": model,
                "top_k": top_k,
            }
        )
        return FakeVoyageRerankResponse(
            [
                FakeVoyageRerankItem(index=1, relevance_score=0.9),
                FakeVoyageRerankItem(index=0, relevance_score=0.5),
            ][:top_k]
        )


class RetrievalProviderTests(unittest.TestCase):
    def setUp(self):
        self._saved_voyageai = sys.modules.get("voyageai")
        sys.modules["voyageai"] = types.SimpleNamespace(Client=FakeVoyageClient)

    def tearDown(self):
        if self._saved_voyageai is None:
            sys.modules.pop("voyageai", None)
        else:
            sys.modules["voyageai"] = self._saved_voyageai

    def test_embedding_factory_raises_for_unsupported_provider(self):
        from app.embeddings.factory import create_embedding_provider

        with patch("app.embeddings.factory.settings") as settings:
            settings.embedding_provider = "unsupported"

            with self.assertRaises(ValueError):
                create_embedding_provider()

    def test_embedding_factory_creates_voyage_provider_when_configured(self):
        from app.embeddings.factory import create_embedding_provider
        from app.embeddings.voyage_provider import VoyageEmbeddingProvider

        with patch("app.embeddings.factory.settings") as settings:
            settings.embedding_provider = "voyage"
            with patch("app.embeddings.voyage_provider.settings") as voyage_settings:
                voyage_settings.voyage_api_key = "voyage-key"
                voyage_settings.voyage_embedding_model_name = "voyage-3.5"
                provider = create_embedding_provider()

        self.assertIsInstance(provider, VoyageEmbeddingProvider)

    def test_voyage_embedding_provider_embeds_documents_and_queries(self):
        from app.embeddings.voyage_provider import VoyageEmbeddingProvider

        with patch("app.embeddings.voyage_provider.settings") as settings:
            settings.voyage_api_key = "voyage-key"
            settings.voyage_embedding_model_name = "voyage-3.5"
            provider = VoyageEmbeddingProvider()

        documents = provider.embed_documents(["first chunk", "second chunk"])
        query = provider.embed_query("What are the requirements?")

        self.assertEqual([[0.1, 0.2], [0.3, 0.4]], documents)
        self.assertEqual([0.1, 0.2], query)
        self.assertEqual("voyage-key", provider._client.api_key)
        self.assertEqual("document", provider._client.embed_calls[0]["input_type"])
        self.assertEqual("query", provider._client.embed_calls[1]["input_type"])

    def test_reranker_factory_raises_for_unsupported_provider(self):
        from app.reranking.factory import create_reranker_provider

        with patch("app.reranking.factory.settings") as settings:
            settings.reranker_provider = "unsupported"

            with self.assertRaises(ValueError):
                create_reranker_provider()

    def test_reranker_factory_creates_voyage_provider_when_configured(self):
        from app.reranking.factory import create_reranker_provider
        from app.reranking.voyage_provider import VoyageRerankerProvider

        with patch("app.reranking.factory.settings") as settings:
            settings.reranker_provider = "voyage"
            with patch("app.reranking.voyage_provider.settings") as voyage_settings:
                voyage_settings.voyage_api_key = "voyage-key"
                voyage_settings.voyage_reranker_model_name = "rerank-2.5"
                provider = create_reranker_provider()

        self.assertIsInstance(provider, VoyageRerankerProvider)

    def test_voyage_reranker_provider_returns_ranked_document_scores(self):
        from app.reranking.provider import RankedDocumentScore
        from app.reranking.voyage_provider import VoyageRerankerProvider

        with patch("app.reranking.voyage_provider.settings") as settings:
            settings.voyage_api_key = "voyage-key"
            settings.voyage_reranker_model_name = "rerank-2.5"
            provider = VoyageRerankerProvider()

        results = provider.rerank(
            question="What are the requirements?",
            documents=["doc one", "doc two"],
            top_k=2,
        )

        self.assertEqual(
            [
                RankedDocumentScore(index=1, score=0.9),
                RankedDocumentScore(index=0, score=0.5),
            ],
            results,
        )
        self.assertEqual("voyage-key", provider._client.api_key)
        self.assertEqual("rerank-2.5", provider._client.rerank_calls[0]["model"])

    def test_rerank_documents_uses_provider_factory_output(self):
        from app.rag.reranker import rerank_documents
        from app.reranking.provider import RankedDocumentScore

        document_one = types.SimpleNamespace(page_content="Doc 1")
        document_two = types.SimpleNamespace(page_content="Doc 2")
        documents_with_scores = [(document_one, 0.2), (document_two, 0.1)]
        reranker_provider = types.SimpleNamespace(
            rerank=lambda question, documents, top_k: [
                RankedDocumentScore(index=1, score=0.9),
                RankedDocumentScore(index=0, score=0.4),
            ]
        )

        with patch("app.rag.reranker.create_reranker_provider", return_value=reranker_provider):
            results = rerank_documents("requirements", documents_with_scores, top_k=2)

        self.assertEqual([(document_two, 0.9), (document_one, 0.4)], results)


if __name__ == "__main__":
    unittest.main()
