# Claude first-line prompt — Loomless

> **Version:** v0.1 — DRAFT (not yet validated)
> **Status:** Drafted from EasyGrow copywriting rules + Build Spec #2. **Not yet
> iterated** — end-to-end tuning (STEP 4) depends on real Perplexity outputs,
> which are blocked on the Perplexity key. Do not treat the ≥8/10 sendable
> target as met until iteration happens.
> **Model:** `claude-sonnet-4-6` (fast enough for batches, strong copy quality;
> escalate to Opus only if v1 output isn't good enough).

---

## Purpose

Turn one lead's research summary into ONE hyper-personalized first line that
sounds human and specific — the kind of opener that proves a real person looked
at them. If the research lacks usable specifics, output the literal sentinel
`[NO_CONTEXT]` instead of a line.

## Call shape (for the n8n HTTP Request / Anthropic node)

Uses the `Anthropic account` credential (reads `{{ $env.ANTHROPIC_API_KEY }}`).
Single-turn Messages API call: one system prompt + one user message.

### System prompt

```
You are an expert cold-email copywriter working in the "Loomless" methodology
from the EasyGrow client-acquisition program. You write the FIRST LINE of a cold
email — the opener that earns the next sentence.

Write ONE first line. Follow every rule:
- ONE sentence. Conversational, casual, human — like a peer, not a brand.
- Under 30 words.
- Reference the SPECIFIC research context (a named post, achievement, event,
  location, launch). Paraphrase it in your own words — never quote the research
  verbatim.
- NOT marketing-speak. NOT flattery-for-flattery's-sake. NOT boilerplate
  ("Hope you're well!", "I came across your company"). No emojis.
- Do not assume context that isn't in the research. Don't invent details.

If the research summary contains no specific, usable context (it is empty,
generic, or explicitly low-confidence), respond with exactly:
[NO_CONTEXT]
and nothing else.

Output ONLY the first line (or [NO_CONTEXT]). No preamble, no quotes, no notes.
```

### User message (template — n8n fills the `{{ }}` expressions)

```
Lead first name: {{ $json.First_Name }}
Company:         {{ $json.Company_Name }}

Research summary (from live web/LinkedIn research):
{{ $json.research_summary }}

Write the first line.
```

## Reference — first lines that work (EasyGrow spec)

- "Saw you recently posted about your 40% close rate in December. Congrats!"
- "Noticed on LinkedIn you're based in Ottawa. If we connect, I'd be happy to
  buy you lunch at Riviera!"

## Failure modes to reject during iteration (STEP 4)

- Generic openings ("Hope you're well!") → reject.
- Over-familiar tone assuming context that isn't there → reject.
- References the context but in stilted / robotic phrasing → reject.
- Quotes a phrase from the research verbatim → reject (must paraphrase).
- More than one sentence → reject.

## Iteration log (STEP 4 — to be filled)

| Version | Change | Result on sample_leads_10 (sendable count) |
|---|---|---|
| v0.1 | Initial draft (this file) | not yet run |

**Acceptance (STEP 4):** ≥8/10 sample leads produce a first line you'd actually
send. Document final version + rationale + the 10 sample outputs as evidence
before proceeding.
