# -*- coding: utf-8 -*-
"""Full-stack E2E test verifying FastAPI REST + WebSocket endpoints, DesktopBridge IPC,
batch outlier refitting, and physical metallurgy analysis (Martensite fraction & Dislocation density)."""

from __future__ import annotations

from pathlib import Path
import openpyxl
from fastapi.testclient import TestClient

from backend.main import app
from backend.desktop_bridge import DesktopBridge


def test_spa_and_health_endpoints() -> None:
    client = TestClient(app)
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"

    # Verify built React SPA index.html is served at root
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "XRD AutoFit Studio" in res_root.text


def test_desktop_bridge_zero_localhost_ipc() -> None:
    """Verify DesktopBridge executes API calls in-process without any localhost network server."""
    bridge = DesktopBridge(app)
    health = bridge.api_get("/api/health")
    assert health["status"] == "ok"

    sample_paths = bridge.api_get("/api/preprocess/sample-paths")
    assert Path(sample_paths["sample_xrd_folder"]).exists()
    assert Path(sample_paths["sample_dic_video"]).exists()


def test_full_xrd_and_dic_api_and_websocket_pipeline(tmp_path: Path) -> None:
    client = TestClient(app)

    # 1. Sample paths
    res_paths = client.get("/api/preprocess/sample-paths")
    assert res_paths.status_code == 200
    paths_data = res_paths.json()
    xrd_folder = paths_data["sample_xrd_folder"]
    dic_video = paths_data["sample_dic_video"]
    dic_folder = paths_data["sample_dic_folder"]
    assert Path(xrd_folder).exists()
    assert Path(dic_video).exists()

    # 2. Step 1 Preprocess Run
    res_prep = client.post(
        "/api/preprocess/run",
        json={
            "folder_path": xrd_folder,
            "specimen_name": "Seki_age_2",
            "th_min": 10.2,
            "spike_threshold_factor": 5.0,
            "valley_distance": 100,
            "valley_avg_window": 11,
            "force_recompute": False,
        },
    )
    assert res_prep.status_code == 200
    prep_data = res_prep.json()
    assert prep_data["status"] == "ok"
    assert len(prep_data["nums"]) == 210
    assert len(prep_data["preview"]["x"]) > 500

    # 3. Step 2 Auto-Detect Initial Values across multiple files (50 & 900)
    res_init = client.post(
        "/api/initial/auto-detect",
        json={
            "folder_path": xrd_folder,
            "mode": "auto",
            "vary_y0": False,
        },
    )
    assert res_init.status_code == 200
    init_data = res_init.json()
    assert init_data["early_num"] == 50
    assert init_data["late_num"] == 900
    groups = {g["group_id"]: g for g in init_data["candidate_groups"]}
    assert "fcc200" in groups
    assert "fcc111_bcc110" in groups

    fcc200_fit = groups["fcc200"]["fits_by_num"]["50"]
    assert fcc200_fit["r_squared"] > 0.999

    pair_fit = groups["fcc111_bcc110"]["fits_by_num"]["900"]
    assert pair_fit["r_squared"] > 0.998

    # Save _initial.xlsx via API
    selected_peaks = []
    for p in fcc200_fit["peaks"]:
        selected_peaks.append({**p, "No": 50})
    for p in pair_fit["peaks"]:
        selected_peaks.append({**p, "No": 900})

    res_save_init = client.post(
        "/api/initial/save-excel",
        json={
            "folder_path": xrd_folder,
            "specimen_name": "Seki_age_2_e2e",
            "selected_peaks": selected_peaks,
        },
    )
    assert res_save_init.status_code == 200
    saved_init_path = Path(res_save_init.json()["saved_path"])
    assert saved_init_path.exists()

    # 4. Step 3 WebSocket Continuous Fitting (fcc200 + fcc111_bcc110 pair)
    with client.websocket_connect("/ws/fitting/run") as ws:
        ws.send_json(
            {
                "folder_path": xrd_folder,
                "specimen_name": "Seki_age_2_e2e",
                "groups": [
                    {
                        "group_id": "fcc200",
                        "engine": "1Peak",
                        "peaks": ["fcc200"],
                        "init_num": 50,
                        "init_peaks": fcc200_fit["peaks"],
                        "th_min": 12.95,
                        "th_max": 13.48,
                        "fitting_range_min": -0.7,
                        "fitting_range_max": 0.7,
                        "max_attempts": 1,
                    },
                    {
                        "group_id": "fcc111_bcc110",
                        "engine": "MultiPeaks",
                        "peaks": ["fcc111", "bcc110"],
                        "dimt_onset_num": 200,
                        "newly_forms_peak": [1],
                        "init_num": 900,
                        "init_peaks": pair_fit["peaks"],
                        "th_min": 11.0,
                        "th_max": 12.1,
                        "fitting_range_min": -0.7,
                        "fitting_range_max": 0.7,
                        "max_attempts": 1,
                    },
                ],
            }
        )
        completed_msg = None
        step_count = 0
        while True:
            msg = ws.receive_json()
            if msg["type"] == "step":
                step_count += 1
            elif msg["type"] == "all_complete":
                completed_msg = msg
                break
            elif msg["type"] == "error":
                raise AssertionError(f"WebSocket error: {msg}")

        assert step_count > 0
        assert completed_msg is not None
        assert "fcc200" in completed_msg["groups"]
        assert "fcc111_bcc110" in completed_msg["groups"]
        assert len(completed_msg["groups"]["fcc200"]["rows"]) == 210
        # Verify output.xlsx was automatically saved into the analyzed directory right after Step 3
        auto_saved_out = Path(completed_msg["saved_output_path"])
        assert auto_saved_out.exists()
        assert auto_saved_out.parent == Path(xrd_folder).resolve()

    # 5. Step 4 Inspect single file, Batch Refit across phases, & Export output.xlsx
    res_inspect = client.get("/api/fitting/waveform/fcc200/50")
    assert res_inspect.status_code == 200
    assert res_inspect.json()["num"] == 50

    res_batch_refit = client.post(
        "/api/fitting/refit-batch",
        json={
            "folder_path": str(Path(xrd_folder) / "bcg_removed_arpls"),
            "use_neighbor_interpolation": True,
            "items": [
                {
                    "group_id": "fcc200",
                    "num": 100,
                },
                {
                    "group_id": "fcc111_bcc110",
                    "num": 850,
                },
            ],
        },
    )
    assert res_batch_refit.status_code == 200
    batch_refit_data = res_batch_refit.json()
    assert batch_refit_data["status"] == "ok"
    assert batch_refit_data["repaired_count"] == 2
    assert Path(batch_refit_data["saved_path"]).parent == Path(xrd_folder).resolve()

    res_export = client.post(
        "/api/fitting/export",
        json={
            "folder_path": xrd_folder,
            "specimen_name": "Seki_age_2_e2e",
        },
    )
    assert res_export.status_code == 200
    out_xlsx = Path(res_export.json()["saved_path"])
    assert out_xlsx.exists()
    assert out_xlsx.parent == Path(xrd_folder).resolve()

    # Verify Physical_Analysis sheet is embedded in output.xlsx
    wb = openpyxl.load_workbook(out_xlsx)
    assert "Physical_Analysis" in wb.sheetnames

    # 6. Step 5 Physical Metallurgy Analysis (Martensite Fraction & Dislocation Density)
    res_phys = client.post(
        "/api/fitting/physics-analysis",
        json={
            "excel_path": None,
            "wavelength_nm": 0.04133,
            "a_gamma0_nm": 0.3588,
            "a_alpha0_nm": 0.2905,
            "instrumental_fwhm_deg": 0.018,
        },
    )
    assert res_phys.status_code == 200
    phys_data = res_phys.json()
    assert phys_data["status"] == "ok"
    assert len(phys_data["nums"]) == 210
    assert len(phys_data["f_alpha_prime"]) == 210
    assert max(v for v in phys_data["f_alpha_prime"] if v is not None) > 0.05
    assert phys_data["wavelength_source"] == "user"
    assert max(v for v in phys_data["rho_gamma_m2"] if v is not None) > 1e12

    # Also test loading physics analysis directly from saved output.xlsx
    res_phys_excel = client.post(
        "/api/fitting/physics-analysis",
        json={
            "excel_path": str(out_xlsx),
            "a_gamma0_nm": 0.3595,
            "a_alpha0_nm": 0.2868,
            "instrumental_fwhm_deg": 0.018,
        },
    )
    assert res_phys_excel.status_code == 200
    assert len(res_phys_excel.json()["nums"]) == 210

    # 7. Mode 2: DIC Video Inspect & WebSocket Export (with Japanese output folder)
    res_vid_inspect = client.post(
        "/api/video/inspect",
        json={
            "mode": "folder",
            "target_path": dic_folder,
            "start_sec": 0.0,
            "stop_sec": 2.0,
            "step_sec": 0.5,
        },
    )
    assert res_vid_inspect.status_code == 200
    assert res_vid_inspect.json()["video_count"] >= 2

    jp_out_dir = tmp_path / "DIC日本語出力テスト"
    with client.websocket_connect("/ws/video/export") as ws_vid:
        ws_vid.send_json(
            {
                "mode": "single",
                "target_path": dic_video,
                "start_sec": 0.0,
                "stop_sec": 1.5,
                "step_sec": 0.5,
                "output_dir": str(jp_out_dir),
                "basename": "dic_frame",
                "ext": "jpg",
            }
        )
        vid_complete = None
        while True:
            msg = ws_vid.receive_json()
            if msg["type"] == "complete":
                vid_complete = msg
                break
            elif msg["type"] == "error":
                raise AssertionError(f"Video WS error: {msg}")
        assert vid_complete is not None
        assert vid_complete["saved_count"] == 3
        assert len(list(jp_out_dir.glob("*.jpg"))) == 3
