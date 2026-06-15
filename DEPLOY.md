# Deploying Study Lamp

Docker + Cloudflare Tunnel. The app runs in one container bound to the server's
loopback; your existing Cloudflare Tunnel publishes it over HTTPS. No public ports,
no certificate management, no reverse proxy to maintain.

## What the app needs

- **Outbound internet** at render time: Azure OpenAI, the search backend (Tavily or
  DuckDuckGo), Google Fonts (the Cairo font in the PDF) and a CDN (KaTeX for math).
  Mermaid diagrams do **not** need outbound internet — the mermaid library is bundled
  into the image (`explainer/figures/vendor/mermaid.min.js`) and rendered offline.
- **Secrets** (set in `.env`): Azure OpenAI endpoint/deployment/key, and a Tavily key
  if `SEARCH_BACKEND=tavily`.
- **One process only.** Job state is in-memory, so never scale to multiple workers or
  replicas (the Dockerfile and compose already enforce a single worker).

## Prerequisites on the server

- Docker Engine + the Compose plugin (`docker compose version`).
- Your Cloudflare Tunnel already up (it is — that's what serves `ssh.mohsen-group.com`).

## 1. Get the code onto the server

```bash
git clone <your-repo-url> studylamp && cd studylamp
# or: rsync -a --exclude .venv --exclude output ./ user@server:~/studylamp/
```

## 2. Configure secrets

```bash
cp .env.example .env
# edit .env: AZURE_OPENAI_ENDPOINT / _DEPLOYMENT / _API_KEY, TAVILY_API_KEY, etc.
```

`.env` is git-ignored and is **not** baked into the image — it's read at container
start via `env_file`.

## 3. Build and run

```bash
docker compose up -d --build
docker compose logs -f          # watch startup
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/   # expect 200
```

Generated PDFs/thumbnails persist in `./output/` on the host (bind-mounted).

## 4. Expose it through your Cloudflare Tunnel

Point a hostname (e.g. `studylamp.mohsen-group.com`) at `http://localhost:8000`.

**Dashboard-managed tunnel** (Zero Trust → Networks → Tunnels):
1. Open your tunnel → **Public Hostname** → **Add a public hostname**.
2. Subdomain `studylamp`, Domain `mohsen-group.com`.
3. Service: **HTTP**, URL `localhost:8000`. Save.

**Locally-managed tunnel** (`~/.cloudflared/config.yml`) — add an ingress rule
*above* the catch-all, then `sudo systemctl restart cloudflared`:
```yaml
ingress:
  - hostname: studylamp.mohsen-group.com
    service: http://localhost:8000
  # ... your existing rules ...
  - service: http_status:404
```

Cloudflare provisions the TLS certificate automatically. Visit
`https://studylamp.mohsen-group.com`.

### Optional: require login

In Zero Trust → **Access → Applications**, add a self-hosted app for
`studylamp.mohsen-group.com` with a policy (e.g. allow your email / Google login).
This puts an auth gate in front of the whole site — the app itself has no user
accounts.

## Updating

```bash
git pull
docker compose up -d --build
```

## Operations

```bash
docker compose logs -f        # tail logs
docker compose restart        # restart
docker compose down           # stop and remove the container (output/ is kept)
```

## Notes & gotchas

- **One worker is intentional.** Don't add `--workers N` or a second replica; running
  jobs are held in memory in a single process.
- **Generation is slow (1–2 min) and CPU/RAM-heavy** while Chromium renders. A small
  VPS is fine for one user at a time; concurrent generations compete for the box.
- **Google Drive upload (optional):** the OAuth callback uses the request's public URL,
  so register `https://studylamp.mohsen-group.com/api/drive/callback` as an authorized
  redirect URI in your Google Cloud OAuth client, and mount the secrets/token files as
  shown (commented) in `docker-compose.yml`.
- **Arabic fonts:** Cairo is fetched from Google Fonts during render; Noto Arabic is
  baked into the image as a fallback. If you ever run somewhere with no outbound
  internet, add a `@font-face` with a bundled Cairo file to the document stylesheet.
