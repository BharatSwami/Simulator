from __future__ import annotations

from dataclasses import dataclass, field
from typing import Deque, Dict, List, Mapping, Any
from collections import deque
import time




@dataclass
class SimParams:
    """Global simulation parameters."""

    dt: float = 0.1  # time step (arbitrary units)
    history_capacity: int = 500  # number of ticks to keep in history


@dataclass
class FactorSpec:
    name: str
    type: str
    params: Dict[str, Any]


@dataclass
class AssetSpec:
    id: str
    label: str
    category: str
    base_price: float
    process: str
    params: Dict[str, Any]


@dataclass
class SimPoint:
    tick: int
    timestamp: float
    factors: Dict[str, float]
    assets: Dict[str, float]


@dataclass
class SimState:
    tick: int = 0
    running: bool = False
    params: SimParams = field(default_factory=SimParams)
    factors: Dict[str, float] = field(default_factory=dict)
    assets: Dict[str, float] = field(default_factory=dict)
    history: Deque[SimPoint] = field(
        default_factory=lambda: deque(maxlen=SimParams().history_capacity)
    )

    def snapshot(self) -> Dict:
        return {
            "tick": self.tick,
            "timestamp": time.time(),
            "factors": dict(self.factors),
            "assets": dict(self.assets),
        }

    def history_as_list(self) -> List[Dict]:
        return [
            {
                "tick": p.tick,
                "timestamp": p.timestamp,
                "factors": p.factors,
                "assets": p.assets,
            }
            for p in self.history
        ]

