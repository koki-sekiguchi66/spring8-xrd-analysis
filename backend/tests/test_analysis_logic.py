# -*- coding: utf-8 -*-
"""Analysis-logic tests on synthetic in-situ XRD data with a known answer (no sample_data required).

Covers the Harada-faithful fitting engines and the direct-comparison phase fraction:
- Origin <-> lmfit width conversions and the Olivero-Longbothum FWHM
- no local background term in the continuous fitters (broad alpha' areas are not truncated)
- MultiPeaks newly forming peak before the onset (amplitude restarts from 0, bounded by +10)
- 2PeaksRatio: only num <= onset, fixed ratio, pre-onset initial file required
- R values (Cromer-Mann), peak-name parsing, component summation, onset zeroing, no fallback
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
from lmfit.lineshapes import voigt

from backend.core.fitters import MultiPeakFitter, Ratio2Fitter, SinglePeakFitter
from backend.core.origin_voigt import calc_origin_fwhm, gamma_to_wL, sigma_to_wG, wG_to_sigma, wL_to_gamma
from backend.core.physics_analyzer import compute_physical_analysis, parse_peak_name, theoretical_R_factor

LAM = 0.04133
A_G, A_A = 0.3588, 0.2905


def _tt(a: float, hkl) -> float:
    d = a / math.sqrt(sum(v * v for v in hkl))
    return 2.0 * math.degrees(math.asin(LAM / (2.0 * d)))


def _profile(x, area, center, fwhm):
    """Voigt with wG = 0.6 FWHM-ish Gaussian part and wL = 0.45 FWHM-ish Lorentzian part."""
    return area * voigt(x, 1.0, center, 0.6 * fwhm / 2.3548, 0.45 * fwhm / 2.0)


@pytest.fixture(scope="module")
def synthetic_dir(tmp_path_factory) -> Path:
    """60 frames: gamma 111/200, alpha' 110/211 forming from num 25 (f -> 0.5)."""
    root = tmp_path_factory.mktemp("synthetic") / "bcg_removed_arpls"
    root.mkdir(parents=True)
    rng = np.random.default_rng(3)
    x = np.arange(10.6, 21.0, 0.0046)
    for num in range(1, 61):
        f = 0.0 if num < 25 else 0.5 * (num - 25) / 35.0
        y = _profile(x, (1 - f) * 600 * 2.074, _tt(A_G, (1, 1, 1)), 0.035)
        y += _profile(x, (1 - f) * 600, _tt(A_G, (2, 0, 0)), 0.040)
        if f > 0:
            y += _profile(x, f * 600 * 2.6926, _tt(A_A, (1, 1, 0)), 0.27)
            y += _profile(x, f * 600 * 0.8193, _tt(A_A, (2, 1, 1)), 0.47)
        y += rng.normal(0.0, 2.0, x.size)
        np.savetxt(root / f"syn_{num:04d}bcg.csv", np.c_[x, y], delimiter=",", fmt="%.5f")
    return root


def _truth_f(num: int) -> float:
    return 0.0 if num < 25 else 0.5 * (num - 25) / 35.0


def test_origin_width_conversions():
    assert math.isclose(sigma_to_wG(1.0), 2.0 * math.sqrt(2.0 * math.log(2.0)))
    assert math.isclose(wG_to_sigma(sigma_to_wG(0.013)), 0.013)
    assert math.isclose(gamma_to_wL(0.02), 0.04) and math.isclose(wL_to_gamma(0.04), 0.02)
    assert math.isclose(calc_origin_fwhm(0.0, 0.1), 0.1, rel_tol=2e-3)  # pure Lorentzian
    assert math.isclose(calc_origin_fwhm(0.1, 0.0), 0.1, rel_tol=1e-9)  # pure Gaussian


def test_peak_name_parsing_and_R_values():
    assert parse_peak_name("bcc112")["key"] == "bcc211"
    assert parse_peak_name("bcc101")["key"] == "bcc110"
    assert parse_peak_name("bcc1102")["key"] == "bcc110"
    assert parse_peak_name("fcc111a")["key"] == "fcc111"
    assert parse_peak_name("bcc321")["multiplicity"] == 48
    assert parse_peak_name("fcc210") is None and parse_peak_name("bcc111") is None
    # Direct-comparison R relative to gamma 200 (Fe Cromer-Mann, B = 0.35 A^2, LP, |F|^2, 1/V^2)
    ref = {"fcc111": 2.0740, "fcc220": 0.5987, "fcc311": 0.6382, "bcc110": 2.6926, "bcc211": 0.8193, "bcc321": 0.2663}
    r200 = theoretical_R_factor("fcc200", LAM, A_G, x_ni=0.0)
    for key, val in ref.items():
        a = A_G if key.startswith("fcc") else A_A
        assert math.isclose(theoretical_R_factor(key, LAM, a, x_ni=0.0) / r200, val, rel_tol=1e-3)


def test_single_peak_broad_alpha_area_not_truncated(synthetic_dir: Path):
    """No edge-based background subtraction: the broad alpha' 211 area is recovered."""
    c211 = _tt(A_A, (2, 1, 1))
    fitter = SinglePeakFitter(
        bcg_dir=synthetic_dir,
        peak="bcc211",
        init_params={"num": 55, "v1_center": c211, "v1_amplitude": 280.0, "v1_wG": 0.6 * 0.47, "v1_wL": 0.45 * 0.47},
        th_min=c211 - 0.7,
        th_max=c211 + 0.7,
    )
    rows = {r["num"]: r for r in fitter.run_all()["rows"]}
    for num in (40, 50, 60):
        true_area = _truth_f(num) * 600 * 0.8193
        assert abs(rows[num]["I_bcc211"] / true_area - 1.0) < 0.05


def test_multipeak_newly_forming_peak_before_onset(synthetic_dir: Path):
    c111, c110 = _tt(A_G, (1, 1, 1)), _tt(A_A, (1, 1, 0))
    fitter = MultiPeakFitter(
        bcg_dir=synthetic_dir,
        peaks=["fcc111", "bcc110"],
        init_params={
            "num": 55,
            "v1_center": c111, "v1_amplitude": (1 - _truth_f(55)) * 600 * 2.074, "v1_wG": 0.021, "v1_wL": 0.016,
            "v2_center": c110, "v2_amplitude": _truth_f(55) * 600 * 2.6926, "v2_wG": 0.162, "v2_wL": 0.061,
        },
        th_min=10.9,
        th_max=12.1,
        dimt_onset_num=25,
        newly_forms_peak=[1],
    )
    rows = {r["num"]: r for r in fitter.run_all()["rows"]}
    assert all(rows[n]["I_bcc110"] <= 10.0 + 1e-6 for n in rows if n < 25)
    assert abs(rows[55]["I_fcc111"] / ((1 - _truth_f(55)) * 600 * 2.074) - 1.0) < 0.03


def test_ratio2_only_pre_onset_with_fixed_ratio(synthetic_dir: Path):
    c111, c110 = _tt(A_G, (1, 1, 1)), _tt(A_A, (1, 1, 0))
    init = {
        "num": 5,
        "v1_center": c111, "v1_amplitude": 1240.0, "v1_wG": 0.021, "v1_wL": 0.016,
        "v2_center": c110, "v2_amplitude": 60.0, "v2_wG": 0.16, "v2_wL": 0.06,
    }
    fitter = Ratio2Fitter(synthetic_dir, ["fcc111", "bcc110"], init, th_min=10.9, th_max=12.1, dimt_onset_num=20, num_init_val_set=2)
    res = fitter.run_all()
    df = res["dataframe"]
    assert df["num"].max() <= 20 and len(df) == 20
    assert np.allclose(df["I_bcc110"] / df["I_fcc111"], res["best_R"], rtol=1e-4)

    late = dict(init, num=50)
    with pytest.raises(ValueError):
        Ratio2Fitter(synthetic_dir, ["fcc111", "bcc110"], late, th_min=10.9, th_max=12.1, dimt_onset_num=20).run_all()


def _rows(nums, **cols):
    return [{"num": n, **{k: v[i] for k, v in cols.items()}} for i, n in enumerate(nums)]


def test_phase_fraction_components_onset_and_no_fallback():
    nums = list(range(1, 11))
    t200, t211, t110 = _tt(A_G, (2, 0, 0)), _tt(A_A, (2, 1, 1)), _tt(A_A, (1, 1, 0))
    f = [0.0] * 4 + [0.1 * k for k in range(1, 7)]
    g200 = {"peaks": ["fcc200"], "rows": _rows(nums, **{"2th_fcc200": [t200] * 10, "I_fcc200": [600 * (1 - v) for v in f], "wG_fcc200": [0.02] * 10, "wL_fcc200": [0.01] * 10, "FWHM_fcc200": [0.025] * 10})}
    # alpha' 211 fitted with noise (5) before the onset, as Harada's single-peak script does
    a211 = {"peaks": ["bcc112"], "engine": "1Peak", "dimt_onset_num": 5,
            "rows": _rows(nums, **{"2th_bcc112": [t211] * 10, "I_bcc112": [5.0 if v == 0 else 600 * 0.8193 * v for v in f], "wG_bcc112": [0.3] * 10, "wL_bcc112": [0.2] * 10, "FWHM_bcc112": [0.4] * 10})}
    ph = compute_physical_analysis({"fcc200": g200, "bcc112": a211}, wavelength_nm=LAM)
    assert ph["alpha_prime_peaks"] == ["bcc211"]  # legacy name recognised
    assert ph["zero_alpha_before_num"] == 5
    assert all(v == 0.0 for v in ph["f_alpha_prime"][:4])
    for got, want in zip(ph["f_alpha_prime"][4:], f[4:]):
        assert abs(got - want) < 0.01
    assert abs(ph["a_gamma_median_nm"] - A_G) < 1e-4  # measured with the given wavelength, not assumed

    # Two components of the same reflection in one group are summed (pre-existing + new alpha' 110)
    comp = {"peaks": ["fcc111a", "bcc110a", "bcc1102"], "engine": "3PeaksLuders",
            "rows": _rows(nums, **{"2th_fcc111a": [_tt(A_G, (1, 1, 1))] * 10, "I_fcc111a": [600 * 2.074 * 0.5] * 10,
                                    "2th_bcc110a": [t110] * 10, "I_bcc110a": [600 * 2.6926 * 0.2] * 10,
                                    "2th_bcc1102": [t110 + 0.03] * 10, "I_bcc1102": [600 * 2.6926 * 0.3] * 10})}
    ph2 = compute_physical_analysis({"L": comp}, wavelength_nm=LAM, a_gamma0_nm=A_G, a_alpha0_nm=A_A)
    assert all(abs(v - 0.5) < 0.01 for v in ph2["f_alpha_prime"])

    # Only gamma peaks -> no fraction (no estimate from the gamma intensity drop)
    ph3 = compute_physical_analysis({"fcc200": g200}, wavelength_nm=LAM)
    assert all(v is None for v in ph3["f_alpha_prime"])
