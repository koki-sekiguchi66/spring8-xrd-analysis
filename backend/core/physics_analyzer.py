# -*- coding: utf-8 -*-
"""Physical Metallurgy Analysis Engine from XRD Voigt Fitting Output (`physics_analyzer.py`).

Computes from fitted peak parameters `[num, 2th_{peak}, I_{peak}, wG_{peak}, wL_{peak}, FWHM_{peak}]`:
1. Martensite Volume Fraction (f_alpha') & Austenite Volume Fraction (f_gamma) via Direct Comparison Method
   with theoretical crystallographic intensity factors R_hkl and Olson-Cohen / Burke-Matsumura kinetics fit.
2. Dislocation Density Evolution (rho_gamma, rho_alpha') [m^-2] for each phase via Modified Williamson-Hall
   and Williamson-Smallman microstrain equations with cubic dislocation contrast factors C_hkl.
3. Lattice Parameter (a_gamma, a_alpha') [nm] and Elastic Lattice Strain (epsilon_hkl) [microstrain].
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit


# Crystallographic metadata for γ-FCC (Austenite) and α'-BCC (Martensite) reflections
CRYSTAL_REFLECTIONS: Dict[str, Dict[str, Any]] = {
    "fcc111": {
        "phase": "gamma",
        "hkl": (1, 1, 1),
        "h2k2l2": 3,
        "multiplicity": 8,
        "H2": 1.0 / 3.0,  # (1+1+1)/9 = 1/3
        "default_2th": 11.41,
    },
    "fcc200": {
        "phase": "gamma",
        "hkl": (2, 0, 0),
        "h2k2l2": 4,
        "multiplicity": 6,
        "H2": 0.0,
        "default_2th": 13.19,
    },
    "fcc220": {
        "phase": "gamma",
        "hkl": (2, 2, 0),
        "h2k2l2": 8,
        "multiplicity": 12,
        "H2": 0.25,
        "default_2th": 18.69,
    },
    "fcc311": {
        "phase": "gamma",
        "hkl": (3, 1, 1),
        "h2k2l2": 11,
        "multiplicity": 24,
        "H2": 19.0 / 121.0,
        "default_2th": 21.95,
    },
    "fcc222": {
        "phase": "gamma",
        "hkl": (2, 2, 2),
        "h2k2l2": 12,
        "multiplicity": 8,
        "H2": 1.0 / 3.0,
        "default_2th": 22.95,
    },
    "bcc110": {
        "phase": "alpha_prime",
        "hkl": (1, 1, 0),
        "h2k2l2": 2,
        "multiplicity": 12,
        "H2": 0.25,
        "default_2th": 11.53,
    },
    "bcc200": {
        "phase": "alpha_prime",
        "hkl": (2, 0, 0),
        "h2k2l2": 4,
        "multiplicity": 6,
        "H2": 0.0,
        "default_2th": 16.33,
    },
    "bcc211": {
        "phase": "alpha_prime",
        "hkl": (2, 1, 1),
        "h2k2l2": 6,
        "multiplicity": 24,
        "H2": 0.25,
        "default_2th": 20.03,
    },
    "bcc220": {
        "phase": "alpha_prime",
        "hkl": (2, 2, 0),
        "h2k2l2": 8,
        "multiplicity": 12,
        "H2": 0.25,
        "default_2th": 23.16,
    },
}


def canonical_peak_key(peak_name: str) -> Optional[str]:
    """Normalize peak name (e.g. 'bcc110_2' or 'fcc111') to a canonical key in CRYSTAL_REFLECTIONS."""
    clean = peak_name.strip().lower()
    for key in CRYSTAL_REFLECTIONS:
        if clean.startswith(key):
            return key
    return None


def lorentz_polarization_factor(two_theta_deg: float) -> float:
    """Compute synchrotron transmission XRD Lorentz-Polarization factor LP(theta)."""
    theta_rad = math.radians(max(1.0, min(89.0, two_theta_deg)) / 2.0)
    two_theta_rad = math.radians(max(2.0, min(178.0, two_theta_deg)))
    denom = (math.sin(theta_rad) ** 2) * math.cos(theta_rad)
    if denom <= 1e-12:
        return 1.0
    return (1.0 + math.cos(two_theta_rad) ** 2) / denom


def atomic_scattering_approx(sin_theta_over_lambda_nm_inv: float) -> float:
    """Approximate atomic scattering factor f(s) for Fe-Ni-C alloy (s = sin(theta)/lambda in nm^-1)."""
    # s in A^-1 is 0.1 * sin_theta_over_lambda_nm_inv
    s_ang = 0.1 * sin_theta_over_lambda_nm_inv
    # Analytic Cromer-Mann style Gaussian decay for Fe (Z=26)
    return 26.0 * math.exp(-3.5 * (s_ang ** 2))


def theoretical_R_factor(
    peak_key: str,
    two_theta_deg: float,
    wavelength_nm: float,
    a_gamma_nm: float = 0.3595,
    a_alpha_nm: float = 0.2868,
) -> float:
    """Calculate theoretical relative intensity factor R_hkl for Direct Comparison Method."""
    meta = CRYSTAL_REFLECTIONS.get(peak_key)
    if not meta:
        return 1.0

    phase = meta["phase"]
    mult = float(meta["multiplicity"])
    lp = lorentz_polarization_factor(two_theta_deg)
    theta_rad = math.radians(two_theta_deg / 2.0)
    s_nm_inv = math.sin(theta_rad) / max(1e-5, wavelength_nm)
    f_atom = atomic_scattering_approx(s_nm_inv)

    # Debye-Waller factor exp(-2M) with B_iso ~ 0.0045 nm^2
    dw = math.exp(-2.0 * 0.0045 * (s_nm_inv ** 2))

    if phase == "gamma":
        # FCC has 4 atoms per unit cell: |F|^2 = 16 * f^2, V_c = a_gamma^3
        v_cell = a_gamma_nm ** 3
        struct_sq = 16.0 * (f_atom ** 2)
    else:
        # BCC has 2 atoms per unit cell: |F|^2 = 4 * f^2, V_c = a_alpha^3
        v_cell = a_alpha_nm ** 3
        struct_sq = 4.0 * (f_atom ** 2)

    return (mult * struct_sq * lp * dw) / max(1e-12, v_cell ** 2)


def calibrate_wavelength_nm(
    merged_df: pd.DataFrame,
    a_gamma0_nm: float = 0.3595,
) -> float:
    """Estimate synchrotron X-ray wavelength (nm) from initial γ-FCC peak positions."""
    # Check fcc200 or fcc111 in the earliest rows
    for pk, h2k2l2 in [("fcc200", 4), ("fcc111", 3), ("fcc220", 8)]:
        col = f"2th_{pk}"
        if col in merged_df.columns:
            valid = merged_df[col].dropna()
            valid = valid[valid > 5.0]
            if not valid.empty:
                two_th0 = float(valid.iloc[:5].median())
                d_hkl = a_gamma0_nm / math.sqrt(h2k2l2)
                lam = 2.0 * d_hkl * math.sin(math.radians(two_th0 / 2.0))
                if 0.015 <= lam <= 0.25:
                    return lam
    # Default SPring-8 30 keV high-energy XRD wavelength (~0.04127 nm)
    return 0.04127


def _olson_cohen_kinetics(x: np.ndarray, fs: float, beta: float, x0: float, n: float) -> np.ndarray:
    dx = np.maximum(0.0, x - x0)
    return fs * (1.0 - np.exp(-beta * (dx ** n)))


def merge_groups_into_dataframe(groups: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str]]:
    """Merge all fitted peak groups on `num` into a single DataFrame."""
    dfs: List[pd.DataFrame] = []
    detected_peaks: List[str] = []

    for gid, grec in groups.items():
        rows = grec.get("rows", [])
        if not rows:
            continue
        df_g = pd.DataFrame(rows)
        if "num" not in df_g.columns:
            continue
        df_g["num"] = df_g["num"].astype(int)
        df_g = df_g.sort_values("num").drop_duplicates(subset=["num"], keep="last")
        dfs.append(df_g)
        for pk in grec.get("peaks", []):
            if pk not in detected_peaks:
                detected_peaks.append(pk)

    if not dfs:
        return pd.DataFrame(), []

    merged = dfs[0]
    for df_next in dfs[1:]:
        overlap_cols = [c for c in df_next.columns if c in merged.columns and c != "num"]
        df_clean = df_next.drop(columns=overlap_cols) if overlap_cols else df_next
        merged = pd.merge(merged, df_clean, on="num", how="outer")

    merged = merged.sort_values("num").reset_index(drop=True)
    return merged, detected_peaks


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
        peaks_in_sheet: List[str] = []
        for col in df.columns:
            if str(col).startswith("2th_"):
                pk = str(col).replace("2th_", "", 1)
                peaks_in_sheet.append(pk)
        if not peaks_in_sheet:
            continue
        groups[sheet] = {
            "group_id": sheet,
            "sheet_name": sheet,
            "peaks": peaks_in_sheet,
            "rows": df.to_dict(orient="records"),
        }
    return groups


def compute_physical_analysis(
    groups: Dict[str, Any],
    wavelength_nm: Optional[float] = None,
    instrumental_fwhm_deg: float = 0.018,
    a_gamma0_nm: float = 0.3595,
    a_alpha0_nm: float = 0.2868,
) -> Dict[str, Any]:
    """Compute Martensite phase fraction, Dislocation density per phase, Lattice constants, and Strains."""
    merged, raw_peaks = merge_groups_into_dataframe(groups)
    if merged.empty:
        raise ValueError("解析対象となるフィッティング結果データがありません。")

    lam_nm = wavelength_nm if (wavelength_nm and wavelength_nm > 0) else calibrate_wavelength_nm(merged, a_gamma0_nm)
    energy_kev = 1.23984193 / lam_nm

    nums = merged["num"].astype(int).tolist()
    n_rows = len(nums)

    # Identify canonical peaks present in columns
    gamma_peaks: List[Tuple[str, str]] = []  # (raw_peak_name, canonical_key)
    alpha_peaks: List[Tuple[str, str]] = []

    for col in merged.columns:
        if col.startswith("2th_"):
            raw_pk = col.replace("2th_", "", 1)
            ckey = canonical_peak_key(raw_pk)
            if ckey:
                phase = CRYSTAL_REFLECTIONS[ckey]["phase"]
                if phase == "gamma":
                    gamma_peaks.append((raw_pk, ckey))
                else:
                    alpha_peaks.append((raw_pk, ckey))

    # 1. Reference initial 2theta_0 for each peak (average of first 5 valid frames where intensity > 0)
    ref_2th0: Dict[str, float] = {}
    ref_fwhm0: Dict[str, float] = {}
    for raw_pk, ckey in gamma_peaks + alpha_peaks:
        col_2th = f"2th_{raw_pk}"
        col_I = f"I_{raw_pk}"
        col_fwhm = f"FWHM_{raw_pk}"
        if col_2th in merged.columns:
            s_2th = pd.to_numeric(merged[col_2th], errors="coerce")
            s_I = pd.to_numeric(merged.get(col_I, pd.Series(np.ones(n_rows))), errors="coerce").fillna(0.0)
            max_I = float(s_I.max()) if len(s_I) > 0 else 0.0
            valid_mask = (s_2th > 5.0) & (s_I > max(1.0, 0.03 * max_I))
            valid_2th = s_2th[valid_mask]
            if not valid_2th.empty:
                ref_2th0[raw_pk] = float(valid_2th.iloc[:5].median())
            else:
                ref_2th0[raw_pk] = CRYSTAL_REFLECTIONS[ckey]["default_2th"]
        if col_fwhm in merged.columns:
            s_fw = pd.to_numeric(merged[col_fwhm], errors="coerce")
            valid_fw = s_fw[(s_fw > 0.005) & (s_fw < 0.5)]
            if not valid_fw.empty:
                # Instrumental width baseline is minimum of configured or 85% of earliest clean width
                ref_fwhm0[raw_pk] = min(instrumental_fwhm_deg, float(valid_fw.iloc[:5].min()) * 0.85)
            else:
                ref_fwhm0[raw_pk] = instrumental_fwhm_deg

    # Burgers vectors (nm) & dislocation contrast constants
    b_gamma_nm = a_gamma0_nm / math.sqrt(2.0)  # ~0.2542 nm
    b_alpha_nm = (math.sqrt(3.0) / 2.0) * a_alpha0_nm  # ~0.2484 nm
    C_h00_gamma, q_gamma = 0.30, 2.2
    C_h00_alpha, q_alpha = 0.285, 1.8

    f_alpha_list: List[float] = []
    f_gamma_list: List[float] = []
    rho_gamma_list: List[Optional[float]] = []
    rho_alpha_list: List[Optional[float]] = []
    a_gamma_list: List[Optional[float]] = []
    a_alpha_list: List[Optional[float]] = []
    microstrain_gamma_list: List[Optional[float]] = []
    microstrain_alpha_list: List[Optional[float]] = []

    lattice_strains_by_peak: Dict[str, List[Optional[float]]] = {
        raw_pk: [] for raw_pk, _ in (gamma_peaks + alpha_peaks)
    }
    dislocation_by_peak: Dict[str, List[Optional[float]]] = {
        raw_pk: [] for raw_pk, _ in (gamma_peaks + alpha_peaks)
    }

    # Representative Williamson-Hall snapshot data (for early, mid, late frames)
    wh_snapshots: Dict[str, Any] = {}
    snapshot_targets = [
        nums[0],
        nums[len(nums) // 2],
        nums[-1],
    ]

    for row_idx, row in merged.iterrows():
        num_val = int(row["num"])

        # --- A. Martensite & Austenite Phase Fraction (Direct Comparison Method) ---
        v_gamma_terms: List[float] = []
        v_alpha_terms: List[float] = []

        for raw_pk, ckey in gamma_peaks:
            val_I = float(row.get(f"I_{raw_pk}", 0.0) or 0.0)
            val_2th = float(row.get(f"2th_{raw_pk}", 0.0) or ref_2th0.get(raw_pk, 12.0))
            if val_I > 0 and val_2th > 5.0:
                R_val = theoretical_R_factor(ckey, val_2th, lam_nm, a_gamma0_nm, a_alpha0_nm)
                v_gamma_terms.append(val_I / R_val)

        for raw_pk, ckey in alpha_peaks:
            val_I = float(row.get(f"I_{raw_pk}", 0.0) or 0.0)
            val_2th = float(row.get(f"2th_{raw_pk}", 0.0) or ref_2th0.get(raw_pk, 12.0))
            if val_I > 0 and val_2th > 5.0:
                R_val = theoretical_R_factor(ckey, val_2th, lam_nm, a_gamma0_nm, a_alpha0_nm)
                v_alpha_terms.append(val_I / R_val)

        mean_v_gamma = float(np.mean(v_gamma_terms)) if v_gamma_terms else 0.0
        mean_v_alpha = float(np.mean(v_alpha_terms)) if v_alpha_terms else 0.0

        if mean_v_gamma + mean_v_alpha > 1e-12:
            if alpha_peaks:
                f_a = mean_v_alpha / (mean_v_gamma + mean_v_alpha)
            else:
                # If only γ-FCC peak(s) were fitted, estimate transformed fraction from normalized γ intensity drop
                f_a = 0.0
            f_a = float(np.clip(f_a, 0.0, 1.0))
            f_g = 1.0 - f_a
        else:
            f_a = 0.0
            f_g = 1.0

        f_alpha_list.append(round(f_a, 5))
        f_gamma_list.append(round(f_g, 5))

        # --- B. Lattice Constants, Elastic Lattice Strains & Dislocation Density ---
        a_g_vals: List[float] = []
        a_a_vals: List[float] = []
        rho_g_peaks: List[float] = []
        rho_a_peaks: List[float] = []
        eps_g_peaks: List[float] = []
        eps_a_peaks: List[float] = []

        wh_pts_gamma: List[Dict[str, float]] = []
        wh_pts_alpha: List[Dict[str, float]] = []

        for raw_pk, ckey in gamma_peaks + alpha_peaks:
            meta = CRYSTAL_REFLECTIONS[ckey]
            phase = meta["phase"]
            h2k2l2 = meta["h2k2l2"]
            H2 = meta["H2"]

            val_2th = float(row.get(f"2th_{raw_pk}", np.nan))
            val_I = float(row.get(f"I_{raw_pk}", 0.0) or 0.0)
            val_fwhm = float(row.get(f"FWHM_{raw_pk}", np.nan))
            val_wG = float(row.get(f"wG_{raw_pk}", np.nan))
            val_wL = float(row.get(f"wL_{raw_pk}", np.nan))

            if np.isnan(val_2th) or val_2th <= 5.0 or val_I <= 1.0:
                lattice_strains_by_peak[raw_pk].append(None)
                dislocation_by_peak[raw_pk].append(None)
                continue

            theta_rad = math.radians(val_2th / 2.0)
            d_nm = lam_nm / (2.0 * math.sin(theta_rad))
            a_nm = d_nm * math.sqrt(h2k2l2)

            if phase == "gamma":
                a_g_vals.append(a_nm)
            else:
                a_a_vals.append(a_nm)

            # Elastic lattice strain relative to initial undeformed 2theta_0 (in microstrain 10^-6)
            two_th0 = ref_2th0.get(raw_pk, val_2th)
            d0_nm = lam_nm / (2.0 * math.sin(math.radians(two_th0 / 2.0)))
            lattice_strain_ue = ((d_nm - d0_nm) / d0_nm) * 1e6
            lattice_strains_by_peak[raw_pk].append(round(lattice_strain_ue, 2))

            # Dislocation density from physical line broadening
            if not np.isnan(val_fwhm) and val_fwhm > 0.002:
                fwhm_inst = ref_fwhm0.get(raw_pk, instrumental_fwhm_deg)
                # Deconvolve instrumental broadening (halagham / Voigt-like geometric subtraction)
                beta_phys_deg = math.sqrt(max(1e-6, (val_fwhm ** 2) - (fwhm_inst ** 2)))
                beta_rad = math.radians(beta_phys_deg)

                K_nm_inv = (2.0 * math.sin(theta_rad)) / lam_nm
                dK_nm_inv = (math.cos(theta_rad) * beta_rad) / lam_nm

                if phase == "gamma":
                    C_bar = C_h00_gamma * (1.0 - q_gamma * H2)
                    b_nm = b_gamma_nm
                else:
                    C_bar = C_h00_alpha * (1.0 - q_alpha * H2)
                    b_nm = b_alpha_nm

                C_bar = max(0.05, C_bar)
                # Effective microstrain e_rms corrected by contrast factor C_bar
                # dK = K * sqrt(C_bar) * e_disl + dK_size
                # Subtract baseline size broadening (~0.9 / 250 nm)
                dK_net = max(1e-5, dK_nm_inv - (0.9 / 300.0))
                e_disl = dK_net / max(1e-4, K_nm_inv * math.sqrt(C_bar))

                # Williamson-Smallman / Ungár relation: rho = (2 * e_disl^2) / (b^2)
                # Convert nm^-2 to m^-2 (1 nm^-2 = 10^18 m^-2)
                rho_m2 = (2.0 * (e_disl ** 2) / (b_nm ** 2)) * 1e18
                rho_m2 = float(np.clip(rho_m2, 1e12, 5e16))
                dislocation_by_peak[raw_pk].append(round(rho_m2, 3))

                if phase == "gamma":
                    rho_g_peaks.append(rho_m2)
                    eps_g_peaks.append(e_disl * 100.0)
                    wh_pts_gamma.append({
                        "peak": raw_pk,
                        "K_C": round(K_nm_inv * math.sqrt(C_bar), 4),
                        "dK": round(dK_nm_inv, 5),
                    })
                else:
                    rho_a_peaks.append(rho_m2)
                    eps_a_peaks.append(e_disl * 100.0)
                    wh_pts_alpha.append({
                        "peak": raw_pk,
                        "K_C": round(K_nm_inv * math.sqrt(C_bar), 4),
                        "dK": round(dK_nm_inv, 5),
                    })
            else:
                dislocation_by_peak[raw_pk].append(None)

        a_gamma_list.append(round(float(np.mean(a_g_vals)), 5) if a_g_vals else None)
        a_alpha_list.append(round(float(np.mean(a_a_vals)), 5) if a_a_vals else None)
        rho_gamma_list.append(round(float(np.mean(rho_g_peaks)), 3) if rho_g_peaks else None)
        rho_alpha_list.append(round(float(np.mean(rho_a_peaks)), 3) if rho_a_peaks else None)
        microstrain_gamma_list.append(round(float(np.mean(eps_g_peaks)), 4) if eps_g_peaks else None)
        microstrain_alpha_list.append(round(float(np.mean(eps_a_peaks)), 4) if eps_a_peaks else None)

        if num_val in snapshot_targets:
            wh_snapshots[str(num_val)] = {
                "num": num_val,
                "gamma": wh_pts_gamma,
                "alpha_prime": wh_pts_alpha,
            }

    # Fallback: If only γ-FCC peaks were analyzed (no α' peaks selected), estimate f_alpha from γ intensity reduction
    if not alpha_peaks and gamma_peaks:
        raw_pk0 = gamma_peaks[0][0]
        s_I0 = pd.to_numeric(merged[f"I_{raw_pk0}"], errors="coerce").fillna(0.0).values
        init_I = float(np.median(s_I0[:5])) if len(s_I0) >= 5 else float(np.max(s_I0))
        if init_I > 0:
            f_alpha_list = [round(float(np.clip(1.0 - (val / init_I), 0.0, 1.0)), 5) for val in s_I0]
            f_gamma_list = [round(1.0 - fa, 5) for fa in f_alpha_list]

    # Fit Olson-Cohen / Burke-Matsumura Kinetics Model to f_alpha_list
    kinetics_fit: Optional[Dict[str, Any]] = None
    try:
        x_arr = np.array(nums, dtype=float)
        y_arr = np.array(f_alpha_list, dtype=float)
        if np.max(y_arr) > 0.03 and len(x_arr) >= 6:
            onset_guess = float(x_arr[np.argmax(y_arr > 0.02)]) if np.any(y_arr > 0.02) else float(x_arr[0])
            p0 = [min(1.0, float(np.max(y_arr)) * 1.05), 0.002, onset_guess, 1.5]
            bounds = ([0.05, 1e-6, float(x_arr[0]), 0.5], [1.0, 5.0, float(x_arr[-1]), 5.0])
            popt, _ = curve_fit(_olson_cohen_kinetics, x_arr, y_arr, p0=p0, bounds=bounds, maxfev=5000)
            y_pred = _olson_cohen_kinetics(x_arr, *popt)
            kinetics_fit = {
                "fs": round(float(popt[0]), 4),
                "beta": float(popt[1]),
                "onset_num": round(float(popt[2]), 1),
                "n": round(float(popt[3]), 3),
                "fitted_curve": [round(float(v), 5) for v in y_pred],
            }
    except Exception:
        kinetics_fit = None

    # Build summary table rows for export & UI
    summary_rows: List[Dict[str, Any]] = []
    for i, num_val in enumerate(nums):
        r_dict: Dict[str, Any] = {
            "num": num_val,
            "f_gamma": f_gamma_list[i],
            "f_alpha_prime": f_alpha_list[i],
            "rho_gamma_m2": rho_gamma_list[i],
            "rho_alpha_prime_m2": rho_alpha_list[i],
            "a_gamma_nm": a_gamma_list[i],
            "a_alpha_prime_nm": a_alpha_list[i],
        }
        for raw_pk in lattice_strains_by_peak:
            r_dict[f"strain_{raw_pk}_ue"] = lattice_strains_by_peak[raw_pk][i]
            r_dict[f"rho_{raw_pk}_m2"] = dislocation_by_peak[raw_pk][i]
        summary_rows.append(r_dict)

    return {
        "wavelength_nm": round(lam_nm, 6),
        "energy_kev": round(energy_kev, 2),
        "gamma_peaks": [p[0] for p in gamma_peaks],
        "alpha_prime_peaks": [p[0] for p in alpha_peaks],
        "nums": nums,
        "f_gamma": f_gamma_list,
        "f_alpha_prime": f_alpha_list,
        "kinetics_fit": kinetics_fit,
        "rho_gamma_m2": rho_gamma_list,
        "rho_alpha_prime_m2": rho_alpha_list,
        "microstrain_gamma_pct": microstrain_gamma_list,
        "microstrain_alpha_prime_pct": microstrain_alpha_list,
        "a_gamma_nm": a_gamma_list,
        "a_alpha_prime_nm": a_alpha_list,
        "lattice_strains_ue": lattice_strains_by_peak,
        "dislocation_by_peak_m2": dislocation_by_peak,
        "williamson_hall_snapshots": wh_snapshots,
        "summary_rows": summary_rows,
    }
