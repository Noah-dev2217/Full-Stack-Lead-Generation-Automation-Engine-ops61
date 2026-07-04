# MIGRATION_NOTE — OPS-61 Loomless (Build Spec #6 handoff)

> Read this before migrating the Loomless pipeline to the company server.

## Canonical workflow source

**The canonical, authoritative Loomless workflow is the running state in the
n8n UI**, exported to `shared/n8n-templates/OPS-61_Loomless_Pipeline.json` via
n8n's own export (workflow **⋯ → Download**, or the REST API). That exported
JSON is the deploy artifact.

**`shared/scripts/build_loomless_workflow.py` is NOT the authoritative source.**
It is a schema-driven **reference snapshot** generator: it emits placeholder IDs
and rebuilds the node bodies from `schema.py` + the CSV fixtures. Do **not** run
it expecting to reproduce the live workflow — it will overwrite the exported
JSON with a placeholder template that is missing the live wiring.

### ⚠️ Naming fix pending (Commit 2)

`build_loomless_workflow.py` is **misleadingly named** — "build" implies it
produces the deploy artifact, which it does not. Planned for **Commit 2**:
rename to `snapshot_loomless_from_schema.py` with a clarifying header, paired
with `snapshot_diff` tooling (below).

## Importing on the target machine (BS#6)

The exported JSON references **dev-machine-specific IDs** — the Google Service
Account credential ID, the `Sub_WriteRowToSheet` / `Sub_NotifyDiscord`
sub-workflow IDs, and the Drive `Loomless-Inbox` / `processed` / `rejected`
folder IDs. **None of these exist on the target machine.** On import you MUST
re-wire, by **ID** (not display name):

- the Google Service Account credential — on the Drive Trigger and on the two
  Sub-workflows' Sheets/Drive nodes;
- the two sub-workflow references (`Sub_WriteRowToSheet`, `Sub_NotifyDiscord`);
- the three Drive folder IDs.

**Specific dev-machine IDs baked into the current export — search the JSON for
each and replace every occurrence on the target:**

| Binding | Dev-machine ID (in this export) | Replace with |
|---|---|---|
| Google Service Account credential | `7qRcnJxTR7hiwTUB` | the target's SA credential ID |
| `Sub_WriteRowToSheet` sub-workflow | `DqGdbRqflR4c03xR` | the target's imported sub-workflow ID |
| `Sub_NotifyDiscord` sub-workflow | `hBlQP46p1R8vZyvy` | the target's imported sub-workflow ID |
| Drive `Loomless-Inbox` / `processed` / `rejected` folders | `REPLACE_WITH_Loomless_Inbox*_FOLDER_ID` (still placeholders — never wired in dev) | the target folder IDs |

**Do NOT trust n8n's auto-wire on a cross-machine import.** n8n binds by ID, not
display name — a same-named credential or sub-workflow on the target has a
*different* ID, so an un-remapped node silently points at a dead reference. This
is the exact **credential-ghost failure** already hit in dev: a node bound to a
dead ID reports success but writes nothing (masked further by Continue-On-Fail).
After import, verify every credential / sub / folder binding **by ID**, not by
the name n8n displays.

## snapshot_diff tooling (planned — BS#6 audit)

A future `snapshot_diff` utility will compare the schema-driven reference
snapshot against the live export to surface drift (params/nodes changed in the
UI but not in the reference, or vice-versa), giving the migration operator an
audit trail before cutover.

## Go-live flip (unchanged from Build Spec #2)

Set `LOOMLESS_MODE=live`, provide real `PERPLEXITY_API_KEY` +
`ANTHROPIC_API_KEY`, point `LOOMLESS_DEV_SHEET_ID` / `GOOGLE_SHEET_ID` at the
production Sheet, then run one real batch and tune the prompts
(`pipelines/01-loomless/prompts/`, 7/10 & 8/10 gates). The live HTTP nodes
already exist behind the `Mode = live?` IF — going live is a config flip +
tuning pass, no workflow surgery.
