"""Phase 1d: Verify the generated synthetic dataset.

Checks row counts, 50-state coverage, FK integrity, and that a non-zero number
of customers sit on real recalled NDCs (the demo's positive-match guarantee).
Exits non-zero if any check fails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))
from settings import CUSTOMERS_CSV, PHARMACIES_CSV, SEED_NDCS_PATH  # noqa: E402


def check(label: str, condition: bool, detail: str = "") -> bool:
    mark = "PASS" if condition else "FAIL"
    print(f"  [{mark}] {label}{(' - ' + detail) if detail else ''}")
    return condition


def main() -> int:
    print("Verifying Phase 1 synthetic data...")
    ok = True

    pharm = pd.read_csv(PHARMACIES_CSV)
    cust = pd.read_csv(CUSTOMERS_CSV, dtype={"prescribed_ndc_code": str})
    seed_ndcs = set(json.loads(SEED_NDCS_PATH.read_text()).get("ndcs", []))

    ok &= check("pharmacies row count > 0", len(pharm) > 0, f"{len(pharm)} rows")
    ok &= check("customers row count > 0", len(cust) > 0, f"{len(cust)} rows")
    ok &= check(
        "states covered >= 50",
        pharm["state"].nunique() >= 50,
        f"{pharm['state'].nunique()} states",
    )

    # FK integrity: every customer pharmacy_id resolves to a pharmacy.
    orphan = ~cust["pharmacy_id"].isin(set(pharm["pharmacy_id"]))
    ok &= check("all customers map to a pharmacy", orphan.sum() == 0, f"{orphan.sum()} orphans")

    # Positive-match guarantee: customers on recalled NDCs.
    overlap = cust["prescribed_ndc_code"].isin(seed_ndcs)
    n_overlap = int(overlap.sum())
    ok &= check("customers on recalled NDCs > 0", n_overlap > 0, f"{n_overlap} matches")

    # NDC format sanity (labeler-product).
    fmt_ok = cust["prescribed_ndc_code"].str.match(r"^\d{4,5}-\d{3,4}$").mean()
    ok &= check("NDC format valid", fmt_ok > 0.99, f"{fmt_ok:.1%} well-formed")

    print(f"\n  affected pharmacies (recalled-NDC customers): "
          f"{cust.loc[overlap, 'pharmacy_id'].nunique()}")
    print(f"  affected states: {cust.loc[overlap, 'state'].nunique()}")

    print("\nRESULT:", "ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
