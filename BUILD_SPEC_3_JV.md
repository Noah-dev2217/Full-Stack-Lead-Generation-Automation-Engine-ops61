# Build Spec #3 — JV Research Bot Pipeline

> **One Claude Code session** (~3-4 hours estimated, longer if row-update pattern surfaces surprises). Second production pipeline. Enriches manually-entered candidate rows in `JV_Targets` tab with audience/offer/contact research via Perplexity.

**Owner:** Rinoah
**Depends on:** Foundation (Build Spec #1) + Loomless (Build Spec #2) — both shipped
**Branch:** `pipeline-2-jv-mock` (branch from `main`)
**Estimated session time:** 3-4 hours

**Reference docs Claude Code must read at session start:**
- `OPS-61_PLAN.md` (v9 — Pipeline 2 is in-scope for this session)
- `BUILD_SPEC_2_LOOMLESS.md` (reference for mock-based dev pattern + acceptance discipline)
- `shared/sheets-schema.md` (JV_Targets locked columns)
- `docs/MIGRATION_NOTE.md` (canonical-source pattern for exports)
- This file

---

## Scope decisions (locked)

**Interpretation:** A2 — enrichment of manually-entered candidates, not discovery-mode search. Operator (Jon / team) manually adds candidate rows with `Name` populated; Pipeline 2 enriches the empty columns.

**Update pattern:** Direct Update Row node inside Pipeline 2. Do NOT create a new `Sub_UpdateRowInSheet` Foundation primitive; promote later if a third pipeline needs the same shape.

**Status trigger:** Empty `status` field means "needs research." Pipeline processes only rows where status is empty. After research: `jv_research_complete` (per schema enum). No schema doc changes needed.

**Trigger architecture:** Google Sheets Trigger (poll `JV_Targets` for empty-status rows) + Manual Trigger (execute now). Both routes converge into shared processing chain.

**Cron / cadence:** Weekly-ish is the target usage pattern, but implementation is a low-frequency Google Sheets Trigger poll (e.g., every 30 minutes or on manual). No separate Schedule Trigger node.

**No Claude API:** JV Bot does research only, no first-line generation. Perplexity is the only external LLM call.

---

## Goal

By session end:

1. New tab-input rows in `JV_Targets` with `Name` populated + empty `status` are picked up by the workflow
2. Each row is enriched via Perplexity research (audience, offers, contact, source URL)
3. The workflow **updates the row in-place** with the research results and sets status to `jv_research_complete`
4. Single-row failures (bad Perplexity response, missing candidate, etc.) tag the row as `dead`; batch continues
5. Discord `#ops-61-feed` receives a batch-summary embed after each poll cycle
6. API-driven n8n tooling built and used throughout (per Q4 decision — invest now, pay off across Pipelines 3, 4, 5 + BS#6 migration)

---

## Out of scope for this session

- Automated outreach (locked — plan constraint, all outreach is manual)
- Discovery-mode: no "Perplexity, find me JV candidates" — that would be A1 interpretation, not A2
- Auto-adding rows to `JV_Targets` from other pipelines
- Enrichment retry logic (dead candidates stay dead — no exponential backoff)
- Rate-limit handling for Perplexity (v1 volume is low enough to not need it; BS#6 concern)

If Claude Code finds itself tempted to build any of the above, stop and commit what's done.

---

## Architecture

```
Operator manually adds row to JV_Targets:
  { Name: "Ash Ambirge", Email: "", ..., status: "" }
                            ↓
              Google Sheets Trigger (poll, 30 min)
                            ↓
              Filter: status IS empty (skip already-processed)
                            ↓
              Batch guard (soft limit — v1 = 20 candidates/poll)
                            ↓
              [per-candidate]
                            ↓
              Mode = live? IF ($env.JV_MODE)
                    ↓                    ↓
              Mock — Perplexity     HTTP — Perplexity (live)
                    ↓                    ↓
                       Merge (append, 2-input)
                            ↓
              Normalize Research (parse JSON, extract fields)
                            ↓
              Guard: research successful? IF
                    ↓                    ↓
              (yes: enriched)      (no: mark dead)
                    ↓                    ↓
                       Merge (rejoin, 2-input)
                            ↓
              Set: Build JV Row (Keep Only Set, only locked cols +
                                 row_id for update lookup)
                            ↓
              Update Row in JV_Targets (by row_id or Name match)
                            ↓
              Aggregate batch results
                            ↓
              Sub_NotifyDiscord (summary)
```

**Key architectural differences from Loomless:**
1. No CSV Drive ingestion (Sheet is the input)
2. No Claude API call (Perplexity only)
3. **Update Row, not Append Row** — this is a new pattern
4. Sheet-Trigger polls instead of Drive-Trigger event
5. No `[NO_CONTEXT]` sentinel needed (research either populates fields or marks dead — no "line-generated but sentinel" case)

---

## New env vars (add to `infra/.env` + `infra/.env.example`)

```
JV_MODE=mock                        # mock | live (defaults to mock, flipped at BS#6)
JV_BATCH_SIZE=20                    # per-poll batch guard (v1 low volume)
JV_POLL_INTERVAL_MINUTES=30         # Google Sheets Trigger poll rate
```

`docker-compose.yml` needs these added to n8n's environment block, same pattern as Loomless's `LOOMLESS_MODE` / `LOOMLESS_BATCH_SIZE` etc.

Restart n8n after adding.

---

## Tasks (in order — each a stop gate)

### STEP 0 — API tooling scaffold (~45 min)

**Per yesterday's Q4 decision, build the tooling BEFORE the workflow.** Every subsequent step benefits.

Build:
- `shared/scripts/n8n_util.py` — client wrapper (auth via `$env.N8N_API_KEY`, list/read/upload/execute methods, `--dry-run` plumbing, **tag-scoped guard: only touch workflows tagged `jv`**)
- `shared/scripts/wire_workflow.py` — replaces `REPLACE_WITH_...` placeholders, wires credentials by name → ID lookup, `--dry-run` shows before/after diff
- `shared/scripts/run_and_verify_jv.py` — trigger workflow execution via API, wait for completion, read execution results, check JV_Targets tab state, report pass/fail

Path B tenancy: scripts REFUSE to touch non-`jv`-tagged workflows. Foundation + Loomless workflows physically protected.

Reuse `n8n_util.py` structure so it's easy to extend for Pipelines 3, 4, 5 (each with their own tag).

**4 dry-run tests before committing:**
- list workflows (should show foundation + loomless + jv when built later)
- read one workflow's definition
- wire_workflow dry-run showing what it would change
- run_and_verify dry-run showing what it would execute

Commit as: `shared/scripts: API-driven n8n tooling scaffold (Path B bounded to jv tag)`

**STOP GATE 0.** Tooling scaffold committed. Dry-runs pass. Do not proceed.

### STEP 1 — Repo scaffolding (~15 min)

- Create branch `pipeline-2-jv-mock` from `main`
- Add:
  - `pipelines/02-jv-research/README.md` — what the pipeline does, how to trigger it manually, how to add candidates
  - `pipelines/02-jv-research/prompts/perplexity_jv_research.md` — v0.1 UNTUNED prompt draft
  - `pipelines/02-jv-research/test-fixtures/mock_jv_candidates.json` — 3-5 mock candidate rows for offline testing

Prompts as versioned files (same discipline as Loomless).

**STOP GATE 1.** Scaffolding confirmed.

### STEP 2 — Env var wiring (~15 min)

- Add `JV_MODE=mock`, `JV_BATCH_SIZE=20`, `JV_POLL_INTERVAL_MINUTES=30` to `infra/.env`
- Add matching placeholders to `infra/.env.example` (git-tracked)
- Add to `infra/docker-compose.yml` under n8n's environment block (mirroring `LOOMLESS_*` pattern)
- Recreate n8n container: `docker compose -f infra/docker-compose.yml up -d`
- **Verify inside container** via throwaway Code node (masked output pattern):
  ```javascript
  return [{ json: {
    jv_mode: $env.JV_MODE,
    jv_batch_size: $env.JV_BATCH_SIZE,
    jv_poll: $env.JV_POLL_INTERVAL_MINUTES,
  }}];
  ```
- Expected: `mock`, `20`, `30`
- Delete throwaway workflow after

**STOP GATE 2.** Env vars resolve inside container.

### STEP 3 — Perplexity JV prompt (~30 min drafting; UNTUNED per Decision #12)

Write `pipelines/02-jv-research/prompts/perplexity_jv_research.md`.

**Goal:** Given a candidate name (+ optional email/social), return structured JSON with:
- `audience_summary` (size + character — e.g., "40k email list, majority female entrepreneurs in coaching")
- `current_offers` (their products/programs — "Signature Course: $3k coaching cohort, monthly workshop")
- `email` (if publicly findable)
- `social_links` (LinkedIn, Twitter, Instagram, YouTube — comma-separated or JSON array)
- `source_url` (where Perplexity found the primary info)
- `confidence` (high | medium | low)

Output shape (JSON):
```json
{
  "audience_summary": "40k email list, majority ...",
  "current_offers": "Course: XYZ, Community: ...",
  "email": "hello@example.com",
  "social_links": "https://twitter.com/x, https://linkedin.com/in/y",
  "source_url": "https://example.com/about",
  "confidence": "high"
}
```

`confidence: low` → status becomes `dead` in the workflow (not enough info to be useful for JV outreach).

**Do NOT iterate the prompt against real Perplexity calls** (Decision #12 — tuning happens at BS#6).

**Commit as:** `jv: draft perplexity_jv_research.md v0.1 (UNTUNED)`

**STOP GATE 3.** Prompt draft committed. Do not proceed.

### STEP 4 — Mock scenarios in the workflow's Code node (~30 min)

Design mock Perplexity responses for deterministic testing. Match the response shape of the real Perplexity API. Include scenarios:

- `normal` — high-confidence, all fields populated
- `partial` — medium-confidence, some fields empty (test the enrichment tolerance)
- `no_context` — low-confidence, empty fields, will trigger `dead` status
- `bad_json` — mock returns malformed JSON (test Normalize node error handling)

Same deterministic scenario detection as Loomless: key off `Name` field or optional `_mock_scenario` column in the test fixture.

**STOP GATE 4.** Mock scenarios drafted, embedded in workflow-to-be.

### STEP 5 — Build the n8n workflow (~90 min)

Create workflow `OPS-61_JV_Research_Pipeline`. Tags: `jv`, `ops-61`.

**Nodes (rough order):**

1. **Google Sheets Trigger** — polls `JV_Targets` tab every `JV_POLL_INTERVAL_MINUTES`, watches for new/modified rows
   - Fires only on rows where `status` is empty
   - Credential: `Google Sheets — OPS-61 SA`
2. **Manual Trigger** — parallel entry for dev/manual runs
3. **DEV: Fake JV Payload** (Code node) — for smoke tests without polling real sheet
   - `FIXTURE = 'smoke_jv_3'` default
   - Fixtures embedded verbatim from `test-fixtures/mock_jv_candidates.json`
4. **Filter** — status IS empty (guard against re-processing)
5. **Batch guard** — `rows.length <= JV_BATCH_SIZE`, else fail loud
6. **Fail-closed dev-Sheet guard** — `LOOMLESS_DEV_SHEET_ID == GOOGLE_SHEET_ID` (reuse Loomless's env for now; simpler than new JV_DEV_SHEET_ID env)
7. **Per-candidate flow:**
   a. **Mode = live? IF** ($env.JV_MODE)
      - `true` → HTTP Request node (Perplexity live)
      - `false` → Mock — Perplexity (Code node with scenario fixtures)
   b. **Merge — Perplexity paths** (2-input append)
   c. **Normalize Research** — parse JSON, extract fields, on parse-fail: `_status=dead`
   d. **Guard: research OK? IF**
      - true (confidence high/medium, fields populated) → continue
      - false (confidence low OR _status=dead) → skip to Set — dead
   e. **Set: Build JV Row** (Code node, Keep Only Set)
      - Emits only the 8 JV_Targets locked columns
      - `[MOCK]` prefix on `Audience_Summary` and `Current_Offers` when in mock mode (skip on `dead` rows — no useful data to prefix)
      - Preserves `row_id` OR `Name` for the Update Row lookup (separate from the emitted row payload)
   f. **Update Row in JV_Targets** (Google Sheets Update Row node)
      - Match by row_id (preferred) or by unique `Name` (fallback)
      - Updates: Audience_Summary, Current_Offers, Email, Social_Links, Source_URL, status
      - Does NOT touch: Name (unchanged), created_at (unchanged)
      - Credential: Google Sheets — OPS-61 SA
      - Continue-on-Fail: ON
   g. **Merge — rejoin lead paths** (2-input append, tolerates 0-vs-N split — proven in Loomless Smoke 2)
8. **Aggregate results** — count total, enriched, dead
9. **Sub_NotifyDiscord** (batch summary)

**Design constraints:**

- **Update Row lookup: use `row_id` if the trigger provides it, else fallback to `Name` match.** `Name` should be unique per JV candidate; if it isn't, that's an operator error and the workflow should tag those candidates as `dead` with a diagnostic message.
- **Continue-on-Fail on Update Row.** A single failed update doesn't kill the batch.
- **Do NOT modify Sub_WriteRowToSheet or Sub_NotifyDiscord.** Foundation primitives are read-only for this session (Path B tenancy).
- **The row_id extraction is fragile — flag as a smoke-test priority.** Google Sheets Trigger's output shape may or may not include a stable row identifier. If it doesn't, we lookup by Name. Verify empirically.

**STOP GATE 5.** Workflow built, saved, no red nodes. Do NOT execute end-to-end.

### STEP 6 — Smoke tests (~45 min)

**Smoke 1 — Mixed batch:**
Test fixture: 3 candidates (`normal`, `partial`, `no_context`).
Expected:
- 2 rows updated with research (normal + partial)
- 1 row marked `dead` (no_context)
- Discord: "3 rows — 2 jv_research_complete, 1 dead [mode=mock]"

**Smoke 2 — Update Row pattern isolation test:**
Test fixture: 1 candidate (`normal`).
Verify:
- The row is updated IN PLACE (not appended as a new row)
- `Name` and `created_at` are unchanged
- All other columns populated
- `Sub_WriteRowToSheet`'s Loomless tab is untouched (write went to JV_Targets only)
- No orphan rows appear anywhere

**Smoke 3 — All-dead batch:**
Test fixture: 3 candidates, all `no_context`.
Verify:
- All 3 rows marked `dead` in JV_Targets
- Rejoin Merge handles 3-vs-0 split (proven in Loomless Smoke 2)
- Discord: "3 rows — 0 jv_research_complete, 3 dead"

Verify each smoke via API (build `verify_jv_batch.py` similar to `verify_loomless_batch.py`).

**STOP GATE 6.** All 3 smokes pass.

### STEP 7 — Failure modes (~30 min)

Test A: Bad Perplexity response (bad_json scenario) → row marked `dead`, batch continues, Discord notes the failure.

Test B: Batch size guard — CSV/fixture with `JV_BATCH_SIZE + 1` rows → Discord level=error, zero updates.

Test C: Update Row failure — deliberately break the row_id lookup for one candidate, verify Continue-on-Fail wraps the error and batch completes.

Test D: Empty batch — no empty-status rows in JV_Targets → workflow exits cleanly, no Discord noise (or "no candidates to process" if we want a heartbeat).

**STOP GATE 7.** All 4 failure modes correctly handled.

### STEP 8 — Reconcile + commit + merge (~30 min)

Follow the Loomless STEP 8 pattern:
1. Reset DEV node to canonical (only `smoke_jv_3` fixture, `FIXTURE = 'smoke_jv_3'`)
2. Sticky note review (Validated sticky for STEP 6-7 results, throughput note, canonical-source reminder)
3. Save workflow in n8n
4. Export via n8n UI → overwrite `shared/n8n-templates/OPS-61_JV_Research_Pipeline.json`
5. Anchored grep inspection (no dev fixtures leaked)
6. Secret sweep (no keys in git)
7. Single reconcile commit
8. Merge `pipeline-2-jv-mock` → `main` with `--no-ff`
9. Push both branches
10. Update `docs/NEXT_SESSION.md` to reflect Pipeline 3 as next

**STOP GATE 8 (final).** Pipeline 2 shipped.

---

## Acceptance criteria (must all be true before merge)

- [ ] Branch `pipeline-2-jv-mock` merged to `main` with `--no-ff`
- [ ] `pipelines/02-jv-research/` populated (README, prompt, test fixtures)
- [ ] `OPS-61_JV_Research_Pipeline.json` exported to `shared/n8n-templates/`
- [ ] `verify_jv_batch.py` script exists and validates JV_Targets writes
- [ ] `n8n_util.py` + `wire_workflow.py` + `run_and_verify_jv.py` shipped as API tooling scaffold (Path B bounded to `jv` tag)
- [ ] Env vars (`JV_MODE`, `JV_BATCH_SIZE`, `JV_POLL_INTERVAL_MINUTES`) wired in `.env`, `.env.example`, `docker-compose.yml`
- [ ] Perplexity prompt v0.1 committed, marked UNTUNED
- [ ] Smoke 1 (mixed batch) passes: 2 enriched + 1 dead
- [ ] Smoke 2 (Update Row isolation) passes: row updated in-place, Name/created_at unchanged, Loomless tab untouched
- [ ] Smoke 3 (all-dead batch) passes: 3 dead, Merge tolerates the split
- [ ] 4 failure modes tested and documented
- [ ] Sticky note documentation on canvas covers scope, mock/live toggle, update-row pattern, validation summary
- [ ] Both Sub_WriteRowToSheet and Sub_NotifyDiscord unmodified (Foundation intact)
- [ ] No secrets in git (`git ls-files | Select-String key|secret|\.env$|service-account` returns only `.env.example`)

---

## Guardrails for the Claude Code session

**DO:**
- Read all reference docs first
- Build API tooling scaffold at STEP 0 (per Q4 decision)
- Use tooling (`wire_workflow.py`, `run_and_verify_jv.py`) for the rest of the session — don't fall back to UI clicks unless tooling can't do the operation
- Verify writes via API/Sheet, not just canvas
- Sticky-note-document the Update Row pattern for future readers
- Treat prompts as versioned files (Loomless discipline)
- Ask before making choices not covered here

**DO NOT:**
- Modify Sub_WriteRowToSheet or Sub_NotifyDiscord (Foundation primitives locked)
- Create a `Sub_UpdateRowInSheet` Foundation primitive (Option B locked — direct node in Pipeline 2)
- Add discovery-mode / search-driven candidate finding (out of scope — A2 locked)
- Iterate the Perplexity prompt against live API (Decision #12 — tuning at BS#6)
- Skip failure-mode tests to save time
- Merge without all acceptance criteria checked

---

## Handoff to Build Spec #4 (FB Group Router)

After Pipeline 2 ships:
- `n8n_util.py` + `wire_workflow.py` scaffold proven, reusable for Pipelines 3-5
- Update Row pattern proven — if FB Router (or Terminator Loom) needs it, promote to `Sub_UpdateRowInSheet` primitive at that time
- API-tooling-driven build workflow proven end-to-end
- Perplexity integration reused a second time, cost baseline more informed

Build Spec #4 (FB Group Router) draft comes after this session's merge.

---

## Session prompt for Claude Code

```
Resuming OPS-61 work — starting Pipeline 2 (JV Research Bot,
Build Spec #3, mock-based per Decision #12).

Read these docs in order:
1. OPS-61_PLAN.md (v9)
2. BUILD_SPEC_2_LOOMLESS.md (reference for mock-based pattern +
   acceptance discipline)
3. BUILD_SPEC_3_JV.md (this session's spec — read carefully)
4. shared/sheets-schema.md (JV_Targets locked columns)
5. docs/MIGRATION_NOTE.md (canonical-source pattern for exports)
6. MEMORY.md (session context from Loomless)

Confirm you've read all six.

═══════════════════════════════════════════════════════════════
STATE AS OF SESSION RESUME:
═══════════════════════════════════════════════════════════════

FOUNDATION: HEALTHY, verified.
LOOMLESS: SHIPPED (merge commit fa63f00, pushed).
JV BOT: NOT STARTED — this session builds it.

BRANCH: main (clean). This session creates
pipeline-2-jv-mock branch from main.

API KEY: N8N_API_KEY present in infra/.env, ready for tooling
build.

SCOPE DECISIONS (locked, do not re-litigate):
- Interpretation A2 (enrichment, not discovery)
- Update pattern: direct Update Row node (Option B, no new
  Foundation primitive)
- Status: empty means "needs research"; jv_research_complete
  when done; dead when Perplexity confidence is low
- Trigger: Google Sheets Trigger (poll) + Manual Trigger
- API tooling built FIRST (STEP 0), used throughout

═══════════════════════════════════════════════════════════════
SESSION GOAL:
═══════════════════════════════════════════════════════════════

Ship Pipeline 2 (JV Research Bot) end-to-end per BUILD_SPEC_3_JV.md
acceptance criteria. Merge to main.

Estimated time: 3-4 hours. Longer if Update Row pattern surfaces
surprises (untested territory in this project).

═══════════════════════════════════════════════════════════════
SEQUENCE:
═══════════════════════════════════════════════════════════════

STEP 0 — API tooling scaffold (Path B, bounded to `jv` tag)
STEP 1 — Repo scaffolding
STEP 2 — Env var wiring
STEP 3 — Perplexity JV prompt (UNTUNED v0.1)
STEP 4 — Mock scenarios embedded in workflow
STEP 5 — Build the n8n workflow (Update Row pattern is new — test
         the Update Row node in isolation BEFORE wiring into main flow)
STEP 6 — 3 smoke tests (mixed / update-row isolation / all-dead)
STEP 7 — 4 failure modes
STEP 8 — Reconcile + commit + merge (Loomless STEP 8 pattern)

Stop-gate at each STEP. Reviewer approves before proceeding.

═══════════════════════════════════════════════════════════════
RULES OF ENGAGEMENT:
═══════════════════════════════════════════════════════════════

- Never print credentials or API keys
- Verify via API (Sheets + n8n execution history), not canvas
- Sub_WriteRowToSheet and Sub_NotifyDiscord are read-only
  (Foundation intact)
- Use API tooling for workflow ops from STEP 5 onward (dry-run
  before every write)
- Path B tenancy: tooling refuses to touch non-`jv`-tagged
  workflows
- If Update Row pattern surfaces an unexpected n8n quirk,
  stop and diagnose — don't paper over
- Reviewer (Rinoah's pastes) approves fix proposals

Start with STEP 0. Report:
1. git status + git log --oneline -5 + docker ps
2. Branch: create pipeline-2-jv-mock from main
3. First tool scaffold file to write (n8n_util.py)
4. Wait for reviewer approval before writing any code
```

---

## References

- Loomless build spec: `BUILD_SPEC_2_LOOMLESS.md`
- Loomless learnings preserved: sticky notes on `OPS-61_Loomless_Pipeline` + MEMORY.md
- Canonical source pattern: `docs/MIGRATION_NOTE.md`
- Foundation primitives: `Sub_WriteRowToSheet` (id: DqGdbRqflR4c03xR), `Sub_NotifyDiscord` (id: hBlQP46p1R8vZyvy)
