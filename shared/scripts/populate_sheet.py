#!/usr/bin/env python3
"""Format an existing OPS-61 CRM Sheet to the exact 4-tab schema.

What it does (idempotent — safe to re-run):
  * Ensures the four tabs exist: Loomless, JV_Targets, Terminator_Loom, Inbound
  * Writes the exact header row (row 1) for each from schema.py
  * Freezes row 1 and bolds the header cells
  * Removes a leftover default "Sheet1" if it's empty and not one of ours

It does NOT create the spreadsheet. Create an empty Sheet manually, share it
with the Service Account email as Editor, put its ID in .env as
GOOGLE_SHEET_ID, then run this. (Editing an existing Sheet the SA can access
sidesteps Service-Account Drive-storage quota issues — see FOUNDATION_SETUP.md.)

Usage:
    pip install -r shared/scripts/requirements.txt
    python shared/scripts/populate_sheet.py
"""
import sys

from _common import build_service, load_env, require_env
from schema import TABS


def main():
    load_env()
    sheet_id = require_env("GOOGLE_SHEET_ID")
    svc = build_service("sheets", "v4").spreadsheets()

    meta = svc.get(spreadsheetId=sheet_id).execute()
    existing = {s["properties"]["title"]: s["properties"] for s in meta["sheets"]}
    print(f"Connected to '{meta['properties']['title']}' ({sheet_id})")
    print(f"Existing tabs: {', '.join(existing) or '(none)'}\n")

    requests = []

    # 1. Create any missing tabs.
    for title in TABS:
        if title not in existing:
            requests.append({"addSheet": {"properties": {"title": title}}})
            print(f"  + will create tab '{title}'")
    if requests:
        svc.batchUpdate(spreadsheetId=sheet_id, body={"requests": requests}).execute()
        # refresh ids for the newly created sheets
        meta = svc.get(spreadsheetId=sheet_id).execute()
        existing = {s["properties"]["title"]: s["properties"] for s in meta["sheets"]}
        requests = []

    # 2. Write headers (values) for each tab.
    value_data = [
        {"range": f"'{title}'!A1", "values": [headers]}
        for title, headers in TABS.items()
    ]
    svc.values().batchUpdate(
        spreadsheetId=sheet_id,
        body={"valueInputOption": "RAW", "data": value_data},
    ).execute()
    print("  ✓ headers written for all 4 tabs")

    # 3. Freeze + bold the header row on each tab.
    for title, headers in TABS.items():
        sid = existing[title]["sheetId"]
        requests.append(
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sid,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            }
        )
        requests.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sid,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": len(headers),
                    },
                    "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                    "fields": "userEnteredFormat.textFormat.bold",
                }
            }
        )

    # 4. Drop a stray empty default "Sheet1" if it isn't one of ours.
    if "Sheet1" not in TABS and "Sheet1" in existing:
        requests.append({"deleteSheet": {"sheetId": existing["Sheet1"]["sheetId"]}})
        print("  - will remove leftover default 'Sheet1'")

    svc.batchUpdate(spreadsheetId=sheet_id, body={"requests": requests}).execute()
    print("  ✓ headers frozen + bolded")
    print("\nDone. Sheet matches shared/sheets-schema.md.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - surface a clean message to the operator
        sys.exit(f"ERROR: {type(exc).__name__}: {exc}")
