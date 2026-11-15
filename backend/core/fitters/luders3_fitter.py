# -*- coding: utf-8 -*-
"""3-peak post-onset fitter for cold-rolled specimens with Lueders deformation.

Faithful port of Harada's `fitting_3peaks_afterLuders_csv_ver4.py`:
- Peaks: `fcc111a` (gamma 111), `bcc110a` (pre-existing alpha' 110, amplitude tied to fcc111 by the
  ratio R obtained with the 2-peak ratio engine), `bcc1102` (alpha' 110 newly formed by DIMT).
- Fixed window `[10.6, 12.3]` deg of the background-removed data, Voigt components only.
- `v2_center = v1_center + v2_delta` with `v2_delta >= 0.1` deg ("breakwater").
- `v3_center <= v3_center_cap` (11.65 deg in ver4) and at least 0.02 deg above v2.
- Backward pass `target -> DIMT_onset_num` (the region before the onset is fitted by the 2-peak ratio
  engine), then a reset to the initial values and a forward pass `target + 1 -> final_num`.
- Inside the Lueders band window `undeform_initial < num < undeform_end` (no deformation at the X-ray
  position) the parameters are not carried over.
- Forward pass: only amplitude/sigma/gamma are carried over (centers stay referenced to the initial
  values), plus the v3 center and amplitude.
- Pass-specific `update_list`s of ver4 are the defaults; residual = mean(|residual|), limit 350.

Bug fixes relative to ver4 (logic only):
- #2-1 With `scale == 0` an unconditional `.set()` after the `if/elif` overwrote the R-tied bounds of
  peak 2; it is now in an `else` branch.
- #2-2 `value=R * scaled[0]` for peak 3 with `fixed_ratio2 == 1` -> `R2 * scaled[0]`.
- #2-3 `fixed_ratio2` initialised before the loops.
- Best attempt kept in the retry loop; fixed seeds; unified columns.
The specimen-specific hand corrections of ver4 (`if i < 220: v3_center -= 0.008`) are not ported.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from lmfit.models import VoigtModel

from .base_fitter import PARAM_NAMES, BaseFitter, FitStepPayload

_PRE_FIT_PERTURB = {"center": (-0.0015, 0.005), "amplitude": (0.999, 1.001), "sigma": (0.99999, 1.00001), "gamma": (0.99999, 1.00001)}
_RETRY_PERTURB = {"amplitude": (0.995, 1.005)}

# ver4 pass-specific update lists
BACKWARD_UPDATE_LIST: List[Tuple[str, str, float]] = [
    ("v1", "amplitude_min_factor", 0.95), ("v1", "amplitude_max_factor", 1.00005),
    ("v1", "sigma_max_factor", 1.001), ("v1", "gamma_max_factor", 1.001),
    ("v2", "amplitude_min_factor", 0.97), ("v2", "amplitude_max_factor", 1.05),
    ("v2", "center_min_offset", -0.00001), ("v2", "center_max_offset", 0.025),
    ("v3", "center_min_offset", -0.008), ("v3", "amplitude_min_factor", 0.95),
    ("v3", "amplitude_min_offset", -50.0), ("v3", "center_max_offset", 0.003),
]
FORWARD_UPDATE_LIST: List[Tuple[str, str, float]] = [
    ("v1", "center_min_offset", -0.002), ("v1", "center_max_offset", 0.005),
    ("v1", "amplitude_max_factor", 1.02), ("v1", "amplitude_min_factor", 0.97),
    ("v1", "sigma_max_factor", 1.003), ("v1", "gamma_max_factor", 1.001),
    ("v2", "amplitude_min_factor", 0.98), ("v2", "amplitude_max_factor", 1.02),
    ("v2", "amplitude_max_offset", 5.0), ("v2", "center_min_offset", -0.001),
    ("v2", "center_max_offset", 0.005), ("v3", "amplitude_min_factor", 0.9),
    ("v3", "amplitude_max_factor", 1.05), ("v3", "amplitude_max_offset", 200.0),
    ("v3", "center_max_offset", 0.002), ("v3", "center_min_offset", -0.015),
    ("v2", "sigma_min_factor", 0.97), ("v2", "gamma_min_factor", 0.97),
]


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
        final_num: Optional[int] = None,
        R: float = 0.52,
        R2: float = 3.45,
        v2_delta_min: float = 0.1,
        v3_center_cap: float = 11.65,
        backward_update_list: Optional[List[Tuple[str, str, float]]] = None,
        forward_update_list: Optional[List[Tuple[str, str, float]]] = None,
        default_fit_limits: Optional[Dict[str, Dict[str, float]]] = None,
        update_list: Optional[List[Tuple[str, str, float]]] = None,
        residual_limit: float = 350.0,
        max_attempts: int = 5,
        fit_y0: bool = False,
        y0_init: float = 0.0,
    ) -> None:
        peaks_list = list(peaks) if peaks and len(peaks) == 3 else ["fcc111a", "bcc110a", "bcc1102"]

        norm_init = dict(init_params)
        if "v3_center" not in norm_init:
            # Only a 2-peak initial set was supplied: start the new bcc110 component slightly above v2
            norm_init["v3_center"] = float(norm_init.get("v2_center", 11.51)) + 0.08
            norm_init["v3_amplitude"] = max(10.0, float(norm_init.get("v2_amplitude", 500.0)) * 0.25)
            if "v2_sigma" in norm_init:
                norm_init["v3_sigma"] = float(norm_init["v2_sigma"])
            else:
                norm_init["v3_wG"] = float(norm_init.get("v2_wG", 0.19))
            if "v2_gamma" in norm_init:
                norm_init["v3_gamma"] = float(norm_init["v2_gamma"])
            else:
                norm_init["v3_wL"] = float(norm_init.get("v2_wL", 0.08))

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
            fit_y0=fit_y0,
            y0_init=y0_init,
        )

        self.dimt_onset_num = int(dimt_onset_num)
        self.undeform_initial = int(undeform_initial)
        self.undeform_end = int(undeform_end)
        self.final_num = int(final_num) if final_num is not None else None
        self.R = float(R)
        self.R2 = float(R2)
        self.v2_delta_min = float(v2_delta_min)
        self.v3_center_cap = float(v3_center_cap)
        self.backward_update_list = list(backward_update_list) if backward_update_list is not None else list(BACKWARD_UPDATE_LIST)
        self.forward_update_list = list(forward_update_list) if forward_update_list is not None else list(FORWARD_UPDATE_LIST)
        self._pass_update_list: List[Tuple[str, str, float]] = []

        # Bug #2-3 fix: initialise the switches explicitly
        self.fixed_ratio: int = 1
        self.fixed_ratio2: int = 0
        self.scale: int = 0
        self.params_to_update: List[str] = list(PARAM_NAMES)

    def _default_limits(self) -> Dict[str, Dict[str, float]]:
        """ver4 `default_fit_limits`."""
        return {
            "v1": {
                "center_min_offset": -0.01, "center_max_offset": 0.002,
                "amplitude_min_factor": 0.95, "amplitude_max_factor": 1.05,
                "amplitude_min_offset": 0.0, "amplitude_max_offset": 10.0,
                "sigma_min_factor": 0.99, "sigma_max_factor": 1.1, "sigma_max_offset": 1e-15,
                "gamma_min_factor": 0.99, "gamma_max_factor": 1.01, "gamma_max_offset": 1e-15,
            },
            "v2": {
                "center_min_offset": -0.01, "center_max_offset": 0.01,
                "amplitude_min_factor": 0.9, "amplitude_max_factor": 1.1,
                "amplitude_min_offset": 0.0, "amplitude_max_offset": 10.0,
                "sigma_min_factor": 0.99, "sigma_max_factor": 1.01, "sigma_max_offset": 1e-15,
                "gamma_min_factor": 0.99, "gamma_max_factor": 1.001, "gamma_max_offset": 1e-10,
            },
            "v3": {
                "center_min_offset": -0.03, "center_max_offset": 0.08,
                "amplitude_min_factor": 0.9, "amplitude_max_factor": 1.1,
                "amplitude_min_offset": 20.0, "amplitude_max_offset": 10.0,
                "sigma_min_factor": 0.9, "sigma_max_factor": 1.005, "sigma_max_offset": 1e-15,
                "gamma_min_factor": 0.9, "gamma_max_factor": 1.005, "gamma_max_offset": 1e-10,
            },
        }

    def get_effective_limits(self) -> Dict[str, Dict[str, float]]:
        # ver4 replaces `update_list` per pass; a user `update_list` is applied on top
        return self.merge_limits(self.merge_limits(self.default_fit_limits, self._pass_update_list), self.update_list)

    def _amp_bounds(self, base_a: float, lim: Dict[str, float]) -> Tuple[float, float]:
        a_min = max(0.0, base_a * lim["amplitude_min_factor"] + lim.get("amplitude_min_offset", 0.0))
        return self.bounded(a_min, base_a * lim["amplitude_max_factor"] + lim.get("amplitude_max_offset", 0.0), 1.0)

    def _perform_fitting_once(
        self,
        th: np.ndarray,
        In: np.ndarray,
        cand_pars: Dict[str, float],
        num_val: int,
    ) -> Tuple[Any, Dict[str, np.ndarray], float, float]:
        lim_all = self.get_effective_limits()
        prev = self.prev_params
        scaled = [amp * self.intensity_scale_factor for amp in prev["amplitude"]]

        mod = VoigtModel(prefix="v1_") + VoigtModel(prefix="v2_") + VoigtModel(prefix="v3_")
        pars = mod.make_params()

        for k in (1, 2, 3):
            lim = lim_all[f"v{k}"]
            if k == 1:
                c_min, c_max = self.bounded(prev["center"][0] + lim["center_min_offset"], prev["center"][0] + lim["center_max_offset"], 0.005)
                pars["v1_center"].set(value=float(np.clip(cand_pars["v1_center"], c_min, c_max)), min=c_min, max=c_max, vary=True)
            elif k == 2:
                # Breakwater: v2 stays at least v2_delta_min above v1 while following it
                delta0 = max(self.v2_delta_min, min(2.0, cand_pars["v2_center"] - cand_pars["v1_center"]))
                pars.add("v2_delta", value=delta0, min=self.v2_delta_min, max=2.0, vary=True)
                pars["v2_center"].set(expr="v1_center + v2_delta")
            else:
                c_lo = max(prev["center"][1] + 0.02, prev["center"][2] + lim["center_min_offset"])
                c_hi = min(prev["center"][2] + lim["center_max_offset"], self.v3_center_cap)
                c_min, c_max = self.bounded(c_lo, c_hi, 0.005)
                pars["v3_center"].set(value=float(np.clip(cand_pars["v3_center"], c_min, c_max)), min=c_min, max=c_max, vary=True)

            if self.scale == 0:
                if k == 2 and self.fixed_ratio == 1:
                    a_min, a_max = self._amp_bounds(self.R * prev["amplitude"][0], lim)
                elif k == 3 and self.fixed_ratio2 == 1:
                    a_min, a_max = self._amp_bounds(self.R2 * prev["amplitude"][0], lim)
                else:  # Bug #2-1 fix
                    a_min, a_max = self._amp_bounds(prev["amplitude"][k - 1], lim)
                a_val = cand_pars[f"v{k}_amplitude"]
            else:
                if k == 2 and self.fixed_ratio == 1:
                    a_val = self.R * scaled[0]
                elif k == 3 and self.fixed_ratio2 == 1:
                    a_val = self.R2 * scaled[0]  # Bug #2-2 fix (R -> R2)
                else:
                    a_val = scaled[k - 1]
                a_min, a_max = self._amp_bounds(a_val, lim)
            pars[f"v{k}_amplitude"].set(value=float(np.clip(a_val, a_min, a_max)), min=a_min, max=a_max, vary=True)

            s_min, s_max = self.bounded(max(1e-6, prev["sigma"][k - 1] * lim["sigma_min_factor"]), prev["sigma"][k - 1] * lim["sigma_max_factor"] + lim.get("sigma_max_offset", 0.0), 1e-6)
            g_min, g_max = self.bounded(max(0.0, prev["gamma"][k - 1] * lim["gamma_min_factor"]), prev["gamma"][k - 1] * lim["gamma_max_factor"] + lim.get("gamma_max_offset", 0.0), 1e-6)
            pars[f"v{k}_sigma"].set(value=float(np.clip(cand_pars[f"v{k}_sigma"], s_min, s_max)), min=s_min, max=s_max, vary=True)
            pars[f"v{k}_gamma"].set(value=float(np.clip(cand_pars[f"v{k}_gamma"], g_min, g_max)), min=g_min, max=g_max, vary=True, expr=None)

        mod, pars = self.attach_y0(mod, pars, In)
        out = mod.fit(In, pars, x=th, method="leastsq")
        comps = out.eval_components(x=th)
        residual_mean = float(np.mean(np.abs(out.residual)))
        relative_residual = residual_mean / max(1e-12, float(np.mean(np.abs(In))))
        return out, comps, residual_mean, relative_residual

    def fit_one_file(self, file_index: int, completed_count: int) -> FitStepPayload:
        random.seed(42)
        np.random.seed(42)
        num, fname, th, In = self.load_window_data(file_index)

        start = self.perturb(self.Init_pars, 3, _PRE_FIT_PERTURB)
        out, comps, residual_mean, relative_residual = self._perform_fitting_once(th, In, start, num)
        best = (residual_mean, out, comps, relative_residual)
        attempt = 0
        while best[0] >= self.residual_limit and attempt < self.max_attempts:
            attempt += 1
            base = {f"v{r}_{nm}": float(best[1].best_values[f"v{r}_{nm}"]) for r in (1, 2, 3) for nm in PARAM_NAMES}
            trial = self.perturb(base, 3, _RETRY_PERTURB)
            o2, c2, rm2, rr2 = self._perform_fitting_once(th, In, trial, num)
            if rm2 < best[0]:
                best = (rm2, o2, c2, rr2)
        residual_mean, out, comps, relative_residual = best
        best_pars = {f"v{r}_{nm}": float(out.best_values[f"v{r}_{nm}"]) for r in (1, 2, 3) for nm in PARAM_NAMES}

        self.prev_integral = self.current_integral
        y0_val = self.carry_y0(out) if self.params_to_update else self.prev_y0
        for nm in PARAM_NAMES:
            if nm in self.params_to_update:
                self.prev_params[nm] = [best_pars[f"v{r}_{nm}"] for r in (1, 2, 3)]
        for r in (1, 2, 3):
            for nm in PARAM_NAMES:
                self.Init_pars[f"v{r}_{nm}"] = self.prev_params[nm][r - 1]

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
            row_data=self.build_row_dict(num, best_pars, residual=residual_mean, y0=float(out.best_values.get("bkg_c", y0_val))),
            x=th.tolist(),
            y_obs=In.tolist(),
            y_fit=out.best_fit.tolist(),
            components={self.peaks[r - 1]: comps.get(f"v{r}_", np.zeros_like(th)).tolist() for r in (1, 2, 3)},
        )
        self.results_by_num[num] = payload
        return payload

    def refit_frame(self, file_index: int) -> FitStepPayload:
        """Step 4 repair with the pass settings (backward / forward) that apply to this frame."""
        num_val = self.files[file_index][0]
        in_band = self.undeform_initial < num_val < self.undeform_end
        if num_val <= self.target_num:
            self.scale, self.fixed_ratio, self.fixed_ratio2 = 0, 1, 0
            self._pass_update_list = self.backward_update_list
            self.params_to_update = [] if in_band else list(PARAM_NAMES)
        else:
            self.scale, self.fixed_ratio, self.fixed_ratio2 = 1, 1, 0
            self._pass_update_list = self.forward_update_list
            self.params_to_update = [] if in_band else ["amplitude", "sigma", "gamma"]
        return self.fit_one_file(file_index, completed_count=1)

    def run_all(self, step_callback: Optional[Callable[[FitStepPayload], None]] = None) -> Dict[str, Any]:
        if self.target_num < self.dimt_onset_num:
            raise ValueError(
                f"3PeaksLuders は変態開始後 (num >= {self.dimt_onset_num}) の領域を解析します。"
                f"初期値は変態開始後のファイルから選んでください (現在の初期値: num={self.target_num})。"
            )
        self.results_by_num.clear()
        self.reset_to_initial()
        completed = 0

        # Step 1: backward from the initial file down to the DIMT onset
        self.scale, self.fixed_ratio, self.fixed_ratio2 = 0, 1, 0
        self._pass_update_list = self.backward_update_list
        for i in reversed(range(0, self.target_index + 1)):
            num_val = self.files[i][0]
            if num_val < self.dimt_onset_num:
                break
            in_band = self.undeform_initial < num_val < self.undeform_end
            self.params_to_update = [] if in_band else list(PARAM_NAMES)
            completed += 1
            payload = self.fit_one_file(i, completed_count=completed)
            if step_callback:
                step_callback(payload)

        # Step 2: reset and forward from the initial file + 1 to final_num
        self.reset_to_initial()
        self.scale, self.fixed_ratio, self.fixed_ratio2 = 1, 1, 0
        self._pass_update_list = self.forward_update_list
        prev_integral_temp = 0.0
        for i in range(self.target_index + 1, len(self.files)):
            num_val = self.files[i][0]
            if self.final_num is not None and num_val >= self.final_num:
                break
            if self.undeform_initial < num_val < self.undeform_end:
                self.params_to_update = []
                self.prev_integral = prev_integral_temp
            else:
                self.params_to_update = ["amplitude", "sigma", "gamma"]
                prev_integral_temp = self.prev_integral
            completed += 1
            payload = self.fit_one_file(i, completed_count=completed)
            # ver4: the new bcc110 component always follows its own fitted amplitude and center
            self.prev_params["amplitude"][2] = float(payload.row_data.get(f"I_{self.peaks[2]}", 0.0))
            self.prev_params["center"][2] = float(payload.row_data.get(f"2th_{self.peaks[2]}", self.prev_params["center"][2]))
            self.Init_pars["v3_amplitude"] = self.prev_params["amplitude"][2]
            self.Init_pars["v3_center"] = self.prev_params["center"][2]
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
