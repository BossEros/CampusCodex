# Testing Patterns

**Analysis Date:** 2026-06-09

## Test Framework

**Runner:**
- `unittest` — Python standard library test runner (no third-party test framework installed)
- Config: No `pytest.ini`, `setup.cfg`, or `pyproject.toml` — tests run via `python -m unittest discover` or directly via `python -m unittest backend/tests/test_*.py`

**Assertion Library:**
- `unittest.TestCase` built-in assertions (`assertEqual`, `assertIsInstance`, `assertIn`, `assert_called_once`, `assert_called_once_with`, `assert_not_called`)

**Mocking:**
- `unittest.mock.patch` — context-manager and decorator-style patching
- `unittest.mock.Mock` — for lightweight dependency mocks
- `types.SimpleNamespace` — lightweight fake objects without class definitions
- `patch.dict(sys.modules, {...})` — module-level stub injection for optional SDK dependencies

**Run Commands:**
```bash
# Run all tests from the repo root
python -m unittest discover -s backend/tests

# Run a specific test file
python -m unittest backend.tests.test_anthropic_provider
python -m unittest backend.tests.test_gemini_provider
python -m unittest backend.tests.test_query_rewrite

# Run a file directly (from backend/)
python -m unittest tests/test_anthropic_provider.py
```

## Test File Organization

**Location:**
- All tests live in `backend/tests/` — a dedicated sibling directory to `backend/app/`
- No co-located tests alongside source files

**Naming:**
- Files: `test_<subject>.py` (e.g., `test_anthropic_provider.py`, `test_query_rewrite.py`)
- Classes: `<Subject>Tests` (e.g., `AnthropicProviderTests`, `GeminiProviderTests`, `QueryRewriteTests`)
- Methods: `test_<what_it_does>_<expected_result_condition>` — long, fully descriptive names

**Structure:**
```
backend/
├── app/
│   ├── llm/
│   │   ├── anthropic_provider.py
│   │   ├── gemini_provider.py
│   │   └── ...
│   └── rag/
│       ├── chat_service.py
│       └── query_transformer.py
└── tests/
    ├── test_anthropic_provider.py    # Tests AnthropicLlmProvider + factory
    ├── test_gemini_provider.py       # Tests GeminiLlmProvider + factory
    └── test_query_rewrite.py         # Tests query_transformer + chat_service pipeline
```

## Test Structure

**Suite Organization:**
```python
# Pattern from backend/tests/test_anthropic_provider.py
class AnthropicProviderTests(unittest.TestCase):
    def setUp(self):
        # Reset shared fake state, install module stubs
        FakeAnthropicClient.messages = FakeMessagesClient()
        fake_anthropic_module = types.SimpleNamespace(Anthropic=FakeAnthropicClient)
        self.anthropic_module_patch = patch.dict(sys.modules, {"anthropic": fake_anthropic_module})
        self.anthropic_module_patch.start()

    def tearDown(self):
        # Always stop patches started in setUp
        self.anthropic_module_patch.stop()

    def test_<descriptive_scenario>(self):
        ...

if __name__ == "__main__":
    unittest.main()
```

**Key patterns:**
- One `TestCase` subclass per test file
- `setUp` resets shared fake client state before each test (class-level attribute reassignment)
- `tearDown` stops all patches started in `setUp`
- Imports of the tested modules happen inside each test method (not at file top), so the patched `sys.modules` are in effect at import time — this is the critical pattern for deferred-import providers

## Mocking

**Framework:** `unittest.mock` only — no third-party mock library (e.g., no `pytest-mock`)

**Pattern 1 — SDK module stub injection via `sys.modules`:**
Used when the provider uses a deferred `from sdk import X` inside `__init__`. The entire SDK module is replaced with a `types.SimpleNamespace` before the provider class is imported inside the test method.

```python
# Pattern from backend/tests/test_anthropic_provider.py
def setUp(self):
    FakeAnthropicClient.messages = FakeMessagesClient()
    fake_anthropic_module = types.SimpleNamespace(Anthropic=FakeAnthropicClient)
    self.anthropic_module_patch = patch.dict(
        sys.modules, {"anthropic": fake_anthropic_module}
    )
    self.anthropic_module_patch.start()

def test_generate_answer_uses_configured_haiku_model(self):
    from app.llm.anthropic_provider import AnthropicLlmProvider  # import AFTER patch
    with patch("app.llm.anthropic_provider.settings") as settings:
        settings.anthropic_api_key = "test-key"
        settings.llm_model_name = "claude-haiku-4-5"
        provider = AnthropicLlmProvider()
    ...
```

**Pattern 2 — `patch()` context manager for settings:**
`settings` objects are patched per test, not globally. The full dotted path to the `settings` name in the module under test is used (not the config module path).

```python
# Pattern from all three test files
with patch("app.llm.anthropic_provider.settings") as settings:
    settings.anthropic_api_key = "test-key"
    settings.llm_model_name = "claude-haiku-4-5"
    provider = AnthropicLlmProvider()
```

**Pattern 3 — `Mock()` for service-layer dependencies:**
High-level pipeline tests replace function-level collaborators with `Mock()` and use `patch.object` on the module rather than the class.

```python
# Pattern from backend/tests/test_query_rewrite.py
with patch.object(chat_service, "rewrite_query_for_retrieval", return_value="rewritten query"):
    with patch.object(chat_service, "retrieve_relevant_chunks", return_value=retrieved_documents) as retrieve:
        with patch.object(chat_service, "build_context", return_value="context"):
            result = chat_service.answer_questions(vector_store, "original question")

retrieve.assert_called_once_with(
    vector_store=vector_store,
    retrieval_query="rewritten query",
    reranking_question="rewritten query",
)
```

**Pattern 4 — `patch.object` on settings attributes:**
When testing functions that read settings at call time (not constructor time), `patch.object` targets specific attributes:

```python
with patch.object(chat_service.settings, "retrieval_candidate_k", 15):
    with patch.object(chat_service.settings, "reranked_top_k", 5):
        ...
```

**What to Mock:**
- All external SDK clients (Anthropic, Gemini, Google GenAI) — replaced with `Fake*` classes
- `settings` object — patched per test with controlled values
- Collaborator functions inside pipeline orchestration tests (e.g., `rewrite_query_for_retrieval`, `retrieve_relevant_chunks`)
- `create_llm_provider` factory — replaced with `Mock()` returning a pre-configured mock provider

**What NOT to Mock:**
- `ChatMessage` schema — used directly from `app.schemas.chat` in tests
- Pure utility/regex logic (e.g., `should_use_previous_question`, `get_last_user_question`) — called with real inputs

## Fixtures and Factories

**Fake client classes:**
Each test file defines its own `Fake*` classes for the SDK being tested. These are plain Python classes that record call arguments and return configurable responses.

```python
# Pattern from backend/tests/test_anthropic_provider.py
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
```

**Key:** Fake client state is reset at class-level in `setUp` by reassigning the class attribute (e.g., `FakeAnthropicClient.messages = FakeMessagesClient()`), since the provider stores a reference to the class-level attribute.

**Test data:**
- Inline, minimal, purpose-built (e.g., `"test-key"`, `"What about absences?"`, `"Absence policy context"`)
- `ChatMessage` instances created inline inside tests — no separate fixture file

**Location:**
- No shared fixture files or `conftest.py` — all test data is local to each test method

## Coverage

**Requirements:** None enforced — no coverage configuration detected (no `.coveragerc`, no `pyproject.toml` coverage section)

**View Coverage:**
```bash
# Run with coverage (if coverage.py is installed)
coverage run -m unittest discover -s backend/tests
coverage report
coverage html
```

## Test Types

**Unit Tests:**
- Scope: Individual provider methods (`generate_answer`, `rewrite_query`) and single-function behavior (`rewrite_query_for_retrieval` with feature flag on/off)
- Approach: SDK replaced with fakes; settings patched; assertions on call arguments and return values
- Files: `backend/tests/test_anthropic_provider.py`, `backend/tests/test_gemini_provider.py`

**Integration-style Unit Tests:**
- Scope: Cross-function pipeline behavior within a single service module (e.g., `answer_questions` calling `rewrite_query_for_retrieval` → `retrieve_relevant_chunks` → `build_context` → `generate_answer`)
- Approach: `patch.object` on the module's own function references so the orchestrator runs but all collaborators are replaced with mocks
- File: `backend/tests/test_query_rewrite.py`

**E2E Tests:** Not present

**Frontend Tests:** Not present — no testing library in `frontend/package.json` (no Vitest, Jest, or Testing Library)

## Common Patterns

**Asserting call arguments on fakes (not Mock):**
```python
# Pattern from backend/tests/test_anthropic_provider.py
create_call = FakeAnthropicClient.messages.create_calls[0]
self.assertEqual("claude-haiku-4-5", create_call["model"])
self.assertEqual(0, create_call["temperature"])
self.assertIn("Question:\nWhat about absences?", create_call["messages"][0]["content"])
```

**Asserting LLM prompt construction:**
```python
# Pattern from backend/tests/test_query_rewrite.py
llm_provider.rewrite_query.assert_called_once()
rewrite_input = llm_provider.rewrite_query.call_args.args[0]
self.assertIn("Previous student question:", rewrite_input)
self.assertIn("What about the schedule?", rewrite_input)
self.assertNotIn("Tell me about enrollment.", rewrite_input)
```

**Asserting fallback behavior (blank response → original input):**
```python
# Pattern from both provider test files
FakeAnthropicClient.messages.next_response = FakeMessageResponse("   ")
rewritten_query = provider.rewrite_query("What about shifting?")
self.assertEqual("What about shifting?", rewritten_query)
```

**Asserting function NOT called:**
```python
# Pattern from backend/tests/test_query_rewrite.py
llm_provider.rewrite_query.assert_not_called()
self.assertEqual("What about requirements for latin honors?", retrieval_query)
```

---

*Testing analysis: 2026-06-09*
