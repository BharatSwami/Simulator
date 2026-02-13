
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

class AssetModel(ABC):

    def __init__(self, asset_id, params, rng):
        super().__init__()
        self.asset_id = asset_id
        self.params = self.params
        self.rng = rng

    @abstractmethod
    def step(self, state):
        pass

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



