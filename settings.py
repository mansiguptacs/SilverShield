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

# ---------- Twilio (optional real demo SMS) ----------
# When all four are set, the dispatch stage ALSO sends one real SMS to the
# designated demo phone, while the full cohort stays simulated. Safe no-op otherwise.
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "").strip()
DEMO_ALERT_TO = os.getenv("DEMO_ALERT_TO", "").strip()
# Trial accounts can't send custom SMS text - they must pass a predefined template id
# (e.g. sms_account_alerts). Set this to send a real SMS on a trial account; leave
# empty on an UPGRADED account to send our full custom recall message.
TWILIO_TRIAL_TEMPLATE = os.getenv("TWILIO_TRIAL_TEMPLATE", "").strip()

# Delivery channel for the real demo alert: "sms", "whatsapp", "callmebot", or "telegram".
#  - sms/whatsapp  -> Twilio (trial = template only; upgraded = full custom text)
#  - callmebot     -> free WhatsApp relay that sends our FULL custom text (no Twilio)
#  - telegram      -> free Telegram bot that sends our FULL custom text (no Twilio)
ALERT_CHANNEL = os.getenv("ALERT_CHANNEL", "sms").strip().lower()
# Twilio WhatsApp Sandbox number (default is Twilio's shared sandbox).
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "+14155238886").strip()
# CallMeBot WhatsApp API key (free; obtained via a one-time opt-in message). Sends to DEMO_ALERT_TO.
CALLMEBOT_APIKEY = os.getenv("CALLMEBOT_APIKEY", "").strip()
# Telegram bot (free, full custom text). Create a bot with @BotFather for the token,
# then the recipient sends /start to the bot; TELEGRAM_CHAT_ID is their chat id.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

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
