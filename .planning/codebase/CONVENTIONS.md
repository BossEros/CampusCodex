# Coding Conventions

**Analysis Date:** 2026-06-09

## Naming Patterns

**Files:**
- Python: `snake_case` for all module files (e.g., `chat_service.py`, `query_transformer.py`, `pdf_loader.py`)
- Python classes: `PascalCase` (e.g., `AnthropicLlmProvider`, `GeminiLlmProvider`, `ChatRequest`)
- Python test files: `test_<subject>.py` prefix (e.g., `test_anthropic_provider.py`, `test_query_rewrite.py`)
- React/JS: `PascalCase` for component files (`App.jsx`), `camelCase` for utility files
- Module-level singleton constants: `UPPER_SNAKE_CASE` (e.g., `EMBEDDING_MODEL_NAME`, `DEPENDENT_FOLLOW_UP_PATTERNS`, `ANSWER_SYSTEM_PROMPT`)

**Functions:**
- Python: `snake_case` verbs describing what the function does (e.g., `load_pdf_documents_with_page_metadata`, `build_faiss_vector_store`, `rewrite_query_for_retrieval`)
- Private/internal helpers: single leading underscore prefix (e.g., `_attach_page_metadata`, `_extract_text`, `_generate_text`)
- React: `camelCase` with descriptive `handle*` prefix for event handlers (e.g., `handleSubmit`, `handleCloseEvidence`, `handleComposerKeyDown`)
- React async fetch utilities: bare `camelCase` nouns/verbs (e.g., `fetchJson`, `loadStatus`, `normalizeMessageContent`)

**Variables:**
- Python: `snake_case` throughout (e.g., `resolved_index_path`, `context_parts`, `reranked_documents`)
- Python loop variables: descriptive nouns, never single letters (e.g., `document`, `ranked_result`, `content_block`)
- React state: `camelCase` noun/adjective pairs (e.g., `isEvidenceOpen`, `activeEvidenceMessageId`, `isSending`)
- React refs: `<target>Ref` suffix (e.g., `messageListRef`, `composerInputRef`)

**Types/Classes:**
- Python Protocol interfaces: `<Name>` (e.g., `LlmProvider` in `backend/app/llm/provider.py`)
- Provider implementations: `<Provider>LlmProvider` pattern (e.g., `AnthropicLlmProvider`, `GeminiLlmProvider`, `GroqLlmProvider`)
- Pydantic schemas: noun-only `PascalCase` (e.g., `ChatRequest`, `ChatResponse`, `ChatMessage`, `ChatSource`)
- Test classes: `<Subject>Tests` suffix (e.g., `AnthropicProviderTests`, `QueryRewriteTests`)
- Test fake objects: `Fake<Thing>` prefix (e.g., `FakeAnthropicClient`, `FakeMessagesClient`, `FakeModelsClient`)

## Code Style

**Formatting:**
- No formatter config file found (no `.prettierrc`, `pyproject.toml`, or `setup.cfg`)
- Python indentation: 4 spaces consistently
- JavaScript/JSX indentation: 2 spaces consistently
- Trailing commas used in multi-line Python data structures and function call arguments
- Multi-line function signatures: each parameter on its own line with closing paren on its own line

**Linting:**
- No ESLint config detected in frontend
- No Flake8/Pylint/Ruff config detected in backend
- Code shows consistent adherence to PEP 8 style despite no enforced config

**Type Annotations:**
- All Python functions carry full return type annotations (e.g., `-> str`, `-> list[Document]`, `-> FAISS`, `-> None`)
- Union types use the modern `X | Y` syntax (`str | Path`, `int | None`, `list[ChatMessage] | None`)
- Local collection variables use explicit type hints where ambiguity exists (e.g., `text_parts: list[str] = []`)
- `TYPE_CHECKING` guard used in `backend/app/rag/chat_service.py` to avoid circular imports at runtime

## Import Organization

**Order (Python):**
1. Standard library (`pathlib`, `re`, `typing`, `contextlib`)
2. Third-party packages (`langchain_core`, `pydantic`, `sentence_transformers`)
3. Internal app imports (`app.core.config`, `app.llm.*`, `app.rag.*`, `app.schemas.*`)

**Deferred imports:**
- Third-party SDK imports that require an API key are deferred inside `__init__` to avoid import errors when the dependency is not installed (e.g., `from anthropic import Anthropic` inside `AnthropicLlmProvider.__init__`, `from google import genai` inside `GeminiLlmProvider.__init__`)
- File: `backend/app/llm/anthropic_provider.py` lines 13-14, `backend/app/llm/gemini_provider.py` lines 11-12

**JavaScript (React):**
- Named React hook imports first (e.g., `import { useEffect, useRef, useState } from "react"`)
- Default component export at the bottom of the file

## Error Handling

**Guard clauses at function entry:**
Every public function validates its inputs at the top with early `raise ValueError` before doing any work. This pattern is applied universally:
```python
# Pattern used in backend/app/rag/chat_service.py, backend/app/llm/anthropic_provider.py, etc.
def generate_answer(self, question: str, context: str) -> str:
    if not question.strip():
        raise ValueError("Question must not be empty")
    if not context.strip():
        return "The student manual does not provide enough information to answer that."
```

**Graceful empty-context return:**
All three LLM providers return a user-facing fallback string instead of raising an exception when context is empty. The exact string is duplicated across `AnthropicLlmProvider`, `GeminiLlmProvider`, `GroqLlmProvider`, and `chat_service.generate_answer`.

**FileNotFoundError / ValueError for I/O:**
`load_faiss_vector_store` and `load_pdf_documents_with_page_metadata` raise typed exceptions (`FileNotFoundError`, `ValueError`) with descriptive messages that include the resolved path.

**FastAPI HTTP error mapping:**
`backend/app/main.py` maps Python exceptions to HTTP status codes explicitly:
- `ValueError` → `400`
- `None` vector store → `503`
- All other exceptions → `500` (with a generic message, not the raw exception detail)

**React:**
- Async functions use try/catch with a typed error handler `formatErrorMessage(error)` that normalizes `Error` instances and unknown throws
- `isMounted` flag in `useEffect` prevents state updates after unmount (see `loadStatus` in `App.jsx`)
- `void` keyword used explicitly when calling `async` functions from event handlers where the promise return value is intentionally ignored

## Logging

**Framework:** `print()` only — used exclusively in `backend/app/scripts/build_index.py` for CLI output during index build.

**Patterns:**
- No structured logging in production code paths (`backend/app/` outside scripts)
- Build script uses descriptive progress messages with counts (e.g., `f"Loaded documents: {len(documents)}"`)

## Comments

**When to comment:**
- Inline comments explain non-obvious intent, not mechanics (e.g., `# Keep a consistent zero-based page field for internal use` in `backend/app/rag/pdf_loader.py`)
- Docstrings used only on Protocol methods in `backend/app/llm/provider.py`; implementation classes do not repeat them

**Pattern:**
- No class-level docstrings on concrete implementations
- No function-level docstrings on non-Protocol functions; intent is conveyed through descriptive names and guard clauses

## Function Design

**Size:** Functions are small and focused — most are under 25 lines. Orchestration functions (`answer_questions`, `rewrite_query_for_retrieval`) delegate immediately to named sub-functions.

**Parameters:** Named arguments used at call sites for multi-argument calls to improve readability:
```python
# Pattern from backend/app/rag/chat_service.py
documents_with_scores = retrieve_relevant_chunks(
    vector_store=vector_store,
    retrieval_query=resolved_question,
    reranking_question=resolved_question,
)
```

**Return values:** Functions return the narrowest useful type. Fallback strings are returned instead of `None` when a meaningful default exists. `None` is returned only when absence is semantically meaningful (e.g., `get_display_page_number` returns `int | None`).

## Module Design

**Exports:**
- No `__all__` declarations; modules export everything at module level
- `settings` singleton is created at module level in `backend/app/core/config.py` and imported directly wherever needed

**Barrel files:**
- `backend/app/llm/__init__.py` is empty — no barrel aggregation used
- All imports are explicit from their source modules

**Factory pattern:**
- `backend/app/llm/factory.py` — `create_llm_provider()` selects and instantiates the correct provider based on `settings.llm_provider`. Provider classes are imported inside `if` branches to avoid loading unused SDK dependencies.

**Global singleton with lazy init:**
- `backend/app/rag/reranker.py` uses a module-level `reranker_model: CrossEncoder | None = None` and a `get_reranker_model()` getter that initializes on first call

**Pydantic for configuration and schemas:**
- `backend/app/core/config.py` — `Settings(BaseSettings)` with `.env` file loading and a `@field_validator` for path resolution
- `backend/app/schemas/chat.py` — All API request/response shapes defined as `BaseModel` with `Field(...)` including descriptions

---

*Convention analysis: 2026-06-09*
