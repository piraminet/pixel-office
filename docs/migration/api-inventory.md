# API Inventory — JavaScript baseline (pre-migration)

All routes from `server.js` (verified by static enumeration + runtime probes; probe results in G1 fixtures).
**Auth column reflects reality: no route is authenticated. `POST /api/auth/login` returns a JSON boolean and establishes no session/cookie/token.**

| # | Method | Path | Lines | Purpose | Auth | Persistence / side effects | Consumers |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/config` | 175 | roster + rooms | none | none | office, scripts, docs |
| 2 | POST | `/api/config` | 278 | full overwrite of roster+rooms | none | rewrites `pixel-config.json`, `agents.json`, `map.json` | dashboard save |
| 3 | POST | `/api/agent/:id/move` | 293 | set x/y/state | none | mutates in-memory roster (not persisted) | scripts, docs |
| 4 | GET | `/api/agent/:id/command` | 596 | pop one pending command, 30s TTL | none | consumes in-memory map | office loop |
| 5 | POST | `/api/agent/:id/command` | 639 | push command | none | in-memory map | scripts, docs |
| 6 | POST | `/api/agent/:id/command/ack` | 632 | clear command | none | in-memory | scripts |
| 7 | POST | `/api/agent/:id/arrived` | 618 | arrival signal | none | writes `pep_arrived_*` signal files | scripts |
| 8 | GET | `/api/messages` | 646 | speech bubbles ids 0..5 | none | none | office |
| 9 | GET | `/api/log` | 309 | last 50 JSONL actions | none | none | office log tab |
| 10 | POST | `/api/log/clear` | 323 | truncate actions log | none | truncates `pixel_actions.jsonl` | UI |
| 11 | GET | `/api/collision` | 693 | collision map | none | none | office |
| 12 | POST | `/api/collision` | 670 | save collision | none | `map.json` | dashboard |
| 13 | GET | `/api/rooms` | 706 | rooms + tiles | none | none | office |
| 14 | POST | `/api/rooms` | 681 | save rooms | none | `map.json`, in-memory rooms | dashboard |
| 15 | GET | `/api/briefing` | 333 | aggregate email/vault/contacts/AI/agents | none | none | none in UI (curl/docs) |
| 16 | GET | `/api/briefing/ai` | 406 | LLM "Charon" briefing | none | prompt embeds infrastructure dossier | office briefing button |
| 17 | POST | `/api/ai/chat` | 183 | LLM proxy, client-supplied systemPrompt allowed | none | none | AI Director chat |
| 18 | GET | `/api/ai/status` | 243 | LiteLLM model list | none | none | UI status |
| 19 | GET | `/api/presence` | 661 | Hermes/OpenClaw runtime presence | none | none (read-only adapters) | office chips |
| 20 | POST | `/api/auth/login` | 267 | password check → `{success:true}` only | none | **no session, no cookie, no state** | dashboard |
| 21 | GET | `/api/email/accounts` | 778 | account metadata (`configured` flag, no passwords) | none | none | email tab |
| 22 | GET | `/api/email/unread/all` | 786 | batch unread counts (IMAP) | none | none | poll 60s |
| 23 | GET | `/api/email/unread` | 796 | single unread count | none | none | poll |
| 24 | GET | `/api/email/inbox` | 807 | message list per account/folder | none | none | email tab |
| 25 | GET | `/api/email/:id` | 820 | full message (HTML body) | none | none | email detail; **HTML rendered → XSS surface** |
| 26 | POST | `/api/email/send` | 832 | **external email delivery** | none | sends via mail2 SMTP | none in UI (script/docs capability) |
| 27 | GET | `/api/contacts/search` | 721 | CRM search, `q` → SQL → shell | none | sqlite tmp copy read | contacts tab — **injection** |
| 28 | GET | `/api/contacts/:id` | 733 | contact detail | none | local CRM DB | contacts tab |
| 29 | GET | `/api/contacts/:id/interactions` | 744 | interaction history | none | local CRM DB | contacts tab |
| 30 | GET | `/api/orgs/search` | 754 | org search | none | local CRM DB | contacts tab |
| 31 | GET | `/api/sync/status` | 766 | CRM sync state | none | none | contacts tab |
| 32 | GET | `/api/vault/status` | 848 | Vaultwarden config state | none | none | briefing |
| 33 | GET | `/api/vault/search` | 858 | vault item search (metadata) | none | 60s sync cache | none in UI |
| 34 | GET | `/api/vault/item/:id` | 873 | **full cipher incl. password**, notes, fields | none | none | none in UI — **secret disclosure** |
| 35 | GET | `/api/vault/folders` | 883 | folder list | none | none | none in UI |
| 36 | GET | `/api/vault/collections` | 893 | collection list | none | none | none in UI |
| — | GET | anything else | 902 | catch-all → `index.html` (even unknown `/api/*` returns 200 HTML) | none | none | SPA fallback |

## Error behavior (observed)

- Handler exceptions → `500 {error: e.message}` (leaks internals); some failures return `200` with empty data (`/api/log` → `[]`, presence degrades per runtime).
- `/api/config` POST with missing `agents` silently resets to the 6-agent default.
- No rate limiting, no CORS config (Express default: same-origin), JSON body size default 100kb.

## Polling / live-activity surfaces (no WebSocket or SSE exists)

| Client mechanism | Interval | Endpoint |
|---|---|---|
| `index.html` presence chips | 15 s | `/api/presence` |
| `index.html` unread badge | 60 s | `/api/email/unread/all` (+per-account) |
| `index.html` chat poll / log refresh intervals (2s/5s class) | ~2–5 s | `/api/agent/:id/command`, `/api/log`, `/api/messages` |
| Initial loads | once | `/api/config`, `/api/rooms`, `/api/collision` |
