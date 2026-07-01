# Build Spec #2 — Loomless AI Personalization Pipeline

> **One Claude Code session** (possibly two if prompt tuning stretches). Builds the first revenue-generating pipeline: ingest cold lead CSVs, research each lead via Perplexity, generate hyper-personalized first lines via Claude, write results to the Sheet.

**Owner:** Rinoah
**Depends on:** Build Spec #1 (Foundation) — complete
**Branch:** `pipeline-1-loomless` (branch from `main`)
**Estimated session time:** 6–8 hours (prompt engineering iteration is the wildcard)
**Reference docs Claude Code must read at session start:**
- `OPS-61_PLAN.md` (architecture context)
- `docs/EASYGROW_SPEC.md` (source spec + copywriting rules)
- `shared/sheets-schema.md` (Loomless tab columns are locked)
- This file (`BUILD_SPEC_2_LOOMLESS.md`)

---

## Goal

By session end, the pipeline can:

1. Watch a designated Google Drive folder (`OPS-61/Loomless-Inbox/`) for new CSV uploads
2. Parse each row (Company_Name, Owner_Full_Name, First_Name, Email, Website)
3. For each lead, call Perplexity API to fetch recent context (LinkedIn posts, achievements, company news, hiring signals)
4. Pass research + lead data to Claude API to generate ONE hyper-personalized first line following EasyGrow copywriting rules
5. Write the row to the `Loomless` tab via `Sub_WriteRowToSheet` with `status=ready_for_review`
6. When a batch completes, ping `#ops-61-feed` via `Sub_NotifyDiscord` with a summary
7. Handle failures gracefully — a single bad lead doesn't kill a 100-lead batch

Volume target v1: 100 leads/day. Scale to 400/day is v2 concern, not this spec.

---

## Out of scope for this session

- Automated email send (locked — plan constraint)
- Follow-up sequences, second lines, or full-body copy (v1 = first line only)
- Auditor/QA agent reviewing first-line quality (Decision #5 — OFF for v1)
- Multiple first-line variants per lead (Decision #7-ish — one variant, operator picks at send time)
- CSV validation UI (operator sees errors in Discord + Sheet only)
- JV research, FB Group capture, video recording (later specs)
- Prod deployment to company server (Build Spec #6)

If Claude Code finds itself tempted to build any of the above, stop and commit what's done.

---

## Architecture

```
Operator drops CSV → OPS-61/Loomless-Inbox/
                            ↓
                    n8n Drive-watch trigger
                            ↓
                    Read CSV rows (batch of N)
                            ↓
             ┌──────────────┴──────────────┐
             │  Per-row (loop or split):    │
             │    1. Perplexity API call    │
             │    2. Claude API call        │
             │    3. Validate + build row   │
             │    4. Sub_WriteRowToSheet    │
             │       tab=Loomless           │
             └──────────────┬──────────────┘
                            ↓
                    Aggregate batch summary
                            ↓
                    Sub_NotifyDiscord
                    (level=info, pipeline=loomless)
                            ↓
                    Move CSV to /processed/ subfolder
                    (or tag as done — Claude Code chooses)
```

## New env vars (add to `infra/.env` + `infra/.env.example`)

```
ANTHROPIC_API_KEY=<Claude Max API key>
PERPLEXITY_API_KEY=<Perplexity Pro API key>
LOOMLESS_BATCH_SIZE=100
LOOMLESS_DAILY_CAP=100
```

Batch size + daily cap are safety valves — prevent a runaway CSV with 5000 rows from silently burning quota.

`infra/docker-compose.yml` also needs the two new API keys added to the `environment:` block, mirroring the pattern established in Foundation. Then restart n8n.

---

## Tasks (in order — each is a stop gate)

### 1. Repo scaffolding (~20 min)

Create branch `pipeline-1-loomless` from `main`.

Add:
- `pipelines/01-loomless/README.md` (replace the placeholder) — describes what the pipeline does, how to trigger it, where the workflow lives, how to view results
- `pipelines/01-loomless/prompts/perplexity_research.md` — the Perplexity query template, versioned
- `pipelines/01-loomless/prompts/claude_first_line.md` — the Claude system + user prompt, versioned
- `pipelines/01-loomless/test-fixtures/sample_leads_10.csv` — 10 realistic test leads for iteration (fake names + real-ish companies for Perplexity to research)

Prompts as separate files (not embedded in workflow JSON) is intentional — they'll be tuned frequently, and diffs should show prompt changes cleanly.

**STOP GATE 1.** Confirm scaffolding, then move on.

### 2. Env vars + n8n credential (~15 min)

- Add `ANTHROPIC_API_KEY` and `PERPLEXITY_API_KEY` to `infra/.env` (Claude Code doesn't see the values — Rinoah pastes them)
- Add to `infra/.env.example` with empty values + comments
- Add to `infra/docker-compose.yml` under n8n's `environment:` block using `${...}` pattern (mirrors GOOGLE_SHEET_ID style)
- Restart n8n: `docker compose up -d n8n` from `infra/`
- Verify with throwaway Code node: `$env.ANTHROPIC_API_KEY` and `$env.PERPLEXITY_API_KEY` both resolve (mask the values in output — print first 8 chars + length only, same pattern as the Discord webhook check)
- In n8n → Credentials → create `Anthropic account` credential using `$env.ANTHROPIC_API_KEY`
- Perplexity uses HTTP Request node directly (no dedicated credential needed) — reads `$env.PERPLEXITY_API_KEY` in the Authorization header

**STOP GATE 2.** Both env vars resolve, Anthropic credential test passes. Do not proceed until confirmed.

### 3. Perplexity research prompt (~45 min — iterate)

Write `pipelines/01-loomless/prompts/perplexity_research.md`.

**Goal:** Given a lead's name + company + website, return a concise research summary containing recent, specific, human-interest facts usable in a personalized first line.

**What to look for (EasyGrow spec):**
- Recent LinkedIn posts (last 30-60 days)
- Podcast appearances or media mentions
- Company news (funding, launches, hiring)
- Personal context (location, recent achievements, milestones)
- Anything specific enough that a first line referencing it would sound "you actually looked at me" rather than "you scraped my domain"

**What NOT to return:**
- Generic company descriptions
- LinkedIn bio boilerplate ("passionate about", "helping businesses grow")
- Anything that sounds like it came from an About page
- Speculation

**Output format:** a JSON object with:
```json
{
  "research_summary": "2-3 sentences of the most useful specific context found",
  "confidence": "high | medium | low",
  "source_hints": ["brief note on where the info came from"]
}
```

`confidence=low` means Perplexity couldn't find anything specific. The pipeline will translate low confidence to `Personalized_First_Line = [NO_CONTEXT]` (per plan) so operators know to skip that lead.

**Iterate against `test-fixtures/sample_leads_10.csv`** — run the Perplexity query on 10 sample leads, eyeball the outputs, tune the prompt until at least 7 of 10 return high-confidence usable context. Document the final prompt version + rationale.

**STOP GATE 3.** Perplexity prompt returns usable output for ≥7/10 test leads. Prompt committed.

### 4. Claude first-line prompt (~60 min — iterate)

Write `pipelines/01-loomless/prompts/claude_first_line.md`.

**Model:** `claude-sonnet-4-6` (fast enough for batches, high enough quality for copy work; can escalate to Opus if v1 output isn't good enough).

**Prompt structure:**

System prompt:
- Role: expert cold email copywriter following the "Loomless" methodology from EasyGrow
- Rules:
  - Write ONE first line only
  - Must sound human, casual, and highly relevant to the specific research context
  - NOT marketing-speak, NOT boilerplate, NOT flattery
  - One sentence, conversational tone
  - Reference the specific context (e.g. a specific post, achievement, or event)
  - Under 30 words
- Examples (from EasyGrow spec):
  - "Saw you recently posted about your 40% close rate in December. Congrats!"
  - "Noticed on LinkedIn you're based in Ottawa. If we connect, I'd be happy to buy you lunch at Riviera!"
- Failure mode: if research_summary lacks specific context, respond with the literal string `[NO_CONTEXT]`

User prompt:
- Lead's first name
- Company name
- Research summary from Perplexity

**Iterate against the same 10 sample leads.** Run Perplexity → Claude end-to-end. Eyeball outputs. Target: ≥8/10 first lines are ones you'd actually send.

Failure modes to hunt for:
- Generic openings ("Hope you're well!") — reject
- Over-familiar tone that assumes context that isn't there — reject
- Reference to research context but in stilted phrasing — reject
- Exact phrase from Perplexity output quoted verbatim — bad, needs paraphrasing
- Multiple sentences — reject, must be one sentence

Document the final prompt + rationale + 10 sample outputs as evidence.

**STOP GATE 4.** Claude prompt produces sendable first lines for ≥8/10 test leads. Committed.

### 5. Build the n8n workflow (~90 min)

Create workflow `OPS-61_Loomless_Pipeline`.

**Nodes (rough order):**

1. **Google Drive Trigger** — watch `OPS-61/Loomless-Inbox/`, trigger on new file created, filter to `.csv` only
2. **Google Drive: Download File** — get the CSV content
3. **Extract from File** — parse CSV → items (one per row)
4. **Batch size guard** — Code node checks `items.length <= LOOMLESS_BATCH_SIZE`; if exceeded, throw a clear error via `stopAndError`
5. **Split In Batches** — process in configurable chunks (start with 10, tune later based on rate limits)
6. **Per-item flow:**
   a. **HTTP Request → Perplexity API** — send query with lead's name/company/website
   b. **Set (data preparation)** — normalize Perplexity response, extract `research_summary` + `confidence`
   c. **IF confidence low** → set `Personalized_First_Line = "[NO_CONTEXT]"`, skip Claude call
   d. **ELSE** → **HTTP Request → Claude API** (or Anthropic node) with the first-line prompt
   e. **Set (build row)** — construct the Sheet row per locked schema (9 cols for Loomless)
   f. **Execute Sub-workflow → Sub_WriteRowToSheet** with `{ tab: "Loomless", row: {...} }`
   g. **Error handling** — if any step fails, log the error, tag row as `status="dead"`, continue to next lead
7. **Aggregate results** — Code node summarizes: total processed, successes, [NO_CONTEXT] count, failures
8. **Execute Sub-workflow → Sub_NotifyDiscord** with batch summary
9. **Move processed CSV** — Google Drive node moves the CSV from `Loomless-Inbox/` to `Loomless-Inbox/processed/` (create folder if missing)

**Design constraints (worth stating explicitly):**

- **Single-lead failure must NOT abort the batch.** Wrap each per-item flow in try/catch (n8n's "Continue on Fail" toggle on each risky node)
- **Every lead MUST result in a row in the Sheet**, even failures. `status` distinguishes (`ready_for_review` vs `dead` vs `[NO_CONTEXT]`)
- **Rate limits:** Perplexity Pro allows ~20 req/min, Anthropic tier depends on account. Split In Batches with a small delay between chunks (start with 3s between batches of 10)
- **Idempotency:** if the workflow crashes mid-batch, re-running the same CSV should not double-write. Simplest solution: the CSV filename is tracked; already-processed CSVs get moved to `/processed/` first as a lock. If that's brittle, add a "Skip if row exists" check (query Sheet for Email match before write).
- **Don't call Sub_WriteRowToSheet with the `tab` field inside `row`** — the sub-workflow's schema validation will treat `tab` as a data field and reject the row. `tab` goes at the top level of the sub's input; only actual Sheet columns go in `row`.

**STOP GATE 5.** Workflow saved, all nodes green (or intentionally awaiting-input yellow), no red flags. Do NOT execute yet.

### 6. Smoke test with 3-lead CSV (~30 min)

Create `pipelines/01-loomless/test-fixtures/smoke_test_3.csv` — 3 leads (2 with real Perplexity-findable context, 1 with intentionally sparse context).

Manually upload to `Loomless-Inbox/`. Workflow should trigger.

Verify:
- All 3 rows appear in the `Loomless` Sheet tab
- 2 have populated `Research_Summary` + `Personalized_First_Line`, `status=ready_for_review`
- 1 has `Personalized_First_Line=[NO_CONTEXT]`, `status=ready_for_review`
- Discord embed appears in `#ops-61-feed` with summary
- CSV moved to `Loomless-Inbox/processed/`

**Verify Sheet content via Sheets API, not just canvas** — same discipline as Foundation. Claude Code writes a `verify_loomless_batch.py` helper that reads the last N rows of the Loomless tab and reports counts by status. This becomes the acceptance-test tool.

**STOP GATE 6.** Smoke test passes end-to-end, verified via API. Do not proceed until confirmed.

### 7. Failure-mode tests (~30 min)

Same discipline as Foundation's Unknown Tab test. Deliberately break things and confirm behavior is loud + safe.

**Test A — Bad Perplexity response** (malformed JSON from Perplexity):
- Temporarily change the Perplexity prompt to instruct "return XML" instead of JSON
- Run 1-lead CSV
- Expected: that lead gets `status=dead`, error logged, other leads in batch (if any) unaffected, Discord ping mentions the failure

**Test B — Claude API returning empty string or invalid format:**
- Force by using a very restrictive prompt or mocking
- Expected: same — `status=dead`, batch continues

**Test C — CSV exceeds batch size guard:**
- Upload 101-lead CSV
- Expected: workflow errors out with clear message via `stopAndError`, zero rows written, Discord ping (level=error)

**Test D — CSV missing required columns:**
- Upload a CSV with only `Email` column
- Expected: batch fails cleanly at parse step, Discord ping with clear "malformed CSV" error, no partial writes

Document each test's actual behavior in `pipelines/01-loomless/README.md`.

**STOP GATE 7.** All 4 failure modes fail loudly and safely. Documented.

### 8. Full 100-lead dry run (~60 min — mostly waiting)

Take a real 100-lead CSV (Rinoah/Jon can provide, or generate synthetic if needed). Upload. Watch execution.

Verify:
- All 100 rows land in Sheet
- Roughly expected ratio of `ready_for_review` vs `[NO_CONTEXT]` (~70-90% ready is target)
- No rate-limit errors from Perplexity or Anthropic
- Total execution time reasonable (rough target: under 30 min for 100 leads)
- Discord summary accurate

**Cost tracking:** log approximate API cost — Perplexity tokens used + Claude tokens used. Add to `pipelines/01-loomless/README.md` as "Cost per 100 leads: ~$X" so scaling to 400/day is a known quantity.

**STOP GATE 8.** 100-lead batch completes cleanly. Costs documented.

### 9. Sticky note documentation on canvas (~10 min)

Add Sticky Notes to the workflow canvas covering:
- Pipeline purpose (1-line summary)
- Inputs (Drive folder, CSV format)
- Outputs (Loomless tab rows + Discord ping)
- Dependencies (`Sub_WriteRowToSheet`, `Sub_NotifyDiscord`, Perplexity + Anthropic APIs)
- Failure modes and their behaviors (from Task 7)
- Cost per 100 leads
- Prompt version references (`prompts/perplexity_research.md`, `prompts/claude_first_line.md`)

### 10. Export + commit + merge (~15 min)

- Export `OPS-61_Loomless_Pipeline.json` to `shared/n8n-templates/`
- Commit incrementally throughout the session
- Final PR-style summary in a commit message before merge
- Merge `pipeline-1-loomless` → `main` with `--no-ff`
- Push both branches to origin

---

## Acceptance criteria

All must be true before this build is complete:

- [ ] Branch `pipeline-1-loomless` merged to `main` with `--no-ff` commit
- [ ] `pipelines/01-loomless/` populated with README, prompts, test fixtures
- [ ] `OPS-61_Loomless_Pipeline.json` exported to `shared/n8n-templates/`, committed
- [ ] `verify_loomless_batch.py` script exists and can validate Loomless tab writes
- [ ] Env vars added to `infra/.env`, `.env.example`, and `docker-compose.yml`
- [ ] Anthropic credential in n8n passes Test
- [ ] Perplexity API accessible from n8n (verified in a throwaway workflow)
- [ ] Perplexity prompt achieves ≥7/10 usable research on test leads
- [ ] Claude prompt achieves ≥8/10 sendable first lines on test leads
- [ ] Smoke test with 3-lead CSV: all rows land in Sheet with correct statuses
- [ ] 4 failure modes tested and documented
- [ ] Full 100-lead batch completes without manual intervention
- [ ] Approximate API cost per 100 leads documented
- [ ] Sticky note documentation on canvas covers all sections
- [ ] Both Sub_WriteRowToSheet and Sub_NotifyDiscord called correctly (foundation primitives reused)
- [ ] No secrets committed (verify with `git ls-files | Select-String -Pattern "key|secret"` returning nothing sensitive)

---

## Guardrails for the Claude Code session

**DO:**
- Read all four reference docs first, confirm understanding before writing any code
- Ask before making design choices not covered in this spec (e.g. batch delay tuning, retry logic)
- Commit incrementally — one commit per major step
- Verify Sheet writes via API, not just n8n canvas (Foundation lesson learned)
- Treat prompts as first-class artifacts — version them, commit them, don't inline them in workflow JSON
- Use `Sub_WriteRowToSheet` and `Sub_NotifyDiscord` as-is (they're locked primitives)
- Handle single-lead failures without aborting the batch
- Keep API keys in n8n env vars only, never in workflow JSON or prompts

**DO NOT:**
- Modify `Sub_WriteRowToSheet` or `Sub_NotifyDiscord` (they're shared primitives — changing them breaks Foundation)
- Modify the locked Loomless schema in `shared/sheets-schema.md`
- Add auto-send capability of any kind (locked plan constraint)
- Add multi-variant generation, follow-up sequences, or an auditor agent (out of scope)
- Print API keys in transcripts or logs (mask when verifying)
- Skip the failure-mode tests to save time (Foundation proved they matter)
- One-shot the whole pipeline before validating the prompts individually
- Merge to main without acceptance criteria all checked

---

## Handoff to Build Spec #3 (JV Research Bot)

Once this ships:
- The Perplexity integration pattern is reusable — JV Bot uses the same HTTP Request approach with a different query template
- `Sub_WriteRowToSheet` proven at real batch scale — JV Bot just calls it with `tab: "JV_Targets"`
- Discord notification patterns established
- Cost baseline for Perplexity understood

Build Spec #3 draft comes after this session's acceptance check-in.

---

## Session prompt to paste to Claude Code

```
Read OPS-61_PLAN.md, docs/EASYGROW_SPEC.md, shared/sheets-schema.md,
and BUILD_SPEC_2_LOOMLESS.md — in that order. Confirm you've read
all four before doing anything else.

Build only what's in BUILD_SPEC_2_LOOMLESS.md. Follow the acceptance
criteria checklist. Stop at each stop gate and wait for me to confirm
before proceeding.

Create branch pipeline-1-loomless from main before writing anything.

Same rules of engagement as Foundation session:
- Never print API keys or credential contents
- Verify Sheet writes via Sheets API, not just n8n canvas
- Treat prompts as versioned files, not workflow-embedded strings
- Single-lead failures must not abort the batch
- Use Sub_WriteRowToSheet and Sub_NotifyDiscord as-is (do not modify)

Ask me for the two API keys (ANTHROPIC_API_KEY and PERPLEXITY_API_KEY)
when you reach STEP 2. Don't guess or fetch them yourself.

Ready when you are — start with STEP 1 (repo scaffolding) after
confirming you understand the scope.
```
