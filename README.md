# OPS-61 — Full-Stack Lead Generation & Automation Engine

> Internal automation suite for FascinateCopy, implementing the EasyGrow client acquisition methodology. Four independent pipelines feeding one shared Google Sheets CRM.

**Owner:** Rinoah Venedict B. Dela Rama
**Direction:** Jon
**Linear:** OPS-61
**Due:** Jul 3
**Status:** Planning complete (v6), build in progress

---

## Core constraint

**Automation stops at asset creation and data logging.** No automated email sending. No automated DMs. Operators manually send everything that touches an account. This protects deliverability and account health.

---

## Pipeline status

| # | Pipeline | Status | Spec |
|---|---|---|---|
| 0 | Spike — auto-tab-select validation | ✅ Done | `spike/` |
| 1 | Foundation — Sheets + n8n base | ⏳ Pending Build Spec | — |
| 2 | Loomless AI Pipeline | ⏳ Pending Build Spec | — |
| 3 | JV Research Bot | ⏳ Pending Build Spec | — |
| 4 | FB Group CRM Router | ⏳ Pending Build Spec | — |
| 5 | Terminator Loom Auto-Recorder | ⏳ Pending Build Spec | — |

---

## Directory structure

```
ops-61/
├── README.md                       ← you are here
├── OPS-61_PLAN.md                  ← master plan (v6, locked)
├── .gitignore
├── .env.example                    ← env var template (copy to .env, never commit)
│
├── docs/
│   ├── EASYGROW_SPEC.md            ← source spec from Jon
│   └── SPIKE_RESULTS.md            ← auto-tab-select validation findings
│
├── shared/
│   ├── sheets-schema.md            ← canonical 4-tab Sheet schema
│   └── n8n-templates/              ← shared n8n subworkflows
│
├── pipelines/
│   ├── 01-loomless/                ← Loomless AI personalization (n8n)
│   ├── 02-jv-research/             ← JV Research Bot (n8n)
│   ├── 03-terminator-loom/         ← Auto-Recorder (Python + Playwright + FFmpeg)
│   └── 04-fb-router/               ← FB Group capture (Chrome extension + n8n)
│
└── spike/                          ← auto-tab-select validation (kept as smoke test)
    ├── README.md
    ├── spike.py
    ├── prospect_test.html
    ├── requirements.txt
    └── screenflow/                 ← bundled internal ScreenFlow recorder
```

---

## Quick links

- **Master plan:** [`OPS-61_PLAN.md`](./OPS-61_PLAN.md)
- **Source spec:** [`docs/EASYGROW_SPEC.md`](./docs/EASYGROW_SPEC.md)
- **Sheets schema:** [`shared/sheets-schema.md`](./shared/sheets-schema.md)
- **Spike findings:** [`docs/SPIKE_RESULTS.md`](./docs/SPIKE_RESULTS.md)
- **NotebookLM context:** https://notebooklm.google.com/notebook/b80416ff-1023-4b63-9fda-033032bac504 (`jonc@fascinatecopy.com`)

---

## Build approach

Each pipeline is built in its own focused Claude Code session. Don't one-shot all four. Open a session, point it at `OPS-61_PLAN.md` + the specific pipeline's build spec, build → test → commit.

Build order (locked in plan, decision #1–11 all resolved):

1. Foundation (Sheets + n8n base + Discord webhook + Service Account)
2. Loomless pipeline
3. JV Research Bot
4. FB Group Chrome extension + webhook
5. Terminator Loom recorder

---

## v0 setup tasks (Jon, parallel to dev)

These don't block dev *start* — placeholders work for build. They block Pipeline 3 acceptance testing and Pipeline 4 live data.

1. Record master MP3 pitch (1–2 min, EasyGrow framework)
2. Provide professional headshot for profile pic overlay (1024x1024 PNG)
3. (Optional) Animated GIF variant for video preview boost
4. Configure FB Group Q3 to: *"Would you like me to reach out to discuss how we may be able to help you with that?"* (Option A — DM permission)

---

## Local dev setup

Each pipeline has its own setup in its directory. For the foundation (and to smoke-test the repo):

```bash
# Clone
git clone git@github.com:Noah-dev2217/ops-61.git
cd ops-61

# Copy env template
cp .env.example .env
# Edit .env with real credentials

# Run the spike to verify ScreenFlow + Playwright still works
cd spike
pip install -r requirements.txt
playwright install chromium
python spike.py
```

---

## Conventions

- **No secrets in repo.** Everything sensitive in `.env`, gitignored.
- **No vendored binaries.** Master MP3, profile pic, recordings stay in Drive or `assets/` (gitignored).
- **Per-pipeline `README.md`** with run instructions and acceptance criteria.
- **Per-pipeline `requirements.txt`** or `package.json` (Python pipelines isolated).
- **n8n workflows** exported as JSON to `shared/n8n-templates/` for version control.
- **Pre-commit hook** (added in Foundation step) runs basic linting + checks for accidentally-committed `.env`.
