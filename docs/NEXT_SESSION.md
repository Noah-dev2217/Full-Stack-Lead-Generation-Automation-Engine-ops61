# OPS-61 — Next Session Opening Prompt (Pipeline 2: JV Research Bot)

> Paste the block below to open the next session. Loomless (Pipeline 1) is DONE
> and merged to `main` (`fa63f00`) — do NOT touch it. Saved 2026-07-05.

---

Resuming OPS-61. Pipeline 1 (Loomless) shipped last session; tonight we start
Pipeline 2 (JV Research Bot). Read these docs in order before doing anything:

1. OPS-61_PLAN.md (Pipeline 2 section + Build order — Loomless now marked DONE)
2. shared/sheets-schema.md (the `JV_Targets` tab is the write target)
3. docs/MIGRATION_NOTE.md (canonical-source model + BS#6 re-wire list — applies
   to every pipeline's STEP 8)
4. MEMORY.md (has Loomless completion state + working style)
5. shared/n8n-templates/OPS-61_Loomless_Pipeline.json (REFERENCE — reuse its
   Perplexity dual-path mock/live pattern; JV reuses the Perplexity integration)

Confirm you've read all five before proceeding.

═══════════════════════════════════════════════════════════════
STATE AS OF SESSION START:
═══════════════════════════════════════════════════════════════

- Pipeline 1 (Loomless): DONE, merged to main `fa63f00`, pushed. UNTOUCHED this
  session.
- Foundation (Sub_WriteRowToSheet, Sub_NotifyDiscord): healthy, used as-is.
- Branch: create `pipeline-2-jv-mock` off `main`.
- Mock-first still in force (Decision #12): build JV on mocked Perplexity, real
  creds + prompt tuning deferred to BS#6.
- Canonical workflow source = n8n UI export (per last session's decision); the
  schema-driven builder is a REFERENCE snapshot only (rename to
  snapshot_*_from_schema.py + snapshot_diff tooling still queued as "Commit 2").
- n8n: ops61-n8n on :5679 (isolated from OPS-52 n8n on :5678). API key present
  in infra/.env if REST tooling is worth building.

═══════════════════════════════════════════════════════════════
SESSION GOAL:
═══════════════════════════════════════════════════════════════

Draft + review Build Spec #3 (JV Research Bot) — mock-based, mirroring the
Loomless spec structure. JV specifics from the plan: weekly cron + manual
webhook trigger; multi-angle Perplexity search (podcast hosts, newsletter
writers, course creators, community builders); extract Name/Email/Social/
audience/offers; dedupe against JV_Targets by domain+name; write status=
jv_research_complete; Discord summary. Then (separate session) build it.

Do NOT one-shot the build — spec/review first, then a dedicated build session,
same as Loomless.

═══════════════════════════════════════════════════════════════
STEP 0 — Environment check (before any work):
═══════════════════════════════════════════════════════════════

- git status (expect clean on main)
- git log --oneline -5 (top should be the Loomless merge fa63f00 + any
  end-of-day housekeeping commit)
- docker ps (ops61-n8n :5679 + OPS-52 n8n :5678 both up)
- git checkout -b pipeline-2-jv-mock   (branch off main)

Stop gate. Confirm before proceeding.

═══════════════════════════════════════════════════════════════
RULES OF ENGAGEMENT (same as the Loomless session — they worked):
═══════════════════════════════════════════════════════════════

- Never print credentials / API keys / secret values.
- Verify via API (Sheets, n8n execution history), NOT just the canvas.
- Stop at each gate; wait for reviewer approval before proceeding.
- Use Sub_WriteRowToSheet + Sub_NotifyDiscord as-is; do NOT modify Foundation.
- Mock-first: no real Perplexity calls in dev; prompts stay UNTUNED (BS#6).
- --dry-run before any tool-driven write; if building REST tooling, keep it
  tag-bounded (Path B tenancy).
- When editing n8n stickies/nodes for STEP 8, remember: n8n UI is canonical →
  edit in UI + export (don't hand-patch the JSON); the schema builder does NOT
  capture UI edits.
- n8n UI export ≈ ~100KB here (not 140–180KB) — don't over-budget size.
- Track my energy; if I'm making mistakes or tired, say so and suggest stopping.
- LOOMLESS IS DONE — this session does not need to touch Pipeline 1.
