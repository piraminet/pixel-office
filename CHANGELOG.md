# Changelog

All notable changes to Pixel Office are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

## [Unreleased]

### Added
- **First-class agent runtimes**: `GET /api/presence` with Hermes Agent (session/gateway state under `~/.hermes`) and OpenClaw (gateway HTTP probe) adapters in `integrations.js`; live status chips in the office overlay.
- Bilingual UI (English/Spanish) with a persisted language toggle (`i18n` block in `index.html`).
- `Makefile` for Docker build/run/test lifecycle plus `.dockerignore` (keeps `.env`, `data/`, `node_modules` out of the image).
- `npm test` now runs the presence-integration self-checks (`test_presence.js`).

## [1.1.0] - 2026-11-19

### Added
- MVP office layout with three areas: Reception, Workstations, Archives.
- Environment customized for the gammaclaw deployment.

## [1.0.0] - 2026-03-07

### Added
- Initial public release: pixel-art office viewer, password-protected dashboard, REST API, and email/calendar automation scripts.

### Security
- Removed accidentally committed keys, added `.gitignore`, and generalized the bundled skill.
