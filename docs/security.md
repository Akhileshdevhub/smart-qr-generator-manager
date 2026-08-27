# Security

An honest account of what the project does and does not protect against.

## Authentication

- **Password hashing.** Passwords are hashed with **bcrypt** (via passlib) and
  only the hash is stored. bcrypt is deliberately slow and salts each password,
  which makes brute-forcing stolen hashes expensive. `test_password_is_hashed_in_db`
  asserts the stored value is a bcrypt hash, not the plaintext.
- **JWT sessions.** Login returns a signed JWT (`sub` = user id, plus an expiry).
  The server trusts a request when the signature verifies with `SECRET_KEY`; no
  server-side session table is needed. Trade-off: a token can't be revoked before
  it expires — acceptable for this project, and mitigated by a short lifetime.
  Token handling lives in `app/core/security.py`.

## Authorization (ownership)

Authorization is enforced **server-side** in `get_owned_project`
(`app/api/dependencies.py`): it loads a project by id and confirms
`project.owner_id == current_user.id`. If not (or the id doesn't exist), it
returns **404**, not 403 — so an attacker can't even tell which ids exist.

This blocks the classic **IDOR** ("insecure direct object reference") attack
where user A edits the id in `/api/qr/123` to reach user B's code.
`tests/test_authorization.py` verifies A cannot read, edit, or delete B's code.

## ID enumeration

Public redirect URLs use a random `short_id` (7 characters from a 55-symbol
alphabet ≈ 1.5 × 10¹² combinations), **not** the sequential database id. You
can't discover other people's codes by counting `/r/1`, `/r/2`, … The internal
integer id is never placed in a public URL.

## URL / redirect validation

Because a dynamic redirect sends a visitor's browser to a stored URL, this is the
most safety-critical validation in the app (`validate_destination_url` in
`payloads.py`):

- Only `http` and `https` are allowed.
- `javascript:`, `data:`, `vbscript:`, `file:`, `ftp:` are explicitly rejected.
- Malformed URLs (no scheme, no domain) are rejected.
- The destination is re-validated **on every scan**, not just at save time
  (defence in depth).

`tests/test_validation.py` covers each dangerous scheme.

## File upload safety

Uploaded logos are validated (size cap 2 MB, must decode as a real PNG/JPG/WEBP,
dimension cap) and then **fully re-encoded** by Pillow, so the original bytes
(which could hide a malicious payload) are never served back.

## Rate limiting

slowapi applies IP-based limits to abuse-prone endpoints: login/registration
(10/min), preview rendering (60/min), and the public redirect (120/min). Behind a
proxy you'd configure the proxy to set a trustworthy `X-Forwarded-For`.

## Secrets management

`SECRET_KEY`, `DATABASE_URL`, etc. come from environment variables / `.env`,
which is git-ignored. `.env.example` documents them without real values. Logs
never include passwords, tokens, or the secret key.

## Error handling

A catch-all handler returns a generic `500 Internal server error` and logs the
detail server-side, so stack traces are never exposed to clients.

## What this does NOT do (be honest in interviews)

- No email verification, password-reset, 2FA, or account lockout.
- No CSRF tokens — the API is token-based (Bearer header), not cookie-based, so
  classic CSRF doesn't apply; but there's no protection against a malicious site
  reading a token out of `localStorage` via XSS. Mitigating that fully would mean
  httpOnly cookies + CSRF protection.
- No malware/phishing scanning of redirect destinations. We block dangerous URL
  *schemes* and allow deactivating a code, but we do not claim to detect
  malicious *content*. See [limitations.md](limitations.md).
- Rate limits are basic and in-memory (per process), not a distributed limiter.
