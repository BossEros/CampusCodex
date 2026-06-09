# Stack Research

**Domain:** Production RAG platform (hosted, authed, evaluated, multi-document) — brownfield additions to an existing FastAPI + React single-doc RAG app
**Researched:** 2026-06-10
**Confidence:** HIGH (versions verified against PyPI + official docs on research date; a few free-tier numbers are MEDIUM — vendor pages change frequently)

> **Scope:** This file covers ONLY the stack additions/migrations for this milestone. The existing core (FastAPI 0.136, React 18.3, Vite 5.4, Pydantic 2.13, pydantic-settings, the `LlmProvider` Protocol + factory, langchain-groq/anthropic/google-genai) is kept and is documented in `.planning/codebase/STACK.md`. Do not re-add it here.

---

## Headline Decisions (read first)

| Decision | Choice | One-line reason |
|----------|--------|-----------------|
| Vector DB | **Pinecone** (`pinecone` SDK v5+) | Recruiter-recognizable managed vector DB; 2GB free serverless index, no CC |
| Embedding + Rerank vendor (single) | **Voyage AI** (`voyageai`) | One vendor does both; **200M free tokens** vs Cohere trial's ~1,000 calls/month (one demo session exhausts Cohere) |
| Embedding model | **voyage-3.5** @ **1024 dims** | Matryoshka (256/512/1024/2048); 1024 balances quality vs Pinecone storage |
| Reranker | **rerank-2.5** | Same SDK/vendor as embeddings; clean two-vendor-becomes-one story |
| Relational DB | **Postgres** on **Neon** (free) | Serverless Postgres, scale-to-zero, sub-second wake, branching |
| ORM/driver | **SQLAlchemy 2.x async + asyncpg** (+ Alembic) | First-class async; more mature than SQLModel for async/migrations |
| Auth tokens | **PyJWT** | python-jose is effectively abandoned; FastAPI docs moved to PyJWT |
| Password hashing | **pwdlib[argon2,bcrypt]** | passlib is unmaintained & breaks with bcrypt 5.x; pwdlib is FastAPI's current path |
| App host | **Render** (free web service) | Only true no-credit-card free tier in 2026 (accept cold-start) |
| Frontend host | **Vercel** (free Hobby) | Best React/Vite static + preview-deploy DX |
| Streaming | **FastAPI `StreamingResponse` + SSE**, async LLM SDKs | Native, EventSource-compatible, works with Groq/Anthropic async streams |
| Eval | **ragas 0.4.x** | Standard RAG metric library; judge LLM can reuse the free Groq provider |

> **Architectural dependency (flag for roadmap):** SSE streaming + SQLAlchemy async + asyncpg all require the backend to move to **`async def`** route handlers and async DB sessions. The codebase map (`ARCHITECTURE.md` → "Architectural Constraints") notes all current handlers are sync and "adding streaming would require provider refactoring and `async def` route handlers." Treat the **sync→async migration as an explicit, early phase**, not an incidental change.

---

## Recommended Stack

### Core Technologies

| Technology | Version (2026-06-10) | Purpose | Why Recommended |
|------------|----------------------|---------|-----------------|
| `pinecone` (Python SDK) | **5.x–9.x** (latest 9.1.0; pin a 5.x+ line) | Managed vector store (replaces local FAISS) | Serverless, recruiter-recognizable, generous free tier. **Note the package rename:** install `pinecone`, NOT the deprecated `pinecone-client`. |
| `voyageai` | **0.4.0** | Embeddings (voyage-3.5) + reranking (rerank-2.5) via one client | Single vendor for both; `Client.embed()` and `Client.rerank()` in one SDK; 200M free tokens |
| `sqlalchemy[asyncio]` | **2.0.50** | Async ORM for users/roles/conversations/messages/doc metadata | 2.x has first-class async; industry standard; pairs with Alembic |
| `asyncpg` | **0.31.0** (latest) | Async Postgres driver under SQLAlchemy async engine | Fastest Postgres driver for asyncio; pairs with the SQLAlchemy 2.x async engine. Use latest. |
| `alembic` | **1.18.4** | DB schema migrations | Canonical SQLAlchemy migration tool; required for a real schema lifecycle |
| `PyJWT` | **2.13.0** | Encode/verify JWT access + refresh tokens | Actively maintained; FastAPI's current documented choice |
| `pwdlib[argon2,bcrypt]` | **0.3.0** | Password hashing (Argon2 default, bcrypt for verification/compat) | passlib unmaintained (last release 2020) and breaks on bcrypt 5.x; pwdlib is the modern FastAPI-aligned replacement |
| `ragas` | **0.4.3** | RAG eval: faithfulness, answer relevancy, context precision/recall | The standard "metric science" library; pin the version (metrics evolve) |

### Supporting Libraries

| Library | Version (2026-06-10) | Purpose | When to Use |
|---------|----------------------|---------|-------------|
| `slowapi` | **0.1.9** | Per-IP / per-user rate limiting + daily cap | Protect the public demo from cost/abuse (PROJECT constraint). In-memory backend is fine for free single-instance; Redis backend only if you scale out. |
| `structlog` | **26.1.0** | Structured JSON logging | Fastest of the options; contextvars propagate correctly across asyncio (vs loguru). Recommended over loguru **because** the app is going async. |
| `sentry-sdk[fastapi]` | **2.62.0** | Error tracking / capture | FastAPI integration auto-enables; free Sentry dev tier. Routes structlog ERROR events automatically. |
| `pytest` | **8.x** (latest 9.0.3 — verify plugin compat before adopting 9) | Test runner (currently MISSING — no config exists) | Add `pyproject.toml`/`pytest.ini` + `conftest.py`; codebase has no runner today |
| `pytest-asyncio` | **1.4.0** | Async test support | Required to test async route handlers / async DB sessions |
| `httpx` | **0.28.1** | Async API integration tests via `ASGITransport`/`AsyncClient` | Standard FastAPI testing transport for async endpoints (TestClient is sync) |
| `python-multipart` | latest | Multipart form parsing | Required by FastAPI for file upload (admin document upload) and OAuth2 password form |
| `pypdf` / `pdfplumber` | (already present) | PDF parsing for ingestion | Keep existing loader; reuse for admin multi-doc upload |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **Docker + docker-compose** | Containerize backend, frontend, Postgres for local + deploy parity | Multi-stage backend image. **Big win:** removing FAISS/sentence-transformers/torch slashes image size — the free-tier hosting goal only materializes after that deletion (per Key Decisions). |
| **GitHub Actions** | CI: ruff lint + pytest + frontend build; deploy on merge | Render + Vercel both auto-deploy on push; GH Actions runs the test/lint gate before merge |
| **ruff** | Lint + format (fast, single tool) | Recommended over black+flake8+isort; one config in `pyproject.toml` |
| **Alembic** | Migrations CLI | `alembic revision --autogenerate` against SQLAlchemy 2.x models |

---

## Single Embed+Rerank Vendor: Voyage vs Cohere (the decision)

Both vendors do embeddings AND reranking in one SDK. The discriminator for a **free-tier portfolio demo** is free-tier allowance + dimension fit for Pinecone.

| Criterion | **Voyage AI (chosen)** | Cohere |
|-----------|------------------------|--------|
| Free allowance | **200M free tokens** per account (most models) | Trial key: **~1,000 API calls/month**, 2,000 inputs/min for embed |
| Commercial / demo use on free tier | Verify clause at signup (see note below) | **Trial keys explicitly NOT allowed for production/commercial use** |
| Embedding model | voyage-3.5 (also voyage-3.5-lite, voyage-4 family) | embed v4 |
| Embedding dims | 256 / 512 / **1024** / 2048 (Matryoshka) | 256–1536 configurable (1536 default) |
| Reranker | rerank-2.5 / rerank-2.5-lite (8k-token query) | rerank 3.5 / rerank 4 |
| Python SDK | `voyageai` 0.4.0 — `embed()` + `rerank()` | `cohere` 7.0.3 |
| Pinecone first-class support | Yes (Pinecone documents voyage models) | Yes |

**Verdict — Voyage.** The decisive, *independently verified* discriminator is the free-tier volume: Cohere's trial key caps at **~1,000 API calls/month** — a single recruiter clicking through the demo (each query = embed + rerank calls) can exhaust that in one session. Voyage's **200M free tokens** comfortably covers ingestion of the benchmark corpus plus ongoing demo traffic. Voyage's Matryoshka dims also let you pick **1024** to keep Pinecone storage/read-units low, and one SDK for embed+rerank cleanly mirrors the existing single-`LlmProvider` story.

> **Secondary (verify before relying on it):** Cohere's docs state trial keys are not for production/commercial use; whether a non-revenue portfolio demo counts as "commercial" is ambiguous. Voyage's commercial-use stance on the free tier was **not independently confirmed** in this research — check Voyage's current terms at signup. The decision does **not** depend on this point; the calls/month cap alone settles it.

**Choose Cohere instead if:** you later need multimodal (image) embeddings as a first-class feature, or you're already paying Cohere — its embed v4 is multimodal. Not worth it for this free-tier v1.

**Dimension ↔ Pinecone gotcha:** the Pinecone index `dimension` is fixed at creation and MUST equal your embedding output dim. Decide **1024** up front; changing dims later means recreating the index and re-embedding everything. Also set the index `metric` to **cosine** (matches the current `multi-qa-MiniLM-...-cos` semantics).

---

## Free-Tier Constraints & Gotchas (every external service)

| Service | Free tier (verify at signup) | Key gotcha for THIS demo |
|---------|------------------------------|--------------------------|
| **Pinecone** (serverless) | 2 GB storage (~300k records), ~2M Write Units/mo, ~1M Read Units/mo, 5 indexes, 1 project. WU/RU reset monthly. No SLA/RBAC/support. | Index `dimension` + `metric` fixed at creation → lock to 1024/cosine. Read units burn on every query — rate-limit user queries (slowapi) to protect the monthly RU budget. |
| **Voyage AI** | 200M free tokens per account (50M for some specialized models). | Free, but RATE-LIMITED — implement retry/backoff in the embedding+reranker provider. Tokens are shared across embed + rerank. Re-verify commercial-use terms at signup. |
| **Neon** (Postgres) | 100 projects × 0.5 GB storage, 100 CU-hours/mo compute, scale-to-zero, branching. | **Autosuspends after ~5 min idle** but wakes in a few hundred ms — fine for a demo. First query after idle has a small wake latency; warm a connection on app startup if it matters. |
| **Render** (web service) | True free tier, **no credit card**, web service + static site (+ time-limited free Postgres). | **Spins down after 15 min inactivity; ~1 min cold start.** Recruiter-facing demo gotcha → either accept it (note "first load ~1 min" in README) or add a cron/uptime ping to keep warm. Render's free Postgres has historically been time-limited (expires after a window) — **confirm current terms**; regardless, prefer **Neon** for the DB and Render only for the API. |
| **Vercel** (frontend) | Free Hobby: static React/Vite hosting, preview deploys, global CDN. | Non-commercial Hobby terms; fine for a portfolio. Set `VITE_API_BASE_URL` to the Render API URL; configure CORS on the backend to the Vercel domain. |
| **Sentry** | Free developer tier (limited events/mo). | Sample/limit events so you don't exhaust the quota from a noisy demo. |
| **Groq / Anthropic / Gemini** (existing) | Groq has a generous free tier (already in use). | Reuse **Groq free tier as the ragas judge LLM** to keep eval cost at $0. |

**Net free-tier topology:** React → **Vercel** | FastAPI → **Render** | Postgres → **Neon** | Vectors → **Pinecone** | Embed+Rerank → **Voyage** | LLM/Eval-judge → **Groq**. All have no-up-front-cost tiers; only Render's cold start needs a README caveat.

---

## Streaming (SSE) — compatibility notes

- Use FastAPI **`StreamingResponse`** with an **async generator** that yields `data: {json}\\n\\n` SSE frames (the double newline is mandatory or `EventSource` silently drops events).
- Groq (via its OpenAI-compatible stream) and Anthropic both expose async streaming; Anthropic emits typed `content_block_delta` events (token text inside), Groq yields OpenAI-style delta chunks. The existing `LlmProvider` Protocol should gain a `stream_answer()` method so each provider adapts its native stream to a common token iterator.
- Requires async SDK clients (`AsyncAnthropic`, async Groq) and `async def` handlers — same async migration flagged above.
- Frontend: consume with `EventSource` or `fetch` + `ReadableStream` reader in `App.jsx` (replace the current single-shot POST).

---

## Installation

```bash
# --- Backend: vector + embeddings/rerank (NEW), remove FAISS/sentence-transformers ---
pip install "pinecone>=5,<10" voyageai

# --- Postgres + async ORM ---
pip install "sqlalchemy[asyncio]==2.0.50" asyncpg==0.31.0 alembic==1.18.4

# --- Auth ---
pip install PyJWT==2.13.0 "pwdlib[argon2,bcrypt]==0.3.0" python-multipart

# --- Production tooling ---
pip install slowapi==0.1.9 structlog==26.1.0 "sentry-sdk[fastapi]==2.62.0"

# --- Evaluation ---
pip install ragas==0.4.3

# --- Dev / test ---
pip install -D pytest "pytest-asyncio==1.4.0" httpx==0.28.1 ruff

# --- REMOVE (the migration is a deletion — frees image size for free-tier hosting) ---
pip uninstall faiss-cpu sentence-transformers langchain-huggingface
# (drop torch/transformers if they were only pulled in by sentence-transformers)
```

> Frontend needs no new runtime deps for SSE (native `EventSource`/`fetch`). Optional: a small SSE helper if you prefer POST-based streaming over GET.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **Voyage** (embed+rerank) | Cohere embed v4 + rerank 3.5/4 | If you need multimodal image embeddings, or already have a paid Cohere account (trial key caps at ~1k calls/mo and forbids commercial use) |
| **SQLAlchemy 2.x async + asyncpg** | SQLModel | If you want Pydantic+ORM unified models and a smaller surface; but SQLModel lags SQLAlchemy/Pydantic releases and its async story is weaker — riskier for this milestone |
| **asyncpg** | psycopg 3 (3.3.4) async | If you want one driver for sync+async or richer type adaptation; asyncpg is faster for pure-async |
| **pwdlib[argon2,bcrypt]** | argon2-cffi directly (25.1.0) | If you want only Argon2 with zero abstraction; pwdlib gives a clean verify+upgrade path and bcrypt compat |
| **Render** (app host) | Fly.io / Railway | If you'll pay ~$5/mo for always-on (no cold start). Both now require a credit card and have no real free tier in 2026. |
| **Neon** (Postgres) | Supabase | If you also want bundled auth/storage/realtime. But Supabase **pauses projects after 1 week idle (needs manual unpause)** — worse for a "click anytime" demo than Neon's auto-wake. |
| **structlog** | loguru (simpler) | If you value 3-line setup over async-correct context propagation; for an async app, structlog is the better fit |
| **ragas** | DeepEval / TruLens | DeepEval for CI/CD gates, TruLens for trace-aware observability. ragas is the simplest "score a golden set" fit; deeper eval/observability is explicitly Out of Scope for v1. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **python-jose** | Effectively abandoned (last release ~3 yrs, CVE history); FastAPI docs moved off it | **PyJWT** |
| **passlib / passlib[bcrypt]** | Unmaintained since 2020; breaks with **bcrypt 5.x** (`__about__` AttributeError) | **pwdlib[argon2,bcrypt]** |
| **pinecone-client** (old package) | Renamed/deprecated; new SDK is the `pinecone` package | **`pinecone`** |
| **Local FAISS + sentence-transformers + cross-encoder** | Heavy (torch/transformers) → bloated image, won't fit free-tier RAM; the whole point of this milestone is to delete them | **Pinecone + Voyage embed/rerank APIs** |
| **Railway / Fly.io "free" tier** | No real free tier in 2026 (trial credits only; require CC) for an always-on demo | **Render** free web service (accept cold start) or pay for always-on |
| **Supabase free DB for an idle demo** | Pauses entirely after 1 week idle, needs manual dashboard unpause | **Neon** (auto-wake on query) |
| **Sync route handlers + sync DB calls** | Blocks the event loop under streaming + async DB; defeats async DB driver | **`async def` handlers + AsyncSession + async LLM SDKs** |
| **Cohere trial key for the public demo** | ~1k calls/mo cap (one session exhausts it); forbids commercial use | **Voyage** free tier (200M tokens) |

---

## Stack Patterns by Variant

**If the recruiter demo must load instantly (no cold start):**
- Move the API to **Fly.io or Railway Hobby (~$5/mo)** for always-on, OR keep Render free + add an uptime-ping cron to keep it warm.
- Because: Render free spins down after 15 min; the keep-warm ping is the zero-cost mitigation.

**If you exceed Voyage's 200M free tokens or hit rate limits:**
- Reduce embedding `output_dimension` to 512, cache embeddings of unchanged chunks, and rate-limit re-ingestion.
- Because: tokens are shared across embed + rerank; ingestion of large docs is the main spender.

**If you later add multimodal documents (images/scanned PDFs):**
- Switch the embedding provider abstraction to **Cohere embed v4** (multimodal).
- Because: voyage-3.5 is text-first; the provider Protocol makes the swap localized.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `sqlalchemy[asyncio]` 2.0.50 | `asyncpg` 0.31.0 | Standard, well-tested async pairing for FastAPI; no known blocker at these versions |
| `pwdlib` 0.3.0 | `bcrypt` 5.0.0, `argon2-cffi` 25.1.0 | pwdlib wraps these cleanly (unlike passlib, which breaks on bcrypt 5.x) |
| `pinecone` 5.x+ | Python 3.12 (existing) | Use `pinecone` package; do NOT also install `pinecone-client` (conflict) |
| `pytest` 9.0.3 | `pytest-asyncio` 1.4.0 | If a plugin lags pytest 9, pin pytest to 8.4.x — verify the plugin matrix before adopting 9 |
| `ragas` 0.4.3 | a judge LLM + embeddings | Most metrics need an LLM-as-judge + embeddings; reuse Groq (free) as judge to keep eval at $0. **Pin ragas** — metric APIs change between minors. |
| FastAPI 0.136 (existing) | `slowapi` 0.1.9, `sentry-sdk[fastapi]` 2.62.0, `StreamingResponse` (Starlette) | All Starlette/FastAPI-native; no version friction expected |

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| Package versions | HIGH | Verified live against PyPI on 2026-06-10 |
| python-jose / passlib deprecation | HIGH | FastAPI discussions + docs change confirmed; PyPI release dates corroborate |
| Voyage 200M tokens / Cohere ~1k calls cap | MEDIUM-HIGH | Both confirmed across vendor + secondary sources; the decision rests on these |
| Voyage commercial-use clause | LOW | Inferred, NOT independently confirmed — re-verify at signup (does not affect the decision) |
| Pinecone free-tier numbers | MEDIUM | Multiple 2026 sources agree (2GB / 2M WU / 1M RU); confirm on pinecone.io/pricing at signup |
| Render/Neon/Supabase tiers | MEDIUM-HIGH | Consistent across 2026 sources; Render no-CC + 15-min spin-down and Neon 5-min auto-wake well-corroborated. Render free-Postgres expiry = recall, not verified here — confirm. |
| Streaming pattern | HIGH | Standard FastAPI `StreamingResponse` + async-generator SSE; provider async SDKs confirmed |
| Async-migration dependency | HIGH | Stated directly in the codebase `ARCHITECTURE.md` constraints |

---

## Sources

- PyPI version index (live, 2026-06-10) — PyJWT 2.13.0, pwdlib 0.3.0, bcrypt 5.0.0, argon2-cffi 25.1.0, voyageai 0.4.0, cohere 7.0.3, pinecone 9.1.0, sqlalchemy 2.0.50, asyncpg 0.31.0, alembic 1.18.4, ragas 0.4.3, slowapi 0.1.9, structlog 26.1.0, sentry-sdk 2.62.0, httpx 0.28.1, pytest 9.0.3, pytest-asyncio 1.4.0, psycopg 3.3.4 — HIGH
- FastAPI discussions #9587 / #11345 (python-jose abandonment) & #11773 (passlib) + FastAPI OAuth2-JWT docs — HIGH
- fastapi-users password-hash docs (pwdlib, Argon2 default) — HIGH
- Pinecone docs: database-limits, quotas-and-limits, "serverless free 3x" blog — MEDIUM
- Voyage AI docs (embeddings, reranker, pricing) + MongoDB Voyage docs (200M free tokens, billing) + voyage-3.5 blog (Matryoshka dims) — MEDIUM
- Cohere docs: rate-limits (trial key = ~1k calls/mo, no commercial use) + pricing — MEDIUM
- Render "platforms with a real free tier 2026" + FastAPI deployment article (15-min spin-down, no CC) — MEDIUM/HIGH
- Neon vs Supabase 2026 comparisons (Neon 5-min auto-wake; Supabase 1-week pause) — MEDIUM
- SQLAlchemy 2.0 async + asyncpg FastAPI guides; SQLModel async caveat — HIGH/MEDIUM
- Groq + Anthropic SSE streaming guides (StreamingResponse async generator, `data:` framing) — HIGH
- ragas docs (faithfulness, available metrics, LLM-judge) — HIGH

---
*Stack research for: production RAG platform (brownfield additions)*
*Researched: 2026-06-10*
