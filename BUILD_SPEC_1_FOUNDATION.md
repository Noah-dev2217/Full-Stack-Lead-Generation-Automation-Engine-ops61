# Build Spec #1 — Foundation (Sheets + n8n + Discord)

> **One Claude Code session.** Builds the shared infrastructure all four pipelines depend on. No pipeline business logic in this session — just the foundation.

**Owner:** Rinoah
**Estimated session time:** 2–3 hours (most of it is Google Workspace clicking, not code)
**Branch:** `foundation`
**Reference docs to load:** `OPS-61_PLAN.md`, `shared/sheets-schema.md`, `docs/EASYGROW_SPEC.md`, this file

---

## Goal

By the end of this session, the repo has:

1. A Google Sheet created with the exact 4-tab schema from `shared/sheets-schema.md`
2. A Google Service Account with editor access to that Sheet + a designated Drive folder
3. Credentials wired into `.env` (gitignored)
4. A working n8n connection to both Google Workspace and Discord
5. One shared n8n subworkflow that all four pipelines will call: `write_row_to_sheet`
6. A Discord webhook configured for the `#ops-61-feed` channel
7. A working smoke test that writes a test row to all 4 tabs and pings Discord

Pipelines themselves come in Build Specs #2–#5. **Do not build pipeline logic in this session.**

---

## Out of scope for this session

- Perplexity API integration (Build Spec #2)
- Claude API integration (Build Spec #2)
- Chrome extension (Build Spec #4)
- Python recorder service (Build Spec #5)
- Any pipeline-specific n8n workflow logic

If you find yourself tempted to build any of the above, stop and commit what you have.

---

## Tasks

### 1. Google Sheet creation

Create a new Sheet in Google Drive called `OPS-61 CRM`. Add four tabs, named **exactly**:

- `Loomless`
- `JV_Targets`
- `Terminator_Loom`
- `Inbound`

For each tab, the header row (row 1) is the column list from `shared/sheets-schema.md`. **Column names are exact, snake_case, no spaces.** Header row should be frozen and bolded.

Reference: full schema in `shared/sheets-schema.md` — copy column names verbatim.

After creation, grab the Sheet ID from the URL (`docs.google.com/spreadsheets/d/<THIS_ID>/edit`) and put it in `.env` as `GOOGLE_SHEET_ID`.

### 2. Google Drive folders

In Drive, create two folders inside an `OPS-61` parent folder:

- `OPS-61/Loomless-Inbox/` — n8n will watch this folder for new CSV uploads (Pipeline 2)
- `OPS-61/Terminator-Loom-Videos/` — recorder uploads mp4s here (Pipeline 5)

Grab the folder IDs from URLs and put them in `.env`:
- `GOOGLE_DRIVE_LOOMLESS_INBOX_FOLDER_ID`
- `GOOGLE_DRIVE_FOLDER_ID` (the Terminator Loom one — the more general var name is intentional, Pipeline 5 is the heavy user)

### 3. Service Account creation

In Google Cloud Console:

1. Create or select a project (e.g. `ops-61-automation`)
2. Enable APIs: **Google Sheets API**, **Google Drive API**
3. Create a Service Account named `ops-61-sa`
4. Generate a JSON key, download it
5. Move the JSON to repo root as `service-account.json` (verify `.gitignore` excludes it — it does, but confirm before commit)
6. Set `GOOGLE_SERVICE_ACCOUNT_PATH=./service-account.json` in `.env`

Grant the Service Account access:
- Share the `OPS-61 CRM` Sheet with the Service Account email (Editor)
- Share both Drive folders with the Service Account email (Editor)

### 4. Discord webhook

Create a Discord channel `#ops-61-feed` in the FC team Discord server. Create a webhook on the channel. Put the webhook URL in `.env` as `DISCORD_WEBHOOK_OPS61_FEED`.

(Threads per pipeline come later as a usability nicety — single channel for v1.)

### 5. n8n base setup

Connect n8n credentials:

1. In n8n, create credential `Google Sheets — OPS-61 SA` using the Service Account JSON
2. In n8n, create credential `Google Drive — OPS-61 SA` using the same Service Account JSON
3. Verify both connect successfully (n8n's "Test" button on the credential)

### 6. Shared subworkflow: `write_row_to_sheet`

Build one reusable n8n workflow that all four pipelines will call. Name: `Sub_WriteRowToSheet`.

**Inputs (passed via webhook or sub-workflow execution):**
```json
{
  "tab": "Loomless | JV_Targets | Terminator_Loom | Inbound",
  "row": { /* object with keys matching the tab's columns */ }
}
```

**Behavior:**
- Validates the `tab` value (one of the 4 known tabs); errors out clearly if not
- Appends `row` to the named tab, mapping object keys to columns
- Auto-fills `created_at` (or `captured_at` / `recorded_at` depending on tab) with current UTC ISO timestamp if not provided
- Returns success/failure + the new row index

**Export to repo:**
After building, export the workflow JSON to `shared/n8n-templates/Sub_WriteRowToSheet.json`. Commit it. Version-controlling n8n workflows as JSON is the convention (see `README.md`).

### 7. Shared subworkflow: `notify_discord`

Build a second reusable workflow named `Sub_NotifyDiscord`.

**Inputs:**
```json
{
  "level": "info | hot | error",
  "pipeline": "loomless | jv | terminator | fb_router",
  "message": "string",
  "fields": { /* optional key-value pairs to include */ }
}
```

**Behavior:**
- Formats a Discord message with emoji prefix based on `level`:
  - `info` → ℹ️
  - `hot` → 🔥
  - `error` → ❌
- Includes `pipeline` tag and timestamp
- POSTs to the webhook URL from `DISCORD_WEBHOOK_OPS61_FEED`

**Export to repo:** `shared/n8n-templates/Sub_NotifyDiscord.json`.

### 8. Smoke test workflow

Build a one-off workflow `OPS-61_Foundation_Smoke_Test`:

- Triggered manually
- Calls `Sub_WriteRowToSheet` four times, once per tab, with a clearly-marked test row (e.g. `Company_Name = "SMOKE_TEST"`)
- Calls `Sub_NotifyDiscord` with `level=info`, `pipeline=loomless`, `message="Foundation smoke test fired"`
- Run it, verify:
  - 4 rows appear in the Sheet (one per tab) with SMOKE_TEST markers
  - 1 message appears in `#ops-61-feed`

After verifying, delete the smoke test rows from the Sheet. Export the smoke test workflow to `shared/n8n-templates/Smoke_Test_Foundation.json` and commit (it stays in the repo as a re-runnable health check).

---

## File deliverables

By end of session, `git status` should show new files at:

```
.env                                         (NOT committed — gitignored)
service-account.json                         (NOT committed — gitignored)
shared/n8n-templates/Sub_WriteRowToSheet.json     (committed)
shared/n8n-templates/Sub_NotifyDiscord.json       (committed)
shared/n8n-templates/Smoke_Test_Foundation.json   (committed)
shared/n8n-templates/README.md                    (committed — short doc explaining how to import these into a fresh n8n instance)
```

Optionally, if any helper scripts are useful (e.g. a Python script to bootstrap the Sheet from the schema file), put them in `shared/scripts/` and document in the n8n-templates README.

---

## Acceptance criteria

All of the following must be true before marking this build spec complete:

- [ ] `OPS-61 CRM` Sheet exists with exactly 4 tabs, exactly the columns from `shared/sheets-schema.md`, headers frozen + bold
- [ ] Both Drive folders exist and are shared with the Service Account
- [ ] `.env` populated locally (Rinoah's machine) with all 7 required vars (4 IDs + SA path + Discord webhook + n8n base URL)
- [ ] `service-account.json` exists locally, gitignored, verified not committed (`git ls-files | grep service-account` returns nothing)
- [ ] n8n credentials for Sheets + Drive both pass the Test button
- [ ] Discord webhook posts a test message successfully
- [ ] Smoke test workflow runs end-to-end: writes 4 rows + pings Discord
- [ ] All three n8n workflow JSONs exported to `shared/n8n-templates/`
- [ ] `shared/n8n-templates/README.md` explains how to re-import into a fresh n8n instance
- [ ] Branch `foundation` merged to `main` after smoke test passes

---

## Guardrails for the Claude Code session

**DO:**
- Read `OPS-61_PLAN.md` first for full context, then `shared/sheets-schema.md` for column truth
- Ask for clarification if any Service Account permission step fails (Google permissions are fiddly; don't guess)
- Commit incrementally: one commit per major step (Sheet created, SA created, n8n connected, subworkflows built, smoke test passed)
- Treat `shared/sheets-schema.md` as the source of truth — if it contradicts the plan, the schema file wins (it's pulled out specifically as canonical)

**DO NOT:**
- Build any pipeline-specific logic (no Perplexity calls, no Claude calls, no CSV parsing, no Playwright). That's later build specs.
- Modify `OPS-61_PLAN.md` or `shared/sheets-schema.md` without flagging in chat first. These are locked.
- Commit `.env` or `service-account.json`. Verify `git status` before every commit.
- Create additional Sheet tabs or extra columns "just in case". Schema is locked.
- Use API keys (Anthropic, Perplexity) in this session — those aren't needed until Build Spec #2.

---

## Handoff to Build Spec #2

When this is done, Build Spec #2 (Loomless pipeline) has everything it needs:

- A Sheet to write to
- A Service Account that can write
- An n8n credential set
- A reusable subworkflow for row writes (call `Sub_WriteRowToSheet` with `tab="Loomless"`)
- A reusable subworkflow for Discord notifications (call `Sub_NotifyDiscord` with `pipeline="loomless"`)
- A smoke-tested foundation

Build Spec #2 will be drafted after this session is complete and verified.
