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


def test_harada_excel_R_values_reproduced():
    """B = 0 and reference lattice parameters reproduce the 850C Excel R values within 1 %."""
    sheet = {"fcc111": 2138.527, "bcc110": 2863.059, "fcc200": 1047.960, "fcc220": 666.669, "bcc211": 948.347, "fcc311": 741.349}
    nums = [1, 2]
    pos = {"fcc111": 11.45, "fcc200": 13.23, "fcc220": 18.73, "fcc311": 22.0, "bcc110": 11.55, "bcc211": 20.07}
    rows = _rows(nums, **{f"2th_{k}": [v] * 2 for k, v in pos.items()}, **{f"I_{k}": [100.0] * 2 for k in pos})
    ph = compute_physical_analysis(
        {"g": {"peaks": list(pos), "rows": rows}},
        wavelength_nm=LAM, b_iso_A2=0.0, r_lattice="reference", a_gamma0_nm=0.3586, a_alpha0_nm=0.2872,
    )
    for key, val in sheet.items():
        assert abs(ph["R_values"][key] / 1000.0 / (val / sheet["fcc200"]) - 1.0) < 0.01


def test_initial_workbook_reader_origin_layout(tmp_path: Path):
    """Origin/Harada `_initial.xlsx`: blocks of 6 columns per peak, numbers sometimes stored as text."""
    import openpyxl

    from backend.core.excel_io import read_initial_workbook

    wb = openpyxl.Workbook()
    ws = wb.active
    sub = ["No"] + ["y0", "xc", "A", "wG", "wL", "FWHM"] * 2
    ws.append([None, "fcc200", None, None, None, None, None, "fcc220"])
    ws.append(sub)
    ws.append([50, 0, 13.2121, 619.15551, 0.01883, 0.01121, 0.02553, 0, 18.73103, 207.51799, 0.01731, 0.01637, 0.02767])
    ws.append([])
    ws.append([None, "bcc112", None, None, None, None, None, "bcc101"])
    ws.append(sub)
    ws.append([900, 30.18, 20.02136, 352.6381, 0.32335, 0.23503, 0.467, 0, 11.51084, 5151.37853, 0.23864, "3.91E-20", 0.23864])
    path = tmp_path / "x_initial.xlsx"
    wb.save(path)

    data = read_initial_workbook(path)
    assert set(data) == {"fcc200", "fcc220", "bcc112", "bcc101"}
    assert data["fcc200"][0]["No"] == 50 and data["bcc112"][0]["No"] == 900
    assert math.isclose(data["bcc101"][0]["wL"], 3.91e-20)
    assert math.isclose(data["bcc112"][0]["y0"], 30.18)


def test_custom_group_spec():
    from backend.core.origin_voigt import make_custom_group_spec

    spec = make_custom_group_spec(["fcc311", "fcc220", "bcc211", "fcc222"])
    assert spec["peaks"] == ["fcc220", "bcc211", "fcc311", "fcc222"]
    assert spec["default_engine"] == "MultiPeaks" and spec["category"] == "multi_pair"
    assert spec["range_min"] < 18.73 and spec["range_max"] > 22.95
    assert make_custom_group_spec(["bcc321"])["default_engine"] == "1Peak"
    with pytest.raises(ValueError):
        make_custom_group_spec(["bcc999"])


def test_ratio2_uses_initial_set_candidates(synthetic_dir: Path):
    init = {
        "num": 5,
        "v1_center": _tt(A_G, (1, 1, 1)), "v1_amplitude": 1240.0, "v1_wG": 0.021, "v1_wL": 0.016,
        "v2_center": _tt(A_A, (1, 1, 0)), "v2_amplitude": 60.0, "v2_wG": 0.16, "v2_wL": 0.06,
    }
    fitter = Ratio2Fitter(synthetic_dir, ["fcc111", "bcc110"], init, dimt_onset_num=20, num_init_val_set=3, r_candidates=[0.05, 0.04, 0.06, 0.07])
    assert fitter.r_candidates == [0.05, 0.04, 0.06]


def test_optional_y0_background_removes_offset_bias(tmp_path: Path):
    """A residual constant background is absorbed by the broad peak without y0 and removed with it."""
    root = tmp_path / "bcg_removed_arpls"
    root.mkdir()
    rng = np.random.default_rng(7)
    x = np.arange(19.0, 21.2, 0.0046)
    c211 = _tt(A_A, (2, 1, 1))
    for num in range(1, 11):
        y = _profile(x, 300.0, c211, 0.47) + 20.0 + rng.normal(0.0, 1.0, x.size)
        np.savetxt(root / f"off_{num:04d}bcg.csv", np.c_[x, y], delimiter=",", fmt="%.5f")
    kw = dict(
        bcg_dir=root,
        peak="bcc211",
        init_params={"num": 5, "v1_center": c211, "v1_amplitude": 300.0, "v1_wG": 0.28, "v1_wL": 0.21},
        th_min=c211 - 0.7,
        th_max=c211 + 0.7,
    )
    plain = SinglePeakFitter(**kw).run_all()["dataframe"]
    with_y0 = SinglePeakFitter(**kw, fit_y0=True, y0_init=15.0).run_all()["dataframe"]
    assert "y0" not in plain.columns and list(with_y0.columns[-2:]) == ["y0", "residual"]
    assert plain["I_bcc211"].median() > 1.10 * 300.0  # bias of the no-background model (Harada)
    assert abs(with_y0["I_bcc211"].median() / 300.0 - 1.0) < 0.05
    assert abs(with_y0["y0"].median() - 20.0) < 3.0


def test_engine_repair_reproduces_run(synthetic_dir: Path):
    """Step 4 engine repair seeded from the neighbouring frame gives the same result as the run."""
    c200 = _tt(A_G, (2, 0, 0))
    kw = dict(
        bcg_dir=synthetic_dir,
        peak="fcc200",
        init_params={"num": 10, "v1_center": c200, "v1_amplitude": 600.0, "v1_wG": 0.024, "v1_wL": 0.018},
        th_min=c200 - 0.4,
        th_max=c200 + 0.4,
    )
    rows = {r["num"]: r for r in SinglePeakFitter(**kw).run_all()["rows"]}
    fitter = SinglePeakFitter(**kw)
    idx = [n for n, _ in fitter.files].index(30)
    fitter.seed_from_row(rows[29], neighbor_index=idx - 1)
    rep = fitter.refit_frame(idx).row_data
    assert abs(rep["I_fcc200"] / rows[30]["I_fcc200"] - 1.0) < 1e-3
    assert abs(rep["2th_fcc200"] - rows[30]["2th_fcc200"]) < 1e-4


def test_fracture_detection_and_analysis_range():
    from backend.core.physics_analyzer import infer_fracture_num

    nums = list(range(1, 41))
    t200 = _tt(A_G, (2, 0, 0))
    I = [600.0 if n < 33 else 80.0 for n in nums]
    g = {"fcc200": {"peaks": ["fcc200"], "rows": _rows(nums, **{"2th_fcc200": [t200] * 40, "I_fcc200": I, "wG_fcc200": [0.02] * 40, "wL_fcc200": [0.01] * 40, "FWHM_fcc200": [0.025] * 40})}}
    assert infer_fracture_num(g) == 33
    ph = compute_physical_analysis(g, wavelength_nm=LAM, max_num=32)
    assert ph["nums"][-1] == 32 and ph["fracture_num_estimate"] == 33


def test_cold_rolled_groups_disable_pre_onset_zeroing_and_luders_init():
    from backend.api.routes_fitting import GroupBatchConfig, _luders_init_params
    from backend.core.physics_analyzer import infer_alpha_onset

    assert infer_alpha_onset({"a": {"engine": "1Peak", "dimt_onset_num": 50}}) == 50
    assert infer_alpha_onset({"a": {"engine": "1Peak", "dimt_onset_num": 50}, "b": {"engine": "2PeaksRatio", "dimt_onset_num": 50}}) == 0
    cfg = GroupBatchConfig(group_id="L", engine="3PeaksLuders", peaks=["fcc111a", "bcc110a", "bcc1102"], init_num=200, init_peaks=[], R=0.3)
    p = _luders_init_params(cfg, {"num": 200, "v1_center": 11.2, "v1_amplitude": 1000.0, "v1_sigma": 0.01, "v1_gamma": 0.01,
                                  "v2_center": 11.45, "v2_amplitude": 900.0, "v2_sigma": 0.1, "v2_gamma": 0.1})
    assert p["v2_amplitude"] == pytest.approx(300.0) and p["v3_amplitude"] == pytest.approx(600.0)
    assert p["v2_center"] < p["v3_center"] < cfg.v3_center_cap


def test_initial_excel_blocks_roundtrip(tmp_path: Path):
    """Step 2 writes one block per group and frame; Step 3 reads them back (2-peak blocks carry R sets)."""
    from backend.core.excel_io import append_initial_block, read_initial_blocks, save_initial_excel

    pk = lambda n, xc, A: {"peak_name": n, "y0": 0.0, "xc": xc, "A": A, "wG": 0.02, "wL": 0.01}
    path = save_initial_excel(tmp_path, "s", [], group_blocks=[
        {"No": 10, "peaks": [pk("fcc111", 11.2, 1000.0), pk("bcc110", 11.45, 300.0)], "ratio_rows": True},
        {"No": 10, "peaks": [pk("fcc200", 12.9, 600.0)], "ratio_rows": False},
        {"No": 280, "peaks": [pk("fcc111", 11.2, 700.0), pk("bcc110", 11.45, 900.0)], "ratio_rows": True},
    ])
    blocks = read_initial_blocks(path)
    assert [(b["peaks"], b["rows"][0]["No"], len(b["rows"])) for b in blocks] == [
        (["fcc111", "bcc110"], 10, 5), (["fcc200"], 10, 1), (["fcc111", "bcc110"], 280, 5)]
    r = [row["entries"]["bcc110"]["A"] / row["entries"]["fcc111"]["A"] for row in blocks[0]["rows"]]
    assert r == pytest.approx([0.3, 0.27, 0.285, 0.315, 0.33])
    lud = [pk("fcc111a", 11.2, 700.0), pk("bcc110a", 11.45, 300.0), pk("bcc1102", 11.5, 600.0)]
    assert append_initial_block(path, lud, 280)["appended"] is True
    assert append_initial_block(path, lud, 280)["appended"] is False  # existing (possibly hand-edited) block kept
    assert read_initial_blocks(path)[-1]["peaks"] == ["fcc111a", "bcc110a", "bcc1102"]


def test_step2_baseline_modes_origin_peak_analyzer():
    """Peak Analyzer baselines: y0 with peaks recovers the area on an offset; end-point lines cut the tails."""
    from backend.core.origin_voigt import fit_origin_voigt_group, window_end_baseline

    x = np.arange(19.0, 21.2, 0.0046)
    c = _tt(A_A, (2, 1, 1))
    y = _profile(x, 300.0, c, 0.47) + 20.0 + 5.0 * (x - x[0])
    line = window_end_baseline(x, y, "straight_line")
    assert line[0] == pytest.approx(y[0]) and line[-1] == pytest.approx(y[-1])
    epw = window_end_baseline(x, y, "end_points_weighted", 5.0)
    assert np.all(np.isfinite(epw)) and epw.shape == x.shape

    def area(mode, fit_with=False):
        r = fit_origin_voigt_group(x, y, 1, "f", "g", ["bcc211"], c - 0.7, c + 0.7, baseline_mode=mode, fit_baseline_with_peaks=fit_with)
        return r.peaks[0].A, r

    a_const, r_const = area("constant")
    a_line_fit, r_line = area("straight_line", True)
    a_epw, r_epw = area("end_points_weighted")
    a_none, _ = area("none")
    assert abs(a_line_fit / 300.0 - 1.0) < 0.03  # true model (sloped background) fitted with the peak
    assert a_none > 1.15 * 300.0 and a_epw < 0.95 * 300.0  # absorbs the offset / cuts the tails
    assert r_const.baseline_mode == "constant" and r_const.peaks[0].y0 > 10.0
    assert r_epw.peaks[0].y0 == 0.0 and r_epw.baseline is not None
    assert r_line.peaks[0].y0 == pytest.approx(20.0 + 5.0 * (r_line.peaks[0].xc - x[0]), abs=2.0)
