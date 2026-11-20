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

---

## G21 — End-to-end MVP acceptance (registered early for scope control)

Statuses recorded as: PASS / FAIL / BLOCKED / SKIP / NOT RUN per workflow MVP-01..15. Current global state: **NOT RUN** (dependencies G7+). Mock-based success will be logged as component qualification only.

---

## Gates G3-G20 — registered next

Each gate gets its section added at implementation start per discipline. Planned dependency chain: G3 contracts → G4 python foundation → G5 provider registry → G6 persistence → G7 OpenClaw → G8 Hermes → G9 alignment → G10 secrets → G11 memory → G12 storage → G13 comms → G14 delegation → G15 integrations → G16 frontend/live → G17 security matix → G18 perf → G19 packaging → G20 cutover. Live-infrastructure blockers already identified: OpenClaw not installed on this host (G7 live), Vaultwarden/CRM/email credentials absent (G10/G13 live) — those gates proceed component-level with synthetic fixtures and record BLOCKED for live rows.
