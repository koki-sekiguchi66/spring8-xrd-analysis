# -*- coding: utf-8 -*-
"""Step 2: Unit & Integration Tests for Backend using real SPring-8 XRD data and Unicode DIC video paths."""

from __future__ import annotations

import shutil
from pathlib import Path

import cv2
import numpy as np
import openpyxl
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.core.bg_remover import get_preprocess_preview, run_background_removal_batch
from backend.core.excel_io import (
    build_unified_columns,
    export_fitting_results_excel,
    load_initial_excel,
    save_initial_excel,
)
from backend.core.fitters import Luders3Fitter, MultiPeakFitter, Ratio2Fitter, SinglePeakFitter
from backend.core.origin_voigt import fit_origin_voigt_group, run_initial_auto_detect
from backend.core.physics_analyzer import compute_physical_analysis
from backend.core.separator import separate_directory
from backend.core.utils import extract_file_num
from backend.core.video_exporter import (
    export_videos_in_folder,
    inspect_video_file,
    save_frame_range_sec,
)
from backend.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_XRD_DIR = REPO_ROOT / "sample_data" / "Seki_age_2_tensile"


def _create_synthetic_dic_video(video_path: Path, fps: float = 10.0, duration_sec: float = 3.0) -> None:
    """Create a synthetic speckle-pattern tensile DIC test video (`.mp4` or `.MP4`)."""
    video_path.parent.mkdir(parents=True, exist_ok=True)
    width, height = 320, 240
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height))
    rng = np.random.default_rng(42)
    base_speckle = rng.integers(30, 220, size=(height, width, 3), dtype=np.uint8)
    n_frames = int(fps * duration_sec)
    for idx in range(n_frames):
        frame = base_speckle.copy()
        cv2.putText(
            frame,
            f"t={idx / fps:.1f}s frame={idx}",
            (18, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
        )
        writer.write(frame)
    writer.release()


def test_regex_file_number_extraction():
    """Verify Bug #5 fix: strict regex extraction of file numbers."""
    assert extract_file_num("Seki_age_2_0050.tth") == 50
    assert extract_file_num("Seki_age_2_0050bcg.csv") == 50
    assert extract_file_num("Seki_age_2_0900bcg.csv") == 900
    assert extract_file_num("Seki_age_2_1050.tth") == 1050
    assert extract_file_num("0001bcg.csv") == 1
    assert extract_file_num("Seki_age_2_prm.json") is None


def test_separator_and_bg_removal_on_real_data():
    """Verify Stage 1 (separation without <50 limit + idempotency) and Stage 2 (Spike + Rubberband + PCHIP)."""
    assert SAMPLE_XRD_DIR.exists(), f"Sample data directory missing: {SAMPLE_XRD_DIR}"

    # 1. First separation run
    sep1 = separate_directory(SAMPLE_XRD_DIR)
    assert sep1.total_tth_count >= 200
    assert 50 in sep1.tth_nums
    assert 900 in sep1.tth_nums
    assert (SAMPLE_XRD_DIR / "tth" / "Seki_age_2_0050.tth").exists()
    assert (SAMPLE_XRD_DIR / "others" / "Seki_age_2_prm.json").exists()

    # 2. Second separation run must be idempotent
    sep2 = separate_directory(SAMPLE_XRD_DIR)
    assert sep2.already_separated is True
    assert sep2.moved_tth_count == 0
    assert sep2.total_tth_count == sep1.total_tth_count

    # 3. Run batch background removal
    bg_res = run_background_removal_batch(SAMPLE_XRD_DIR, th_min=10.2)
    assert bg_res["processed_count"] == sep1.total_tth_count
    bcg_0050 = SAMPLE_XRD_DIR / "bcg_removed_arpls" / "Seki_age_2_0050bcg.csv"
    bcg_0900 = SAMPLE_XRD_DIR / "bcg_removed_arpls" / "Seki_age_2_0900bcg.csv"
    assert bcg_0050.exists()
    assert bcg_0900.exists()

    # 4. Preview single file
    preview = get_preprocess_preview(SAMPLE_XRD_DIR, target_num=50, th_min=10.2)
    assert preview["num"] == 50
    assert preview["method_used"] in ("PCHIP", "arPLS")
    assert len(preview["x"]) > 5000
    assert len(preview["monotonic_x"]) >= 2


def test_origin_voigt_initial_detection_and_excel_io(tmp_path: Path):
    """Verify Stage 3: Origin-compatible Voigt fitting (R^2 > 0.99) on 0050 & 0900 and Excel generation."""
    res = run_initial_auto_detect(SAMPLE_XRD_DIR, mode="auto", vary_y0=False)
    assert 50 in res["selected_nums"]
    assert 900 in res["selected_nums"]

    groups_by_id = {g["group_id"]: g for g in res["candidate_groups"]}
    assert "fcc111_bcc110" in groups_by_id
    assert "fcc200" in groups_by_id
    assert "fcc220" in groups_by_id
    assert "bcc211" in groups_by_id
    assert "fcc311" in groups_by_id

    # Verify fcc200 on num=50 achieves R^2 > 0.99 and matches Origin reference (xc ≈ 13.2121, FWHM ≈ 0.0255)
    fit_fcc200_50 = groups_by_id["fcc200"]["fits_by_num"]["50"]
    assert fit_fcc200_50["r_squared"] > 0.99, f"Expected R^2 > 0.99, got {fit_fcc200_50['r_squared']}"
    pk_fcc200 = fit_fcc200_50["peaks"][0]
    assert abs(pk_fcc200["xc"] - 13.2121) < 0.002
    assert abs(pk_fcc200["FWHM"] - 0.02553) < 0.002

    # Verify fcc311 on num=50 achieves R^2 > 0.99
    fit_fcc311_50 = groups_by_id["fcc311"]["fits_by_num"]["50"]
    assert fit_fcc311_50["r_squared"] > 0.99

    # Verify fcc111 + bcc110 pair on num=900 achieves R^2 > 0.99 and matches Origin reference
    fit_pair_900 = groups_by_id["fcc111_bcc110"]["fits_by_num"]["900"]
    assert fit_pair_900["r_squared"] > 0.99, f"Expected R^2 > 0.99, got {fit_pair_900['r_squared']}"
    pk_fcc111 = fit_pair_900["peaks"][0]
    pk_bcc110 = fit_pair_900["peaks"][1]
    assert abs(pk_fcc111["xc"] - 11.3898) < 0.005
    assert abs(pk_bcc110["xc"] - 11.511) < 0.015

    # Save `_initial.xlsx` and reload with `load_initial_excel`
    selected_peaks = [
        pk_fcc200,
        groups_by_id["fcc220"]["fits_by_num"]["50"]["peaks"][0],
        groups_by_id["fcc311"]["fits_by_num"]["50"]["peaks"][0],
        pk_fcc111,
        pk_bcc110,
        groups_by_id["bcc211"]["fits_by_num"]["900"]["peaks"][0],
    ]
    saved_initial = save_initial_excel(tmp_path, "Seki_age_2_test", selected_peaks)
    assert Path(saved_initial).exists()

    init_pars_1, prev_1 = load_initial_excel(saved_initial, ["fcc200"])
    assert init_pars_1["num"] == 50.0
    assert abs(init_pars_1["v1_center"] - pk_fcc200["xc"]) < 1e-4

    init_pars_2, prev_2 = load_initial_excel(saved_initial, ["fcc111", "bcc110"], row_index=1)
    assert init_pars_2["num"] == 900.0
    assert len(prev_2["center"]) == 2


def test_all_four_fitters_and_output_excel(tmp_path: Path):
    """Verify all 4 bug-fixed continuous fitters and unified column ordering in `output.xlsx`."""
    # Create a small 8-file subset of real *bcg.csv files for fast end-to-end testing of all 4 fitters
    sub_bcg = tmp_path / "bcg_removed_arpls"
    sub_bcg.mkdir(parents=True, exist_ok=True)
    src_bcg = SAMPLE_XRD_DIR / "bcg_removed_arpls"
    for num in [25, 50, 100, 200, 400, 600, 800, 900]:
        f = src_bcg / f"Seki_age_2_{num:04d}bcg.csv"
        shutil.copy2(f, sub_bcg / f.name)

    # 1. SinglePeakFitter (Bug #1 fix)
    f1 = SinglePeakFitter(
        bcg_dir=sub_bcg,
        peak="fcc200",
        init_params={
            "num": 50,
            "v1_center": 13.2121,
            "v1_amplitude": 620.0,
            "v1_wG": 0.0188,
            "v1_wL": 0.0112,
        },
    )
    res1 = f1.run_all()
    df1 = res1["dataframe"]
    assert list(df1.columns) == ["num", "2th_fcc200", "I_fcc200", "wG_fcc200", "wL_fcc200", "FWHM_fcc200", "residual"]
    assert len(df1) == 8

    # 2. Ratio2Fitter (2-peak ratio search + unified columns)
    f2 = Ratio2Fitter(
        bcg_dir=sub_bcg,
        peaks=["fcc111", "bcc110"],
        init_params={
            "num": 50,
            "v1_center": 11.3898,
            "v1_amplitude": 21546.0,
            "v1_wG": 0.0373,
            "v1_wL": 0.0309,
            "v2_center": 11.5108,
            "v2_amplitude": 5151.0,
            "v2_wG": 0.2386,
            "v2_wL": 0.0100,
        },
        dimt_onset_num=200,
        num_init_val_set=3,
    )
    # ver10: the 2-peak ratio engine covers only num <= DIMT onset, starting from a pre-onset initial file
    res2 = f2.run_all()
    df2 = res2["dataframe"]
    assert list(df2.columns) == build_unified_columns(["fcc111", "bcc110"])
    assert df2["num"].max() <= 200
    assert len(res2["history_R"]) >= 1
    assert res2["best_R"] > 0
    ratio = df2["I_bcc110"] / df2["I_fcc111"]
    assert np.allclose(ratio, res2["best_R"], rtol=1e-4)

    # 3. Luders3Fitter (Bug #2-1, #2-2, #2-3 fixes + v2_delta breakwater)
    f3 = Luders3Fitter(
        bcg_dir=sub_bcg,
        peaks=["fcc111a", "bcc110a", "bcc1102"],
        init_params={
            "num": 900,
            "v1_center": 11.3898,
            "v1_amplitude": 21546.0,
            "v1_wG": 0.0373,
            "v1_wL": 0.0309,
            "v2_center": 11.5108,
            "v2_amplitude": 4000.0,
            "v2_wG": 0.20,
            "v2_wL": 0.02,
            "v3_center": 11.58,
            "v3_amplitude": 1200.0,
            "v3_wG": 0.22,
            "v3_wL": 0.02,
        },
        dimt_onset_num=200,
        undeform_initial=200,
        undeform_end=400,
    )
    res3 = f3.run_all()
    df3 = res3["dataframe"]
    assert list(df3.columns) == build_unified_columns(["fcc111a", "bcc110a", "bcc1102"])
    # Verify v2_delta >= 0.1 breakwater held for every row
    assert np.all(df3["2th_bcc110a"] - df3["2th_fcc111a"] >= 0.099)

    # 4. MultiPeakFitter (Bug #3 fix: newly_forms_peak list iteration)
    f4 = MultiPeakFitter(
        bcg_dir=sub_bcg,
        peaks=["fcc220", "bcc211"],
        init_params={
            "num": 900,
            "v1_center": 18.67,
            "v1_amplitude": 150.0,
            "v1_wG": 0.03,
            "v1_wL": 0.02,
            "v2_center": 20.02,
            "v2_amplitude": 352.0,
            "v2_wG": 0.32,
            "v2_wL": 0.23,
        },
        th_min=18.2,
        th_max=20.7,
        dimt_onset_num=200,
        newly_forms_peak=[1],
    )
    res4 = f4.run_all()
    df4 = res4["dataframe"]
    assert list(df4.columns) == build_unified_columns(["fcc220", "bcc211"])
    # ver4.0.0: before the DIMT onset the newly forming peak restarts from 0 every frame (bounded to <= 10)
    pre_dimt_rows = df4[df4["num"] < 200]
    assert np.all(pre_dimt_rows["I_bcc211"] <= 10.0 + 1e-6)

    # 5. Export all to `output.xlsx` and verify sheets + embedded chart images
    out_xlsx = tmp_path / "Seki_age_2_testoutput.xlsx"
    exp = export_fitting_results_excel(
        out_xlsx,
        [
            {"sheet_name": "fcc200", "peaks": ["fcc200"], "rows": res1["rows"]},
            {
                "sheet_name": "fcc111bcc110",
                "peaks": ["fcc111", "bcc110"],
                "rows": res2["rows"],
                "best_R": res2["best_R"],
                "history_R": res2["history_R"],
                "history_residual": res2["history_residual"],
            },
        ],
    )
    assert Path(exp["saved_path"]).exists()
    wb = openpyxl.load_workbook(exp["saved_path"])
    assert "fcc200" in wb.sheetnames
    assert "fcc111bcc110" in wb.sheetnames
    assert len(wb["fcc111bcc110"]._images) >= 1


def test_video_exporter_unicode_japanese_paths_and_case_insensitive_mp4(tmp_path: Path):
    """Verify DIC video frame extraction on Japanese folder paths with both `.mp4` and `.MP4`."""
    jp_dir = tmp_path / "日本語フォルダ_DIC試験データ" / "引張試験_01"
    vid1 = jp_dir / "sample_lower.mp4"
    vid2 = jp_dir / "SAMPLE_UPPER.MP4"
    _create_synthetic_dic_video(vid1, fps=10.0, duration_sec=2.5)
    _create_synthetic_dic_video(vid2, fps=10.0, duration_sec=2.5)

    # Also save a persistent sample DIC video in `sample_data/dic_sample/` for the UI
    persistent_dic_dir = REPO_ROOT / "sample_data" / "dic_sample"
    _create_synthetic_dic_video(persistent_dic_dir / "DIC_tensile_sample.mp4", fps=10.0, duration_sec=5.0)
    _create_synthetic_dic_video(persistent_dic_dir / "DIC_tensile_sample_02.MP4", fps=10.0, duration_sec=4.0)

    # 1. Inspect metadata
    meta = inspect_video_file(vid1)
    assert meta.fps == pytest.approx(10.0, rel=0.1)
    assert meta.frame_count == 25
    assert meta.width == 320 and meta.height == 240

    # 2. Single video extraction to Japanese directory
    single_out = jp_dir / "出力画像_単一"
    res_single = save_frame_range_sec(
        video_path=vid1,
        start_sec=0.0,
        stop_sec=2.0,
        step_sec=0.5,
        dir_path=single_out,
        basename="試験片A_img",
        ext="jpg",
    )
    assert res_single["saved_count"] == 4
    for fpath in res_single["saved_files"]:
        assert Path(fpath).exists()
        assert Path(fpath).stat().st_size > 500

    # 3. Folder batch extraction (must detect both .mp4 and .MP4!)
    batch_out = jp_dir / "出力画像_一括"
    res_batch = export_videos_in_folder(
        folder_path=jp_dir,
        start_sec=0.0,
        stop_sec=2.0,
        step_sec=1.0,
        output_root_dir=batch_out,
        basename_suffix="_img",
        ext="png",
    )
    assert res_batch["video_count"] == 2
    assert res_batch["total_saved_frames"] == 4


def test_fastapi_endpoints():
    """Verify FastAPI REST endpoints end-to-end."""
    client = TestClient(app)
    r_health = client.get("/api/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "ok"

    r_samples = client.get("/api/preprocess/sample-paths")
    assert r_samples.status_code == 200
    assert "Seki_age_2_tensile" in r_samples.json()["sample_xrd_folder"]


def test_comparison_with_reference_initial_and_output_old():
    """Verify initial values and continuous fitting against `1100C10min_700C600min_initial-old.xlsx` and `1100C10min_700C600minoutput-old.xlsx`."""
    ref_init_xlsx = SAMPLE_XRD_DIR / "1100C10min_700C600min_initial-old.xlsx"
    ref_out_xlsx = SAMPLE_XRD_DIR / "1100C10min_700C600minoutput-old.xlsx"
    assert ref_init_xlsx.exists()
    assert ref_out_xlsx.exists()

    # 1. Compare Stage 3 auto-detected initial values against 1100C10min_700C600min_initial-old.xlsx
    res_init = run_initial_auto_detect(SAMPLE_XRD_DIR, mode="manual", manual_nums=[50, 900], vary_y0=False)
    groups_by_id = {g["group_id"]: g for g in res_init["candidate_groups"]}

    # Single peaks at num=50 (fcc200, fcc220, fcc311)
    for pk in ["fcc200", "fcc220", "fcc311"]:
        ref_pars, _ = load_initial_excel(ref_init_xlsx, [pk], row_index=1)
        fit_50 = groups_by_id[pk]["fits_by_num"]["50"]["peaks"][0]
        assert abs(fit_50["xc"] - ref_pars["v1_center"]) < 0.001, f"{pk} xc mismatch: {fit_50['xc']} vs {ref_pars['v1_center']}"
        rel_err_A = abs(fit_50["A"] - ref_pars["v1_amplitude"]) / ref_pars["v1_amplitude"]
        assert rel_err_A < 0.02, f"{pk} A relative error too large: {rel_err_A:.4f}"

    # bcc211 (bcc112) and fcc111+bcc110 at num=900
    ref_bcc211, _ = load_initial_excel(ref_init_xlsx, ["bcc211"], row_index=1)
    fit_bcc211_900 = groups_by_id["bcc211"]["fits_by_num"]["900"]["peaks"][0]
    assert abs(fit_bcc211_900["xc"] - ref_bcc211["v1_center"]) < 0.005
    assert abs(fit_bcc211_900["A"] - ref_bcc211["v1_amplitude"]) / ref_bcc211["v1_amplitude"] < 0.03

    ref_pair, _ = load_initial_excel(ref_init_xlsx, ["fcc111", "bcc110"], row_index=1)
    fit_pair_900 = groups_by_id["fcc111_bcc110"]["fits_by_num"]["900"]["peaks"]
    assert abs(fit_pair_900[0]["xc"] - ref_pair["v1_center"]) < 0.005
    assert abs(fit_pair_900[1]["xc"] - ref_pair["v2_center"]) < 0.015
    assert abs(fit_pair_900[0]["A"] - ref_pair["v1_amplitude"]) / ref_pair["v1_amplitude"] < 0.02
    assert abs(fit_pair_900[1]["A"] - ref_pair["v2_amplitude"]) / ref_pair["v2_amplitude"] < 0.03

    # 2. Run continuous fitting via FastAPI /api/fitting/run (which auto-orders bcc211 before fcc111_bcc110)
    # and compare key frames against 1100C10min_700C600minoutput-old.xlsx
    client = TestClient(app)
    batch_payload = {
        "folder_path": str(SAMPLE_XRD_DIR),
        "specimen_name": "Seki_age_2_verify",
        "groups": [
            {
                "group_id": "fcc111_bcc110",
                "engine": "MultiPeaks",
                "peaks": ["fcc111", "bcc110"],
                "init_num": 900,
                "init_peaks": fit_pair_900,
                "th_min": groups_by_id["fcc111_bcc110"]["range_min"],
                "th_max": groups_by_id["fcc111_bcc110"]["range_max"],
                "dimt_onset_num": 200,
                "newly_forms_peak": [1],
            },
            {
                "group_id": "fcc200",
                "engine": "1Peak",
                "peaks": ["fcc200"],
                "init_num": 50,
                "init_peaks": [groups_by_id["fcc200"]["fits_by_num"]["50"]["peaks"][0]],
                "th_min": groups_by_id["fcc200"]["range_min"],
                "th_max": groups_by_id["fcc200"]["range_max"],
                "dimt_onset_num": 200,
            },
            {
                "group_id": "bcc211",
                "engine": "1Peak",
                "peaks": ["bcc211"],
                "init_num": 900,
                "init_peaks": [fit_bcc211_900],
                "th_min": groups_by_id["bcc211"]["range_min"],
                "th_max": groups_by_id["bcc211"]["range_max"],
                "dimt_onset_num": 200,
            },
        ],
    }
    r_run = client.post("/api/fitting/run", json=batch_payload)
    assert r_run.status_code == 200
    run_data = r_run.json()
    out_groups = run_data["groups"]

    # Check fcc200 against 1100C10min_700C600minoutput-old.xlsx
    ref_fcc200_df = pd.read_excel(ref_out_xlsx, sheet_name="fcc200").set_index("num")
    our_fcc200_df = pd.DataFrame(out_groups["fcc200"]["rows"]).set_index("num")
    assert "residual" in our_fcc200_df.columns
    # Verify wL_fcc200 is independently fitted (not fixed to initial value with random noise)
    assert our_fcc200_df["wL_fcc200"].std() > 0.001
    for check_num in [25, 50, 100, 200, 400, 600, 800, 900, 1000]:
        assert abs(our_fcc200_df.loc[check_num, "2th_fcc200"] - ref_fcc200_df.loc[check_num, "2th_fcc200"]) < 0.003
        assert abs(our_fcc200_df.loc[check_num, "FWHM_fcc200"] - ref_fcc200_df.loc[check_num, "FWHM_fcc200"]) < 0.012

    # Check bcc211: Harada's single-peak method has no onset handling; the phase fraction treats
    # newly forming alpha' before the DIMT onset as I = 0
    ref_bcc112_df = pd.read_excel(ref_out_xlsx, sheet_name="bcc112").set_index("num")
    our_bcc211_df = pd.DataFrame(out_groups["bcc211"]["rows"]).set_index("num")
    phys = compute_physical_analysis(out_groups, wavelength_nm=0.04133)
    f_by_num = dict(zip(phys["nums"], phys["f_alpha_prime"]))
    assert all(f_by_num[n] in (0.0, None) for n in f_by_num if n < 200)
    # At num=900 (no local background term, as in Harada's scripts), I_bcc211 and FWHM_bcc211 match reference bcc112
    assert abs(our_bcc211_df.loc[900, "2th_bcc211"] - ref_bcc112_df.loc[900, "2th_bcc112"]) < 0.01
    assert abs(our_bcc211_df.loc[900, "I_bcc211"] - ref_bcc112_df.loc[900, "I_bcc112"]) / ref_bcc112_df.loc[900, "I_bcc112"] < 0.08
    assert abs(our_bcc211_df.loc[900, "FWHM_bcc211"] - ref_bcc112_df.loc[900, "FWHM_bcc112"]) < 0.03

    # Check fcc111_bcc110 (MultiPeaks, newly forming bcc110): bounded to <= 10 before the onset
    ref_pair_df = pd.read_excel(ref_out_xlsx, sheet_name="fcc111bcc101").set_index("num")
    our_pair_df = pd.DataFrame(out_groups["fcc111_bcc110"]["rows"]).set_index("num")
    assert np.all(our_pair_df.loc[our_pair_df.index < 200, "I_bcc110"] <= 10.0 + 1e-6)
    # In transformation regime (e.g. num=600, 800, 900, 1000), 2th and FWHM closely match reference
    for check_num in [600, 800, 900, 1000]:
        assert abs(our_pair_df.loc[check_num, "2th_fcc111"] - ref_pair_df.loc[check_num, "2th_fcc111"]) < 0.01
        assert abs(our_pair_df.loc[check_num, "2th_bcc110"] - ref_pair_df.loc[check_num, "2th_bcc101"]) < 0.04

    # Clean up temporary verification output file if created
    verify_out = SAMPLE_XRD_DIR / "Seki_age_2_verifyoutput.xlsx"
    if verify_out.exists():
        verify_out.unlink()
