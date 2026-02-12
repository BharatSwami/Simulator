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


# @dataclass
# class SimParams:
#     """Global simulation parameters."""

#     dt: float = 0.1  # time step (arbitrary units)
#     history_capacity: int = 500  # number of ticks to keep in history


# @dataclass
# class FactorSpec:
#     name: str
#     type: str
#     params: Dict[str, Any]


# @dataclass
# class AssetSpec:
#     id: str
#     label: str
#     category: str
#     base_price: float
#     process: str
#     params: Dict[str, Any]


# @dataclass
# class SimPoint:
#     tick: int
#     timestamp: float
#     factors: Dict[str, float]
#     assets: Dict[str, float]


# @dataclass
# class SimState:
#     tick: int = 0
#     running: bool = False
#     params: SimParams = field(default_factory=SimParams)
#     factors: Dict[str, float] = field(default_factory=dict)
#     assets: Dict[str, float] = field(default_factory=dict)
#     history: Deque[SimPoint] = field(
#         default_factory=lambda: deque(maxlen=SimParams().history_capacity)
#     )

#     def snapshot(self) -> Dict:
#         return {
#             "tick": self.tick,
#             "timestamp": time.time(),
#             "factors": dict(self.factors),
#             "assets": dict(self.assets),
#         }

#     def history_as_list(self) -> List[Dict]:
#         return [
#             {
#                 "tick": p.tick,
#                 "timestamp": p.timestamp,
#                 "factors": p.factors,
#                 "assets": p.assets,
#             }
#             for p in self.history
#         ]


class SimulationEngine:
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

    # ---- Factor dynamics -------------------------------------------------

    def _step_factor_gbm(self, name: str, spec: FactorSpec) -> float:
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

    # ---- Asset dynamics --------------------------------------------------

    def _step_assets(self) -> None:
        dt = self.params.dt
        factors: Mapping[str, float] = self.state.factors
        new_assets: Dict[str, float] = {}

        for aid, spec in self.asset_specs.items():
            price = self.state.assets.get(aid, spec.base_price)

            if spec.process == "factor_linear_gbm":
                params = spec.params
                alpha = float(params.get("alpha", 0.0))
                sigma = float(params.get("sigma", 0.0))
                betas: Dict[str, float] = params.get("betas", {}) or {}
                mu_eff = alpha
                for fname, beta in betas.items():
                    fval = factors.get(fname, 0.0)
                    # mu_eff += float(beta) * float(fval)
                    prev = self._prev_factors.get(fname, fval)
                    factor_ret = (fval - prev)
                    mu_eff += float(beta) * factor_ret
                dW = self._rng.normal(0.0, math.sqrt(dt))
                log_p = math.log(max(price, 1e-8)) + mu_eff * dt + sigma * dW
                # new_assets[aid] = float(math.exp(log_p))
                MAX_LOG = 700.0
                MIN_LOG = -700.0

                log_p = max(min(log_p, MAX_LOG), MIN_LOG)

                new_assets[aid] = float(math.exp(log_p))

            elif spec.process == "option_call":
                params = spec.params
                underlying_id = params.get("underlying")
                if underlying_id is None or underlying_id not in self.state.assets:
                    new_assets[aid] = price
                    continue
                S = self.state.assets[underlying_id]
                K = float(params.get("strike", S))
                maturity_ticks = int(params.get("maturity_ticks", 50))
                tau = max(0.0, (maturity_ticks - self.state.tick) * dt)
                rate_factor = params.get("rate_factor", "rate")
                vol_factor = params.get("vol_factor", "vol")
                r = float(factors.get(rate_factor, 0.01))
                sigma_impl = float(factors.get(vol_factor, 0.2))
                if tau <= 0.0 or sigma_impl <= 0.0:
                    call_val = max(S - K, 0.0)
                else:
                    try:
                        d1 = (math.log(S / K) + (r + 0.5 * sigma_impl**2) * tau) / (
                            sigma_impl * math.sqrt(tau)
                        )
                        d2 = d1 - sigma_impl * math.sqrt(tau)
                        n_d1 = 0.5 * (1.0 + math.erf(d1 / math.sqrt(2.0)))
                        n_d2 = 0.5 * (1.0 + math.erf(d2 / math.sqrt(2.0)))
                        call_val = float(S * n_d1 - K * math.exp(-r * tau) * n_d2)
                    except (OverflowError, ValueError):
                        call_val = max(S - K, 0.0)
                new_assets[aid] = call_val

            elif spec.process == "future":
                params = spec.params
                underlying_id = params.get("underlying")
                if underlying_id is None or underlying_id not in self.state.assets:
                    new_assets[aid] = price
                    continue
                S = self.state.assets[underlying_id]
                maturity_ticks = int(params.get("maturity_ticks", 50))
                tau = max(0.0, (maturity_ticks - self.state.tick) * dt)
                rate_factor = params.get("rate_factor", "rate")
                r = float(factors.get(rate_factor, 0.01))
                new_assets[aid] = float(S * math.exp(r * tau))

            elif spec.process == "swap_rate":
                params = spec.params
                rate_factor = params.get("rate_factor", "rate")
                maturity_ticks = int(params.get("maturity_ticks", 50))
                tau = max(0.0, (maturity_ticks - self.state.tick) * dt)
                r = float(factors.get(rate_factor, 0.01))
                fixed_rate = float(params.get("fixed_rate", 0.02))
                new_assets[aid] = float((r - fixed_rate) * tau)

            else:
                new_assets[aid] = price

        self.state.assets.update(new_assets)

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

