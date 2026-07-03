#!/usr/bin/env python3
"""Verify a Loomless batch straight from the Google Sheet (source of truth).

Reads the last N rows of the `Loomless` tab via the Sheets API — NOT the n8n
canvas — and reports counts by status, plus how many are the `[NO_CONTEXT]`
sentinel and how many carry the mock `[MOCK] ` marker. This is the Foundation
lesson: a green n8n run is not proof; check the actual data.

    python shared/scripts/verify_loomless_batch.py                 # last 10 rows
    python shared/scripts/verify_loomless_batch.py --last 3        # last 3 rows
    python shared/scripts/verify_loomless_batch.py --last 3 --json # machine output
    python shared/scripts/verify_loomless_batch.py --cleanup-last 3  # delete last 3 data rows

Reuses _common.py (Service Account auth) + schema.py (locked column order).
`--cleanup-last N` deletes the bottom N data rows so a mock smoke run is
re-runnable; it prints a preview first and refuses if any of those rows do NOT
look like a mock/dev row (guards against nuking real data).
"""
import argparse
import json
import sys

from _common import build_service, load_env, require_env
from schema import TABS

TAB = "Loomless"
COLS = TABS[TAB]
MOCK_PREFIX = "[MOCK] "
SENTINEL = "[NO_CONTEXT]"


def read_rows(sheets, sheet_id):
    values = (
        sheets.values()
        .get(spreadsheetId=sheet_id, range=f"'{TAB}'!A:Z")
        .execute()
        .get("values", [])
    )
    if not values:
        return [], []
    header = values[0]
    data = values[1:]
    rows = []
    for r in data:
        # pad short rows so every column resolves
        padded = r + [""] * (len(header) - len(r))
        rows.append(dict(zip(header, padded)))
    return header, rows


def strip_mock(v):
    return v[len(MOCK_PREFIX):] if v.startswith(MOCK_PREFIX) else v


def classify(row):
    status = (row.get("status") or "").strip()
    line = strip_mock((row.get("Personalized_First_Line") or "").strip())
    is_noctx = line == SENTINEL
    is_mock = (row.get("Research_Summary") or "").startswith(MOCK_PREFIX) or (
        row.get("Personalized_First_Line") or ""
    ).startswith(MOCK_PREFIX)
    return status, is_noctx, is_mock


def looks_like_mock_or_dev(row):
    """A row is safe to clean if it is clearly a mock row or a dead row."""
    status, _, is_mock = classify(row)
    return is_mock or status == "dead"


def report(rows, n, as_json):
    tail = rows[-n:] if n else rows
    counts = {}
    noctx = 0
    mock = 0
    for row in tail:
        status, is_noctx, is_mock = classify(row)
        counts[status or "(blank)"] = counts.get(status or "(blank)", 0) + 1
        noctx += 1 if is_noctx else 0
        mock += 1 if is_mock else 0

    summary = {
        "tab": TAB,
        "total_rows_in_tab": len(rows),
        "inspected": len(tail),
        "by_status": counts,
        "no_context": noctx,
        "mock_marked": mock,
    }

    if as_json:
        print(json.dumps(summary, indent=2))
        return summary

    print(f"Loomless tab — {len(rows)} data row(s) total; inspecting last {len(tail)}:\n")
    print(f"  {'#':>3}  {'First_Name':<12} {'status':<18} {'mock':<5} first_line")
    print(f"  {'-'*3}  {'-'*12} {'-'*18} {'-'*5} {'-'*40}")
    base = len(rows) - len(tail)
    for i, row in enumerate(tail):
        status, is_noctx, is_mock = classify(row)
        line = (row.get("Personalized_First_Line") or "").strip()
        shown = (line[:40] + "…") if len(line) > 40 else line
        print(f"  {base + i + 1:>3}  {(row.get('First_Name') or '')[:12]:<12} "
              f"{status:<18} {'yes' if is_mock else 'no':<5} {shown}")
    print("\n  by status :", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "(none)")
    print(f"  [NO_CONTEXT]: {noctx}")
    print(f"  [MOCK] marked: {mock} / {len(tail)}")
    return summary


def cleanup_last(sheets, sheet_id, rows, n):
    if n <= 0:
        sys.exit("ERROR: --cleanup-last needs a positive N")
    tail = rows[-n:]
    if len(tail) < n:
        sys.exit(f"ERROR: only {len(tail)} data row(s) exist; cannot clean last {n}")
    print(f"About to delete the bottom {n} data row(s) of '{TAB}':")
    for row in tail:
        status, is_noctx, _ = classify(row)
        print(f"  - {row.get('First_Name','')!r:<14} status={status} "
              f"line={(row.get('Personalized_First_Line') or '')[:30]!r}")
    unsafe = [r for r in tail if not looks_like_mock_or_dev(r)]
    if unsafe:
        sys.exit(
            f"REFUSING: {len(unsafe)} of those row(s) don't look like mock/dev rows "
            "(no [MOCK] marker and status != dead). Delete manually if intended."
        )
    # locate the Loomless sheetId + delete bottom-up
    meta = sheets.get(spreadsheetId=sheet_id).execute()
    sheet_gid = next(
        s["properties"]["sheetId"]
        for s in meta["sheets"]
        if s["properties"]["title"] == TAB
    )
    total_with_header = len(rows) + 1  # +1 header
    start = total_with_header - n       # 0-based index of first row to delete
    requests = [{
        "deleteDimension": {
            "range": {"sheetId": sheet_gid, "dimension": "ROWS",
                      "startIndex": start, "endIndex": total_with_header}
        }
    }]
    sheets.batchUpdate(spreadsheetId=sheet_id, body={"requests": requests}).execute()
    print(f"\nDeleted {n} row(s).")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--last", type=int, default=10, help="how many trailing rows to inspect (default 10)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--cleanup-last", type=int, metavar="N", help="delete the bottom N data rows and exit")
    args = p.parse_args()

    load_env()
    sheet_id = require_env("GOOGLE_SHEET_ID")
    sheets = build_service("sheets", "v4").spreadsheets()
    _, rows = read_rows(sheets, sheet_id)

    if args.cleanup_last is not None:
        cleanup_last(sheets, sheet_id, rows, args.cleanup_last)
        return

    if not rows:
        print(f"'{TAB}' tab has no data rows yet.")
        return
    report(rows, args.last, args.json)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"ERROR: {type(exc).__name__}: {exc}")
