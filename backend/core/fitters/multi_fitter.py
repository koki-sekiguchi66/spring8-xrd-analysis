# -*- coding: utf-8 -*-
"""General multi-peak simultaneous continuous Voigt fitter.

Faithful port of Harada's `fitting_multi peaks_csv_ver4.0.0.py`:
- A fixed window `[th_min, th_max]` of the background-removed data is fitted with n Voigt functions
  and no local background term (the edge-based linear subtraction is commented out in ver4.0.0).
- Peaks are ordered by 2theta; peak k (k >= 2) must stay at least `min_peak_separation` above
  peak k-1 (ver4.0.0 uses +0.5 deg).
- Newly forming peaks (`newly_forms_peak`, e.g. alpha' peaks): before `DIMT_onset_num`, their
  previous-frame amplitude is reset to 0 at the start of every frame, so their amplitude is bounded
  to `[0, amplitude_max_offset]` (10 by default). They are not hard-fixed to zero.
- Residual = mean(|residual|) (absolute); retries with small perturbations while it exceeds
  `residual_limit` (60 in ver4.0.0).
- Backward pass `target -> first`, reset, forward pass `target + 1 -> last`.

Bug fixes relative to ver4.0.0 (logic only):
- #3 `prev_params['amplitude'][newly_forms_peak] = 0` raised TypeError for a list index -> loop.
- The fixed +0.5 deg neighbour separation inverts the center bounds (min > max) for peaks closer than
  0.5 deg; the separation is now `min(0.5, 0.5 * initial spacing)`, identical to ver4.0.0 for
  well-separated peaks.
- The retry loop now keeps the best attempt (ver4.0.0 refitted from the best start values instead).
- Fixed random seed per frame for reproducibility.

`use_bcc211_constraint` (bcc110 position/width derived from a fitted bcc211 via Bragg's law and the
tan(theta) ratio) is NOT part of Harada's method and is disabled by default.
"""

from __future__ import annotations

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

_PRE_FIT_PERTURB = {"center": (-0.0001, 0.0001), "sigma": (0.999999, 1.000001), "gamma": (0.999999, 1.000001)}
_RETRY_PERTURB = {"center": (-0.001, 0.001), "amplitude": (0.995, 1.005), "sigma": (0.99999, 1.00001), "gamma": (0.99999, 1.00001)}

HARADA_MULTI_SEPARATION_DEG = 0.5


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
        dimt_onset_num: int = 0,
        newly_forms_peak: Optional[List[int]] = None,
        min_peak_separation: float = HARADA_MULTI_SEPARATION_DEG,
        use_bcc211_constraint: bool = False,
        bcc110_center_tol_deg: float = 0.05,
        bcc211_guide_by_num: Optional[Dict[int, Dict[str, float]]] = None,
        default_fit_limits: Optional[Dict[str, Dict[str, float]]] = None,
        update_list: Optional[List[Tuple[str, str, float]]] = None,
        residual_limit: float = 60.0,
        max_attempts: int = 10,
        fit_y0: bool = False,
        y0_init: float = 0.0,
    ) -> None:
        c_first = float(init_params["v1_center"])
        c_last = float(init_params[f"v{len(peaks)}_center"])
        eff_th_min = float(th_min) if th_min is not None else (c_first - 0.8)
        eff_th_max = float(th_max) if th_max is not None else (c_last + 0.8)

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
            fit_y0=fit_y0,
            y0_init=y0_init,
        )

        self.dimt_onset_num = int(dimt_onset_num)
        if newly_forms_peak is not None:
            self.newly_forms_peak = [int(i) for i in newly_forms_peak if 0 <= int(i) < self.n]
        else:
            self.newly_forms_peak = [idx for idx, pk in enumerate(self.peaks) if is_martensite_peak(pk)]
        self.min_peak_separation = float(min_peak_separation)
        self.use_bcc211_constraint = bool(use_bcc211_constraint)
        self.bcc110_center_tol_deg = max(0.005, float(bcc110_center_tol_deg))
        self.bcc211_guide_by_num: Dict[int, Dict[str, float]] = dict(bcc211_guide_by_num) if bcc211_guide_by_num else {}

    def _default_limits(self) -> Dict[str, Dict[str, float]]:
        """`default_fit_limits` of `fitting_multi peaks_csv_ver4.0.0.py`."""
        return {
            f"v{idx + 1}": {
                "center_min_offset": -0.02,
                "center_max_offset": 0.05,
                "amplitude_min_factor": 0.90,
                "amplitude_max_factor": 1.10,
                "amplitude_min_offset": 0.0,
                "amplitude_max_offset": 10.0,
                "sigma_min_factor": 0.90,
                "sigma_max_factor": 1.10,
                "sigma_min_offset": -1e-4,
                "sigma_max_offset": 1e-4,
                "gamma_min_factor": 0.90,
                "gamma_max_factor": 1.10,
                "gamma_min_offset": -1e-4,
                "gamma_max_offset": 1e-4,
            }
            for idx in range(self.n)
        }

    def _separation(self, k: int) -> float:
        """Minimum separation between peak k-1 and peak k (1-based k >= 2)."""
        init_spacing = abs(self.base_init_pars[f"v{k}_center"] - self.base_init_pars[f"v{k - 1}_center"])
        return min(self.min_peak_separation, 0.5 * init_spacing)

    def _before_onset(self, num_val: int) -> bool:
        return self.dimt_onset_num > 0 and num_val < self.dimt_onset_num

    def _perform_fitting_once(
        self,
        th: np.ndarray,
        In: np.ndarray,
        cand_pars: Dict[str, float],
        num_val: int,
    ) -> Tuple[Any, Dict[str, np.ndarray], float, float]:
        lim_all = self.get_effective_limits()
        scaled = [amp * self.intensity_scale_factor for amp in self.prev_params["amplitude"]]

        mod = None
        pars = None
        for k in range(1, self.n + 1):
            prefix = f"v{k}_"
            vm = VoigtModel(prefix=prefix)
            p = vm.make_params()
            lim = lim_all[f"v{k}"]
            pk_name = self.peaks[k - 1]

            # Optional (non-Harada) bcc211 -> bcc110 tie
            tie: Optional[Dict[str, float]] = None
            if (
                self.use_bcc211_constraint
                and not self._before_onset(num_val)
                and num_val in self.bcc211_guide_by_num
                and pk_name in ("bcc110", "bcc101")
            ):
                guide = self.bcc211_guide_by_num[num_val]
                if float(guide.get("I", 0.0)) > 1e-3 and float(guide.get("2th", 0.0)) > 5.0:
                    tie = calc_bcc110_from_bcc211(float(guide["2th"]), float(guide["sigma"]), float(guide["gamma"]))

            c_prev = self.prev_params["center"][k - 1]
            if tie is not None:
                c_lo, c_hi = tie["center_110_calc"] - self.bcc110_center_tol_deg, tie["center_110_calc"] + self.bcc110_center_tol_deg
            else:
                c_lo, c_hi = c_prev + lim["center_min_offset"], c_prev + lim["center_max_offset"]
            if k >= 2:
                c_lo = max(self.prev_params["center"][k - 2] + self._separation(k), c_lo)
            c_min, c_max = self.bounded(c_lo, c_hi, 0.01)

            a_min = max(0.0, scaled[k - 1] * lim["amplitude_min_factor"] + lim["amplitude_min_offset"])
            a_min, a_max = self.bounded(a_min, scaled[k - 1] * lim["amplitude_max_factor"] + lim["amplitude_max_offset"], 1.0)

            if tie is not None:
                s_ref, g_ref = max(1e-6, tie["sigma_110_calc"]), max(0.0, tie["gamma_110_calc"])
                s_min, s_max = self.bounded(s_ref * lim["sigma_min_factor"], s_ref * lim["sigma_max_factor"], 1e-5)
                g_min, g_max = self.bounded(g_ref * lim["gamma_min_factor"], g_ref * lim["gamma_max_factor"], 1e-5)
            else:
                s_prev = self.prev_params["sigma"][k - 1]
                s_min, s_max = self.bounded(
                    max(1e-6, s_prev * lim["sigma_min_factor"] + lim["sigma_min_offset"]),
                    s_prev * lim["sigma_max_factor"] + lim["sigma_max_offset"],
                    1e-5,
                )
                g_prev = self.prev_params["gamma"][k - 1]
                g_min, g_max = self.bounded(
                    max(0.0, g_prev * lim["gamma_min_factor"] + lim["gamma_min_offset"]),
                    g_prev * lim["gamma_max_factor"] + lim["gamma_max_offset"],
                    1e-5,
                )

            p[f"{prefix}center"].set(value=float(np.clip(cand_pars[f"v{k}_center"], c_min, c_max)), min=c_min, max=c_max, vary=True)
            p[f"{prefix}amplitude"].set(value=float(np.clip(scaled[k - 1], a_min, a_max)), min=a_min, max=a_max, vary=True)
            p[f"{prefix}sigma"].set(value=float(np.clip(cand_pars[f"v{k}_sigma"], s_min, s_max)), min=s_min, max=s_max, vary=True)
            p[f"{prefix}gamma"].set(value=float(np.clip(cand_pars[f"v{k}_gamma"], g_min, g_max)), min=g_min, max=g_max, vary=True, expr=None)

            if mod is None:
                mod, pars = vm, p
            else:
                mod += vm
                pars.update(p)

        mod, pars = self.attach_y0(mod, pars, In)
        out = mod.fit(In, pars, x=th, method="leastsq")
        comps = out.eval_components(x=th)
        residual_mean = float(np.mean(np.abs(out.residual)))
        relative_residual = residual_mean / max(1e-12, float(np.mean(np.abs(In))))
        return out, comps, residual_mean, relative_residual

    def fit_one_file(self, file_index: int, completed_count: int) -> FitStepPayload:
        random.seed(42)
        np.random.seed(42)

        num = self.files[file_index][0]
        # ver4.0.0: before the DIMT onset the newly forming peaks restart from amplitude 0 every frame
        if self._before_onset(num):
            for pk_idx in self.newly_forms_peak:  # Bug #3 fix (list index -> loop)
                self.prev_params["amplitude"][pk_idx] = 0.0

        num, fname, th, In = self.load_window_data(file_index)

        start = self.perturb(self.Init_pars, self.n, _PRE_FIT_PERTURB)
        out, comps, residual_mean, relative_residual = self._perform_fitting_once(th, In, start, num)
        best = (residual_mean, out, comps, relative_residual)

        attempt = 0
        while best[0] >= self.residual_limit and attempt < self.max_attempts:
            attempt += 1
            base = {f"v{r}_{nm}": float(best[1].best_values[f"v{r}_{nm}"]) for r in range(1, self.n + 1) for nm in PARAM_NAMES}
            trial = self.perturb(base, self.n, _RETRY_PERTURB)
            o2, c2, rm2, rr2 = self._perform_fitting_once(th, In, trial, num)
            if rm2 < best[0]:
                best = (rm2, o2, c2, rr2)

        residual_mean, out, comps, relative_residual = best
        best_pars = {f"v{r}_{nm}": float(out.best_values[f"v{r}_{nm}"]) for r in range(1, self.n + 1) for nm in PARAM_NAMES}

        self.prev_integral = self.current_integral
        y0_val = self.carry_y0(out)
        for r in range(1, self.n + 1):
            for nm in PARAM_NAMES:
                self.prev_params[nm][r - 1] = best_pars[f"v{r}_{nm}"]
                self.Init_pars[f"v{r}_{nm}"] = best_pars[f"v{r}_{nm}"]

        row_data = self.build_row_dict(num, best_pars, residual=residual_mean, y0=y0_val)
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
            is_outlier=bool(residual_mean >= self.residual_limit),
            row_data=row_data,
            x=th.tolist(),
            y_obs=In.tolist(),
            y_fit=out.best_fit.tolist(),
            components=comp_lists,
        )
        self.results_by_num[num] = payload
        return payload

    def run_all(self, step_callback: Optional[Callable[[FitStepPayload], None]] = None) -> Dict[str, Any]:
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
