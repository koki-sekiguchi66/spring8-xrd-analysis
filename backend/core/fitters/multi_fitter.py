# -*- coding: utf-8 -*-
"""General multi-peak simultaneous continuous Voigt fitter (`fitting_multi peaks_csv_ver4.0.0.py` equivalent).

Fixes:
- Bug #3: Replaced invalid list indexing `prev_params['amplitude'][newly_forms_peak] = 0`
  (which raises `TypeError`) with an explicit loop over `newly_forms_peak`.
- Bug #1: Proper best-residual tracking in retry loop.
- Bug #4: Unified output column order `[num, 2th_{peak}, I_{peak}, wG_{peak}, wL_{peak}, FWHM_{peak}]`.
- Bug #5: Strict regex file number extraction.
- Bug #6/#7: Removed `plt.show()` inside loops.
- Bug #8: Replaced `np.trapz` with `scipy.integrate.trapezoid`.
"""

from __future__ import annotations

import copy
import random
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from lmfit.models import VoigtModel

from .base_fitter import (
    PARAM_NAMES,
    BaseFitter,
    FitStepPayload,
    calc_bcc110_from_bcc211,
    is_martensite_peak,
)


class MultiPeakFitter(BaseFitter):
    engine_name = "MultiPeaks"

    def __init__(
        self,
        bcg_dir: str | Path,
        peaks: List[str],
        init_params: Dict[str, float],
        group_id: Optional[str] = None,
        th_min: Optional[float] = None,
        th_max: Optional[float] = None,
        dimt_onset_num: int = 200,
        newly_forms_peak: Optional[List[int]] = None,
        min_peak_separation: float = 0.03,
        use_bcc211_constraint: bool = True,
        bcc110_center_tol_deg: float = 0.05,
        bcc211_guide_by_num: Optional[Dict[int, Dict[str, float]]] = None,
        default_fit_limits: Optional[Dict[str, Dict[str, float]]] = None,
        update_list: Optional[List[Tuple[str, str, float]]] = None,
        residual_limit: float = 60.0,
        max_attempts: int = 6,
    ) -> None:
        c_first = float(init_params["v1_center"])
        c_last = float(init_params[f"v{len(peaks)}_center"])
        eff_th_min = float(th_min) if th_min is not None else (c_first - 0.8)
        eff_th_max = float(th_max) if th_max is not None else (c_last + 0.8)

        # Item 4: Expand default per-frame parameter variation limits (amplitude: 0.80~1.25, sigma & gamma: 0.70~1.40)
        if default_fit_limits is None:
            default_fit_limits = {}
            for idx in range(len(peaks)):
                default_fit_limits[f"v{idx + 1}"] = {
                    "center_min_offset": -0.02,
                    "center_max_offset": 0.05,
                    "amplitude_min_factor": 0.80,
                    "amplitude_max_factor": 1.25,
                    "amplitude_min_offset": 0.0,
                    "amplitude_max_offset": 10.0,
                    "sigma_min_factor": 0.70,
                    "sigma_max_factor": 1.40,
                    "sigma_min_offset": 0.0,
                    "sigma_max_offset": 1e-4,
                    "gamma_min_factor": 0.70,
                    "gamma_max_factor": 1.40,
                    "gamma_min_offset": 0.0,
                    "gamma_max_offset": 1e-4,
                }

        super().__init__(
            bcg_dir=bcg_dir,
            peaks=peaks,
            init_params=init_params,
            group_id=group_id or "".join(peaks),
            th_min=eff_th_min,
            th_max=eff_th_max,
            default_fit_limits=default_fit_limits,
            update_list=update_list,
            residual_limit=residual_limit,
            max_attempts=max_attempts,
        )

        self.dimt_onset_num = int(dimt_onset_num)
        if newly_forms_peak is not None:
            self.newly_forms_peak = [int(i) for i in newly_forms_peak]
        else:
            # Item 5: Automatically identify α'-martensite peaks (bcc*) as newly forming when dimt_onset_num > 0
            self.newly_forms_peak = [idx for idx, pk in enumerate(self.peaks) if is_martensite_peak(pk)]
        self.min_peak_separation = float(min_peak_separation)
        self.use_bcc211_constraint = bool(use_bcc211_constraint)
        self.bcc110_center_tol_deg = max(0.005, float(bcc110_center_tol_deg))
        self.bcc211_guide_by_num: Dict[int, Dict[str, float]] = dict(bcc211_guide_by_num) if bcc211_guide_by_num else {}

    def _is_peak_suppressed(self, k_zero_based: int, num_val: int) -> bool:
        """Item 5: Return True if peak `k_zero_based` is a martensite/newly forming peak before `dimt_onset_num`."""
        return (
            self.dimt_onset_num > 0
            and num_val < self.dimt_onset_num
            and (
                k_zero_based in self.newly_forms_peak
                or is_martensite_peak(self.peaks[k_zero_based])
            )
        )

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

        mod = None
        pars = None

        for k in range(1, self.n + 1):
            prefix = f"v{k}_"
            vm = VoigtModel(prefix=prefix)
            p = vm.make_params()
            lim = fit_limits[f"v{k}"]
            pk_name = self.peaks[k - 1]
            is_suppressed = self._is_peak_suppressed(k - 1, num_val)

            # Item 6: Check if bcc211 physical constraint applies to bcc110/bcc101 on this frame
            bcc211_conv: Optional[Dict[str, float]] = None
            if (
                not is_suppressed
                and self.use_bcc211_constraint
                and num_val in self.bcc211_guide_by_num
                and pk_name in ("bcc110", "bcc101")
            ):
                guide = self.bcc211_guide_by_num[num_val]
                if float(guide.get("I", 0.0)) > 1e-3 and float(guide.get("2th", 0.0)) > 5.0:
                    bcc211_conv = calc_bcc110_from_bcc211(
                        th2_bcc211_deg=float(guide["2th"]),
                        sigma_211=float(guide["sigma"]),
                        gamma_211=float(guide["gamma"]),
                    )

            c_prev = self.prev_params["center"][k - 1]
            if k == 1:
                min_sep = 0.01
                c_min = c_prev + lim.get("center_min_offset", -0.02)
                c_max = c_prev + lim.get("center_max_offset", 0.05)
            else:
                # Item 2: Neighbor separation <= 30% of initial peak spacing (or 0.03 deg), never fixed +0.5 deg!
                init_spacing = abs(
                    self.base_init_pars[f"v{k}_center"] - self.base_init_pars[f"v{k - 1}_center"]
                )
                min_sep = min(0.03, max(0.005, min(self.min_peak_separation, 0.30 * init_spacing)))
                if bcc211_conv is not None:
                    c_calc = bcc211_conv["center_110_calc"]
                    tol = self.bcc110_center_tol_deg
                    c_min = max(self.prev_params["center"][k - 2] + min_sep, c_calc - tol)
                    c_max = c_calc + tol
                else:
                    c_min = max(
                        self.prev_params["center"][k - 2] + min_sep,
                        c_prev + lim.get("center_min_offset", -0.02),
                    )
                    c_max = c_prev + lim.get("center_max_offset", 0.05)

            # Item 2: Strict guard right before .set(min=..., max=...) to prevent min >= max inversion
            if c_min >= c_max:
                c_max = c_min + max(0.01, min_sep)
            c_val = min(max(cand_pars[f"v{k}_center"], c_min + 1e-6), c_max - 1e-6)

            if is_suppressed:
                p[f"{prefix}center"].set(value=c_val, min=c_min, max=c_max, vary=False)
                p[f"{prefix}amplitude"].set(value=0.0, min=0.0, max=1e-9, vary=False, expr=None)
            else:
                amp_guess = scaled_amplitude_guess[k - 1]
                a_min = max(0.0, amp_guess * lim.get("amplitude_min_factor", 0.80) + lim.get("amplitude_min_offset", 0.0))
                a_max = max(
                    a_min + 1.0,
                    amp_guess * lim.get("amplitude_max_factor", 1.25) + lim.get("amplitude_max_offset", 10.0),
                )
                p[f"{prefix}center"].set(value=c_val, min=c_min, max=c_max, vary=True)
                p[f"{prefix}amplitude"].set(value=min(max(amp_guess, a_min), a_max), min=a_min, max=a_max, vary=True, expr=None)

            if bcc211_conv is not None:
                s_ref = max(1e-6, bcc211_conv["sigma_110_calc"])
                s_min = max(1e-6, s_ref * lim.get("sigma_min_factor", 0.70))
                s_max = max(s_min + 1e-5, s_ref * lim.get("sigma_max_factor", 1.40))
                g_ref = max(1e-10, bcc211_conv["gamma_110_calc"])
                g_min = max(1e-10, g_ref * lim.get("gamma_min_factor", 0.70))
                g_max = max(g_min + 1e-5, g_ref * lim.get("gamma_max_factor", 1.40))
            else:
                s_prev = self.prev_params["sigma"][k - 1]
                s_min = max(1e-6, s_prev * lim.get("sigma_min_factor", 0.70) + lim.get("sigma_min_offset", 0.0))
                s_max = max(s_min + 1e-5, s_prev * lim.get("sigma_max_factor", 1.40) + lim.get("sigma_max_offset", 1e-4))
                g_prev = self.prev_params["gamma"][k - 1]
                g_min = max(1e-10, g_prev * lim.get("gamma_min_factor", 0.70) + lim.get("gamma_min_offset", 0.0))
                g_max = max(g_min + 1e-5, g_prev * lim.get("gamma_max_factor", 1.40) + lim.get("gamma_max_offset", 1e-4))

            p[f"{prefix}sigma"].set(
                value=min(max(cand_pars[f"v{k}_sigma"], s_min), s_max),
                min=s_min,
                max=s_max,
                vary=not is_suppressed,
            )

            # Item 1: Explicitly set vary=not is_suppressed and expr=None on gamma
            p[f"{prefix}gamma"].set(
                value=min(max(cand_pars[f"v{k}_gamma"], g_min), g_max),
                min=g_min,
                max=g_max,
                vary=not is_suppressed,
                expr=None,
            )

            if mod is None:
                mod = vm
                pars = p
            else:
                mod += vm
                pars.update(p)

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
                if self._is_peak_suppressed(p_idx - 1, num):
                    continue
                trial_pars[f"v{p_idx}_center"] += random.uniform(-0.001, 0.001)
                trial_pars[f"v{p_idx}_amplitude"] *= random.uniform(0.995, 1.005)
                trial_pars[f"v{p_idx}_sigma"] *= random.uniform(0.999, 1.001)
                trial_pars[f"v{p_idx}_gamma"] *= random.uniform(0.999, 1.001)

            out_try, comps_try, res_mean_try, rel_res_try = self._perform_fitting_once(th, In, trial_pars, num)
            if res_mean_try < prev_residual:
                prev_residual = res_mean_try
                best_out = out_try
                best_comps = comps_try
                best_rel_res = rel_res_try
                for r in range(1, self.n + 1):
                    for name in PARAM_NAMES:
                        best_pars[f"v{r}_{name}"] = float(out_try.best_values.get(f"v{r}_{name}"))

        self.prev_integral = self.current_integral
        for r in range(1, self.n + 1):
            if self._is_peak_suppressed(r - 1, num):
                best_pars[f"v{r}_amplitude"] = 0.0
            else:
                for name in PARAM_NAMES:
                    self.prev_params[name][r - 1] = float(best_pars[f"v{r}_{name}"])
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
        for i in reversed(range(0, self.target_index + 1)):
            completed += 1
            payload = self.fit_one_file(i, completed_count=completed)
            if step_callback:
                step_callback(payload)

        # Step 2: Reset and run forward from target_index + 1 to end
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
