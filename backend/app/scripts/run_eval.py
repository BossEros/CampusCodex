from pathlib import Path
import argparse
import json
import sys

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.eval.golden_set import load_golden_set
from app.eval.harness import ScoredSample, build_samples, score_sample
from app.eval.judge import build_judge_embeddings, build_judge_llm
from app.eval.report import build_report, write_report
from app.rag.vector_store import create_pinecone_client, load_pinecone_vector_store

DEFAULT_GOLDEN_SET_PATH = BACKEND_DIR.parent / "data" / "eval" / "golden_qa.json"
DEFAULT_RESULTS_DIR = BACKEND_DIR.parent / "data" / "eval" / "results"
SCORING_PROGRESS_CACHE_PATH = DEFAULT_RESULTS_DIR / ".scoring-progress-cache.json"


def load_scoring_progress_cache() -> dict[str, dict[str, float]]:
    if not SCORING_PROGRESS_CACHE_PATH.exists():
        return {}

    return json.loads(SCORING_PROGRESS_CACHE_PATH.read_text(encoding="utf-8"))


def save_scoring_progress_cache(scores_by_question_id: dict[str, dict[str, float]]) -> None:
    SCORING_PROGRESS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCORING_PROGRESS_CACHE_PATH.write_text(json.dumps(scores_by_question_id), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the RAGAS evaluation harness against a Pinecone namespace.",
    )
    parser.add_argument(
        "--golden-set",
        default=str(DEFAULT_GOLDEN_SET_PATH),
        help="Path to the golden Q/A JSON file.",
    )
    parser.add_argument(
        "--namespace",
        default=settings.pinecone_benchmark_namespace,
        help=(
            "Pinecone namespace to evaluate against. Defaults to the frozen benchmark "
            "namespace. Pointing this at the shared_kb namespace breaks eval-integrity "
            "isolation and prints a warning."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output report path. Defaults to data/eval/results/<UTC timestamp>.json.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only evaluate the first N golden questions (cheap smoke test).",
    )
    return parser.parse_args()


def print_summary(report: dict) -> None:
    metadata = report["metadata"]
    print("\nEvaluation summary")
    print(f"  Judge model:     {metadata['judge_llm_provider']}/{metadata['judge_llm_model']}")
    print(f"  Pinecone index:  {metadata['pinecone_index']} (namespace: {metadata['pinecone_namespace']})")
    print(f"  Golden set size: {metadata['golden_set_size']}")
    print(f"  Run at (UTC):    {metadata['run_at_utc']}")
    print("\n  Metric               Mean score")
    for metric_name, mean_score in report["aggregate_scores"].items():
        formatted_score = f"{mean_score:.3f}" if mean_score is not None else "n/a"
        print(f"  {metric_name:<20} {formatted_score}")


def main() -> None:
    args = parse_args()

    if args.namespace == settings.pinecone_shared_namespace:
        print(
            "WARNING: evaluating against the shared_kb namespace breaks eval-integrity "
            "isolation. This should only ever be pointed at the benchmark namespace."
        )

    print(f"Loading golden set from {args.golden_set}...")
    golden_questions = load_golden_set(args.golden_set)
    if args.limit is not None:
        golden_questions = golden_questions[: args.limit]
    print(f"Loaded {len(golden_questions)} golden question(s).")

    pinecone_client = create_pinecone_client()
    vector_store = load_pinecone_vector_store(pinecone_client, namespace=args.namespace)

    print("Retrieving and generating answers for each golden question...")
    samples = build_samples(vector_store, golden_questions)
    for index, sample in enumerate(samples, start=1):
        print(
            f"  [{index}/{len(samples)}] {sample.golden_question.id}: "
            f"retrieved {len(sample.retrieved_contexts)} chunk(s)"
        )

    print("Building judge LLM and embeddings...")
    judge_llm = build_judge_llm()
    judge_embeddings = build_judge_embeddings()

    from ragas.metrics.collections import (
        AnswerRelevancy,
        ContextPrecisionWithReference,
        ContextRecall,
        Faithfulness,
    )

    faithfulness_metric = Faithfulness(llm=judge_llm)
    answer_relevancy_metric = AnswerRelevancy(llm=judge_llm, embeddings=judge_embeddings)
    context_precision_metric = ContextPrecisionWithReference(llm=judge_llm)
    context_recall_metric = ContextRecall(llm=judge_llm)

    print("Scoring samples against RAGAS metrics (this calls the judge LLM repeatedly)...")
    scores_by_question_id = load_scoring_progress_cache()
    if scores_by_question_id:
        print(f"Resuming from cache: {len(scores_by_question_id)} question(s) already scored.")

    scored_samples: list[ScoredSample] = []
    for index, sample in enumerate(samples, start=1):
        question_id = sample.golden_question.id

        if question_id in scores_by_question_id:
            print(f"  [{index}/{len(samples)}] {question_id}: using cached scores")
            scored_samples.append(
                ScoredSample(golden_question=sample.golden_question, scores=scores_by_question_id[question_id])
            )
            continue

        print(f"  [{index}/{len(samples)}] scoring {question_id}...")
        scored_sample = score_sample(
            sample,
            faithfulness_metric,
            answer_relevancy_metric,
            context_precision_metric,
            context_recall_metric,
        )
        scored_samples.append(scored_sample)
        scores_by_question_id[question_id] = scored_sample.scores
        save_scoring_progress_cache(scores_by_question_id)

    report = build_report(
        scored_samples,
        metadata={
            "judge_llm_provider": "anthropic",
            "judge_llm_model": settings.eval_judge_model_name,
            "embedding_model": settings.voyage_embedding_model_name,
            "pinecone_index": settings.pinecone_index_name,
            "pinecone_namespace": args.namespace,
        },
    )

    output_path = args.output
    if output_path is None:
        run_timestamp = report["metadata"]["run_at_utc"].replace(":", "-")
        output_path = DEFAULT_RESULTS_DIR / f"{run_timestamp}.json"

    written_path = write_report(report, output_path)
    SCORING_PROGRESS_CACHE_PATH.unlink(missing_ok=True)
    print(f"\nReport written to: {written_path}")
    print_summary(report)


if __name__ == "__main__":
    main()
