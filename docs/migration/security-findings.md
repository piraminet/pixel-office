# Security Findings — JavaScript baseline

Static + dynamic review 2026-11-20, pre-G2. Severity: CRITICAL > HIGH > MEDIUM > LOW. Every finding cites source evidence; reproduction commands in G1/G2 fixtures.

| ID | Sev | Finding | Evidence | G2 disposition |
|---|---|---|---|---|
| S-01 | CRITICAL | **Repo root served statically** — `.env` (production secrets), `server.js`, `package.json`, docs all downloadable. | server.js:107 `express.static(path.join(__dirname))` | Replace with explicit public-dir allowlist |
| S-02 | CRITICAL | **Raw Vaultwarden cipher retrieval**: `GET /api/vault/item/:id` returns `password`, `notes`, custom `fields` verbatim to any caller. | vault.js:224-244 (`getItem`), server.js:873 | Disable route pending G10 executor; search/status without secrets may stay, gated |
| S-03 | CRITICAL | **Unauthenticated external email send**: `POST /api/email/send` delivers SMTP mail to arbitrary recipients. | server.js:832 | Disable until authz + draft-first flow (G13) |
| S-04 | CRITICAL | **Command/SQL injection via CRM search**: user `q` string-interpolated into SQL, then the whole SQL is shell-interpolated into `execSync(...)` (`"`, `` ` ``, `$()` break the quoting). | contacts.js:72-79 + contacts.js:38 | Disable `/api/contacts/search` + `/api/orgs/search` (any sqlite3 exec path) until parameterized rewrite (G6/G8) |
| S-05 | HIGH | **Unauthenticated state mutation** across `/api/config`, `/api/agent/*`, `/api/rooms`, `/api/collision`, `/api/log/clear`, `/api/messages`-adjacent writers. | api-inventory table | Session-gate all mutating + sensitive routes |
| S-06 | HIGH | **Login theater**: `POST /api/auth/login` returns `{success:true}`; no cookie, no token, no middleware — the dashboard's "auth" is client-side only. | server.js:267-276 | Signed HTTP-only session cookie; `requireSession` middleware |
| S-07 | HIGH | **Hardcoded default password** `pixeladmin` when `DASHBOARD_PASSWORD` unset. | server.js:27 | Refuse boot in production with unset password unless `KIOSK=true` + read-only |
| S-08 | HIGH | **Open inference proxy**: `POST /api/ai/chat` accepts arbitrary `systemPrompt` from unauthenticated callers, forwards to LiteLLM (key held server-side) — resource abuse + data-exfil channel. | server.js:183-240 | Gate behind session; drop client `systemPrompt`; whitelist office-context prompts |
| S-09 | MEDIUM | **Confidential infrastructure dossier in public-repo source**: internal IPs, hostnames, mailbox list, org/subsidiary structure, vault counts embedded in briefing prompts (server.js:465-550). | server.js:465-550 | Move dossier to gitignored runtime config; **history rewrite = owner decision (escalate)** — commits to new work must not add such content |
| S-10 | MEDIUM | **Full email content returned as HTML** to client (`/api/email/:id`) — remote content rendered untrusted; XSS + prompt-injection intake. | server.js:820 | Sanitize/render as text-in-viewport; treat bodies as data (G13) |
| S-11 | MEDIUM | Error/message leakage: `500 {error: e.message}` across routes can disclose paths/creds-adjacent detail; `console.log` of command bodies. | multiple (api-inventory §Errors) | Central error formatter; redact |
| S-12 | LOW | `0.0.0.0` bind by default; catch-all `sendFile(index.html)` masks unknown `/api/*` as 200; no rate limiting; log endpoint unauthenticated (may carry sensitive chatter). | server.js:906, 902 | Documented in hardening; bind host config added G2 |
| S-13 | LOW | `.gitignore` entry `PIXEL_DATA_DIR/` (literal dir name) never matches the runtime-relative `data/` — `data/` entry does the work; harmless but misleading. | .gitignore | Fix entry |
| S-14 | INFO | Secrets reach logs via shell-script JSONL (`pixel_actions.jsonl`) — no evidence of actual secret writes found; monitored in G6/G10 audits. | scripts | Audit assertions |

**Explicitly in-scope G2 remediations (deployment blockers):** S-01..S-08, S-11. Capabilities that cannot yet be implemented securely are **disabled** (per mandate §G2), with routes returning 404/403 and documented, not silently removed — behavior preserved for G13/G10 qualification later.

**Escalation required from owner:** S-09 history scrub on the public repo (destructive operation) — recorded, not acted on.
