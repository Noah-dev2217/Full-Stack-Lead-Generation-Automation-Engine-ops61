"""Shared helpers for the OPS-61 foundation scripts.

Keeps credential loading + .env parsing in one place so populate_sheet.py
and verify_foundation.py stay short. No pipeline logic here.
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Scopes the Service Account needs: read/write Sheets + Drive.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def load_env():
    """Populate os.environ from repo-root .env if present.

    Uses python-dotenv when installed; otherwise a minimal KEY=VALUE parser.
    Values already in the real environment win (don't clobber).
    """
    env_path = REPO_ROOT / ".env"
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(env_path)
        return
    except ImportError:
        pass

    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        # strip an inline trailing comment on simple unquoted values
        if value and value[0] not in "\"'" and "  #" in value:
            value = value.split("  #", 1)[0].strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def require_env(name):
    val = os.environ.get(name, "").strip()
    if not val:
        sys.exit(f"ERROR: required env var {name} is not set (check your .env)")
    return val


def service_account_path():
    """Resolve the SA JSON path from env, relative to repo root if needed."""
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "./service-account.json")
    p = Path(raw)
    if not p.is_absolute():
        p = (REPO_ROOT / raw).resolve()
    if not p.exists():
        sys.exit(
            f"ERROR: service account JSON not found at {p}\n"
            "Create it in Google Cloud Console (see FOUNDATION_SETUP.md, step 3)\n"
            "and set GOOGLE_SERVICE_ACCOUNT_PATH in .env."
        )
    return str(p)


def get_credentials():
    try:
        from google.oauth2 import service_account  # type: ignore
    except ImportError:
        sys.exit(
            "ERROR: missing deps. Run:\n"
            "  pip install -r shared/scripts/requirements.txt"
        )
    return service_account.Credentials.from_service_account_file(
        service_account_path(), scopes=SCOPES
    )


def build_service(api, version):
    from googleapiclient.discovery import build  # type: ignore

    return build(api, version, credentials=get_credentials(), cache_discovery=False)
