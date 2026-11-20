# Integration Inventory

Verified 2026-11-20. "Live status" = what this session could actually verify from the office host; unavailable ≠ removed.

## In-repo integration modules

| Module | Exposed capability | External service(s) | Mechanism | Live status |
|---|---|---|---|---|
| `integrations.js` | runtime presence roster | Hermes Agent, OpenClaw | file reads (`$HERMES_HOME/runtime/active_sessions.json`, `gateway_state.json`) + HTTP probe `/v1/models` (Bearer) | **Hermes: live** (gateway pid, mattermost platform, sessions). **OpenClaw: offline locally**, online path mock-verified; no OpenClaw install found on this host (`which openclaw`, `~/.openclaw` absent, no processes) |
| `email.js` (475 L) | per-account IMAP unread/list/read, SMTP send | mail2 (`MAIL2_HOST`, default `159.65.183.161`, user `root`) via SSH → localhost IMAP/SMTP; 10 account configs with per-account env passwords | ssh2 exec, IMAP over loopback | **Unverified from this host** (SSH key absent → honest blocker) |
| `vault.js` (291 L) | vault sync/search/folders/collections/**full item retrieval** | Vaultwarden `VW_BASE_URL` (default `bw.theblacktech.com`), Bitwarden API-key OAuth `client_credentials` (user + org grants, token cache) | https requests | **Unverified** (client creds unset in `.env.example`); `getStatus()` reachable |
| `contacts.js` (291 L) | CRM search/detail/interactions/organizations/sync-status | local file sqlite3 CLI on **OpenClaw workspace DB** (`/home/node/.openclaw/workspace/crm/crm.db`, sqlite3 binary from `/home/node/.openclaw/bin`) — this module presumes the office runs **inside the OpenClaw host node env** | `child_process.execSync` (SQL→shell) + tmp copy | **Host-bound**: works only where OpenClaw's workspace lives; SQL+shell injection confirmed in source |
| Bash scripts (`pep_email_checker.sh`, `pep_supervisor.sh`, `marian_calendar_checker.sh`, `marian_supervisor.sh`, `dustin_doc_tokens.sh`, `add_calendar_event.sh`, `test_email_alert.sh`) | move agents, bubbles, log entries on email/calendar signals | the pixel server's own REST API; calendar via local file `data/calendar_events.json`-style injection (`add_calendar_event.sh` writes to `PIXEL_DATA_DIR`) | curl + fs | Active; `dustin_doc_tokens.sh` counts files in a workspace dir |

## External services referenced (mandate §3 table vs evidence)

| Service | In repo? | Where referenced | Live verified this session |
|---|---|---|---|
| OpenClaw (primary harness) | referenced (README, presence adapter, CRM paths imply office ran as OpenClaw tool) | `integrations.js`, `contacts.js` paths | **Not installed locally** |
| Hermes (independent harness) | session-14 presence adapter | `integrations.js` | **Live** (v0.23.3 gateway, mattermost) |
| Charon (OpenClaw-powered Chief Concierge) | **No adapter** — server-side "Charon" is an LLM prompt persona in `/api/briefing/ai` (`systemPrompt` at server.js:465) | — | BLOCKED pending real OpenClaw identity |
| Mattermost | mentioned in `gateway_state.json` platforms (Hermes-side), not integrated by pixel-office | — | via Hermes gateway state only |
| Vaultwarden | `vault.js` live code | `bw.theblacktech.com` | Unverified (no creds on host) |
| Memory Palace / ChromaDB | **not integrated** (mention only inside briefing prompt text) | — | Not reachable from repo |
| MinIO / S3 | **not integrated** (briefing text mentions `rustfs/S3`) | — | — |
| Odoo / Home Assistant / Rundeck / Grafana / FreshRSS / GitHub / K8s / WireGuard | **not integrated**; only prompt-text mentions | server.js briefing dossier | — |
| LiteLLM (inference) | `server.js` `LITELLM_API_URL` default `litellm.blacktech.dev`, model `glm-5.3-flash` | `/api/ai/chat`, `/api/ai/status`, briefings | **Live** (status/`/v1/models` reachable during earlier session runs) |
| GitLab (`gl.theblacktech.com`), Nextcloud, Immich, OpenProject, Mailcow, Graylog | prompt-text mentions only | server.js:508-540 dossier | Not integrated |

## Reconciliation notes (mandate §3: "reconcile against actual deployed environment")

1. `contacts.js` hard-codes **OpenClaw workspace paths** — the CRM integration is an OpenClaw-host artifact, incompatible with standalone/container deploys (confirmed by Docker run this session: CRM endpoints fail).
2. `email.js`/`vault.js` assume SSH key at `/app/ssh/id_ed25519` (Dockerfile does not provide it) — credential delivery is undocumented; treat as deployment gap, do not "fix" by embedding.
3. Historical gammaclaw modules (Nextcloud `WebDAV/OCS/CalDAV`, Paperless, CRM SSH bridge — commit `14fb96e`) were **removed** in later public commits; only their briefing-prompt traces remain. Not active code.
4. `README` claims `sample-data/` priming — directory absent. `SKILL.md` claims `GEMINI_API_KEY` — obsolete. `.env.example` `OLLAMA_*` — obsolete.
5. OpenClaw gateway facts (from earlier verified session work): port `18789`, loopback, token auth, HTTP OpenAI-compat surface `/v1/models`; session detail needs the WS RPC (`connect` → `hello-ok` snapshot) — **do not invent endpoints**; adapter ships HTTP online/offline until a real gateway is targetable.

## Honest availability summary for G7+ planning

- OpenClaw **live target: BLOCKED** on this host (no install, no address). Adapter work proceeds against documented interfaces + mock, marked component-qualified only.
- Vaultwarden/CRM/email live qualification **BLOCKED** on missing credentials/keys on this host — synthetic-credential testing only.
- Hermes **available now** for G8: gateway process, leases file, surfaces (`cli`, `gateway:*`), profiles under `~/.hermes/profiles/`.
