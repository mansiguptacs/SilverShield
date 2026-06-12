"""Shared, env-driven configuration for FDA SafetyNet.

Everything that differs between local and cloud (ClickHouse host, API keys,
scale knobs) is read here so migration is a config swap, not a code change.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# ---------- openFDA ----------
OPENFDA_BASE = "https://api.fda.gov"
OPENFDA_ENFORCEMENT = f"{OPENFDA_BASE}/drug/enforcement.json"
OPENFDA_API_KEY = os.getenv("OPENFDA_API_KEY", "").strip()

# ---------- ClickHouse ----------
CLICKHOUSE = {
    "host": os.getenv("CLICKHOUSE_HOST", "localhost"),
    "port": int(os.getenv("CLICKHOUSE_PORT", "8123")),
    "username": os.getenv("CLICKHOUSE_USER", "default"),
    "password": os.getenv("CLICKHOUSE_PASSWORD", ""),
    "database": os.getenv("CLICKHOUSE_DATABASE", "safetynet"),
    "secure": os.getenv("CLICKHOUSE_SECURE", "false").lower() == "true",
}

# ---------- Scale knobs ----------
SCALE_PHARMACIES = int(os.getenv("SCALE_PHARMACIES", "5000"))
SCALE_CUSTOMERS = int(os.getenv("SCALE_CUSTOMERS", "1000000"))
NDC_OVERLAP_RATE = float(os.getenv("NDC_OVERLAP_RATE", "0.18"))

# ---------- Data artifact paths ----------
SEED_NDCS_PATH = DATA_DIR / "seed_ndcs.json"
PHARMACIES_CSV = DATA_DIR / "pharmacies.csv"
CUSTOMERS_CSV = DATA_DIR / "customers.csv"

# ---------- OpenAI / agents ----------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
USE_AGENTS = os.getenv("USE_AGENTS", "false").lower() == "true"

# ---------- Severity mapping (openFDA classification -> our labels) ----------
CLASSIFICATION_TO_SEVERITY = {
    "Class I": "Lethal",
    "Class II": "Moderate",
    "Class III": "Minor",
}
