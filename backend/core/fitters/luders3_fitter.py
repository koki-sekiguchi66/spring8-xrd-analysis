# -*- coding: utf-8 -*-
"""3-Peak Lüders post-deformation continuous fitter (`fitting_3peaks_afterLuders_csv_ver4.py` equivalent).

Fixes all 3 bugs in Section 4 (#2) of Implementation Plan:
- Bug #2-1: Added missing `else:` branch when `scale == 0` so `k == 2` / `k == 3` fixed ratio
  constraints are not overwritten by an unconditional `pars[f'v{k}_amplitude'].set(...)`.
- Bug #2-2: Fixed typo `value=R * scaled_amplitude_guess[0]` -> `value=R2 * scaled_amplitude_guess[0]`
  when `scale == 1` and `k == 3`.
- Bug #2-3: Explicitly initialized `fixed_ratio2 = 0` at the start of loops so `i == undeform_initial`
  never encounters an undefined variable.
- Preserves the `v2_delta` breakwater variable (`v2_center = v1_center + v2_delta`, `min=0.1`).
"""

from __future__ import annotations

import copy
import random
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from lmfit.models import VoigtModel

from .base_fitter import PARAM_NAMES, BaseFitter, FitStepPayload


class Luders3Fitter(BaseFitter):
    engine_name = "3PeaksLuders"

    def __init__(
        self,
        bcg_dir: str | Path,
        peaks: Optional[List[str]],
        init_params: Dict[str, float],
        group_id: Optional[str] = None,
        th_min: float = 10.6,
        th_max: float = 12.3,
        dimt_onset_num: int = 180,
        undeform_initial: int = 200,
        undeform_end: int = 275,
        R: float = 0.52,
        R2: float = 3.45,
        v2_delta_min: float = 0.1,
        default_fit_limits: Optional[Dict[str, Dict[str, float]]] = None,
        update_list: Optional[List[Tuple[str, str, float]]] = None,
        residual_limit: float = 350.0,
        max_attempts: int = 5,
    ) -> None:
        peaks_list = list(peaks) if peaks and len(peaks) == 3 else ["fcc111a", "bcc110a", "bcc1102"]

        # Synthesize 3rd peak initial values if user passed a 2-peak initial set
        norm_init = dict(init_params)
        if "v3_center" not in norm_init:
            norm_init["v3_center"] = float(norm_init.get("v2_center", 11.51)) + 0.08
            norm_init["v3_amplitude"] = max(10.0, float(norm_init.get("v2_amplitude", 500.0)) * 0.25)
            norm_init["v3_sigma"] = float(norm_init.get("v2_sigma", 0.08))
            norm_init["v3_gamma"] = float(norm_init.get("v2_gamma", 0.04))

        # Item 4: Expand default per-frame parameter variation limits (amplitude: 0.80~1.25, sigma & gamma: 0.70~1.40)
        if default_fit_limits is None:
            default_fit_limits = {
                "v1": {
                    "center_min_offset": -0.01,
                    "center_max_offset": 0.005,
                    "amplitude_min_factor": 0.80,
                    "amplitude_max_factor": 1.25,
                    "amplitude_min_offset": 0.0,
                    "amplitude_max_offset": 10.0,
                    "sigma_min_factor": 0.70,
                    "sigma_max_factor": 1.40,
                    "sigma_min_offset": 0.0,
                    "sigma_max_offset": 1e-10,
                    "gamma_min_factor": 0.70,
                    "gamma_max_factor": 1.40,
                    "gamma_min_offset": 0.0,
                    "gamma_max_offset": 1e-10,
                },
                "v2": {
                    "center_min_offset": -0.01,
                    "center_max_offset": 0.01,
                    "amplitude_min_factor": 0.80,
                    "amplitude_max_factor": 1.25,
                    "amplitude_min_offset": 0.0,
                    "amplitude_max_offset": 10.0,
                    "sigma_min_factor": 0.70,
                    "sigma_max_factor": 1.40,
                    "sigma_min_offset": 0.0,
                    "sigma_max_offset": 1e-10,
                    "gamma_min_factor": 0.70,
                    "gamma_max_factor": 1.40,
                    "gamma_min_offset": 0.0,
                    "gamma_max_offset": 1e-10,
                },
                "v3": {
                    "center_min_offset": -0.03,
                    "center_max_offset": 0.08,
                    "amplitude_min_factor": 0.80,
                    "amplitude_max_factor": 1.25,
                    "amplitude_min_offset": 0.0,
                    "amplitude_max_offset": 50.0,
                    "sigma_min_factor": 0.70,
                    "sigma_max_factor": 1.40,
                    "sigma_min_offset": 0.0,
                    "sigma_max_offset": 1e-10,
                    "gamma_min_factor": 0.70,
                    "gamma_max_factor": 1.40,
                    "gamma_min_offset": 0.0,
                    "gamma_max_offset": 1e-10,
                },
            }

        super().__init__(
            bcg_dir=bcg_dir,
            peaks=peaks_list,
            init_params=norm_init,
            group_id=group_id or "".join(peaks_list),
            th_min=th_min,
            th_max=th_max,
            default_fit_limits=default_fit_limits,
            update_list=update_list,
            residual_limit=residual_limit,
            max_attempts=max_attempts,
        )

        self.dimt_onset_num = int(dimt_onset_num)
        self.undeform_initial = int(undeform_initial)
        self.undeform_end = int(undeform_end)
        self.R = float(R)
        self.R2 = float(R2)
        self.v2_delta_min = max(0.02, float(v2_delta_min))

        # Bug #2-3 fix: Explicitly initialize fixed_ratio and fixed_ratio2
        self.fixed_ratio: int = 1
        self.fixed_ratio2: int = 0
        self.scale: int = 0
        self.params_to_update: List[str] = ["center", "amplitude", "sigma", "gamma"]

    def _perform_fitting_once(
        self,
        th: np.ndarray,
        In: np.ndarray,
        cand_pars: Dict[str, float],
        num_val: int,
    ) -> Tuple[Any, Dict[str, np.ndarray], float, float]:
        fit_limits = self.get_effective_limits()
        scaled_amplitude_guess = [
            max(0.0, amp * self.intensity_scale_factor) for amp in self.prev_params["amplitude"]
        ]

        mod = VoigtModel(prefix="v1_") + VoigtModel(prefix="v2_") + VoigtModel(prefix="v3_")
        pars = mod.make_params()

        for k in range(1, self.n + 1):
            lim = fit_limits[f"v{k}"]
            is_v3_suppressed = (k == 3 and self.dimt_onset_num > 0 and num_val < self.dimt_onset_num)
            if k == 1:
                c_min = self.prev_params["center"][0] + lim.get("center_min_offset", -0.01)
                c_max = self.prev_params["center"][0] + lim.get("center_max_offset", 0.005)
                if c_min >= c_max:
                    c_max = c_min + 0.01
                c_val = min(max(cand_pars["v1_center"], c_min + 1e-6), c_max - 1e-6)
                pars["v1_center"].set(value=c_val, min=c_min, max=c_max, vary=True)
            elif k == 2:
                # Breakwater logic: v2_center = v1_center + v2_delta with v2_delta >= v2_delta_min (0.1 deg)
                init_delta = max(self.v2_delta_min, cand_pars["v2_center"] - cand_pars["v1_center"])
                pars.add("v2_delta", value=init_delta, min=self.v2_delta_min, max=2.0, vary=True)
                pars["v2_center"].set(expr="v1_center + v2_delta")
            else:
                init_spacing = abs(self.base_init_pars["v3_center"] - self.base_init_pars["v2_center"])
                min_sep = min(0.03, max(0.005, 0.30 * init_spacing))
                c_min = max(
                    self.prev_params["center"][k - 2] + min_sep,
                    self.prev_params["center"][k - 1] + lim.get("center_min_offset", -0.03),
                )
                c_max = min(self.prev_params["center"][k - 1] + lim.get("center_max_offset", 0.08), 11.85)
                # Item 2: Strict guard right before .set(min=..., max=...)
                if c_min >= c_max:
                    c_max = c_min + max(0.02, min_sep)
                c_val = min(max(cand_pars[f"v{k}_center"], c_min + 1e-6), c_max - 1e-6)
                pars[f"v{k}_center"].set(value=c_val, min=c_min, max=c_max, vary=not is_v3_suppressed)

            # Amplitude setting with Bug #2-1 (missing else), Bug #2-2 (R2 typo), and Item 5 (pre-onset 0 fix)
            if is_v3_suppressed:
                pars["v3_amplitude"].set(value=0.0, min=0.0, max=1e-9, vary=False, expr=None)
            elif self.scale == 0:
                if k == 2 and self.fixed_ratio == 1:
                    base_a = self.R * self.prev_params["amplitude"][0]
                    a_min = max(0.0, base_a * lim.get("amplitude_min_factor", 0.80) + lim.get("amplitude_min_offset", 0.0))
                    a_max = max(a_min + 1.0, base_a * lim.get("amplitude_max_factor", 1.25) + lim.get("amplitude_max_offset", 10.0))
                    pars[f"v{k}_amplitude"].set(
                        value=min(max(cand_pars[f"v{k}_amplitude"], a_min), a_max),
                        min=a_min,
                        max=a_max,
                        vary=True,
                    )
                elif k == 3 and self.fixed_ratio2 == 1:
                    base_a = self.R2 * self.prev_params["amplitude"][0]
                    a_min = max(0.0, base_a * lim.get("amplitude_min_factor", 0.80) + lim.get("amplitude_min_offset", 0.0))
                    a_max = max(a_min + 1.0, base_a * lim.get("amplitude_max_factor", 1.25) + lim.get("amplitude_max_offset", 10.0))
                    pars[f"v{k}_amplitude"].set(
                        value=min(max(cand_pars[f"v{k}_amplitude"], a_min), a_max),
                        min=a_min,
                        max=a_max,
                        vary=True,
                    )
                else:
                    # Bug #2-1 fix: Placed inside `else:` so k==2/k==3 fixed ratio is NOT overwritten!
                    base_a = self.prev_params["amplitude"][k - 1]
                    a_min = max(0.0, base_a * lim.get("amplitude_min_factor", 0.80) + lim.get("amplitude_min_offset", 0.0))
                    a_max = max(a_min + 1.0, base_a * lim.get("amplitude_max_factor", 1.25) + lim.get("amplitude_max_offset", 10.0))
                    pars[f"v{k}_amplitude"].set(
                        value=min(max(cand_pars[f"v{k}_amplitude"], a_min), a_max),
                        min=a_min,
                        max=a_max,
                        vary=True,
                    )
            else:
                if k == 2 and self.fixed_ratio == 1:
                    base_a = self.R * scaled_amplitude_guess[0]
                    a_min = max(0.0, base_a * lim.get("amplitude_min_factor", 0.80) + lim.get("amplitude_min_offset", 0.0))
                    a_max = max(a_min + 1.0, base_a * lim.get("amplitude_max_factor", 1.25) + lim.get("amplitude_max_offset", 10.0))
                    pars[f"v{k}_amplitude"].set(
                        value=min(max(base_a, a_min), a_max),
                        min=a_min,
                        max=a_max,
                        vary=True,
                    )
                elif k == 3 and self.fixed_ratio2 == 1:
                    # Bug #2-2 fix: Use self.R2 * scaled_amplitude_guess[0] instead of R!
                    base_a = self.R2 * scaled_amplitude_guess[0]
                    a_min = max(0.0, base_a * lim.get("amplitude_min_factor", 0.80) + lim.get("amplitude_min_offset", 0.0))
                    a_max = max(a_min + 1.0, base_a * lim.get("amplitude_max_factor", 1.25) + lim.get("amplitude_max_offset", 10.0))
                    pars[f"v{k}_amplitude"].set(
                        value=min(max(base_a, a_min), a_max),
                        min=a_min,
                        max=a_max,
                        vary=True,
                    )
                else:
                    base_a = scaled_amplitude_guess[k - 1]
                    a_min = max(0.0, base_a * lim.get("amplitude_min_factor", 0.80) + lim.get("amplitude_min_offset", 0.0))
                    a_max = max(a_min + 1.0, base_a * lim.get("amplitude_max_factor", 1.25) + lim.get("amplitude_max_offset", 10.0))
                    pars[f"v{k}_amplitude"].set(
                        value=min(max(base_a, a_min), a_max),
                        min=a_min,
                        max=a_max,
                        vary=True,
                    )

            s_prev = self.prev_params["sigma"][k - 1]
            s_min = max(1e-6, s_prev * lim.get("sigma_min_factor", 0.70))
            s_max = max(s_min + 1e-5, s_prev * lim.get("sigma_max_factor", 1.40) + lim.get("sigma_max_offset", 1e-10))
            pars[f"v{k}_sigma"].set(
                value=min(max(cand_pars[f"v{k}_sigma"], s_min), s_max),
                min=s_min,
                max=s_max,
                vary=not is_v3_suppressed,
            )

            g_prev = self.prev_params["gamma"][k - 1]
            g_min = max(1e-10, g_prev * lim.get("gamma_min_factor", 0.70))
            g_max = max(g_min + 1e-5, g_prev * lim.get("gamma_max_factor", 1.40) + lim.get("gamma_max_offset", 1e-10))
            pars[f"v{k}_gamma"].set(
                value=min(max(cand_pars[f"v{k}_gamma"], g_min), g_max),
                min=g_min,
                max=g_max,
                vary=not is_v3_suppressed,
                expr=None,
            )

        out = mod.fit(In, pars, x=th, method="leastsq", max_nfev=1000)
        comps = out.eval_components(x=th)
        residual_mean = float(np.mean(np.abs(out.residual)))
        mean_abs_in = max(1e-6, float(np.mean(np.abs(In))))
        relative_residual = residual_mean / mean_abs_in
        return out, comps, residual_mean, relative_residual

    def fit_one_file(self, file_index: int, completed_count: int) -> FitStepPayload:
        # Item 7-2: Fixed random seed for 100% deterministic reproducibility
        random.seed(42)
        np.random.seed(42)

        num, fname, th, In = self.load_window_data(file_index)

        out, comps, residual_mean, relative_residual = self._perform_fitting_once(th, In, self.Init_pars, num)
        prev_residual = residual_mean
        best_out = out
        best_comps = comps
        best_rel_res = relative_residual
        best_pars = {
            f"v{r}_{name}": float(out.best_values.get(f"v{r}_{name}", self.Init_pars[f"v{r}_{name}"]))
            for r in range(1, self.n + 1)
            for name in PARAM_NAMES
        }

        attempt = 0
        while prev_residual >= self.residual_limit and attempt < self.max_attempts:
            attempt += 1
            trial_pars = copy.deepcopy(best_pars)
            for p_idx in range(1, self.n + 1):
                trial_pars[f"v{p_idx}_amplitude"] *= random.uniform(0.995, 1.005)
            out_try, comps_try, res_mean_try, rel_res_try = self._perform_fitting_once(th, In, trial_pars, num)
            if res_mean_try < prev_residual:
                prev_residual = res_mean_try
                best_out = out_try
                best_comps = comps_try
                best_rel_res = rel_res_try
                for r in range(1, self.n + 1):
                    for name in PARAM_NAMES:
                        best_pars[f"v{r}_{name}"] = float(out_try.best_values.get(f"v{r}_{name}"))

        if self.dimt_onset_num > 0 and num < self.dimt_onset_num:
            best_pars["v3_amplitude"] = 0.0

        self.prev_integral = self.current_integral
        for name in PARAM_NAMES:
            if name in self.params_to_update:
                self.prev_params[name] = [float(best_pars[f"v{r}_{name}"]) for r in range(1, self.n + 1)]
        for r in range(1, self.n + 1):
            for name in PARAM_NAMES:
                self.Init_pars[f"v{r}_{name}"] = self.prev_params[name][r - 1]

        row_data = self.build_row_dict(num, best_pars, residual=best_rel_res)
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
            residual_rmse=prev_residual,
            relative_residual=best_rel_res,
            attempts=attempt,
            is_outlier=bool(prev_residual >= self.residual_limit),
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
        self.results_by_num.clear()
        self.reset_to_initial()
        completed = 0

        # Step 1: Backward from target_index down to 0
        self.scale = 0
        self.fixed_ratio = 1
        self.fixed_ratio2 = 0  # Bug #2-3 fix: explicitly initialized before loop!

        for i in reversed(range(0, self.target_index + 1)):
            num_val = self.files[i][0]
            if num_val > self.undeform_initial:
                self.fixed_ratio = 1
                self.fixed_ratio2 = 0
            else:
                self.fixed_ratio = 1
                self.fixed_ratio2 = 0

            if num_val < self.dimt_onset_num:
                self.prev_params["amplitude"][2] = 0.0
                self.Init_pars["v3_amplitude"] = 0.0

            if self.undeform_initial < num_val < self.undeform_end:
                self.params_to_update = []
            else:
                self.params_to_update = ["center", "amplitude", "sigma", "gamma"]

            completed += 1
            payload = self.fit_one_file(i, completed_count=completed)
            if step_callback:
                step_callback(payload)

        # Step 2: Reset and run forward from target_index + 1 to end
        self.reset_to_initial()
        self.scale = 1
        self.fixed_ratio = 1
        self.fixed_ratio2 = 0
        prev_integral_temp = 0.0

        for i in range(self.target_index + 1, len(self.files)):
            num_val = self.files[i][0]
            if self.undeform_initial < num_val < self.undeform_end:
                self.params_to_update = []
                self.prev_integral = prev_integral_temp
            else:
                self.params_to_update = ["amplitude", "sigma", "gamma"]
                prev_integral_temp = self.prev_integral

            completed += 1
            payload = self.fit_one_file(i, completed_count=completed)
            self.prev_params["amplitude"][2] = float(payload.row_data.get(f"I_{self.peaks[2]}", 0.0))
            self.prev_params["center"][2] = float(payload.row_data.get(f"2th_{self.peaks[2]}", self.prev_params["center"][2]))
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
