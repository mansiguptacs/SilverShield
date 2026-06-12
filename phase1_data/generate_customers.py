"""Phase 1c (part 2): Generate ~1,000,000 synthetic customer-prescription records
linked to pharmacies (which carry geography). ~NDC_OVERLAP_RATE of prescriptions
use real recalled NDCs so the demo produces positive matches.

Vectorized with numpy + a small Faker name pool so 1M rows generate in seconds.

Output: data/customers.csv
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

sys.path.append(str(Path(__file__).resolve().parent.parent))
from settings import (  # noqa: E402
    CUSTOMERS_CSV,
    NDC_OVERLAP_RATE,
    PHARMACIES_CSV,
    SCALE_CUSTOMERS,
    SEED_NDCS_PATH,
)

RNG = np.random.default_rng(7)
NAME_POOL_SIZE = 20000


def build_name_pool(size: int = NAME_POOL_SIZE) -> np.ndarray:
    fake = Faker()
    Faker.seed(7)
    return np.array([fake.name() for _ in range(size)])


def random_ndc_codes(n: int) -> np.ndarray:
    """Generate n random NDC-formatted strings (labeler-product, 5-4 digits)."""
    labeler = pd.Series(RNG.integers(10000, 99999, n).astype(str)).str.zfill(5)
    product = pd.Series(RNG.integers(1000, 9999, n).astype(str)).str.zfill(4)
    return (labeler + "-" + product).to_numpy()


def random_phones(n: int) -> np.ndarray:
    area = RNG.integers(200, 999, n)
    pre = RNG.integers(200, 999, n)
    line = RNG.integers(0, 9999, n)
    s_area = pd.Series(area.astype(str))
    s_pre = pd.Series(pre.astype(str))
    s_line = pd.Series(line.astype(str)).str.zfill(4)
    return ("+1" + s_area + s_pre + s_line).to_numpy()


def generate(n: int = SCALE_CUSTOMERS) -> pd.DataFrame:
    if not PHARMACIES_CSV.exists():
        raise FileNotFoundError(
            f"{PHARMACIES_CSV} not found - run generate_pharmacies.py first."
        )
    pharmacies = pd.read_csv(PHARMACIES_CSV, usecols=["pharmacy_id", "state"])
    pharm_ids = pharmacies["pharmacy_id"].to_numpy()
    pharm_states = pharmacies["state"].to_numpy()

    seed = json.loads(SEED_NDCS_PATH.read_text())
    seed_ndcs = np.array(seed.get("ndcs", []))
    if seed_ndcs.size == 0:
        raise ValueError("No seed NDCs - run fetch_seed_ndcs.py first.")

    # Assign each customer to a pharmacy (carry its state along).
    p_idx = RNG.integers(0, len(pharm_ids), n)

    # NDC: overlap_rate -> real recalled NDC, else random.
    overlap_mask = RNG.random(n) < NDC_OVERLAP_RATE
    recalled = seed_ndcs[RNG.integers(0, len(seed_ndcs), n)]
    ndc = np.where(overlap_mask, recalled, random_ndc_codes(n))

    name_pool = build_name_pool()
    names = name_pool[RNG.integers(0, len(name_pool), n)]

    df = pd.DataFrame(
        {
            "customer_id": "CU" + pd.Series(np.arange(n) + 1).astype(str),
            "name": names,
            "phone_number": random_phones(n),
            "pharmacy_id": pharm_ids[p_idx],
            "state": pharm_states[p_idx],
            "prescribed_ndc_code": ndc,
        }
    )
    return df, int(overlap_mask.sum())


def main() -> None:
    print(
        f"Generating {SCALE_CUSTOMERS} customers "
        f"(target NDC overlap rate {NDC_OVERLAP_RATE:.0%})..."
    )
    df, n_overlap = generate()
    df.to_csv(CUSTOMERS_CSV, index=False)
    print(f"Wrote {len(df)} customers -> {CUSTOMERS_CSV}")
    print(f"  customers on recalled NDCs (overlap): {n_overlap} ({n_overlap/len(df):.1%})")
    print(f"  distinct pharmacies referenced: {df['pharmacy_id'].nunique()}")
    print(f"  states covered: {df['state'].nunique()}")


if __name__ == "__main__":
    main()
