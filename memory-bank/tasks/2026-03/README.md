# Tasks — March 2026

## 2026-03-07: Password Reset + .env Support + TopBar Fix
- Password reset flow: forgot password form, SMTP email with JWT reset link, set new password page
- `.env` file support via `python-dotenv` for mail config and JWT secret
- `MailConfig` added to config schema with env var overrides
- TopBar user menu dropdown z-index fix (was clipped by main overflow)
- Stable JWT secret in `.env` for session persistence across server restarts
- Files: `mail.py`, `auth.py`, `schema.py`, `loader.py`, `LoginPage.tsx`, `ResetPasswordPage.tsx`, `TopBar.tsx`
- See: [070307_password-reset.md](./070307_password-reset.md)

## 2026-03-07: Z-index Fix + GPT-5.4 + .env Docs
- Fixed z-index stacking contexts trapping dropdowns (Shell z-10, TopBar z-20 removed)
- Added CSS z-index tokens (`--z-background`, `--z-dropdown`, `--z-overlay`, `--z-modal`)
- Added `isolate` to Shell root, replaced backdrop hack with click-outside pattern in TopBar
- Added GPT-5.4 to model catalog (1M context, $2.50/$15.00, no-temperature)
- Updated `.env.example` with provider API key placeholders
- Updated README quick start with all provider env vars
- Files: `duh-theme.css`, `Shell.tsx`, `TopBar.tsx`, `GridOverlay.tsx`, `ParticleField.tsx`, `ExportMenu.tsx`, `ConsensusComplete.tsx`, `ThreadDetail.tsx`, `catalog.py`, `.env.example`, `README.md`
- 1603 Python + 185 Vitest tests passing
