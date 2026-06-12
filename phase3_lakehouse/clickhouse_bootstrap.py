"""Phase 3: Bootstrap the ClickHouse lakehouse.

- Applies 01_create_tables.sql and 02_materialized_view.sql.
- Bulk-loads pharmacies.csv and customers.csv (patient_ehr).
- Works against local ClickHouse or ClickHouse Cloud (env-driven).

Usage:
    python phase3_lakehouse/clickhouse_bootstrap.py            # full bootstrap
    python phase3_lakehouse/clickhouse_bootstrap.py --schema-only
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import clickhouse_connect
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))
from settings import CLICKHOUSE, CUSTOMERS_CSV, PHARMACIES_CSV  # noqa: E402

SQL_DIR = Path(__file__).resolve().parent
INSERT_BATCH = 200_000


def get_client(database: str | None = None):
    cfg = dict(CLICKHOUSE)
    db = database if database is not None else cfg.pop("database")
    if database is not None:
        cfg.pop("database", None)
    return clickhouse_connect.get_client(database=db, **cfg)


def run_sql_file(client, path: Path) -> None:
    """Execute a .sql file containing multiple ; -separated statements."""
    sql = path.read_text()
    # Strip line comments, split on semicolons.
    statements = []
    for raw in sql.split(";"):
        lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("--")]
        stmt = "\n".join(lines).strip()
        if stmt:
            statements.append(stmt)
    for stmt in statements:
        client.command(stmt)
    print(f"  applied {len(statements)} statements from {path.name}")


def load_pharmacies(client) -> None:
    df = pd.read_csv(PHARMACIES_CSV, dtype={"zip": str})
    client.insert_df("safetynet.pharmacies", df)
    print(f"  loaded {len(df)} pharmacies")


def load_customers(client) -> None:
    cols = ["customer_id", "name", "phone_number", "pharmacy_id", "state", "prescribed_ndc_code"]
    total = 0
    t0 = time.time()
    for chunk in pd.read_csv(
        CUSTOMERS_CSV, dtype={"prescribed_ndc_code": str, "phone_number": str}, chunksize=INSERT_BATCH
    ):
        client.insert_df("safetynet.patient_ehr", chunk[cols])
        total += len(chunk)
        print(f"    ...{total:,} customers", end="\r")
    print(f"\n  loaded {total:,} customers in {time.time()-t0:.1f}s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema-only", action="store_true", help="apply SQL only, skip data load")
    ap.add_argument("--reset", action="store_true", help="drop the safetynet database first")
    args = ap.parse_args()

    print(f"Connecting to ClickHouse at {CLICKHOUSE['host']}:{CLICKHOUSE['port']} "
          f"(secure={CLICKHOUSE['secure']})...")
    admin = get_client(database="default")

    if args.reset:
        admin.command("DROP DATABASE IF EXISTS safetynet")
        print("  dropped database safetynet")

    print("Applying schema...")
    run_sql_file(admin, SQL_DIR / "01_create_tables.sql")
    run_sql_file(admin, SQL_DIR / "02_materialized_view.sql")

    if args.schema_only:
        print("Schema applied (--schema-only). Done.")
        return

    client = get_client()
    print("Loading reference + EHR data...")
    load_pharmacies(client)
    load_customers(client)

    n_ph = client.command("SELECT count() FROM safetynet.pharmacies")
    n_cust = client.command("SELECT count() FROM safetynet.patient_ehr")
    print(f"\nBootstrap complete: {n_ph} pharmacies, {n_cust} customers.")


if __name__ == "__main__":
    main()
