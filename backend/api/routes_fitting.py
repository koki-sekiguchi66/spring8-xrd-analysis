# -*- coding: utf-8 -*-
"""API & WebSocket routes for Step 3 (Batch Fitting & Live Monitor) and Step 4 (Review, Repair & Excel Export)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ..core.excel_io import build_unified_columns, export_fitting_results_excel
from ..core.fitters import FitStepPayload, Luders3Fitter, MultiPeakFitter, Ratio2Fitter, SinglePeakFitter
from ..core.origin_voigt import calc_origin_fwhm, fit_origin_voigt_group, wG_to_sigma, wL_to_gamma
from ..core.physics_analyzer import compute_physical_analysis, load_groups_from_output_excel
from ..core.utils import find_file_by_num, infer_specimen_name, list_sorted_bcg_files, resolve_analyzed_folder

router = APIRouter(tags=["fitting"])

# In-memory store for the latest batch run so Step 4 can inspect/repair waveforms and export to Excel
SESSION_STORE: Dict[str, Dict[str, Any]] = {
    "folder_path": "",
    "specimen_name": "",
    "groups": {},
}


class GroupBatchConfig(BaseModel):
    group_id: str
    engine: str = Field(default="1Peak", description="'1Peak' | '2PeaksRatio' | '3PeaksLuders' | 'MultiPeaks'")
    peaks: List[str]
    init_num: int
    init_peaks: List[Dict[str, Any]]
    th_min: Optional[float] = None
    th_max: Optional[float] = None
    fitting_range_min: float = -0.7
    fitting_range_max: float = 0.7
    dimt_onset_num: int = 200
    undeform_initial: int = 200
    undeform_end: int = 275
    final_num: Optional[int] = None
    R: float = 0.52
    R2: float = 3.45
    # None -> engine default of Harada's original script
    # (1Peak: 0.7 relative RMS, MultiPeaks: 60 MAE, 2PeaksRatio: 200 RMS, 3PeaksLuders: 350 MAE)
    residual_limit: Optional[float] = None
    max_attempts: Optional[int] = None
    newly_forms_peak: Optional[List[int]] = None
    min_peak_separation: float = 0.5
    suppress_before_onset: bool = False
    initial_ep_region: int = 1
    end_ep_region: int = 120
    num_init_val_set: int = 5
    vib_ratio_fine: float = 0.1
    r_candidates: Optional[List[float]] = None
    v3_center_cap: float = 11.65
    # 3PeaksLuders: take R from the best_R of this 2PeaksRatio group (Harada's cold-rolled flow)
    R_source_group: Optional[str] = None
    use_bcc211_constraint: bool = False
    bcc110_center_tol_deg: float = 0.05
    # Constant background y0 in the window (Origin's y0). Off = Harada's scripts.
    fit_y0: bool = False
    default_fit_limits: Optional[Dict[str, Dict[str, float]]] = None


class BatchRunRequest(BaseModel):
    folder_path: str
    specimen_name: Optional[str] = None
    groups: List[GroupBatchConfig]


class RepairFileRequest(BaseModel):
    folder_path: str
    group_id: str
    num: int
    peaks: List[str]
    range_min: float
    range_max: float
    initial_centers: Optional[List[float]] = None
    initial_wG: Optional[List[float]] = None
    initial_wL: Optional[List[float]] = None
    initial_A: Optional[List[float]] = None
    vary_y0: bool = False
    # "engine": re-fit with the group's own engine model (constraints, limits, residual definition)
    # seeded from the neighboring frame in the pass direction; "free": unconstrained Origin Voigt fit.
    mode: str = "engine"


class ExportExcelRequest(BaseModel):
    folder_path: Optional[str] = None
    specimen_name: Optional[str] = None
    groups: Optional[List[Dict[str, Any]]] = None


class BatchRefitItem(BaseModel):
    group_id: str
    num: int
    peaks: Optional[List[str]] = None
    range_min: Optional[float] = None
    range_max: Optional[float] = None
    initial_centers: Optional[List[float]] = None
    initial_wG: Optional[List[float]] = None
    initial_wL: Optional[List[float]] = None
    initial_A: Optional[List[float]] = None
    vary_y0: bool = False


class BatchRefitRequest(BaseModel):
    folder_path: Optional[str] = None
    items: List[BatchRefitItem]
    use_neighbor_interpolation: bool = True
    vary_y0: bool = False
    mode: str = "engine"


class PhysicsAnalysisRequest(BaseModel):
    folder_path: Optional[str] = None
    specimen_name: Optional[str] = None
    excel_path: Optional[str] = None
    groups: Optional[Dict[str, Any]] = None
    wavelength_nm: Optional[float] = None
    instrumental_fwhm_deg: float = 0.018
    a_gamma0_nm: float = 0.3588
    a_alpha0_nm: float = 0.2905
    include_peaks: Optional[List[str]] = None
    exclude_peaks: Optional[List[str]] = None
    kinetics_max_num: Optional[int] = None
    zero_alpha_before_num: Optional[int] = None
    b_iso_A2: float = 0.35
    r_lattice: str = "measured"
    min_num: Optional[int] = None
    max_num: Optional[int] = None


def _build_init_params_from_config(cfg: GroupBatchConfig) -> Dict[str, float]:
    init_pars: Dict[str, float] = {"num": float(cfg.init_num)}
    for idx, pk_item in enumerate(cfg.init_peaks, 1):
        init_pars[f"v{idx}_center"] = float(pk_item["xc"])
        init_pars[f"v{idx}_amplitude"] = float(pk_item["A"])
        wG = float(pk_item.get("wG", 0.02))
        wL = float(pk_item.get("wL", 0.015))
        init_pars[f"v{idx}_sigma"] = wG_to_sigma(wG)
        init_pars[f"v{idx}_gamma"] = wL_to_gamma(wL)
    return init_pars


def _order_groups_for_bcc211_dependency(groups: List[GroupBatchConfig]) -> List[GroupBatchConfig]:
    """Run order: bcc211 before a bcc211-constrained fcc111 + bcc110 group (item 6-3), and
    2PeaksRatio before 3PeaksLuders (best_R handoff in the cold-rolled flow). Stable otherwise."""
    needs_bcc211_first = any(
        g.use_bcc211_constraint and any(pk in ("bcc110", "bcc101") for pk in g.peaks)
        for g in groups
    )

    def _priority(cfg: GroupBatchConfig) -> int:
        eng = _engine_of(cfg)
        if eng == "3PeaksLuders":
            return 3
        if needs_bcc211_first:
            if any(pk in ("bcc211", "bcc112") for pk in cfg.peaks):
                return 0
            if cfg.use_bcc211_constraint and any(pk in ("bcc110", "bcc101") for pk in cfg.peaks):
                return 2
        return 1

    return sorted(groups, key=_priority)


def _resolve_luders_R(cfg: GroupBatchConfig) -> GroupBatchConfig:
    """3PeaksLuders: R = best_R of the linked 2PeaksRatio group of this session, when available."""
    if _engine_of(cfg) != "3PeaksLuders" or not cfg.R_source_group:
        return cfg
    src = SESSION_STORE.get("groups", {}).get(cfg.R_source_group) or {}
    if src.get("best_R") is not None:
        return cfg.model_copy(update={"R": float(src["best_R"])})
    return cfg


def _luders_init_params(cfg: GroupBatchConfig, init_pars: Dict[str, float]) -> Dict[str, float]:
    """Complete 3PeaksLuders initial values from a 2-peak (fcc111 + bcc110) Origin fit.

    v2 (pre-existing alpha') = R x v1 as in the Lüders script (fixed_ratio); v3 (new alpha') takes the
    remaining bcc110 area, starting 0.03 deg above v2 (below `v3_center_cap`).
    """
    if "v3_center" in init_pars or "v2_center" not in init_pars:
        return init_pars
    out = dict(init_pars)
    a_tot = float(out["v2_amplitude"])
    a_pre = min(float(cfg.R) * float(out["v1_amplitude"]), 0.95 * a_tot)
    out["v2_amplitude"] = max(1e-6, a_pre)
    out["v3_amplitude"] = max(0.05 * a_tot, a_tot - a_pre)
    out["v3_center"] = min(float(out["v2_center"]) + 0.03, float(cfg.v3_center_cap) - 0.005)
    out["v3_sigma"] = float(out["v2_sigma"])
    out["v3_gamma"] = float(out["v2_gamma"])
    return out


def _extract_bcc211_guide_from_session(session_groups: Dict[str, Any]) -> Dict[int, Dict[str, float]]:
    """Extract per-frame `num -> {2th, I, wG, wL, sigma, gamma}` from a completed `bcc211` (`bcc112`) group."""
    guide: Dict[int, Dict[str, float]] = {}
    for grec in session_groups.values():
        for pk in grec.get("peaks", []):
            if pk in ("bcc211", "bcc112"):
                for r in grec.get("rows", []):
                    num_val = int(r["num"])
                    wG_val = float(r.get(f"wG_{pk}", 0.0))
                    wL_val = float(r.get(f"wL_{pk}", 0.0))
                    guide[num_val] = {
                        "2th": float(r.get(f"2th_{pk}", 0.0)),
                        "I": float(r.get(f"I_{pk}", 0.0)),
                        "wG": wG_val,
                        "wL": wL_val,
                        "sigma": wG_to_sigma(wG_val),
                        "gamma": wL_to_gamma(wL_val),
                    }
                if guide:
                    return guide
    return guide


ENGINE_DEFAULTS: Dict[str, Dict[str, float]] = {
    "1Peak": {"residual_limit": 0.7, "max_attempts": 5},
    "MultiPeaks": {"residual_limit": 60.0, "max_attempts": 10},
    "2PeaksRatio": {"residual_limit": 200.0, "max_attempts": 10},
    "3PeaksLuders": {"residual_limit": 350.0, "max_attempts": 5},
}


def _engine_of(cfg: GroupBatchConfig) -> str:
    return "1Peak" if (cfg.engine == "1Peak" or len(cfg.peaks) == 1) else cfg.engine


def _instantiate_fitter(
    bcg_dir: Path,
    cfg: GroupBatchConfig,
    bcc211_guide_by_num: Optional[Dict[int, Dict[str, float]]] = None,
):
    init_pars = _build_init_params_from_config(cfg)
    eng = _engine_of(cfg)
    defaults = ENGINE_DEFAULTS.get(eng, ENGINE_DEFAULTS["MultiPeaks"])
    residual_limit = float(cfg.residual_limit) if cfg.residual_limit is not None else defaults["residual_limit"]
    max_attempts = int(cfg.max_attempts) if cfg.max_attempts is not None else int(defaults["max_attempts"])
    y0_init = float(cfg.init_peaks[0].get("y0", 0.0) or 0.0) if (cfg.fit_y0 and cfg.init_peaks) else 0.0

    if eng == "1Peak":
        return SinglePeakFitter(
            bcg_dir=bcg_dir,
            peak=cfg.peaks[0],
            init_params=init_pars,
            group_id=cfg.group_id,
            fitting_range_min=cfg.fitting_range_min,
            fitting_range_max=cfg.fitting_range_max,
            th_min=cfg.th_min,
            th_max=cfg.th_max,
            dimt_onset_num=cfg.dimt_onset_num,
            suppress_before_onset=cfg.suppress_before_onset,
            default_fit_limits=cfg.default_fit_limits,
            residual_limit=residual_limit,
            max_attempts=max_attempts,
            fit_y0=cfg.fit_y0,
            y0_init=y0_init,
        )
    if eng == "2PeaksRatio":
        return Ratio2Fitter(
            bcg_dir=bcg_dir,
            peaks=cfg.peaks,
            init_params=init_pars,
            group_id=cfg.group_id,
            fitting_range_min=cfg.fitting_range_min,
            fitting_range_max=cfg.fitting_range_max,
            th_min=cfg.th_min,
            th_max=cfg.th_max,
            dimt_onset_num=cfg.dimt_onset_num,
            initial_ep_region=cfg.initial_ep_region,
            end_ep_region=cfg.end_ep_region,
            num_init_val_set=cfg.num_init_val_set,
            vib_ratio_fine=cfg.vib_ratio_fine,
            r_candidates=cfg.r_candidates,
            default_fit_limits=cfg.default_fit_limits,
            residual_limit=residual_limit,
            max_attempts=max_attempts,
            fit_y0=cfg.fit_y0,
            y0_init=y0_init,
        )
    if eng == "3PeaksLuders":
        return Luders3Fitter(
            bcg_dir=bcg_dir,
            peaks=cfg.peaks if len(cfg.peaks) == 3 else ["fcc111a", "bcc110a", "bcc1102"],
            init_params=_luders_init_params(cfg, init_pars),
            group_id=cfg.group_id,
            th_min=cfg.th_min if cfg.th_min is not None else 10.6,
            th_max=cfg.th_max if cfg.th_max is not None else 12.3,
            dimt_onset_num=cfg.dimt_onset_num,
            undeform_initial=cfg.undeform_initial,
            undeform_end=cfg.undeform_end,
            final_num=cfg.final_num,
            R=cfg.R,
            R2=cfg.R2,
            v3_center_cap=cfg.v3_center_cap,
            default_fit_limits=cfg.default_fit_limits,
            residual_limit=residual_limit,
            max_attempts=max_attempts,
            fit_y0=cfg.fit_y0,
            y0_init=y0_init,
        )
    return MultiPeakFitter(
        bcg_dir=bcg_dir,
        peaks=cfg.peaks,
        init_params=init_pars,
        group_id=cfg.group_id,
        th_min=cfg.th_min,
        th_max=cfg.th_max,
        dimt_onset_num=cfg.dimt_onset_num,
        newly_forms_peak=cfg.newly_forms_peak,
        min_peak_separation=cfg.min_peak_separation,
        use_bcc211_constraint=cfg.use_bcc211_constraint,
        bcc110_center_tol_deg=cfg.bcc110_center_tol_deg,
        bcc211_guide_by_num=bcc211_guide_by_num,
        default_fit_limits=cfg.default_fit_limits,
        residual_limit=residual_limit,
        max_attempts=max_attempts,
        fit_y0=cfg.fit_y0,
        y0_init=y0_init,
    )


def export_session_to_analyzed_directory(
    folder_path: Optional[str] = None,
    specimen_name: Optional[str] = None,
    groups_override: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Always save `(specimen_name)output.xlsx` directly into the analyzed specimen directory."""
    target_folder_str = (folder_path or "").strip() or SESSION_STORE.get("folder_path", "")
    if not target_folder_str:
        raise ValueError("解析対象ディレクトリ (folder_path) が設定されていません。")
    root = resolve_analyzed_folder(target_folder_str)
    specimen = (specimen_name or "").strip() or SESSION_STORE.get("specimen_name") or infer_specimen_name(root)
    out_path = root / f"{specimen}output.xlsx"

    sheet_items: List[Dict[str, Any]] = []
    if groups_override:
        sheet_items = groups_override
    else:
        for _gid, grec in SESSION_STORE.get("groups", {}).items():
            sheet_items.append({
                "sheet_name": grec.get("sheet_name") or "".join(grec["peaks"]),
                "peaks": grec["peaks"],
                "rows": grec["rows"],
                "engine": grec.get("engine"),
                "dimt_onset_num": grec.get("dimt_onset_num"),
                "best_R": grec.get("best_R"),
                "history_R": grec.get("history_R"),
                "history_residual": grec.get("history_residual"),
            })

    if not sheet_items:
        raise ValueError("No fitting results available to export.")

    return export_fitting_results_excel(out_path, sheet_items)


@router.websocket("/ws/fitting/run")
async def ws_fitting_run(websocket: WebSocket) -> None:
    """Stream real-time continuous fitting progress, waveforms, and trend parameters via WebSocket."""
    await websocket.accept()
    loop = asyncio.get_running_loop()
    try:
        raw_req = await websocket.receive_json()
        req = BatchRunRequest(**raw_req)
        root = resolve_analyzed_folder(req.folder_path)
        bcg_dir = root / "bcg_removed_arpls"
        specimen = req.specimen_name or infer_specimen_name(root)

        SESSION_STORE["folder_path"] = str(root)
        SESSION_STORE["specimen_name"] = specimen
        SESSION_STORE["groups"] = {}

        ordered_groups = _order_groups_for_bcc211_dependency(req.groups)
        total_groups = len(ordered_groups)
        summary_groups: Dict[str, Any] = {}

        for g_idx, cfg in enumerate(ordered_groups):
            bcc211_guide = _extract_bcc211_guide_from_session(SESSION_STORE["groups"])
            cfg = _resolve_luders_R(cfg)
            fitter = _instantiate_fitter(bcg_dir, cfg, bcc211_guide_by_num=bcc211_guide)
            n_files = len(fitter.files)
            stride = max(1, n_files // 60)  # Stream waveform every ~stride files + first/last/outliers for 60fps UI

            await websocket.send_json({
                "type": "group_start",
                "group_index": g_idx,
                "total_groups": total_groups,
                "group_id": cfg.group_id,
                "engine": fitter.engine_name,
                "dimt_onset_num": cfg.dimt_onset_num,
                "peaks": fitter.peaks,
                "total_files": n_files,
            })

            queue: asyncio.Queue = asyncio.Queue()

            def _on_step(payload: FitStepPayload) -> None:
                include_wf = (
                    payload.completed_files == 1
                    or payload.completed_files == payload.total_files
                    or payload.completed_files % stride == 0
                    or payload.is_outlier
                )
                msg = {
                    "type": "step",
                    "group_index": g_idx,
                    "total_groups": total_groups,
                    **payload.to_stream_dict(include_waveform=include_wf),
                }
                loop.call_soon_threadsafe(queue.put_nowait, msg)

            def _run_sync():
                return fitter.run_all(step_callback=_on_step)

            fut = loop.run_in_executor(None, _run_sync)
            while not fut.done():
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=0.05)
                    await websocket.send_json(item)
                except asyncio.TimeoutError:
                    continue

            while not queue.empty():
                item = queue.get_nowait()
                await websocket.send_json(item)

            res = await fut
            outlier_nums = [
                num for num, p in res["results_by_num"].items() if p.is_outlier
            ]
            group_record = {
                "group_id": cfg.group_id,
                "sheet_name": "".join(fitter.peaks),
                "engine": fitter.engine_name,
                "dimt_onset_num": cfg.dimt_onset_num,
                "peaks": fitter.peaks,
                "th_min": fitter.th_min,
                "th_max": fitter.th_max,
                "rows": res["rows"],
                "outlier_nums": sorted(outlier_nums),
                "best_R": res.get("best_R"),
                "history_R": res.get("history_R"),
                "history_residual": res.get("history_residual"),
                "results_by_num": res["results_by_num"],
                "config": cfg.model_dump(),
            }
            SESSION_STORE["groups"][cfg.group_id] = group_record

            summary_groups[cfg.group_id] = {
                "group_id": cfg.group_id,
                "sheet_name": "".join(fitter.peaks),
                "engine": fitter.engine_name,
                "dimt_onset_num": cfg.dimt_onset_num,
                "peaks": fitter.peaks,
                "th_min": round(fitter.th_min, 4),
                "th_max": round(fitter.th_max, 4),
                "rows": res["rows"],
                "outlier_nums": sorted(outlier_nums),
                "best_R": res.get("best_R"),
                "history_R": res.get("history_R"),
                "history_residual": res.get("history_residual"),
            }

            await websocket.send_json({
                "type": "group_complete",
                "group_index": g_idx,
                "total_groups": total_groups,
                "group_summary": summary_groups[cfg.group_id],
            })

        saved_output_path = ""
        try:
            auto_exp = await asyncio.to_thread(
                export_session_to_analyzed_directory,
                folder_path=str(root),
                specimen_name=specimen,
            )
            saved_output_path = auto_exp.get("saved_path", "")
        except Exception:
            saved_output_path = str(root / f"{specimen}output.xlsx")

        await websocket.send_json({
            "type": "all_complete",
            "folder_path": str(root),
            "specimen_name": specimen,
            "saved_output_path": saved_output_path,
            "groups": summary_groups,
        })
    except WebSocketDisconnect:
        return
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "detail": str(e)})
        except Exception:
            pass


@router.post("/api/fitting/run")
async def api_fitting_run_sync(req: BatchRunRequest) -> Dict[str, Any]:
    """REST endpoint for running batch fitting synchronously (used by automated tests or fallback)."""
    root = resolve_analyzed_folder(req.folder_path)
    bcg_dir = root / "bcg_removed_arpls"
    specimen = req.specimen_name or infer_specimen_name(root)

    SESSION_STORE["folder_path"] = str(root)
    SESSION_STORE["specimen_name"] = specimen
    SESSION_STORE["groups"] = {}
    summary_groups: Dict[str, Any] = {}

    ordered_groups = _order_groups_for_bcc211_dependency(req.groups)
    for cfg in ordered_groups:
        bcc211_guide = _extract_bcc211_guide_from_session(SESSION_STORE["groups"])
        cfg = _resolve_luders_R(cfg)
        fitter = _instantiate_fitter(bcg_dir, cfg, bcc211_guide_by_num=bcc211_guide)
        res = await asyncio.to_thread(fitter.run_all)
        outlier_nums = [num for num, p in res["results_by_num"].items() if p.is_outlier]
        SESSION_STORE["groups"][cfg.group_id] = {
            "group_id": cfg.group_id,
            "sheet_name": "".join(fitter.peaks),
            "engine": fitter.engine_name,
            "dimt_onset_num": cfg.dimt_onset_num,
            "peaks": fitter.peaks,
            "th_min": fitter.th_min,
            "th_max": fitter.th_max,
            "rows": res["rows"],
            "outlier_nums": sorted(outlier_nums),
            "best_R": res.get("best_R"),
            "history_R": res.get("history_R"),
            "history_residual": res.get("history_residual"),
            "results_by_num": res["results_by_num"],
            "config": cfg.model_dump(),
        }
        summary_groups[cfg.group_id] = {
            "group_id": cfg.group_id,
            "sheet_name": "".join(fitter.peaks),
            "engine": fitter.engine_name,
            "dimt_onset_num": cfg.dimt_onset_num,
            "peaks": fitter.peaks,
            "th_min": round(fitter.th_min, 4),
            "th_max": round(fitter.th_max, 4),
            "rows": res["rows"],
            "outlier_nums": sorted(outlier_nums),
            "best_R": res.get("best_R"),
            "history_R": res.get("history_R"),
            "history_residual": res.get("history_residual"),
        }

    saved_output_path = ""
    try:
        auto_exp = await asyncio.to_thread(
            export_session_to_analyzed_directory,
            folder_path=str(root),
            specimen_name=specimen,
        )
        saved_output_path = auto_exp.get("saved_path", "")
    except Exception:
        saved_output_path = str(root / f"{specimen}output.xlsx")

    return {
        "status": "ok",
        "folder_path": str(root),
        "specimen_name": specimen,
        "saved_output_path": saved_output_path,
        "groups": summary_groups,
    }


@router.get("/api/fitting/waveform/{group_id}/{num}")
async def api_get_fitted_waveform(
    group_id: str,
    num: int,
    folder_path: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Return the fitted waveform and separated components for a specific `group_id` and `num` in Step 4."""
    group_rec = SESSION_STORE.get("groups", {}).get(group_id)
    if group_rec and num in group_rec.get("results_by_num", {}):
        payload: FitStepPayload = group_rec["results_by_num"][num]
        return payload.to_stream_dict(include_waveform=True)

    raise HTTPException(status_code=404, detail=f"Waveform for group '{group_id}' num={num} not found in session.")


def _neighbor_seed(
    group_rec: Dict[str, Any], num: int, exclude: set
) -> Tuple[Optional[Dict[str, Any]], Optional[int]]:
    """Nearest clean row in the pass direction of the engine (the frame the original run came from).

    1Peak / MultiPeaks / 3PeaksLuders: backward pass for num <= initial num (previous = num + 1),
    forward pass after it (previous = num - 1). 2PeaksRatio: forward from the first file.
    """
    cfg = group_rec.get("config") or {}
    rows = {int(r["num"]): r for r in group_rec.get("rows", []) if r.get("num") is not None}
    bad = set(int(n) for n in group_rec.get("outlier_nums", [])) | set(exclude) | {int(num)}
    clean = sorted(n for n in rows if n not in bad)
    if not clean:
        return None, None
    after = [n for n in clean if n > num]
    before = [n for n in clean if n < num]
    forward = group_rec.get("engine") == "2PeaksRatio" or num > int(cfg.get("init_num", num))
    if forward:
        pick = before[-1] if before else after[0]
    else:
        pick = after[0] if after else before[-1]
    return rows[pick], pick


def _engine_repair(
    bcg_dir: Path,
    group_rec: Dict[str, Any],
    num: int,
    exclude: set,
    manual: Optional[Dict[str, List[float]]] = None,
) -> FitStepPayload:
    """Re-fit one frame with the group's own engine (same model, limits and residual as the run)."""
    cfg = GroupBatchConfig(**group_rec["config"])
    guide = _extract_bcc211_guide_from_session(SESSION_STORE.get("groups", {}))
    fitter = _instantiate_fitter(bcg_dir, cfg, bcc211_guide_by_num=guide)
    idx, _ = find_file_by_num(fitter.files, num)
    if idx < 0:
        raise FileNotFoundError(f"File num={num} not found in {bcg_dir}")
    seed, seed_num = _neighbor_seed(group_rec, num, exclude)
    seed = dict(seed or {})
    if manual:
        for k, pk in enumerate(cfg.peaks):
            for key, col in (("centers", "2th_"), ("A", "I_"), ("wG", "wG_"), ("wL", "wL_")):
                arr = manual.get(key)
                if arr is not None and k < len(arr) and arr[k] is not None:
                    seed[f"{col}{pk}"] = float(arr[k])
    n_idx = find_file_by_num(fitter.files, seed_num)[0] if seed_num is not None else None
    if seed:
        fitter.seed_from_row(seed, neighbor_index=n_idx)
    if isinstance(fitter, Ratio2Fitter):
        R = group_rec.get("best_R")
        return fitter.refit_frame(idx, R=float(R) if R is not None else None)
    return fitter.refit_frame(idx)


def _store_repaired_payload(group_rec: Dict[str, Any], payload: FitStepPayload) -> None:
    num = int(payload.num)
    rows = group_rec.setdefault("rows", [])
    for r_idx, r in enumerate(rows):
        if int(r.get("num", -1)) == num:
            rows[r_idx] = dict(payload.row_data)
            break
    group_rec.setdefault("results_by_num", {})[num] = payload
    outs = set(int(n) for n in group_rec.get("outlier_nums", []))
    if payload.is_outlier:
        outs.add(num)
    else:
        outs.discard(num)
    group_rec["outlier_nums"] = sorted(outs)


@router.post("/api/fitting/refit-file")
async def api_repair_single_file(req: RepairFileRequest) -> Dict[str, Any]:
    """Re-fit a single outlier file in Step 4 and update the stored row and waveform in place."""
    try:
        folder_str = (req.folder_path or "").strip() or SESSION_STORE.get("folder_path", "")
        root = resolve_analyzed_folder(folder_str)
        bcg_dir = root / "bcg_removed_arpls"
        files = list_sorted_bcg_files(bcg_dir)
        idx, path = find_file_by_num(files, req.num)
        if path is None:
            raise FileNotFoundError(f"File num={req.num} not found in {bcg_dir}")
        actual_num = files[idx][0]

        group_rec = SESSION_STORE.get("groups", {}).get(req.group_id)
        if req.mode == "engine" and group_rec and group_rec.get("config"):
            manual = {"centers": req.initial_centers, "A": req.initial_A, "wG": req.initial_wG, "wL": req.initial_wL}
            payload = await asyncio.to_thread(_engine_repair, bcg_dir, group_rec, actual_num, set(), manual)
            _store_repaired_payload(group_rec, payload)
            saved_path = ""
            try:
                saved_path = (await asyncio.to_thread(export_session_to_analyzed_directory, folder_path=str(root))).get("saved_path", "")
            except Exception:
                pass
            return {
                "status": "ok",
                "mode": "engine",
                "num": actual_num,
                "updated_row": payload.row_data,
                "is_outlier": payload.is_outlier,
                "saved_path": saved_path,
                "fit": payload.to_stream_dict(include_waveform=True),
            }

        arr = np.loadtxt(path, delimiter=",")
        x, y = arr[:, 0], arr[:, 1]

        fit_res = await asyncio.to_thread(
            fit_origin_voigt_group,
            x_full=x,
            y_full=y,
            num=actual_num,
            filename=path.name,
            group_id=req.group_id,
            peak_names=req.peaks,
            range_min=req.range_min,
            range_max=req.range_max,
            initial_centers=req.initial_centers,
            initial_wG=req.initial_wG,
            initial_wL=req.initial_wL,
            initial_A=req.initial_A,
            vary_y0=req.vary_y0,
        )

        # Build unified row dict
        updated_row: Dict[str, float] = {"num": int(actual_num)}
        for p in fit_res.peaks:
            pk = p.peak_name
            updated_row[f"2th_{pk}"] = round(p.xc, 6)
            updated_row[f"I_{pk}"] = round(p.A, 6)
            updated_row[f"wG_{pk}"] = round(p.wG, 6)
            updated_row[f"wL_{pk}"] = round(p.wL, 6)
            updated_row[f"FWHM_{pk}"] = round(p.FWHM, 6)
        updated_row["residual"] = round(fit_res.relative_residual, 6)

        # Update SESSION_STORE if present
        group_rec = SESSION_STORE.get("groups", {}).get(req.group_id)
        if group_rec:
            rows = group_rec.get("rows", [])
            for r_idx, r in enumerate(rows):
                if int(r.get("num", -1)) == actual_num:
                    rows[r_idx] = updated_row
                    break
            if actual_num in group_rec.get("results_by_num", {}):
                old_p: FitStepPayload = group_rec["results_by_num"][actual_num]
                old_p.row_data = updated_row
                old_p.x = fit_res.x
                old_p.y_obs = fit_res.y_obs
                old_p.y_fit = fit_res.y_fit
                old_p.components = fit_res.components
                old_p.residual_rmse = fit_res.rmse
                old_p.relative_residual = fit_res.relative_residual
                old_p.is_outlier = False
            if actual_num in group_rec.get("outlier_nums", []):
                group_rec["outlier_nums"].remove(actual_num)

        saved_path = ""
        try:
            auto_exp = await asyncio.to_thread(
                export_session_to_analyzed_directory,
                folder_path=str(root),
            )
            saved_path = auto_exp.get("saved_path", "")
        except Exception:
            pass

        return {
            "status": "ok",
            "mode": "free",
            "num": actual_num,
            "updated_row": updated_row,
            "is_outlier": False,
            "saved_path": saved_path,
            "fit": fit_res.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/fitting/export")
async def api_export_excel(req: ExportExcelRequest) -> Dict[str, Any]:
    """Export all analyzed single peaks and multi-peak pairs to `(specimen_name)output.xlsx` in the analyzed directory."""
    try:
        res = await asyncio.to_thread(
            export_session_to_analyzed_directory,
            folder_path=req.folder_path,
            specimen_name=req.specimen_name,
            groups_override=req.groups,
        )
        return {
            "status": "ok",
            **res,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def _interpolate_neighbor_guess(
    group_rec: Dict[str, Any],
    target_num: int,
    peaks: List[str],
) -> Tuple[Optional[List[float]], Optional[List[float]], Optional[List[float]], Optional[List[float]]]:
    """Interpolate initial guesses (xc, wG, wL, A) from nearest non-outlier neighbor rows."""
    rows = group_rec.get("rows", [])
    outliers = set(group_rec.get("outlier_nums", []))
    clean_rows = [r for r in rows if int(r.get("num", -1)) not in outliers and int(r.get("num", -1)) != target_num]
    if not clean_rows:
        clean_rows = [r for r in rows if int(r.get("num", -1)) != target_num]
    if not clean_rows:
        return None, None, None, None

    before = [r for r in clean_rows if int(r["num"]) < target_num]
    after = [r for r in clean_rows if int(r["num"]) > target_num]
    r_prev = before[-1] if before else (after[0] if after else clean_rows[0])
    r_next = after[0] if after else r_prev

    n_prev = int(r_prev["num"])
    n_next = int(r_next["num"])
    alpha = 0.5 if n_next == n_prev else float(target_num - n_prev) / float(n_next - n_prev)
    alpha = max(0.0, min(1.0, alpha))

    centers: List[float] = []
    wGs: List[float] = []
    wLs: List[float] = []
    As: List[float] = []

    for pk in peaks:
        c1, c2 = float(r_prev.get(f"2th_{pk}", 0.0)), float(r_next.get(f"2th_{pk}", 0.0))
        a1, a2 = float(r_prev.get(f"I_{pk}", 100.0)), float(r_next.get(f"I_{pk}", 100.0))
        g1, g2 = float(r_prev.get(f"wG_{pk}", 0.02)), float(r_next.get(f"wG_{pk}", 0.02))
        l1, l2 = float(r_prev.get(f"wL_{pk}", 0.015)), float(r_next.get(f"wL_{pk}", 0.015))
        centers.append((1.0 - alpha) * c1 + alpha * c2)
        As.append(max(1.0, (1.0 - alpha) * a1 + alpha * a2))
        wGs.append(max(0.004, (1.0 - alpha) * g1 + alpha * g2))
        wLs.append(max(0.002, (1.0 - alpha) * l1 + alpha * l2))

    return centers, wGs, wLs, As


@router.post("/api/fitting/refit-batch")
async def api_repair_batch_files(req: BatchRefitRequest) -> Dict[str, Any]:
    """Batch re-fit multiple selected `(group_id, num)` items across phases/groups in one action."""
    try:
        folder_str = (req.folder_path or "").strip() or SESSION_STORE.get("folder_path")
        if not folder_str:
            raise ValueError("folder_path is not set.")
        root = resolve_analyzed_folder(folder_str)
        bcg_dir = root / "bcg_removed_arpls"
        files = list_sorted_bcg_files(bcg_dir)

        repaired_results: List[Dict[str, Any]] = []

        for item in req.items:
            gid = item.group_id
            group_rec = SESSION_STORE.get("groups", {}).get(gid)
            peaks = item.peaks or (group_rec["peaks"] if group_rec else [])
            if not peaks:
                continue

            r_min = item.range_min if item.range_min is not None else (float(group_rec["th_min"]) if group_rec else 10.5)
            r_max = item.range_max if item.range_max is not None else (float(group_rec["th_max"]) if group_rec else 24.0)

            idx, path = find_file_by_num(files, item.num)
            if path is None:
                continue
            actual_num = files[idx][0]

            if req.mode == "engine" and group_rec and group_rec.get("config"):
                # Frames still waiting in this batch are not used as seeds
                pending = {int(it.num) for it in req.items if it.group_id == gid and int(it.num) != actual_num}
                manual = None
                if item.initial_centers is not None:
                    manual = {"centers": item.initial_centers, "A": item.initial_A, "wG": item.initial_wG, "wL": item.initial_wL}
                payload = await asyncio.to_thread(_engine_repair, bcg_dir, group_rec, actual_num, pending, manual)
                _store_repaired_payload(group_rec, payload)
                repaired_results.append({
                    "group_id": gid,
                    "num": actual_num,
                    "updated_row": payload.row_data,
                    "rmse": round(payload.residual_rmse, 4),
                    "relative_residual": round(payload.relative_residual, 4),
                    "r_squared": None,
                    "is_outlier": payload.is_outlier,
                })
                continue

            arr = np.loadtxt(path, delimiter=",")
            x, y = arr[:, 0], arr[:, 1]

            init_c = item.initial_centers
            init_g = item.initial_wG
            init_l = item.initial_wL
            init_a = item.initial_A

            if req.use_neighbor_interpolation and group_rec and init_c is None:
                nc, ng, nl, na = _interpolate_neighbor_guess(group_rec, actual_num, peaks)
                init_c = nc
                init_g = ng
                init_l = nl
                init_a = na

            # Run Origin Voigt fit (and try a second pass with vary_y0=True if residual is high)
            fit_res = await asyncio.to_thread(
                fit_origin_voigt_group,
                x_full=x,
                y_full=y,
                num=actual_num,
                filename=path.name,
                group_id=gid,
                peak_names=peaks,
                range_min=r_min,
                range_max=r_max,
                initial_centers=init_c,
                initial_wG=init_g,
                initial_wL=init_l,
                initial_A=init_a,
                vary_y0=item.vary_y0 or req.vary_y0,
            )

            updated_row: Dict[str, float] = {"num": int(actual_num)}
            for p in fit_res.peaks:
                pk = p.peak_name
                updated_row[f"2th_{pk}"] = round(p.xc, 6)
                updated_row[f"I_{pk}"] = round(p.A, 6)
                updated_row[f"wG_{pk}"] = round(p.wG, 6)
                updated_row[f"wL_{pk}"] = round(p.wL, 6)
                updated_row[f"FWHM_{pk}"] = round(p.FWHM, 6)
            updated_row["residual"] = round(fit_res.relative_residual, 6)

            if group_rec:
                rows = group_rec.get("rows", [])
                for r_idx, r in enumerate(rows):
                    if int(r.get("num", -1)) == actual_num:
                        rows[r_idx] = updated_row
                        break
                if actual_num in group_rec.get("results_by_num", {}):
                    old_p: FitStepPayload = group_rec["results_by_num"][actual_num]
                    old_p.row_data = updated_row
                    old_p.x = fit_res.x
                    old_p.y_obs = fit_res.y_obs
                    old_p.y_fit = fit_res.y_fit
                    old_p.components = fit_res.components
                    old_p.residual_rmse = fit_res.rmse
                    old_p.relative_residual = fit_res.relative_residual
                    old_p.is_outlier = False
                if actual_num in group_rec.get("outlier_nums", []):
                    group_rec["outlier_nums"].remove(actual_num)

            repaired_results.append({
                "group_id": gid,
                "num": actual_num,
                "updated_row": updated_row,
                "rmse": round(fit_res.rmse, 4),
                "relative_residual": round(fit_res.relative_residual, 4),
                "r_squared": round(fit_res.r_squared, 5),
                "is_outlier": False,
            })

        saved_path = ""
        try:
            auto_exp = await asyncio.to_thread(
                export_session_to_analyzed_directory,
                folder_path=str(root),
            )
            saved_path = auto_exp.get("saved_path", "")
        except Exception:
            pass

        return {
            "status": "ok",
            "repaired_count": len(repaired_results),
            "repaired_items": repaired_results,
            "saved_path": saved_path,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/fitting/physics-analysis")
async def api_physics_analysis(req: PhysicsAnalysisRequest) -> Dict[str, Any]:
    """Compute Martensite Phase Fraction, Dislocation Density per Phase, Lattice Constants & Strains."""
    try:
        target_groups: Dict[str, Any] = {}
        source_label = "session"

        if req.excel_path and Path(req.excel_path).exists():
            target_groups = await asyncio.to_thread(load_groups_from_output_excel, req.excel_path)
            source_label = str(Path(req.excel_path).resolve())
        elif req.groups:
            target_groups = req.groups
        elif SESSION_STORE.get("groups"):
            target_groups = SESSION_STORE["groups"]
        elif req.folder_path:
            root = Path(req.folder_path).resolve()
            specimen = req.specimen_name or infer_specimen_name(root)
            candidate_xlsx = root / f"{specimen}output.xlsx"
            if candidate_xlsx.exists():
                target_groups = await asyncio.to_thread(load_groups_from_output_excel, candidate_xlsx)
                source_label = str(candidate_xlsx)

        if not target_groups:
            raise ValueError("物理量解析を行うためのフィッティング結果データまたは output.xlsx が見つかりません。")

        phys = await asyncio.to_thread(
            compute_physical_analysis,
            groups=target_groups,
            wavelength_nm=req.wavelength_nm,
            instrumental_fwhm_deg=req.instrumental_fwhm_deg,
            a_gamma0_nm=req.a_gamma0_nm,
            a_alpha0_nm=req.a_alpha0_nm,
            include_peaks=req.include_peaks,
            exclude_peaks=req.exclude_peaks,
            kinetics_max_num=req.kinetics_max_num,
            zero_alpha_before_num=req.zero_alpha_before_num,
            b_iso_A2=req.b_iso_A2,
            r_lattice=req.r_lattice,
            min_num=req.min_num,
            max_num=req.max_num,
        )
        return {
            "status": "ok",
            "source": source_label,
            **phys,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
