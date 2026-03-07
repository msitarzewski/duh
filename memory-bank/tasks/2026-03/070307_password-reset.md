# 070307_password-reset

## Objective
Add password reset flow with email delivery, .env configuration support, and frontend UI.

## Outcome
- Password reset: forgot password form, email with JWT reset link, set new password page
- .env support: `python-dotenv` loads `.env` at startup, mail + JWT config via env vars
- Mail system: SMTP sender using stdlib (`smtplib`), supports plain/TLS/SSL
- TopBar dropdown z-index fix: user menu no longer hidden behind main content area
- JWT secret persistence: stable secret in `.env` survives server restarts
- 1586 Python tests + 185 Vitest tests (1771 total), build clean

## Files Modified
- `src/duh/config/schema.py` — added `MailConfig`, `reset_token_expiry_minutes` to `AuthConfig`
- `src/duh/config/loader.py` — `.env` loading via `python-dotenv`, mail env var resolution
- `src/duh/api/auth.py` — `POST /api/auth/forgot-password` + `POST /api/auth/reset-password`
- `pyproject.toml` — added `python-dotenv>=1.0`
- `web/src/api/types.ts` — forgot/reset request/response types
- `web/src/api/client.ts` — `forgotPassword()` + `resetPassword()` API calls
- `web/src/pages/LoginPage.tsx` — "Forgot password?" flow with inline form
- `web/src/App.tsx` — `/reset-password` public route
- `web/src/pages/index.ts` — export `ResetPasswordPage`
- `web/src/components/layout/TopBar.tsx` — `relative z-20` to fix dropdown clipping

## Files Created
- `src/duh/mail.py` — SMTP email sender (stdlib, no new deps beyond dotenv)
- `web/src/pages/ResetPasswordPage.tsx` — token-based password reset form
- `.env.example` — reference template for all env vars

## Patterns Applied
- Extends existing `AuthConfig` in `config/schema.py`
- Follows existing auth route pattern in `api/auth.py`
- Reuses `GlassPanel`, `GlowButton` shared components on new pages
- Mail env var resolution mirrors provider API key resolution pattern in `loader.py`

## Integration Points
- `api/auth.py:forgot_password` generates reset JWT, calls `mail.send_email()`
- `api/auth.py:reset_password` decodes JWT, updates `User.password_hash`
- Frontend: LoginPage → forgot flow → email → ResetPasswordPage → sign in
- `load_dotenv()` runs before all config resolution in `load_config()`

## Architectural Decisions
- Used stdlib `smtplib` over aiosmtplib — reset email is a rare operation, sync is fine
- Reset token is a purpose-scoped JWT (`"purpose": "password_reset"`) with 15-min expiry
- Generic response on forgot-password ("If that email is registered...") prevents email enumeration
- `.env` env vars always override defaults (not just when field is empty)
