# Tasks — March 2026

## 2026-03-07: Password Reset + .env Support + TopBar Fix
- Password reset flow: forgot password form, SMTP email with JWT reset link, set new password page
- `.env` file support via `python-dotenv` for mail config and JWT secret
- `MailConfig` added to config schema with env var overrides
- TopBar user menu dropdown z-index fix (was clipped by main overflow)
- Stable JWT secret in `.env` for session persistence across server restarts
- Files: `mail.py`, `auth.py`, `schema.py`, `loader.py`, `LoginPage.tsx`, `ResetPasswordPage.tsx`, `TopBar.tsx`
- See: [070307_password-reset.md](./070307_password-reset.md)
