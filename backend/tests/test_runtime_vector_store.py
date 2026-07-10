import sys
import types
import unittest
from unittest.mock import Mock, patch

from langchain_core.documents import Document


class FakePineconeMatch:
    def __init__(self, score: float, metadata: dict) -> None:
        self.score = score
        self.metadata = metadata


class FakePineconeQueryResponse:
    def __init__(self, matches: list[FakePineconeMatch]) -> None:
        self.matches = matches


class FakePineconeIndex:
    def __init__(self) -> None:
        self.query_calls: list[dict] = []
        self.query_response = FakePineconeQueryResponse([])

    def query(self, **kwargs):
        self.query_calls.append(kwargs)
        return self.query_response


class FakePineconeClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.index_calls: list[str] = []
        self.index_instance = FakePineconeIndex()

    def Index(self, index_name: str) -> FakePineconeIndex:
        self.index_calls.append(index_name)
        return self.index_instance


class RuntimeVectorStoreTests(unittest.TestCase):
    def setUp(self):
        self._saved_pinecone = sys.modules.get("pinecone")
        sys.modules["pinecone"] = types.SimpleNamespace(Pinecone=FakePineconeClient)

    def tearDown(self):
        if self._saved_pinecone is None:
            sys.modules.pop("pinecone", None)
        else:
            sys.modules["pinecone"] = self._saved_pinecone

    def test_load_runtime_vector_store_loads_pinecone_adapter(self):
        from app.rag.vector_store import PineconeVectorStoreAdapter, load_runtime_vector_store

        pinecone_client = FakePineconeClient(api_key="pinecone-key")

        with patch("app.rag.vector_store.settings") as settings:
            settings.pinecone_api_key = "pinecone-key"
            settings.pinecone_index_name = "campus-codex"
            settings.pinecone_shared_namespace = "shared_kb"

            with patch("app.rag.vector_store.create_embedding_provider", return_value=Mock()):
                vector_store = load_runtime_vector_store(pinecone_client)

        self.assertIsInstance(vector_store, PineconeVectorStoreAdapter)
        self.assertEqual(["campus-codex"], pinecone_client.index_calls)

    def test_load_pinecone_vector_store_accepts_namespace_override(self):
        from app.rag.vector_store import load_pinecone_vector_store

        pinecone_client = FakePineconeClient(api_key="pinecone-key")

        with patch("app.rag.vector_store.settings") as settings:
            settings.pinecone_index_name = "campus-codex"
            settings.pinecone_shared_namespace = "shared_kb"

            with patch("app.rag.vector_store.create_embedding_provider", return_value=Mock()):
                vector_store = load_pinecone_vector_store(pinecone_client, namespace="benchmark")

        self.assertEqual("benchmark", vector_store.runtime_details.namespace)

    def test_pinecone_vector_store_adapter_uses_shared_namespace_and_maps_metadata(self):
        from app.rag.vector_store import PineconeVectorStoreAdapter

        index_client = FakePineconeIndex()
        index_client.query_response = FakePineconeQueryResponse(
            [
                FakePineconeMatch(
                    score=0.91,
                    metadata={
                        "title": "Student Manual 2019",
                        "source": "data/raw/student_manual_2019.pdf",
                        "page": 4,
                        "page_number": 5,
                        "text": "Transfer students must submit the registrar's clearance.",
                    },
                )
            ]
        )
        embedding_provider = Mock()
        embedding_provider.embed_query.return_value = [0.12, 0.34]

        with patch("app.rag.vector_store.create_embedding_provider", return_value=embedding_provider):
            vector_store = PineconeVectorStoreAdapter(
                index_client=index_client,
                namespace="shared_kb",
                index_name="campus-codex",
            )

        results = vector_store.search_similar_chunks("transfer requirements", 3)

        self.assertEqual(1, len(results))
        document, score = results[0]
        self.assertIsInstance(document, Document)
        self.assertEqual(0.91, score)
        self.assertEqual(
            "Transfer students must submit the registrar's clearance.",
            document.page_content,
        )
        self.assertEqual("Student Manual 2019", document.metadata["title"])
        self.assertEqual("data/raw/student_manual_2019.pdf", document.metadata["source"])
        self.assertEqual(4, document.metadata["page"])
        self.assertEqual(5, document.metadata["page_number"])
        self.assertEqual(
            [
                {
                    "vector": [0.12, 0.34],
                    "top_k": 3,
                    "namespace": "shared_kb",
                    "include_metadata": True,
                }
            ],
            index_client.query_calls,
        )

    def test_build_sources_includes_document_title(self):
        from app.rag.chat_service import build_sources

        document = Document(
            page_content="This is a source excerpt",
            metadata={
                "title": "Student Manual 2019",
                "page": 1,
                "source": "data/raw/student_manual_2019.pdf",
            },
        )

        sources = build_sources([(document, 0.77)])

        self.assertEqual(
            {
                "excerpt": "This is a source excerpt",
                "score": 0.77,
                "title": "Student Manual 2019",
                "page_number": 2,
                "source": "data/raw/student_manual_2019.pdf",
            },
            sources[0],
        )

    def test_get_index_status_reports_runtime_vector_store_details(self):
        from app.main import get_index_status
        from app.rag.vector_store import VectorStoreRuntimeDetails

        request = types.SimpleNamespace(
            app=types.SimpleNamespace(
                state=types.SimpleNamespace(
                    vector_store=types.SimpleNamespace(
                        runtime_details=VectorStoreRuntimeDetails(
                            provider_name="pinecone",
                            index_name="campus-codex",
                            namespace="shared_kb",
                        )
                    )
                )
            )
        )

        with patch("app.main.settings") as settings:
            settings.pdf_path = "data/raw/student_manual_2019.pdf"
            settings.pinecone_index_name = "campus-codex"
            settings.voyage_embedding_model_name = "voyage-3.5"
            settings.embedding_provider = "voyage"
            settings.retrieval_candidate_k = 15
            settings.reranked_top_k = 5
            settings.llm_provider = "groq"
            settings.llm_model_name = "llama-3.1-8b-instant"
            settings.reranker_provider = "voyage"
            settings.voyage_reranker_model_name = "rerank-2.5"
            settings.enable_query_rewrite = True

            status = get_index_status(request)

        self.assertEqual("pinecone", status["vector_store_provider"])
        self.assertEqual("shared_kb", status["vector_store_namespace"])
        self.assertEqual("campus-codex", status["pinecone_index_name"])
        self.assertEqual("voyage", status["embedding_provider"])
        self.assertEqual("voyage-3.5", status["embedding_model"])
        self.assertEqual("rerank-2.5", status["reranker_model"])


if __name__ == "__main__":
    unittest.main()
