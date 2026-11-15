# -*- coding: utf-8 -*-
"""API routes for Step 2: Multi-file Origin-compatible Voigt initial value exploration & Excel saving."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.excel_io import read_initial_workbook, save_initial_excel
from ..core.physics_analyzer import canonical_peak_key
from ..core.origin_voigt import fit_origin_voigt_group, run_custom_group, run_initial_auto_detect
from ..core.utils import find_file_by_num, infer_specimen_name, list_sorted_bcg_files, resolve_analyzed_folder
from .routes_fitting import SESSION_STORE

router = APIRouter(prefix="/api/initial", tags=["initial"])


class AutoDetectRequest(BaseModel):
    folder_path: str
    mode: str = Field(default="auto", description="'auto' | 'manual'")
    manual_nums: Optional[List[int]] = None
    vary_y0: bool = False


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


class CustomGroupRequest(BaseModel):
    folder_path: str
    peaks: List[str]
    nums: List[int]
    range_min: Optional[float] = None
    range_max: Optional[float] = None
    group_id: Optional[str] = None
    vary_y0: bool = False


class LoadInitialExcelRequest(BaseModel):
    excel_path: str


class SaveInitialExcelRequest(BaseModel):
    folder_path: str
    specimen_name: Optional[str] = None
    selected_peaks: List[Dict[str, Any]]


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
            vary_y0=req.vary_y0,
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
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/load-excel")
async def api_initial_load_excel(req: LoadInitialExcelRequest) -> Dict[str, Any]:
    """Read an Origin / Harada style `_initial.xlsx` (all peak blocks and all initial-value rows)."""
    try:
        peaks = await asyncio.to_thread(read_initial_workbook, req.excel_path)
        return {
            "status": "ok",
            "excel_path": str(Path(req.excel_path)),
            "peaks": peaks,
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
