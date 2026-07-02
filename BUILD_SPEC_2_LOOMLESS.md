# Build Spec #2 — Loomless Pipeline, mock-based dev

> **STATUS: APPROVED — restructured to the mock-based approach per Decision #12.**
> This supersedes the original live-call spec. Implementation runs in a fresh
> session (per the merge handoff); do not build from this file in the same session
> it was approved.
>
> **What changed vs the original** (driven by PLAN v8, Decision #12 — mock-based
> dev, credentials at migration):
> - No real Perplexity/Anthropic calls during dev. Each external call has **two
>   paths in one workflow** — a real HTTP Request node (`live`) and a mock Code
>   node (`mock`) — selected by `LOOMLESS_MODE`.
> - Prompts stay **UNTUNED v0.1 drafts**; tuning moves to Build Spec #6.
> - Acceptance criteria are **unchanged in intent** (row lands in Sheet, Discord
>   fires, failures handled) but **validated against mock data**.
> - `Sub_WriteRowToSheet` + `Sub_NotifyDiscord` run with their real, free,
>   already-provisioned credentials in **both** modes.
> - Cost per 100 leads is **$0 in dev**; the live cost estimate is a Build Spec #6
>   deliverable.

**Owner:** Rinoah · **Depends on:** Build Spec #1 (complete) · **Plan:** v8 / Decision #12
**Branch (proposed):** `pipeline-1-loomless-mock` off `main` (after the current
valid work is merged). Reusing `pipeline-1-loomless` is also fine — your call.

---

## Goal

By session end the Loomless workflow can, **in mock mode with zero external API
cost**:

1. Watch `OPS-61/Loomless-Inbox/` for new CSV uploads.
2. Parse each row (`Company_Name, Owner_Full_Name, First_Name, Email, Website`).
3. Produce a **research object** — from a mock Code node (`mock`) or a real
   Perplexity HTTP Request (`live`), selected by `LOOMLESS_MODE`.
4. Produce **one first line** — from a mock Code node (`mock`) or a real Anthropic
   HTTP Request (`live`), selected by `LOOMLESS_MODE`. Low-confidence research
   short-circuits to `[NO_CONTEXT]` (no Claude/mock-Claude call).
5. Write each lead to the `Loomless` tab via `Sub_WriteRowToSheet`
   (`status=ready_for_review`, or `dead` on per-lead failure).
6. Ping `#ops-61-feed` via `Sub_NotifyDiscord` with a batch summary.
7. Survive single-lead failures without aborting the batch.

Flipping `LOOMLESS_MODE=mock → live` (plus real credentials) is the **only**
change needed to go live — that flip + tuning is Build Spec #6.

---

## Out of scope (unchanged from original, plus)

- All original out-of-scope items (auto-send, follow-ups, auditor agent, multi-
  variant, CSV UI, JV/FB/video, prod deploy).
- **New:** real Perplexity/Anthropic calls, prompt tuning, live cost measurement,
  Drive OAuth hardening — all deferred to Build Spec #6.

---

## Architecture (mock/live dual-path)

```
Operator drops CSV → Drive: OPS-61/Loomless-Inbox/
        ↓  Drive trigger (.csv only) → Download → Extract from File (rows)
        ↓  Batch-size guard (Code): items.length <= LOOMLESS_BATCH_SIZE else stopAndError
        ↓  Split In Batches (chunk of N)
   ┌─────────────────────── per lead ───────────────────────┐
   │  [Research]                                             │
   │    IF $env.LOOMLESS_MODE == 'live'                      │
   │      → HTTP Request: Perplexity   ┐                     │
   │    else                           ├→ (same-shape JSON) → Set: normalize
   │      → Code: MOCK Perplexity      ┘      → research_summary, confidence
   │                                                         │
   │  IF confidence == 'low' → Set Personalized_First_Line = "[NO_CONTEXT]"
   │  else [First line]                                      │
   │    IF $env.LOOMLESS_MODE == 'live'                      │
   │      → HTTP Request: Anthropic    ┐                     │
   │    else                           ├→ (same-shape JSON) → Set: extract text
   │      → Code: MOCK Anthropic       ┘      → Personalized_First_Line
   │                                                         │
   │  Set: build row (9 Loomless cols) → Sub_WriteRowToSheet (tab=Loomless)
   │  (Continue-on-Fail everywhere; on failure tag row status=dead)
   └─────────────────────────────────────────────────────────┘
        ↓  Aggregate (Code): processed / ready / [NO_CONTEXT] / dead
        ↓  Sub_NotifyDiscord (level=info, pipeline=loomless)
        ↓  Move CSV → Loomless-Inbox/processed/
```

### Convergence design (reviewer question **a**)

**Decision: same-shape + single shared normalizer.** The mock Code node returns
the **exact JSON shape** the real HTTP Request returns (see "Mock response
shapes"). Both branches wire into **one** downstream **normalizer Set node** —
there is NO per-path normalizer.

- Flow: `IF mode` → (mock Code | live HTTP Request) → **Merge** (mode = "Choose
  Branch"/append; exactly one branch is ever populated per item) → **Set:
  normalize** (extracts `research_summary`, `confidence` from the raw shape) →
  downstream.
- **Why this over a normalizer-per-path:** the parsing/extraction logic is
  written and tested **once** against **one** shape. If mock and live each had
  their own normalizer, the two could drift and mock would stop being a faithful
  proxy for live — defeating the point of mock-based dev. Byte-compatibility is
  enforced at the *source* (mock emits the real shape), so everything after the
  Merge is genuinely mode-agnostic and identical in both modes.
- The same pattern repeats for the Anthropic call: `IF mode` → (mock | live) →
  Merge → `Set: extract text` (`content[0].text` → `Personalized_First_Line`).

---

## Env vars

Add one new var; the rest already exist from the current branch.

```
LOOMLESS_MODE=mock          # mock | live  — dev default is mock
LOOMLESS_DEV_SHEET_ID=      # the dev CRM Sheet ID; mock mode refuses to write
                            #   to any other Sheet (fail-closed guard, question c)
ANTHROPIC_API_KEY=          # already wired; only needed in live mode (BS#6)
PERPLEXITY_API_KEY=         # already wired; only needed in live mode (BS#6)
LOOMLESS_BATCH_SIZE=100
LOOMLESS_DAILY_CAP=100
```

Add `LOOMLESS_MODE` + `LOOMLESS_DEV_SHEET_ID` to `infra/.env`,
`infra/.env.example`, and the compose `environment:` block (mirrors existing
pattern). Restart n8n. (`LOOMLESS_DEV_SHEET_ID` = the current `GOOGLE_SHEET_ID`
during dev.)

---

## Mock response shapes (canonical — match these exactly)

Documented in `pipelines/01-loomless/mocks/README.md`; the logic lives in the
workflow's mock Code nodes (git-tracked via the exported JSON).

**Mock Perplexity** (OpenAI-compatible chat-completions shape; the research JSON
is a *string* inside `choices[0].message.content`, exactly as the real API
returns it):

```json
{
  "id": "mock-pplx-<leadhash>",
  "model": "sonar",
  "choices": [{
    "index": 0, "finish_reason": "stop",
    "message": { "role": "assistant",
      "content": "{\"research_summary\":\"...\",\"confidence\":\"high\",\"source_hints\":[\"mock\"]}" }
  }],
  "usage": { "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0 }
}
```

**Mock Anthropic** (Messages API shape; first line in `content[0].text`):

```json
{
  "id": "msg_mock_<leadhash>", "type": "message", "role": "assistant",
  "model": "claude-sonnet-4-5-20250929",
  "content": [{ "type": "text", "text": "Saw your December post on that 40% close rate — congrats!" }],
  "stop_reason": "end_turn",
  "usage": { "input_tokens": 0, "output_tokens": 0 }
}
```

### Deterministic mock scenarios (so smoke + failure tests are repeatable)

The mock Code nodes branch on the lead so every downstream path is exercised
without editing the workflow. Proposed convention (keyed off `First_Name`, or an
optional `_mock_scenario` CSV column if present):

| Scenario | Trigger | Mock Perplexity | Mock Anthropic | Expected row |
|---|---|---|---|---|
| `normal` | default | confidence=high, real-ish summary | one-sentence first line | `ready_for_review`, line populated |
| `no_context` | e.g. `First_Name=Robert` | confidence=low | (skipped) | `ready_for_review`, `[NO_CONTEXT]` |
| `bad_research` | `_mock_scenario=bad_research` | non-JSON string in content | (skipped) | `dead` (parse fails) |
| `empty_line` | `_mock_scenario=empty_line` | confidence=high | `content[0].text=""` | `dead` (invalid line) |

### Field stripping (reviewer question **b**)

**First, the actual `Sub_WriteRowToSheet` behavior** (verified against the
committed workflow, not assumed): its per-tab Append nodes use
`mappingMode: defineBelow` — each locked column is mapped **explicitly** from
`$json.<col>`, all fields `required: false`. Consequence: a field in `row` that
isn't a locked column (e.g. `_mock_scenario`) is **simply not referenced, so it
is silently ignored — it does NOT abort the write.** The Sub's *only* loud-fail
is an **unroutable `tab`**: `tab` must be top-level in `{ tab, row }`; if it's
missing/unknown the Switch falls through to the "Unknown Tab" Stop-And-Error.
So the reviewer's stated risk ("extra field blows up the write") does **not**
hold against this Sub — but we still strip, for cleanliness and future-proofing.

**Stripping is structural, not a delete list.** The final **`Set: build row`**
node (immediately before `Sub_WriteRowToSheet`) runs with n8n's
**"Include Other Input Fields" = OFF** ("Keep Only Set") and assigns *only* the
locked Loomless data columns:

```
Company_Name, Owner_Full_Name, First_Name, Email, Website,
Research_Summary, Personalized_First_Line, status
```

Nothing passes through implicitly, so `_mock_scenario` and all intermediates are
dropped **by construction** — no reliance on remembering to delete them, and
robust even if the Sub later adds strict validation. Notes: `created_at` is
auto-stamped by the Sub if omitted; `tab: "Loomless"` is passed at the **top
level** of the Sub input, never inside `row`. This Set node is the single choke
point where row shape is guaranteed correct, identically in mock and live mode.

---

## Mock/live safety — how mock rows can never pass as production (reviewer question **c**)

**Recommendation: a layered defense (a fourth option), not any single one of the
three.** No single control is sufficient; each covers a different failure.

**1. Primary — environment isolation (different Sheets per environment).** Dev
writes to the current dev CRM Sheet (`GOOGLE_SHEET_ID` today). Production is a
**fresh Sheet provisioned on the target at migration** (Decision #12 replaces all
credentials, Sheet included). Mock rows and real rows therefore **physically
never share a spreadsheet** — this is the real guarantee, and it falls straight
out of the mock-first plan.

**2. Defense-in-depth — a `[MOCK]` content marker.** Whenever
`LOOMLESS_MODE=mock`, the `Set: build row` node prefixes `Research_Summary` and
`Personalized_First_Line` with `[MOCK] `. Any human scanning the Sheet sees it
instantly; any query can filter it. In `live` mode the prefix is absent.
*Why not the reviewer's "marker in the `status` column" (option 2 as stated):*
`status` is a **locked enum** (`ready_for_review|dead|…`) that operator Discord
filters and `verify_loomless_batch.py` match on exactly — a `MOCK_` prefix there
would break those. Loomless also has **no `operator_notes` column** (that's the
`Inbound` tab). Prefixing the two free-text string columns is the schema-safe way
to achieve the same "unmistakable" intent.

**3. Fail-closed guard — allowlist, not pattern-match.** The batch-guard Code
node (top of the workflow) asserts: **if `LOOMLESS_MODE=mock`, the target
`GOOGLE_SHEET_ID` MUST equal `$env.LOOMLESS_DEV_SHEET_ID`; otherwise
`stopAndError` before any write.** This is fail-closed (explicit allowlist of the
known dev Sheet), stronger than the reviewer's "matches a production pattern"
(fail-open — anything not matching the guessed pattern slips through). It blocks
the "mock config accidentally pointed at the prod Sheet" accident directly.

**4. Runbook step (option 1) — retained, but never the sole control.** Build
Spec #6's runbook gets an explicit "set `LOOMLESS_MODE=live` and clear
`LOOMLESS_DEV_SHEET_ID`" checklist item. Humans forget; layers 1–3 don't.

*(If you'd rather keep v1 lean: layers 1 + 2 are the minimum I'd ship — isolation
is the guarantee, `[MOCK]` makes it visible. Layer 3 is cheap (~6 lines in a node
that already exists) and I recommend including it.)*

## Tasks (each a stop gate)

### 0. Merge current valid work (prereq) — DONE on branch, merge handed to Rinoah
Scaffolding, env placeholders, PLAN v8, UNTUNED prompts are committed. Merge to
`main`, then branch for the build.

### 1. Add `LOOMLESS_MODE` + `LOOMLESS_DEV_SHEET_ID` env vars (~10 min)
`infra/.env` + `.env.example` + `docker-compose.yml`; restart n8n; confirm
`$env.LOOMLESS_MODE == "mock"` and `$env.LOOMLESS_DEV_SHEET_ID` resolve inside the
container (masked check, same as before). **No new credentials** — Anthropic
credential already exists; Perplexity is live-only. **STOP GATE 1.**

### 2. Build the workflow — mock paths first (~90 min)
Drive trigger → download → Extract → **batch guard** (Code: `items.length <=
LOOMLESS_BATCH_SIZE` **and** the fail-closed dev-Sheet assertion from question c,
layer 3) → Split In Batches → per-lead dual-path (mock Code nodes wired now; live
HTTP Request nodes built but parked behind the `live` IF branch; each pair
reconverges via Merge → shared normalizer, question a) → **`Set: build row`**
("Keep Only Set"; applies the `[MOCK] ` prefix when `LOOMLESS_MODE=mock`) →
`Sub_WriteRowToSheet` → aggregate → `Sub_NotifyDiscord` → move CSV.
Continue-on-Fail on every risky node; failures → `status=dead`, batch continues.
Do NOT execute yet. **STOP GATE 2.**

### 3. `verify_loomless_batch.py` + 3-lead mock smoke (~30 min)
Add `shared/scripts/verify_loomless_batch.py` (reads last N Loomless rows, counts
by status — reuses `_common.py`/`schema.py`). Upload `test-fixtures/smoke_test_3.csv`
(1 normal, 1 no_context, 1 error scenario). Verify **via Sheets API, not canvas**:
rows land with correct statuses, Discord fires, CSV moved to `/processed/`.
**STOP GATE 3.**

### 4. Failure-mode tests on mock (~30 min)
- A. `bad_research` mock → that lead `status=dead`, batch continues, Discord notes it.
- B. `empty_line` mock → `status=dead`, batch continues.
- C. CSV > `LOOMLESS_BATCH_SIZE` → `stopAndError`, zero rows, Discord (level=error).
- D. CSV missing required columns → clean fail at parse, Discord error, no writes.
Document each in `pipelines/01-loomless/README.md`. **STOP GATE 4.**

### 5. 100-lead mock dry run (~20 min)
Synthetic 100-lead CSV through mock. All rows land; status ratios sane; no errors;
note wall-clock. **Cost = $0 (mock)** — live cost is a Build Spec #6 deliverable.
**STOP GATE 5.**

### 6. Canvas sticky notes (~10 min)
Purpose, inputs/outputs, dependencies, the mock/live toggle + how to flip it,
mock scenario table, prompt-version refs, and a "UNTUNED — tune in BS#6" banner.

### 7. Export + commit + merge (~15 min)
Export `OPS-61_Loomless_Pipeline.json` → `shared/n8n-templates/` (mock Code node
logic travels inside it). Incremental commits. Merge with `--no-ff` (commands
handed back to Rinoah). Push.

---

## Acceptance criteria (mock-validated)

- [ ] `LOOMLESS_MODE` + `LOOMLESS_DEV_SHEET_ID` wired in `.env`/`.env.example`/
      compose; resolve in container.
- [ ] Workflow has both mock + live paths per external call, switched by an IF on
      `$env.LOOMLESS_MODE`; mock output shape == live output shape (single shared
      normalizer, question a).
- [ ] Fail-closed guard: in `mock` mode the workflow refuses to write unless
      `GOOGLE_SHEET_ID == LOOMLESS_DEV_SHEET_ID` (question c, layer 3).
- [ ] Mock rows carry a visible `[MOCK] ` prefix in `Research_Summary` +
      `Personalized_First_Line`; absent in `live` mode (question c, layer 2).
- [ ] `_mock_scenario` (+ all intermediates) never reach the Sheet — `Set: build
      row` uses "Keep Only Set" (question b).
- [ ] 3-lead mock smoke: 2 `ready_for_review` (one `[NO_CONTEXT]`) + correct
      handling of the error lead; verified via `verify_loomless_batch.py`.
- [ ] 4 failure modes fail loudly + safely; documented.
- [ ] 100-lead mock run completes with no manual intervention.
- [ ] `OPS-61_Loomless_Pipeline.json` exported + committed.
- [ ] `Sub_WriteRowToSheet` + `Sub_NotifyDiscord` used unmodified.
- [ ] Prompts committed as UNTUNED v0.1.
- [ ] No secrets committed; `infra/.env` still gitignored.
- [ ] Sticky notes document the mock/live flip for the BS#6 operator.

**Explicitly NOT required here (moved to Build Spec #6):** real API reachability,
7/10 & 8/10 prompt quality gates, live cost per 100 leads.

---

## Guardrails

**DO:** keep mock output byte-compatible with live output shape; keep prompts as
UNTUNED files; verify Sheet writes via API; use the two Sub-workflows as-is;
handle single-lead failures without aborting; keep `LOOMLESS_MODE=mock` as the
committed default.

**DO NOT:** make any real Perplexity/Anthropic call; tune prompts; commit keys;
modify the Foundation primitives or the locked Loomless schema; add auto-send;
delete anything Rinoah pasted into `.env`.

---

## Handoff to Build Spec #6 (migration)

On the target machine: provision real credentials, set `LOOMLESS_MODE=live`, run
one real batch, tune `perplexity_research.md` + `claude_first_line.md` against
live outputs (7/10, 8/10 gates), and record live cost per 100 leads. Because the
live HTTP Request nodes already exist behind the `live` branch, going live is a
config flip + tuning pass — no workflow surgery.
