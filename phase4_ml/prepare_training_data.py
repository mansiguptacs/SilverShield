"""Phase 4 prep: build a balanced labeled training set from openFDA.

The live pipeline window is small + imbalanced (mostly Class II), so for model
training we pull a larger, class-balanced sample of historical recalls directly
from openFDA. Labels = classification (Class I/II/III) -> severity.

Output: data/training_recalls.csv (reason_for_recall, classification, severity)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
from settings import CLASSIFICATION_TO_SEVERITY, DATA_DIR, OPENFDA_API_KEY, OPENFDA_ENFORCEMENT  # noqa: E402

PER_CLASS = 1500
PAGE = 1000
OUT = DATA_DIR / "training_recalls.csv"


def fetch_class(classification: str, target: int = PER_CLASS) -> list[dict]:
    rows: list[dict] = []
    skip = 0
    while len(rows) < target:
        params = {
            "search": f'classification:"{classification}"',
            "limit": min(PAGE, target - len(rows)),
            "skip": skip,
        }
        if OPENFDA_API_KEY:
            params["api_key"] = OPENFDA_API_KEY
        resp = requests.get(OPENFDA_ENFORCEMENT, params=params, timeout=30)
        if resp.status_code != 200:
            break
        results = resp.json().get("results", [])
        if not results:
            break
        for r in results:
            reason = (r.get("reason_for_recall") or "").strip()
            if reason:
                rows.append({"reason_for_recall": reason, "classification": classification})
        skip += len(results)
        if skip >= 25000:
            break
    return rows


def main() -> None:
    all_rows: list[dict] = []
    for cls in ["Class I", "Class II", "Class III"]:
        rows = fetch_class(cls)
        print(f"  {cls}: {len(rows)} recalls")
        all_rows.extend(rows)

    df = pd.DataFrame(all_rows)
    df["severity"] = df["classification"].map(CLASSIFICATION_TO_SEVERITY)
    df = df.drop_duplicates(subset=["reason_for_recall"]).reset_index(drop=True)
    df.to_csv(OUT, index=False)
    print(f"\nWrote {len(df)} labeled recalls -> {OUT}")
    print(df["severity"].value_counts().to_string())


if __name__ == "__main__":
    main()
