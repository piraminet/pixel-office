# Pixel Office — Migration Ledger

Governed by the Python MVP gauntlet mandate (2026-11-20). Active stack until qualification: JavaScript (`server.js` + Express). Branch: `migration/python-mvp`. Verdicts restricted to **PASS / FAIL / PARTIAL / BLOCKED / DEFERRED / NOT RUN**; component qualification and live deployment qualification are tracked separately.

Evidence convention: every gate cites executed commands + artifacts. Mock success ≠ live success. Implementation complete ≠ deployment authorized.

---

## G0 — Repository reconciliation

**Objective:** pin repo state, document all active/obsolete behavior, reconcile drift, protect user changes, no secrets in reports. Criteria registered before any implementation work beyond the baseline pin.

**Acceptance criteria (registered pre-execution):**
- C0.1 Repository state pinned: branch, HEAD, tags, clean tree recorded.
- C0.2 Every public HTTP route enumerated with auth status and persistence effects (`api-inventory.md` table).
- C0.3 All integration modules classified with live-availability evidence (`integration-inventory.md`).
- C0.4 Security findings enumerated with source evidence + severity, no secret values reproduced (`security-findings.md`).
- C0.5 Obsolete/drifted references reconciled and recorded (OLLAMA_*, GEMINI_API_KEY, sample-data/, removed gammaclaw modules).
- C0.6 Uncommitted user changes preserved (baseline pin commit) and enumerated.
- C0.7 No live secret values appear in any G0 artifact.

**Test/probe names:** `git status/log/tag/remote/ls-files` pin capture; `grep` route enumeration cross-checked against G1 runtime probes; `npm test` baseline (11/11).

**Evidence:**
- 2026-11-20 `git status` clean after pin; pin commit `a345661` on `main` (12 files, +534/−32), branch `migration/python-mvp` created from it.
- Route table: 36 routes + catch-all, static enumeration at server.js lines cited; zero authenticated routes; session-less login confirmed by source read (server.js:267-276).
- Full-file reads: server.js (910 L), vault.js (291 L), email.js head+config (475 L total, config §1-90 + structure), contacts.js (291 L, injection paths), integrations.js (own session work).
- `git tag -l` → empty. `git remote -v` → github.com:bageera/pixel-office.git (mandate URL matches).
- Drift items: 4 recorded (§G0 inventory §3, integration-inventory §Reconciliation).
- npm test baseline: 11 PASS / 0 FAIL (2026-11-20).

**Verdict: PASS.** Files: docs/migration/{G0-repository-inventory,api-inventory,integration-inventory,security-findings}.md + this ledger. Commit: `96f3ed5`. Limitations: email/vault/CRM availability unverified from this host (missing creds/keys) — recorded as blockers, not failures. Remaining: none for G0.

**Security implications:** findings S-01..S-04 are pre-deployment blockers; remediation staged in G2 before any new integration.
**Rollback implications:** baseline pin commit is additive; reverting G0 docs = revert docs commits only.

---

## G1 — Behavioral baseline

**Objective:** reproducible baseline of the active JS app: startup, routes, frontend behavior, auth behavior, restart recovery, sanitized fixtures, compatibility matrix, known-defect register, perf baseline.

**Registered status: criteria registered, work begins on migration branch immediately after G0 commit.**

Acceptance criteria:
- C1.1 Every enumerated route probed live (200/4xx/5xx recorded) with sanitized fixtures committed.
- C1.2 Frontend walk recorded for: office render, character select, log/email/contacts tabs, briefing button, dashboard login flow.
- C1.3 Restart recovery behavior recorded (agents.json reload, in-memory command loss acknowledged).
- C1.4 Baseline performance snapshot (startup time, RSS) recorded.
- C1.5 Unsafe behaviors classified separately (security-findings S-*) and NOT preserved as contract.

**Evidence (2026-11-20, migration/python-mvp):**
- Baseline suite `node tests/api-baseline.js`: **34 assertions, 0 failures** (`npm test` wiring updated: presence suite + baseline run together).
- Fixtures committed: `docs/migration/fixtures/g1-probes.json` (35 probed routes with status + sanitized response shapes), `g1-recovery.json` (config persists; commands do not).
- Browser walk (browser automation, screenshots): office render (6 client chars / 3 rooms / collision 25), tabs (log 12 filters, email 11 chips), dashboard login reject/accept, i18n toggle — details + known defects D-01..D-06 in `G1-baseline.md`.
- Per-startup RSS snapshot: ≈70 MiB idle, boot 314 ms (node v26).
- Real-baseline surprises corrected in the probe (documented, not trimmed): collision 500-on-fresh, 11 email accounts, 200-with-error degradation, Ghostface reinsertion on restart.

**Verdict: PASS.** Commit: (see G1 commit). Limitations: live LLM/email/vault behaviors not part of the deterministic suite; live-path evidence held in session records + integration-inventory. Frontend walk covers office + dashboard + log/email/contacts tabs; briefing button exercised live in earlier session runs only.

Now G2 (criteria above) proceeds on this branch.

---

## G2 — Immediate security remediation

**Objective:** close deployment-blocking criticals/highs in the active JS app before any new integration; disable unsafe capabilities; serve explicit public dir; consistent auth on sensitive routes.

Acceptance criteria:
- C2.1 `GET /.env`, `GET /server.js`, `GET /package.json` return 404 (only allowlisted public assets served).
- C2.2 `GET /api/vault/item/:id` returns 403 (capability disabled); vault search/status gated or disabled.
- C2.3 `POST /api/email/send` returns 403 (disabled until authorized draft flow).
- C2.4 `GET /api/contacts/search?q=<breakout>` returns error/403 without shell execution (capability disabled until parameterized rewrite).
- C2.5 Mutating + sensitive routes require a session cookie; unauthenticated requests → 401; `POST /api/auth/login` issues HTTP-only signed cookie.
- C2.6 Default password `pixeladmin` no longer silently accepted (boot refusal or KIOSK read-only documented).
- C2.7 `POST /api/ai/chat` requires session and ignores client `systemPrompt`.
- C2.8 Office UI (unauthenticated viewer flows) still works; dashboard login now functional end-to-end (regression).
- C2.9 `npm test` + new security regression suite green.

**Objective:** close S-01..S-08 (+S-11 partial) in the active JS app before any new integration; disable unsecurable capabilities; consistent auth on sensitive routes; keep office viewer and dashboard working.

**Implementation (smallest sufficient, zero new deps):**
- `server.js`: static allowlist (index/dashboard + `/assets/**` with `path.resolve` containment + image extension check), strict 404 catch-all (both pages have no client-side routing), HMAC-signed `pixel_session` HttpOnly cookie (12h, timing-safe compare), `requireAuth` middleware (cookie OR `Bearer PIXEL_API_TOKEN`), login rate limit (5 fails/15min/IP), boot guard (`DASHBOARD_PASSWORD` required unless `PIXEL_ALLOW_NO_PASSWORD=1`), `POST /api/ai/chat` gated + client `systemPrompt` ignored (server-owned prompt only), `/api/briefing*` gated, vault CRUD routes gated, `/api/vault/item/:id` → 403, `/api/email/send` → 403, `/api/contacts/search` + `/api/orgs/search` → 403, default password removed.
- `index.html`: 🔒 Owner login chip (prompt → login → cookie), 401-aware chat/briefing errors (bilingual `loginNeeded` key), client `systemPrompt` no longer sent.
- Scripts (`pep_email_checker.sh`, `marian_calendar_checker.sh`, `dustin_doc_tokens.sh`): `AUTH_ARGS=( -H "Authorization: Bearer $PIXEL_API_TOKEN" )` when token set, inserted into their `send_command` curls.
- `.env.example` / README: `PIXEL_API_TOKEN`, `PIXEL_SESSION_SECRET`, boot-guard + disabled-capability documentation. CHANGELOG updated.

**Test commands + results:**
- `npm test` → presence 11 PASS + `tests/api-baseline.js` **44 PASS / 0 FAIL** (includes the security regression section: static 404s incl. `/assets/../server.js` traversal, 401s on all mutating/sensitive routes w/o auth, token path 200s, cookie issuance, disabled-route 403s, rate-limit 429, unknown-path 404, restart recovery).
- In-page/browser evidence: office renders intact post-gating (6 chars, chips); briefing button shows localized "Owner login required"; `ownerLogin()` → "Owner session established"; subsequent briefing fails 500 at the (deliberately offline) LLM — i.e., auth passed, external dependency honestly failed; dashboard login flow + save works with cookie.
- Cookie-vs-no-cookie curl proof: `POST /api/config` 401 unauthenticated / **200 with login cookie jar** / 200 with token.

**Design decisions:** auth-before-existence on unknown agents (401 over 404 for unauth); read-mostly public office surface (config/log/presence/email reads) — documented residual; contacts `:id`/`interactions`/`sync/status` left public (integer-param safe) pending G10 authorization; error-message redaction deferred to G4 (Python standardizes response shapes) — recorded as PARTIAL for S-11.

**Verdict: PASS** (C2.1–C2.9 executed and satisfied; S-11 redaction sweep explicitly deferred with rationale). Commit: `c571249`. Files: server.js, index.html, 3 scripts, .env.example, README.md, CHANGELOG.md, tests/api-baseline.js, fixtures. Limitations: in-memory rate-limit + per-boot session secret (reset on restart) — acceptable for MVP office scale, noted. Security implications: no new crypto (Node stdlib HMAC); secrets never logged. Rollback: revert the G2 commit; scripts + README document behavior change.

---

## G21 — End-to-end MVP acceptance (registered early for scope control)

Statuses recorded as: PASS / FAIL / BLOCKED / SKIP / NOT RUN per workflow MVP-01..15. Current global state: **NOT RUN** (dependencies G7+). Mock-based success will be logged as component qualification only.

---

## Gates G3-G20 — registered next

### G3 — Language-neutral component contracts (criteria registered 2026-11-20, NOT RUN)

Eligibility: independent (no live infrastructure required). Order: before G4 module shapes.

- C3.1 Versioned JSON Schema files exist under `contracts/` for all 16 mandate types (AgentIdentity, RuntimeBinding, AgentStatus, AgentCapability, Task, TaskReceipt, TaskResult, ActivityEvent, ApprovalRequest, ApprovalResult, ProviderDescriptor, DocumentReference, MemoryReference, CredentialReference, AuditEvent, HealthStatus), each carrying `id`, `type`, `version`.
- C3.2 An OpenAPI document exposes the same contracts for HTTP payloads.
- C3.3 A shared fixture set (valid + invalid per contract) validates identically through BOTH a Python validator (pydantic/jsonschema from generated models) and a JS validator (node, no new deps: hand-rolled subset validator or ajv — record the choice).
- C3.4 Invalid fixtures are rejected in both languages; every fixture asserts the 8 identity separations for AgentIdentity (organizational / sprite / native-harness / harness-instance / session / task / scope / authorization-context fields exist and are NOT conflated).
- C3.5 Caller-supplied agent identifiers are never treated as authenticated identity — schema distinguishes `asserted_id` from `verified_binding`.
- C3.6 Schema evolution rules documented ( additive version bumps, unknown/unsupported version → explicit 4xx, never silent).
- C3.7 No raw credential fields anywhere in the 16 contracts (grep audit).

### G4 — Python application foundation (criteria registered 2026-11-20, NOT RUN)

Eligibility: independent of live integrations; depends on nothing else. Structure per mandate §G4, adapted (existing tree stays put; Python additive).

- C4.1 `pyproject.toml` + `uv.lock` pin the stack (fastapi, uvicorn, pydantic, httpx, pytest, ruff, pyright) — reproducible install via `uv sync` on a clean checkout.
- C4.2 `src/pixel_office/` provides: `main.py` (lifecycle: startup, readiness, graceful shutdown), `config.py` (pydantic-settings from env, NO secret defaults), health/readiness endpoints (`/healthz`, `/readyz`) versioned under `/api/v1/*` where applicable, structured logging in JSON to stdout, per-request validation + consistent error envelope, auth middleware mirroring the G2 model (session cookie or bearer token), and a dependency-injection seam for future providers.
- C4.3 `pytest` suite green: config, health endpoints via httpx ASGI transport (no network), auth middleware (reject/accept), graceful shutdown handler.
- C4.4 `ruff check` + `ruff format --check` + `pyright` (basic strictness) all pass with zero errors.
- C4.5 The Node.js application remains fully operational during the phase — `npm test` still 55 asserts (11 presence + 44 baseline) PASS and Docker build still succeeds.
- C4.6 No secrets in source or `.env.example` values; CI-able single command documented (`make python-setup && make python-test`).

### G5-G20 dependencies and known blockers (for scheduling)

- G7 (OpenClaw) live qualification BLOCKED on this host: no OpenClaw install/gateway address; proceed adapter-vs-contract + mock, record BLOCKED for live rows.
- G10/G13 live rows BLOCKED on Vaultwarden API creds / SSH key availability on this host; synthetic-credential component qualification proceeds.
- G11 (Memory Palace), G12 (MinIO) need endpoint reachability verification from this host before adapter work (WireGuard/gamma network) — verify early in those gates.
- G18/G19/G20 execute after G8+G12+G13 (needed load profile + packaging).
- G21 workflows classified per final evidence.

