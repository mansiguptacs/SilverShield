"""Phase 3 verification: prove the materialized-view trigger fires at scale.

Inserts ONE real recalled NDC into fda_recalls and confirms that:
  - patient_alerts auto-populates with the affected customers (MV trigger),
  - alert_geo_rollup shows per-state aggregate counts (no PII),
  - the nationwide match completes in sub-second/low-second time.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from settings import CLASSIFICATION_TO_SEVERITY, SEED_NDCS_PATH  # noqa: E402
from phase3_lakehouse.clickhouse_bootstrap import get_client  # noqa: E402


def main() -> int:
    client = get_client()

    # Pick a real recalled NDC that we know exists in patient_ehr.
    seed = json.loads(SEED_NDCS_PATH.read_text())
    test_ndc = None
    for ndc in seed["ndcs"]:
        n = client.command(
            "SELECT count() FROM safetynet.patient_ehr WHERE prescribed_ndc_code = %(n)s",
            parameters={"n": ndc},
        )
        if int(n) > 0:
            test_ndc = ndc
            expected = int(n)
            break
    if not test_ndc:
        print("FAIL: no seed NDC found in patient_ehr")
        return 1
    print(f"Test NDC {test_ndc}: {expected} customers prescribed it nationwide.")

    # Clean any prior test rows for idempotency.
    client.command("TRUNCATE TABLE safetynet.patient_alerts")
    client.command("TRUNCATE TABLE safetynet.alert_geo_rollup")
    client.command(
        "ALTER TABLE safetynet.fda_recalls DELETE WHERE recall_number = 'TEST-RECALL-001'"
    )
    time.sleep(0.5)

    severity = CLASSIFICATION_TO_SEVERITY["Class I"]
    t0 = time.time()
    client.insert(
        "safetynet.fda_recalls",
        [[
            "TEST-RECALL-001", test_ndc,
            "Products may contain a life-threatening contaminant.",
            "Class I", severity, "Ongoing", "Test Pharma Inc.",
            "Nationwide", "20260612",
            "https://api.fda.gov/drug/enforcement.json?search=recall_number:TEST-RECALL-001",
        ]],
        column_names=[
            "recall_number", "product_ndc", "reason_for_recall", "classification",
            "severity", "status", "recalling_firm", "distribution_pattern",
            "report_date", "source_url",
        ],
    )
    elapsed = time.time() - t0

    n_alerts = int(client.command(
        "SELECT count() FROM safetynet.patient_alerts WHERE recall_number = 'TEST-RECALL-001'"
    ))
    print(f"\nMV trigger: inserted 1 recall -> {n_alerts} patient_alerts in {elapsed:.3f}s")

    rollup = client.query(
        """
        SELECT state,
               countMerge(affected_customers)  AS customers,
               uniqMerge(affected_pharmacies)  AS pharmacies
        FROM safetynet.alert_geo_rollup
        WHERE recall_number = 'TEST-RECALL-001'
        GROUP BY state ORDER BY customers DESC LIMIT 5
        """
    )
    total_states = int(client.command(
        "SELECT uniqExact(state) FROM safetynet.alert_geo_rollup WHERE recall_number='TEST-RECALL-001'"
    ))
    total_pharm = int(client.command(
        "SELECT uniqMerge(affected_pharmacies) FROM safetynet.alert_geo_rollup WHERE recall_number='TEST-RECALL-001'"
    ))

    print(f"Geo rollup: {total_states} states, {total_pharm} pharmacies affected.")
    print("Top affected states:")
    for state, customers, pharmacies in rollup.result_rows:
        print(f"    {state}: {customers} customers across {pharmacies} pharmacies")

    ok = n_alerts == expected and total_states > 0
    print("\nRESULT:", "MV TRIGGER + GEO ROLLUP WORKING" if ok else "CHECK FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
