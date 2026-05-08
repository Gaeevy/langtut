"""Import irregular verb forms from a JSON file into the verbs API.

Expected JSON format: list[verb_object]
Each verb_object has: infinitive, tense, forms.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import config
from app.models import VerbImportRequest

# Target environment selector. Change to "production" when needed.
TARGET_ENV = "local"

# Optional import API key from environment.
# Keep this out of source files; set LANGTUT_VERBS_IMPORT_API_KEY when importing.
IMPORT_API_KEY = config.verbs_import_api_key

VERBS_JSON_PATH = Path("verbs.json")
REQUEST_TIMEOUT_SECONDS = 20
MAX_RETRIES = 2


def get_api_base_by_env() -> dict[str, str]:
    """Build API base URL mapping from settings/env-backed config."""
    return {
        "local": config.verbs_import_local_url,
        "production": config.verbs_import_production_url,
    }


def parse_arguments() -> argparse.Namespace:
    """Parse CLI arguments."""
    api_base_by_env = get_api_base_by_env()
    parser = argparse.ArgumentParser(description="Import irregular verbs JSON into verbs API.")
    parser.add_argument(
        "--file",
        default=str(VERBS_JSON_PATH),
        help="Path to verbs JSON file (default: verbs.json)",
    )
    parser.add_argument(
        "--env",
        default=TARGET_ENV,
        choices=sorted(api_base_by_env),
        help="Target environment key from settings-backed URLs",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate/print payloads without sending requests",
    )
    return parser.parse_args()


def iter_payloads(raw_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate payloads with shared Pydantic import model."""
    payloads: list[dict[str, Any]] = []
    for entry in raw_data:
        model = VerbImportRequest(**entry)
        payloads.append(model.model_dump(mode="json"))
    return payloads


def post_payload(
    api_base_url: str, payload: dict[str, Any], timeout_seconds: int
) -> tuple[bool, str]:
    """Send one payload to the verbs import endpoint."""
    endpoint = f"{api_base_url.rstrip('/')}/api/verbs/forms"
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if IMPORT_API_KEY:
        headers["X-Import-Key"] = IMPORT_API_KEY

    request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # nosec B310
            response_body = response.read().decode("utf-8")
            return True, response_body
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        return False, f"HTTP {exc.code}: {error_body}"
    except urllib.error.URLError as exc:
        return False, f"Network error: {exc.reason}"


def main() -> int:
    """Load verbs JSON and import all payloads sequentially."""
    args = parse_arguments()
    api_base_by_env = get_api_base_by_env()
    verbs_path = Path(args.file)
    if not verbs_path.exists():
        print(f"Input file not found: {verbs_path}")
        return 1

    raw_data = json.loads(verbs_path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, list):
        print("Invalid JSON format: expected top-level list.")
        return 1

    payloads = iter_payloads(raw_data)

    if not payloads:
        print("No payloads found in verbs file.")
        return 1

    api_base_url = api_base_by_env[args.env]
    if not api_base_url.strip():
        print(f"Configured URL for env '{args.env}' is empty.")
        print("Set it in .secrets.toml (preferred) or LANGTUT_VERBS_IMPORT_PRODUCTION_URL env var.")
        return 1
    print(f"Loaded {len(payloads)} payload(s) from {verbs_path}")
    print(f"Target: {args.env} -> {api_base_url}")

    if args.dry_run:
        for index, payload in enumerate(payloads, start=1):
            print(f"[DRY {index}/{len(payloads)}] {payload['infinitive']} | {payload['tense']}")
        print("Dry run completed.")
        return 0

    success_count = 0
    for index, payload in enumerate(payloads, start=1):
        ok = False
        message = ""
        for attempt in range(MAX_RETRIES + 1):
            ok, message = post_payload(
                api_base_url=api_base_url,
                payload=payload,
                timeout_seconds=REQUEST_TIMEOUT_SECONDS,
            )
            if ok:
                break
            if attempt < MAX_RETRIES:
                time.sleep(1)

        if ok:
            success_count += 1
            print(f"[{index}/{len(payloads)}] OK {payload['infinitive']} | {payload['tense']}")
        else:
            print(f"[{index}/{len(payloads)}] FAIL {payload['infinitive']} | {payload['tense']}")
            print(message)

    print(f"Done. Success: {success_count}/{len(payloads)}")
    return 0 if success_count == len(payloads) else 1


if __name__ == "__main__":
    sys.exit(main())
