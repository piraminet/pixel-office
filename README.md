# Pixel Office

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
   cp -n .env.example .env   # tweak PORT, PIXEL_DATA_DIR, DASHBOARD_PASSWORD
   npm install
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

- Login via `POST /api/auth/login`; password comes from `.env` (`DASHBOARD_PASSWORD`).
- Leave the password blank only for kiosk demos.
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
  - `oficina-placeholder.png` → built-in placeholder grid. If you purchase Donarg's Office Interior Tileset drop your PNG as `assets/oficina.png` (gitignored) and the app will pick it up automatically in the viewer + dashboard.
- `docs/media/` → screenshots used here; keep 1920px width when updating marketing shots.

## 🎨 Credits & external assets

- Inspired by [pixel-agents](https://github.com/pablodelucca/pixel-agents) by Pablo Delucca — this project reuses the idea of a pixelated OpenClaw office and adapts it to this stack.
- Character sprites come from the [MetroCity Free Topdown Character Pack](https://jik-a-4.itch.io/metrocity-free-topdown-character-pack) by JIK-a-4. Review the itch.io license before redistributing; attribution is required.
- The office background was built with [Office Interior Tileset (16x16)](https://donarg.itch.io/officetileset) by Donarg (USD $2). This is the only part of Pixel Office that is not freely available; the tileset is **not** included here because of its license. To use it locally, purchase the pack, export your layout as `services/pixel/assets/oficina.png`, and Pixel Office will automatically pick it up (the file is gitignored).

See [CREDITS.md](CREDITS.md) for a handy table you can keep updated.

## 📦 Deploy notes

- Local demo: `npm start`.
- Remote share: e.g. `cloudflared tunnel --url http://127.0.0.1:19000` (or any reverse proxy you prefer).
- `.gitignore` already skips `.env`, `node_modules`, `data/`, backups and temp logs.

## ✅ Pre-share checklist

- [ ] Fresh `.env` with a password for the recipient.
- [ ] `data/` populated (from `sample-data/` or your latest backup).
- [ ] Dashboard login + save flow tested.
- [ ] Bash scripts pointing to the right `PIXEL_DATA_DIR`.
- [ ] Screenshots + video link still representative.

---

## 🇪🇸 Resumen en español

Pixel Office es un tablero retro para ver a tus agentes como personajes pixelados, editar habitaciones y colisiones desde un dashboard con contraseña y automatizar eventos mediante scripts. Sigue los pasos de "Quick start" (copiar `.env`, instalar dependencias, poblar `data/` desde `sample-data/` y arrancar `npm start`). Toda la API y los scripts están documentados arriba; solo recuerda que la carpeta `data/` queda fuera del repositorio para no filtrar estados reales.
Sprites: MetroCity Free Topdown Character Pack (JIK-a-4). Tileset: Office Interior Tileset de Donarg (no incluido; cópialo como `assets/oficina.png` si lo compras).
