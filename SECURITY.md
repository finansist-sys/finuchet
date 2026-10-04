# Security

## Reporting a vulnerability

Please **do not open a public issue**. Use GitHub private vulnerability reporting:
repository → **Security** → **Report a vulnerability**. We aim to reply within 7 days.

## Design summary

- **Authentication**: Telegram Mini App `initData` verified with HMAC-SHA256 (bot token derived key),
  constant-time comparison, 24 h lifetime; destructive actions require data signed within 10 minutes.
- **Pseudonymous storage**: only `HMAC(pepper, telegram_id)` is stored; no names, usernames, e-mails,
  phones or IPs. The pepper is kept outside the database and its backups.
- **Authorization**: every query is scoped to the authenticated user; bot button callbacks re-check
  ownership (forged `callback_data` cannot reach other users' data).
- **Webhook**: unguessable path + `X-Telegram-Bot-Api-Secret-Token` check.
- **Input handling**: strict schemas (unknown fields rejected), length/amount limits, Unicode
  bidi/control characters stripped, card-number-like names rejected, HTML escaped in bot messages,
  linear-time parser (no ReDoS). Validation errors never echo submitted values.
- **Browser**: strict CSP (no inline scripts, only `telegram.org` as external script), no third-party
  analytics, no financial data in local storage.
- **Infrastructure**: database on an internal Docker network only, non-superuser DB role,
  non-root read-only app container, dropped capabilities, no access logs.
- **Repository**: pre-commit privacy guard + CI scan block e-mails, tokens, keys, local paths and
  non-anonymous commit identities.

## Running the checks

```sh
cd backend && pytest && ruff check app tests && pip-audit -r requirements.txt
cd webapp && npx tsc -p tsconfig.json --noEmit && npx vitest run && npm audit
python scripts/privacy_guard.py all
```
