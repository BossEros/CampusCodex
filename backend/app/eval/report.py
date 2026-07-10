from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import math

from app.eval.harness import METRIC_NAMES, ScoredSample

OUT_OF_SCOPE_CATEGORY = "out-of-scope"


def build_report(scored_samples: list[ScoredSample], metadata: dict[str, Any]) -> dict:
    headline_samples = [
        scored_sample
        for scored_sample in scored_samples
        if scored_sample.golden_question.category != OUT_OF_SCOPE_CATEGORY
    ]

    return {
        "metadata": {
            **metadata,
            "run_at_utc": datetime.now(timezone.utc).isoformat(),
            "golden_set_size": len(scored_samples),
        },
        "aggregate_scores": _aggregate_scores(headline_samples),
        "guardrail_scores": _guardrail_scores(scored_samples),
        "per_question": [_to_question_entry(scored_sample) for scored_sample in scored_samples],
    }


def write_report(report: dict, output_path: str | Path) -> Path:
    resolved_output_path = Path(output_path).resolve()
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return resolved_output_path


def _aggregate_scores(scored_samples: list[ScoredSample]) -> dict[str, float | None]:
    aggregate_scores: dict[str, float | None] = {}

    for metric_name in METRIC_NAMES:
        metric_values = [
            scored_sample.scores[metric_name]
            for scored_sample in scored_samples
            if metric_name in scored_sample.scores and not math.isnan(scored_sample.scores[metric_name])
        ]
        aggregate_scores[metric_name] = (
            sum(metric_values) / len(metric_values) if metric_values else None
        )

    return aggregate_scores


def _guardrail_scores(scored_samples: list[ScoredSample]) -> list[dict]:
    return [
        _to_question_entry(scored_sample)
        for scored_sample in scored_samples
        if scored_sample.golden_question.category == OUT_OF_SCOPE_CATEGORY
    ]


def _to_question_entry(scored_sample: ScoredSample) -> dict:
    return {
        "id": scored_sample.golden_question.id,
        "category": scored_sample.golden_question.category,
        "question": scored_sample.golden_question.question,
        **scored_sample.scores,
    }
