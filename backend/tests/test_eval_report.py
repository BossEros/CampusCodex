from pathlib import Path
import json
import tempfile
import unittest


class ReportTests(unittest.TestCase):
    def _make_scored_sample(self, question_id, scores, category=None):
        from app.eval.golden_set import GoldenQuestion
        from app.eval.harness import ScoredSample

        golden_question = GoldenQuestion(
            id=question_id,
            question=f"Question for {question_id}",
            reference_answer="A reference answer.",
            category=category,
        )
        return ScoredSample(golden_question=golden_question, scores=scores)

    def test_build_report_computes_aggregate_means(self):
        from app.eval.report import build_report

        scored_samples = [
            self._make_scored_sample(
                "gq-001",
                {
                    "faithfulness": 1.0,
                    "answer_relevancy": 0.8,
                    "context_precision": 0.6,
                    "context_recall": 0.4,
                },
            ),
            self._make_scored_sample(
                "gq-002",
                {
                    "faithfulness": 0.0,
                    "answer_relevancy": 0.6,
                    "context_precision": 0.4,
                    "context_recall": 0.6,
                },
            ),
        ]

        report = build_report(scored_samples, metadata={"judge_llm_model": "claude-haiku-4-5"})

        self.assertEqual("claude-haiku-4-5", report["metadata"]["judge_llm_model"])
        self.assertEqual(2, report["metadata"]["golden_set_size"])
        self.assertIn("run_at_utc", report["metadata"])
        self.assertAlmostEqual(0.5, report["aggregate_scores"]["faithfulness"])
        self.assertAlmostEqual(0.7, report["aggregate_scores"]["answer_relevancy"])
        self.assertEqual(2, len(report["per_question"]))
        self.assertEqual("gq-001", report["per_question"][0]["id"])
        self.assertEqual(1.0, report["per_question"][0]["faithfulness"])

    def test_build_report_excludes_nan_scores_from_aggregate(self):
        from app.eval.report import build_report

        scored_samples = [
            self._make_scored_sample(
                "gq-001",
                {
                    "faithfulness": float("nan"),
                    "answer_relevancy": 0.8,
                    "context_precision": 0.6,
                    "context_recall": 0.4,
                },
            ),
            self._make_scored_sample(
                "gq-002",
                {
                    "faithfulness": 0.6,
                    "answer_relevancy": 0.6,
                    "context_precision": 0.4,
                    "context_recall": 0.6,
                },
            ),
        ]

        report = build_report(scored_samples, metadata={})

        self.assertAlmostEqual(0.6, report["aggregate_scores"]["faithfulness"])

    def test_build_report_returns_none_aggregate_when_all_scores_missing(self):
        from app.eval.report import build_report

        scored_samples = [self._make_scored_sample("gq-001", {})]

        report = build_report(scored_samples, metadata={})

        self.assertIsNone(report["aggregate_scores"]["faithfulness"])

    def test_write_report_creates_parent_directories_and_valid_json(self):
        from app.eval.report import write_report

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "results.json"

            written_path = write_report({"aggregate_scores": {"faithfulness": 0.9}}, output_path)

            self.assertTrue(written_path.exists())
            self.assertEqual({"aggregate_scores": {"faithfulness": 0.9}}, json.loads(written_path.read_text()))


if __name__ == "__main__":
    unittest.main()
