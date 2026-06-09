# Pitfalls Research

**Domain:** Production RAG platform migration — local single-doc FAISS app → hosted, authed, multi-doc, evaluated RAG on free tiers (Pinecone + Voyage + Neon + Render/Vercel)
**Researched:** 2026-06-10
**Confidence:** HIGH (anchored to the chosen stack in STACK.md and the concrete anti-patterns in `.planning/codebase/CONCERNS.md` / `ARCHITECTURE.md`; PyJWT `algorithms` behavior and Render SSE buffering independently verified)

> **Scope:** These are the SPECIFIC mistakes for THIS migration, hooked to either a concrete item already in the codebase map or to a chosen stack component. Generic web-dev advice is deliberately excluded. Phase names below assume STACK.md's stated structure: **sync→async migration is an explicit early phase**, and **a thin authed slice is deployed by ~phase 2–3** (not last).

---

## Critical Pitfalls

### Pitfall 1: Eval/KB contamination — uploads pollute the fixed benchmark in Pinecone

**What goes wrong:**
Admin-uploaded documents and the canonical `student_manual` golden benchmark both live in Pinecone. If they share one index/namespace, an admin upload changes what the eval queries retrieve, so RAGAS context-precision/recall scores drift with every upload. This directly violates the PROJECT.md constraint: *"user-uploaded docs do not affect eval scores."* The eval number becomes meaningless and non-reproducible.

**Why it happens:**
Pinecone's free tier allows only **1 project / 5 indexes**, so developers default to dumping everything into the default namespace of one index. Namespaces are an afterthought because the existing FAISS app had exactly one corpus and no concept of scoping.

**How to avoid:**
Put the benchmark corpus in a **dedicated namespace** (e.g. `benchmark`) — or a dedicated index if you can spare one of the 5. The eval pipeline queries ONLY that namespace and is the only writer to it. Admin uploads write to a separate namespace (e.g. `shared-kb`). Make the namespace a required, non-defaulted argument in the embedding/index provider abstraction so a query can never silently hit the wrong corpus.

**Warning signs:**
RAGAS scores change between runs with no eval-code changes; the benchmark namespace vector count grows after an admin upload; `index.describe_index_stats()` shows benchmark vectors mixed with uploaded-doc vectors.

**Phase to address:** Vector-DB migration phase (define namespaces at index creation) + Eval phase (eval reads benchmark namespace only).

---

### Pitfall 2: Pinecone dimension/metric lock-in — and the 384→1024 re-embed with no migration path

**What goes wrong:**
Pinecone serverless index `dimension` and `metric` are **fixed at creation**. The existing index uses `multi-qa-MiniLM-L6-cos-v1` at **384 dims**; voyage-3.5 outputs **1024 dims**. There is no "convert" path — the entire corpus must be re-embedded with Voyage and re-upserted into a NEW 1024-dim index. Worse: if you create the index at the wrong dimension (e.g. you leave a 384 default, or pick Voyage's 2048), every upsert fails or, if dims happen to match a wrong model, retrieval silently returns garbage (the API-era version of CONCERNS.md's "embedding model mismatch produces garbage retrieval silently").

**Why it happens:**
Treating embedding-model swap as a config change rather than a data migration. The Matryoshka choice (256/512/1024/2048) adds a decision point that's easy to get wrong.

**How to avoid:**
Lock **1024 dims + cosine metric** at index creation (matches the existing `-cos` semantics; STACK.md decision). Store the embedding model name + dimension in Postgres document metadata so a future model swap is detectable. Re-embedding the benchmark is a one-time scripted step (replaces `build_index.py`); budget it explicitly. Assert `len(embedding) == index.dimension` in the ingestion provider before upsert.

**Warning signs:**
Upsert errors mentioning dimension mismatch; retrieval returns plausible-looking but topically-wrong chunks; query embeddings produced by a different model/version than ingest embeddings.

**Phase to address:** Vector-DB migration phase (create index with correct dim/metric, re-embed benchmark).

---

### Pitfall 3: Async migration regression — the new Voyage/LLM provider re-blocks the event loop

**What goes wrong:**
The whole point of the sync→async migration (CONCERNS.md: `POST /api/chat` is sync `def`, blocking uvicorn workers) is undone because `voyageai.Client` is **synchronous**. Calling `client.embed()` / `client.rerank()` inside an `async def` handler runs blocking network I/O on the event loop thread, stalling every concurrent request — the exact failure the migration was meant to fix, now hidden inside the shiny new provider abstraction. Same trap for any LangChain `ChatGroq` / sync SDK call left in place.

**Why it happens:**
"It's an API call now, so it must be async" — but the SDK being remote doesn't make it non-blocking. The provider abstraction makes the blocking call easy to overlook because it's behind a clean interface.

**How to avoid:**
In the embedding/reranker provider, wrap sync Voyage calls in `await asyncio.to_thread(...)` (or use an async client if Voyage ships one). Audit every provider method: no bare sync network call inside `async def`. For LLM streaming, use the genuinely async SDKs (`AsyncAnthropic`, async Groq) per STACK.md. Add a load test (e.g. 10 concurrent `/api/chat`) that fails if p95 latency scales linearly with concurrency.

**Warning signs:**
Concurrent requests serialize (2 users = ~2× latency each); a single slow embed call freezes unrelated health checks; CPU shows one busy thread while requests queue.

**Phase to address:** Sync→async migration phase (foundational — do before streaming and before the provider abstractions are written).

---

### Pitfall 4: Mixing sync and async DB sessions / import-time binding leaks into Postgres layer

**What goes wrong:**
Two failure modes: (a) calling a sync SQLAlchemy `Session` or sync `psycopg` from an `async def` handler blocks the loop and can corrupt connection state; (b) repeating the existing import-time anti-pattern (CONCERNS/ARCHITECTURE: `EMBEDDING_MODEL_NAME = settings...` bound at import in `vector_store.py`) by creating the async engine or `sessionmaker` at module import — which binds the DB URL before env/secrets are loaded and breaks test fixtures and per-request session scoping.

**Why it happens:**
SQLAlchemy 2.x supports both sync and async with nearly identical APIs, so it's easy to copy a sync snippet. The codebase already has an import-time-binding habit to copy.

**How to avoid:**
Use `create_async_engine` + `async_sessionmaker` + `AsyncSession` exclusively. Provide sessions via a FastAPI dependency (`async def get_session()` yielding `AsyncSession`), constructed inside the lifespan/function body — never at import. One session per request; never share a session across `await` points concurrently.

**Warning signs:**
`MissingGreenlet` / "greenlet_spawn has not been called" errors; `InterfaceError: another operation is in progress`; tests that pass alone but fail together (shared engine state).

**Phase to address:** Persistence/Postgres phase (built on the async foundation from Pitfall 3's phase).

---

### Pitfall 5: Neon autosuspend kills pooled connections — first query after idle errors

**What goes wrong:**
Neon free tier **autosuspends after ~5 min idle**. SQLAlchemy's async pool keeps connection objects that point at now-dead asyncpg sockets. The first request after idle (e.g. the recruiter who opens the demo) throws `ConnectionDoesNotExistError` / `connection was closed` instead of transparently reconnecting.

**Why it happens:**
Default pool settings assume an always-on DB. Local Postgres never suspends, so this is invisible in dev and only appears on the deployed free-tier demo — the worst place to discover it.

**How to avoid:**
Configure the async engine with `pool_pre_ping=True` (validates/replaces dead connections before use) and a conservative `pool_recycle` (e.g. 300s). Optionally warm one connection on app startup. Keep the pool small (Neon free + Render free = few connections available anyway).

**Warning signs:**
Demo works during active testing, throws 500 on the first click after a coffee break; connection-closed errors clustered after idle periods; errors only on the deployed instance, never locally.

**Phase to address:** Persistence/Postgres phase; re-verify in the deploy phase against real Neon.

---

### Pitfall 6: Multi-tenant data leakage — users see others' chats, or queries leak across scope

**What goes wrong:**
Two leak surfaces: (a) **chat history** — a `GET /conversations/{id}` that filters only by id, not by `user_id`, lets any authed user read anyone's chats (IDOR); (b) **vector scope** — once multi-doc + per-scope namespaces exist, a missing namespace/metadata filter on the Pinecone query returns chunks the user shouldn't see. In a shared-KB v1 the KB is intentionally shared, but conversation/message rows are per-user and MUST be filtered server-side.

**Why it happens:**
Filtering by resource id alone feels sufficient; the `user_id` check is forgotten because the frontend "only requests its own data." Authorization is conflated with authentication (logged in ≠ authorized for this row).

**How to avoid:**
Every query for user-owned data includes `WHERE user_id = current_user.id` enforced in the data-access layer, not the route. RBAC: only `admin` hits document-management/upload endpoints (decorator/dependency, not UI-only hiding). Write an explicit test: user A cannot fetch user B's conversation (expect 404/403).

**Warning signs:**
Endpoints take an id but no authenticated-user filter; admin actions gated only in React; no test that crosses user boundaries.

**Phase to address:** Auth/RBAC phase (ownership checks) + Persistence phase (schema with `user_id` FKs).

---

### Pitfall 7: JWT algorithm confusion, weak verification, and refresh handling

**What goes wrong:**
Classic JWT failures, made concrete for PyJWT: (a) calling `jwt.decode()` without pinning `algorithms=[...]`, or computing it from the token's own `alg` header — enabling `alg: none` or RS256→HS256 confusion attacks; (b) no token expiry / no refresh rotation, so a leaked token is valid forever; (c) storing tokens insecurely (access token in `localStorage` is XSS-exfiltratable).

**Why it happens:**
Copy-pasted tutorials that pass tokens around without pinning algorithms or expiries. STACK.md correctly chose PyJWT over abandoned python-jose, but PyJWT still requires correct usage.

**How to avoid:**
Always `jwt.decode(token, key, algorithms=["HS256"])` with a hardcoded list (verified: PyJWT requires explicit `algorithms` and warns against deriving it from the token — RFC 8725 §2.1). Short-lived access tokens (~15 min) + longer refresh tokens; rotate refresh tokens on use and store a server-side denylist/version so refresh can be revoked. Sign with a strong secret from env (not in repo — see Pitfall 8). For refresh tokens, prefer an httpOnly, Secure, SameSite cookie over `localStorage`.

**Warning signs:**
`jwt.decode` called without `algorithms`; tokens with no `exp`; refresh token that never rotates or can't be revoked; access token visible in `localStorage`.

**Phase to address:** Auth/RBAC phase.

---

### Pitfall 8: Secrets in a PUBLIC repo and in the hosted demo

**What goes wrong:**
This is a **public portfolio repo** with real API keys behind a public demo (Voyage, Pinecone, Groq/Anthropic, Neon, Sentry, JWT secret). A committed `.env`, a key pasted into `docker-compose.yml`, or a key in CI logs is instantly scraped by bots and run up costs / abused. Git history retains the secret even after deletion.

**Why it happens:**
Local dev uses a `.env`; the leap to "public repo + live demo" multiplies exposure, and the existing app never had secrets to manage. CONCERNS.md already notes there's no env hygiene story.

**How to avoid:**
`.env` in `.gitignore` (verify before first push); commit only `.env.example` with placeholder values. All real secrets in Render/Vercel/Neon dashboard env vars, never in the repo or image. Add a secret-scanner (gitleaks/trufflehog) to CI. If a key is ever committed, **rotate it** — deleting the commit is not enough. Use distinct keys for local vs deployed so a local leak doesn't compromise the demo.

**Warning signs:**
`.env` shows up in `git status`/`git log`; keys hardcoded in compose/Dockerfile; gitleaks flags history; the same key used everywhere.

**Phase to address:** Production-engineering phase (CI secret scan) — but `.gitignore`/`.env.example` must be correct **from the very first commit of this milestone**.

---

### Pitfall 9: Free-tier rate limits & cost blowups on a public demo

**What goes wrong:**
Three blowup vectors: (a) **Voyage** is rate-limited even on 200M free tokens — ingesting a multi-page upload fires many embed calls; without backoff you hit 429s mid-ingest and leave a half-indexed doc. (b) **Pinecone read units** burn on every query; an unthrottled public demo (or a bot) drains the ~1M RU/month budget. (c) **LLM tokens** — unbounded `question`/`history` (CONCERNS.md: no `max_length` on question, no cap on history) lets one client send megabyte prompts, exhausting LLM free tiers and Voyage tokens.

**Why it happens:**
Local dev has one user and no quotas, so abuse/cost is invisible until the demo is public.

**How to avoid:**
Implement retry-with-exponential-backoff in the Voyage provider; batch embeds and make ingestion idempotent/resumable. Enforce `max_length` on question + `max_items` on history (Pydantic) — closes the existing flagged hole. slowapi per-user daily cap (PROJECT constraint) — but see Pitfall 10 for the proxy gotcha. Set Sentry event sampling so a noisy demo doesn't exhaust Sentry's quota too.

**Warning signs:**
429s during ingestion; Pinecone RU dashboard climbing fast; one IP/user driving most traffic; large request payloads in logs.

**Phase to address:** Ingestion phase (Voyage backoff/batching), Auth+ratelimit phase (caps), and request-validation early.

---

### Pitfall 10: slowapi behind Render's proxy rate-limits the wrong IP

**What goes wrong:**
Render terminates TLS at a proxy, so the request's source IP is the **proxy's**, not the client's. slowapi keyed on `get_remote_address` then sees one IP for everyone — so either the entire demo is throttled as a single client (legit users blocked) or, if you key on something else, the per-user cap silently does nothing. Either way the cost-protection constraint is defeated.

**Why it happens:**
slowapi defaults to the socket peer IP; works perfectly locally, breaks behind any reverse proxy. Invisible until deployed.

**How to avoid:**
Behind the proxy, key the limiter on the **authenticated user id** (the demo is authed anyway) rather than IP — this is also the truer "per-user daily cap." If keying on IP for unauthed routes, derive it from a trusted `X-Forwarded-For` (only trust it because Render sets it). Verify on the deployed instance that two different users get independent limits.

**Warning signs:**
After deploy, second user gets 429 immediately; or the cap never triggers no matter how many requests; all rate-limit logs show the same IP.

**Phase to address:** Auth+rate-limit phase; verify in deploy phase.

---

### Pitfall 11: SSE breaks in production — proxy buffering, wrong framing, CORS

**What goes wrong:**
Streaming works locally, arrives all-at-once (or not at all) in production. Causes: (a) Render **static-site rewrites buffer** streamed bodies (delivered as a few large chunks, not token-by-token); (b) missing `data: {json}\n\n` double-newline → `EventSource` silently drops events (STACK.md flag); (c) missing `text/event-stream` content-type and `X-Accel-Buffering: no` / `Cache-Control: no-cache` headers; (d) CORS not allowing the streaming endpoint from the Vercel origin.

**Why it happens:**
Local uvicorn has no buffering proxy; the existing app is a single-shot POST with no streaming concerns at all (ARCHITECTURE: "adding streaming would require provider refactoring and async handlers").

**How to avoid:**
Point the Vercel frontend **directly at the Render API URL** (`VITE_API_BASE_URL`) instead of routing through a Render static-site rewrite, which avoids the rewrite-buffering trap. Set `media_type="text/event-stream"`, `Cache-Control: no-cache`, `X-Accel-Buffering: no` on the `StreamingResponse`. Yield correct `data: ...\n\n` frames. Send periodic keep-alive comments to defeat idle-connection closes. Test streaming against the deployed URL, not just localhost.

**Warning signs:**
Tokens arrive in one burst after deploy; `EventSource` `onmessage` never fires; stream works on localhost only; CORS error on the stream endpoint.

**Phase to address:** Streaming phase; re-verify in deploy phase.

---

### Pitfall 12: RAGAS eval — judge nondeterminism, contamination, and cost

**What goes wrong:**
(a) LLM-as-judge metrics (faithfulness, answer relevancy) are **nondeterministic** — same inputs score differently per run, so a "62% → 58%" drop may be judge noise, not a regression. (b) Eval reads a contaminated index (see Pitfall 1). (c) Judge cost/rate-limits — running the full golden set fires many judge LLM + embedding calls; on free tiers this hits limits or runs slowly, and a noisy judge model makes scores unstable.

**Why it happens:**
RAGAS metrics look like deterministic numbers but are LLM-derived. Treating one eval run as ground truth.

**How to avoid:**
Pin the judge model and set temperature to 0 where supported. Reuse Groq free tier as the judge (STACK.md) to keep cost ~$0, with backoff for rate limits. Run eval against the **fixed benchmark namespace only**. Report scores as ranges / run eval N times for critical comparisons, and surface "judge model + date" alongside the number in the README so the metric is interpretable, not presented as exact truth.

**Warning signs:**
Scores swing run-to-run with no code change; eval run hits judge rate limits or takes very long; eval retrieval count changes after an upload (contamination).

**Phase to address:** Eval phase (depends on the benchmark-namespace decision from the vector-DB phase).

---

### Pitfall 13: Free-tier cold starts surprise the recruiter

**What goes wrong:**
Render free **spins down after 15 min inactivity (~1 min cold start)** and Neon autosuspends (~sub-second wake). A recruiter clicking the demo cold waits ~1 minute on a blank screen and assumes it's broken — the exact opposite of the portfolio goal.

**Why it happens:**
Always-on local dev; the cold start only manifests for the first visitor after idle.

**How to avoid:**
Either accept it and put a clear "first load may take ~1 min (free tier waking up)" note + a loading state in the README/UI, or add a cron/uptime ping to keep Render warm (zero-cost mitigation). Don't let the frontend show a generic error during the wake window — show a "starting up" state.

**Warning signs:**
First request after idle times out or hangs; demo "works" only right after you deploy/test it; frontend shows a hard error instead of a waking state.

**Phase to address:** Deploy phase + README/polish phase.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Single Pinecone namespace for benchmark + uploads | One less config step; fits 5-index free cap | Breaks eval integrity (Pitfall 1); near-impossible to untangle scores later | **Never** — namespace split is the whole eval-integrity story |
| Wrap sync Voyage call directly in `async def` (no `to_thread`) | Compiles, "looks async," works in dev | Re-blocks the loop under load — undoes the migration (Pitfall 3) | Never for request-path calls; tolerable only in offline scripts |
| Access token in `localStorage` | Trivial frontend wiring | XSS token theft (Pitfall 7) | MVP only if refresh token is httpOnly cookie and access token is short-lived |
| Skip `pool_pre_ping` (default pool) | Less config | First-request-after-idle 500s on Neon (Pitfall 5) | Never on a free-tier autosuspending DB |
| No request size limits (keep existing unbounded question/history) | Faster to ship | Cost blowup / token exhaustion on public demo (Pitfall 9) | Never once internet-facing |
| Hardcode key in docker-compose for "local only" | Quick local run | Leaks to public repo / image (Pitfall 8) | Never in a public repo |
| Re-embed benchmark manually each time | No script to write | Non-reproducible eval corpus; drift | MVP if scripted-and-committed soon after |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **Pinecone serverless** | Querying immediately after upsert (eventual consistency) returns an incomplete index — eval/first-query reads missing vectors | After ingest, poll `describe_index_stats()` until vector count matches expected before querying/eval; don't assume read-after-write |
| **Pinecone** | Index dim/metric chosen wrong, discovered after data loaded | Create index with **1024 / cosine** up front; assert embedding length before upsert (Pitfall 2) |
| **Voyage AI** | Using the same `input_type` for ingest and query (or omitting it) → silent retrieval degradation | Use `input_type="document"` at ingest and `input_type="query"` at query time; keep consistent with the model used to build the index |
| **Voyage AI** | Sync `Client` called on event loop; no backoff | `asyncio.to_thread` + exponential backoff; batch embeds (Pitfalls 3, 9) |
| **Neon** | Pool holds connections across autosuspend | `pool_pre_ping=True`, small `pool_recycle` (Pitfall 5) |
| **Render** | Frontend routed through Render static-site rewrite buffers SSE | Point Vercel frontend directly at the Render API URL; set streaming headers (Pitfall 11) |
| **slowapi + Render proxy** | Keyed on remote IP → everyone shares the proxy IP | Key on authenticated user id (Pitfall 10) |
| **FAISS removal** | Leaving `allow_dangerous_deserialization=True` / FAISS load path / torch deps behind | Delete FAISS+sentence-transformers+cross-encoder entirely — the pickle-RCE risk (CONCERNS.md) goes away and image shrinks (the free-tier hosting win) |
| **Sentry** | Default sampling → noisy demo exhausts free event quota | Set `traces_sample_rate` / event sampling low |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Sync network call (Voyage/LLM/DB) inside `async def` | Concurrent requests serialize; health check freezes under load | `asyncio.to_thread` / async clients; concurrency load test | Immediately under 2+ concurrent users |
| Full chat history sent + embedded every turn (existing flaw) | Latency + token cost grow linearly with conversation length | Truncate history to last N turns (frontend or backend) | Long conversations / many turns |
| Unbounded ingestion of large uploads | 429s mid-ingest; partial index; Voyage token burn | Batch + backoff + resumable ingest | Any multi-page upload |
| Unthrottled queries on Pinecone free RU | Read-unit budget drains; queries start failing late in month | Per-user cap (slowapi keyed on user); cache repeated queries | Public/bot traffic |
| Provider re-instantiated per request (existing anti-pattern) | Redundant client/connection setup each call | Instantiate providers once in lifespan, inject (PROJECT requirement) | High request rate |
| Cold start on first visit | ~1 min blank wait, looks broken | Keep-warm ping or clear waking-state UI | After 15 min idle (every demo gap) |

## Security Mistakes

Domain-specific issues beyond OWASP basics.

| Mistake | Risk | Prevention |
|---------|------|------------|
| `jwt.decode()` without pinned `algorithms` | `alg:none` / RS256→HS256 confusion → forged tokens | `algorithms=["HS256"]` hardcoded; never derive from token (RFC 8725) |
| No refresh rotation / revocation | Leaked token valid forever | Short access TTL + rotating refresh + server-side revocation list |
| Secrets in public repo / image | Key scraping, cost abuse | `.gitignore` `.env`, dashboard env vars, gitleaks in CI, rotate on leak |
| Conversation fetch filters by id only | IDOR — read other users' chats | `WHERE user_id = current_user.id` in data layer; cross-user test |
| RBAC enforced only in React | Anyone can call admin upload/delete via curl | Server-side role dependency on every admin route |
| CORS `allow_origins=["*"]` + `allow_credentials=True` | Illegal combo (browser rejects) / over-broad if it "works" with cookie auth | Explicit Vercel origin list; narrow methods/headers (CONCERNS.md flagged `*`) |
| `/api/index/status` leaks internal paths/config (existing) | Recon for attackers | Remove internal details or gate behind admin auth |
| FAISS pickle deserialization left in (existing) | RCE via tampered index | Remove FAISS entirely with the migration |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Generic error during cold start | Recruiter thinks demo is broken | "Service is waking up (~1 min on free tier)" state |
| No streaming feedback / spinner only | Feels slow even when streaming works | Render tokens as they arrive; show typing indicator |
| Rewritten follow-up query answered instead of user's actual question (existing fragile area) | LLM answers a question the user didn't ask | Retrieve with rewritten query, generate against original (CONCERNS.md note) |
| Lost source citations after pipeline swap | Trust signal (the core value prop) disappears | Preserve chunk→source metadata through Voyage rerank + Pinecone (carry page_number in vector metadata) |
| Silent eval number with no context | Recruiter can't interpret "0.6 faithfulness" | Report metric + judge model + date + what corpus in README |

## "Looks Done But Isn't" Checklist

- [ ] **Async migration:** Often missing `to_thread` around the sync Voyage client — verify a concurrency load test shows no serialization (Pitfall 3).
- [ ] **Pinecone index:** Often created at wrong dim/metric — verify `describe_index_stats` shows 1024/cosine before bulk upsert (Pitfall 2).
- [ ] **Eval isolation:** Often shares an index with uploads — verify eval queries a benchmark-only namespace and uploads can't write it (Pitfall 1).
- [ ] **Neon pool:** Often missing `pool_pre_ping` — verify first request after 5+ min idle succeeds on the deployed DB (Pitfall 5).
- [ ] **JWT decode:** Often missing pinned `algorithms` — verify decode rejects an `alg:none` token (Pitfall 7).
- [ ] **Secrets:** Often `.env` tracked or key in compose — verify `git log`/gitleaks is clean before first public push (Pitfall 8).
- [ ] **Rate limit:** Often keyed on proxy IP — verify two deployed users get independent limits (Pitfall 10).
- [ ] **SSE:** Often works only on localhost — verify token-by-token streaming against the deployed Render URL, not via a static-site rewrite (Pitfall 11).
- [ ] **Multi-tenant:** Often missing `user_id` filter — verify user A gets 403/404 for user B's conversation (Pitfall 6).
- [ ] **Request limits:** Often left unbounded — verify `max_length` on question + `max_items` on history reject oversized payloads (Pitfall 9).
- [ ] **Citations:** Often dropped in pipeline swap — verify answers still cite page numbers after Voyage/Pinecone migration.
- [ ] **FAISS removal:** Often deps linger — verify torch/sentence-transformers/faiss are gone from the image (the hosting win).

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Eval contamination (shared index) | MEDIUM | Create benchmark namespace; re-embed + re-upsert benchmark there; repoint eval; purge uploads from benchmark scope |
| Wrong Pinecone dimension | MEDIUM | Delete index, recreate at 1024/cosine, re-embed entire corpus (no in-place fix) |
| Committed secret | MEDIUM | **Rotate the key immediately** (deletion insufficient); scrub history (BFG/filter-repo); add gitleaks to CI |
| Async loop blocking found late | MEDIUM | Wrap sync calls in `to_thread`/swap to async SDK; add concurrency test to lock it in |
| Neon stale-connection 500s | LOW | Add `pool_pre_ping=True` + `pool_recycle`; redeploy |
| Rate-limit keyed on wrong IP | LOW | Switch limiter key to authenticated user id; redeploy and verify |
| SSE buffered in prod | LOW–MEDIUM | Point frontend at API URL directly; add `X-Accel-Buffering: no` + `text/event-stream`; re-test on deploy |
| Multi-tenant leak | LOW–MEDIUM | Add `user_id` filter in data layer; add cross-user test; audit all owned-resource endpoints |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Eval/KB contamination | Vector-DB migration (namespaces) + Eval | Eval queries benchmark namespace only; upload doesn't change benchmark vector count |
| 2. Dimension/metric lock-in & re-embed | Vector-DB migration | `describe_index_stats` = 1024/cosine; pre-upsert length assert |
| 3. Async provider re-blocks loop | Sync→async migration (early) | Concurrency load test: no linear latency scaling |
| 4. Sync/async DB mixing & import-time binding | Persistence/Postgres | No `MissingGreenlet`; engine built in lifespan, tests isolated |
| 5. Neon stale connections | Persistence/Postgres + Deploy | First request after idle succeeds on deployed Neon |
| 6. Multi-tenant leakage | Auth/RBAC + Persistence | Cross-user fetch returns 403/404 |
| 7. JWT confusion/refresh | Auth/RBAC | `alg:none` rejected; refresh rotates & revocable |
| 8. Secrets in repo/demo | First commit + CI (Production eng) | gitleaks clean; only `.env.example` tracked |
| 9. Rate limits / cost blowup | Ingestion + Auth+ratelimit + early validation | Voyage backoff; per-user cap enforced; payload limits reject oversized |
| 10. slowapi wrong IP behind proxy | Auth+ratelimit + Deploy | Two deployed users get independent limits |
| 11. SSE buffering/framing/CORS | Streaming + Deploy | Token-by-token stream on deployed URL |
| 12. RAGAS judge noise/contamination/cost | Eval | Pinned judge temp=0; benchmark-only retrieval; scores reported with context |
| 13. Free-tier cold start | Deploy + README polish | First-visit waking state, not an error |

## Sources

- `.planning/codebase/CONCERNS.md` — existing anti-patterns (sync chat endpoint, import-time binding, per-request provider, unbounded question/history, CORS `*`, FAISS pickle, embedding-mismatch-produces-garbage) — HIGH
- `.planning/codebase/ARCHITECTURE.md` — architectural constraints (sync handlers, single corpus, async needed for streaming) — HIGH
- `.planning/PROJECT.md` — eval-integrity constraint (uploads must not affect eval), public-demo cost/abuse constraint — HIGH
- `.planning/research/STACK.md` — chosen stack + free-tier gotchas (Pinecone dim/metric lock, Voyage sync rate-limited, Neon 5-min autosuspend, Render 15-min spin-down, SSE `data:` framing) — HIGH
- PyJWT API docs — `algorithms` required, RFC 8725 §2.1 warning against deriving alg from token, strict-by-default verification — HIGH ([pyjwt.readthedocs.io](https://pyjwt.readthedocs.io/en/stable/api.html))
- Render community + FastAPI SSE docs — static-site rewrite buffering of streams; `X-Accel-Buffering: no`, `text/event-stream`, keep-alive framing — MEDIUM ([Render: SSE buffering](https://community.render.com/t/sse-continually-buffering/3840), [Render: stream buffering in static rewrite](https://community.render.com/t/http-stream-buffering-in-static-site-rewrite/22299), [FastAPI SSE](https://fastapi.tiangolo.com/tutorial/server-sent-events/))
- Pinecone serverless eventual-consistency + namespace model; SQLAlchemy async `pool_pre_ping`; Voyage `input_type` document/query distinction — MEDIUM (corroborated across vendor docs + STACK.md)

---
*Pitfalls research for: production RAG platform migration (free-tier, hosted, authed, multi-doc, evaluated)*
*Researched: 2026-06-10*
