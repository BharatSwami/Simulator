from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, Session, create_engine, select


class SimulationRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    params_json: str = Field(default="{}")
    notes: Optional[str] = None


class SimulationPoint(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="simulationrun.id", index=True)
    tick_index: int
    timestamp: float
    gold: float
    rate: float
    dollar: float
    wheat: float


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sim.db")

engine = create_engine(DATABASE_URL, echo=False)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)


def create_run(params_json: str, notes: str | None = None) -> SimulationRun:
    with get_session() as session:
        run = SimulationRun(params_json=params_json, notes=notes)
        session.add(run)
        session.commit()
        session.refresh(run)
        return run


def finish_run(run_id: int) -> None:
    with get_session() as session:
        run = session.exec(
            select(SimulationRun).where(SimulationRun.id == run_id)
        ).one_or_none()
        if run is None:
            return
        run.ended_at = datetime.utcnow()
        session.add(run)
        session.commit()


def add_point(
    run_id: int,
    tick_index: int,
    timestamp: float,
    gold: float,
    rate: float,
    dollar: float,
    wheat: float,
) -> None:
    with get_session() as session:
        point = SimulationPoint(
            run_id=run_id,
            tick_index=tick_index,
            timestamp=timestamp,
            gold=gold,
            rate=rate,
            dollar=dollar,
            wheat=wheat,
        )
        session.add(point)
        session.commit()


def get_run_with_points(run_id: int) -> tuple[SimulationRun | None, list[SimulationPoint]]:
    with get_session() as session:
        run = session.get(SimulationRun, run_id)
        if run is None:
            return None, []
        points = session.exec(
            select(SimulationPoint)
            .where(SimulationPoint.run_id == run_id)
            .order_by(SimulationPoint.tick_index)
        ).all()
        return run, list(points)

