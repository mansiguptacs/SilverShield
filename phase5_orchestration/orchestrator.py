"""Deterministic orchestrator (Phase 5 core / MVP brain).

Walks each matched recall through the canonical pipeline, emitting events the UI
animates. The agent layer (Phase 6) is an optional swap that reuses these exact
tools + events.

Confidentiality by design: the orchestrator only ever handles de-identified
aggregates. PII re-association happens inside the data-layer dispatch tool.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from phase4_ml.predict import classify  # noqa: E402
from phase5_orchestration.events import Event, bus  # noqa: E402
from phase5_orchestration.tools import clickhouse_tools, sms_stub  # noqa: E402
from phase5_orchestration.tools.cite import cite  # noqa: E402
from phase5_orchestration.tools.openui_client import render_alert_card  # noqa: E402

# Per-stage hold times so the live trace is readable - linger on the moments
# that matter (cohort match, dispatch, the generated card).
STAGE_DELAYS = {
    "fda_alert": 2.0,
    "ingested": 1.0,
    "severity_classified": 2.0,
    "cohort_identified": 2.4,
    "message_drafted": 2.2,
    "dispatched": 2.4,
    "card_rendered": 3.0,
    "cited": 1.8,
}


async def _emit(stage: str, recall_number: str, payload: dict, actor: str = "orchestrator"):
    await bus.publish(Event(stage=stage, recall_number=recall_number, payload=payload, actor=actor))
    await asyncio.sleep(STAGE_DELAYS.get(stage, 1.2))


async def process_recall(recall: dict) -> None:
    rn = recall["recall_number"]

    await _emit("fda_alert", rn, {
        "recalling_firm": recall["recalling_firm"],
        "product_ndc": recall["product_ndc"],
        "reason_for_recall": recall["reason_for_recall"],
        "source_url": recall["source_url"],
    })

    await _emit("ingested", rn, {"source": "openFDA enforcement", "ndc": recall["product_ndc"]})

    # ML severity (on text only - no PII).
    pred = classify(recall["reason_for_recall"], recall.get("severity"))
    severity = pred["severity"]
    await _emit("severity_classified", rn, {
        "severity": severity, "confidence": pred["confidence"], "model": pred["source"],
    })

    # Nationwide cohort match (de-identified per-state rollup + pharmacy points).
    cohort = clickhouse_tools.cohort_summary(rn)
    points = clickhouse_tools.affected_pharmacy_points(rn)
    await _emit("cohort_identified", rn, {
        "severity": severity,
        "total_customers": cohort["total_customers"],
        "total_pharmacies": cohort["total_pharmacies"],
        "total_states": cohort["total_states"],
        "by_state": cohort["by_state"],
        "pharmacy_points": points,
    })

    # Compose outreach message.
    message = sms_stub.build_message(severity, recall["recalling_firm"], recall["product_ndc"])
    await _emit("message_drafted", rn, {"severity": severity, "message": message})

    # Dispatch to the cohort (aggregates + masked samples only).
    result = sms_stub.dispatch_to_cohort(rn, severity, recall["recalling_firm"], recall["product_ndc"])
    await _emit("dispatched", rn, {
        "channel": result["channel"],
        "dispatched": result["dispatched"],
        "pharmacies_notified": result["pharmacies_notified"],
        "states": result["states"],
        "sample_recipients": result["sample_recipients"],
    })

    # Runtime OpenUI alert card.
    card = render_alert_card({
        "recall_number": rn, "severity": severity, "product_ndc": recall["product_ndc"],
        "recalling_firm": recall["recalling_firm"], "reason_for_recall": recall["reason_for_recall"],
        "customers": cohort["total_customers"], "pharmacies": cohort["total_pharmacies"],
        "states": cohort["total_states"],
    })
    await _emit("card_rendered", rn, {"html": card["html"], "generated_by": card["generated_by"]})

    # Ground the action.
    cite(rn, severity, recall["source_url"],
         f"Alerted {cohort['total_customers']:,} customers across "
         f"{cohort['total_states']} states ({recall['recalling_firm']}).")
    await _emit("cited", rn, {"file": "cited.md", "severity": severity})


async def run(limit: int = 8) -> None:
    recalls = clickhouse_tools.list_match_recalls(limit=limit)
    await bus.publish(Event(stage="run_started", recall_number="-", payload={"recalls": len(recalls)}))
    for recall in recalls:
        await process_recall(recall)
    await bus.publish(Event(stage="run_complete", recall_number="-", payload={"recalls": len(recalls)}))


if __name__ == "__main__":
    async def _main():
        recalls = clickhouse_tools.list_match_recalls(limit=3)
        print(f"Processing {len(recalls)} recalls (printing events)...")
        q = bus.subscribe()

        async def printer():
            while True:
                ev = await q.get()
                p = ev["payload"]
                extra = p.get("total_customers", p.get("dispatched", p.get("severity", "")))
                print(f"  [{ev['stage']:>20}] {ev['recall_number']:<16} {extra}")

        task = asyncio.create_task(printer())
        await run(limit=3)
        await asyncio.sleep(0.2)
        task.cancel()

    asyncio.run(_main())
