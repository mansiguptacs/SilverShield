"""Phase 1c (part 1): Generate ~5,000 synthetic pharmacies across all 50 states
(+ DC), population-weighted, with approximate geo coordinates for the national
map. Vectorized with numpy for speed.

Output: data/pharmacies.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))
from settings import PHARMACIES_CSV, SCALE_PHARMACIES  # noqa: E402
from phase1_data.us_geo import PHARMACY_CHAINS, US_STATES  # noqa: E402

RNG = np.random.default_rng(42)


def generate(n: int = SCALE_PHARMACIES) -> pd.DataFrame:
    abbrs = np.array([s[0] for s in US_STATES])
    names = np.array([s[1] for s in US_STATES])
    pops = np.array([s[2] for s in US_STATES], dtype=float)
    lats = np.array([s[3] for s in US_STATES])
    lons = np.array([s[4] for s in US_STATES])

    weights = pops / pops.sum()
    idx = RNG.choice(len(US_STATES), size=n, p=weights)

    # Jitter coordinates around each state's centroid so points spread out.
    lat = lats[idx] + RNG.normal(0, 0.9, n)
    lon = lons[idx] + RNG.normal(0, 0.9, n)

    chain_idx = RNG.integers(0, len(PHARMACY_CHAINS), n)
    chains = np.array(PHARMACY_CHAINS)[chain_idx]
    store_num = RNG.integers(100, 9999, n)

    df = pd.DataFrame(
        {
            "pharmacy_id": [f"PH{1000000 + i}" for i in range(n)],
            "name": [f"{c} #{s}" for c, s in zip(chains, store_num)],
            "chain": chains,
            "state": abbrs[idx],
            "state_name": names[idx],
            "zip": RNG.integers(10000, 99999, n).astype(str),
            "lat": np.round(lat, 4),
            "lon": np.round(lon, 4),
        }
    )
    return df


def main() -> None:
    print(f"Generating {SCALE_PHARMACIES} pharmacies across {len(US_STATES)} states...")
    df = generate()
    df.to_csv(PHARMACIES_CSV, index=False)
    by_state = df["state"].nunique()
    print(f"Wrote {len(df)} pharmacies -> {PHARMACIES_CSV}")
    print(f"  states covered: {by_state}/{len(US_STATES)}")
    print("  top states by pharmacy count:")
    print(df["state"].value_counts().head(5).to_string())


if __name__ == "__main__":
    main()
