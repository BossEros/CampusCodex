from app.core.config import settings
from app.llm.provider import LlmProvider


def create_llm_provider() -> LlmProvider:
    provider_name = settings.llm_provider.lower().strip()
    
    if provider_name == "groq":
        from app.llm.groq_provider import GroqLlmProvider

        return GroqLlmProvider()

    if provider_name == "anthropic":
        from app.llm.anthropic_provider import AnthropicLlmProvider

        return AnthropicLlmProvider()

    if provider_name == "gemini":
        from app.llm.gemini_provider import GeminiLlmProvider

        return GeminiLlmProvider()
    
    raise ValueError(f"Unsupported LLM Provider: {settings.llm_provider}")
