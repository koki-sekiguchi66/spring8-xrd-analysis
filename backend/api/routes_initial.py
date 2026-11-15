# -*- coding: utf-8 -*-
"""API routes for Step 2: Multi-file Origin-compatible Voigt initial value exploration & Excel saving."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.excel_io import append_initial_block, read_initial_blocks, read_initial_workbook, save_initial_excel
from ..core.physics_analyzer import canonical_peak_key
from ..core.origin_voigt import baseline_kwargs, fit_origin_voigt_group, run_custom_group, run_initial_auto_detect
from ..core.utils import find_file_by_num, infer_specimen_name, list_sorted_bcg_files, resolve_analyzed_folder
from .routes_fitting import SESSION_STORE

router = APIRouter(prefix="/api/initial", tags=["initial"])


class BaselineSpec(BaseModel):
    """Origin Peak Analyzer baseline of the Step 2 fit window."""

    mode: str = Field(default="constant", description="'none' | 'constant' | 'end_points_weighted' | 'straight_line'")
    end_points_pct: float = 5.0
    fit_with_peaks: bool = False


class AutoDetectRequest(BaseModel):
    folder_path: str
    mode: str = Field(default="auto", description="'auto' | 'manual'")
    manual_nums: Optional[List[int]] = None
    vary_y0: bool = False
    baseline: Optional[BaselineSpec] = None


class RefitSingleRequest(BaseModel):
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
    baseline: Optional[BaselineSpec] = None


class CustomGroupRequest(BaseModel):
    folder_path: str
    peaks: List[str]
    nums: List[int]
    range_min: Optional[float] = None
    range_max: Optional[float] = None
    group_id: Optional[str] = None
    vary_y0: bool = False
    baseline: Optional[BaselineSpec] = None


class LoadInitialExcelRequest(BaseModel):
    excel_path: str


class SaveInitialExcelRequest(BaseModel):
    folder_path: str
    specimen_name: Optional[str] = None
    selected_peaks: List[Dict[str, Any]]
    # One block per group and representative frame: {"group_id", "No", "peaks": [...], "ratio_rows"}
    group_blocks: Optional[List[Dict[str, Any]]] = None


class LudersBlockRequest(BaseModel):
    folder_path: str
    excel_path: str
    num: int
    # 2-peak fcc111 + bcc110 fit of this frame (Step 2): start values of the 3-peak fit
    base_peaks: List[Dict[str, Any]]
    range_min: float
    range_max: float
    peak_names: List[str] = Field(default_factory=lambda: ["fcc111a", "bcc110a", "bcc1102"])
    v3_center_cap: float = 11.65
    baseline: Optional[BaselineSpec] = None


@router.post("/auto-detect")
async def api_initial_auto_detect(req: AutoDetectRequest) -> Dict[str, Any]:
    """Run Origin-compatible Voigt fitting on representative (early γ + late γ+α') or manual files."""
    try:
        res = await asyncio.to_thread(
            run_initial_auto_detect,
            folder_path=req.folder_path,
            mode=req.mode,
            manual_nums=req.manual_nums,
            vary_y0=req.vary_y0,
            baseline=req.baseline.model_dump() if req.baseline else None,
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/refit-single")
async def api_initial_refit_single(req: RefitSingleRequest) -> Dict[str, Any]:
    """Immediately re-compute Origin-compatible Voigt fit for a single peak or pair with updated range/centers."""
    try:
        root = resolve_analyzed_folder(req.folder_path)
        bcg_dir = root / "bcg_removed_arpls"
        files = list_sorted_bcg_files(bcg_dir)
        idx, path = find_file_by_num(files, req.num)
        if path is None:
            raise FileNotFoundError(f"File number {req.num} not found in {bcg_dir}")
        actual_num = files[idx][0]
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
            **baseline_kwargs(req.baseline.model_dump() if req.baseline else None, req.vary_y0),
        )
        return fit_res.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/custom-group")
async def api_initial_custom_group(req: CustomGroupRequest) -> Dict[str, Any]:
    """Create a user-defined peak group (any combination of reflections) and fit it on the given files."""
    try:
        return await asyncio.to_thread(
            run_custom_group,
            folder_path=req.folder_path,
            peaks=req.peaks,
            nums=req.nums,
            range_min=req.range_min,
            range_max=req.range_max,
            group_id=req.group_id,
            vary_y0=req.vary_y0,
            baseline=req.baseline.model_dump() if req.baseline else None,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/load-excel")
async def api_initial_load_excel(req: LoadInitialExcelRequest) -> Dict[str, Any]:
    """Read an Origin / Harada style `_initial.xlsx` (all peak blocks and all initial-value rows)."""
    try:
        blocks = await asyncio.to_thread(read_initial_blocks, req.excel_path)
        peaks = await asyncio.to_thread(read_initial_workbook, req.excel_path)
        return {
            "status": "ok",
            "excel_path": str(Path(req.excel_path)),
            "peaks": peaks,
            "blocks": blocks,
            "canonical": {name: canonical_peak_key(name) for name in peaks},
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/save-excel")
async def api_initial_save_excel(req: SaveInitialExcelRequest) -> Dict[str, Any]:
    """Save user-approved initial peak values to `(specimen_name)_initial.xlsx` in the analyzed directory."""
    try:
        root = resolve_analyzed_folder(req.folder_path)
        specimen = req.specimen_name or infer_specimen_name(root)
        SESSION_STORE["folder_path"] = str(root)
        SESSION_STORE["specimen_name"] = specimen
        saved_path = await asyncio.to_thread(
            save_initial_excel,
            folder_path=root,
            specimen_name=specimen,
            peaks_data=req.selected_peaks,
            group_blocks=req.group_blocks,
        )
        return {
            "status": "ok",
            "saved_path": saved_path,
            "folder_path": str(root),
            "specimen_name": specimen,
            "peak_count": len(req.selected_peaks),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/luders-block")
async def api_initial_luders_block(req: LudersBlockRequest) -> Dict[str, Any]:
    """3-peak (fcc111a / bcc110a / bcc1102) Origin-compatible fit of a post-onset frame, appended to
    `_initial.xlsx` as the 3PeaksLuders initial block (as in Harada's procedure). A block that already
    exists for these peaks and No is kept unchanged (hand edits win)."""
    try:
        root = resolve_analyzed_folder(req.folder_path)
        files = list_sorted_bcg_files(root / "bcg_removed_arpls")
        idx, path = find_file_by_num(files, req.num)
        if path is None:
            raise FileNotFoundError(f"File num={req.num} not found")
        arr = np.loadtxt(path, delimiter=",")
        b1, b2 = req.base_peaks[0], req.base_peaks[1]
        c3 = min(float(b2["xc"]) + 0.03, req.v3_center_cap - 0.005)
        fit = await asyncio.to_thread(
            fit_origin_voigt_group,
            x_full=arr[:, 0],
            y_full=arr[:, 1],
            num=int(files[idx][0]),
            filename=path.name,
            group_id="luders",
            peak_names=req.peak_names,
            range_min=req.range_min,
            range_max=req.range_max,
            initial_centers=[float(b1["xc"]), float(b2["xc"]), c3],
            initial_wG=[float(b1["wG"]), float(b2["wG"]), float(b2["wG"])],
            initial_wL=[float(b1["wL"]), float(b2["wL"]), float(b2["wL"])],
            initial_A=[float(b1["A"]), 0.5 * float(b2["A"]), 0.5 * float(b2["A"])],
            **baseline_kwargs(req.baseline.model_dump() if req.baseline else None),
        )
        fd = fit.to_dict()
        if fd.get("error") or len(fd.get("peaks", [])) != 3:
            raise ValueError(fd.get("error") or "3 ピーク fit に失敗しました")
        res = await asyncio.to_thread(append_initial_block, req.excel_path, fd["peaks"], int(files[idx][0]))
        blk = res["block"]
        row = blk["rows"][0]
        peaks = [{"peak_name": n, "No": row["No"], **row["entries"][n]} for n in blk["peaks"]]
        return {"status": "ok", "appended": res["appended"], "num": row["No"], "peaks": peaks, "fit": fd}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
