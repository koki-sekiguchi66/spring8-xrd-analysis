# -*- coding: utf-8 -*-
"""2-peak fixed-intensity-ratio fitter for the pre-DIMT region.

Faithful port of Harada's `fitting_2peaks_csv_fixed_ratio_diff_inits_ver10.py`.

Physical premise (ver10): in cold-rolled specimens the martensite that already exists before the
tensile test does not change until the DIMT onset, so the ratio `R = I_bcc110 / I_fcc111` is constant
for `num <= DIMT_onset_num`. Both peaks are fitted with `v2_amplitude = R * v1_amplitude`, and R is the
value that minimises the total residual over that region:
1. Coarse search: one R per initial-value set (`num_init_val_set` rows of `_initial.xlsx`; here the
   same multipliers `[1.0, 0.90, 0.95, 1.05, 1.10]` that `save_initial_excel` writes for the 2nd peak).
2. Fine search: `R = rough_best_R + vib * vib_ratio_fine`, `vib = -5 ... +5` (absolute step, 0.1 in ver10).
For every candidate R, all files with `num <= DIMT_onset_num` are fitted forward from the first file,
starting from the initial values. Widths are updated only inside the elasto-plastic region
`initial_ep_region < num < end_ep_region`; elsewhere only center and amplitude are carried over.
The output is the run with the best R and covers only `num <= DIMT_onset_num`; the post-onset region
is fitted by the 3-peak Lueders engine (`luders3_fitter.py`), as in the original workflow.

Peak 2 is therefore pre-existing martensite and is NOT set to zero before the onset.
For specimens without pre-existing martensite (annealed / aged), use `MultiPeaks` instead.

Bug fixes relative to ver10 (logic only): best attempt kept in the retry loop, column order
unified, strict file-number parsing, no `plt.show()`, `scipy.integrate.trapezoid`, fixed seeds.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from lmfit.models import VoigtModel

from .base_fitter import PARAM_NAMES, BaseFitter, FitStepPayload

_PRE_FIT_PERTURB = {"center": (-0.0001, 0.0001), "amplitude": (0.999, 1.001), "sigma": (0.999, 1.001), "gamma": (0.999, 1.001)}
_RETRY_PERTURB = {"center": (-0.00001, 0.0), "amplitude": (0.995, 1.005), "sigma": (0.999, 1.001), "gamma": (0.999, 1.001)}
# Multipliers of the 2nd-peak amplitude written by `save_initial_excel` (one row per initial-value set)
INITIAL_SET_MULTIPLIERS = [1.0, 0.90, 0.95, 1.05, 1.10]
# ver10 neighbour separation
RATIO2_SEPARATION_DEG = 0.005


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
        vib_ratio_fine: float = 0.1,
        r_candidates: Optional[List[float]] = None,
        default_fit_limits: Optional[Dict[str, Dict[str, float]]] = None,
        update_list: Optional[List[Tuple[str, str, float]]] = None,
        residual_limit: float = 200.0,
        max_attempts: int = 10,
        fit_y0: bool = False,
        y0_init: float = 0.0,
        **_ignored: Any,
    ) -> None:
        if len(peaks) < 2:
            raise ValueError("Ratio2Fitter requires 2 peaks (e.g., ['fcc111', 'bcc110']).")
        # ver10: window relative to the initial center of the 2nd peak
        c2 = float(init_params.get("v2_center", init_params["v1_center"] + 0.12))
        eff_th_min = float(th_min) if th_min is not None else (c2 + fitting_range_min)
        eff_th_max = float(th_max) if th_max is not None else (c2 + fitting_range_max)

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
            fit_y0=fit_y0,
            y0_init=y0_init,
        )

        self.dimt_onset_num = int(dimt_onset_num)
        self.initial_ep_region = int(initial_ep_region)
        self.end_ep_region = int(end_ep_region)
        self.num_init_val_set = max(1, min(len(INITIAL_SET_MULTIPLIERS), int(num_init_val_set)))
        self.vib_ratio_fine = float(vib_ratio_fine)
        # R of each initial-value set (rows of `_initial.xlsx`); None -> INITIAL_SET_MULTIPLIERS
        self.r_candidates = [float(r) for r in (r_candidates or []) if r and float(r) > 0][: self.num_init_val_set] or None

        v1_amp = max(1e-12, self.base_init_pars["v1_amplitude"])
        self.initial_R = max(1e-6, self.base_init_pars["v2_amplitude"] / v1_amp)
        self.best_R: float = self.initial_R
        self.history_R: List[float] = []
        self.history_residual: List[float] = []
        self.params_to_update: List[str] = list(PARAM_NAMES)

    def _default_limits(self) -> Dict[str, Dict[str, float]]:
        """ver10 `default_fit_limits` with the `update_list` that ver10 always applies inside the R loop."""
        base = {
            "v1": {
                "center_min_offset": -0.005, "center_max_offset": 0.005,
                "amplitude_min_factor": 0.95, "amplitude_max_factor": 1.05, "amplitude_max_offset": 10.0,
                "sigma_min_factor": 0.95, "sigma_max_factor": 1.05, "sigma_max_offset": 1e-10,
                "gamma_min_factor": 0.95, "gamma_max_factor": 1.05, "gamma_max_offset": 1e-10,
            },
            "v2": {
                "center_min_offset": -0.005, "center_max_offset": 0.005,
                "amplitude_min_factor": 0.95, "amplitude_max_factor": 1.05, "amplitude_max_offset": 10.0,
                "sigma_min_factor": 0.95, "sigma_max_factor": 1.02, "sigma_max_offset": 1e-10,
                "gamma_min_factor": 0.95, "gamma_max_factor": 1.02, "gamma_max_offset": 1e-10,
            },
        }
        ver10_update_list = [
            ("v1", "center_min_offset", -0.015), ("v1", "center_max_offset", 0.005),
            ("v1", "sigma_min_factor", 0.99), ("v1", "sigma_max_factor", 1.02),
            ("v1", "gamma_min_factor", 0.99), ("v1", "gamma_max_factor", 1.005),
            ("v1", "sigma_max_offset", 1e-10), ("v1", "gamma_max_offset", 1e-10),
            ("v2", "center_min_offset", -0.01), ("v2", "center_max_offset", 0.005),
            ("v2", "sigma_min_factor", 0.99), ("v2", "sigma_max_factor", 1.02),
            ("v2", "gamma_min_factor", 0.99), ("v2", "gamma_max_factor", 1.005),
            ("v2", "sigma_max_offset", 1e-10), ("v2", "gamma_max_offset", 1e-10),
        ]
        return self.merge_limits(base, ver10_update_list)

    # ------------------------------------------------------------------ fitting
    def _fit_single_step(
        self,
        th: np.ndarray,
        In: np.ndarray,
        cand_pars: Dict[str, float],
        R: float,
    ) -> Tuple[Any, Dict[str, np.ndarray], float, float]:
        lim_all = self.get_effective_limits()
        scaled = [amp * self.intensity_scale_factor for amp in self.prev_params["amplitude"]]

        mod = VoigtModel(prefix="v1_") + VoigtModel(prefix="v2_")
        pars = mod.make_params()
        for k in (1, 2):
            lim = lim_all[f"v{k}"]
            c_prev = self.prev_params["center"][k - 1]
            c_lo, c_hi = c_prev + lim["center_min_offset"], c_prev + lim["center_max_offset"]
            if k == 2:
                c_lo = max(self.prev_params["center"][0] + RATIO2_SEPARATION_DEG, c_lo)
            c_min, c_max = self.bounded(c_lo, c_hi, 0.005)

            s_prev = self.prev_params["sigma"][k - 1]
            s_min, s_max = self.bounded(max(1e-6, s_prev * lim["sigma_min_factor"]), s_prev * lim["sigma_max_factor"] + lim.get("sigma_max_offset", 0.0), 1e-6)
            g_prev = self.prev_params["gamma"][k - 1]
            g_min, g_max = self.bounded(max(0.0, g_prev * lim["gamma_min_factor"]), g_prev * lim["gamma_max_factor"] + lim.get("gamma_max_offset", 0.0), 1e-6)

            pars[f"v{k}_center"].set(value=float(np.clip(cand_pars[f"v{k}_center"], c_min, c_max)), min=c_min, max=c_max, vary=True)
            pars[f"v{k}_sigma"].set(value=float(np.clip(cand_pars[f"v{k}_sigma"], s_min, s_max)), min=s_min, max=s_max, vary=True)
            pars[f"v{k}_gamma"].set(value=float(np.clip(cand_pars[f"v{k}_gamma"], g_min, g_max)), min=g_min, max=g_max, vary=True, expr=None)

        lim1 = lim_all["v1"]
        a_min = max(0.0, scaled[0] * lim1["amplitude_min_factor"])
        a_min, a_max = self.bounded(a_min, scaled[0] * lim1["amplitude_max_factor"] + lim1.get("amplitude_max_offset", 0.0), 1.0)
        pars["v1_amplitude"].set(value=float(np.clip(scaled[0], a_min, a_max)), min=a_min, max=a_max, vary=True)
        # ver10: amplitude ratio fixed
        pars["v2_amplitude"].set(expr=f"v1_amplitude * {float(R):.10g}")

        mod, pars = self.attach_y0(mod, pars, In)
        out = mod.fit(In, pars, x=th, method="leastsq")
        comps = out.eval_components(x=th)
        residual_mean = float(np.sqrt(np.mean(out.residual ** 2)))
        relative_residual = residual_mean / max(1e-12, float(np.mean(np.abs(In))))
        return out, comps, residual_mean, relative_residual

    def _fit_frame(self, file_index: int, R: float, completed: int, total: int, allow_retry: bool = True) -> Tuple[FitStepPayload, float]:
        random.seed(42)
        np.random.seed(42)
        num, fname, th, In = self.load_window_data(file_index)

        start = self.perturb(self.Init_pars, 2, _PRE_FIT_PERTURB)
        out, comps, residual_mean, relative_residual = self._fit_single_step(th, In, start, R)
        best = (residual_mean, out, comps, relative_residual)
        attempt = 0
        while allow_retry and best[0] >= self.residual_limit and attempt < self.max_attempts:
            attempt += 1
            base = {f"v{r}_{nm}": float(best[1].best_values[f"v{r}_{nm}"]) for r in (1, 2) for nm in PARAM_NAMES}
            trial = self.perturb(base, 2, _RETRY_PERTURB)
            o2, c2, rm2, rr2 = self._fit_single_step(th, In, trial, R)
            if rm2 < best[0]:
                best = (rm2, o2, c2, rr2)
        residual_mean, out, comps, relative_residual = best
        best_pars = {f"v{r}_{nm}": float(out.best_values[f"v{r}_{nm}"]) for r in (1, 2) for nm in PARAM_NAMES}

        # ver10: carry only `params_to_update`; the other parameters keep their previous values
        self.prev_integral = self.current_integral
        y0_val = self.carry_y0(out)
        for nm in PARAM_NAMES:
            if nm in self.params_to_update:
                self.prev_params[nm] = [best_pars[f"v{r}_{nm}"] for r in (1, 2)]
        for r in (1, 2):
            for nm in PARAM_NAMES:
                self.Init_pars[f"v{r}_{nm}"] = self.prev_params[nm][r - 1]

        payload = FitStepPayload(
            group_id=self.group_id,
            engine=self.engine_name,
            peaks=self.peaks,
            file_index=file_index,
            total_files=total,
            completed_files=completed,
            num=num,
            filename=fname,
            residual_rmse=residual_mean,
            relative_residual=relative_residual,
            attempts=attempt,
            is_outlier=bool(residual_mean >= self.residual_limit),
            row_data=self.build_row_dict(num, best_pars, residual=residual_mean, y0=y0_val),
            x=th.tolist(),
            y_obs=In.tolist(),
            y_fit=out.best_fit.tolist(),
            components={self.peaks[r - 1]: comps.get(f"v{r}_", np.zeros_like(th)).tolist() for r in (1, 2)},
        )
        return payload, residual_mean

    def refit_frame(self, file_index: int, R: Optional[float] = None) -> FitStepPayload:
        """Step 4 repair with the fixed ratio R (the best R of the run) and the ver10 update rule."""
        num = self.files[file_index][0]
        if self.initial_ep_region < num < self.end_ep_region:
            self.params_to_update = list(PARAM_NAMES)
        else:
            self.params_to_update = ["center", "amplitude"]
        payload, _ = self._fit_frame(file_index, float(R if R is not None else self.initial_R), 1, 1)
        self.results_by_num[payload.num] = payload
        return payload

    def _run_with_R(
        self,
        R: float,
        indices: List[int],
        allow_retry: bool = True,
        prune_above: Optional[float] = None,
    ) -> Tuple[float, Dict[int, FitStepPayload], bool]:
        """Fit every pre-DIMT file forward from the first file with a fixed ratio R.

        `prune_above`: stop as soon as the running total exceeds it (the residuals are non-negative,
        so such an R cannot become the best one; the selected R is unchanged).
        """
        self.reset_to_initial()
        total_residual = 0.0
        results: Dict[int, FitStepPayload] = {}
        for c, idx in enumerate(indices, 1):
            num = self.files[idx][0]
            if self.initial_ep_region < num < self.end_ep_region:
                self.params_to_update = list(PARAM_NAMES)
            else:
                self.params_to_update = ["center", "amplitude"]
            payload, res = self._fit_frame(idx, R, c, len(indices), allow_retry=allow_retry)
            total_residual += res
            results[payload.num] = payload
            if prune_above is not None and total_residual > prune_above:
                return total_residual, results, True
        return total_residual, results, False

    def run_all(self, step_callback: Optional[Callable[[FitStepPayload], None]] = None) -> Dict[str, Any]:
        """Coarse R search over the initial-value sets, fine R search, then output the best run."""
        self.history_R.clear()
        self.history_residual.clear()
        self.results_by_num.clear()

        if self.target_num > self.dimt_onset_num:
            raise ValueError(
                f"2PeaksRatio は変態開始前 (num <= {self.dimt_onset_num}) の領域を先頭ファイルから前向きに解析します。"
                f"初期値は変態開始前のファイルから選んでください (現在の初期値: num={self.target_num})。"
            )
        indices = [i for i, (num, _) in enumerate(self.files) if num <= self.dimt_onset_num]
        if not indices:
            raise ValueError(
                f"2PeaksRatio fits only num <= DIMT_onset_num, but no file satisfies num <= {self.dimt_onset_num}."
            )

        best_total = float("inf")
        best_R = self.initial_R
        tried: set = set()
        self.pruned_R: List[float] = []

        # Search pass: the retry loop is skipped (it only engages when a frame exceeds residual_limit,
        # i.e. for clearly wrong R) and candidates are abandoned once their running total exceeds the
        # best total so far. Both only save time; the arg-min over the candidates is unchanged.
        def _try(R: float) -> None:
            nonlocal best_total, best_R
            key = round(R, 10)
            if R <= 0 or key in tried:
                return
            tried.add(key)
            prune = best_total if np.isfinite(best_total) else None
            total, _results, pruned = self._run_with_R(R, indices, allow_retry=False, prune_above=prune)
            if pruned:
                self.pruned_R.append(round(R, 6))
                return
            self.history_R.append(round(R, 6))
            self.history_residual.append(round(total, 4))
            if total < best_total:
                best_total, best_R = total, R

        # Stage 1: one R per initial-value set (ver10: A_bcc110 / A_fcc111 of rows N = 1..num_init_val_set)
        if self.r_candidates:
            for R in self.r_candidates:
                _try(R)
        else:
            for mult in INITIAL_SET_MULTIPLIERS[: self.num_init_val_set]:
                _try(self.initial_R * mult)
        # Stage 2: rough_best_R + vib * vib_ratio_fine, vib = -5 ... +5
        rough_best_R = best_R
        for vib in range(-5, 6):
            _try(rough_best_R + vib * self.vib_ratio_fine)

        self.best_R = best_R
        paired = sorted(zip(self.history_R, self.history_residual))
        self.history_R = [p[0] for p in paired]
        self.history_residual = [p[1] for p in paired]

        # Output pass with the full ver10 per-frame procedure (including retries) at the best R
        _total, best_results, _ = self._run_with_R(best_R, indices, allow_retry=True)
        self.results_by_num = dict(sorted(best_results.items()))
        if step_callback:
            for payload in self.results_by_num.values():
                step_callback(payload)

        df = self.build_dataframe()
        return {
            "group_id": self.group_id,
            "engine": self.engine_name,
            "peaks": self.peaks,
            "best_R": round(self.best_R, 6),
            "history_R": self.history_R,
            "history_residual": self.history_residual,
            "pruned_R": self.pruned_R,
            "dataframe": df,
            "rows": df.to_dict(orient="records"),
            "results_by_num": self.results_by_num,
        }
