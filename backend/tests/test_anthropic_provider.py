import sys
import types
import unittest
from unittest.mock import patch


class FakeMessageResponse:
    def __init__(self, text: str) -> None:
        self.content = [types.SimpleNamespace(type="text", text=text)]


class FakeMessagesClient:
    def __init__(self) -> None:
        self.create_calls = []
        self.next_response = FakeMessageResponse("response text")

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return self.next_response


class FakeAnthropicClient:
    messages = FakeMessagesClient()

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key


class AnthropicProviderTests(unittest.TestCase):
    def setUp(self):
        FakeAnthropicClient.messages = FakeMessagesClient()
        fake_anthropic_module = types.SimpleNamespace(Anthropic=FakeAnthropicClient)
        self._saved_anthropic = sys.modules.get("anthropic")
        sys.modules["anthropic"] = fake_anthropic_module

    def tearDown(self):
        if self._saved_anthropic is None:
          sys.modules.pop("anthropic", None)
        else:
          sys.modules["anthropic"] = self._saved_anthropic

    def test_factory_creates_anthropic_provider_when_configured(self):
        from app.llm.anthropic_provider import AnthropicLlmProvider
        from app.llm.factory import create_llm_provider

        with patch("app.llm.factory.settings") as settings:
            settings.llm_provider = "anthropic"
            with patch("app.llm.anthropic_provider.settings") as anthropic_settings:
                anthropic_settings.anthropic_api_key = "test-key"
                anthropic_settings.llm_model_name = "claude-haiku-4-5"

                provider = create_llm_provider()

        self.assertIsInstance(provider, AnthropicLlmProvider)

    def test_generate_answer_uses_configured_haiku_model(self):
        from app.llm.anthropic_provider import AnthropicLlmProvider

        with patch("app.llm.anthropic_provider.settings") as settings:
            settings.anthropic_api_key = "test-key"
            settings.llm_model_name = "claude-haiku-4-5"
            provider = AnthropicLlmProvider()

        answer = provider.generate_answer(
            question="What about absences?",
            context="Absence policy context",
        )

        create_call = FakeAnthropicClient.messages.create_calls[0]
        self.assertEqual("response text", answer)
        self.assertEqual("claude-haiku-4-5", create_call["model"])
        self.assertEqual(0, create_call["temperature"])
        self.assertIn("Question:\nWhat about absences?", create_call["messages"][0]["content"])
        self.assertIn("Context:\nAbsence policy context", create_call["messages"][0]["content"])

    def test_rewrite_query_returns_original_question_when_claude_returns_blank_text(self):
        from app.llm.anthropic_provider import AnthropicLlmProvider

        with patch("app.llm.anthropic_provider.settings") as settings:
            settings.anthropic_api_key = "test-key"
            settings.llm_model_name = "claude-haiku-4-5"
            provider = AnthropicLlmProvider()

        FakeAnthropicClient.messages.next_response = FakeMessageResponse("   ")

        rewritten_query = provider.rewrite_query("What about shifting?")

        self.assertEqual("What about shifting?", rewritten_query)


if __name__ == "__main__":
    unittest.main()
