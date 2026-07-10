import unittest
from unittest.mock import Mock, patch


class JudgeTests(unittest.TestCase):
    def test_build_judge_llm_raises_when_anthropic_api_key_missing(self):
        from app.eval.judge import build_judge_llm

        with patch("app.eval.judge.settings") as settings:
            settings.anthropic_api_key = None

            with self.assertRaises(ValueError):
                build_judge_llm()

    def test_build_judge_llm_constructs_when_anthropic_api_key_present(self):
        from app.eval.judge import build_judge_llm

        with patch("app.eval.judge.settings") as settings:
            settings.anthropic_api_key = "test-key"
            settings.eval_judge_model_name = "claude-haiku-4-5"

            judge_llm = build_judge_llm()

        self.assertIsNotNone(judge_llm)

    def test_build_judge_embeddings_delegates_to_embedding_provider(self):
        from app.eval.judge import build_judge_embeddings

        embedding_provider = Mock()
        embedding_provider.embed_query.return_value = [0.1, 0.2]
        embedding_provider.embed_documents.return_value = [[0.1, 0.2], [0.3, 0.4]]

        with patch("app.eval.judge.create_embedding_provider", return_value=embedding_provider):
            judge_embeddings = build_judge_embeddings()

        self.assertEqual([0.1, 0.2], judge_embeddings.embed_text("a query"))
        self.assertEqual(
            [[0.1, 0.2], [0.3, 0.4]],
            judge_embeddings.embed_texts(["doc one", "doc two"]),
        )


if __name__ == "__main__":
    unittest.main()
