"""Phase 1b: Seed real recalled NDCs from openFDA.

Pulls recent drug recall enforcement records and extracts their National Drug
Codes (NDCs). We plant a slice of these into the synthetic customer data so the
live demo produces guaranteed positive matches against real FDA recalls.

Output: data/seed_ndcs.json -> {"ndcs": [...], "samples": [{recall metadata}]}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

sys.path.append(str(Path(__file__).resolve().parent.parent))
from settings import OPENFDA_API_KEY, OPENFDA_ENFORCEMENT, SEED_NDCS_PATH  # noqa: E402

# How many recent recall records to scan for NDCs.
FETCH_LIMIT = 1000


def fetch_recent_recalls(limit: int = FETCH_LIMIT) -> list[dict]:
    """Fetch the most recent recall enforcement reports."""
    params = {"sort": "report_date:desc", "limit": min(limit, 1000)}
    if OPENFDA_API_KEY:
        params["api_key"] = OPENFDA_API_KEY
    resp = requests.get(OPENFDA_ENFORCEMENT, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("results", [])


def extract_ndcs(records: list[dict]) -> tuple[list[str], list[dict]]:
    """Pull unique product_ndc values plus a few sample recalls for context."""
    ndcs: set[str] = set()
    samples: list[dict] = []
    for rec in records:
        openfda = rec.get("openfda", {}) or {}
        product_ndcs = openfda.get("product_ndc", []) or []
        for ndc in product_ndcs:
            if ndc:
                ndcs.add(ndc)
        if product_ndcs and len(samples) < 25:
            samples.append(
                {
                    "recall_number": rec.get("recall_number"),
                    "product_ndc": product_ndcs[0],
                    "classification": rec.get("classification"),
                    "reason_for_recall": (rec.get("reason_for_recall") or "")[:200],
                    "recalling_firm": rec.get("recalling_firm"),
                }
            )
    return sorted(ndcs), samples


def main() -> None:
    print(f"Fetching up to {FETCH_LIMIT} recent recalls from openFDA...")
    records = fetch_recent_recalls()
    print(f"  retrieved {len(records)} recall records")

    ndcs, samples = extract_ndcs(records)
    print(f"  extracted {len(ndcs)} unique recalled NDCs")

    payload = {"ndcs": ndcs, "samples": samples}
    SEED_NDCS_PATH.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {len(ndcs)} seed NDCs -> {SEED_NDCS_PATH}")

    if ndcs:
        print("Sample recalled NDCs:", ", ".join(ndcs[:5]))
    else:
        print("WARNING: no NDCs extracted - matching demo may have no positive hits.")


if __name__ == "__main__":
    main()
