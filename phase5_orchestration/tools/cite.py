"""Grounding / citation tool: append every action to cited.md with its openFDA
source URL. This is the auditable "ground truth" trail (also the natural hook
for Senso.ai in Phase 7).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[2]
CITED_PATH = ROOT / "cited.md"
_lock = Lock()


def cite(recall_number: str, severity: str, source_url: str, summary: str) -> str:
    """Append a grounded citation entry; return the markdown snippet."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    entry = (
        f"- **{ts}** | recall `{recall_number}` | severity **{severity}**\n"
        f"  - {summary}\n"
        f"  - source: {source_url}\n"
    )
    with _lock:
        if not CITED_PATH.exists():
            CITED_PATH.write_text(
                "# FDA SafetyNet - Grounded Action Log\n\n"
                "Every alert below is traceable to an openFDA enforcement record.\n\n"
            )
        with CITED_PATH.open("a") as fh:
            fh.write(entry)
    return entry
