# Perplexity research prompt — Loomless

> **Version:** v0.1 — DRAFT (not yet validated)
> **Status:** Drafted from EasyGrow spec + Build Spec #2 guidance. **Not yet run
> against test leads** — Perplexity API key is on hold (STEP 3 is a hard block
> until the key is in `.env`). Do not treat the ≥7/10 usable-context target as
> met until iteration happens.
> **Model target:** Perplexity `sonar` / `sonar-pro` (online search). Final model
> pinned during STEP 3 iteration.

---

## Purpose

Given a single lead (name + company + website), return a concise research
summary of **recent, specific, human-interest facts** that a cold-email first
line could reference so it reads "you actually looked at me," not "you scraped
my domain."

## Call shape (for the n8n HTTP Request node)

Perplexity is called directly via HTTP Request (no dedicated n8n credential).
`Authorization: Bearer {{ $env.PERPLEXITY_API_KEY }}`. The prompt below is the
`user` message; the JSON contract is enforced via the `system` message.

### System message

```
You are a precise B2B research assistant. You search the live web and LinkedIn
for RECENT, SPECIFIC, verifiable facts about a person and their company.

You return ONLY a single JSON object, no prose, no markdown fences, matching:
{
  "research_summary": string,   // 2-3 sentences, most useful specific context
  "confidence": "high" | "medium" | "low",
  "source_hints": string[]      // brief notes on where each fact came from
}

Rules:
- Prefer facts from the last 30-60 days.
- Every fact must be specific enough to reference in a personal message:
  a named post, a launch, a milestone, a location, a media appearance, a hire.
- If you cannot find anything specific and recent, set confidence to "low" and
  say so plainly in research_summary. NEVER invent or speculate to fill space.
- confidence="high": at least one recent, specific, personally-relevant fact.
  "medium": something real but generic or slightly dated.
  "low": nothing usable beyond boilerplate.
```

### User message (template — n8n fills the `{{ }}` expressions)

```
Research this lead for a personalized cold-email opening line.

First name:    {{ $json.First_Name }}
Full name:     {{ $json.Owner_Full_Name }}
Company:       {{ $json.Company_Name }}
Website:       {{ $json.Website }}

Find the most recent, specific, human-interest context about this person and
their company. Look for:
- Recent LinkedIn posts (last 30-60 days) and what they were about
- Podcast appearances, interviews, or media mentions
- Company news: funding, product launches, hiring, expansion, awards
- Personal context: location, recent achievements, milestones

Do NOT return:
- Generic company descriptions or "about page" boilerplate
- LinkedIn bio filler ("passionate about", "helping businesses grow")
- Anything speculative or unverifiable

Return the JSON object described in the system message. Nothing else.
```

## Output contract

```json
{
  "research_summary": "2-3 sentences of the most useful specific context found",
  "confidence": "high | medium | low",
  "source_hints": ["brief note on where the info came from"]
}
```

- `confidence="low"` is the signal that Perplexity found nothing usable. The
  pipeline translates low confidence into `Personalized_First_Line = [NO_CONTEXT]`
  (skips the Claude call) so operators know to skip that lead. A no-context lead
  is **not** an error — it still gets a row with `status=ready_for_review`.

## Iteration log (STEP 3 — to be filled)

| Version | Change | Result on sample_leads_10 (usable ≥ high-conf) |
|---|---|---|
| v0.1 | Initial draft (this file) | not yet run |

**Acceptance (STEP 3):** ≥7/10 sample leads return high-confidence usable context.
Document final version + rationale here before proceeding.
