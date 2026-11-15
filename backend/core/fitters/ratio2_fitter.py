# -*- coding: utf-8 -*-
"""2-Peak fixed intensity ratio R optimization + continuous fitter
(`fitting_2peaks_csv_fixed_ratio_diff_inits_ver10.py` equivalent).

Fixes:
- Bug #1: Proper best-residual tracking in retry loop.
- Bug #4: Unified output column order `[num, 2th_p1, I_p1, wG_p1, wL_p1, FWHM_p1, 2th_p2, I_p2, wG_p2, wL_p2, FWHM_p2]`.
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


class Ratio2Fitter(BaseFitter):
    engine_name = "2PeaksRatio"

    def __init__(
        self,
        bcg_dir: str | Path,
        peaks: List[str],
        init_params: Dict[str, float],
        group_id: Optional[str] = None,
        fitting_range_min: float = -1.0,
        fitting_range_max: float = 0.7,
        th_min: Optional[float] = None,
        th_max: Optional[float] = None,
        dimt_onset_num: int = 200,
        initial_ep_region: int = 1,
        end_ep_region: int = 120,
        num_init_val_set: int = 5,
        vib_ratio_fine: float = 0.05,
        use_bcc211_constraint: bool = True,
        bcc110_center_tol_deg: float = 0.05,
        bcc211_guide_by_num: Optional[Dict[int, Dict[str, float]]] = None,
        default_fit_limits: Optional[Dict[str, Dict[str, float]]] = None,
        update_list: Optional[List[Tuple[str, str, float]]] = None,
        residual_limit: float = 200.0,
        max_attempts: int = 5,
    ) -> None:
        if len(peaks) < 2:
            raise ValueError("Ratio2Fitter requires at least 2 peaks (e.g., ['fcc111', 'bcc110']).")
        c2 = float(init_params.get("v2_center", init_params["v1_center"] + 0.12))
        eff_th_min = float(th_min) if th_min is not None else (c2 + fitting_range_min)
        eff_th_max = float(th_max) if th_max is not None else (c2 + fitting_range_max)

        # Item 4: Expand default per-frame parameter variation limits (amplitude: 0.80~1.25, sigma & gamma: 0.70~1.40)
        if default_fit_limits is None:
            default_fit_limits = {
                "v1": {
                    "center_min_offset": -0.015,
                    "center_max_offset": 0.015,
                    "amplitude_min_factor": 0.80,
                    "amplitude_max_factor": 1.25,
                    "amplitude_min_offset": 0.0,
                    "amplitude_max_offset": 20.0,
                    "sigma_min_factor": 0.70,
                    "sigma_max_factor": 1.40,
                    "sigma_min_offset": 0.0,
                    "sigma_max_offset": 1e-4,
                    "gamma_min_factor": 0.70,
                    "gamma_max_factor": 1.40,
                    "gamma_min_offset": 0.0,
                    "gamma_max_offset": 1e-4,
                },
                "v2": {
                    "center_min_offset": -0.015,
                    "center_max_offset": 0.020,
                    "amplitude_min_factor": 0.80,
                    "amplitude_max_factor": 1.25,
                    "amplitude_min_offset": 0.0,
                    "amplitude_max_offset": 30.0,
                    "sigma_min_factor": 0.70,
                    "sigma_max_factor": 1.40,
                    "sigma_min_offset": 0.0,
                    "sigma_max_offset": 1e-4,
                    "gamma_min_factor": 0.70,
                    "gamma_max_factor": 1.40,
                    "gamma_min_offset": 0.0,
                    "gamma_max_offset": 1e-4,
                },
            }

        super().__init__(
            bcg_dir=bcg_dir,
            peaks=peaks[:2],
            init_params=init_params,
            group_id=group_id or "".join(peaks[:2]),
            th_min=eff_th_min,
            th_max=eff_th_max,
            default_fit_limits=default_fit_limits,
            update_list=update_list,
            residual_limit=residual_limit,
            max_attempts=max_attempts,
        )

        self.dimt_onset_num = int(dimt_onset_num)
        self.initial_ep_region = int(initial_ep_region)
        self.end_ep_region = int(end_ep_region)
        self.num_init_val_set = max(1, int(num_init_val_set))
        self.vib_ratio_fine = float(vib_ratio_fine)
        self.use_bcc211_constraint = bool(use_bcc211_constraint)
        self.bcc110_center_tol_deg = max(0.005, float(bcc110_center_tol_deg))
        self.bcc211_guide_by_num: Dict[int, Dict[str, float]] = dict(bcc211_guide_by_num) if bcc211_guide_by_num else {}

        v1_amp = max(1e-3, self.base_init_pars["v1_amplitude"])
        v2_amp = max(1e-3, self.base_init_pars["v2_amplitude"])
        self.initial_R = max(0.01, v2_amp / v1_amp)
        self.best_R: float = self.initial_R
        self.history_R: List[float] = []
        self.history_residual: List[float] = []

    def _fit_single_step(
        self,
        th: np.ndarray,
        In: np.ndarray,
        cand_pars: Dict[str, float],
        fixed_R: Optional[float],
        num_val: Optional[int] = None,
    ) -> Tuple[Any, Dict[str, np.ndarray], float, float]:
        fit_limits = self.get_effective_limits()
        scaled_amp = [max(0.0, a * self.intensity_scale_factor) for a in self.prev_params["amplitude"]]

        v1_mod = VoigtModel(prefix="v1_")
        v2_mod = VoigtModel(prefix="v2_")
        mod = v1_mod + v2_mod
        pars = mod.make_params()

        # Item 2: Neighbor separation <= 30% of initial peak spacing (or 0.03 deg)
        init_spacing = abs(self.base_init_pars["v2_center"] - self.base_init_pars["v1_center"])
        min_sep = min(0.03, max(0.005, 0.30 * init_spacing))

        # Item 5: Check if Peak 2 (martensite bcc110/bcc101) should be fixed to 0.0 before DIMT onset
        is_v2_suppressed = (
            num_val is not None
            and self.dimt_onset_num > 0
            and num_val < self.dimt_onset_num
            and is_martensite_peak(self.peaks[1])
        )

        # Item 6: Check if bcc211 physical constraint applies to Peak 2 on this frame
        bcc211_conv: Optional[Dict[str, float]] = None
        if (
            not is_v2_suppressed
            and self.use_bcc211_constraint
            and num_val is not None
            and num_val in self.bcc211_guide_by_num
            and self.peaks[1] in ("bcc110", "bcc101")
        ):
            guide = self.bcc211_guide_by_num[num_val]
            if float(guide.get("I", 0.0)) > 1e-3 and float(guide.get("2th", 0.0)) > 5.0:
                bcc211_conv = calc_bcc110_from_bcc211(
                    th2_bcc211_deg=float(guide["2th"]),
                    sigma_211=float(guide["sigma"]),
                    gamma_211=float(guide["gamma"]),
                )

        for k in (1, 2):
            lim = fit_limits[f"v{k}"]
            c_prev = self.prev_params["center"][k - 1]
            if k == 1:
                c_min = c_prev + lim.get("center_min_offset", -0.015)
                c_max = c_prev + lim.get("center_max_offset", 0.015)
            else:
                if bcc211_conv is not None:
                    c_calc = bcc211_conv["center_110_calc"]
                    tol = self.bcc110_center_tol_deg
                    c_min = max(self.prev_params["center"][0] + min_sep, c_calc - tol)
                    c_max = c_calc + tol
                else:
                    c_min = max(self.prev_params["center"][0] + min_sep, c_prev + lim.get("center_min_offset", -0.015))
                    c_max = c_prev + lim.get("center_max_offset", 0.020)

            # Item 2: Strict guard right before .set(min=..., max=...) to prevent min >= max inversion
            if c_min >= c_max:
                c_max = c_min + max(0.01, min_sep)
            c_val = min(max(cand_pars[f"v{k}_center"], c_min + 1e-6), c_max - 1e-6)

            if k == 2 and bcc211_conv is not None:
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

            s_val = min(max(cand_pars[f"v{k}_sigma"], s_min), s_max)
            g_val = min(max(cand_pars[f"v{k}_gamma"], g_min), g_max)

            vary_flag = not (k == 2 and is_v2_suppressed)
            pars[f"v{k}_center"].set(value=c_val, min=c_min, max=c_max, vary=vary_flag)
            pars[f"v{k}_sigma"].set(value=s_val, min=s_min, max=s_max, vary=vary_flag)
            # Item 1: Explicitly set vary=vary_flag and expr=None on gamma
            pars[f"v{k}_gamma"].set(
                value=g_val,
                min=g_min,
                max=g_max,
                vary=vary_flag,
                expr=None,
            )

        # Amplitude constraints
        lim1 = fit_limits["v1"]
        a1_guess = scaled_amp[0]
        a1_min = max(0.0, a1_guess * lim1.get("amplitude_min_factor", 0.80))
        a1_max = max(a1_min + 1.0, a1_guess * lim1.get("amplitude_max_factor", 1.25) + lim1.get("amplitude_max_offset", 20.0))
        pars["v1_amplitude"].set(value=min(max(a1_guess, a1_min), a1_max), min=a1_min, max=a1_max, vary=True)

        if is_v2_suppressed:
            # Item 5: Strictly fix martensite amplitude to 0.0 before DIMT onset
            pars["v2_amplitude"].set(value=0.0, min=0.0, max=1e-9, vary=False, expr=None)
        elif fixed_R is not None and fixed_R > 0:
            pars["v2_amplitude"].set(expr=f"v1_amplitude * {fixed_R:.8f}")
        else:
            lim2 = fit_limits["v2"]
            a2_guess = scaled_amp[1]
            a2_min = max(0.0, a2_guess * lim2.get("amplitude_min_factor", 0.80))
            a2_max = max(a2_min + 1.0, a2_guess * lim2.get("amplitude_max_factor", 1.25) + lim2.get("amplitude_max_offset", 30.0))
            pars["v2_amplitude"].set(value=min(max(a2_guess, a2_min), a2_max), min=a2_min, max=a2_max, vary=True, expr=None)

        out = mod.fit(In, pars, x=th, method="leastsq", max_nfev=300)
        comps = out.eval_components(x=th)
        residual_mean = float(np.sqrt(np.mean(out.residual ** 2)))
        mean_abs_in = max(1e-6, float(np.mean(np.abs(In))))
        relative_residual = residual_mean / mean_abs_in
        return out, comps, residual_mean, relative_residual

    def _evaluate_R_candidate(self, R_val: float, pre_dimt_indices: List[int]) -> float:
        """Evaluate total RMSE across pre-DIMT files for a candidate intensity ratio `R_val`."""
        self.reset_to_initial()
        total_res = 0.0
        for idx in pre_dimt_indices:
            num, _, th, In = self.load_window_data(idx)
            out, _, res_mean, _ = self._fit_single_step(th, In, self.Init_pars, fixed_R=R_val, num_val=None)
            total_res += res_mean
            self.prev_integral = self.current_integral

            params_to_update = (
                ["center", "amplitude", "sigma", "gamma"]
                if (self.initial_ep_region < num < self.end_ep_region)
                else ["center", "amplitude"]
            )
            for name in PARAM_NAMES:
                if name in params_to_update:
                    self.prev_params[name] = [float(out.best_values.get(f"v{r}_{name}")) for r in (1, 2)]
            for r in (1, 2):
                for name in PARAM_NAMES:
                    self.Init_pars[f"v{r}_{name}"] = self.prev_params[name][r - 1]
        return total_res

    def fit_one_file(
        self,
        file_index: int,
        completed_count: int,
        fixed_R: Optional[float] = None,
    ) -> FitStepPayload:
        # Item 7-2: Fixed random seed for 100% deterministic reproducibility
        random.seed(42)
        np.random.seed(42)

        num, fname, th, In = self.load_window_data(file_index)

        is_v2_suppressed = (
            self.dimt_onset_num > 0
            and num < self.dimt_onset_num
            and is_martensite_peak(self.peaks[1])
        )
        use_R = fixed_R if (not is_v2_suppressed and fixed_R is not None and num <= self.dimt_onset_num) else None
        out, comps, residual_mean, relative_residual = self._fit_single_step(
            th, In, self.Init_pars, fixed_R=use_R, num_val=num
        )

        prev_residual = residual_mean
        best_out = out
        best_comps = comps
        best_rel_res = relative_residual
        best_pars = {
            f"v{r}_{name}": float(out.best_values.get(f"v{r}_{name}", self.Init_pars[f"v{r}_{name}"]))
            for r in (1, 2)
            for name in PARAM_NAMES
        }

        attempt = 0
        while prev_residual >= self.residual_limit and attempt < self.max_attempts:
            attempt += 1
            trial_pars = copy.deepcopy(best_pars)
            for p_idx in (1, 2):
                trial_pars[f"v{p_idx}_center"] += random.uniform(-0.0005, 0.0005)
                trial_pars[f"v{p_idx}_amplitude"] *= random.uniform(0.99, 1.01)
                trial_pars[f"v{p_idx}_sigma"] *= random.uniform(0.995, 1.005)
                trial_pars[f"v{p_idx}_gamma"] *= random.uniform(0.995, 1.005)

            out_try, comps_try, res_mean_try, rel_res_try = self._fit_single_step(
                th, In, trial_pars, fixed_R=use_R, num_val=num
            )
            if res_mean_try < prev_residual:
                prev_residual = res_mean_try
                best_out = out_try
                best_comps = comps_try
                best_rel_res = rel_res_try
                for r in (1, 2):
                    for name in PARAM_NAMES:
                        best_pars[f"v{r}_{name}"] = float(out_try.best_values.get(f"v{r}_{name}"))

        self.prev_integral = self.current_integral
        if is_v2_suppressed:
            best_pars["v2_amplitude"] = 0.0
            for name in PARAM_NAMES:
                self.prev_params[name][0] = float(best_pars[f"v1_{name}"])
                self.Init_pars[f"v1_{name}"] = self.prev_params[name][0]
        else:
            params_to_update = (
                ["center", "amplitude", "sigma", "gamma"]
                if (num >= self.dimt_onset_num or (self.initial_ep_region < num < self.end_ep_region))
                else ["center", "amplitude"]
            )
            for name in PARAM_NAMES:
                if name in params_to_update:
                    self.prev_params[name] = [float(best_pars[f"v{r}_{name}"]) for r in (1, 2)]
            for r in (1, 2):
                for name in PARAM_NAMES:
                    self.Init_pars[f"v{r}_{name}"] = self.prev_params[name][r - 1]

        row_data = self.build_row_dict(num, best_pars, residual=best_rel_res)
        comp_lists = {
            self.peaks[r - 1]: best_comps.get(f"v{r}_", np.zeros_like(th)).tolist()
            for r in (1, 2)
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
        """Execute 2-stage coarse-to-fine R optimization followed by full bidirectional fitting."""
        self.history_R.clear()
        self.history_residual.clear()
        self.results_by_num.clear()

        # Select pre-DIMT indices for fast & accurate R optimization
        pre_dimt_all = [i for i, (num, _) in enumerate(self.files) if num <= self.dimt_onset_num]
        if not pre_dimt_all:
            pre_dimt_all = list(range(min(8, len(self.files))))
        # Sample up to 8 pre-DIMT files during coarse/fine R search so batch runs stay fast and responsive
        stride = max(1, len(pre_dimt_all) // 8)
        eval_indices = pre_dimt_all[::stride]

        # Stage 1: Coarse R search across `num_init_val_set` ratios around initial_R
        coarse_factors = np.linspace(0.80, 1.20, min(3, self.num_init_val_set))
        best_total_res = float("inf")
        best_R = self.initial_R

        for factor in coarse_factors:
            cand_R = max(0.005, float(self.initial_R * factor))
            tot_res = self._evaluate_R_candidate(cand_R, eval_indices)
            self.history_R.append(round(cand_R, 5))
            self.history_residual.append(round(tot_res, 4))
            if tot_res < best_total_res:
                best_total_res = tot_res
                best_R = cand_R

        # Stage 2: Fine R search around rough_best_R
        rough_best_R = best_R
        fine_step = max(0.002, rough_best_R * self.vib_ratio_fine)
        for vib in (-1, 1):
            cand_R = max(0.005, rough_best_R + vib * fine_step)
            tot_res = self._evaluate_R_candidate(cand_R, eval_indices)
            self.history_R.append(round(cand_R, 5))
            self.history_residual.append(round(tot_res, 4))
            if tot_res < best_total_res:
                best_total_res = tot_res
                best_R = cand_R

        self.best_R = best_R

        # Sort R history by R for clean plotting
        paired_hist = sorted(zip(self.history_R, self.history_residual), key=lambda kv: kv[0])
        self.history_R = [p[0] for p in paired_hist]
        self.history_residual = [p[1] for p in paired_hist]

        # Stage 3: Full dataset bidirectional pass using optimal best_R
        self.reset_to_initial()
        completed = 0
        for i in reversed(range(0, self.target_index + 1)):
            completed += 1
            payload = self.fit_one_file(i, completed_count=completed, fixed_R=self.best_R)
            if step_callback:
                step_callback(payload)

        self.reset_to_initial()
        for i in range(self.target_index + 1, len(self.files)):
            completed += 1
            payload = self.fit_one_file(i, completed_count=completed, fixed_R=self.best_R)
            if step_callback:
                step_callback(payload)

        df = self.build_dataframe()
        return {
            "group_id": self.group_id,
            "engine": self.engine_name,
            "peaks": self.peaks,
            "best_R": round(self.best_R, 5),
            "history_R": self.history_R,
            "history_residual": self.history_residual,
            "dataframe": df,
            "rows": df.to_dict(orient="records"),
            "results_by_num": self.results_by_num,
        }
