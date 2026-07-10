# Golden Q/A Set

Create `data/eval/golden_qa.json` here — a JSON array of question/reference-answer pairs, scored against the frozen `benchmark` Pinecone namespace by `backend/app/scripts/run_eval.py`.

Schema (validated by `backend/app/eval/golden_set.py::load_golden_set`):

```json
[
  {
    "id": "gq-001",
    "category": "admissions",
    "question": "What documents does a transfer student need to submit to the registrar?",
    "reference_answer": "Transfer students must submit the registrar's clearance, official transcript of records, and honorable dismissal from their previous school."
  }
]
```

- `id` (required, unique) — short stable identifier, referenced in per-question report rows.
- `question` (required) — a standalone question (no chat history / follow-up phrasing — the harness does not run query rewriting).
- `reference_answer` (required) — the ground-truth answer, verified against the actual PDF text. This is what `context_precision` and `context_recall` are scored against, so accuracy here directly determines whether the reported scores mean anything.
- `category` (optional) — a free-text tag (e.g. `"admissions"`, `"grading"`, `"out-of-scope"`) for readability in the report; not used by scoring.

Recommended: 15-20 questions, spanning multiple manual sections, including at least 2-3 intentionally hard or out-of-scope questions so the eval isn't cherry-picked.
