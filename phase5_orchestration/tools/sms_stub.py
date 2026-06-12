"""Simulated emergency dispatch.

Resolves the affected cohort at the data layer and "sends" alerts. Returns only
aggregates + masked samples - the orchestrator/LLM never sees raw PII. Swappable
for a real Composio/Twilio executor in Phase 7 via the same signature.
"""
from __future__ import annotations

from . import clickhouse_tools


def build_message(severity: str, recalling_firm: str, product_ndc: str) -> str:
    urgency = {
        "Lethal": "URGENT SAFETY RECALL - STOP USE IMMEDIATELY",
        "Moderate": "Important medication recall notice",
        "Minor": "Medication recall notification",
    }.get(severity, "Medication recall notification")
    return (
        f"{urgency}: A medication you filled (NDC {product_ndc}, {recalling_firm}) "
        f"has been recalled by the FDA. Please contact your pharmacy before taking "
        f"another dose. Reply STOP to opt out."
    )


def dispatch_to_cohort(recall_number: str, severity: str, recalling_firm: str,
                       product_ndc: str) -> dict:
    """Dispatch to every matched customer for a recall. Returns aggregates."""
    message = build_message(severity, recalling_firm, product_ndc)
    summary = clickhouse_tools.cohort_summary(recall_number)
    samples = clickhouse_tools.sample_masked_recipients(recall_number, k=3)
    channel = "sms_simulated"  # Phase 7: swap for Composio/Twilio
    return {
        "channel": channel,
        "dispatched": summary["total_customers"],
        "pharmacies_notified": summary["total_pharmacies"],
        "states": summary["total_states"],
        "message": message,
        "sample_recipients": samples,
    }
