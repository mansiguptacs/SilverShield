"""Optional real-world emergency-alert delivery for a single DEMO recipient.

The full nationwide cohort dispatch stays *simulated* (preserving the scale and
confidentiality story). When Twilio credentials and a demo recipient are
configured, we additionally send exactly ONE real SMS to that designated phone -
so a live demo audience sees an actual emergency alert arrive on a real device
while the dashboard shows the nationwide fan-out.

This is a tangible stand-in for a Wireless Emergency Alert (real Amber Alerts go
through FEMA IPAWS via carriers and cannot be triggered by third parties).

Safe no-op when unconfigured.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))
from settings import (  # noqa: E402
    ALERT_CHANNEL,
    CALLMEBOT_APIKEY,
    DEMO_ALERT_TO,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_FROM_NUMBER,
    TWILIO_TRIAL_TEMPLATE,
    TWILIO_WHATSAPP_FROM,
)

# SMS hard ceiling is ~1600 chars; keep the body well under for multi-segment safety.
_MAX_BODY = 1400

_SIREN = "\U0001F6A8"  # rotating-light emoji


def _mask(number: str) -> str:
    digits = "".join(c for c in number if c.isdigit())
    if len(digits) < 4:
        return "***"
    return f"\u2022\u2022\u2022\u2022{digits[-4:]}"


def is_configured() -> bool:
    if ALERT_CHANNEL == "telegram":
        return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
    if ALERT_CHANNEL == "callmebot":
        return bool(CALLMEBOT_APIKEY and DEMO_ALERT_TO)
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and DEMO_ALERT_TO):
        return False
    if ALERT_CHANNEL == "whatsapp":
        return bool(TWILIO_WHATSAPP_FROM)
    return bool(TWILIO_FROM_NUMBER)


def _send_telegram(body: str) -> dict:
    """Free delivery via a Telegram bot. Sends our full custom text to TELEGRAM_CHAT_ID."""
    import requests

    resp = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": body},
        timeout=25,
    )
    if resp.ok and resp.json().get("ok"):
        return {"sent": True, "channel": "telegram", "mode": "custom",
                "to": f"chat {TELEGRAM_CHAT_ID}"}
    return {"sent": False, "channel": "telegram", "mode": "custom",
            "reason": f"HTTP {resp.status_code}: {resp.text[:160]}"}


def resolve_chat_id() -> dict:
    """Helper: read the latest chat id that messaged the bot (run after sending /start)."""
    import requests

    resp = requests.get(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates", timeout=25
    )
    data = resp.json()
    ids = []
    for u in data.get("result", []):
        msg = u.get("message") or u.get("edited_message") or {}
        chat = msg.get("chat") or {}
        if chat.get("id") is not None:
            ids.append((chat["id"], chat.get("first_name") or chat.get("title") or ""))
    return {"ok": data.get("ok", False), "chats": ids}


def _send_callmebot(body: str) -> dict:
    """Free WhatsApp delivery via CallMeBot. Sends our full custom text to DEMO_ALERT_TO."""
    import requests

    resp = requests.get(
        "https://api.callmebot.com/whatsapp.php",
        params={"phone": DEMO_ALERT_TO, "text": body, "apikey": CALLMEBOT_APIKEY},
        timeout=25,
    )
    text = (resp.text or "").lower()
    ok = resp.ok and ("queued" in text or "sent" in text or "message" in text and "error" not in text)
    if ok:
        return {"sent": True, "channel": "whatsapp", "mode": "callmebot", "to": _mask(DEMO_ALERT_TO)}
    return {"sent": False, "channel": "whatsapp", "mode": "callmebot",
            "reason": f"HTTP {resp.status_code}: {resp.text[:160]}"}


def build_emergency_sms(severity: str, recalling_firm: str, product_ndc: str,
                        recall_number: str) -> str:
    """An amber-alert-styled body for the single real demo SMS."""
    headline = {
        "Lethal": "LIFE-THREATENING DRUG RECALL",
        "Moderate": "URGENT DRUG RECALL",
        "Minor": "DRUG RECALL NOTICE",
    }.get(severity, "DRUG RECALL NOTICE")
    return (
        f"{_SIREN} FDA SAFETYNET ALERT {_SIREN}\n"
        f"{headline}\n"
        f"A medication you filled (NDC {product_ndc}, {recalling_firm}) was recalled "
        f"by the U.S. FDA. Do not take another dose - contact your pharmacy now.\n"
        f"Recall {recall_number}. Reply STOP to opt out."
    )[:_MAX_BODY]


def send_demo_sms(severity: str, recalling_firm: str, product_ndc: str,
                  recall_number: str) -> dict:
    """Send one real SMS to the demo phone. Returns a de-identified status dict."""
    if not is_configured():
        return {"sent": False, "channel": "twilio", "reason": "not_configured"}
    try:
        custom = build_emergency_sms(severity, recalling_firm, product_ndc, recall_number)

        if ALERT_CHANNEL == "telegram":
            return _send_telegram(custom)

        if ALERT_CHANNEL == "callmebot":
            return _send_callmebot(custom)

        from twilio.rest import Client

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        if ALERT_CHANNEL == "whatsapp":
            # WhatsApp Sandbox allows free-form custom text within the 24h window that
            # opens after the recipient texts "join <code>" to the sandbox number.
            msg = client.messages.create(
                body=custom,
                from_=f"whatsapp:{TWILIO_WHATSAPP_FROM}",
                to=f"whatsapp:{DEMO_ALERT_TO}",
            )
            return {"sent": True, "channel": "whatsapp", "mode": "custom",
                    "sid": msg.sid, "to": _mask(DEMO_ALERT_TO)}

        # SMS: trial accounts must pass a predefined template id as the body;
        # upgraded accounts send our full custom emergency text.
        body = TWILIO_TRIAL_TEMPLATE or custom
        msg = client.messages.create(body=body, from_=TWILIO_FROM_NUMBER, to=DEMO_ALERT_TO)
        mode = "trial_template" if TWILIO_TRIAL_TEMPLATE else "custom"
        return {"sent": True, "channel": "sms", "mode": mode,
                "sid": msg.sid, "to": _mask(DEMO_ALERT_TO)}
    except Exception as exc:  # noqa: BLE001
        return {"sent": False, "channel": "twilio", "reason": str(exc)}


if __name__ == "__main__":
    # Standalone credential check:  python -m phase5_orchestration.tools.real_alert
    print("Twilio configured:", is_configured())
    if not is_configured():
        print("Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, "
              "DEMO_ALERT_TO in .env (numbers in E.164, e.g. +15551234567).")
        raise SystemExit(1)
    print(f"Sending test alert from {TWILIO_FROM_NUMBER} to {_mask(DEMO_ALERT_TO)} ...")
    status = send_demo_sms("Lethal", "McKesson", "69448-025", "D-0353-2026")
    print(status)
    raise SystemExit(0 if status.get("sent") else 1)
