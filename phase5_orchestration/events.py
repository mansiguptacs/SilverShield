"""Shared event schema + in-process pub/sub for the live pipeline trace.

The orchestrator emits stage events; the FastAPI WebSocket fans them out to all
connected browsers. The optional Phase 6 agent layer emits the SAME event types,
so the UI is agnostic to which brain is driving.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass, field
from typing import Any

# Canonical pipeline stages (drive the animated trace in the UI).
STAGES = [
    "fda_alert",          # openFDA recall picked up
    "ingested",           # landed in lakehouse
    "severity_classified",  # ML model scored severity
    "cohort_identified",  # nationwide patient match (per-state)
    "message_drafted",    # outreach message composed
    "dispatched",         # alerts fanned out to cohort
    "card_rendered",      # OpenUI alert card generated
    "cited",              # grounded in cited.md
]


@dataclass
class Event:
    stage: str
    recall_number: str
    payload: dict[str, Any] = field(default_factory=dict)
    actor: str = "orchestrator"
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


class EventBus:
    """Fan-out async broadcaster. Each subscriber gets its own queue."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._history: list[dict] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    async def publish(self, event: Event) -> None:
        data = event.to_dict()
        # Reset replay history at the start of each run so late joiners see only
        # the current run's accumulated state.
        if event.stage == "run_started":
            self._history = []
        self._history.append(data)
        self._history = self._history[-600:]
        for q in list(self._subscribers):
            await q.put(data)

    @property
    def history(self) -> list[dict]:
        return self._history


bus = EventBus()
