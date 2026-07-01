# OPS-61 Foundation — Setup Runbook

The manual, browser-driven half of **Build Spec #1**. Code deliverables (n8n
workflow templates, helper scripts, pre-commit hook) are already in the repo;
this runbook covers the Google Cloud / Google Workspace / Discord / n8n steps
that need *your* logged-in sessions, in order.

Work top to bottom. Each step says where a repo script or template takes over so
you do as little clicking as possible. Tick the acceptance checklist at the end.

---

## 0. One-time local setup

```bash
cp .env.example .env                    # fill in as you go below
git config core.hooksPath hooks         # activate the secret-blocking pre-commit hook
pip install -r shared/scripts/requirements.txt
```

`.env` and `service-account.json` are gitignored — never commit them.

---

## 1. Google Cloud project + Service Account

> If any permission step here fails, **stop and flag it** — Google IAM is fiddly
> and guessing makes it worse.

1. Go to <https://console.cloud.google.com> → create a project named
   `ops-61-automation` (or select an existing one).
2. **APIs & Services → Library** → enable both:
   - **Google Sheets API**
   - **Google Drive API**
3. **APIs & Services → Credentials → Create Credentials → Service account**:
   - Name: `ops-61-sa`
   - Role: none required at the project level (access is granted per-file by
     sharing, below). Skip the optional grant steps.
4. Open the new service account → **Keys → Add key → Create new key → JSON**.
   Download it.
5. Move the file to the repo root as **`service-account.json`**.
6. Confirm it's ignored:
   ```bash
   git check-ignore service-account.json   # should print the filename
   git status --short                      # service-account.json must NOT appear
   ```
7. In `.env`, leave `GOOGLE_SERVICE_ACCOUNT_PATH=./service-account.json`.
8. Copy the service account's **email** (looks like
   `ops-61-sa@ops-61-automation.iam.gserviceaccount.com`) — you'll share files
   with it next.

---

## 2. Create the Sheet + Drive folders, share with the SA

We let *you* create the containers (one-time clicks) and let the **script** do
the exact-schema formatting. Creating them by hand and sharing to the SA avoids
Service-Account Drive-storage-quota errors that hit SA-created files.

1. **Drive → New → Google Sheets** → rename the spreadsheet to **`OPS-61 CRM`**.
   - Copy its ID from the URL: `docs.google.com/spreadsheets/d/`**`<ID>`**`/edit`.
   - Put it in `.env` as `GOOGLE_SHEET_ID`.
   - **Share** (top-right) → add the SA email as **Editor**.
2. **Drive → New → Folder** → `OPS-61`. Inside it create two subfolders:
   - `Loomless-Inbox`  → share with SA email as **Editor**. Copy its folder ID
     (from the URL `drive/folders/<ID>`) into `.env` as
     `GOOGLE_DRIVE_LOOMLESS_INBOX_FOLDER_ID`.
   - `Terminator-Loom-Videos` → share with SA email as **Editor**. Copy its
     folder ID into `.env` as `GOOGLE_DRIVE_FOLDER_ID`.
3. Run the formatter — it builds the 4 tabs with the exact locked schema,
   freezes + bolds the header row, and is safe to re-run:
   ```bash
   python shared/scripts/populate_sheet.py
   ```
   Expected: `✓ headers written for all 4 tabs` and `✓ headers frozen + bolded`.

---

## 3. Discord webhook

1. In the FC team Discord server, create a text channel **`#ops-61-feed`**.
2. Channel → **Edit Channel → Integrations → Webhooks → New Webhook**.
3. Name it `OPS-61 Feed`, **Copy Webhook URL**.
4. Put it in `.env` as `DISCORD_WEBHOOK_OPS61_FEED`.

Quick check (writes 4 SMOKE_TEST rows + posts one Discord message, all via the
Service Account — no n8n needed yet):

```bash
python shared/scripts/verify_foundation.py
# inspect the Sheet + #ops-61-feed, then:
python shared/scripts/verify_foundation.py --cleanup
```

If this passes, your creds, Sheet, and webhook are all good before you touch n8n.

---

## 4. n8n credentials + workflow import

On the Hostinger VPS n8n (`N8N_BASE_URL`, default `https://n8n.fascinatecopy.com`):

1. **Set env vars** on the n8n process and restart (see
   `shared/n8n-templates/README.md` for the why):
   ```
   GOOGLE_SHEET_ID=<same as .env>
   DISCORD_WEBHOOK_OPS61_FEED=<same as .env>
   ```
2. **Credentials → New → Google Service Account API** (`googleApi`):
   - Name it `Google Sheets — OPS-61 SA`.
   - Paste the full contents of `service-account.json`.
   - Click **Test** → must succeed. (Optionally clone it as
     `Google Drive — OPS-61 SA`; same JSON, used by later Drive nodes.)
3. **Import the three workflows** following the order + post-import wiring in
   `shared/n8n-templates/README.md` (sub-workflows first; re-select credential
   on the Sheets node and the two sub-workflows in the smoke test).

---

## 5. Run the n8n smoke test

1. Open `OPS-61_Foundation_Smoke_Test` → **Test workflow**.
2. Verify **4 rows** (one per tab, `SMOKE_TEST` marker) and **1 message** in
   `#ops-61-feed`.
3. Delete the test rows: `python shared/scripts/verify_foundation.py --cleanup`
   (or remove them by hand).

---

## 6. Finish

```bash
git ls-files | grep -i 'service-account\|^\.env$'   # must return NOTHING
```

Then merge `foundation` → `main` (the build spec's final acceptance item).

---

## Acceptance checklist (from BUILD_SPEC_1_FOUNDATION.md)

- [ ] `OPS-61 CRM` Sheet: 4 tabs, exact columns from `shared/sheets-schema.md`, headers frozen + bold  → **§2** (`populate_sheet.py`)
- [ ] Both Drive folders exist + shared with the SA  → **§2**
- [ ] `.env` has all required vars (Sheet ID, 2 folder IDs, SA path, Discord webhook, n8n base URL)  → filled across **§1–§3**
- [ ] `service-account.json` exists locally, gitignored, not committed  → **§1.6 / §6**
- [ ] n8n Sheets + Drive credentials pass Test  → **§4.2**
- [ ] Discord webhook posts a test message  → **§3** (`verify_foundation.py`)
- [ ] Smoke test runs end-to-end: 4 rows + Discord ping  → **§5**
- [ ] Three n8n workflow JSONs exported to `shared/n8n-templates/`  → **done in repo**
- [ ] `shared/n8n-templates/README.md` explains re-import  → **done in repo**
- [ ] Branch `foundation` merged to `main` after smoke test passes  → **§6**
