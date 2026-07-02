#!/usr/bin/env python3
"""Generate OPS-61_Loomless_Pipeline.json (Build Spec #2 — mock-based dev).

Single source of truth for the Loomless n8n workflow. The Loomless row columns
are pulled from `schema.TABS["Loomless"]` so the write payload can never drift
from the locked CRM schema (working-style rule).

The per-lead transformation logic lives as PURE JS functions in JS_LIB below.
Those exact strings are:
  1. embedded into the workflow's Code nodes (thin n8n wrappers call them), and
  2. concatenated into an offline harness (write_harness()) that exercises the
     four mock scenarios with plain node.js — no n8n, no external API.
Because both consume the identical strings, the offline validation faithfully
represents what the shipped nodes do.

Usage:
    python build_loomless_workflow.py            # writes the workflow JSON
    python build_loomless_workflow.py --harness  # also writes the offline harness

Outputs:
    shared/n8n-templates/OPS-61_Loomless_Pipeline.json
    <scratchpad>/loomless_harness.js   (only with --harness; path via env or arg)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import schema  # noqa: E402

LOOMLESS_COLS = schema.TABS["Loomless"]
# lead columns = everything the pipeline does NOT generate itself
_GENERATED = {"Research_Summary", "Personalized_First_Line", "status", "created_at"}
LEAD_COLS = [c for c in LOOMLESS_COLS if c not in _GENERATED]  # 5 source-CSV cols
REQUIRED_COLS = list(LEAD_COLS)  # required CSV headers == the 5 lead cols

# ─────────────────────────────────────────────────────────────────────────────
# PURE JS LOGIC (shared by n8n Code nodes AND the offline harness)
# No n8n-isms in here ($json/$env/$() live in the thin wrappers). Plain funcs.
# ─────────────────────────────────────────────────────────────────────────────

# buildRow's lead-column assignments are generated from the schema so they can't
# drift. Produces lines like:  Company_Name: s(d.Company_Name),
_LEAD_ASSIGNS = "\n".join(f"      {c}: s(d.{c})," for c in LEAD_COLS)

JS_LIB = r"""
// ---- shared helpers ----
function s(v) { return v == null ? '' : String(v); }
function leadHash(d) {
  return s(d.Email || d.First_Name || 'lead').replace(/[^a-zA-Z0-9]/g, '').slice(0, 8).toLowerCase();
}

// ---- MOCK Perplexity: returns the OpenAI-compatible chat-completions shape ----
// The research object is a JSON *string* inside choices[0].message.content,
// exactly as the real Perplexity API returns it.
function mockPplx(lead) {
  var scenario = s(lead._mock_scenario).trim().toLowerCase();
  var first = s(lead.First_Name).trim();
  var co = s(lead.Company_Name).trim();
  var site = s(lead.Website).trim();
  var content;
  if (scenario === 'bad_research') {
    content = '<<<PERPLEXITY_ERROR>>> upstream returned a non-JSON blob; this is deliberately unparseable';
  } else if (scenario === 'no_context' || first.toLowerCase() === 'robert') {
    content = JSON.stringify({
      research_summary: 'No recent, specific, verifiable public context found for '
        + (first || 'this lead') + ' at ' + (co || 'their company') + '.',
      confidence: 'low',
      source_hints: ['mock']
    });
  } else {
    content = JSON.stringify({
      research_summary: (first || 'The founder') + ' at ' + (co || 'the company')
        + ' recently shared a notable milestone; ' + (site || 'their site')
        + ' highlights a new offering worth referencing.',
      confidence: 'high',
      source_hints: ['mock:linkedin', 'mock:site']
    });
  }
  return {
    id: 'mock-pplx-' + leadHash(lead),
    model: 'sonar',
    choices: [{ index: 0, finish_reason: 'stop', message: { role: 'assistant', content: content } }],
    usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 }
  };
}

// ---- shared normalizer (question a): raw pplx shape -> research fields ----
// Re-attaches the lead so downstream nodes have both the research + source cols.
function normalizeResearch(raw, lead) {
  var research_summary = '', confidence = 'low', _status = 'ok', _error = '';
  try {
    var contentStr = raw && raw.choices && raw.choices[0] && raw.choices[0].message
      ? raw.choices[0].message.content : '';
    var parsed = JSON.parse(contentStr);
    research_summary = s(parsed.research_summary);
    confidence = s(parsed.confidence == null ? 'low' : parsed.confidence).toLowerCase();
  } catch (e) {
    _status = 'dead';
    _error = 'bad_research: Perplexity payload was not valid JSON';
  }
  return Object.assign({}, lead, {
    research_summary: research_summary, confidence: confidence, _status: _status, _error: _error
  });
}

// call Claude only when research is usable (mirrors the "Call Claude?" IF node)
function shouldCallClaude(d) {
  return d._status !== 'dead' && d.confidence !== 'low';
}

// low-confidence or dead-research short-circuit (no Claude call)
function noContextLine(d) {
  var line = d._status === 'dead' ? '' : '[NO_CONTEXT]';
  return Object.assign({}, d, { Personalized_First_Line: line });
}

// ---- MOCK Anthropic: returns the Messages API shape; line in content[0].text -
function mockAnthropic(d) {
  var scenario = s(d._mock_scenario).trim().toLowerCase();
  var text;
  if (scenario === 'empty_line') {
    text = '';
  } else {
    var who = d.First_Name ? d.First_Name : 'there';
    var co = d.Company_Name ? d.Company_Name : 'your company';
    text = 'Saw the recent milestone over at ' + co + ' — genuinely impressive work, ' + who + '.';
  }
  return {
    id: 'msg_mock_' + leadHash(d),
    type: 'message', role: 'assistant',
    model: 'claude-sonnet-4-5-20250929',
    content: [{ type: 'text', text: text }],
    stop_reason: 'end_turn',
    usage: { input_tokens: 0, output_tokens: 0 }
  };
}

// ---- shared extractor (question a): raw anthropic shape -> first line ----
function extractFirstLine(raw, norm) {
  var text = '', _status = norm._status || 'ok', _error = norm._error || '';
  try { text = s(raw.content[0].text); } catch (e) { text = ''; }
  if (!text || !text.trim()) {
    _status = 'dead';
    _error = 'empty_line: model returned no first line';
  }
  return Object.assign({}, norm, { Personalized_First_Line: text, _status: _status, _error: _error });
}

// ---- the single choke point: build {tab,row} with ONLY the locked columns ----
// [MOCK] prefixes the two LLM-output columns in mock mode, but NEVER wraps the
// [NO_CONTEXT] sentinel (operators + verify_loomless_batch.py match it exactly)
// and never a lone-prefix on empties.
function buildRow(d, mode) {
  var isMock = mode === 'mock';
  var px = '[MOCK] ';
  var status = d._status === 'dead' ? 'dead' : 'ready_for_review';
  var rs = s(d.research_summary);
  var line = s(d.Personalized_First_Line);
  var research = (isMock && rs) ? px + rs : rs;
  var isSentinel = line === '[NO_CONTEXT]';
  var firstLine = (isMock && line && !isSentinel) ? px + line : line;
  return { tab: 'Loomless', row: {
/*LEAD_ASSIGNS*/
      Research_Summary: research,
      Personalized_First_Line: firstLine,
      status: status
  } };
}

// ---- batch guard + fail-closed safety asserts (run once for all items) ----
function guardCheck(rows, env) {
  var REQUIRED = /*REQUIRED*/;
  var mode = s(env.LOOMLESS_MODE || 'mock');
  var batchSize = parseInt(env.LOOMLESS_BATCH_SIZE || '100', 10);
  var gsheet = s(env.GOOGLE_SHEET_ID);
  var devsheet = s(env.LOOMLESS_DEV_SHEET_ID);
  function err(reason, message, fields) {
    return { ok: false, errorItem: {
      _guard_error: 'yes', level: 'error', pipeline: 'loomless',
      message: message, fields: Object.assign({ reason: reason, mode: mode }, fields || {})
    } };
  }
  // layer-3 fail-closed dev-sheet guard: in mock mode, refuse unless the target
  // Sheet IS the known dev Sheet (allowlist, not a pattern match).
  if (mode === 'mock' && gsheet !== devsheet) {
    return err('sheet_guard',
      'Loomless batch REFUSED: mock mode but GOOGLE_SHEET_ID != LOOMLESS_DEV_SHEET_ID (fail-closed)',
      { google_sheet_len: gsheet.length, dev_sheet_len: devsheet.length });
  }
  if (!rows || rows.length === 0) {
    return err('empty_csv', 'Loomless batch rejected: CSV produced zero rows', { rows: 0 });
  }
  var first = rows[0] || {};
  var missing = REQUIRED.filter(function (c) { return !(c in first); });
  if (missing.length) {
    return err('missing_columns',
      'Loomless batch rejected: CSV missing required column(s): ' + missing.join(', '),
      { missing: missing.join(','), got: Object.keys(first).join(',') });
  }
  if (rows.length > batchSize) {
    return err('batch_too_large',
      'Loomless batch rejected: ' + rows.length + ' rows exceeds LOOMLESS_BATCH_SIZE=' + batchSize,
      { rows: rows.length, cap: batchSize });
  }
  return { ok: true };
}

// ---- aggregate write results into one Discord summary item ----
function aggregate(rows, mode) {
  var total = 0, ready = 0, noctx = 0, dead = 0;
  for (var i = 0; i < rows.length; i++) {
    var row = (rows[i] && rows[i].row) ? rows[i].row : rows[i]; // unwrap {success,tab,row}
    total++;
    var st = row.status;
    var line = s(row.Personalized_First_Line).replace(/^\[MOCK\]\s+/, '');
    if (st === 'dead') { dead++; }
    else { ready++; if (line.trim() === '[NO_CONTEXT]') { noctx++; } }
  }
  return {
    level: 'info',
    pipeline: 'loomless',
    message: 'Loomless batch ready: ' + total + ' rows — ' + ready + ' ready_for_review ('
      + noctx + ' [NO_CONTEXT]), ' + dead + ' dead [mode=' + mode + ']',
    fields: { total: total, ready_for_review: ready, no_context: noctx, dead: dead, mode: mode }
  };
}
""".replace("/*LEAD_ASSIGNS*/", _LEAD_ASSIGNS).replace(
    "/*REQUIRED*/", json.dumps(REQUIRED_COLS)
)


# ─────────────────────────────────────────────────────────────────────────────
# n8n node builders
# ─────────────────────────────────────────────────────────────────────────────

RL_SUB_WRITE = "REPLACE_WITH_Sub_WriteRowToSheet_ID"
RL_SUB_DISCORD = "REPLACE_WITH_Sub_NotifyDiscord_ID"
RL_INBOX = "REPLACE_WITH_Loomless_Inbox_FOLDER_ID"
RL_PROCESSED = "REPLACE_WITH_Loomless_Inbox_processed_FOLDER_ID"
RL_REJECTED = "REPLACE_WITH_Loomless_Inbox_rejected_FOLDER_ID"
RL_CRED = "REPLACE_WITH_Google_SA_CREDENTIAL_ID"
CRED_NAME = "Google Sheets — OPS-61 SA"


def code_node(name, node_id, pos, js, per_item=False, on_error=None):
    p = {"mode": "runOnceForEachItem" if per_item else "runOnceForAllItems", "jsCode": js}
    node = {
        "parameters": p, "id": node_id, "name": name,
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": pos,
    }
    if on_error:
        node["onError"] = on_error
    return node


def if_node(name, node_id, pos, left, op_operation, right, op_type="string", combinator="and", extra=None):
    conditions = [{
        "id": "c1", "leftValue": left, "rightValue": right,
        "operator": {"type": op_type, "operation": op_operation},
    }]
    if extra:
        conditions.append(extra)
    return {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                "conditions": conditions, "combinator": combinator,
            },
            "options": {},
        },
        "id": node_id, "name": name, "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": pos,
    }


def exec_wf(name, node_id, pos, rl_value, cached_name, on_error=None):
    node = {
        "parameters": {
            "source": "database",
            "workflowId": {"__rl": True, "value": rl_value, "mode": "list", "cachedResultName": cached_name},
            "options": {},
        },
        "id": node_id, "name": name, "type": "n8n-nodes-base.executeWorkflow",
        "typeVersion": 1.2, "position": pos,
    }
    if on_error:
        node["onError"] = on_error
    return node


def merge_node(name, node_id, pos):
    return {
        "parameters": {"numberInputs": 2, "mode": "append"},
        "id": node_id, "name": name, "type": "n8n-nodes-base.merge",
        "typeVersion": 3, "position": pos,
    }


def sticky(name, node_id, pos, content, w=380, h=260, color=7):
    return {
        "parameters": {"content": content, "height": h, "width": w, "color": color},
        "id": node_id, "name": name, "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1, "position": pos,
    }


# thin n8n wrappers around the shared JS_LIB funcs -----------------------------
W_GUARD = JS_LIB + """
const items = $input.all();
const chk = guardCheck(items.map(i => i.json), $env);
if (!chk.ok) { return [{ json: chk.errorItem }]; }
return items;  // pass through unchanged (preserves pairedItem lineage)
"""

W_MOCK_PPLX = JS_LIB + """
return { json: mockPplx($json) };
"""

W_NORMALIZE = JS_LIB + """
const lead = $('Extract Rows from CSV').item.json;
return { json: normalizeResearch($json, lead) };
"""

W_NOCTX = JS_LIB + """
return { json: noContextLine($json) };
"""

W_MOCK_ANTHROPIC = JS_LIB + """
return { json: mockAnthropic($json) };
"""

W_EXTRACT = JS_LIB + """
const norm = $('Normalize Research').item.json;
return { json: extractFirstLine($json, norm) };
"""

W_BUILD = JS_LIB + """
return { json: buildRow($json, $env.LOOMLESS_MODE) };
"""

W_AGG = JS_LIB + """
const rows = $input.all().map(i => i.json);
return [{ json: aggregate(rows, $env.LOOMLESS_MODE) }];
"""

# live-mode HTTP bodies (parked behind the live IF; UNTUNED — tuned in BS#6) ----
PPLX_SYSTEM = (
    "You are a precise B2B research assistant. Search the live web and LinkedIn for RECENT, "
    "SPECIFIC, verifiable facts about a person and their company. Return ONLY a single JSON "
    "object: {\"research_summary\": string, \"confidence\": \"high\"|\"medium\"|\"low\", "
    "\"source_hints\": string[]}. Prefer facts from the last 30-60 days. If nothing specific and "
    "recent, set confidence to \"low\". Never invent."
)
CLAUDE_SYSTEM = (
    "You are an expert cold-email copywriter (EasyGrow \"Loomless\"). Write ONE first line: one "
    "sentence, under 30 words, conversational, referencing the SPECIFIC research context "
    "(paraphrased, never quoted). No marketing-speak, no emojis. If the research has no usable "
    "specific context, respond with exactly [NO_CONTEXT] and nothing else. Output ONLY the line."
)


def http_perplexity(node_id, pos):
    body = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": PPLX_SYSTEM},
            {"role": "user", "content": "=Research this lead for a personalized cold-email opening line.\\n\\n"
                "First name: {{ $json.First_Name }}\\nFull name: {{ $json.Owner_Full_Name }}\\n"
                "Company: {{ $json.Company_Name }}\\nWebsite: {{ $json.Website }}\\n\\n"
                "Return the JSON object described in the system message. Nothing else."},
        ],
    }
    return {
        "parameters": {
            "method": "POST",
            "url": "https://api.perplexity.ai/chat/completions",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "Authorization", "value": "=Bearer {{ $env.PERPLEXITY_API_KEY }}"},
                {"name": "Content-Type", "value": "application/json"},
            ]},
            "sendBody": True, "specifyBody": "json",
            "jsonBody": "={{ " + json.dumps(body) + " }}",
            "options": {},
        },
        "id": node_id, "name": "HTTP — Perplexity (live)",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": pos,
        "onError": "continueRegularOutput",
    }


def http_anthropic(node_id, pos):
    body = {
        "model": "claude-sonnet-4-5-20250929",
        "max_tokens": 120,
        "system": CLAUDE_SYSTEM,
        "messages": [
            {"role": "user", "content": "=Lead first name: {{ $json.First_Name }}\\nCompany: {{ $json.Company_Name }}\\n\\n"
                "Research summary (from live web/LinkedIn research):\\n{{ $json.research_summary }}\\n\\nWrite the first line."},
        ],
    }
    return {
        "parameters": {
            "method": "POST",
            "url": "https://api.anthropic.com/v1/messages",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "x-api-key", "value": "={{ $env.ANTHROPIC_API_KEY }}"},
                {"name": "anthropic-version", "value": "2023-06-01"},
                {"name": "Content-Type", "value": "application/json"},
            ]},
            "sendBody": True, "specifyBody": "json",
            "jsonBody": "={{ " + json.dumps(body) + " }}",
            "options": {},
        },
        "id": node_id, "name": "HTTP — Anthropic (live)",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": pos,
        "onError": "continueRegularOutput",
    }


def build_workflow():
    nodes = []

    # trigger + ingest ---------------------------------------------------------
    nodes.append({
        "parameters": {
            "authentication": "serviceAccount",
            "pollTimes": {"item": [{"mode": "everyMinute"}]},
            "triggerOn": "specificFolder",
            "folderToWatch": {"__rl": True, "value": RL_INBOX, "mode": "list", "cachedResultName": "Loomless-Inbox"},
            "event": "fileCreated",
            "options": {},
        },
        "id": "loomless-0001", "name": "Watch Loomless-Inbox (.csv)",
        "type": "n8n-nodes-base.googleDriveTrigger", "typeVersion": 1, "position": [-1560, 300],
        "credentials": {"googleApi": {"id": RL_CRED, "name": CRED_NAME}},
    })
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": False, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [{
                    "id": "csv", "leftValue": "={{ ($json.name || $json.fileName || '').toLowerCase() }}",
                    "rightValue": ".csv", "operator": {"type": "string", "operation": "endsWith"},
                }],
                "combinator": "and",
            },
            "options": {},
        },
        "id": "loomless-0002", "name": "Filter — .csv only",
        "type": "n8n-nodes-base.filter", "typeVersion": 2.2, "position": [-1340, 300],
    })
    nodes.append({
        "parameters": {
            "authentication": "serviceAccount",
            "operation": "download",
            "fileId": {"__rl": True, "value": "={{ $json.id }}", "mode": "id"},
            "options": {"binaryPropertyName": "data"},
        },
        "id": "loomless-0003", "name": "Download CSV",
        "type": "n8n-nodes-base.googleDrive", "typeVersion": 3, "position": [-1120, 300],
        "credentials": {"googleApi": {"id": RL_CRED, "name": CRED_NAME}},
        "onError": "continueRegularOutput",
    })
    nodes.append({
        "parameters": {"operation": "csv", "binaryPropertyName": "data", "options": {}},
        "id": "loomless-0004", "name": "Extract Rows from CSV",
        "type": "n8n-nodes-base.extractFromFile", "typeVersion": 1, "position": [-900, 300],
    })

    # guard --------------------------------------------------------------------
    nodes.append(code_node("Guard — batch/columns/dev-sheet", "loomless-0005", [-680, 300], W_GUARD))
    nodes.append(if_node("Guard failed?", "loomless-0006", [-460, 300],
                         "={{ $json._guard_error }}", "equals", "yes"))
    nodes.append(exec_wf("Notify — batch rejected", "loomless-0007", [-460, 520],
                         RL_SUB_DISCORD, "Sub_NotifyDiscord"))
    # Option A: park the rejected CSV out of the inbox so the Drive Trigger can't
    # re-fire on it every poll (infinite reject loop). Folder is ID-referenced, so
    # OPS-61/Loomless-Inbox/rejected/ must exist + be wired at STEP 3.
    nodes.append({
        "parameters": {
            "authentication": "serviceAccount",
            "operation": "move",
            "fileId": {"__rl": True, "value": "={{ $('Watch Loomless-Inbox (.csv)').first().json.id }}", "mode": "id"},
            "driveId": {"__rl": True, "value": "My Drive", "mode": "list", "cachedResultName": "My Drive"},
            "folderId": {"__rl": True, "value": RL_REJECTED, "mode": "list", "cachedResultName": "rejected"},
            "options": {},
        },
        "id": "loomless-0027", "name": "Move CSV → rejected/",
        "type": "n8n-nodes-base.googleDrive", "typeVersion": 3, "position": [-240, 520],
        "credentials": {"googleApi": {"id": RL_CRED, "name": CRED_NAME}},
        "onError": "continueRegularOutput",
    })
    nodes.append({
        "parameters": {"errorType": "errorMessage",
                       "errorMessage": "={{ $json.message || 'Loomless batch rejected by guard' }}"},
        "id": "loomless-0008", "name": "Stop — batch rejected",
        "type": "n8n-nodes-base.stopAndError", "typeVersion": 1, "position": [-20, 520],
    })

    # perplexity dual path -----------------------------------------------------
    nodes.append(if_node("Mode = live? (Perplexity)", "loomless-0009", [-240, 300],
                         "={{ $env.LOOMLESS_MODE }}", "equals", "live"))
    nodes.append(http_perplexity("loomless-0010", [-20, 180]))
    nodes.append(code_node("Mock — Perplexity", "loomless-0011", [-20, 400], W_MOCK_PPLX, per_item=True))
    nodes.append(merge_node("Merge — Perplexity paths", "loomless-0012", [200, 300]))
    nodes.append(code_node("Normalize Research", "loomless-0013", [420, 300], W_NORMALIZE, per_item=True))

    # confidence short-circuit + anthropic dual path ---------------------------
    nodes.append(if_node("Call Claude?", "loomless-0014", [640, 300],
                         "={{ $json._status }}", "notEquals", "dead",
                         extra={"id": "c2", "leftValue": "={{ $json.confidence }}",
                                "rightValue": "low", "operator": {"type": "string", "operation": "notEquals"}}))
    nodes.append(code_node("Set — [NO_CONTEXT] / dead", "loomless-0015", [860, 480], W_NOCTX, per_item=True))
    nodes.append(if_node("Mode = live? (Anthropic)", "loomless-0016", [860, 220],
                         "={{ $env.LOOMLESS_MODE }}", "equals", "live"))
    nodes.append(http_anthropic("loomless-0017", [1080, 120]))
    nodes.append(code_node("Mock — Anthropic", "loomless-0018", [1080, 320], W_MOCK_ANTHROPIC, per_item=True))
    nodes.append(merge_node("Merge — Anthropic paths", "loomless-0019", [1300, 220]))
    nodes.append(code_node("Extract First Line", "loomless-0020", [1520, 220], W_EXTRACT, per_item=True))

    # rejoin + build + write ---------------------------------------------------
    nodes.append(merge_node("Merge — rejoin lead paths", "loomless-0021", [1740, 340]))
    nodes.append(code_node("Set: Build Loomless Row (Keep Only Set)", "loomless-0022", [1960, 340], W_BUILD, per_item=True))
    nodes.append(exec_wf("Sub_WriteRowToSheet", "loomless-0023", [2180, 340],
                         RL_SUB_WRITE, "Sub_WriteRowToSheet", on_error="continueRegularOutput"))

    # aggregate + notify + move ------------------------------------------------
    nodes.append(code_node("Aggregate Batch", "loomless-0024", [2400, 340], W_AGG))
    nodes.append(exec_wf("Sub_NotifyDiscord (summary)", "loomless-0025", [2620, 340],
                         RL_SUB_DISCORD, "Sub_NotifyDiscord"))
    nodes.append({
        "parameters": {
            "authentication": "serviceAccount",
            "operation": "move",
            "fileId": {"__rl": True, "value": "={{ $('Watch Loomless-Inbox (.csv)').first().json.id }}", "mode": "id"},
            "driveId": {"__rl": True, "value": "My Drive", "mode": "list", "cachedResultName": "My Drive"},
            "folderId": {"__rl": True, "value": RL_PROCESSED, "mode": "list", "cachedResultName": "processed"},
            "options": {},
        },
        "id": "loomless-0026", "name": "Move CSV → processed/",
        "type": "n8n-nodes-base.googleDrive", "typeVersion": 3, "position": [2840, 340],
        "credentials": {"googleApi": {"id": RL_CRED, "name": CRED_NAME}},
        "onError": "continueRegularOutput",
    })

    # sticky notes (drafted now; STEP 6 gate) ----------------------------------
    nodes.append(sticky("Doc — Overview", "loomless-note-1", [-1560, -220], (
        "## OPS-61 · Pipeline 1 — Loomless (mock-based dev)\n\n"
        "**Purpose:** CSV of leads → per-lead research + ONE personalized first line → `Loomless` tab → Discord summary.\n"
        "**In:** Drive `OPS-61/Loomless-Inbox/*.csv` (cols: " + ", ".join(LEAD_COLS) + ").\n"
        "**Out:** `Loomless` rows (`status=ready_for_review` | `dead`) + `#ops-61-feed` ping.\n\n"
        "**Automation stops at logging — no email is ever sent (locked constraint).**\n\n"
        "Depends on: `Sub_WriteRowToSheet`, `Sub_NotifyDiscord` (locked Foundation primitives, used as-is)."
    ), w=560, h=300, color=4))
    nodes.append(sticky("Doc — UNTUNED banner", "loomless-note-2", [-960, -220], (
        "### ⚠️ UNTUNED — prompts are v0.1 drafts\n\n"
        "Per PLAN v8 / Decision #12, prompts are NOT tuned in this build. "
        "Real Perplexity/Anthropic calls, prompt tuning, and live cost measurement all move to **Build Spec #6 (migration)**.\n\n"
        "Prompt sources: `pipelines/01-loomless/prompts/`."
    ), w=360, h=300, color=3))
    nodes.append(sticky("Doc — Mock/Live toggle", "loomless-note-3", [-240, 40], (
        "### Mock/Live toggle — `$env.LOOMLESS_MODE`\n\n"
        "Each external call has TWO paths, chosen by the `Mode = live?` IF:\n"
        "- **mock** (dev default): the `Mock — …` Code node returns the **exact** API JSON shape.\n"
        "- **live** (BS#6): the `HTTP — …` node calls the real API.\n\n"
        "Both paths reconverge into ONE shared normalizer (`Normalize Research` / `Extract First Line`) so downstream is mode-agnostic.\n\n"
        "**To go live:** set `LOOMLESS_MODE=live` + provide real keys. That flip + tuning IS Build Spec #6."
    ), w=440, h=280, color=5))
    nodes.append(sticky("Doc — $env auth on live HTTP", "loomless-note-4", [-40, -40], (
        "### 🔑 Live HTTP nodes use `$env` header auth — NO n8n credential\n\n"
        "`HTTP — Perplexity`: `Authorization: Bearer {{ $env.PERPLEXITY_API_KEY }}`\n"
        "`HTTP — Anthropic`: `x-api-key: {{ $env.ANTHROPIC_API_KEY }}` + `anthropic-version: 2023-06-01`\n\n"
        "Deliberate: keeps the workflow credential-free except the Google SA. No 'Anthropic account' credential to wire. "
        "Model pinned **claude-sonnet-4-5-20250929**. Parked behind the live IF — they receive 0 items in mock mode and never execute."
    ), w=460, h=240, color=6))
    nodes.append(sticky("Doc — Mock scenarios", "loomless-note-5", [420, -80], (
        "### Deterministic mock scenarios\n"
        "Branch keyed off `First_Name` or optional `_mock_scenario` CSV column:\n\n"
        "| Trigger | Result row |\n|---|---|\n"
        "| default | `ready_for_review`, real line |\n"
        "| `First_Name=Robert` / `_mock_scenario=no_context` | `ready_for_review`, `[NO_CONTEXT]` |\n"
        "| `_mock_scenario=bad_research` | `dead` (research JSON parse fails) |\n"
        "| `_mock_scenario=empty_line` | `dead` (Claude returns empty) |\n\n"
        "`[MOCK] ` prefixes `Research_Summary` + real first lines — but NEVER the `[NO_CONTEXT]` sentinel."
    ), w=460, h=280, color=5))
    nodes.append(sticky("Doc — Rejected CSVs", "loomless-note-7", [-460, 720], (
        "### 🗂️ Where CSVs go after a run\n\n"
        "- **Success:** `OPS-61/Loomless-Inbox/processed/`\n"
        "- **Guard rejection** (bad batch — oversize / missing cols / wrong Sheet):\n"
        "  Discord `❌ error` ping, then the CSV is **moved to** "
        "`OPS-61/Loomless-Inbox/rejected/`, then the run stops.\n\n"
        "Moving it out of the inbox stops the Drive Trigger re-firing on the same "
        "bad file every poll (reject loop). **Operator:** find rejected uploads in "
        "`rejected/`, fix, re-drop into the inbox.\n\n"
        "_Both `processed/` and `rejected/` are ID-referenced Drive folders — they "
        "must exist + be wired (STEP 3), unlike Sheet tabs which the Sub auto-creates._"
    ), w=440, h=280, color=2))
    nodes.append(sticky("Doc — Build row / safety", "loomless-note-6", [1900, 120], (
        "### `Set: Build Loomless Row` = the single choke point\n\n"
        "Emits ONLY `{ tab, row }` with the 8 locked data cols (Keep-Only-Set by construction — nothing passes implicitly). "
        "`created_at` is auto-stamped by `Sub_WriteRowToSheet`.\n\n"
        "**Safety (question c):** (1) dev/prod use different Sheets; (2) `[MOCK]` marker; "
        "(3) fail-closed guard: mock mode refuses to write unless `GOOGLE_SHEET_ID == LOOMLESS_DEV_SHEET_ID`.\n\n"
        "Continue-On-Fail on external + write nodes → a single bad lead becomes `status=dead`, batch continues."
    ), w=460, h=300, color=4))

    connections = {
        "Watch Loomless-Inbox (.csv)": {"main": [[{"node": "Filter — .csv only", "type": "main", "index": 0}]]},
        "Filter — .csv only": {"main": [[{"node": "Download CSV", "type": "main", "index": 0}]]},
        "Download CSV": {"main": [[{"node": "Extract Rows from CSV", "type": "main", "index": 0}]]},
        "Extract Rows from CSV": {"main": [[{"node": "Guard — batch/columns/dev-sheet", "type": "main", "index": 0}]]},
        "Guard — batch/columns/dev-sheet": {"main": [[{"node": "Guard failed?", "type": "main", "index": 0}]]},
        "Guard failed?": {"main": [
            [{"node": "Notify — batch rejected", "type": "main", "index": 0}],          # true  (output 0)
            [{"node": "Mode = live? (Perplexity)", "type": "main", "index": 0}],        # false (output 1)
        ]},
        "Notify — batch rejected": {"main": [[{"node": "Move CSV → rejected/", "type": "main", "index": 0}]]},
        "Move CSV → rejected/": {"main": [[{"node": "Stop — batch rejected", "type": "main", "index": 0}]]},
        "Mode = live? (Perplexity)": {"main": [
            [{"node": "HTTP — Perplexity (live)", "type": "main", "index": 0}],          # true
            [{"node": "Mock — Perplexity", "type": "main", "index": 0}],                 # false
        ]},
        "HTTP — Perplexity (live)": {"main": [[{"node": "Merge — Perplexity paths", "type": "main", "index": 0}]]},
        "Mock — Perplexity": {"main": [[{"node": "Merge — Perplexity paths", "type": "main", "index": 1}]]},
        "Merge — Perplexity paths": {"main": [[{"node": "Normalize Research", "type": "main", "index": 0}]]},
        "Normalize Research": {"main": [[{"node": "Call Claude?", "type": "main", "index": 0}]]},
        "Call Claude?": {"main": [
            [{"node": "Mode = live? (Anthropic)", "type": "main", "index": 0}],          # true  → Claude
            [{"node": "Set — [NO_CONTEXT] / dead", "type": "main", "index": 0}],         # false → short-circuit
        ]},
        "Mode = live? (Anthropic)": {"main": [
            [{"node": "HTTP — Anthropic (live)", "type": "main", "index": 0}],
            [{"node": "Mock — Anthropic", "type": "main", "index": 0}],
        ]},
        "HTTP — Anthropic (live)": {"main": [[{"node": "Merge — Anthropic paths", "type": "main", "index": 0}]]},
        "Mock — Anthropic": {"main": [[{"node": "Merge — Anthropic paths", "type": "main", "index": 1}]]},
        "Merge — Anthropic paths": {"main": [[{"node": "Extract First Line", "type": "main", "index": 0}]]},
        "Extract First Line": {"main": [[{"node": "Merge — rejoin lead paths", "type": "main", "index": 0}]]},
        "Set — [NO_CONTEXT] / dead": {"main": [[{"node": "Merge — rejoin lead paths", "type": "main", "index": 1}]]},
        "Merge — rejoin lead paths": {"main": [[{"node": "Set: Build Loomless Row (Keep Only Set)", "type": "main", "index": 0}]]},
        "Set: Build Loomless Row (Keep Only Set)": {"main": [[{"node": "Sub_WriteRowToSheet", "type": "main", "index": 0}]]},
        "Sub_WriteRowToSheet": {"main": [[{"node": "Aggregate Batch", "type": "main", "index": 0}]]},
        "Aggregate Batch": {"main": [[{"node": "Sub_NotifyDiscord (summary)", "type": "main", "index": 0}]]},
        "Sub_NotifyDiscord (summary)": {"main": [[{"node": "Move CSV → processed/", "type": "main", "index": 0}]]},
    }

    return {
        "name": "OPS-61_Loomless_Pipeline",
        "nodes": nodes,
        "connections": connections,
        "active": False,
        "settings": {"executionOrder": "v1"},
        "pinData": {},
        "meta": {"templateCredsSetupCompleted": False},
        "tags": [{"name": "ops-61"}, {"name": "loomless"}],
    }


def write_harness(path):
    driver = r"""
// Offline validation harness — drives the SAME JS_LIB functions the n8n Code
// nodes use, through the full per-lead flow, with no n8n and no external API.
function runLead(lead, mode) {
  const raw1 = mockPplx(lead);
  const norm = normalizeResearch(raw1, lead);
  let after;
  if (shouldCallClaude(norm)) {
    const raw2 = mockAnthropic(norm);
    after = extractFirstLine(raw2, norm);
  } else {
    after = noContextLine(norm);
  }
  return buildRow(after, mode);
}

const MODE = 'mock';
const leads = [
  { _scenario: 'normal',       lead: { Company_Name: 'Brightpath Coaching', Owner_Full_Name: 'Marcus Delaney', First_Name: 'Marcus', Email: 'marcus@brightpathcoaching.com', Website: 'https://brightpathcoaching.com' } },
  { _scenario: 'no_context',   lead: { Company_Name: 'Ironclad Roofing Co', Owner_Full_Name: 'Robert Nkemelu', First_Name: 'Robert', Email: 'rob@ironcladroofing.com', Website: 'https://ironcladroofing.com' } },
  { _scenario: 'bad_research', lead: { Company_Name: 'Northwind Digital', Owner_Full_Name: 'Sarah Whitmore', First_Name: 'Sarah', Email: 'sarah@northwinddigital.io', Website: 'https://northwinddigital.io', _mock_scenario: 'bad_research' } },
  { _scenario: 'empty_line',   lead: { Company_Name: 'Lumen Analytics', Owner_Full_Name: 'Elena Kovac', First_Name: 'Elena', Email: 'elena@lumenanalytics.ai', Website: 'https://lumenanalytics.ai', _mock_scenario: 'empty_line' } },
];

console.log('=== PER-LEAD (mode=' + MODE + ') ===');
const results = [];
for (const t of leads) {
  const out = runLead(t.lead, MODE);
  results.push(out);
  console.log('\n--- scenario: ' + t._scenario + ' ---');
  console.log('status                 :', out.row.status);
  console.log('Personalized_First_Line:', JSON.stringify(out.row.Personalized_First_Line));
  console.log('Research_Summary       :', JSON.stringify(out.row.Research_Summary));
  console.log('lead cols intact       :', ['Company_Name','Owner_Full_Name','First_Name','Email','Website'].every(c => c in out.row));
  console.log('extra keys leaked      :', Object.keys(out.row).filter(k => !EXPECTED_ROW_KEYS.includes(k)));
}

console.log('\n=== AGGREGATE ===');
console.log(JSON.stringify(aggregate(results.map(r => r.row), MODE).message));

console.log('\n=== EDGE: all-no_context batch (3x Robert) — must be 3 rows, NOT 0 ===');
const allNoCtx = [
  { Company_Name: 'Ironclad Roofing Co', Owner_Full_Name: 'Robert Nkemelu', First_Name: 'Robert', Email: 'rob@ironcladroofing.com', Website: 'https://ironcladroofing.com' },
  { Company_Name: 'Redstone Builders',   Owner_Full_Name: 'Robert Alvarez', First_Name: 'Robert', Email: 'robert@redstonebuilders.com', Website: 'https://redstonebuilders.com' },
  { Company_Name: 'Kingfisher Plumbing', Owner_Full_Name: 'Robert Osei',    First_Name: 'Robert', Email: 'rob@kingfisherplumbing.com', Website: 'https://kingfisherplumbing.com' },
];
const noCtxRows = allNoCtx.map(l => runLead(l, MODE).row);
noCtxRows.forEach((r, i) => console.log('  row ' + (i + 1) + ': status=' + r.status +
  ' line=' + JSON.stringify(r.Personalized_First_Line) +
  ' research_has_MOCK=' + /^\[MOCK\] /.test(r.Research_Summary)));
const agg2 = aggregate(noCtxRows, MODE);
const edgeOk = agg2.fields.total === 3 && agg2.fields.ready_for_review === 3 &&
  agg2.fields.no_context === 3 && agg2.fields.dead === 0 &&
  noCtxRows.every(r => r.Personalized_First_Line === '[NO_CONTEXT]');
console.log('  aggregate:', JSON.stringify(agg2.fields));
console.log('  EDGE PASS (logic yields 3 clean [NO_CONTEXT] rows):', edgeOk);
console.log('  NOTE: n8n Merge skipped-branch behavior is verified at runtime in STEP 3 via Sheets API.');

console.log('\n=== GUARD checks ===');
const devEnv = { LOOMLESS_MODE: 'mock', LOOMLESS_BATCH_SIZE: '100', GOOGLE_SHEET_ID: 'SHEET_DEV', LOOMLESS_DEV_SHEET_ID: 'SHEET_DEV' };
const okRows = leads.map(t => t.lead);
console.log('valid batch ok         :', JSON.stringify(guardCheck(okRows, devEnv)));
console.log('oversize (cap=2)       :', JSON.stringify(guardCheck(okRows, Object.assign({}, devEnv, { LOOMLESS_BATCH_SIZE: '2' })).errorItem.fields.reason));
console.log('missing columns        :', JSON.stringify(guardCheck([{ First_Name: 'X' }], devEnv).errorItem.fields.reason));
console.log('sheet mismatch (mock)  :', JSON.stringify(guardCheck(okRows, Object.assign({}, devEnv, { GOOGLE_SHEET_ID: 'SHEET_PROD' })).errorItem.fields.reason));
console.log('empty csv              :', JSON.stringify(guardCheck([], devEnv).errorItem.fields.reason));
"""
    expected_keys = "const EXPECTED_ROW_KEYS = " + json.dumps(
        LEAD_COLS + ["Research_Summary", "Personalized_First_Line", "status"]
    ) + ";\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(JS_LIB + "\n" + expected_keys + driver)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.abspath(os.path.join(here, "..", "n8n-templates", "OPS-61_Loomless_Pipeline.json"))
    wf = build_workflow()
    with open(out, "w", encoding="utf-8") as f:
        json.dump(wf, f, indent=2, ensure_ascii=False)
        f.write("\n")
    n_real = len([n for n in wf["nodes"] if n["type"] != "n8n-nodes-base.stickyNote"])
    n_note = len([n for n in wf["nodes"] if n["type"] == "n8n-nodes-base.stickyNote"])
    print(f"wrote {out}")
    print(f"  functional nodes: {n_real}, sticky notes: {n_note}, total: {len(wf['nodes'])}")
    print(f"  Loomless cols (from schema.py): {LOOMLESS_COLS}")

    if "--harness" in sys.argv:
        hp = None
        for a in sys.argv:
            if a.startswith("--harness-out="):
                hp = a.split("=", 1)[1]
        if not hp:
            hp = os.path.join(here, "loomless_harness.js")
        write_harness(hp)
        print(f"wrote harness {hp}")


if __name__ == "__main__":
    main()
