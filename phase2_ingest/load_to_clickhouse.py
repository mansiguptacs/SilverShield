"""Phase 2: Load openFDA recalls (read via PyAirbyte) into ClickHouse.

Flattens the nested openFDA records, maps classification -> severity, expands
multi-NDC recalls into one row per product_ndc, and inserts into fda_recalls.
Each insert fires the materialized view -> patient_alerts (the matching engine).

Re-running is incremental: PyAirbyte's cache state means only new recalls are
read, and ReplacingMergeTree dedups on (product_ndc, recall_number).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
from settings import CLASSIFICATION_TO_SEVERITY, OPENFDA_ENFORCEMENT  # noqa: E402
from phase2_ingest.airbyte_source import read_recalls  # noqa: E402
from phase3_lakehouse.clickhouse_bootstrap import get_client  # noqa: E402

COLUMNS = [
    "recall_number", "product_ndc", "reason_for_recall", "classification",
    "severity", "status", "recalling_firm", "distribution_pattern",
    "report_date", "source_url",
]


def flatten(record: dict) -> list[list]:
    """One openFDA recall -> one row per product_ndc."""
    openfda = record.get("openfda") or {}
    ndcs = openfda.get("product_ndc") or []
    if not ndcs:
        return []
    classification = record.get("classification") or ""
    severity = CLASSIFICATION_TO_SEVERITY.get(classification, "Minor")
    recall_number = record.get("recall_number") or ""
    source_url = f"{OPENFDA_ENFORCEMENT}?search=recall_number:{recall_number}"
    base = [
        recall_number, None,
        record.get("reason_for_recall") or "",
        classification, severity,
        record.get("status") or "",
        record.get("recalling_firm") or "",
        record.get("distribution_pattern") or "",
        record.get("report_date") or "",
        source_url,
    ]
    rows = []
    for ndc in ndcs:
        row = list(base)
        row[1] = ndc
        rows.append(row)
    return rows


def main() -> None:
    result, _ = read_recalls()
    records = list(result["drug_enforcement"])
    print(f"Flattening {len(records)} recalls...")

    rows: list[list] = []
    for rec in records:
        rows.extend(flatten(rec))

    if not rows:
        print("No NDC-bearing recalls to load.")
        return

    client = get_client()

    # Incremental at the warehouse boundary: only insert recalls we haven't
    # ingested yet. This keeps re-syncs idempotent and prevents the MV from
    # fanning out duplicate patient alerts.
    existing = {
        r[0] for r in client.query(
            "SELECT DISTINCT recall_number FROM safetynet.fda_recalls"
        ).result_rows
    }
    new_rows = [r for r in rows if r[0] not in existing]
    skipped = len(rows) - len(new_rows)

    if not new_rows:
        print(f"No new recalls (skipped {skipped} already-ingested rows). Up to date.")
        return

    client.insert("safetynet.fda_recalls", new_rows, column_names=COLUMNS)
    print(f"Inserted {len(new_rows)} NEW recall-NDC rows "
          f"(skipped {skipped} already-ingested).")

    n_recalls = client.command("SELECT count() FROM safetynet.fda_recalls")
    n_alerts = client.command("SELECT count() FROM safetynet.patient_alerts")
    n_states = client.command("SELECT uniqExact(state) FROM safetynet.patient_alerts")
    print(f"  fda_recalls rows: {n_recalls}")
    print(f"  patient_alerts (auto-matched via MV): {n_alerts}")
    print(f"  states with alerts: {n_states}")


if __name__ == "__main__":
    main()
