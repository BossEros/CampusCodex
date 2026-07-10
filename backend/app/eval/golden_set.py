from dataclasses import dataclass
from pathlib import Path
import json


@dataclass(frozen=True)
class GoldenQuestion:
    id: str
    question: str
    reference_answer: str
    category: str | None = None


REQUIRED_FIELDS = ("id", "question", "reference_answer")


def load_golden_set(path: str | Path) -> list[GoldenQuestion]:
    resolved_path = Path(path).resolve()

    if not resolved_path.exists():
        raise FileNotFoundError(f"Golden Q/A set not found: {resolved_path}")

    raw_records = json.loads(resolved_path.read_text(encoding="utf-8"))

    if not isinstance(raw_records, list) or not raw_records:
        raise ValueError(f"Golden Q/A set must be a non-empty JSON array: {resolved_path}")

    golden_questions = [_parse_record(record, index) for index, record in enumerate(raw_records)]
    _validate_unique_ids(golden_questions, resolved_path)

    return golden_questions


def _parse_record(record: dict, index: int) -> GoldenQuestion:
    if not isinstance(record, dict):
        raise ValueError(f"Golden Q/A record at index {index} must be a JSON object")

    for field_name in REQUIRED_FIELDS:
        field_value = record.get(field_name)
        if not isinstance(field_value, str) or not field_value.strip():
            raise ValueError(
                f"Golden Q/A record at index {index} is missing a non-empty '{field_name}' field"
            )

    return GoldenQuestion(
        id=record["id"],
        question=record["question"],
        reference_answer=record["reference_answer"],
        category=record.get("category"),
    )


def _validate_unique_ids(golden_questions: list[GoldenQuestion], source_path: Path) -> None:
    seen_ids: set[str] = set()

    for golden_question in golden_questions:
        if golden_question.id in seen_ids:
            raise ValueError(f"Duplicate golden Q/A id '{golden_question.id}' in {source_path}")
        seen_ids.add(golden_question.id)
