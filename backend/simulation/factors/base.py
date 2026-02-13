
from __future__ import annotations
from abc import ABC, abstractmethod
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

from ..assests.base import AssetModel

class FactorModel(AssetModel):

    def __init__(self):
        super().__init__()


    @abstractmethod
    def step(self):
        pass

    # ---- Factor dynamics -------------------------------------------------

    def _step_factor_gbm(self, name: str, spec: FactorSpec) -> float:
        # print("hello")
        dt = self.params.dt
        x = self.state.factors[name]
        mu = float(spec.params.get("mu", 0.0))
        sigma = float(spec.params.get("sigma", 0.0))
        dW = self._rng.normal(0.0, math.sqrt(dt))
        return float(x * math.exp((mu - 0.5 * sigma * sigma) * dt + sigma * dW))

    def _step_factor_ou(self, name: str, spec: FactorSpec) -> float:
        dt = self.params.dt
        x = self.state.factors[name]
        mean = float(spec.params.get("mean", 0.0))
        kappa = float(spec.params.get("kappa", 0.1))
        sigma = float(spec.params.get("sigma", 0.0))
        dW = self._rng.normal(0.0, math.sqrt(dt))
        return float(x + kappa * (mean - x) * dt + sigma * dW)

    def _step_factor_rw(self, name: str, spec: FactorSpec) -> float:
        dt = self.params.dt
        x = self.state.factors[name]
        mu = float(spec.params.get("mu", 0.0))
        sigma = float(spec.params.get("sigma", 0.0))
        dW = self._rng.normal(0.0, math.sqrt(dt))
        return float(x + mu * dt + sigma * dW)

    def _step_factors(self) -> None:
        new_values: Dict[str, float] = {}
        for name, spec in self.factor_specs.items():
            if spec.type == "gbm":
                new_values[name] = self._step_factor_gbm(name, spec)
            elif spec.type == "ou":
                new_values[name] = self._step_factor_ou(name, spec)
            else:
                new_values[name] = self._step_factor_rw(name, spec)
        self.state.factors.update(new_values)