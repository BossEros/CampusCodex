# Codebase Concerns

**Analysis Date:** 2026-06-09

---

## Tech Debt

**Synchronous chat endpoint blocks the ASGI event loop:**
- Issue: `POST /api/chat` is a plain `def` function, not `async def`. All LLM calls (Groq, Anthropic, Gemini), FAISS similarity search, and cross-encoder reranking execute on the main thread. FastAPI runs these in a thread pool, but this blocks uvicorn workers under concurrent load.
- Files: `backend/app/main.py` (line 55), `backend/app/rag/chat_service.py`, all providers in `backend/app/llm/`
- Impact: Concurrent users stall each other. No parallelism benefit from uvicorn's async model.
- Fix approach: Convert `chat()` to `async def` and use `asyncio.to_thread()` or switch to async provider SDKs (`anthropic.AsyncAnthropic`, `groq.AsyncGroq`).

**Embedding model re-instantiated on every index build and load:**
- Issue: `create_embedding_model()` in `backend/app/rag/vector_store.py` constructs a new `HuggingFaceEmbeddings` instance every call. This means model weights are loaded twice during `load_faiss_vector_store()` — once in the function and once during FAISS `load_local`. There is no caching or singleton for the embedding model at runtime.
- Files: `backend/app/rag/vector_store.py` (lines 10-11, 33-34)
- Impact: Slower startup; unnecessary memory allocation.
- Fix approach: Add a module-level `_embedding_model: HuggingFaceEmbeddings | None = None` singleton mirroring the pattern used in `reranker.py`.

**LLM provider instantiated on every request:**
- Issue: `create_llm_provider()` in `backend/app/llm/factory.py` is called inside both `generate_answer()` and `rewrite_query_for_retrieval()` on each chat request. For a single question with query rewrite enabled, two separate provider instances are created.
- Files: `backend/app/rag/chat_service.py` (line 56), `backend/app/rag/query_transformer.py` (line 58), `backend/app/llm/factory.py`
- Impact: Redundant object creation per request; no connection reuse for HTTP clients.
- Fix approach: Cache the provider as application-level state in `main.py` lifespan, alongside `vector_store`.

**PLAN.md references outdated embedding model name:**
- Issue: `PLAN.md` (line 75) specifies `sentence-transformers/all-MiniLM-L6-v2` but the codebase uses `sentence-transformers/multi-qa-MiniLM-L6-cos-v1` (in `backend/app/core/config.py` line 14). An operator following the plan would build an index with the wrong model, causing silent retrieval failure.
- Files: `PLAN.md`, `backend/app/core/config.py`
- Impact: Embedding model mismatch between index build and query time produces garbage retrieval silently.
- Fix approach: Update `PLAN.md` to match the actual default in `config.py`.

**`load_pdf_as_single_document` is a passthrough alias with no distinct behavior:**
- Issue: `backend/app/rag/pdf_loader.py` (line 52-53) defines `load_pdf_as_single_document()` as a one-line alias that just delegates to `load_pdf_documents_with_page_metadata()`. The function name implies single-document extraction (as referenced in `PLAN.md` step 3) but the behavior is page-per-document. The alias is never called anywhere in the current codebase.
- Files: `backend/app/rag/pdf_loader.py` (lines 52-53)
- Impact: Dead code causes confusion about PDF loading strategy.
- Fix approach: Remove the alias. The DEVELOPER_GUIDE already documents the page-level extraction rationale clearly.

**`build_index.py` uses `page` metadata (zero-based) for display without offset:**
- Issue: `backend/app/scripts/build_index.py` (line 31-33) prints `Page: {int(page_number) + 1}` — adding +1 inline rather than using the already-normalized `page_number` field from `_attach_page_metadata()`, which stores `page_number = zero_based_page + 1`. The script duplicates the display logic from `chat_service.py::get_display_page_number()`.
- Files: `backend/app/scripts/build_index.py` (lines 31-33), `backend/app/rag/chat_service.py` (lines 64-78)
- Impact: Violates DRY; if the page normalization logic changes, the script's output will diverge silently.
- Fix approach: Call `get_display_page_number(chunk)` in `build_index.py` instead of recomputing inline.

---

## Known Bugs

**`get_display_page_number` has inconsistent offset logic for page metadata:**
- Symptoms: When `document.metadata["page"]` is present (the normalized path), the function returns `page_number + 1`. When only `page_number` is present (the alternate path), it returns `page_number` directly without adding 1. Since `_attach_page_metadata()` always sets both keys, the alternate-path branch is unreachable in production, but if any document arrives with only `page_number` (e.g., from a different loader), the page offset would be wrong.
- Files: `backend/app/rag/chat_service.py` (lines 64-78), `backend/app/rag/pdf_loader.py` (lines 19-27)
- Trigger: Any document loaded outside `pdf_loader.py::_attach_page_metadata()` that has `page_number` but not `page`.
- Workaround: The dual-metadata approach in `_attach_page_metadata()` prevents this from triggering in practice, but it is structurally fragile.

**`should_use_previous_question` treats any short question as dependent without prior context:**
- Symptoms: When `previous_user_question` is empty and the current question has ≤ 4 words, `should_use_previous_question()` returns `True`. An LLM rewrite call is then made, but `rewrite_input` will just be the question itself (the else-branch at `query_transformer.py` line 67) — a no-op rewrite costing an extra LLM call.
- Files: `backend/app/rag/query_transformer.py` (lines 29-35, 59-68)
- Trigger: First message with ≤ 4 words (e.g., "What is tuition?") when `enable_query_rewrite=True`.
- Workaround: None. The rewrite result returns the same or similar text, so answer quality is unaffected, but a redundant LLM call is made.

---

## Security Considerations

**No authentication or authorization on any API endpoint:**
- Risk: All three endpoints (`/health`, `/api/index/status`, `/api/chat`) are publicly accessible with no API key, token, or session check. `/api/index/status` exposes internal configuration details including absolute file paths (`pdf_path`, `faiss_index_path`), model names, and tuning parameters.
- Files: `backend/app/main.py` (lines 33-69)
- Current mitigation: CORS whitelist limits origins to `localhost:5173`/`127.0.0.1:5173`. This only blocks cross-origin browser requests; direct HTTP clients (curl, scripts) are not blocked.
- Recommendations: Add an API key header check (even a simple shared secret via env var) before deployment beyond localhost. Remove internal path details from the `/api/index/status` response or gate it separately.

**No input length limits on question or chat history:**
- Risk: `ChatRequest` accepts an unbounded `question` string and an unbounded `history` list. A malicious or buggy client could send megabytes of history, causing large prompt payloads to all three LLM providers. This could exhaust token limits, incur unexpected API costs, or cause provider-side errors.
- Files: `backend/app/schemas/chat.py` (lines 15-19)
- Current mitigation: Pydantic enforces `min_length=1` on `question`, but no `max_length`. No cap on `history` list length.
- Recommendations: Add `max_length=2000` on `question`, `max_items=20` on `history` (or similar limits appropriate to the LLM's context window), and document the limits.

**CORS wildcard methods and headers with hardcoded localhost origins:**
- Risk: `allow_methods=["*"]` and `allow_headers=["*"]` are broader than necessary for a JSON POST API. If the origin whitelist is ever relaxed or the app is exposed beyond localhost, all HTTP methods and headers become cross-origin accessible.
- Files: `backend/app/main.py` (lines 22-31)
- Current mitigation: Origins are restricted to two localhost addresses.
- Recommendations: Narrow to `allow_methods=["GET", "POST"]` and `allow_headers=["Content-Type"]`. Move allowed origins to an env var for deployment flexibility.

**`allow_dangerous_deserialization=True` on FAISS index load:**
- Risk: FAISS `.load_local()` uses pickle internally. The `allow_dangerous_deserialization=True` flag acknowledges that loading a tampered FAISS index could execute arbitrary code. The index is stored in `data/indexes/` which is gitignored but the directory is not access-controlled.
- Files: `backend/app/rag/vector_store.py` (line 38)
- Current mitigation: Index files are local-only and not committed to git.
- Recommendations: Document this risk explicitly. Verify the index file checksum or restrict filesystem permissions on the index directory for any non-local deployment.

---

## Performance Bottlenecks

**Cross-encoder reranker loads model weights on first request, not on startup:**
- Problem: `get_reranker_model()` uses lazy initialization — the `CrossEncoder` model loads on the first chat request, not during the lifespan startup. First-request latency is significantly higher than subsequent ones.
- Files: `backend/app/rag/reranker.py` (lines 5-14)
- Cause: Lazy global singleton; reranker is never pre-warmed in `main.py::lifespan()`.
- Improvement path: Add `get_reranker_model()` call inside the lifespan context alongside `load_faiss_vector_store()` to pre-warm the model at startup.

**Full history sent to backend on every message:**
- Problem: `frontend/src/App.jsx` (lines 265-269) sends the entire `messages` array to the backend on every request. As conversation length grows, payload and processing time increase linearly, even though only the last user message is used by `get_last_user_question()`.
- Files: `frontend/src/App.jsx` (lines 265-269), `backend/app/rag/query_transformer.py` (lines 8-13)
- Cause: No history truncation on frontend or backend.
- Improvement path: Trim the history sent to the last N messages (e.g., 6-10) on the frontend, or add backend truncation in `answer_questions()`.

**Embedding model is not cached between FAISS builds:**
- Problem: `build_faiss_vector_store()` and `load_faiss_vector_store()` each call `create_embedding_model()` independently. In a build session, both calls construct a full `HuggingFaceEmbeddings` instance with model weight loading.
- Files: `backend/app/rag/vector_store.py` (lines 10-11, 17, 33-34)
- Cause: No module-level singleton for the embedding model.
- Improvement path: Mirror the `reranker_model` singleton pattern in `vector_store.py`.

---

## Fragile Areas

**Global `vector_store` in `main.py` is not thread-safe:**
- Files: `backend/app/main.py` (lines 9, 13-15)
- Why fragile: `vector_store` is a module-level `None` mutated inside the `lifespan` coroutine. If the lifespan ever fails mid-initialization (e.g., FAISS index file is corrupt), the global stays `None` and every subsequent request gets a 503. There is no health check or readiness signal beyond the boolean check.
- Safe modification: Always check `if vector_store is None` before use (already done). Do not add any code paths that re-assign `vector_store` outside lifespan.
- Test coverage: No test covers the lifespan startup failure path.

**Global `reranker_model` singleton in `reranker.py` is module-level mutable state:**
- Files: `backend/app/rag/reranker.py` (lines 5-14)
- Why fragile: Module-level global is mutated on first call. In test environments this causes cross-test contamination if the real model is accidentally loaded. The existing test for `rerank_documents` patches at the call site, not at the singleton.
- Safe modification: Always access via `get_reranker_model()`; never read `reranker_model` directly.
- Test coverage: No test covers `get_reranker_model()` isolation or reranker integration.

**`answer_questions` passes `resolved_question` (rewritten) to both retrieval and `generate_answer`, discarding the original question:**
- Files: `backend/app/rag/chat_service.py` (lines 106-118)
- Why fragile: The rewritten query is better for FAISS retrieval but may differ meaningfully from the student's actual phrasing. Passing the rewritten form to `generate_answer` means the LLM answers a query the student never asked. For most follow-up rewrites this is equivalent, but for edge cases where the rewrite diverges, the answer may be misaligned.
- Safe modification: Pass the original `question` to `generate_answer()` and `resolved_question` only to retrieval.
- Test coverage: `test_answer_questions_retrieves_with_rewritten_query_and_answers_original_question` asserts both use the rewritten query — this test documents the current behavior but does not validate whether that behavior is correct.

**`normalizeMessageContent` in the frontend uses fragile regex-based markdown parsing:**
- Files: `frontend/src/App.jsx` (lines 20-28, 30-137)
- Why fragile: A custom regex pipeline normalizes LLM output (injecting newlines before list markers, certain transition words). This is brittle against changes in LLM provider formatting. Different providers (Groq vs Anthropic vs Gemini) produce slightly different whitespace/list conventions. The `renderInline()` function only handles `**bold**` — no italic, inline code, or link parsing.
- Safe modification: Keep changes to LLM prompts aligned with what the parser expects. Do not add new formatting conventions without updating `normalizeMessageContent`.
- Test coverage: Zero frontend tests exist.

---

## Scaling Limits

**FAISS index is a single in-memory flat store:**
- Current capacity: Suitable for a single fixed PDF (hundreds of pages, thousands of chunks).
- Limit: FAISS flat index does exact nearest-neighbor search — O(n) per query. For tens of thousands of chunks, query time grows linearly. The index must fit in RAM.
- Scaling path: Switch to an IVF or HNSW FAISS index type for approximate search, or migrate to a managed vector database (Chroma, Qdrant, Pinecone) if multi-document support is needed.

**Single-PDF architecture — no multi-document or dynamic ingestion support:**
- Current capacity: One PDF, configured at startup via `settings.pdf_path`.
- Limit: Adding a second document requires rebuilding the entire index and restarting the backend.
- Scaling path: Extend `build_index.py` to accept multiple PDFs, or add an ingestion API endpoint.

---

## Dependencies at Risk

**`langchain-community` pinned to 0.4.1 — FAISS integration has changed across versions:**
- Risk: LangChain's community package has had breaking changes in vectorstore APIs across minor versions. The `allow_dangerous_deserialization` parameter was added as a breaking change in a prior release. Future updates may require code changes.
- Impact: `vector_store.py` FAISS load/save API could break on upgrade.
- Migration plan: Pin carefully. Test `load_faiss_vector_store` after any `langchain-community` upgrade.

**`faiss-cpu` pinned to 1.13.2 — CPU-only, no GPU path:**
- Risk: No risk of breakage, but `faiss-cpu` cannot be swapped for `faiss-gpu` without code changes if GPU acceleration is needed later.
- Impact: Acceptable for local demo; would require explicit migration for production.
- Migration plan: No action needed for current scope.

**Frontend has no linting, type-checking, or build validation beyond Vite:**
- Risk: `package.json` has no ESLint, no TypeScript, no test runner. All JavaScript in `frontend/src/App.jsx` is untyped. Regressions in the 466-line monolithic component will not be caught by any automated check.
- Impact: Frontend bugs go undetected until manual testing.
- Migration plan: Add ESLint with `eslint-plugin-react-hooks`. Consider TypeScript migration for the frontend.

---

## Missing Critical Features

**No test runner configuration (pytest.ini / pyproject.toml):**
- Problem: No `pytest.ini`, `setup.cfg`, or `pyproject.toml` exists in `backend/`. Tests must be run by manually navigating to `backend/` and running `python -m pytest` or `python -m unittest`. Test discovery paths and PYTHONPATH configuration are undocumented.
- Blocks: CI integration, `pytest` automatic discovery from the repo root.

**No Groq provider unit tests:**
- Problem: `backend/tests/` covers `AnthropicLlmProvider` and `GeminiLlmProvider` with unit tests, but `GroqLlmProvider` in `backend/app/llm/groq_provider.py` has zero dedicated tests.
- Blocks: Confidence in Groq path correctness; regression detection.

**No integration or end-to-end tests for the RAG pipeline:**
- Problem: No tests exercise the full `answer_questions()` → retrieval → rerank → generate flow with a real or mock FAISS store. `pdf_loader.py`, `text_chunker.py`, `vector_store.py`, and `reranker.py` have no test files at all.
- Blocks: Safe refactoring of the retrieval and reranking pipeline.

**No frontend `.env` in the repo:**
- Problem: `frontend/.env.example` exists but no `frontend/.env` is present. The frontend falls back to `http://127.0.0.1:8000` via the `??` nullish coalescing operator in `App.jsx` line 4. This is workable locally but the `.env` setup step is undocumented in `README.md`.
- Blocks: Clear onboarding for new developers.

---

## Test Coverage Gaps

**`backend/app/rag/pdf_loader.py` — no tests:**
- What's not tested: PDF loading, page metadata normalization, error cases (missing file, wrong extension, empty PDF).
- Files: `backend/app/rag/pdf_loader.py`
- Risk: Silent regressions in page number offsets if metadata normalization changes.
- Priority: Medium

**`backend/app/rag/text_chunker.py` — no tests:**
- What's not tested: Chunking behavior, empty document error, chunk size/overlap effects.
- Files: `backend/app/rag/text_chunker.py`
- Risk: Low; function is a thin wrapper around a well-tested LangChain splitter.
- Priority: Low

**`backend/app/rag/vector_store.py` — no tests:**
- What's not tested: `build_faiss_vector_store` with empty documents, `load_faiss_vector_store` with missing index, `save_faiss_vector_store` path creation.
- Files: `backend/app/rag/vector_store.py`
- Risk: Index corruption or missing-file errors are only caught at runtime startup.
- Priority: Medium

**`backend/app/rag/reranker.py` — no tests:**
- What's not tested: `rerank_documents` with empty input, `get_reranker_model` singleton behavior, score extraction from ranked results.
- Files: `backend/app/rag/reranker.py`
- Risk: Reranker is on the critical path for every chat response; silent failures here produce wrong answers.
- Priority: High

**`backend/app/llm/groq_provider.py` — no tests:**
- What's not tested: `GroqLlmProvider.generate_answer()`, `GroqLlmProvider.rewrite_query()`, missing API key validation, blank response fallback.
- Files: `backend/app/llm/groq_provider.py`
- Risk: Groq is the PLAN.md default provider; regressions in its path are high-impact.
- Priority: High

**Frontend `App.jsx` — zero tests:**
- What's not tested: Form submission, history construction, source panel open/close, error banner display, `FormattedMessage` rendering, `normalizeMessageContent` regex transformations.
- Files: `frontend/src/App.jsx`
- Risk: UI regressions are only caught by manual testing.
- Priority: Medium

---

*Concerns audit: 2026-06-09*
