# -*- coding: utf-8 -*-
"""Physical quantities from the fitted peak parameters `[num, 2th_*, I_*, wG_*, wL_*, FWHM_*]`.

1. Martensite volume fraction by the direct comparison method (as in Harada's Excel workflow):

       f_alpha' = (1/m sum_alpha I/R) / (1/m sum_alpha I/R + 1/n sum_gamma I/R)

   R_hkl = p |F|^2 LP exp(-2B s^2) / V^2 with Cromer-Mann atomic scattering factors (Fe/Ni alloy),
   V from the lattice parameters measured in the same data set, and LP = (1 + cos^2 2th)/(sin^2 th cos th).
   Components of the same reflection in one fitting group (e.g. `bcc110a` + `bcc1102`, pre-existing and
   newly formed alpha') are summed before entering the average. A reflection fitted to I = 0 counts as a
   measured zero; a missing (NaN) reflection is left out of that frame. Frames without both phases get
   `None` (no estimate from the gamma intensity drop).
   `include_peaks` / `exclude_peaks` select the reflections (texture-dominated reflections such as
   gamma 111 can be excluded). Per-reflection `I/R` values are exported so the average can be recomputed.
2. Lattice parameters and lattice strain (relative to the first valid frames of each peak).
3. Dislocation density by the modified Williamson-Hall method (Ungar):
   dK = 0.9/D + (pi M^2 b^2 / 2)^(1/2) rho^(1/2) K C^(1/2)  ->  rho = 2 slope^2 / (pi M^2 b^2).
   Instrumental broadening is removed from the Gaussian part only (wG_phys^2 = wG^2 - wG_inst^2).
   Contrast factors use average C_h00 / q values; treat the result as semi-quantitative.

The X-ray wavelength must be supplied (default 0.04133 nm of this beam time). It is never derived
from an assumed lattice parameter, which would force a_gamma to that assumption.
"""

from __future__ import annotations

import math
import re
from itertools import permutations, product
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

DEFAULT_WAVELENGTH_NM = 0.04133
DEFAULT_A_GAMMA_NM = 0.3588
DEFAULT_A_ALPHA_NM = 0.2905
DEFAULT_B_ISO_A2 = 0.35  # isotropic Debye-Waller B (A^2), Fe at room temperature
DEFAULT_X_NI = 0.23  # Ni atomic fraction of Fe-24Ni-0.5C-0.8V (both phases)

# Cromer-Mann coefficients (International Tables for Crystallography, Vol. C, Table 6.1.1.4)
_CROMER_MANN = {
    "Fe": ((11.7695, 7.3573, 3.5222, 2.3045), (4.7611, 0.3072, 15.3535, 76.8805), 1.0369),
    "Ni": ((12.8376, 7.2920, 4.4438, 2.3800), (3.8785, 0.2565, 12.1763, 66.3421), 1.0341),
}

# Average dislocation contrast factors (edge/screw mixture)
_CONTRAST = {"gamma": (0.30, 2.2), "alpha_prime": (0.285, 1.8)}

_PEAK_RE = re.compile(r"^(fcc|bcc|bct)(\d)(\d)(\d)(.*)$", re.IGNORECASE)

# Kept for backward compatibility of imports; derived from parse_peak_name
CRYSTAL_REFLECTIONS: Dict[str, Dict[str, Any]] = {}


def parse_peak_name(peak_name: str) -> Optional[Dict[str, Any]]:
    """Parse names such as `fcc111`, `fcc111a`, `bcc112`, `bcc101`, `bcc1102`, `bcc321`.

    Returns the canonical reflection key (indices sorted, e.g. bcc112 -> bcc211, bcc101 -> bcc110),
    phase, hkl, multiplicity and H^2, or `None` if the name is not a valid cubic reflection.
    """
    m = _PEAK_RE.match(str(peak_name).strip())
    if not m:
        return None
    lattice = m.group(1).lower()
    hkl = tuple(sorted((int(m.group(2)), int(m.group(3)), int(m.group(4))), reverse=True))
    h, k, l = hkl
    if hkl == (0, 0, 0):
        return None
    if lattice == "fcc":
        if not (h % 2 == k % 2 == l % 2):
            return None
        phase = "gamma"
    else:  # bcc / bct (pseudo-cubic average of the tetragonal doublet)
        if (h + k + l) % 2 != 0:
            return None
        phase = "alpha_prime"
        lattice = "bcc"
    sq = h * h + k * k + l * l
    return {
        "key": f"{lattice}{h}{k}{l}",
        "phase": phase,
        "hkl": hkl,
        "h2k2l2": sq,
        "multiplicity": multiplicity(hkl),
        "H2": (h * h * k * k + k * k * l * l + l * l * h * h) / float(sq * sq),
        "component": m.group(5),
    }


def canonical_peak_key(peak_name: str) -> Optional[str]:
    info = parse_peak_name(peak_name)
    return info["key"] if info else None


def multiplicity(hkl: Tuple[int, int, int]) -> int:
    """Number of distinct {hkl} planes in the cubic system (sign and permutation equivalents)."""
    seen = set()
    for perm in permutations(hkl):
        for signs in product((1, -1), repeat=3):
            seen.add(tuple(s * v for s, v in zip(signs, perm)))
    return len(seen)


def atomic_scattering_factor(s_inv_A: float, x_ni: float = DEFAULT_X_NI) -> float:
    """Composition-weighted Cromer-Mann f(s) of the Fe-Ni matrix, s = sin(theta)/lambda in A^-1."""
    def _f(el: str) -> float:
        a, b, c = _CROMER_MANN[el]
        return sum(ai * math.exp(-bi * s_inv_A ** 2) for ai, bi in zip(a, b)) + c
    return (1.0 - x_ni) * _f("Fe") + x_ni * _f("Ni")


def lorentz_polarization_factor(two_theta_deg: float) -> float:
    th = math.radians(two_theta_deg / 2.0)
    return (1.0 + math.cos(2.0 * th) ** 2) / (math.sin(th) ** 2 * math.cos(th))


def bragg_two_theta(hkl: Tuple[int, int, int], a_nm: float, wavelength_nm: float) -> float:
    d = a_nm / math.sqrt(sum(v * v for v in hkl))
    return 2.0 * math.degrees(math.asin(min(0.999999, wavelength_nm / (2.0 * d))))


def theoretical_R_factor(
    peak_name: str,
    wavelength_nm: float,
    a_nm: float,
    b_iso_A2: float = DEFAULT_B_ISO_A2,
    x_ni: float = DEFAULT_X_NI,
) -> float:
    """R_hkl = p |F|^2 LP exp(-2B s^2) / V^2 (V in nm^3) at the Bragg angle of the given lattice parameter."""
    info = parse_peak_name(peak_name)
    if info is None:
        raise ValueError(f"Unknown reflection: {peak_name}")
    hkl = info["hkl"]
    two_th = bragg_two_theta(hkl, a_nm, wavelength_nm)
    d_A = 10.0 * a_nm / math.sqrt(info["h2k2l2"])
    s = 1.0 / (2.0 * d_A)
    f = atomic_scattering_factor(s, x_ni)
    n_atoms = 4 if info["phase"] == "gamma" else 2
    f_sq = (n_atoms * f) ** 2
    dw = math.exp(-2.0 * b_iso_A2 * s * s)
    return info["multiplicity"] * f_sq * lorentz_polarization_factor(two_th) * dw / (a_nm ** 3) ** 2


def _olson_cohen_kinetics(x: np.ndarray, fs: float, beta: float, x0: float, n: float) -> np.ndarray:
    """Empirical JMAK/Avrami-type curve in frame number (not the strain-based Olson-Cohen equation)."""
    dx = np.maximum(0.0, x - x0)
    return fs * (1.0 - np.exp(-beta * (dx ** n)))


PREEXISTING_ALPHA_ENGINES = {"2PeaksRatio", "3PeaksLuders"}


def infer_alpha_onset(groups: Dict[str, Any]) -> int:
    """DIMT onset stored with the fitted groups (smallest one), or 0 if unknown."""
    onsets = [int(rec["dimt_onset_num"]) for rec in groups.values() if rec.get("dimt_onset_num")]
    return min(onsets) if onsets else 0


def merge_groups_into_dataframe(groups: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str]]:
    """Merge all fitted groups on `num` (the first group wins for identical column names)."""
    dfs: List[pd.DataFrame] = []
    detected: List[str] = []
    for grec in groups.values():
        rows = grec.get("rows", [])
        if not rows:
            continue
        df_g = pd.DataFrame(rows)
        if "num" not in df_g.columns:
            continue
        df_g["num"] = df_g["num"].astype(int)
        dfs.append(df_g.sort_values("num").drop_duplicates(subset=["num"], keep="last"))
        for pk in grec.get("peaks", []):
            if pk not in detected:
                detected.append(pk)
    if not dfs:
        return pd.DataFrame(), []
    merged = dfs[0]
    for df_next in dfs[1:]:
        overlap = [c for c in df_next.columns if c in merged.columns and c != "num"]
        merged = pd.merge(merged, df_next.drop(columns=overlap), on="num", how="outer")
    return merged.sort_values("num").reset_index(drop=True), detected


def load_groups_from_output_excel(excel_path: str | Path) -> Dict[str, Any]:
    """Read an existing `*output.xlsx` workbook and reconstruct the `groups` structure."""
    path = Path(excel_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Output Excel file not found: {path}")
    xl = pd.ExcelFile(path, engine="openpyxl")
    groups: Dict[str, Any] = {}
    for sheet in xl.sheet_names:
        if sheet.lower() in ("physical_analysis", "summary"):
            continue
        df = pd.read_excel(xl, sheet_name=sheet)
        if "num" not in df.columns:
            continue
        df = df.dropna(subset=["num"]).copy()
        df["num"] = df["num"].astype(int)
        peaks_in_sheet = [str(c).replace("2th_", "", 1) for c in df.columns if str(c).startswith("2th_")]
        if not peaks_in_sheet:
            continue
        groups[sheet] = {"group_id": sheet, "sheet_name": sheet, "peaks": peaks_in_sheet, "rows": df.to_dict(orient="records")}
    return groups


def _num(v: Any) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return float("nan")
    return f


def _select(key: str, raw: str, include: Optional[set], exclude: set) -> bool:
    if key in exclude or raw in exclude:
        return False
    if include is None:
        return True
    return key in include or raw in include


def compute_physical_analysis(
    groups: Dict[str, Any],
    wavelength_nm: Optional[float] = None,
    instrumental_fwhm_deg: float = 0.018,
    a_gamma0_nm: float = DEFAULT_A_GAMMA_NM,
    a_alpha0_nm: float = DEFAULT_A_ALPHA_NM,
    include_peaks: Optional[List[str]] = None,
    exclude_peaks: Optional[List[str]] = None,
    b_iso_A2: float = DEFAULT_B_ISO_A2,
    x_ni: float = DEFAULT_X_NI,
    wilkens_M: float = 1.0,
    kinetics_max_num: Optional[int] = None,
    zero_alpha_before_num: Optional[int] = None,
) -> Dict[str, Any]:
    """Martensite fraction, lattice parameters/strains and dislocation densities per frame.

    `zero_alpha_before_num`: alpha' reflections of newly forming martensite are counted as I = 0 for
    `num < zero_alpha_before_num` (DIMT onset). Harada's single-peak and multi-peak scripts still fit
    noise there (amplitude bounded but not zero), which otherwise produces a spurious f_alpha'.
    Groups fitted with 2PeaksRatio / 3PeaksLuders (pre-existing martensite of cold-rolled specimens)
    are never zeroed. `None` = take the onset stored with the groups; `0` = disabled.
    """
    lam = float(wavelength_nm) if (wavelength_nm and wavelength_nm > 0) else DEFAULT_WAVELENGTH_NM
    wavelength_source = "user" if (wavelength_nm and wavelength_nm > 0) else "default"
    include = {canonical_peak_key(p) or p for p in include_peaks} | set(include_peaks) if include_peaks else None
    exclude = ({canonical_peak_key(p) or p for p in exclude_peaks} | set(exclude_peaks)) if exclude_peaks else set()

    if zero_alpha_before_num is None:
        zero_alpha_before_num = infer_alpha_onset(groups)
    zero_before = int(zero_alpha_before_num or 0)

    # ---- collect per-group, per-reflection data -------------------------------------------------
    raw_peaks: List[Tuple[str, Dict[str, Any], str]] = []  # (raw name, info, group id)
    group_frames: List[Tuple[str, pd.DataFrame, List[str]]] = []
    preexisting_groups = {str(g) for g, rec in groups.items() if str(rec.get("engine", "")) in PREEXISTING_ALPHA_ENGINES}
    for gid, grec in groups.items():
        rows = grec.get("rows", [])
        if not rows:
            continue
        df = pd.DataFrame(rows)
        if "num" not in df.columns:
            continue
        df["num"] = df["num"].astype(int)
        df = df.sort_values("num").drop_duplicates(subset=["num"], keep="last").set_index("num")
        peaks = [p for p in grec.get("peaks", []) if f"I_{p}" in df.columns]
        group_frames.append((str(gid), df, peaks))
        for p in peaks:
            info = parse_peak_name(p)
            if info and all(p != rp for rp, _, _ in raw_peaks):
                raw_peaks.append((p, info, str(gid)))
    if not group_frames:
        raise ValueError("解析対象となるフィッティング結果データがありません。")

    nums = sorted({int(n) for _, df, _ in group_frames for n in df.index})
    n_rows = len(nums)

    def series(df: pd.DataFrame, col: str) -> pd.Series:
        return pd.to_numeric(df[col], errors="coerce").reindex(nums) if col in df.columns else pd.Series(np.nan, index=nums)

    # Canonical reflection intensities: sum of components within a group; first group wins across groups
    refl_I: Dict[str, pd.Series] = {}
    refl_meta: Dict[str, Dict[str, Any]] = {}
    refl_source: Dict[str, str] = {}
    for gid, df, peaks in group_frames:
        per_key: Dict[str, pd.Series] = {}
        for p in peaks:
            info = parse_peak_name(p)
            if info is None or not _select(info["key"], p, include, exclude):
                continue
            s_I = series(df, f"I_{p}").clip(lower=0.0)
            if info["phase"] == "alpha_prime" and zero_before > 0 and gid not in preexisting_groups:
                s_I = s_I.where(~((s_I.index < zero_before) & s_I.notna()), 0.0)
            per_key[info["key"]] = s_I if info["key"] not in per_key else per_key[info["key"]].add(s_I, fill_value=0.0)
            refl_meta[info["key"]] = info
        for key, s in per_key.items():
            if key not in refl_I:
                refl_I[key] = s
                refl_source[key] = gid
            else:
                refl_I[key] = refl_I[key].combine_first(s)

    # ---- lattice parameters (for V and Bragg angles) --------------------------------------------
    def lattice_param(two_th: float, info: Dict[str, Any]) -> float:
        d = lam / (2.0 * math.sin(math.radians(two_th / 2.0)))
        return d * math.sqrt(info["h2k2l2"])

    a_by_phase: Dict[str, List[List[float]]] = {"gamma": [[] for _ in nums], "alpha_prime": [[] for _ in nums]}
    peak_series: Dict[str, Dict[str, pd.Series]] = {}
    for p, info, gid in raw_peaks:
        df = next(d for g, d, _ in group_frames if g == gid)
        s2 = series(df, f"2th_{p}")
        sI = series(df, f"I_{p}")
        peak_series[p] = {"2th": s2, "I": sI, "wG": series(df, f"wG_{p}"), "wL": series(df, f"wL_{p}"), "FWHM": series(df, f"FWHM_{p}")}
        i_max = float(np.nanmax(sI.values)) if np.any(np.isfinite(sI.values)) else 0.0
        for idx, n in enumerate(nums):
            t, i_val = s2.loc[n], sI.loc[n]
            if np.isfinite(t) and t > 5.0 and np.isfinite(i_val) and i_val > max(1.0, 0.03 * i_max):
                a_by_phase[info["phase"]][idx].append(lattice_param(float(t), info))

    def phase_median(phase: str, fallback: float) -> float:
        vals = [v for frame in a_by_phase[phase] for v in frame]
        return float(np.median(vals)) if vals else fallback

    a_gamma_med = phase_median("gamma", a_gamma0_nm)
    a_alpha_med = phase_median("alpha_prime", a_alpha0_nm)

    R_values: Dict[str, float] = {}
    for key, info in refl_meta.items():
        a_nm = a_gamma_med if info["phase"] == "gamma" else a_alpha_med
        R_values[key] = theoretical_R_factor(key, lam, a_nm, b_iso_A2, x_ni)
    # Normalise for readability (gamma 200 = 1000 if present)
    r_norm = R_values.get("fcc200") or (max(R_values.values()) if R_values else 1.0)
    R_scaled = {k: 1000.0 * v / r_norm for k, v in R_values.items()}

    gamma_keys = sorted(k for k, m in refl_meta.items() if m["phase"] == "gamma")
    alpha_keys = sorted(k for k, m in refl_meta.items() if m["phase"] == "alpha_prime")

    f_alpha_list: List[Optional[float]] = []
    f_gamma_list: List[Optional[float]] = []
    ir_by_key: Dict[str, List[Optional[float]]] = {k: [] for k in gamma_keys + alpha_keys}
    for n in nums:
        terms: Dict[str, List[float]] = {"gamma": [], "alpha_prime": []}
        for key in gamma_keys + alpha_keys:
            val = refl_I[key].loc[n]
            if np.isfinite(val):
                ir = float(val) / R_scaled[key]
                terms[refl_meta[key]["phase"]].append(ir)
                ir_by_key[key].append(round(ir, 6))
            else:
                ir_by_key[key].append(None)
        if terms["gamma"] and terms["alpha_prime"]:
            vg, va = float(np.mean(terms["gamma"])), float(np.mean(terms["alpha_prime"]))
            if vg + va > 0:
                fa = va / (vg + va)
                f_alpha_list.append(round(fa, 5))
                f_gamma_list.append(round(1.0 - fa, 5))
                continue
        f_alpha_list.append(None)
        f_gamma_list.append(None)

    # ---- lattice strain & dislocation density per peak -----------------------------------------
    M2 = float(wilkens_M) ** 2
    b_vec = {"gamma": a_gamma_med / math.sqrt(2.0), "alpha_prime": math.sqrt(3.0) / 2.0 * a_alpha_med}
    wG_inst = float(instrumental_fwhm_deg)

    lattice_strains_by_peak: Dict[str, List[Optional[float]]] = {}
    dislocation_by_peak: Dict[str, List[Optional[float]]] = {}
    wh_points: List[Dict[str, List[Tuple[str, float, float]]]] = [{"gamma": [], "alpha_prime": []} for _ in nums]

    for p, info, _gid in raw_peaks:
        ps = peak_series[p]
        sI = ps["I"]
        i_max = float(np.nanmax(sI.values)) if np.any(np.isfinite(sI.values)) else 0.0
        valid = [(n, float(ps["2th"].loc[n])) for n in nums
                 if np.isfinite(ps["2th"].loc[n]) and ps["2th"].loc[n] > 5.0 and np.isfinite(sI.loc[n]) and sI.loc[n] > max(1.0, 0.03 * i_max)]
        ref_2th = float(np.median([t for _, t in valid[:5]])) if valid else bragg_two_theta(info["hkl"], a_gamma_med if info["phase"] == "gamma" else a_alpha_med, lam)
        d0 = lam / (2.0 * math.sin(math.radians(ref_2th / 2.0)))
        C_h00, q = _CONTRAST[info["phase"]]
        C_bar = max(1e-3, C_h00 * (1.0 - q * info["H2"]))
        strains: List[Optional[float]] = []
        rhos: List[Optional[float]] = []
        valid_nums = {n for n, _ in valid}
        for idx, n in enumerate(nums):
            if n not in valid_nums:
                strains.append(None)
                rhos.append(None)
                continue
            t = float(ps["2th"].loc[n])
            th = math.radians(t / 2.0)
            d = lam / (2.0 * math.sin(th))
            strains.append(round((d - d0) / d0 * 1e6, 2))
            wG, wL = float(ps["wG"].loc[n]), float(ps["wL"].loc[n])
            if not (np.isfinite(wG) and np.isfinite(wL)):
                rhos.append(None)
                continue
            wG_phys = math.sqrt(max(0.0, wG * wG - wG_inst * wG_inst))
            fwhm_phys = 0.5346 * wL + math.sqrt(0.2166 * wL * wL + wG_phys * wG_phys)
            K = 2.0 * math.sin(th) / lam
            dK = math.cos(th) * math.radians(fwhm_phys) / lam
            x_wh = K * math.sqrt(C_bar)
            wh_points[idx][info["phase"]].append((p, x_wh, dK))
            # Per-peak upper bound (size broadening neglected)
            rho = 2.0 * (dK / x_wh) ** 2 / (math.pi * M2 * b_vec[info["phase"]] ** 2) * 1e18
            rhos.append(round(rho, 3))
        lattice_strains_by_peak[p] = strains
        dislocation_by_peak[p] = rhos

    rho_phase: Dict[str, List[Optional[float]]] = {"gamma": [], "alpha_prime": []}
    eps_phase: Dict[str, List[Optional[float]]] = {"gamma": [], "alpha_prime": []}
    for idx in range(n_rows):
        for phase in ("gamma", "alpha_prime"):
            pts = wh_points[idx][phase]
            xs = np.array([x for _, x, _ in pts])
            ys = np.array([y for _, _, y in pts])
            rho_val = None
            eps_val = None
            if len(pts) >= 2 and np.ptp(xs) > 1e-9:
                slope, _intercept = np.polyfit(xs, ys, 1)
                if slope > 0:
                    rho_val = round(2.0 * slope ** 2 / (math.pi * M2 * b_vec[phase] ** 2) * 1e18, 3)
                    # mWH slope / 2 corresponds to the apparent microstrain of the classical W-H plot (%)
                    eps_val = round(float(slope) / 2.0 * 100.0, 5)
            rho_phase[phase].append(rho_val)
            eps_phase[phase].append(eps_val)

    a_gamma_list = [round(float(np.mean(v)), 6) if v else None for v in a_by_phase["gamma"]]
    a_alpha_list = [round(float(np.mean(v)), 6) if v else None for v in a_by_phase["alpha_prime"]]

    wh_snapshots: Dict[str, Any] = {}
    valid_idx = [i for i in range(n_rows) if wh_points[i]["gamma"] or wh_points[i]["alpha_prime"]]
    for i in ([valid_idx[0], valid_idx[len(valid_idx) // 2], valid_idx[-1]] if valid_idx else []):
        wh_snapshots[str(nums[i])] = {
            "num": nums[i],
            "gamma": [{"peak": p, "K_C": round(x, 4), "dK": round(y, 6)} for p, x, y in wh_points[i]["gamma"]],
            "alpha_prime": [{"peak": p, "K_C": round(x, 4), "dK": round(y, 6)} for p, x, y in wh_points[i]["alpha_prime"]],
        }

    # ---- empirical kinetics curve f(num) ---------------------------------------------------------
    kinetics_fit: Optional[Dict[str, Any]] = None
    try:
        pts = [(n, f) for n, f in zip(nums, f_alpha_list) if f is not None and (kinetics_max_num is None or n <= kinetics_max_num)]
        if len(pts) >= 6:
            x_arr = np.array([p[0] for p in pts], dtype=float)
            y_arr = np.array([p[1] for p in pts], dtype=float)
            if np.max(y_arr) > 0.03:
                onset_guess = float(x_arr[np.argmax(y_arr > 0.02)]) if np.any(y_arr > 0.02) else float(x_arr[0])
                p0 = [min(1.0, float(np.max(y_arr)) * 1.05), 0.002, onset_guess, 1.5]
                bounds = ([0.01, 1e-8, float(x_arr[0]), 0.3], [1.0, 10.0, float(x_arr[-1]), 6.0])
                popt, _ = curve_fit(_olson_cohen_kinetics, x_arr, y_arr, p0=p0, bounds=bounds, maxfev=10000)
                curve = _olson_cohen_kinetics(np.array(nums, dtype=float), *popt)
                kinetics_fit = {
                    "model": "f = fs [1 - exp(-beta (num - num0)^n)] (empirical, frame-number based)",
                    "fs": round(float(popt[0]), 4),
                    "beta": float(popt[1]),
                    "onset_num": round(float(popt[2]), 1),
                    "n": round(float(popt[3]), 3),
                    "fitted_curve": [round(float(v), 5) for v in curve],
                }
    except Exception:
        kinetics_fit = None

    summary_rows: List[Dict[str, Any]] = []
    for i, n in enumerate(nums):
        r: Dict[str, Any] = {
            "num": n,
            "f_gamma": f_gamma_list[i],
            "f_alpha_prime": f_alpha_list[i],
            "rho_gamma_m2": rho_phase["gamma"][i],
            "rho_alpha_prime_m2": rho_phase["alpha_prime"][i],
            "a_gamma_nm": a_gamma_list[i],
            "a_alpha_prime_nm": a_alpha_list[i],
        }
        for key in gamma_keys + alpha_keys:
            r[f"IR_{key}"] = ir_by_key[key][i]
        for p in lattice_strains_by_peak:
            r[f"strain_{p}_ue"] = lattice_strains_by_peak[p][i]
            r[f"rho_{p}_m2"] = dislocation_by_peak[p][i]
        summary_rows.append(r)

    return {
        "wavelength_nm": round(lam, 6),
        "wavelength_source": wavelength_source,
        "zero_alpha_before_num": zero_before,
        "energy_kev": round(1.23984193 / lam, 3),
        "gamma_peaks": gamma_keys,
        "alpha_prime_peaks": alpha_keys,
        "available_reflections": sorted({info["key"] for _p, info, _g in raw_peaks}),
        "excluded_reflections": sorted(
            {info["key"] for _p, info, _g in raw_peaks} - set(gamma_keys) - set(alpha_keys)
        ),
        "reflection_sources": refl_source,
        "R_values": {k: round(v, 3) for k, v in R_scaled.items()},
        "a_gamma_median_nm": round(a_gamma_med, 6),
        "a_alpha_prime_median_nm": round(a_alpha_med, 6),
        "nums": nums,
        "f_gamma": f_gamma_list,
        "f_alpha_prime": f_alpha_list,
        "kinetics_fit": kinetics_fit,
        "rho_gamma_m2": rho_phase["gamma"],
        "rho_alpha_prime_m2": rho_phase["alpha_prime"],
        "microstrain_gamma_pct": eps_phase["gamma"],
        "microstrain_alpha_prime_pct": eps_phase["alpha_prime"],
        "a_gamma_nm": a_gamma_list,
        "a_alpha_prime_nm": a_alpha_list,
        "lattice_strains_ue": lattice_strains_by_peak,
        "dislocation_by_peak_m2": dislocation_by_peak,
        "williamson_hall_snapshots": wh_snapshots,
        "summary_rows": summary_rows,
    }
