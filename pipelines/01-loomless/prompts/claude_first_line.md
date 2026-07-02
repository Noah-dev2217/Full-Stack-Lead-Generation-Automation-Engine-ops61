# Claude first-line prompt — Loomless

> **Version:** v0.1 — **UNTUNED. Final tuning at migration (Build Spec #6).**
> **Status:** First-principles draft from EasyGrow copywriting rules. Per PLAN v8
> Decision #12 (mock-based dev), this prompt is **never run against real Claude
> during dev** — the workflow uses a mock Code node returning a realistic first
> line of this shape. End-to-end tuning against live Perplexity + Claude outputs
> happens in Build Spec #6 (handoff). The ≥8/10 sendable target is a Build Spec
> #6 gate, not a dev gate.
> **Model (PINNED, for live mode):** `claude-sonnet-4-5-20250929` — use this exact string in the
> Anthropic node / HTTP Request node of the workflow. Build Spec #2 named
> `claude-sonnet-4-6`, but this account/key resolves to
> `claude-sonnet-4-5-20250929` (verified via direct `api.anthropic.com/v1/messages`
> call). Escalate to an Opus model only if v1 output isn't good enough.
> **Credential:** n8n `Anthropic account` (reads `{{ $env.ANTHROPIC_API_KEY }}`).
> Note: n8n's built-in credential **Test button 404s** on this version (hits a
> deprecated endpoint) — this is a false negative; the key is verified working
> via direct API call, and real workflow nodes function correctly.

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

## Iteration log (Build Spec #6 — to be filled at migration)

| Version | Change | Result on sample_leads_10 (sendable count) |
|---|---|---|
| v0.1 | Initial draft (this file) — untuned | not run (mock dev) |

**Acceptance (Build Spec #6):** ≥8/10 sample leads produce a first line you'd
actually send against live APIs. Document final version + rationale + the 10
sample outputs as evidence before switching Loomless to `LOOMLESS_MODE=live`.
