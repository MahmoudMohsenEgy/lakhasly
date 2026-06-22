# Study Lamp — App Login (Single Shared Password)

**Date:** 2026-06-22
**Status:** Design approved, pending implementation plan

## Problem

Study Lamp (the FastAPI web app at `studylamp.mohsen-group.com`) currently has
**no authentication** — anyone who can reach the URL can generate and read
modules. We want to keep strangers out while letting a small fixed group of
known people use the tool.

## Decisions

These were settled during brainstorming:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Gate location | **In-app auth** | Self-contained; no dependency on Cloudflare Access config. |
| User base | **Small fixed group** | A handful of known people; no public signup. |
| Login method | **Single shared password** | Simplest viable gate; the group shares one secret. |
| Data scope | **Shared library** | Everyone sees the same modules; login is purely a gate. |
| Crypto basis | **stdlib only** (`hashlib.scrypt` + `hmac`) | Zero new dependencies; offline-capable; matches the app's self-contained ethos (bundled mermaid, baked-in fonts). |

**Accepted tradeoff:** a single shared password means no per-person identity and
no per-person revocation. To remove one person's access, rotate the password (and
the secret key) and re-share with the rest. For a few known people sharing a study
tool, this is an acceptable trade.

## Architecture

Auth is a self-contained front gate. The agent, jobs, library, thumbnails, and
rendering are **unchanged**. All new logic lives in one module.

### `src/explainer/web/auth.py` (new)

- **`check_password(submitted: str) -> bool`** — constant-time compare of the
  submitted password against the configured scrypt hash, using
  `hmac.compare_digest`.
- **`hash_password(plaintext: str) -> str`** — generate a per-deploy random salt,
  scrypt-hash the password, return a single `salt$hash` string (base64). Used by
  the CLI helper, not at request time.
- **`SessionCodec`** — hmac-signs a cookie payload `{issued_at}` with the server
  secret.
  - `issue() -> str` — mint a signed, timestamped cookie value.
  - `read(cookie: str) -> bool` — return whether the cookie is valid: good
    signature **and** not older than the TTL. Rejects tampered, expired, or
    garbage cookies.
- **`require_auth`** — a FastAPI dependency applied to protected routes. Missing
  or invalid session → redirect to `/login` for HTML requests, `401` JSON for
  `/api/*` requests.

### `src/explainer/web/app.py` (changes)

New routes, wired in `create_app`:

- `GET /login` — minimal login page (one password field), respecting the existing
  light/dark + EN/AR styling.
- `POST /login` — verify the password; on success set the session cookie and
  redirect to `/`; on failure re-render with a generic error after a fixed delay.
- `POST /logout` — clear the cookie, redirect to `/login`.

The gate is applied to `/` and all `/api/*` routes. `/login` (GET + POST) and the
static assets needed to render the login page stay public.

### `src/explainer/config.py` (changes)

Two new fields read in `Config.from_env`:

- `STUDYLAMP_PASSWORD_HASH` — the `salt$hash` string from the helper. **Required**;
  app refuses to start if unset.
- `STUDYLAMP_SECRET_KEY` — signs session cookies. **Required**; app refuses to
  start if unset (fail closed — never sign with a default).
- `STUDYLAMP_SESSION_DAYS` — session TTL in days. Optional, default **30**.

### CLI helper

`explain-web hash-password` (or an equivalent subcommand) prompts for a password
and prints the `salt$hash` string to paste into `.env`. No plaintext password is
ever written to disk.

## Request flow

1. Unauthenticated visitor hits any protected page → `require_auth` finds no valid
   cookie → redirect to `GET /login` (HTML) or `401` (`/api/*`).
2. `GET /login` serves the minimal password page.
3. `POST /login` → `check_password` constant-time compare:
   - **Match:** `SessionCodec.issue()` mints an hmac-signed cookie `{issued_at}`,
     set `HttpOnly`, `SameSite=Lax`, `Secure`; redirect to `/`.
   - **No match:** re-render `/login` with a generic "Wrong password" message after
     a fixed ~250ms delay to blunt rapid guessing.
4. `POST /logout` clears the cookie, redirects to `/login`.

**Session lifetime:** the cookie carries a signed `issued_at`. `read()` rejects
anything older than `STUDYLAMP_SESSION_DAYS` (default 30) or with a bad signature.
No server-side session store — stateless, preserving the single-process /
in-memory-job constraint. Rotating `STUDYLAMP_SECRET_KEY` invalidates all sessions
at once ("log everyone out" lever).

## Security details

- **Hashing:** `hashlib.scrypt` with a per-deploy random salt stored alongside the
  hash. Helper emits a single `salt$hash` (base64) string; no plaintext on disk.
- **Cookie:** `HttpOnly` + `SameSite=Lax` + `Secure` (served over HTTPS via
  Cloudflare); signed with `hmac.new(secret, …, sha256)`, verified with
  `hmac.compare_digest`.
- **Fail closed:** unset `STUDYLAMP_SECRET_KEY` or `STUDYLAMP_PASSWORD_HASH` →
  app refuses to start with a clear message pointing at the helper.
- **Generic failures:** never reveal whether it's "no password set" vs "wrong
  password"; fixed delay on failed login.

## Edge cases

- No `STUDYLAMP_PASSWORD_HASH` configured → startup error pointing at the
  `hash-password` helper.
- Tampered / expired / garbage cookie → treated as logged-out, redirect to
  `/login`.
- `/api/*` unauthenticated → `401` JSON; the frontend's existing fetch wrapper
  (`api.js`) gets a small tweak to redirect to `/login` on a 401.

## Testing

Extends the existing `tests/` suite, using `httpx` (already in dev deps).

- **`auth.py` units:** hash round-trip; wrong password rejected; cookie
  issue→read round-trip; tampered cookie rejected; expired cookie rejected.
- **App integration:** gated route without cookie → redirect/401; `POST /login`
  wrong → re-render; correct → cookie set + `/` reachable; `/login` reachable
  while logged out; `logout` clears access.
- **CLI helper:** `hash-password` output parses back into a verifiable hash.

## Docs

- **`DEPLOY.md`** — replace the "Optional: require login" Cloudflare Access note
  with the in-app login setup (generate hash, set the two env vars).
- **`.env.example`** — add `STUDYLAMP_PASSWORD_HASH`, `STUDYLAMP_SECRET_KEY`,
  `STUDYLAMP_SESSION_DAYS`, with helper instructions.

## Out of scope

- Per-user accounts, usernames, signup, password reset flows.
- Per-user / private module libraries.
- Cloudflare Access (the edge-gate alternative we chose not to use).
