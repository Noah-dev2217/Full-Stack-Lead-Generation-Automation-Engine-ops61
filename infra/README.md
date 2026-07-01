# OPS-61 infra — dedicated n8n container

The n8n instance that runs all four OPS-61 pipelines. It lives **inside this
repo** on purpose: at handoff (build-order step 6), the whole stack moves to the
company server as one `git clone` — no extracting OPS-61 workflows out of a
shared n8n.

## What's here

| File | Committed? | Purpose |
|---|---|---|
| `docker-compose.yml` | ✅ yes | The n8n service definition |
| `.env.example` | ✅ yes | Template listing the secrets to provide |
| `.env` | ❌ gitignored | Real Sheet ID + Discord webhook (local only) |

## Run it (local dev)

```bash
cd infra
cp .env.example .env      # first time only — then fill in the two values
docker compose up -d
```

- Open **http://localhost:5679**
- Stop: `docker compose down` (data survives — it's in the `ops61_n8n_data` volume)
- Logs: `docker compose logs -f n8n`

## Isolation from OPS-52

This container shares **nothing** with the OPS-52 n8n at `C:\youtube-automation-os`:

| | OPS-52 | OPS-61 |
|---|---|---|
| Compose project | `youtube-automation-os` | `ops61` |
| Container name | `n8n` | `ops61-n8n` |
| Host port | `5678` | `5679` |
| Named volume | `n8n_data` (external) | `ops61_n8n_data` |
| Image | `youtube-automation-os-n8n:1.121.1-ffmpeg` (custom) | `n8nio/n8n:1.121.1` (stock) |

Both can run simultaneously. Starting/stopping one never touches the other.

## Env vars

Secrets are interpolated from `infra/.env` via `${...}` — they are **not**
hardcoded in `docker-compose.yml`, so the compose file is safe to commit:

- `GOOGLE_SHEET_ID` — OPS-61 CRM Sheet
- `DISCORD_WEBHOOK_OPS61_FEED` — #ops-61-feed webhook (dev server for now)
- `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` — lets Code nodes read `$env.*`

## Handoff to the company server (build-order step 6)

1. `git clone` the OPS-61 repo onto the target machine.
2. `cd infra && cp .env.example .env`, fill in the **prod** Sheet ID + the
   **prod** Discord webhook (not the dev one).
3. Adjust host-facing settings if the server isn't accessed via localhost:
   `N8N_HOST`, `WEBHOOK_URL` (and the `5679:5678` mapping if needed).
4. `docker compose up -d`.
5. Re-create the n8n Google Service Account credential and re-import the three
   workflows from `shared/n8n-templates/` (see that folder's README). n8n
   credentials are encrypted per-instance and are **not** carried in git.
