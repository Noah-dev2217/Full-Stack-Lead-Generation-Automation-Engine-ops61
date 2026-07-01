"""Canonical OPS-61 CRM tab schema.

Single source of truth for the helper scripts. Column lists are copied
verbatim from `shared/sheets-schema.md` (the locked canonical schema).
If that file changes, update here too — and only after a plan update.
"""

# tab name -> ordered header row (exact snake_case, no spaces)
TABS = {
    "Loomless": [
        "Company_Name",
        "Owner_Full_Name",
        "First_Name",
        "Email",
        "Website",
        "Research_Summary",
        "Personalized_First_Line",
        "status",
        "created_at",
    ],
    "JV_Targets": [
        "Name",
        "Email",
        "Social_Links",
        "Audience_Summary",
        "Current_Offers",
        "Source_URL",
        "status",
        "created_at",
    ],
    "Terminator_Loom": [
        "First_Name",
        "Last_Name",
        "Website",
        "status",
        "video_drive_link",
        "recorded_at",
        "error_log",
    ],
    "Inbound": [
        "Name",
        "Profile_URL",
        "Q1_Current_Revenue",
        "Q2_12_Month_Goal",
        "Q3_DM_Permission",
        "status",
        "operator_action",
        "captured_at",
    ],
}

# Per-tab timestamp column that the row-writer auto-fills with UTC ISO 8601.
TIMESTAMP_COLUMN = {
    "Loomless": "created_at",
    "JV_Targets": "created_at",
    "Terminator_Loom": "recorded_at",
    "Inbound": "captured_at",
}

TAB_NAMES = list(TABS.keys())
