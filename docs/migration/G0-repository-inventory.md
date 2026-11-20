# G0 — Repository Inventory

Reconciled 2026-11-20 on branch `migration/python-mvp` (forked from `main` @ `a345661`, the local baseline commit of verified session work).

## 1. Pinned repository state

| Item | Value |
|---|---|
| Remote | `git@github.com:bageera/pixel-office.git` (mandate URL confirmed) |
| Branch / HEAD at inspection | `main` @ `a345661` ("Python migration baseline") after pinning 12 files of verified prior-session work |
| Pre-baseline HEAD | `9046b38` "MVP office layout: 3 areas (Reception, Workstations, Archives)" |
| Tags | none |
| Working tree after pin | clean |
| Uncommitted user changes | The `a345661` pin itself: presence integration (`integrations.js`, `server.js` route), Makefile/`.dockerignore`, `CHANGELOG.md`, EN/ES i18n in `index.html`, `test_presence.js`, lockfile sync, doc updates. All authored and browser/Docker-verified in this session; none discarded. |

## 2. Entry points and deployment configs

| File | Role | Notes |
|---|---|---|
| `server.js` | Express 5 HTTP app, single process, `0.0.0.0:${PORT:-19000}` | In-memory `config` + JSON files under `PIXEL_DATA_DIR` |
| `Makefile` | `install/test/build/run/stop/logs/clean` Docker lifecycle | Verified 2026-11-20 (colima) |
| `Dockerfile` | node:20-alpine, `npm install --production`, `COPY . .` | `.dockerignore` keeps `.env`/`data`/`node_modules` out (verified) |
| `start.sh` | Local launcher: copy `.env`, `npm install`, `npm start` | |
| `package.json` | name `pixel`, version `1.1.0`, type commonjs | deps: dotenv ^16.4.5, express ^5.2.1, ssh2 ^1.16.0 (73 lock packages) |
| `test_presence.js` | only automated test (`npm test`) | 11 passing asserts, run 2026-11-20 |
| `docs/media/` | Marketing screenshots | Tracked |
| `assets/` | 7 character sprites (`char_0..char_6.png`), office placeholder | `char_1` sprite exists but no roster id 1 |

**Docker run caveat (verified):** inside the container, Hermes reads `/root/.hermes` and OpenClaw probe targets container-local `127.0.0.1:18789`; both report offline without runtime mounts/URL overrides.

## 3. Environment variables

Active in code: `PORT`, `PIXEL_DATA_DIR`, `DASHBOARD_PASSWORD`, `LITELLM_API_URL`, `LITELLM_API_KEY`, `LITELLM_MODEL`, `MAIL2_HOST`, `MAIL2_USER`, `SSH_KEY_PATH`, `GAMMA_HOST`, `GAMMA_USER`, `EMAIL_IMAP_HOST`, `EMAIL_IMAP_PORT`, `EMAIL_USER`, `EMAIL_PASSWORD`, `EMAIL_2_PASSWORD`, `EMAIL_PASS_*` (9 accounts), `CRM_DB_PATH`, `SQLITE3_PATH`, `SYNC_STATE_PATH`, `VW_BASE_URL`, `VW_USER_CLIENT_ID/SECRET`, `VW_ORG_CLIENT_ID/SECRET`, `HERMES_HOME`, `OPENCLAW_GATEWAY_URL`, `OPENCLAW_GATEWAY_TOKEN`.

**Obsolete / drifting (reconcile):**
- `.env.example` advertises `OLLAMA_API_URL` / `OLLAMA_MODEL` — referenced by nothing in code.
- `SKILL.md` §2 claims `.env` controls `GEMINI_API_KEY` — earlier-generation artifact.
- `README.md` documents `sample-data/` priming — the directory does not exist in the tree.
- `DASHBOARD_PASSWORD` falls back to hardcoded `pixeladmin` in code (see security findings).
- `email.js` reads `EMAIL_PASS_*` env keys directly; `.env.example` never lists them (undocumented secret surface).

## 4. Persistence formats

| File (`PIXEL_DATA_DIR`, gitignored) | Format | Writer |
|---|---|---|
| `agents.json` | array of 6 agent objects `{id,name,role,room,color,x,y,state,active}` | server + dashboard save |
| `pixel-config.json` | legacy full config `{agents,rooms}` | `/api/config` POST (also still written) |
| `map.json` | `{rooms[], collision[], updatedAt}` | `/api/rooms`, `/api/collision` |
| `pixel_collision.json`, `pixel_rooms.json` | mirrors of map.json fields | persistMapData |
| `pixel_actions.jsonl` | JSONL `{time,agent,action,msg}`, last-100 kept | bash scripts |
| `agent_<id>_message.txt` | speech bubble text, ids 0..5 | scripts + `/api/messages` reader is read-only |
| `pep_arrived_office`, `pep_arrived_concierge` | signal files | `/api/agent/:id/arrived` |
| (in-memory only) `agentCommands` + `commandTimestamps` | JS map, 30s TTL | `/api/agent/:id/command*` — **lost on restart** |

No SQLite, no DB migrations today. Legacy migration path exists: `agents.json` → else `pixel-config.json` → else defaults, with an "Off Duty"-drop migration step.

## 5. Agent roster and identity structures

Roster (ids deliberately skip 1): Curator(0), Charon(2), Wardog(3), Fixer(4), Tailor(5), Ghostface(6, Owner). `id` doubles as sprite index (`char_<id>.png`) and log color key — visual identity, runtime identity and DB key are the same integer today. No harness identity exists anywhere (server-side "Charon" is an LLM prompt persona, see api-inventory).

## 6. Behavior classification (active / obsolete / incomplete / visual)

| Component | State |
|---|---|
| Office viewer, config/rooms/collision APIs, dashboard editor | **Active** |
| Presence API + chips (Hermes/OpenClaw) | **Active** (Hermes live-verified; OpenClaw live-verified offline / mock-verified online) |
| Email inbox/read/send, unread counts | **Active** (10 account configs; IMAP/SSH via mail2 — availability unverified from this host) |
| Contacts/CRM (local sqlite copy of OpenClaw workspace DB) | **Active on gamma-hosted deploy only**; expects `/home/node/.openclaw/...` paths |
| Vaultwarden APIs | **Active code, live-unverified**; exposes raw ciphers (critical finding) |
| `/api/briefing`, `/api/briefing/ai`, `/api/ai/chat` | **Active**; `/api/briefing/ai` embeds a large confidential infrastructure dossier into prompts (finding S-09) |
| Bash automation scripts (pep/marian/dustin/checkers) | **Active** (depend on sibling server + `PIXEL_DATA_DIR`) |
| Historical gammaclaw modules (Nextcloud/Paperless/CRM-bridge "coordination API", per commit `14fb96e`) | **Removed in later public commits** — superseded, do not resurrect; referenced by nothing in current tree |
| `OLLAMA_*` env vars, `GEMINI_API_KEY` in SKILL.md, `sample-data/` docs | **Obsolete doc/config drift** |
| Sprite idle/walk animation, speech bubbles, manual override UI | **Visual** (client-side only) |

## 7. Missing modules / unresolved imports

None — every `require()` in runtime code resolves to a tracked file or listed dependency (`node -c` style require-check executed via `npm start` boots multiple times this session).

## 8. Frontend ↔ backend coupling

`index.html` (2296 lines): polls `/api/config`, `/api/rooms`, `/api/collision`, `/api/messages`, `/api/log`, `/api/agent/:id/command`, `/api/presence`, `/api/briefing/ai`, `/api/ai/chat`, `/api/email/*`, `/api/contacts/*`, `/api/sync/status`; posts moves/commands. `dashboard.html` (919 lines): `/api/auth/login`, `/api/config`, `/api/rooms`, `/api/collision`. Both are served by the same origin, no build step, CDN Tailwind.

## 9. Existing test coverage

Single suite: `test_presence.js` (11 asserts; adapters + endpoint cache + roster). No route tests, no frontend tests, no security tests.
