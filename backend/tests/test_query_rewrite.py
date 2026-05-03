import unittest
from unittest.mock import Mock, patch


class QueryRewriteTests(unittest.TestCase):
    def test_rewrite_query_for_retrieval_returns_original_question_when_disabled(self):
        from app.rag.query_transformer import rewrite_query_for_retrieval

        question = "What about shifting?"

        with patch("app.rag.query_transformer.settings") as settings:
            settings.enable_query_rewrite = False

            retrieval_query = rewrite_query_for_retrieval(question)

        self.assertEqual(question, retrieval_query)

    def test_rewrite_query_for_retrieval_uses_llm_provider_when_enabled(self):
        from app.rag.query_transformer import rewrite_query_for_retrieval

        llm_provider = Mock()
        llm_provider.rewrite_query.return_value = "What are the requirements for shifting courses?"

        with patch("app.rag.query_transformer.settings") as settings:
            settings.enable_query_rewrite = True

            with patch("app.rag.query_transformer.create_llm_provider", return_value=llm_provider):
                retrieval_query = rewrite_query_for_retrieval("What about shifting?")

        self.assertEqual("What are the requirements for shifting courses?", retrieval_query)

    def test_answer_questions_retrieves_with_rewritten_query_and_answers_original_question(self):
        from app.rag import chat_service

        vector_store = Mock()
        retrieved_documents = [("document", 1.0)]

        with patch.object(chat_service, "rewrite_query_for_retrieval", return_value="rewritten query"):
            with patch.object(chat_service, "retrieve_relevant_chunks", return_value=retrieved_documents) as retrieve:
                with patch.object(chat_service, "build_context", return_value="context") as build_context:
                    with patch.object(chat_service, "generate_answer", return_value="answer") as generate_answer:
                        with patch.object(chat_service, "build_sources", return_value=[]) as build_sources:
                            result = chat_service.answer_questions(vector_store, "original question")

        retrieve.assert_called_once_with(
            vector_store=vector_store,
            retrieval_query="rewritten query",
            reranking_question="original question",
        )
        build_context.assert_called_once_with(retrieved_documents)
        generate_answer.assert_called_once_with("original question", "context")
        build_sources.assert_called_once_with(retrieved_documents)
        self.assertEqual({"answer": "answer", "sources": []}, result)

    def test_retrieve_relevant_chunks_searches_with_retrieval_query_and_reranks_original_question(self):
        from app.rag import chat_service

        vector_store = Mock()
        candidate_documents = [("candidate", 0.25)]
        reranked_documents = [("candidate", 2.5)]
        vector_store.similarity_search_with_score.return_value = candidate_documents

        with patch.object(chat_service.settings, "retrieval_candidate_k", 15):
            with patch.object(chat_service.settings, "reranked_top_k", 5):
                with patch.object(chat_service, "rerank_documents", return_value=reranked_documents) as rerank:
                    result = chat_service.retrieve_relevant_chunks(
                        vector_store=vector_store,
                        retrieval_query="requirements for shifting courses",
                        reranking_question="What about shifting?",
                    )

        vector_store.similarity_search_with_score.assert_called_once_with(
            "requirements for shifting courses",
            k=15,
        )
        rerank.assert_called_once_with(
            question="What about shifting?",
            documents_with_scores=candidate_documents,
            top_k=5,
        )
        self.assertEqual(reranked_documents, result)


if __name__ == "__main__":
    unittest.main()
