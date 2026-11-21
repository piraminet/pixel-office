# Changelog

All notable changes to **Pixel Startup** (formerly "Pixel Office"; the visual environment keeps that name) are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

## [Unreleased]

### Added
- **Mechanic Shop / Pirate Ship / Lost Boys Treehouse packs (G22 B3):** three isometric launch environments through the shared generator pipeline — `mechanic_layout`, `pirate_layout`, `treehouse_layout` + `PACK_META`/`LAYOUTS` registry in `tools/generate_environments.py` (generic `build_pack` for all packs; zero backend changes to register new ones). Each: 7 rooms, 16 workstations, 4 interaction spots, themed furniture (workbenches + tool partitions + crate lift platforms; helmsman's wheel, rudder housing, barrels, cargo crates; log walls, lookouts, tree perches) and per-pack palettes with brightened wall-dark for backdrop contrast. Label-pill anchors spaced so iso-adjacent rooms don't collide after projection; partition height 96→72 synced in both the generator and `environments.js`. Test suite extended to 60 asserts: static 4-pack manifest validation, built-in pack switching round (mechanic-shop), registry-count updates.

- **Isometric environment system (G22 B1/B2):** reusable environment manifests (`assets/environments/<id>/manifest.json`, schema 1) validated by `environments.js`; generic pack registry — new packs drop in as directories with no backend changes. New APIs: `GET /api/environments` (list + active + default), `GET /api/environment` (active manifest), `GET /api/environment/:id/manifest`, `POST /api/environment` (auth; selection persisted to `data/environment.json`, survives restart with graceful fallback to `continental` when a pack is deleted). Painted-map endpoints (`/api/collision`, `/api/rooms`) now serve manifest-baked data for non-default environments; dashboard painting/editing stays bound to the default environment (409 otherwise). Packs carry an optional `presentation` block (`projection: isometric`, tile 28×14, origin, wall height), a validated `furniture` taxonomy (kinds + solid-tile rule) that drives rendering and depth sorting, per-environment collision (18×22), 7 named rooms, 16 workstations, 4 interaction spots, spawn and agent-room placement slots. Backdrops are deterministic programmatic renders (`tools/generate_environments.py --check|--only <id>`): Habbo-style cutaway (camera-facing walls become a gold floor curb), continuous ziggurat cornices, room-tinted floors — original generated art, no copyrighted assets. Suite `tests/environments.js` (33 asserts) added to `npm test`.

### Changed
- **Project reorientation (G−1):** platform identity moves from Pixel Office to **Pixel Startup** — repository/package `pixel-startup`, future Python package `pixel_startup`, CLI `pixel-startup`. The visual environment keeps the **Pixel Office** name; character identities, sprites, data file formats (`pixel_actions.jsonl`, `pixel-config.json`, …), API routes, the `pixel_session` cookie and the Vaultwarden device identifier are unchanged for backward compatibility. GitHub repository renamed to `bageera/pixel-startup` (2026-11-20, owner-authorized; GitHub redirects all old-name URLs).

### Fixed
- **Agent-harness presence (Hermes + OpenClaw chips):** `GET /api/presence` is now auth-gated (dashboard cookie or Bearer token) — anonymous callers get 401, since the payload includes session ids/pids; the frontend chips render live state for logged-in users and stay offline for anonymous visitors. `integrations.js` gains `HERMES_PRESENCE_TRUST_FILES=1` for containerized consumers: pods have their own PID namespace (host PIDs unverifiable via `kill(pid,0)`), so liveness derives from `gateway_state.json`/`active_sessions.json` content bounded by mtime freshness checks (5 min for the heartbeat-rewritten gateway file, 30 min for the event-driven session lease file whose staleness is bounded by Hermes' lease GC) instead of host PID probes.
- **`dashboard.html` was inert** (corrupt token spellings shipped in 14fb96e): 18 `onclickk` → `onclick` handlers (Export/Import/Save/Logout/tabs/minimap/brushes), 27 `transiten` → `transition`, 5 `positen` → `position` CSS, `.clickk()`/`clickkX/Y`/`handleMinimapClickk` fixed, and the `rolee` → `role` data-field corruption restored (role inputs round-trip correctly now).
- **`char_2.png` (Charon) was a 631-byte stub** since 14fb96e; the intact 5,221-byte sheet was recovered from git history (075e1f1) and kept as `char_2_original.png`.

### Added
- **Python migration gauntlet (G7–G9):** OpenClaw adapter (`/v1/models` only; undocumented ops explicit `supported:false`), Hermes adapter (live filesystem interface — gateway/session/platform discovery, evidence-gated promotion), employee/character alignment (SQLite schema v2: binding-proof chain with storage-layer impersonation guard, CAS lifecycle machine, boot-time non-destructive roster alignment; Charon's OpenClaw binding stays pending the gateway). Details: `docs/migration/MIGRATION-LEDGER.md`.
- **Custom Charon sprite**: hooded figure with cyan glow accents — deterministic palette swap of the restored sheet (`tools/generate-assets.py`), preserving the 7x3/16x32 frame geometry the canvas slices.
- **Real pixel-art office placeholder** replacing the blank-grid background: 640x800 (true canvas size — the old 960x720 asset overfilled and clipped), drawn from the default collision map (brick walls, desks/shelves/counter with cyan LED strip, doors, chairs, plants, wall lamps, room tints aligned to Reception/Workstations/Archives anchors). Regenerate with `tools/generate-assets.py` after editing the layout.

### Added
- **First-class agent runtimes**: `GET /api/presence` with Hermes Agent (session/gateway state under `~/.hermes`) and OpenClaw (gateway HTTP probe) adapters in `integrations.js`; live status chips in the office overlay.
- Bilingual UI (English/Spanish) with a persisted language toggle (`i18n` block in `index.html`).
- `Makefile` for Docker build/run/test lifecycle plus `.dockerignore` (keeps `.env`, `data/`, `node_modules` out of the image); `make push-image` publishes to `ghcr.io/bageera/pixel-startup:latest` for build hosts.
- `npm test` now runs the presence-integration, API-baseline (44 asserts) and security regression suites.

### Security
- **Static serving restricted to an explicit public allowlist** (previously the repository root was served — `.env` and source were downloadable).
- **Session authentication**: `POST /api/auth/login` now issues an HttpOnly HMAC-signed cookie; mutating and sensitive APIs require it; automation uses `Bearer PIXEL_API_TOKEN`. Default password `pixeladmin` removed; boot refuses to start without `DASHBOARD_PASSWORD` unless `PIXEL_ALLOW_NO_PASSWORD=1`. Login attempts rate-limited.
- **Raw Vaultwarden item retrieval disabled** (returned passwords to any caller) — returns 403 until the capability executor replaces it.
- **External email send disabled** until authorized draft-first delivery ships.
- **Contacts/org search disabled** (SQL→shell injection class); AI proxy hardened (client system prompts ignored, gated).

## [1.1.0] - 2026-11-19

### Added
- MVP office layout with three areas: Reception, Workstations, Archives.
- Environment customized for the gammaclaw deployment.

## [1.0.0] - 2026-03-07

### Added
- Initial public release: pixel-art office viewer, password-protected dashboard, REST API, and email/calendar automation scripts.

### Security
- Removed accidentally committed keys, added `.gitignore`, and generalized the bundled skill.
