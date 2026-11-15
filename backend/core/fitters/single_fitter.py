# -*- coding: utf-8 -*-
"""Single-peak bidirectional continuous Voigt fitter (`fittning_1peaks_ver7.0_NH.py` equivalent).

Fixes:
- Bug #1: Removed premature `prev_residual = relative_residual` assignment before
  `if relative_residual < prev_residual:`, ensuring the best parameter set across
  random retry attempts is properly preserved.
- Bug #4: Unified column order `[num, 2th_{peak}, I_{peak}, wG_{peak}, wL_{peak}, FWHM_{peak}]`.
- Bug #5: Strict regex file number extraction.
- Bug #6/#7: Removed `plt.show()` blocking; streams results via callback/WebSocket.
- Bug #8: Replaced `np.trapz` with `scipy.integrate.trapezoid`.
"""

from __future__ import annotations

import copy
import random
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from lmfit.models import VoigtModel

from .base_fitter import PARAM_NAMES, BaseFitter, FitStepPayload, is_martensite_peak


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
        dimt_onset_num: int = 200,
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

    def _perform_fitting_once(
        self,
        th: np.ndarray,
        In: np.ndarray,
        cand_init_pars: Dict[str, float],
        num_val: int,
    ) -> Tuple[Any, Dict[str, np.ndarray], float, float]:
        """Run one lmfit Voigt optimization with independent sigma & gamma."""
        fit_limits = self.get_effective_limits()
        scaled_amplitude_guess = [
            max(0.0, amp * self.intensity_scale_factor) for amp in self.prev_params["amplitude"]
        ]

        mod = None
        pars = None

        for k in range(1, self.n + 1):
            prefix = f"v{k}_"
            vm = VoigtModel(prefix=prefix)
            p = vm.make_params()
            lim = fit_limits[f"v{k}"]
            pk_name = self.peaks[k - 1]

            c_prev = self.prev_params["center"][k - 1]
            c_min = c_prev + lim.get("center_min_offset", -0.05)
            c_max = c_prev + lim.get("center_max_offset", 0.20)
            # Item 2: Guard against min >= max inversion
            if c_min >= c_max:
                c_max = c_min + 0.02
            c_val = min(max(cand_init_pars[f"v{k}_center"], c_min + 1e-6), c_max - 1e-6)

            # Item 4: Default variation limits: amplitude 0.80 ~ 1.25, sigma & gamma 0.70 ~ 1.40
            amp_guess = scaled_amplitude_guess[k - 1]
            a_min = max(0.0, amp_guess * lim.get("amplitude_min_factor", 0.80) + lim.get("amplitude_min_offset", 0.0))
            a_max = max(a_min + 1.0, amp_guess * lim.get("amplitude_max_factor", 1.25) + lim.get("amplitude_max_offset", 10.0))
            a_val = min(max(amp_guess, a_min), a_max)

            s_prev = self.prev_params["sigma"][k - 1]
            s_min = max(1e-6, s_prev * lim.get("sigma_min_factor", 0.70) + lim.get("sigma_min_offset", 0.0))
            s_max = max(s_min + 1e-5, s_prev * lim.get("sigma_max_factor", 1.40) + lim.get("sigma_max_offset", 1e-6))
            s_val = min(max(cand_init_pars[f"v{k}_sigma"], s_min), s_max)

            g_prev = self.prev_params["gamma"][k - 1]
            g_min = max(1e-10, g_prev * lim.get("gamma_min_factor", 0.70) + lim.get("gamma_min_offset", 0.0))
            g_max = max(g_min + 1e-5, g_prev * lim.get("gamma_max_factor", 1.40) + lim.get("gamma_max_offset", 1e-6))
            g_val = min(max(cand_init_pars[f"v{k}_gamma"], g_min), g_max)

            # Item 5: Fix martensite (alpha'-BCC) peak intensity to 0.0 before transformation onset (num < dimt_onset_num)
            is_suppressed = (
                self.dimt_onset_num > 0
                and num_val < self.dimt_onset_num
                and is_martensite_peak(pk_name)
            )
            if is_suppressed:
                p[f"{prefix}center"].set(value=c_val, min=c_min, max=c_max, vary=False)
                p[f"{prefix}amplitude"].set(value=0.0, min=0.0, max=1e-9, vary=False, expr=None)
                p[f"{prefix}sigma"].set(value=s_val, min=s_min, max=s_max, vary=False)
                p[f"{prefix}gamma"].set(value=g_val, min=g_min, max=g_max, vary=False, expr=None)
            else:
                p[f"{prefix}center"].set(value=c_val, min=c_min, max=c_max, vary=True)
                p[f"{prefix}amplitude"].set(value=a_val, min=a_min, max=a_max, vary=True)
                p[f"{prefix}sigma"].set(value=s_val, min=s_min, max=s_max, vary=True)
                # Item 1: Origin-compatible independent Lorentzian width (vary=True, expr=None)
                p[f"{prefix}gamma"].set(value=g_val, min=g_min, max=g_max, vary=True, expr=None)

            if mod is None:
                mod = vm
                pars = p
            else:
                mod += vm
                pars.update(p)

        out = mod.fit(In, pars, x=th, method="leastsq", max_nfev=1000)
        comps = out.eval_components(x=th)
        residual_mean = float(np.sqrt(np.mean(out.residual ** 2)))
        mean_abs_in = max(1e-6, float(np.mean(np.abs(In))))
        relative_residual = residual_mean / mean_abs_in

        return out, comps, residual_mean, relative_residual

    def fit_one_file(self, file_index: int, completed_count: int) -> FitStepPayload:
        # Item 7-2: Fixed random seed for 100% deterministic reproducibility
        random.seed(42)
        np.random.seed(42)

        num, fname, th, In = self.load_window_data(file_index)

        # Initial fit pass
        work_pars = copy.deepcopy(self.Init_pars)
        out, comps, residual_mean, relative_residual = self._perform_fitting_once(th, In, work_pars, num)

        # Item 3-1: Initialize prev_residual and best state from initial fit BEFORE retry loop
        prev_residual = relative_residual
        best_out = out
        best_comps = comps
        best_residual_mean = residual_mean
        best_pars = {
            f"v{r}_{name}": float(out.best_values.get(f"v{r}_{name}", work_pars[f"v{r}_{name}"]))
            for r in range(1, self.n + 1)
            for name in PARAM_NAMES
        }

        all_suppressed = all(
            self.dimt_onset_num > 0 and num < self.dimt_onset_num and is_martensite_peak(pk)
            for pk in self.peaks
        )

        attempt = 0
        while not all_suppressed and prev_residual >= self.residual_limit and attempt < self.max_attempts:
            attempt += 1
            trial_pars = copy.deepcopy(best_pars)
            for p_idx in range(1, self.n + 1):
                trial_pars[f"v{p_idx}_center"] += random.uniform(-0.002, 0.002)
                trial_pars[f"v{p_idx}_amplitude"] *= random.uniform(0.95, 1.05)
                trial_pars[f"v{p_idx}_sigma"] *= random.uniform(0.90, 1.10)
                trial_pars[f"v{p_idx}_gamma"] *= random.uniform(0.90, 1.10)

            out_try, comps_try, res_mean_try, rel_res_try = self._perform_fitting_once(th, In, trial_pars, num)

            # Item 3-1: ONLY update prev_residual and best_out/best_pars when residual strictly improves!
            if rel_res_try < prev_residual:
                prev_residual = rel_res_try
                best_out = out_try
                best_comps = comps_try
                best_residual_mean = res_mean_try
                for r in range(1, self.n + 1):
                    for name in PARAM_NAMES:
                        best_pars[f"v{r}_{name}"] = float(out_try.best_values.get(f"v{r}_{name}"))

        # Update tracking state for next file (unless peak was suppressed to 0 before DIMT onset)
        if not all_suppressed:
            self.prev_integral = self.current_integral
            self.prev_params = {
                name: [float(best_pars[f"v{r}_{name}"]) for r in range(1, self.n + 1)]
                for name in PARAM_NAMES
            }
            for r in range(1, self.n + 1):
                for name in PARAM_NAMES:
                    self.Init_pars[f"v{r}_{name}"] = self.prev_params[name][r - 1]
        else:
            for r in range(1, self.n + 1):
                best_pars[f"v{r}_amplitude"] = 0.0

        row_data = self.build_row_dict(num, best_pars, residual=prev_residual)
        comp_lists = {
            self.peaks[r - 1]: best_comps.get(f"v{r}_", np.zeros_like(th)).tolist()
            for r in range(1, self.n + 1)
        }

        payload = FitStepPayload(
            group_id=self.group_id,
            engine=self.engine_name,
            peaks=self.peaks,
            file_index=file_index,
            total_files=len(self.files),
            completed_files=completed_count,
            num=num,
            filename=fname,
            residual_rmse=best_residual_mean,
            relative_residual=prev_residual,
            attempts=attempt,
            is_outlier=bool(not all_suppressed and prev_residual >= self.residual_limit),
            row_data=row_data,
            x=th.tolist(),
            y_obs=In.tolist(),
            y_fit=best_out.best_fit.tolist(),
            components=comp_lists,
        )
        self.results_by_num[num] = payload
        return payload

    def run_all(
        self,
        step_callback: Optional[Callable[[FitStepPayload], None]] = None,
    ) -> Dict[str, Any]:
        """Run bidirectional fitting from `target_index -> 0` and `target_index + 1 -> end`."""
        self.results_by_num.clear()
        self.reset_to_initial()
        completed = 0

        # Step 1: Backward from target_index down to 0
        for i in reversed(range(0, self.target_index + 1)):
            completed += 1
            payload = self.fit_one_file(i, completed_count=completed)
            if step_callback:
                step_callback(payload)

        # Step 2: Reset to initial and run forward from target_index + 1 to end
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
