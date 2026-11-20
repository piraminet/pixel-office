# Changelog

All notable changes to Pixel Office are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

## [Unreleased]

### Added
- **First-class agent runtimes**: `GET /api/presence` with Hermes Agent (session/gateway state under `~/.hermes`) and OpenClaw (gateway HTTP probe) adapters in `integrations.js`; live status chips in the office overlay.
- Bilingual UI (English/Spanish) with a persisted language toggle (`i18n` block in `index.html`).
- `Makefile` for Docker build/run/test lifecycle plus `.dockerignore` (keeps `.env`, `data/`, `node_modules` out of the image).
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
