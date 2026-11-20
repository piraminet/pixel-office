# G1 — Behavioral Baseline (JavaScript)

Executed 2026-11-20 on `migration/python-mvp`. Every observed value comes from `node tests/api-baseline.js` (34 assertions, 0 failures) + a scripted browser walk (`browser_exec` session, screenshots per step). External services forced to synthetic offline config inside the baseline harness so results are deterministic; live-service behavior recorded separately below.

## 1. Reproduction commands

```bash
npm test                     # presence suite (11) + G1 baseline suite (34 asserts, boots its own server on :19031)
node tests/api-baseline.js   # baseline alone; fixtures → docs/migration/fixtures/g1-*.json
```

## 2. Route matrix results (live)

Full per-route status + response shape: `docs/migration/fixtures/g1-probes.json`.
Highlights (observed, not assumed):

- Boot → listening in **314 ms** (node v26); RSS idle ≈ **70 MiB** (71,600 KB), VSZ ≈ 424 MiB.
- Fresh install: `GET /api/collision` → **500 "Map not available"** (UI silently falls back to built-in default — quirk D-04).
- `GET /api/email/accounts` → **11** account configs, no `password` fields (metadata-only path verified).
- Offline degradation quirks: email inbox errors and vault item errors return **200 with an `error` field** instead of 4xx/5xx (D-05).
- Command channel round-trip (push → consume → consumed-null) verified with 30s TTL semantics.
- `POST /api/config` persists to `agents.json` + `map.json` and survives restart; **in-memory commands do not survive restart** (documented loss, not corruption).
- Restart quirk (D-06): server.js:134-137 re-inserts **Ghostface into any custom roster on every boot** — `POST /api/config` with a 1-agent roster yields `Curator, Ghostface` after restart.
- Unauthenticated `POST /api/config` accepted (finding S-05 — recorded, not "preserved").
- `GET /server.js`, `GET /.env`, `GET /package.json` all **200 (source/secret download)** — S-01 reproduced live.
- Unknown `/api/*` → 200 with `index.html` HTML (catch-all masks API errors).

## 3. Live-service behavior (separate from synthetic baseline)

- LLM (`/api/briefing/ai`, `/api/ai/chat`): verified live in earlier session runs on this host (LiteLLM `litellm.blacktech.dev`, model `glm-5.3-flash` responded with content); NOT re-probed in the committed baseline (deterministic offline config) — live reproducibility documented in the session record, not asserted by CI.
- Presence: Hermes live (gateway pid + mattermost platform observed); OpenClaw offline (no install) with online path mock-verified earlier.
- Dashboard login against real `.env` password: **rejects** synthetic wrong password ("Password incorrect") and accepts the matching real one (editor unlocks) — verified via browser without echoing the real value.

## 4. Frontend compatibility matrix (browser walk)

| Behavior | Observed | Evidence |
|---|---|---|
| Office renders | 6 client characters, 3 rooms (Reception/Workstations/Archives), collision map loaded (25px grid) | browser walk 1 + screenshot |
| Character selection UI | renders; see D-01 | walk 1 |
| Presence chips | "Hermes · 1 session · channels: mattermost / OpenClaw · offline" | walk 1 |
| Log tab | filter bar renders (12 buttons), entries view OK on empty log | walk 2 |
| Email tab | 11 account chips render from `/api/email/accounts` | walk 2 |
| Contacts tab | **sync status stuck on "Loading sync status..." when the CRM source is absent** (no failure UI) → D-02 | walk 2 |
| Canvas | 640×800 | walk 2 |
| Dashboard login | wrong password rejected inline; correct password unlocks editor (ES localized) | walk 3 + screenshot |
| Dashboard save | persists config (covered by API probes: `POST /api/config` → disk reload) | fixture |
| EN/ES toggle + i18n sweep | verified 2026-11-20 (previous session work, still passing) | browser re-run |

## 5. Known-defect register (baseline defects — migration MUST NOT inherit silently)

| ID | Severity (as baseline behavior) | Description | Evidence | Migration disposition |
|---|---|---|---|---|
| D-01 | High (UX/contract) | Ghostface (roster id 6, Owner) **never renders** — render loop scans ids 0..5 only; id-slot 1 renders fallback "Character 2" because no roster id 1 exists. Roster↔sprite↔key identity conflation. | server.js render loop `for(let i=0;i<6;i++)` + browser walk char_names | G9: separate visual id / roster id / runtime id; render from roster length |
| D-02 | Medium (UX) | Contacts sync status never leaves "Loading..." on missing CRM source | browser walk 2 | G16: explicit degraded/offline state |
| D-03 | High (security UX) | Dashboard "login" gates only the DOM; no server session (findings S-05/S-06) | api probe: `POST /api/config` unauth → 200 | G2: session middleware |
| D-04 | Low | `/api/collision` on fresh install is 500 rather than 200-empty; frontend paper-over | probe | G6: null-safe default |
| D-05 | Medium | Integration errors swallowed as 200 `{error}` on email inbox / vault item / vault search | probes | G4: consistent error semantics (documented as behavior change) |
| D-06 | Medium | Ghostface unconditionally re-added to custom rosters on restart | probe + restart recovery assert | G9: owner-owned character binding without roster mutation |

Unsafe behaviors classified for remediation, not preservation: S-01..S-08 (see security-findings.md).

## 6. Baseline performance and resource snapshot

| Metric | Value | Condition |
|---|---|---|
| Cold start → listening | 314 ms | node v26.0.0, local SSD, fresh /tmp data dir |
| Idle RSS | ≈ 70.0 MiB | after 2s idle, no requests |
| Idle VSZ | ≈ 424.5 MiB | same |
| Per-request latency | unmeasured individually (localhost trivial) | G18 will compare Node vs Python under equivalent load |

Verdict: **PASS** for C1.1-C1.5 (criteria in ledger). Commit ids recorded with the G1 commit.
