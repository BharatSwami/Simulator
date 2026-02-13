from __future__ import annotations

from dataclasses import dataclass, field
from typing import Deque, Dict, List, Mapping, Any
from collections import deque
from pathlib import Path
import time
import json
import math

import numpy as np

from simulation.define.base import (
    SimParams,
    SimState,
    AssetSpec,
    FactorSpec,
    SimPoint
)

from simulation.factors.base import FactorModel



class SimulationEngine(FactorModel):
    """Configurable factor + asset simulation engine."""

    def __init__(
        self,
        seed: int | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        base_dir = Path(__file__).resolve().parents[1]
        if config_path is None:
            config_path = base_dir / "config" / "model.json"
        self._config_path = Path(config_path)
        self._config = self._load_config(self._config_path)

        self.params = SimParams()

        self.factor_specs: Dict[str, FactorSpec] = {}
        for name, spec in self._config.get("factors", {}).items():
            self.factor_specs[name] = FactorSpec(
                name=name,
                type=spec.get("type", "rw"),
                params=spec.get("params", {}),
            )

        self.asset_specs: Dict[str, AssetSpec] = {}
        for aid, spec in self._config.get("assets", {}).items():
            self.asset_specs[aid] = AssetSpec(
                id=aid,
                label=spec.get("label", aid),
                category=spec.get("category", "other"),
                base_price=float(spec.get("base_price", 1.0)),
                process=spec.get("process", "factor_linear_gbm"),
                params=spec.get("params", {}),
            )

        self.state = SimState(params=self.params)
        self._rng = np.random.default_rng(seed)
        self._init_state_from_specs()
        self._prev_factors = dict(self.state.factors)


    @staticmethod
    def _load_config(path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _init_state_from_specs(self) -> None:
        self.state.tick = 0
        self.state.factors = {}
        for name, spec in self.factor_specs.items():
            start = float(spec.params.get("start", 0.0))
            self.state.factors[name] = start
        self.state.assets = {}
        for aid, spec in self.asset_specs.items():
            self.state.assets[aid] = float(spec.base_price)
        self.state.history = deque(maxlen=self.state.params.history_capacity)

    def reset(self, seed: int | None = None) -> None:
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        self._init_state_from_specs()

    def set_params(self, **kwargs) -> None:
        # Currently support only dt/history_capacity via params;
        # factor/asset-specific overrides can be added later if needed.
        if "dt" in kwargs:
            self.params.dt = float(kwargs["dt"])
        if "history_capacity" in kwargs:
            self.params.history_capacity = int(kwargs["history_capacity"])
            self.state.history = deque(maxlen=self.params.history_capacity)


    # ---- Public step API -------------------------------------------------

    def step(self) -> SimPoint:
        self.state.tick += 1
        self._step_factors()
        self._step_assets()
        # After everything is computed,
        # update previous factor memory
        self._prev_factors = dict(self.state.factors)

        point = SimPoint(
            tick=self.state.tick,
            timestamp=time.time(),
            factors=dict(self.state.factors),
            assets=dict(self.state.assets),
        )
        self.state.history.append(point)
        return point

