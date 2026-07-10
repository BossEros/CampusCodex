from typing import Any
import asyncio

from ragas.embeddings.base import BaseRagasEmbedding
from ragas.llms import llm_factory

from app.core.config import settings
from app.embeddings.factory import create_embedding_provider
from app.eval.rate_limit import call_with_voyage_rate_limit_retry


def build_judge_llm() -> Any:
    if not settings.anthropic_api_key:
        raise ValueError("Anthropic API key is required for the RAGAS judge LLM.")

    from anthropic import AsyncAnthropic

    # RAGAS's metric classes call the judge LLM via `agenerate()`, so the
    # wrapped client must be async-capable (AsyncAnthropic), not the sync
    # `Anthropic` client used elsewhere (e.g. AnthropicLlmProvider).
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    judge_llm = llm_factory(
        settings.eval_judge_model_name,
        provider="anthropic",
        client=client,
        temperature=0,
        # ragas's default max_tokens=1024 truncates structured output (e.g.
        # faithfulness's atomic-statement breakdown) on longer answers,
        # raising an IncompleteOutputException mid-run.
        max_tokens=4096,
    )

    # ragas's InstructorModelArgs defaults set both temperature and top_p,
    # but Claude rejects requests that specify both. Drop top_p so only the
    # explicit temperature=0 above is sent.
    judge_llm.model_args.pop("top_p", None)

    return judge_llm


class VoyageRagasEmbeddings(BaseRagasEmbedding):
    def __init__(self, embedding_provider: Any) -> None:
        super().__init__()
        self._embedding_provider = embedding_provider

    def embed_text(self, text: str, **kwargs: Any) -> list[float]:
        return call_with_voyage_rate_limit_retry(lambda: self._embedding_provider.embed_query(text))

    def embed_texts(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        return call_with_voyage_rate_limit_retry(
            lambda: self._embedding_provider.embed_documents(texts)
        )

    async def aembed_text(self, text: str, **kwargs: Any) -> list[float]:
        return await asyncio.to_thread(self.embed_text, text)

    async def aembed_texts(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        return await asyncio.to_thread(self.embed_texts, texts)


def build_judge_embeddings() -> VoyageRagasEmbeddings:
    return VoyageRagasEmbeddings(create_embedding_provider())
