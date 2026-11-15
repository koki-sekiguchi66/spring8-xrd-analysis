# -*- coding: utf-8 -*-
"""Base class for bidirectional continuous XRD Voigt fitting."""

from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.integrate import trapezoid

from ..excel_io import build_unified_columns
from ..origin_voigt import (
    calc_bcc110_from_bcc211,
    calc_origin_fwhm,
    gamma_to_wL,
    is_martensite_peak,
    sigma_to_wG,
    wG_to_sigma,
    wL_to_gamma,
)
from ..utils import find_file_by_num, list_sorted_bcg_files

PARAM_NAMES = ["center", "amplitude", "sigma", "gamma"]


@dataclass
class FitStepPayload:
    """Data payload emitted after each file is fitted for live WebSocket streaming & review."""

    group_id: str
    engine: str
    peaks: List[str]
    file_index: int
    total_files: int
    completed_files: int
    num: int
    filename: str
    residual_rmse: float
    relative_residual: float
    attempts: int
    is_outlier: bool
    row_data: Dict[str, float]
    x: List[float] = field(default_factory=list)
    y_obs: List[float] = field(default_factory=list)
    y_fit: List[float] = field(default_factory=list)
    components: Dict[str, List[float]] = field(default_factory=dict)

    def to_stream_dict(self, include_waveform: bool = True) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "group_id": self.group_id,
            "engine": self.engine,
            "peaks": self.peaks,
            "file_index": self.file_index,
            "total_files": self.total_files,
            "completed_files": self.completed_files,
            "progress_pct": round(100.0 * self.completed_files / max(1, self.total_files), 1),
            "num": self.num,
            "filename": self.filename,
            "residual_rmse": round(self.residual_rmse, 4),
            "relative_residual": round(self.relative_residual, 5),
            "attempts": self.attempts,
            "is_outlier": self.is_outlier,
            "row_data": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in self.row_data.items()},
        }
        if include_waveform:
            d["waveform"] = {
                "x": [round(v, 4) for v in self.x],
                "y_obs": [round(v, 3) for v in self.y_obs],
                "y_fit": [round(v, 3) for v in self.y_fit],
                "components": {k: [round(v, 3) for v in arr] for k, arr in self.components.items()},
            }
        return d


class BaseFitter:
    """Shared infrastructure for all 4 continuous fitting modes."""

    engine_name: str = "Base"

    def __init__(
        self,
        bcg_dir: str | Path,
        peaks: List[str],
        init_params: Dict[str, float],
        group_id: Optional[str] = None,
        th_min: Optional[float] = None,
        th_max: Optional[float] = None,
        default_fit_limits: Optional[Dict[str, Dict[str, float]]] = None,
        update_list: Optional[List[Tuple[str, str, float]]] = None,
        residual_limit: float = 0.7,
        max_attempts: int = 5,
    ) -> None:
        self.bcg_dir = Path(bcg_dir).resolve()
        self.peaks = list(peaks)
        self.n = len(self.peaks)
        self.group_id = group_id or "".join(self.peaks)
        self.files: List[Tuple[int, Path]] = list_sorted_bcg_files(self.bcg_dir)
        if not self.files:
            raise FileNotFoundError(f"No *bcg.csv files found in {self.bcg_dir}")

        self.base_init_pars = self._normalize_init_pars(init_params)
        self.Init_pars = copy.deepcopy(self.base_init_pars)
        self.prev_params = self._build_prev_params(self.Init_pars)

        self.target_num = int(round(float(self.base_init_pars.get("num", self.files[0][0]))))
        self.target_index, _ = find_file_by_num(self.files, self.target_num)
        if self.target_index < 0:
            self.target_index = 0

        self.th_min = float(th_min) if th_min is not None else float(self.Init_pars["v1_center"] - 0.7)
        self.th_max = float(th_max) if th_max is not None else float(self.Init_pars[f"v{self.n}_center"] + 0.7)

        # Engine defaults (Harada's original values) with any user-supplied entries merged on top,
        # so a partial override (e.g. only v1.amplitude_max_factor) never drops the other keys.
        self.default_fit_limits = self._default_limits()
        for peak_key, entries in (default_fit_limits or {}).items():
            if peak_key in self.default_fit_limits and isinstance(entries, dict):
                for param_key, value in entries.items():
                    if value is not None:
                        self.default_fit_limits[peak_key][param_key] = float(value)
        self.update_list: List[Tuple[str, str, float]] = list(update_list) if update_list else []
        self.residual_limit = float(residual_limit)
        self.max_attempts = int(max_attempts)

        self.prev_integral: float = 0.0
        self.current_integral: float = 0.0
        self.intensity_scale_factor: float = 1.0

        self.results_by_num: Dict[int, FitStepPayload] = {}
        self._file_cache: Dict[int, np.ndarray] = {}

    def _default_limits(self) -> Dict[str, Dict[str, float]]:
        """Per-frame parameter limits (relative to the previous frame).

        Default = `default_fit_limits` of Harada's `fittning_1peaks_ver7.0_NH.py`.
        Each engine overrides this with the defaults of its own original script.
        """
        limits: Dict[str, Dict[str, float]] = {}
        for idx in range(self.n):
            limits[f"v{idx + 1}"] = {
                "center_min_offset": -0.05,
                "center_max_offset": 0.20,
                "amplitude_min_factor": 0.70,
                "amplitude_max_factor": 1.40,
                "amplitude_min_offset": 0.0,
                "amplitude_max_offset": 10.0,
                "sigma_min_factor": 0.80,
                "sigma_max_factor": 1.30,
                "sigma_min_offset": -1e-3,
                "sigma_max_offset": 1e-3,
                "gamma_min_factor": 0.80,
                "gamma_max_factor": 1.30,
                "gamma_min_offset": -1e-3,
                "gamma_max_offset": 1e-3,
            }
        return limits

    @staticmethod
    def merge_limits(
        base: Dict[str, Dict[str, float]],
        update_list: Optional[List[Tuple[str, str, float]]] = None,
    ) -> Dict[str, Dict[str, float]]:
        """Apply Harada-style `update_list = [(peak_key, param_key, value), ...]` to a copy of `base`."""
        merged = copy.deepcopy(base)
        for peak_key, param_key, new_value in update_list or []:
            if peak_key in merged:
                merged[peak_key][param_key] = float(new_value)
        return merged

    @staticmethod
    def bounded(lo: float, hi: float, min_width: float) -> Tuple[float, float]:
        """Return `(lo, hi)` with a guaranteed positive width (lmfit silently swaps inverted bounds)."""
        if not (hi > lo):
            hi = lo + min_width
        return lo, hi

    @staticmethod
    def perturb(pars: Dict[str, float], n: int, ranges: Dict[str, Tuple[float, float]], skip: Optional[List[int]] = None) -> Dict[str, float]:
        """Harada-style random perturbation of starting values.

        `ranges['center']` is an additive range; the others are multiplicative ranges.
        Uses the module-level `random` state, which callers seed per frame for reproducibility.
        """
        out = dict(pars)
        skip_set = set(skip or [])
        for k in range(1, n + 1):
            if (k - 1) in skip_set:
                continue
            if "center" in ranges:
                out[f"v{k}_center"] = out[f"v{k}_center"] + random.uniform(*ranges["center"])
            for name in ("amplitude", "sigma", "gamma"):
                if name in ranges:
                    out[f"v{k}_{name}"] = out[f"v{k}_{name}"] * random.uniform(*ranges[name])
        return out

    def _normalize_init_pars(self, raw: Dict[str, Any]) -> Dict[str, float]:
        """Accept either `{v1_center, v1_amplitude, v1_sigma, v1_gamma}` or `{v1_wG, v1_wL}`."""
        norm: Dict[str, float] = {"num": float(raw.get("num", raw.get("No", 50)))}
        for idx in range(1, self.n + 1):
            norm[f"v{idx}_center"] = float(raw[f"v{idx}_center"])
            norm[f"v{idx}_amplitude"] = max(0.0, float(raw[f"v{idx}_amplitude"]))
            if f"v{idx}_sigma" in raw:
                norm[f"v{idx}_sigma"] = max(1e-7, float(raw[f"v{idx}_sigma"]))
            else:
                norm[f"v{idx}_sigma"] = wG_to_sigma(float(raw.get(f"v{idx}_wG", 0.02)))
            if f"v{idx}_gamma" in raw:
                norm[f"v{idx}_gamma"] = max(1e-10, float(raw[f"v{idx}_gamma"]))
            else:
                norm[f"v{idx}_gamma"] = wL_to_gamma(float(raw.get(f"v{idx}_wL", 0.015)))
        return norm

    def _build_prev_params(self, init_pars: Dict[str, float]) -> Dict[str, List[float]]:
        return {
            name: [float(init_pars[f"v{q}_{name}"]) for q in range(1, self.n + 1)]
            for name in PARAM_NAMES
        }

    def reset_to_initial(self) -> None:
        """Reset tracking state back to initial values before switching direction."""
        self.Init_pars = copy.deepcopy(self.base_init_pars)
        self.prev_params = self._build_prev_params(self.Init_pars)
        self.prev_integral = 0.0
        self.intensity_scale_factor = 1.0

    def get_effective_limits(self) -> Dict[str, Dict[str, float]]:
        fit_limits = copy.deepcopy(self.default_fit_limits)
        if self.update_list:
            for peak_key, param_key, new_value in self.update_list:
                if peak_key in fit_limits and param_key in fit_limits[peak_key]:
                    fit_limits[peak_key][param_key] = float(new_value)
        return fit_limits

    def load_window_data(self, file_index: int) -> Tuple[int, str, np.ndarray, np.ndarray]:
        """Load the `(th, In)` slice within `[th_min, th_max]` for `file_index` and update the integral scaling.

        Faithful to Harada's scripts: the background is removed only once in preprocessing
        (`bg_remover.py`), and the window is fitted with Voigt components only. The edge-based
        10-point linear subtraction exists in the originals only as commented-out code; applying it
        removes the Lorentzian tails of broad alpha' peaks (about -17 % area at FWHM 0.47 deg).
        """
        num, path = self.files[file_index]
        if file_index not in self._file_cache:
            self._file_cache[file_index] = np.loadtxt(path, delimiter=",", dtype=float)
        in_file = self._file_cache[file_index]

        mask = (in_file[:, 0] >= self.th_min) & (in_file[:, 0] <= self.th_max)
        sub = in_file[mask]
        if len(sub) < 8:
            raise ValueError(f"Insufficient points ({len(sub)}) in [{self.th_min}, {self.th_max}] for {path.name}")

        th = sub[:, 0]
        In = sub[:, 1]

        # Integral-intensity scale factor (Harada: current_integral / prev_integral).
        # Bug #8 fix: scipy.integrate.trapezoid instead of the removed np.trapz.
        self.current_integral = max(0.0, float(trapezoid(In, th)))
        if self.prev_integral > 0 and self.current_integral > 0:
            self.intensity_scale_factor = max(0.1, min(10.0, self.current_integral / self.prev_integral))
        else:
            self.intensity_scale_factor = 1.0

        return num, path.name, th, In

    def build_row_dict(self, num: int, best_values: Dict[str, float], residual: float = 0.0) -> Dict[str, float]:
        """Build unified row dictionary `[num, 2th_{peak}, I_{peak}, wG_{peak}, wL_{peak}, FWHM_{peak}, ..., residual]`."""
        row: Dict[str, float] = {"num": int(num)}
        for m, pk in enumerate(self.peaks, 1):
            center = float(best_values.get(f"v{m}_center", 0.0))
            amp = float(best_values.get(f"v{m}_amplitude", 0.0))
            sigma = float(best_values.get(f"v{m}_sigma", 0.0))
            gamma = float(best_values.get(f"v{m}_gamma", 0.0))
            if amp <= 1e-6:
                amp = 0.0
            wG = sigma_to_wG(sigma)
            wL = gamma_to_wL(gamma)
            fwhm = calc_origin_fwhm(wG, wL)
            row[f"2th_{pk}"] = center
            row[f"I_{pk}"] = amp
            row[f"wG_{pk}"] = wG
            row[f"wL_{pk}"] = wL
            row[f"FWHM_{pk}"] = fwhm
        row["residual"] = float(residual)
        return row

    def build_dataframe(self) -> pd.DataFrame:
        """Return sorted DataFrame strictly matching `[num, 2th_{peak}, I_{peak}, wG_{peak}, wL_{peak}, FWHM_{peak}]`."""
        cols = build_unified_columns(self.peaks)
        if not self.results_by_num:
            return pd.DataFrame(columns=cols)
        rows = [
            self.results_by_num[num].row_data
            for num in sorted(self.results_by_num.keys())
        ]
        df = pd.DataFrame(rows)
        for c in cols:
            if c not in df.columns:
                df[c] = np.nan
        return df[cols].sort_values("num").reset_index(drop=True)
