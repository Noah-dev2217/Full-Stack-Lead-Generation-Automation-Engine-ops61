# OPS-61 shared n8n workflows

Version-controlled exports of the reusable n8n workflows the four pipelines
depend on. Import these into a fresh n8n instance to rebuild the foundation.

| File | Workflow | Role |
|---|---|---|
| `Sub_WriteRowToSheet.json` | `Sub_WriteRowToSheet` | Append a row to any CRM tab. Validates the tab name, auto-fills the per-tab timestamp column. Called by every pipeline. |
| `Sub_NotifyDiscord.json` | `Sub_NotifyDiscord` | Post a formatted embed to `#ops-61-feed`. Emoji + colour by `level`. Called by every pipeline. |
| `Smoke_Test_Foundation.json` | `OPS-61_Foundation_Smoke_Test` | Health check — writes one `SMOKE_TEST` row to all 4 tabs and pings Discord. Re-runnable. |

---

## Prerequisites on the n8n instance

These workflows read configuration from the n8n instance's **environment**, not
from the committed JSON (keeps the Sheet ID and webhook URL out of git). On the
Hostinger VPS, set these env vars for the n8n process (docker-compose
`environment:` block, or n8n's own `.env`) and restart n8n:

```
GOOGLE_SHEET_ID=<the OPS-61 CRM Sheet ID>
DISCORD_WEBHOOK_OPS61_FEED=<the #ops-61-feed webhook URL>
```

> n8n must allow expressions to read env vars. If `N8N_BLOCK_ENV_ACCESS_IN_NODE`
> is set to `true`, change it to `false` (or unset it) and restart, otherwise
> `{{ $env.GOOGLE_SHEET_ID }}` resolves empty.

You also need one **Google Service Account API** credential (n8n credential type
`googleApi`), built from `service-account.json`. The Foundation build spec names
it `Google Sheets — OPS-61 SA`. One credential covers Sheets and Drive.

---

## Import order (matters — sub-workflows first)

1. **`Sub_WriteRowToSheet.json`** → Import from File.
   - Open the **Append Row to Tab** node → set its credential to
     `Google Sheets — OPS-61 SA`. (The exported `id` is a placeholder; n8n will
     flag it as missing until you pick the real credential.)
   - Save.
2. **`Sub_NotifyDiscord.json`** → Import from File. No credential needed (it
   POSTs to the webhook URL via `$env`). Save.
3. **`Smoke_Test_Foundation.json`** → Import from File.
   - Open **Write Row to Each Tab** → in the *Workflow* field, select the
     imported `Sub_WriteRowToSheet`.
   - Open **Notify Discord** → select the imported `Sub_NotifyDiscord`.
   - (The exported `workflowId` values are `REPLACE_WITH_..._ID` placeholders —
     n8n can't resolve them across instances, so you re-select once after import.)
   - Save.

---

## Calling conventions (for pipeline build specs #2–#5)

**Write a row** — call `Sub_WriteRowToSheet` with one item per row:

```json
{ "tab": "Loomless", "row": { "Company_Name": "Acme", "First_Name": "Sam", "status": "ready_for_review" } }
```

- `tab` must be exactly one of `Loomless` | `JV_Targets` | `Terminator_Loom` | `Inbound` (else the workflow throws).
- `row` keys must match the tab's column headers in `shared/sheets-schema.md`. Unknown keys are ignored by auto-map; missing columns are left blank.
- The per-tab timestamp column (`created_at` / `recorded_at` / `captured_at`) is auto-filled with the current UTC ISO 8601 time **if you don't supply it**.
- You can pass several items in one call — each is appended to its own `tab`.

**Send a notification** — call `Sub_NotifyDiscord`:

```json
{ "level": "hot", "pipeline": "fb_router", "message": "DM permission granted — Jane Doe", "fields": { "Profile": "https://fb.com/jane" } }
```

- `level`: `info` (ℹ️ blue) | `hot` (🔥 orange) | `error` (❌ red). Defaults to `info`.
- `pipeline`: free label, e.g. `loomless` | `jv` | `terminator` | `fb_router`.
- `fields`: optional flat key→value object, rendered as inline embed fields.

---

## Running the smoke test

1. Open `OPS-61_Foundation_Smoke_Test`, click **Test workflow**.
2. Verify: one `SMOKE_TEST` row in each of the 4 tabs, and one ℹ️ message in
   `#ops-61-feed`.
3. Delete the 4 test rows (or run `python shared/scripts/verify_foundation.py --cleanup`).

> Note: the smoke test passes all 4 items through a single `Sub_WriteRowToSheet`
> call; the sub-workflow loops over them and routes each item to its own tab
> (one append per tab). Net effect is the four writes the build spec asks for.

A pure-Python equivalent (no n8n needed) lives at
`shared/scripts/verify_foundation.py` — handy for validating the Service Account
and webhook before n8n is wired.
