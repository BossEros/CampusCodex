import types
import unittest
from unittest.mock import Mock, patch

from langchain_core.documents import Document


class HarnessTests(unittest.TestCase):
    def test_build_sample_collects_raw_chunk_texts_separately_from_generated_answer(self):
        from app.eval import harness
        from app.eval.golden_set import GoldenQuestion

        golden_question = GoldenQuestion(
            id="gq-001",
            question="What is the passing grade?",
            reference_answer="3.0 is the passing grade.",
        )
        document_one = Document(page_content="Chunk one text", metadata={"page": 1})
        document_two = Document(page_content="Chunk two text", metadata={"page": 2})
        documents_with_scores = [(document_one, 0.9), (document_two, 0.8)]
        vector_store = Mock()

        with patch.object(
            harness, "retrieve_relevant_chunks", return_value=documents_with_scores
        ) as retrieve_mock:
            with patch.object(
                harness, "build_context", return_value="Context 1:\nChunk one text\n\nContext 2:\nChunk two text"
            ):
                with patch.object(harness, "generate_answer", return_value="The passing grade is 3.0.") as generate_mock:
                    sample = harness.build_sample(vector_store=vector_store, golden_question=golden_question)

        retrieve_mock.assert_called_once_with(
            vector_store=vector_store,
            retrieval_query="What is the passing grade?",
            reranking_question="What is the passing grade?",
        )
        generate_mock.assert_called_once_with(
            "What is the passing grade?",
            "Context 1:\nChunk one text\n\nContext 2:\nChunk two text",
        )
        self.assertEqual(["Chunk one text", "Chunk two text"], sample.retrieved_contexts)
        self.assertEqual("The passing grade is 3.0.", sample.response)
        self.assertEqual(golden_question, sample.golden_question)

    def test_score_sample_calls_each_metric_with_expected_arguments_and_aggregates_scores(self):
        from app.eval.golden_set import GoldenQuestion
        from app.eval.harness import EvalSample, score_sample

        golden_question = GoldenQuestion(
            id="gq-001",
            question="What is the passing grade?",
            reference_answer="3.0 is the passing grade.",
        )
        sample = EvalSample(
            golden_question=golden_question,
            response="The passing grade is 3.0.",
            retrieved_contexts=["Chunk one text"],
        )

        def make_metric(score_value: float) -> Mock:
            metric = Mock()
            metric.score.return_value = types.SimpleNamespace(value=score_value)
            return metric

        faithfulness_metric = make_metric(0.9)
        answer_relevancy_metric = make_metric(0.85)
        context_precision_metric = make_metric(0.8)
        context_recall_metric = make_metric(0.75)

        scored_sample = score_sample(
            sample,
            faithfulness_metric,
            answer_relevancy_metric,
            context_precision_metric,
            context_recall_metric,
        )

        faithfulness_metric.score.assert_called_once_with(
            user_input="What is the passing grade?",
            response="The passing grade is 3.0.",
            retrieved_contexts=["Chunk one text"],
        )
        answer_relevancy_metric.score.assert_called_once_with(
            user_input="What is the passing grade?",
            response="The passing grade is 3.0.",
        )
        context_precision_metric.score.assert_called_once_with(
            user_input="What is the passing grade?",
            reference="3.0 is the passing grade.",
            retrieved_contexts=["Chunk one text"],
        )
        context_recall_metric.score.assert_called_once_with(
            user_input="What is the passing grade?",
            retrieved_contexts=["Chunk one text"],
            reference="3.0 is the passing grade.",
        )
        self.assertEqual(
            {
                "faithfulness": 0.9,
                "answer_relevancy": 0.85,
                "context_precision": 0.8,
                "context_recall": 0.75,
            },
            scored_sample.scores,
        )


if __name__ == "__main__":
    unittest.main()
