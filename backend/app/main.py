from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .simulation import SimulationEngine
from .db import (
    SimulationPoint,
    SimulationRun,
    add_point,
    create_db_and_tables,
    create_run,
    finish_run,
    get_run_with_points,
)


app = FastAPI(title="Economic World Simulator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


engine = SimulationEngine()
engine.state.running = False

_websocket_clients: List[WebSocket] = []
_simulation_task: asyncio.Task | None = None
_current_run_id: int | None = None


@app.on_event("startup")
async def on_startup() -> None:
    create_db_and_tables()


class ParamsUpdate(BaseModel):
    params: Dict[str, Any]


class RunCreate(BaseModel):
    params: Dict[str, Any] | None = None
    notes: str | None = None
    auto_start: bool = True


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/state")
async def get_state() -> Dict[str, Any]:
    """Return current state and recent history."""
    return {
        "current": engine.state.snapshot(),
        "history": engine.state.history_as_list(),
    }


@app.post("/params")
async def update_params(payload: ParamsUpdate) -> Dict[str, Any]:
    engine.set_params(**payload.params)
    return {"ok": True, "params": payload.params}


async def _simulation_loop() -> None:
    """Background loop that advances the simulation and broadcasts ticks."""
    global _simulation_task, _current_run_id
    try:
        while True:
            if engine.state.running:
                point = engine.step()
                if _current_run_id is not None:
                    # Persist a subset of values for now, mapping factors/assets
                    # into the existing SimulationPoint schema.
                    gold_val = float(point.factors.get("gold", 0.0))
                    rate_val = float(point.factors.get("rate", 0.0))
                    dollar_val = float(point.assets.get("USD_IDX", 0.0))
                    wheat_val = float(point.assets.get("WHEAT", 0.0))
                    add_point(
                        run_id=_current_run_id,
                        tick_index=point.tick,
                        timestamp=point.timestamp,
                        gold=gold_val,
                        rate=rate_val,
                        dollar=dollar_val,
                        wheat=wheat_val,
                    )
                message = {
                    "type": "tick",
                    "tick": point.tick,
                    "timestamp": point.timestamp,
                    "factors": point.factors,
                    "assets": point.assets,
                }
                living_clients: List[WebSocket] = []
                for ws in list(_websocket_clients):
                    try:
                        await ws.send_json(message)
                        living_clients.append(ws)
                    except Exception:
                        # Drop dead connections
                        continue
                _websocket_clients[:] = living_clients
            await asyncio.sleep(0.2)
    finally:
        _simulation_task = None


async def _ensure_simulation_task_running() -> None:
    global _simulation_task
    if _simulation_task is None or _simulation_task.done():
        _simulation_task = asyncio.create_task(_simulation_loop())


@app.post("/runs")
async def create_simulation_run(payload: RunCreate) -> Dict[str, Any]:
    """Start a recorded simulation run with optional parameters."""
    global _current_run_id

    params = payload.params or {}
    params_json = json.dumps(params)
    run = create_run(params_json=params_json, notes=payload.notes)
    _current_run_id = run.id

    engine.reset()
    if params:
        engine.set_params(**params)

    if payload.auto_start:
        engine.state.running = True
        await _ensure_simulation_task_running()

    return {"id": run.id, "params": params, "auto_start": payload.auto_start}


@app.get("/runs/{run_id}")
async def get_simulation_run(run_id: int) -> Dict[str, Any]:
    run, points = get_run_with_points(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": run.id,
        "started_at": run.started_at,
        "ended_at": run.ended_at,
        "params_json": run.params_json,
        "notes": run.notes,
        "points": [
            {
                "tick": p.tick_index,
                "timestamp": p.timestamp,
                "gold": p.gold,
                "rate": p.rate,
                "dollar": p.dollar,
                "wheat": p.wheat,
            }
            for p in points
        ],
    }


@app.websocket("/ws/sim")
async def websocket_sim(ws: WebSocket) -> None:
    await ws.accept()
    _websocket_clients.append(ws)

    await _ensure_simulation_task_running()

    await ws.send_json(
        {
            "type": "snapshot",
            "current": engine.state.snapshot(),
            "history": engine.state.history_as_list(),
        }
    )

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")
            if msg_type == "control":
                action = data.get("action")
                if action == "start":
                    engine.state.running = True
                elif action == "pause":
                    engine.state.running = False
                elif action == "reset":
                    engine.reset()
            elif msg_type == "set_params":
                params = data.get("params") or {}
                engine.set_params(**params)
            await ws.send_json(
                {
                    "type": "ack",
                    "state": engine.state.snapshot(),
                }
            )
    except WebSocketDisconnect:
        pass
    finally:
        if ws in _websocket_clients:
            _websocket_clients.remove(ws)

