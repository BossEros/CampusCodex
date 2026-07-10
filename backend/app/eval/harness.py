from dataclasses import dataclass, field
from typing import Any

from app.eval.golden_set import GoldenQuestion
from app.eval.rate_limit import call_with_voyage_rate_limit_retry
from app.rag.chat_service import build_context, generate_answer, retrieve_relevant_chunks
from app.rag.vector_store import VectorStore

METRIC_NAMES = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")


@dataclass(frozen=True)
class EvalSample:
    golden_question: GoldenQuestion
    response: str
    retrieved_contexts: list[str]


@dataclass
class ScoredSample:
    golden_question: GoldenQuestion
    scores: dict[str, float] = field(default_factory=dict)


def build_sample(vector_store: VectorStore, golden_question: GoldenQuestion) -> EvalSample:
    # Retrieval embeds the query and reranking calls Voyage's rerank API —
    # both share the same harsh free-tier rate limit as judge scoring.
    documents_with_scores = call_with_voyage_rate_limit_retry(
        lambda: retrieve_relevant_chunks(
            vector_store=vector_store,
            retrieval_query=golden_question.question,
            reranking_question=golden_question.question,
        )
    )

    retrieved_contexts = [document.page_content for document, _ in documents_with_scores]
    context = build_context(documents_with_scores)
    response = generate_answer(golden_question.question, context)

    return EvalSample(
        golden_question=golden_question,
        response=response,
        retrieved_contexts=retrieved_contexts,
    )


def build_samples(
    vector_store: VectorStore,
    golden_questions: list[GoldenQuestion],
) -> list[EvalSample]:
    return [build_sample(vector_store, golden_question) for golden_question in golden_questions]


def score_sample(
    sample: EvalSample,
    faithfulness_metric: Any,
    answer_relevancy_metric: Any,
    context_precision_metric: Any,
    context_recall_metric: Any,
) -> ScoredSample:
    scored_sample = ScoredSample(golden_question=sample.golden_question)

    faithfulness_result = faithfulness_metric.score(
        user_input=sample.golden_question.question,
        response=sample.response,
        retrieved_contexts=sample.retrieved_contexts,
    )
    scored_sample.scores["faithfulness"] = float(faithfulness_result.value)

    answer_relevancy_result = answer_relevancy_metric.score(
        user_input=sample.golden_question.question,
        response=sample.response,
    )
    scored_sample.scores["answer_relevancy"] = float(answer_relevancy_result.value)

    context_precision_result = context_precision_metric.score(
        user_input=sample.golden_question.question,
        reference=sample.golden_question.reference_answer,
        retrieved_contexts=sample.retrieved_contexts,
    )
    scored_sample.scores["context_precision"] = float(context_precision_result.value)

    context_recall_result = context_recall_metric.score(
        user_input=sample.golden_question.question,
        retrieved_contexts=sample.retrieved_contexts,
        reference=sample.golden_question.reference_answer,
    )
    scored_sample.scores["context_recall"] = float(context_recall_result.value)

    return scored_sample
