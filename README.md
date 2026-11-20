# Pixel Startup

**Pixel Startup** is the persistent, multi-harness organizational operations platform behind the pixel office. **Pixel Office** remains the name of the visual office component you see here — the retro pixel-art environment with its characters (Curator, Charon, Wardog, Fixer, Tailor, Ghostface), rooms and speech bubbles.

> Formerly released as "Pixel Office" (npm package `pixel`); the platform identity moved to Pixel Startup with the Python backend migration (`docs/migration/`). Git history, upstream attribution and licenses are unchanged — see [CREDITS.md](CREDITS.md).

Retro control room for OpenClaw agents: live pixel-art office, secure dashboard to edit rooms/collision maps, and automation hooks for scripts and AI directors.

> 🇪🇸 ¿Buscas la versión en español? Está al final de este documento, pero la referencia principal es ahora la versión en inglés.

## 🎬 Demo

- Video walkthrough: https://youtu.be/GGyWQJAv9_8
- Screenshots
  - **AI Director session**
    
    ![AI Director in action](docs/media/pixel-office-session.jpg)
  - **Agent & room editor**
    
    ![Agent editor](docs/media/pixel-dashboard-characters.jpg)
  - **Collision & IA layout editor**
    
    ![Collision editor](docs/media/pixel-dashboard-collisions.jpg)

## ✨ Highlights

- **Live pixel office** with retro sprites, speech bubbles and manual overrides.
- **Password-protected dashboard** (`dashboard.html`) to edit agents, rooms and collision maps without touching code.
- **JSON persistence** (`agents.json`, `map.json`) plus backward compatibility with legacy `pixel-config.json`.
- **REST API** to move agents, post commands, fetch logs and update layouts.
- **Automation scripts** that react to email/calendar signals or any Unix file trigger.
- **AI Director mode** (see screenshot) to orchestrate scenes with natural language prompts.

## 🧱 Folder map

```
services/pixel
├── index.html            # Live office
├── dashboard.html        # Secure dashboard
├── server.js             # Express API + static files
├── assets/               # Backgrounds + sprite sheets
├── sample-data/          # Versioned demo config
├── data/                 # Runtime data (gitignored)
├── docs/media/           # Screens & marketing art
└── *.sh                  # Automation scripts
```

## 🚀 Quick start

1. **Install dependencies**
   ```bash
   cd services/pixel
   cp -n .env.example .env   # tweak PORT, PIXEL_DATA_DIR, DASHBOARD_PASSWORD, agent-runtime vars
   npm install               # or: make install
   ```

2. **Prime the runtime data** with the public samples:
   ```bash
   mkdir -p data
   cp sample-data/agents.sample.json data/agents.json
   cp sample-data/map.sample.json data/map.json
   ```

   > Optional: if you own Donarg's Office Interior Tileset, drop the exported PNG as `assets/oficina.png` (gitignored). Pixel Office will automatically swap the placeholder background for your art.

3. **Run the server**
   ```bash
   npm start
   ```
   - Office: `http://localhost:19000/`
   - Dashboard: `http://localhost:19000/dashboard.html`

> `services/pixel/data/` is ignored by git, so you can keep private states/logs locally. Only the `.sample.json` files are tracked for reproducible demos.

## 🔐 Dashboard & auth

- Login via `POST /api/auth/login`; password comes from `.env` (`DASHBOARD_PASSWORD`). **Boot refuses to start without it** unless `PIXEL_ALLOW_NO_PASSWORD=1` (explicit kiosk mode).
- Successful login issues an **HttpOnly signed session cookie** (`pixel_session`, 12h, HMAC-SHA256 with `PIXEL_SESSION_SECRET` — random per boot if unset). Mutating and sensitive routes require the session; automation (bash scripts) authenticates with `Authorization: Bearer $PIXEL_API_TOKEN`.
- **Disabled pending secure reimplementation** (see `docs/migration/security-findings.md`): raw vault item retrieval (`/api/vault/item/:id`), external email send (`/api/email/send`), contacts/org search (SQL→shell injection class).
- The office viewer stays read-mostly (config/log/presence/email reads are public); AI Director chat + briefings require an owner session — use the 🔒 **Owner login** in the office overlay.
- Each save from the dashboard rewrites `data/agents.json` + `data/map.json`.

## 🕹️ REST API cheat sheet

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET /api/config` | Returns current agents + rooms. |
| `POST /api/config` | Overwrites agents + rooms (also persists). |
| `POST /api/agent/:id/move` | Updates `x`, `y`, `state` for an agent. |
| `GET /api/agent/:id/command` | Retrieves (and consumes) the latest pending command. |
| `POST /api/agent/:id/command` | Pushes a command for that agent. |
| `POST /api/agent/:id/arrived` | Signals arrival (`pep_arrived_*` files). |
| `POST /api/agent/:id/command/ack` | Clears a pending command without executing it. |
| `GET /api/messages` | Returns speech bubbles (`agent_{id}_message.txt`). |
| `GET /api/log` / `POST /api/log/clear` | Reads or wipes `pixel_actions.jsonl`. |
| `GET/POST /api/collision` | Reads or saves the collision map. |
| `GET/POST /api/rooms` | Reads or saves room definitions. |

## 🧩 First-class agent runtimes (Hermes + OpenClaw)

The office is not just a mockup — it shows the **live presence of real agent runtimes** and both runtimes can drive it through the REST API.

### Live presence (`GET /api/presence`)

`integrations.js` reads real runtime state, no dependencies:

- **Hermes Agent**: session leases from `$HERMES_HOME/runtime/active_sessions.json` (pid-liveness-checked) + gateway/platform state from `$HERMES_HOME/gateway_state.json`.
- **OpenClaw**: probes the gateway's OpenAI surface (`/v1/models` at `OPENCLAW_GATEWAY_URL`, default `http://127.0.0.1:18789`, optional `OPENCLAW_GATEWAY_TOKEN`).

```json
{ "hermes": { "online": true, "gateway": {"state": "running"}, "platforms": ["mattermost"], "sessions": [...] },
  "openclaw": { "online": false, "url": "http://127.0.0.1:18789" },
  "agents": [ { "key": "hermes:gateway", "name": "Hermes Gateway", "runtime": "hermes", "detail": "..." } ] }
```

The live office (`index.html`) polls this every 15s and renders status chips (green/gray) top-left: sessions per runtime, connected channels, model counts.

### Driving the office from an agent (Hermes tools or OpenClaw skills)

Both runtimes act on the same API — no special code needed:

```bash
# Walk Charon (concierge desk agent) to the Workstations room and say something
curl -X POST http://127.0.0.1:19000/api/agent/2/move -H 'Content-Type: application/json' -d '{"x":320,"y":440,"state":"walking"}'
curl -X POST http://127.0.0.1:19000/api/agent/2/command -H 'Content-Type: application/json' -d '{"type":"move","x":320,"y":440}'
echo "Triage complete: 3 urgent emails routed." > "$PIXEL_DATA_DIR/agent_2_message.txt"
```

Full endpoint list: [REST API cheat sheet](#-rest-api-cheat-sheet). Speech-bubble/log files live under `data/` (see `add_calendar_event.sh` for a worked example).

## 🤖 Built-in automations

| Script | Purpose |
|--------|---------|
| `pep_email_checker.sh` | Watches `/tmp/email_alert_pending` and moves Pep with a speech bubble. |
| `marian_calendar_checker.sh` | Syncs Marian with agenda/OOO status. |
| `dustin_doc_tokens.sh` | Toggles CEO activity depending on workload. |
| `add_calendar_event.sh` | Helper to inject sample calendar events. |

All scripts read `.env`, respect `PIXEL_DATA_DIR` and append to `pixel_actions.jsonl` so the dashboard log stays in sync.

## 📂 Data & assets

- `sample-data/*.sample.json` → version-controlled demo config.
- `data/` → live state (logs, commands, rooms, speech bubbles); auto-created on first run.
- `assets/`:
  - `characters/` → MetroCity Free Topdown Character Pack by [JIK-a-4](https://jik-a-4.itch.io/metrocity-free-topdown-character-pack) (credit/details below).
  - `oficina-placeholder.png` → built-in pixel-art office (drawn from the default collision map; regenerable via `tools/generate-assets.py`). If you purchase Donarg's Office Interior Tileset drop your PNG as `assets/oficina.png` (gitignored) and the app will pick it up automatically.
- `docs/media/` → screenshots used here; keep 1920px width when updating marketing shots.

## 🎨 Credits & external assets

- Inspired by [pixel-agents](https://github.com/pablodelucca/pixel-agents) by Pablo Delucca — this project reuses the idea of a pixelated OpenClaw office and adapts it to this stack.
- Character sprites come from the [MetroCity Free Topdown Character Pack](https://jik-a-4.itch.io/metrocity-free-topdown-character-pack) by JIK-a-4. Review the itch.io license before redistributing; attribution is required.
- The office background was built with [Office Interior Tileset (16x16)](https://donarg.itch.io/officetileset) by Donarg (USD $2). This is the only part of Pixel Office that is not freely available; the tileset is **not** included here because of its license. To use it locally, purchase the pack, export your layout as `services/pixel/assets/oficina.png`, and Pixel Office will automatically pick it up (the file is gitignored).

See [CREDITS.md](CREDITS.md) for a handy table you can keep updated.

## 📦 Deploy notes

- Makefile shortcuts: `make build` (Docker image), `make run` (container with `data/` mounted and `.env` injected), `make test`, `make logs`, `make clean`. The image never bakes `.env`, `data/` or `node_modules` (see `.dockerignore`). Runtime presence reflects the host from inside the container: mount the runtimes you want visible, e.g. add `-v $(HOME)/.hermes:/root/.hermes:ro` to `make run`, and point `OPENCLAW_GATEWAY_URL` at a reachable gateway.
- Build hosts: `make push-image` publishes the image to `ghcr.io/bageera/pixel-startup:latest`, then pull with `docker pull ghcr.io/bageera/pixel-startup:latest` (the GHCR package is private — the pulling host needs `docker login ghcr.io` first).
- Local demo: `npm start`.
- Releases: version lives in `package.json` (SemVer, mirrored in [CHANGELOG.md](CHANGELOG.md)); bump with `npm version patch|minor|major`, then `make tag` creates and pushes annotated `vX.Y.Z` from that version.
- Remote share: e.g. `cloudflared tunnel --url http://127.0.0.1:19000` (or any reverse proxy you prefer).
- `.gitignore` already skips `.env`, `node_modules`, `data/`, backups and temp logs.
- Notable changes go to [CHANGELOG.md](CHANGELOG.md).

## 🌐 Languages (EN/ES)

The office UI is bilingual. A 🌐 toggle in the top-left overlay switches English ⇄ Español; the choice is remembered in `localStorage` and defaults to the browser language. Translations live in the `I18N` dictionary at the top of `index.html` — static markup uses `data-i18n`/`data-i18n-ph`/`data-i18n-title` attributes, JS strings use `t('key')`. The `dashboard.html` admin panel is currently English-only.

## ✅ Pre-share checklist

- [ ] Fresh `.env` with a password for the recipient.
- [ ] `data/` populated (from `sample-data/` or your latest backup).
- [ ] Dashboard login + save flow tested.
- [ ] Bash scripts pointing to the right `PIXEL_DATA_DIR`.
- [ ] Screenshots + video link still representative.

---

## 🇪🇸 Resumen en español

Pixel Office es el entorno visual de **Pixel Startup**, la plataforma de operaciones organizacionales multi-harness. Este tablero retro sigue siendo la cara visible: agentes pixelados, habitaciones editables y automatización por scripts; los pasos de "Quick start" aplican tal cual (copiar `.env`, instalar dependencias, poblar `data/` y arrancar `npm start`). Toda la API y los scripts están documentados arriba; la carpeta `data/` queda fuera del repositorio para no filtrar estados reales.

Novedades: la oficina muestra la **presencia en vivo de Hermes Agent y OpenClaw** (`GET /api/presence` + chips de estado), la interfaz del visor es **bilingüe (EN/ES)** con el interruptor 🌐 arriba a la izquierda, hay un **Makefile** para construir y correr la imagen Docker (`make build && make run`) y los cambios importantes se registran en `CHANGELOG.md`.

Sprites: MetroCity Free Topdown Character Pack (JIK-a-4). Tileset: Office Interior Tileset de Donarg (no incluido; cópialo como `assets/oficina.png` si lo compras).
