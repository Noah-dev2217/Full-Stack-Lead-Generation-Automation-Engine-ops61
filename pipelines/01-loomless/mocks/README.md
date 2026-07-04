# Loomless mocks — canonical response shapes

> Per PLAN v8 / Decision #12 (mock-based dev). During dev the Perplexity and
> Anthropic calls are **mocked**: `Mock — Perplexity` and `Mock — Anthropic`
> Code nodes return the **exact JSON shape** the real APIs return, so both the
> mock and live paths reconverge through one shared normalizer and everything
> downstream is mode-agnostic. No real API calls, no cost, no credentials until
> Build Spec #6.

The mock logic is **not** hand-maintained here — it is generated into the
workflow's Code nodes from a single source:
`shared/scripts/build_loomless_workflow.py` (`JS_LIB`). That same source feeds an
offline harness so what we validate == what ships. This file documents the
shapes for humans.

---

## Selection

`Mode = live? (Perplexity)` / `Mode = live? (Anthropic)` are IF nodes on
`$env.LOOMLESS_MODE`:

- `mock` (dev default) → the `Mock — …` Code node runs.
- `live` (Build Spec #6) → the `HTTP — …` node calls the real API.

Exactly one branch is populated per item; both wire into the same shared
normalizer.

---

## Mock Perplexity (OpenAI-compatible chat-completions)

The research object is a JSON **string** inside `choices[0].message.content`,
exactly as the real Perplexity API returns it. The normalizer `JSON.parse`s it.

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

## Mock Anthropic (Messages API)

First line in `content[0].text`.

```json
{
  "id": "msg_mock_<leadhash>", "type": "message", "role": "assistant",
  "model": "claude-sonnet-4-5-20250929",
  "content": [{ "type": "text", "text": "Saw the recent milestone over at ..." }],
  "stop_reason": "end_turn",
  "usage": { "input_tokens": 0, "output_tokens": 0 }
}
```

---

## Deterministic scenarios

Branch on `First_Name` or an optional `_mock_scenario` CSV column:

| Scenario | Trigger | Mock Perplexity | Mock Anthropic | Expected row |
|---|---|---|---|---|
| `normal` | default | `confidence=high`, real-ish summary | one-sentence line | `ready_for_review`, line populated |
| `no_context` | `First_Name=Robert` or `_mock_scenario=no_context` | `confidence=low` | (skipped) | `ready_for_review`, `[NO_CONTEXT]` |
| `bad_research` | `_mock_scenario=bad_research` | non-JSON string in `content` | (skipped) | `dead` (normalizer parse fails) |
| `empty_line` | `_mock_scenario=empty_line` | `confidence=high` | `content[0].text=""` | `dead` (invalid line) |

`_mock_scenario` never reaches the Sheet — `Set: Build Loomless Row` emits only
the locked columns.

### `[MOCK]` marker

In mock mode, `Research_Summary` and real first lines are prefixed with
`[MOCK] `. The `[NO_CONTEXT]` sentinel is **never** prefixed (operators and
`verify_loomless_batch.py` match it exactly). `verify_loomless_batch.py` strips a
leading `[MOCK] ` before classifying.

---

## Regenerate / validate

```bash
# regenerate the workflow JSON (+ offline harness)
python shared/scripts/build_loomless_workflow.py --harness --harness-out=<path>/loomless_harness.js
node <path>/loomless_harness.js     # drives all 4 scenarios + guard checks, no n8n
```

Going live (Build Spec #6) is a config flip — `LOOMLESS_MODE=live` + real keys —
plus prompt tuning. No workflow surgery: the live HTTP nodes already exist behind
the `live` branch.
