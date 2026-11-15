# -*- coding: utf-8 -*-
"""Stage 3: Origin-compatible Voigt model, crystallographic phase/hkl auto-identification,
and multi-file initial parameter estimation for metastable austenitic steels (γ-FCC + α'-BCC).
"""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from lmfit.models import ConstantModel, VoigtModel
from scipy.integrate import trapezoid
from scipy.signal import find_peaks
from scipy.special import wofz

from .utils import find_file_by_num, list_sorted_bcg_files, resolve_analyzed_folder

FWHM_G_FACTOR = 2.0 * math.sqrt(2.0 * math.log(2.0))  # 2 * sqrt(2 * ln 2) ≈ 2.3548200450309493


def is_martensite_peak(peak_name: str) -> bool:
    """Return True if `peak_name` belongs to the α'-BCC / BCT martensite phase."""
    low = str(peak_name).strip().lower()
    return low.startswith(("bcc", "bct", "alpha"))


def subtract_local_linear_bg(
    x: np.ndarray,
    y: np.ndarray,
    n_edge: int = 10,
) -> Tuple[np.ndarray, np.ndarray, float, float]:
    """Subtract linear background connecting the mean coordinates of the first and last `n_edge` points.

    Returns:
        `(y_subtracted, y_bg_line, slope, intercept)`
    """
    if len(x) < 2:
        return y.copy(), np.zeros_like(y), 0.0, 0.0
    k = min(int(n_edge), max(1, len(x) // 2))
    start_x = float(np.mean(x[:k]))
    start_y = float(np.mean(y[:k]))
    end_x = float(np.mean(x[-k:]))
    end_y = float(np.mean(y[-k:]))
    dx = end_x - start_x
    slope = (end_y - start_y) / dx if abs(dx) > 1e-9 else 0.0
    intercept = start_y - slope * start_x
    bg_line = slope * x + intercept
    return (y - bg_line), bg_line, float(slope), float(intercept)


def calc_bcc110_from_bcc211(
    th2_bcc211_deg: float,
    sigma_211: float,
    gamma_211: float,
) -> Dict[str, float]:
    """Convert `bcc211(112)` ($Q=6$) position & widths to `bcc110(101)` ($Q=2$) via Bragg's law and $\\tan\\theta$ ratio.

    - Center angle:
      $$2\\theta_{110}^{\\text{calc}} = 2 \\arcsin\\left(\\frac{1}{\\sqrt{3}}\\sin\\theta_{211}\\right)$$
    - Strain broadening ratio:
      $$R_{\\tan} = \\frac{\\tan\\theta_{110}^{\\text{calc}}}{\\tan\\theta_{211}}$$
    """
    th_211_rad = math.radians(float(th2_bcc211_deg) / 2.0)
    sin_110 = min(0.9999, max(1e-6, math.sin(th_211_rad) / math.sqrt(3.0)))
    th_110_rad = math.asin(sin_110)
    th2_110_deg = 2.0 * math.degrees(th_110_rad)

    tan_211 = max(1e-6, math.tan(th_211_rad))
    tan_110 = max(1e-6, math.tan(th_110_rad))
    r_tan = tan_110 / tan_211

    return {
        "th2_110_calc": float(th2_110_deg),
        "center_110_calc": float(th2_110_deg),
        "r_tan": float(r_tan),
        "sigma_110_calc": max(1e-6, float(sigma_211) * r_tan),
        "gamma_110_calc": max(1e-10, float(gamma_211) * r_tan),
    }


def sigma_to_wG(sigma: float) -> float:
    """Convert Gaussian standard deviation sigma to Gaussian FWHM wG (Origin convention)."""
    return float(sigma) * FWHM_G_FACTOR


def wG_to_sigma(wG: float) -> float:
    """Convert Gaussian FWHM wG to Gaussian standard deviation sigma."""
    return max(1e-8, float(wG) / FWHM_G_FACTOR)


def gamma_to_wL(gamma: float) -> float:
    """Convert Lorentzian HWHM gamma to Lorentzian FWHM wL (Origin convention)."""
    return float(gamma) * 2.0


def wL_to_gamma(wL: float) -> float:
    """Convert Lorentzian FWHM wL to Lorentzian HWHM gamma."""
    return max(1e-10, float(wL) / 2.0)


def calc_origin_fwhm(wG: float, wL: float) -> float:
    """Olivero-Longbothum approximation for Voigt FWHM used by Origin and existing scripts."""
    return 0.5346 * wL + math.sqrt(0.2166 * (wL ** 2) + (wG ** 2))


def eval_origin_voigt(x: np.ndarray, y0: float, xc: float, A: float, wG: float, wL: float) -> np.ndarray:
    """Exact Origin Peak Analyzer Voigt profile evaluation via Faddeeva function w(z)."""
    sigma = max(1e-8, wG_to_sigma(wG))
    gamma = max(0.0, wL_to_gamma(wL))
    z = ((x - xc) + 1j * gamma) / (sigma * math.sqrt(2.0))
    profile = np.real(wofz(z)) / (sigma * math.sqrt(2.0 * math.pi))
    return y0 + A * profile


# Crystallographic definitions for Metastable Austenitic Steel (γ-FCC & α'-BCC)
PHASE_REFLECTIONS: List[Dict[str, Any]] = [
    {"name": "fcc111", "phase": "gamma", "phase_label": "γ-FCC", "hkl": "(111)", "Q": 3, "default_2th": 11.42},
    {"name": "bcc110", "phase": "alpha_prime", "phase_label": "α'-BCC", "hkl": "(110)", "Q": 2, "default_2th": 11.52},
    {"name": "fcc200", "phase": "gamma", "phase_label": "γ-FCC", "hkl": "(200)", "Q": 4, "default_2th": 13.21},
    {"name": "bcc200", "phase": "alpha_prime", "phase_label": "α'-BCC", "hkl": "(200)", "Q": 4, "default_2th": 16.32},
    {"name": "fcc220", "phase": "gamma", "phase_label": "γ-FCC", "hkl": "(220)", "Q": 8, "default_2th": 18.73},
    {"name": "bcc211", "phase": "alpha_prime", "phase_label": "α'-BCC", "hkl": "(211)", "Q": 6, "default_2th": 20.02},
    {"name": "fcc311", "phase": "gamma", "phase_label": "γ-FCC", "hkl": "(311)", "Q": 11, "default_2th": 22.00},
    {"name": "fcc222", "phase": "gamma", "phase_label": "γ-FCC", "hkl": "(222)", "Q": 12, "default_2th": 22.95},
    {"name": "bcc220", "phase": "alpha_prime", "phase_label": "α'-BCC", "hkl": "(220)", "Q": 8, "default_2th": 23.16},
]

CANDIDATE_GROUP_SPECS: List[Dict[str, Any]] = [
    {
        "group_id": "fcc111_bcc110",
        "label": "fcc111 + bcc110 (重畳ペア)",
        "category": "multi_pair",
        "peaks": ["fcc111", "bcc110"],
        "phases": ["gamma", "alpha_prime"],
        "range_min": 10.90,
        "range_max": 12.10,
        "recommended_stage": "late",
        "default_engine": "2PeaksRatio",
        "supported_engines": ["2PeaksRatio", "3PeaksLuders", "MultiPeaks"],
        "default_selected": True,
        "description": "γ(111) 主ピークと α'(110) マルテンサイト主ピークの重畳ペア",
    },
    {
        "group_id": "fcc200",
        "label": "fcc200 (γ単一ピーク)",
        "category": "single",
        "peaks": ["fcc200"],
        "phases": ["gamma"],
        "range_min": 12.60,
        "range_max": 13.80,
        "recommended_stage": "early",
        "default_engine": "1Peak",
        "supported_engines": ["1Peak"],
        "default_selected": True,
        "description": "孤立した高強度 γ(200) オーステナイト単一ピーク",
    },
    {
        "group_id": "bcc200",
        "label": "bcc200 (α'単一ピーク)",
        "category": "single",
        "peaks": ["bcc200"],
        "phases": ["alpha_prime"],
        "range_min": 15.80,
        "range_max": 16.85,
        "recommended_stage": "late",
        "default_engine": "1Peak",
        "supported_engines": ["1Peak"],
        "default_selected": False,
        "description": "α'(200) マルテンサイト単一ピーク（微弱時は非推奨）",
    },
    {
        "group_id": "fcc220",
        "label": "fcc220 (γ単一ピーク)",
        "category": "single",
        "peaks": ["fcc220"],
        "phases": ["gamma"],
        "range_min": 18.20,
        "range_max": 19.30,
        "recommended_stage": "early",
        "default_engine": "1Peak",
        "supported_engines": ["1Peak", "MultiPeaks"],
        "default_selected": True,
        "description": "γ(220) オーステナイト単一ピーク",
    },
    {
        "group_id": "bcc211",
        "label": "bcc211 (α'単一ピーク)",
        "category": "single",
        "peaks": ["bcc211"],
        "phases": ["alpha_prime"],
        "range_min": 19.32,
        "range_max": 20.72,
        "recommended_stage": "late",
        "default_engine": "1Peak",
        "supported_engines": ["1Peak", "MultiPeaks"],
        "default_selected": True,
        "description": "DIMT進行の指標となる孤立 α'(211) マルテンサイトピーク",
    },
    {
        "group_id": "fcc311",
        "label": "fcc311 (γ単一ピーク)",
        "category": "single",
        "peaks": ["fcc311"],
        "phases": ["gamma"],
        "range_min": 21.40,
        "range_max": 22.55,
        "recommended_stage": "early",
        "default_engine": "1Peak",
        "supported_engines": ["1Peak", "MultiPeaks"],
        "default_selected": True,
        "description": "γ(311) オーステナイト単一ピーク",
    },
    {
        "group_id": "fcc222_bcc220",
        "label": "fcc222 + bcc220 (重畳ペア)",
        "category": "multi_pair",
        "peaks": ["fcc222", "bcc220"],
        "phases": ["gamma", "alpha_prime"],
        "range_min": 22.45,
        "range_max": 23.65,
        "recommended_stage": "late",
        "default_engine": "MultiPeaks",
        "supported_engines": ["MultiPeaks", "2PeaksRatio"],
        "default_selected": False,
        "description": "高角側の γ(222) と α'(220) の重畳ペア",
    },
]


@dataclass
class PeakFitParam:
    peak_name: str
    phase: str
    hkl: str
    No: int
    y0: float
    xc: float
    A: float
    wG: float
    wL: float
    FWHM: float
    sigma: float
    gamma: float
    snr: float


@dataclass
class CandidateFitResult:
    group_id: str
    num: int
    filename: str
    range_min: float
    range_max: float
    vary_y0: bool
    r_squared: float
    rmse: float
    relative_residual: float
    is_weak: bool
    peaks: List[PeakFitParam]
    x: List[float]
    y_obs: List[float]
    y_fit: List[float]
    residual: List[float]
    components: Dict[str, List[float]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "num": self.num,
            "filename": self.filename,
            "range_min": round(self.range_min, 4),
            "range_max": round(self.range_max, 4),
            "vary_y0": self.vary_y0,
            "r_squared": round(self.r_squared, 6),
            "rmse": round(self.rmse, 4),
            "relative_residual": round(self.relative_residual, 5),
            "is_weak": self.is_weak,
            "peaks": [
                {
                    "peak_name": p.peak_name,
                    "phase": p.phase,
                    "hkl": p.hkl,
                    "No": p.No,
                    "y0": round(p.y0, 5),
                    "xc": round(p.xc, 5),
                    "A": round(p.A, 5),
                    "wG": round(p.wG, 5),
                    "wL": round(p.wL, 5),
                    "FWHM": round(p.FWHM, 5),
                    "sigma": round(p.sigma, 6),
                    "gamma": round(p.gamma, 6),
                    "snr": round(p.snr, 2),
                }
                for p in self.peaks
            ],
            "x": [round(v, 5) for v in self.x],
            "y_obs": [round(v, 4) for v in self.y_obs],
            "y_fit": [round(v, 4) for v in self.y_fit],
            "residual": [round(v, 4) for v in self.residual],
            "components": {k: [round(v, 4) for v in arr] for k, arr in self.components.items()},
        }


def select_representative_files(bcg_dir: str | Path) -> Dict[str, Any]:
    """Automatically select early (γ single-phase) and late (γ + α' dual-phase) representative files.

    Implements Section 3.3 (2) Auto Mode:
    - Scans early 4–12% region (preferring num=50 if available and clean) where fcc111/fcc200
      intensity is strong and bcc211 (19.6–20.4 deg) integral intensity is at noise level.
    - Scans late 80–95% region (preferring num=900 if available and strong) where α'-martensite
      (bcc110 and bcc211) integral intensity is well-developed.
    """
    bcg_path = Path(bcg_dir)
    files = list_sorted_bcg_files(bcg_path)
    if not files:
        raise FileNotFoundError(f"No *bcg.csv files found in {bcg_path}")

    n_files = len(files)
    if n_files == 1:
        only_num = files[0][0]
        return {
            "early_num": only_num,
            "late_num": only_num,
            "selected_nums": [only_num],
            "dimt_onset_estimate": only_num,
        }

    # Check if standard reference numbers (50 and 900) exist in the dataset
    num_to_path = {num: p for num, p in files}

    # Early window: 3% to 12% of files
    early_start = max(0, int(n_files * 0.03))
    early_end = max(early_start + 1, int(n_files * 0.12))
    early_candidates = files[early_start:early_end]

    best_early_num = early_candidates[0][0]
    best_early_score = -float("inf")

    for num, p in early_candidates:
        try:
            arr = np.loadtxt(p, delimiter=",")
            x, y = arr[:, 0], arr[:, 1]
            fcc_mask = (x >= 11.2) & (x <= 13.5)
            bcc211_mask = (x >= 19.7) & (x <= 20.4)
            fcc_peak = float(np.max(y[fcc_mask])) if np.any(fcc_mask) else 0.0
            bcc_area = float(trapezoid(np.maximum(0.0, y[bcc211_mask]), x[bcc211_mask])) if np.any(bcc211_mask) else 0.0
            # Prefer canonical reference num=50 (5% point) when bcc211 is at noise level
            bonus = 2.0 if num == 50 else 1.0
            score = bonus * fcc_peak / (100.0 + bcc_area)
            if score > best_early_score:
                best_early_score = score
                best_early_num = num
        except Exception:
            continue

    # Late window: 78% to 94% of files
    late_start = max(0, int(n_files * 0.78))
    late_end = max(late_start + 1, int(n_files * 0.94))
    late_candidates = files[late_start:late_end]

    best_late_num = late_candidates[-1][0]
    best_late_score = -float("inf")

    for num, p in late_candidates:
        try:
            arr = np.loadtxt(p, delimiter=",")
            x, y = arr[:, 0], arr[:, 1]
            bcc211_mask = (x >= 19.6) & (x <= 20.45)
            bcc110_mask = (x >= 11.46) & (x <= 11.80)
            bcc211_area = float(trapezoid(np.maximum(0.0, y[bcc211_mask]), x[bcc211_mask])) if np.any(bcc211_mask) else 0.0
            bcc110_area = float(trapezoid(np.maximum(0.0, y[bcc110_mask]), x[bcc110_mask])) if np.any(bcc110_mask) else 0.0
            bonus = 1.25 if num == 900 else 1.0
            score = bonus * (bcc211_area * 20.0 + bcc110_area * 0.5)
            if score > best_late_score:
                best_late_score = score
                best_late_num = num
        except Exception:
            continue

    # Estimate DIMT onset by sampling ~25 files across the dataset for bcc211 emergence
    sample_step = max(1, n_files // 25)
    sampled = files[::sample_step]
    bcc211_areas: List[Tuple[int, float]] = []
    for num, p in sampled:
        try:
            arr = np.loadtxt(p, delimiter=",")
            x, y = arr[:, 0], arr[:, 1]
            m = (x >= 19.65) & (x <= 20.40)
            area = float(trapezoid(np.maximum(0.0, y[m]), x[m])) if np.any(m) else 0.0
            bcc211_areas.append((num, area))
        except Exception:
            continue

    dimt_onset_num = files[min(len(files) - 1, max(1, int(n_files * 0.18)))][0]
    if len(bcc211_areas) >= 4:
        base_area = float(np.median([a for _, a in bcc211_areas[:3]]))
        max_area = max(a for _, a in bcc211_areas)
        threshold_area = base_area + 0.08 * max(10.0, max_area - base_area)
        for num, area in bcc211_areas:
            if area > threshold_area and num > best_early_num:
                dimt_onset_num = num
                break

    selected = sorted(list({best_early_num, best_late_num}))
    return {
        "early_num": best_early_num,
        "late_num": best_late_num,
        "selected_nums": selected,
        "dimt_onset_estimate": dimt_onset_num,
    }


def predict_crystallographic_peaks(x: np.ndarray, y: np.ndarray) -> List[Dict[str, Any]]:
    """Identify the 9 reflection positions of γ-FCC and α'-BCC phases using Bragg's law."""
    # Locate main peak in 11.0 ~ 11.8 deg as fcc111 (Q=3)
    m111 = (x >= 11.10) & (x <= 11.75)
    if np.any(m111):
        idx_max = int(np.argmax(y[m111]))
        th2_fcc111 = float(x[m111][idx_max])
    else:
        th2_fcc111 = 11.41

    sin_th_fcc111 = math.sin(math.radians(th2_fcc111 / 2.0))
    # k_gamma = lambda / (2 * a_gamma) = sin(theta_111) / sqrt(3)
    k_gamma = sin_th_fcc111 / math.sqrt(3.0)

    # Check if fcc200 (12.8 ~ 13.5 deg) has a clear peak to refine k_gamma
    m200 = (x >= 12.85) & (x <= 13.55)
    if np.any(m200) and np.max(y[m200]) > 200.0:
        th2_fcc200_obs = float(x[m200][int(np.argmax(y[m200]))])
        k_gamma_200 = math.sin(math.radians(th2_fcc200_obs / 2.0)) / math.sqrt(4.0)
        k_gamma = 0.5 * (k_gamma + k_gamma_200)

    # Lattice constant ratio a_gamma / a_alpha_prime ≈ 1.251
    # Check bcc211 (19.6 ~ 20.4 deg) to refine k_alpha if α' phase is present
    k_alpha = k_gamma * 1.251
    mbcc211 = (x >= 19.65) & (x <= 20.40)
    if np.any(mbcc211) and np.max(y[mbcc211]) > 80.0:
        th2_bcc211_obs = float(x[mbcc211][int(np.argmax(y[mbcc211]))])
        k_alpha_obs = math.sin(math.radians(th2_bcc211_obs / 2.0)) / math.sqrt(6.0)
        if 1.22 <= (k_alpha_obs / k_gamma) <= 1.28:
            k_alpha = k_alpha_obs

    markers: List[Dict[str, Any]] = []
    for ref in PHASE_REFLECTIONS:
        k_val = k_gamma if ref["phase"] == "gamma" else k_alpha
        sin_th = min(0.999, k_val * math.sqrt(float(ref["Q"])))
        pred_2th = 2.0 * math.degrees(math.asin(sin_th))

        # Refine to local maximum within ±0.18 deg if a distinct peak exists
        win = (x >= pred_2th - 0.18) & (x <= pred_2th + 0.18)
        obs_2th = pred_2th
        peak_intensity = 0.0
        if np.any(win):
            x_w, y_w = x[win], y[win]
            # For bcc110 which sits on the right shoulder of fcc111, keep theoretical offset if overwhelmed
            if ref["name"] == "bcc110":
                sh_win = (x >= max(th2_fcc111 + 0.08, pred_2th - 0.12)) & (x <= pred_2th + 0.18)
                if np.any(sh_win):
                    obs_2th = float(th2_fcc111 + 0.125)
                    idx_near = int(np.argmin(np.abs(x - obs_2th)))
                    peak_intensity = float(y[idx_near])
            else:
                idx_local = int(np.argmax(y_w))
                obs_2th = float(x_w[idx_local])
                peak_intensity = float(y_w[idx_local])

        markers.append({
            "name": ref["name"],
            "phase": ref["phase"],
            "phase_label": ref["phase_label"],
            "hkl": ref["hkl"],
            "theoretical_2th": round(pred_2th, 4),
            "observed_2th": round(obs_2th, 4),
            "intensity": round(peak_intensity, 2),
        })

    return markers


def fit_origin_voigt_group(
    x_full: np.ndarray,
    y_full: np.ndarray,
    num: int,
    filename: str,
    group_id: str,
    peak_names: List[str],
    range_min: float,
    range_max: float,
    initial_centers: Optional[List[float]] = None,
    initial_wG: Optional[List[float]] = None,
    initial_wL: Optional[List[float]] = None,
    initial_A: Optional[List[float]] = None,
    vary_y0: bool = False,
    subtract_linear_bg: bool = False,
) -> CandidateFitResult:
    """Perform an Origin-compatible independent-width Voigt fit on a single peak or multi-peak group."""
    random.seed(42)
    np.random.seed(42)

    mask = (x_full >= range_min) & (x_full <= range_max)
    x = x_full[mask]
    y_raw = y_full[mask]

    if len(x) < 10:
        raise ValueError(f"Insufficient points ({len(x)}) in range [{range_min}, {range_max}]")

    if subtract_linear_bg:
        y, _, _, _ = subtract_local_linear_bg(x, y_raw, n_edge=10)
    else:
        y = y_raw

    ref_lookup = {r["name"]: r for r in PHASE_REFLECTIONS}
    markers_map = {m["name"]: m for m in predict_crystallographic_peaks(x_full, y_full)}

    noise_floor = max(1.0, float(np.std(np.diff(y))) / math.sqrt(2.0))

    model = None
    params = None

    if vary_y0:
        c_mod = ConstantModel(prefix="bg_")
        c_pars = c_mod.make_params(c=float(np.percentile(y, 10)))
        c_pars["bg_c"].set(min=-500.0, max=max(500.0, float(np.max(y)) * 0.5), vary=True)
        model = c_mod
        params = c_pars

    n_peaks = len(peak_names)
    prev_c0: Optional[float] = None
    for idx, pk_name in enumerate(peak_names):
        prefix = f"v{idx + 1}_"
        vm = VoigtModel(prefix=prefix)
        p = vm.make_params()

        is_bcc = is_martensite_peak(pk_name)
        # Determine initial center
        if initial_centers and idx < len(initial_centers) and initial_centers[idx] is not None:
            c0 = float(initial_centers[idx])
        elif pk_name in markers_map:
            c0 = float(markers_map[pk_name]["observed_2th"])
        else:
            c0 = float(range_min + (idx + 1) * (range_max - range_min) / (n_peaks + 1))

        # Special handling for overlapping fcc111 + bcc110 pair
        if n_peaks == 2 and peak_names[0].startswith("fcc111") and is_bcc:
            idx_max = int(np.argmax(y))
            c_fcc = float(x[idx_max])
            if idx == 0:
                c0 = float(initial_centers[0]) if (initial_centers and len(initial_centers) > 0 and initial_centers[0] is not None) else c_fcc
                c_min, c_max = max(range_min, c0 - 0.12), min(range_max, c0 + 0.08)
            else:
                c0 = float(initial_centers[1]) if (initial_centers and len(initial_centers) > 1 and initial_centers[1] is not None) else (c_fcc + 0.125)
                init_spacing = max(0.02, abs(c0 - (prev_c0 if prev_c0 is not None else c_fcc)))
                min_sep = min(0.03, 0.30 * init_spacing)
                c_min = max((prev_c0 if prev_c0 is not None else c_fcc) + min_sep, c0 - 0.12)
                c_max = min(range_max, c0 + 0.28)
        elif n_peaks == 1:
            # For single isolated peak, center initial guess at maximum in window
            if not (initial_centers and idx < len(initial_centers) and initial_centers[idx] is not None):
                c0 = float(x[int(np.argmax(y))])
            c_min, c_max = max(range_min, c0 - 0.35), min(range_max, c0 + 0.35)
        else:
            c_min = max(range_min, c0 - 0.25)
            if prev_c0 is not None:
                init_spacing = max(0.02, abs(c0 - prev_c0))
                min_sep = min(0.03, 0.30 * init_spacing)
                c_min = max(c_min, prev_c0 + min_sep)
            c_max = min(range_max, c0 + 0.25)

        # Item 2 Guard: strictly prevent min >= max inversion
        if c_min >= c_max:
            mid = 0.5 * (c_min + c_max)
            c_min = mid - 0.02
            c_max = mid + 0.02
        c0 = min(max(c0, c_min + 1e-6), c_max - 1e-6)
        prev_c0 = c0

        wG0 = (
            float(initial_wG[idx])
            if (initial_wG and idx < len(initial_wG) and initial_wG[idx])
            else (0.18 if is_bcc else 0.022)
        )
        wL0 = (
            float(initial_wL[idx])
            if (initial_wL and idx < len(initial_wL) and initial_wL[idx])
            else (0.08 if is_bcc else 0.015)
        )

        near_mask = np.abs(x - c0) <= (0.18 if is_bcc else 0.08)
        local_height = float(np.max(y[near_mask])) if np.any(near_mask) else float(np.max(y))
        local_height = max(1.0, local_height)

        if initial_A and idx < len(initial_A) and initial_A[idx] is not None and initial_A[idx] > 0:
            a0 = float(initial_A[idx])
        else:
            fwhm0 = calc_origin_fwhm(wG0, wL0)
            a0 = max(1.0, local_height * fwhm0 * (0.45 if (n_peaks > 1 and is_bcc) else 1.25))

        p[f"{prefix}center"].set(value=c0, min=c_min, max=c_max, vary=True)
        p[f"{prefix}amplitude"].set(value=a0, min=0.0, max=max(1e5, float(np.max(y)) * 10.0), vary=True)
        p[f"{prefix}sigma"].set(value=wG_to_sigma(wG0), min=1e-6, max=0.6, vary=True)
        # Item 1 Fix: Always explicitly set vary=True, expr=None on gamma!
        p[f"{prefix}gamma"].set(value=wL_to_gamma(wL0), min=1e-12, max=0.6, vary=True, expr=None)

        if model is None:
            model = vm
            params = p
        else:
            model += vm
            params.update(p)

    out = model.fit(y, params, x=x, method="leastsq", max_nfev=2000)
    comps = out.eval_components(x=x)

    y_fit = out.best_fit
    residual = y - y_fit
    ss_res = float(np.sum(residual ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-12 else 0.0
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    mean_abs_y = float(np.mean(np.abs(y)))
    rel_res = rmse / mean_abs_y if mean_abs_y > 1e-9 else 0.0

    y0_val = float(out.best_values.get("bg_c", 0.0)) if vary_y0 else 0.0

    fitted_peaks: List[PeakFitParam] = []
    comp_dict: Dict[str, List[float]] = {}

    for idx, pk_name in enumerate(peak_names):
        prefix = f"v{idx + 1}_"
        xc = float(out.best_values[f"{prefix}center"])
        A = float(out.best_values[f"{prefix}amplitude"])
        sigma = float(out.best_values[f"{prefix}sigma"])
        gamma = float(out.best_values[f"{prefix}gamma"])
        wG = sigma_to_wG(sigma)
        wL = gamma_to_wL(gamma)
        fwhm = calc_origin_fwhm(wG, wL)

        comp_arr = comps.get(prefix, np.zeros_like(x))
        comp_dict[pk_name] = (comp_arr + y0_val).tolist()
        peak_height = float(np.max(comp_arr)) if len(comp_arr) > 0 else 0.0
        snr = peak_height / noise_floor

        ref_meta = ref_lookup.get(pk_name, {"phase": "gamma" if "fcc" in pk_name else "alpha_prime", "hkl": pk_name})
        fitted_peaks.append(
            PeakFitParam(
                peak_name=pk_name,
                phase=ref_meta["phase"],
                hkl=ref_meta["hkl"],
                No=num,
                y0=y0_val,
                xc=xc,
                A=A,
                wG=wG,
                wL=wL,
                FWHM=fwhm,
                sigma=sigma,
                gamma=gamma,
                snr=snr,
            )
        )

    is_weak = any(p.snr < 3.5 or p.A < 8.0 for p in fitted_peaks) or r_squared < 0.65

    return CandidateFitResult(
        group_id=group_id,
        num=num,
        filename=filename,
        range_min=range_min,
        range_max=range_max,
        vary_y0=vary_y0,
        r_squared=r_squared,
        rmse=rmse,
        relative_residual=rel_res,
        is_weak=is_weak,
        peaks=fitted_peaks,
        x=x.tolist(),
        y_obs=y.tolist(),
        y_fit=y_fit.tolist(),
        residual=residual.tolist(),
        components=comp_dict,
    )


def run_initial_auto_detect(
    folder_path: str | Path,
    mode: str = "auto",
    manual_nums: Optional[List[int]] = None,
    vary_y0: bool = False,
) -> Dict[str, Any]:
    """Run initial peak & pair discovery across representative or manually specified files."""
    root = resolve_analyzed_folder(folder_path)
    bcg_dir = root / "bcg_removed_arpls"
    files = list_sorted_bcg_files(bcg_dir)
    if not files:
        raise FileNotFoundError(f"No *bcg.csv files found in {bcg_dir}. Run preprocessing first.")

    auto_info = select_representative_files(bcg_dir)
    if mode == "manual" and manual_nums:
        target_nums: List[int] = []
        for req_num in manual_nums:
            idx, _ = find_file_by_num(files, req_num)
            if idx >= 0:
                actual = files[idx][0]
                if actual not in target_nums:
                    target_nums.append(actual)
        if not target_nums:
            target_nums = auto_info["selected_nums"]
    else:
        target_nums = auto_info["selected_nums"]

    early_num = target_nums[0]
    late_num = target_nums[-1]

    profiles_by_num: Dict[int, Dict[str, Any]] = {}
    loaded_arrays: Dict[int, Tuple[str, np.ndarray, np.ndarray]] = {}

    for num in target_nums:
        idx, path = find_file_by_num(files, num)
        if path is None:
            continue
        arr = np.loadtxt(path, delimiter=",")
        x, y = arr[:, 0], arr[:, 1]
        loaded_arrays[num] = (path.name, x, y)
        markers = predict_crystallographic_peaks(x, y)
        # Downsample full profile slightly only if >4000 pts for fast JSON transfer while preserving peaks
        profiles_by_num[num] = {
            "num": num,
            "filename": path.name,
            "x": np.round(x, 4).tolist(),
            "y": np.round(y, 3).tolist(),
            "markers": markers,
        }

    candidate_groups: List[Dict[str, Any]] = []
    for spec in CANDIDATE_GROUP_SPECS:
        gid = spec["group_id"]
        fits_by_num: Dict[str, Dict[str, Any]] = {}
        for num, (fname, x, y) in loaded_arrays.items():
            try:
                fit_res = fit_origin_voigt_group(
                    x_full=x,
                    y_full=y,
                    num=num,
                    filename=fname,
                    group_id=gid,
                    peak_names=spec["peaks"],
                    range_min=spec["range_min"],
                    range_max=spec["range_max"],
                    vary_y0=vary_y0,
                )
                fits_by_num[str(num)] = fit_res.to_dict()
            except Exception as e:
                fits_by_num[str(num)] = {"error": str(e), "num": num}

        rec_num = early_num if spec["recommended_stage"] == "early" else late_num
        if str(rec_num) not in fits_by_num and target_nums:
            rec_num = target_nums[0]

        rec_fit = fits_by_num.get(str(rec_num), {})
        is_weak = bool(rec_fit.get("is_weak", False))

        candidate_groups.append({
            **spec,
            "recommended_num": rec_num,
            "selected_num": rec_num,
            "selected": bool(spec["default_selected"] and not is_weak),
            "is_weak": is_weak,
            "fits_by_num": fits_by_num,
        })

    return {
        "folder_path": str(root),
        "mode": mode,
        "available_nums": [n for n, _ in files],
        "selected_nums": target_nums,
        "early_num": early_num,
        "late_num": late_num,
        "dimt_onset_estimate": auto_info["dimt_onset_estimate"],
        "profiles_by_num": {str(k): v for k, v in profiles_by_num.items()},
        "candidate_groups": candidate_groups,
    }
