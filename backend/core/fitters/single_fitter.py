# -*- coding: utf-8 -*-
"""Single-peak bidirectional continuous Voigt fitter.

Faithful port of Harada's `fittning_1peaks_ver7.0_NH.py`:
- The window `[xc0 + fitting_range_min, xc0 + fitting_range_max]` (default +-0.7 deg) of the
  background-removed data is fitted with ONE Voigt function and no local background term.
- Per-frame limits are relative to the previous frame (`default_fit_limits` of ver7.0).
- The amplitude guess is scaled by the window integral ratio `current_integral / prev_integral`.
- Starting values are randomly perturbed before every fit; if the relative residual
  `RMS(residual) / mean(|I|)` exceeds `residual_limit`, the fit is retried with larger perturbations.
- Backward pass `target -> first file`, then a reset to the initial values and a forward pass
  `target + 1 -> last file`.
- ver7.0 has no "zero before DIMT onset" logic for single peaks; it is available here only as an
  opt-in (`suppress_before_onset=True`).

Bug fixes relative to ver7.0 (logic only, the analysis method is unchanged):
- #1 Retry loop: `prev_residual = relative_residual` was assigned before the comparison, so the best
  attempt was never kept. The best attempt (lowest relative residual) is now kept.
- Multiple peaks in one run reused `prev_params` of the previous peak (window and bounds of the 2nd
  peak were centred on the 1st peak). Each peak now has its own fitter instance and state.
- The forward pass kept `prev_integral` from the end of the backward pass; it is now reset.
- #5 strict file-number parsing, #6 no `plt.show()`, #8 `np.trapz` -> `scipy.integrate.trapezoid`.
- Fixed random seed per frame for reproducibility.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from lmfit.models import VoigtModel

from .base_fitter import PARAM_NAMES, BaseFitter, FitStepPayload, is_martensite_peak

# Perturbation ranges of ver7.0 (center: additive, others: multiplicative)
_PRE_FIT_PERTURB = {"center": (-0.001, 0.001), "amplitude": (0.999, 1.001), "sigma": (0.95, 1.05), "gamma": (0.95, 1.05)}
_RETRY_PERTURB = {"center": (-0.001, 0.001), "amplitude": (0.97, 1.03), "sigma": (0.90, 1.10), "gamma": (0.90, 1.10)}


class SinglePeakFitter(BaseFitter):
    engine_name = "1Peak"

    def __init__(
        self,
        bcg_dir: str | Path,
        peak: str | List[str],
        init_params: Dict[str, float],
        group_id: Optional[str] = None,
        fitting_range_min: float = -0.7,
        fitting_range_max: float = 0.7,
        th_min: Optional[float] = None,
        th_max: Optional[float] = None,
        dimt_onset_num: int = 0,
        suppress_before_onset: bool = False,
        default_fit_limits: Optional[Dict[str, Dict[str, float]]] = None,
        update_list: Optional[List[Tuple[str, str, float]]] = None,
        residual_limit: float = 0.7,
        max_attempts: int = 5,
    ) -> None:
        peaks_list = [peak] if isinstance(peak, str) else list(peak)
        c0 = float(init_params["v1_center"])
        eff_th_min = float(th_min) if th_min is not None else (c0 + fitting_range_min)
        eff_th_max = float(th_max) if th_max is not None else (c0 + fitting_range_max)

        super().__init__(
            bcg_dir=bcg_dir,
            peaks=peaks_list,
            init_params=init_params,
            group_id=group_id or peaks_list[0],
            th_min=eff_th_min,
            th_max=eff_th_max,
            default_fit_limits=default_fit_limits,
            update_list=update_list,
            residual_limit=residual_limit,
            max_attempts=max_attempts,
        )
        self.dimt_onset_num = int(dimt_onset_num)
        self.suppress_before_onset = bool(suppress_before_onset)

    def _is_suppressed(self, k_zero_based: int, num_val: int) -> bool:
        return (
            self.suppress_before_onset
            and self.dimt_onset_num > 0
            and num_val < self.dimt_onset_num
            and is_martensite_peak(self.peaks[k_zero_based])
        )

    def _perform_fitting_once(
        self,
        th: np.ndarray,
        In: np.ndarray,
        cand_pars: Dict[str, float],
        num_val: int,
    ) -> Tuple[Any, Dict[str, np.ndarray], float, float]:
        """One lmfit Voigt optimisation with ver7.0 bounds (sigma and gamma independent)."""
        lim_all = self.get_effective_limits()
        scaled = [amp * self.intensity_scale_factor for amp in self.prev_params["amplitude"]]

        mod = None
        pars = None
        for k in range(1, self.n + 1):
            prefix = f"v{k}_"
            vm = VoigtModel(prefix=prefix)
            p = vm.make_params()
            lim = lim_all[f"v{k}"]

            c_prev = self.prev_params["center"][k - 1]
            c_min, c_max = self.bounded(c_prev + lim["center_min_offset"], c_prev + lim["center_max_offset"], 0.02)

            a_min = max(0.0, scaled[k - 1] * lim["amplitude_min_factor"] + lim["amplitude_min_offset"])
            a_max = scaled[k - 1] * lim["amplitude_max_factor"] + lim["amplitude_max_offset"]
            a_min, a_max = self.bounded(a_min, a_max, 1.0)

            s_prev = self.prev_params["sigma"][k - 1]
            s_min = max(1e-6, s_prev * lim["sigma_min_factor"] + lim["sigma_min_offset"])
            s_min, s_max = self.bounded(s_min, s_prev * lim["sigma_max_factor"] + lim["sigma_max_offset"], 1e-5)

            g_prev = self.prev_params["gamma"][k - 1]
            g_min = max(0.0, g_prev * lim["gamma_min_factor"] + lim["gamma_min_offset"])
            g_min, g_max = self.bounded(g_min, g_prev * lim["gamma_max_factor"] + lim["gamma_max_offset"], 1e-5)

            vary = not self._is_suppressed(k - 1, num_val)
            p[f"{prefix}center"].set(value=float(np.clip(cand_pars[f"v{k}_center"], c_min, c_max)), min=c_min, max=c_max, vary=vary)
            if vary:
                p[f"{prefix}amplitude"].set(value=float(np.clip(scaled[k - 1], a_min, a_max)), min=a_min, max=a_max, vary=True)
            else:
                p[f"{prefix}amplitude"].set(value=0.0, min=0.0, max=1e-9, vary=False)
            p[f"{prefix}sigma"].set(value=float(np.clip(cand_pars[f"v{k}_sigma"], s_min, s_max)), min=s_min, max=s_max, vary=vary)
            # lmfit's VoigtModel ties gamma to sigma by default (expr='sigma'); Origin fits wL independently.
            p[f"{prefix}gamma"].set(value=float(np.clip(cand_pars[f"v{k}_gamma"], g_min, g_max)), min=g_min, max=g_max, vary=vary, expr=None)

            if mod is None:
                mod, pars = vm, p
            else:
                mod += vm
                pars.update(p)

        out = mod.fit(In, pars, x=th, method="leastsq")
        comps = out.eval_components(x=th)
        residual_mean = float(np.sqrt(np.mean(out.residual ** 2)))
        relative_residual = residual_mean / max(1e-12, float(np.mean(np.abs(In))))
        return out, comps, residual_mean, relative_residual

    def fit_one_file(self, file_index: int, completed_count: int) -> FitStepPayload:
        random.seed(42)
        np.random.seed(42)

        num, fname, th, In = self.load_window_data(file_index)
        suppressed_idx = [k for k in range(self.n) if self._is_suppressed(k, num)]

        # ver7.0: perturb the starting values, then fit
        start = self.perturb(self.Init_pars, self.n, _PRE_FIT_PERTURB, skip=suppressed_idx)
        out, comps, residual_mean, relative_residual = self._perform_fitting_once(th, In, start, num)
        best = (relative_residual, out, comps, residual_mean)

        attempt = 0
        while best[0] >= self.residual_limit and attempt < self.max_attempts and len(suppressed_idx) < self.n:
            attempt += 1
            base = {f"v{r}_{nm}": float(best[1].best_values[f"v{r}_{nm}"]) for r in range(1, self.n + 1) for nm in PARAM_NAMES}
            trial = self.perturb(base, self.n, _RETRY_PERTURB, skip=suppressed_idx)
            o2, c2, rm2, rr2 = self._perform_fitting_once(th, In, trial, num)
            if rr2 < best[0]:  # Bug #1 fix: keep the best attempt only
                best = (rr2, o2, c2, rm2)

        relative_residual, out, comps, residual_mean = best
        best_pars = {f"v{r}_{nm}": float(out.best_values[f"v{r}_{nm}"]) for r in range(1, self.n + 1) for nm in PARAM_NAMES}

        # Carry the fitted parameters to the next frame (suppressed peaks keep their previous state)
        self.prev_integral = self.current_integral
        for r in range(1, self.n + 1):
            if (r - 1) in suppressed_idx:
                best_pars[f"v{r}_amplitude"] = 0.0
                continue
            for nm in PARAM_NAMES:
                self.prev_params[nm][r - 1] = best_pars[f"v{r}_{nm}"]
                self.Init_pars[f"v{r}_{nm}"] = best_pars[f"v{r}_{nm}"]

        row_data = self.build_row_dict(num, best_pars, residual=relative_residual)
        comp_lists = {self.peaks[r - 1]: comps.get(f"v{r}_", np.zeros_like(th)).tolist() for r in range(1, self.n + 1)}
        payload = FitStepPayload(
            group_id=self.group_id,
            engine=self.engine_name,
            peaks=self.peaks,
            file_index=file_index,
            total_files=len(self.files),
            completed_files=completed_count,
            num=num,
            filename=fname,
            residual_rmse=residual_mean,
            relative_residual=relative_residual,
            attempts=attempt,
            is_outlier=bool(len(suppressed_idx) < self.n and relative_residual >= self.residual_limit),
            row_data=row_data,
            x=th.tolist(),
            y_obs=In.tolist(),
            y_fit=out.best_fit.tolist(),
            components=comp_lists,
        )
        self.results_by_num[num] = payload
        return payload

    def run_all(self, step_callback: Optional[Callable[[FitStepPayload], None]] = None) -> Dict[str, Any]:
        """Backward pass `target -> first`, reset to initial values, forward pass `target + 1 -> last`."""
        self.results_by_num.clear()
        self.reset_to_initial()
        completed = 0
        for i in reversed(range(0, self.target_index + 1)):
            completed += 1
            payload = self.fit_one_file(i, completed_count=completed)
            if step_callback:
                step_callback(payload)

        self.reset_to_initial()
        for i in range(self.target_index + 1, len(self.files)):
            completed += 1
            payload = self.fit_one_file(i, completed_count=completed)
            if step_callback:
                step_callback(payload)

        df = self.build_dataframe()
        return {
            "group_id": self.group_id,
            "engine": self.engine_name,
            "peaks": self.peaks,
            "dataframe": df,
            "rows": df.to_dict(orient="records"),
            "results_by_num": self.results_by_num,
        }
