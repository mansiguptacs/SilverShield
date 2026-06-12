"""FastAPI backend: REST + WebSocket live trace + static frontend.

Run:
    .venv/bin/uvicorn phase5_orchestration.server:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from phase5_orchestration import orchestrator  # noqa: E402
from phase5_orchestration.events import bus  # noqa: E402
from phase5_orchestration.tools import clickhouse_tools  # noqa: E402

FRONTEND = Path(__file__).resolve().parent / "frontend"

app = FastAPI(title="FDA SafetyNet")

_run_lock = asyncio.Lock()


@app.get("/api/stats")
async def stats():
    return clickhouse_tools.global_stats()


@app.get("/api/recalls")
async def recalls(limit: int = 12):
    return clickhouse_tools.list_match_recalls(limit=limit)


@app.get("/api/pharmacies")
async def pharmacies(sample: int = 1400):
    return clickhouse_tools.pharmacy_network(sample=sample)


@app.post("/api/run")
async def run(limit: int = 8):
    if _run_lock.locked():
        return JSONResponse({"status": "already_running"}, status_code=409)

    async def _runner():
        async with _run_lock:
            await orchestrator.run(limit=limit)

    asyncio.create_task(_runner())
    return {"status": "started", "limit": limit}


@app.websocket("/stream")
async def stream(ws: WebSocket):
    await ws.accept()
    q = bus.subscribe()
    try:
        # Replay current run so refreshes / late joiners catch up to live state.
        for past in list(bus.history):
            await ws.send_json(past)
        while True:
            event = await q.get()
            await ws.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(q)


@app.get("/")
async def index():
    return FileResponse(FRONTEND / "index.html")


if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")
