"""Phase 2: Run the openFDA declarative source via PyAirbyte.

Uses the declarative YAML manifest (config/openfda_manifest.yaml) executed by
PyAirbyte's low-code interpreter. State is persisted in a DuckDB cache so re-runs
are truly incremental (already-seen records are skipped).

The same manifest can be pasted into the Airbyte Cloud Connector Builder for the
cloud-migration track.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import airbyte as ab
import yaml
from airbyte.caches import DuckDBCache
from airbyte.experimental import get_source

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
from settings import OPENFDA_API_KEY  # noqa: E402

MANIFEST_PATH = ROOT / "config" / "openfda_manifest.yaml"
CACHE_DIR = ROOT / ".pyairbyte-cache"
# Default ingestion window: recent recalls keep the demo fast + bounded.
DEFAULT_LOOKBACK_DAYS = 120


def build_config(lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> dict:
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=lookback_days)).strftime("%Y%m%d")
    end = now.strftime("%Y%m%d")
    cfg: dict = {"start_date": start, "end_date": end}
    if OPENFDA_API_KEY:
        cfg["api_key"] = OPENFDA_API_KEY
    return cfg


def get_cache() -> DuckDBCache:
    CACHE_DIR.mkdir(exist_ok=True)
    return DuckDBCache(db_path=str(CACHE_DIR / "openfda.duckdb"))


def _inject_dates(manifest: dict, start: str, end: str) -> dict:
    """Inject concrete dates into the manifest.

    The YAML keeps config-based interpolation for Airbyte Cloud portability, but
    PyAirbyte's local declarative runner (airbyte 0.47 + cdk 7.x) does not pass
    config into manifest interpolation, so we substitute literal cursor bounds
    here. The request itself is driven by the cursor's stream_interval, so
    re-runs resume from saved state (true incremental).
    """
    cursor = manifest["definitions"]["incremental_cursor"]
    cursor["start_datetime"]["datetime"] = start
    cursor["end_datetime"]["datetime"] = end
    return manifest


def read_recalls(lookback_days: int = DEFAULT_LOOKBACK_DAYS):
    """Run the source and return (read_result, cache). Incremental via cache state."""
    manifest = yaml.safe_load(MANIFEST_PATH.read_text())
    config = build_config(lookback_days)
    manifest = _inject_dates(manifest, config["start_date"], config["end_date"])

    print(f"openFDA ingestion window: {config['start_date']} -> {config['end_date']}")
    source = get_source(
        "source-openfda",
        config=config,
        source_manifest=manifest,
    )
    source.select_streams(["drug_enforcement"])

    cache = get_cache()
    result = source.read(cache=cache)
    return result, cache


def main() -> None:
    result, _ = read_recalls()
    stream = result["drug_enforcement"]
    n = len(list(stream))
    print(f"Read {n} recall records (this sync). New/changed records this run: "
          f"{result.processed_records}")


if __name__ == "__main__":
    main()
