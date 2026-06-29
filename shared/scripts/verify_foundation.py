#!/usr/bin/env python3
"""Non-n8n smoke test for the OPS-61 foundation.

Proves the Service Account can write every tab and the Discord webhook fires —
the same checks the n8n Smoke_Test_Foundation workflow performs, but runnable
straight from the repo without touching n8n. Useful to validate creds before
wiring n8n, and as a standalone health check.

    python shared/scripts/verify_foundation.py            # write 4 rows + ping
    python shared/scripts/verify_foundation.py --cleanup  # delete SMOKE_TEST rows
    python shared/scripts/verify_foundation.py --no-discord

Every written row carries the literal SMOKE_TEST marker so --cleanup can find
and remove them.
"""
import argparse
import datetime as dt
import sys

from _common import build_service, load_env, require_env
from schema import TABS, TIMESTAMP_COLUMN

MARKER = "SMOKE_TEST"

# Field values for the smoke row, keyed by column. Columns absent here default
# to MARKER; the per-tab timestamp column is filled with current UTC ISO.
SMOKE_OVERRIDES = {
    "Loomless": {"status": "pending", "Email": "smoke@test.local"},
    "JV_Targets": {"status": "jv_research_complete", "Email": "smoke@test.local"},
    "Terminator_Loom": {"status": "ready_for_video", "First_Name": "Smoke", "Last_Name": "Test"},
    "Inbound": {
        "status": "warm_inbound",
        "Q3_DM_Permission": "Yes",
        "operator_action": "direct_intent_calendly",
    },
}


def utc_now_iso():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_row(tab):
    overrides = SMOKE_OVERRIDES.get(tab, {})
    ts_col = TIMESTAMP_COLUMN[tab]
    row = []
    for col in TABS[tab]:
        if col in overrides:
            row.append(overrides[col])
        elif col == ts_col:
            row.append(utc_now_iso())
        else:
            row.append(MARKER)
    return row


def write_rows(sheets, sheet_id):
    for tab in TABS:
        sheets.values().append(
            spreadsheetId=sheet_id,
            range=f"'{tab}'!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [build_row(tab)]},
        ).execute()
        print(f"  ✓ wrote SMOKE_TEST row to '{tab}'")


def cleanup_rows(sheets, sheet_id):
    meta = sheets.get(spreadsheetId=sheet_id).execute()
    ids = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    total = 0
    for tab in TABS:
        if tab not in ids:
            continue
        values = (
            sheets.values()
            .get(spreadsheetId=sheet_id, range=f"'{tab}'!A:Z")
            .execute()
            .get("values", [])
        )
        # row 0 is the header; flag any data row containing the marker
        hits = [i for i, r in enumerate(values) if i > 0 and MARKER in r]
        # delete bottom-up so indices stay valid
        requests = [
            {
                "deleteDimension": {
                    "range": {
                        "sheetId": ids[tab],
                        "dimension": "ROWS",
                        "startIndex": i,
                        "endIndex": i + 1,
                    }
                }
            }
            for i in sorted(hits, reverse=True)
        ]
        if requests:
            sheets.batchUpdate(
                spreadsheetId=sheet_id, body={"requests": requests}
            ).execute()
        print(f"  ✓ removed {len(hits)} SMOKE_TEST row(s) from '{tab}'")
        total += len(hits)
    print(f"Cleanup complete: {total} row(s) removed.")


def ping_discord():
    import requests  # type: ignore

    url = require_env("DISCORD_WEBHOOK_OPS61_FEED")
    payload = {
        "embeds": [
            {
                "title": "ℹ️ [loomless] Foundation smoke test fired",
                "description": "verify_foundation.py wrote a SMOKE_TEST row to all 4 tabs.",
                "color": 0x3498DB,
                "footer": {"text": "OPS-61 foundation"},
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
        ]
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    print("  ✓ Discord webhook posted (HTTP %s)" % resp.status_code)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cleanup", action="store_true", help="delete SMOKE_TEST rows and exit")
    parser.add_argument("--no-discord", action="store_true", help="skip the Discord ping")
    args = parser.parse_args()

    load_env()
    sheet_id = require_env("GOOGLE_SHEET_ID")
    sheets = build_service("sheets", "v4").spreadsheets()

    if args.cleanup:
        cleanup_rows(sheets, sheet_id)
        return

    write_rows(sheets, sheet_id)
    if not args.no_discord:
        ping_discord()
    print("\nSmoke test passed. Run with --cleanup to remove the test rows.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"ERROR: {type(exc).__name__}: {exc}")
