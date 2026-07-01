# Pipeline 1 — Loomless AI Personalization

Generates ONE hyper-personalized cold-email first line per lead, at a v1 volume
target of **100 leads/day**. Ingests a scraped-lead CSV, researches each lead
with Perplexity, writes a first line with Claude, and logs every result to the
`Loomless` tab of the OPS-61 CRM Sheet — then pings `#ops-61-feed` with a batch
summary.

> **Automation stops at asset creation + data logging.** No email is ever sent
> by this pipeline (locked plan constraint). Operators send manually after
> reviewing `status=ready_for_review` rows.

---

## How it works

```
Operator drops CSV → Drive: OPS-61/Loomless-Inbox/
        ↓  (n8n Drive-watch trigger, .csv only)
Download + parse CSV → one item per row
        ↓  (batch-size guard: reject > LOOMLESS_BATCH_SIZE)
Per lead:
   1. Perplexity API  → recent, specific research context
   2. Claude API      → one first line (or [NO_CONTEXT])
   3. build row (9 Loomless cols) → Sub_WriteRowToSheet (tab=Loomless)
        ↓
Aggregate summary → Sub_NotifyDiscord (level=info, pipeline=loomless)
        ↓
Move CSV → Loomless-Inbox/processed/
```

Full architecture + decisions: `OPS-61_PLAN.md` → "Pipeline 1". Build contract:
`BUILD_SPEC_2_LOOMLESS.md`. Locked column schema: `shared/sheets-schema.md`.

## How to trigger

- **Normal:** upload a `.csv` to the Drive folder `OPS-61/Loomless-Inbox/`.
  The n8n Drive trigger picks it up automatically.
- **CSV columns (required, exact):** `Company_Name`, `Owner_Full_Name`,
  `First_Name`, `Email`, `Website`. A CSV missing these fails cleanly at the
  parse step (see Failure modes).

## Where the workflow lives

- n8n workflow: **`OPS-61_Loomless_Pipeline`** (dedicated OPS-61 n8n,
  http://localhost:5679).
- Exported JSON: `shared/n8n-templates/OPS-61_Loomless_Pipeline.json`
  *(exported at STEP 10 — not yet present).*
- Reused primitives (do not modify): `Sub_WriteRowToSheet`, `Sub_NotifyDiscord`.

## Prompts (versioned, first-class artifacts)

Prompts live as files, **not** embedded in workflow JSON, so tuning shows up as
clean diffs:

- `prompts/perplexity_research.md` — Perplexity research query template.
- `prompts/claude_first_line.md` — Claude system + user prompt for the first line.

## Test fixtures

- `test-fixtures/sample_leads_10.csv` — 10 leads for prompt iteration.
- `test-fixtures/smoke_test_3.csv` — 3-lead end-to-end smoke test *(added at STEP 6).*

## How to view results

- **Sheet:** `Loomless` tab. Each lead lands as one row with
  `Research_Summary`, `Personalized_First_Line`, and a `status`.
- **Statuses:** `ready_for_review` (usable line, or `[NO_CONTEXT]` sentinel),
  `dead` (a step failed for that lead — batch continues).
- **Verify via API, not the canvas:** run `python shared/scripts/verify_loomless_batch.py`
  to read the last N Loomless rows and report counts by status
  *(helper added at STEP 6).*

## Failure modes

*Documented at STEP 7 (failure-mode tests). Placeholder — behaviors verified:*

- [ ] Bad Perplexity response (malformed) → that lead `status=dead`, batch continues.
- [ ] Claude empty/invalid → that lead `status=dead`, batch continues.
- [ ] CSV exceeds `LOOMLESS_BATCH_SIZE` → `stopAndError`, zero rows, Discord error.
- [ ] CSV missing required columns → clean fail at parse, Discord error, no writes.

## Cost per 100 leads

*Documented at STEP 8 (100-lead dry run). Placeholder: ~$TBD (Perplexity + Claude).*

---

## Build status

- [x] STEP 1 — repo scaffolding (this file + prompts + fixtures)
- [~] STEP 2 — env vars + n8n credential (**Anthropic side done; Perplexity on hold**)
- [ ] STEP 3 — Perplexity research prompt (**BLOCKED on Perplexity API key**)
- [ ] STEP 4 — Claude first-line prompt
- [ ] STEP 5 — build n8n workflow
- [ ] STEP 6 — 3-lead smoke test
- [ ] STEP 7 — failure-mode tests
- [ ] STEP 8 — 100-lead dry run
- [ ] STEP 9 — canvas sticky notes
- [ ] STEP 10 — export + commit + merge
