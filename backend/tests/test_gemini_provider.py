import sys
import types
import unittest
from unittest.mock import patch


class FakeGenerateContentConfig:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs


class FakeModelsClient:
    def __init__(self) -> None:
        self.generate_content_calls = []
        self.next_response = types.SimpleNamespace(text="response text")

    def generate_content(self, **kwargs):
        self.generate_content_calls.append(kwargs)
        return self.next_response


class FakeGeminiClient:
    models = FakeModelsClient()

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key


class GeminiProviderTests(unittest.TestCase):
    def setUp(self):
        FakeGeminiClient.models = FakeModelsClient()
        fake_genai_module = types.SimpleNamespace(Client=FakeGeminiClient)
        fake_types_module = types.SimpleNamespace(GenerateContentConfig=FakeGenerateContentConfig)
        fake_genai_module.types = fake_types_module
        fake_google_module = types.SimpleNamespace(genai=fake_genai_module)
        self.google_module_patch = patch.dict(
            sys.modules,
            {
                "google": fake_google_module,
                "google.genai": fake_genai_module,
                "google.genai.types": fake_types_module,
            },
        )
        self.google_module_patch.start()

    def tearDown(self):
        self.google_module_patch.stop()

    def test_factory_creates_gemini_provider_when_configured(self):
        from app.llm.factory import create_llm_provider
        from app.llm.gemini_provider import GeminiLlmProvider

        with patch("app.llm.factory.settings") as settings:
            settings.llm_provider = "gemini"
            with patch("app.llm.gemini_provider.settings") as gemini_settings:
                gemini_settings.gemini_api_key = "test-key"
                gemini_settings.llm_model_name = "gemini-2.5-flash"

                provider = create_llm_provider()

        self.assertIsInstance(provider, GeminiLlmProvider)

    def test_generate_answer_uses_configured_gemini_model(self):
        from app.llm.gemini_provider import GeminiLlmProvider

        with patch("app.llm.gemini_provider.settings") as settings:
            settings.gemini_api_key = "test-key"
            settings.llm_model_name = "gemini-2.5-flash"
            provider = GeminiLlmProvider()

        answer = provider.generate_answer(
            question="What about absences?",
            context="Absence policy context",
        )

        generate_content_call = FakeGeminiClient.models.generate_content_calls[0]
        self.assertEqual("response text", answer)
        self.assertEqual("gemini-2.5-flash", generate_content_call["model"])
        self.assertIn("Question:\nWhat about absences?", generate_content_call["contents"])
        self.assertIn("Context:\nAbsence policy context", generate_content_call["contents"])
        self.assertEqual(0, generate_content_call["config"].kwargs["temperature"])

    def test_rewrite_query_returns_original_question_when_gemini_returns_blank_text(self):
        from app.llm.gemini_provider import GeminiLlmProvider

        with patch("app.llm.gemini_provider.settings") as settings:
            settings.gemini_api_key = "test-key"
            settings.llm_model_name = "gemini-2.5-flash"
            provider = GeminiLlmProvider()

        FakeGeminiClient.models.next_response = types.SimpleNamespace(text="   ")

        rewritten_query = provider.rewrite_query("What about shifting?")

        self.assertEqual("What about shifting?", rewritten_query)


if __name__ == "__main__":
    unittest.main()
