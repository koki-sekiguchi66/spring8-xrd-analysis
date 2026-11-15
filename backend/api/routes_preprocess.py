# -*- coding: utf-8 -*-
"""API routes for Step 1: Folder selection, OS native dialog, .tth separation, and BG removal."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.bg_remover import get_preprocess_preview, run_background_removal_batch
from ..core.separator import separate_directory
from ..core.utils import (
    find_sample_data_root,
    infer_specimen_name,
    list_sorted_bcg_files,
    list_sorted_tth_files,
    resolve_analyzed_folder,
)
from .routes_fitting import SESSION_STORE

router = APIRouter(prefix="/api", tags=["preprocess"])


class NativeDialogRequest(BaseModel):
    mode: str = Field(default="folder", description="'folder' | 'video_file' | 'save_folder'")
    title: str = Field(default="Select Target")
    initial_dir: Optional[str] = None


class PreprocessRunRequest(BaseModel):
    folder_path: str
    specimen_name: Optional[str] = None
    th_min: float = Field(default=10.2, ge=0.0, le=35.0)
    spike_threshold_factor: float = Field(default=5.0, ge=1.0, le=30.0)
    valley_distance: int = Field(default=100, ge=10, le=500)
    valley_avg_window: int = Field(default=11, ge=3, le=51)
    force_recompute: bool = False


def _open_tk_dialog(mode: str, title: str, initial_dir: Optional[str]) -> str:
    """Run tkinter filedialog in a dedicated thread so it never blocks the event loop."""
    result_holder: List[str] = [""]

    def _worker() -> None:
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            init_d = initial_dir if (initial_dir and Path(initial_dir).exists()) else str(Path.cwd())
            if mode == "video_file":
                selected = filedialog.askopenfilename(
                    title=title,
                    initialdir=init_d,
                    filetypes=[
                        ("Video Files", "*.mp4 *.MP4 *.mov *.MOV *.avi *.AVI *.mkv *.MKV"),
                        ("All Files", "*.*"),
                    ],
                )
            elif mode == "excel_file":
                selected = filedialog.askopenfilename(
                    title=title,
                    initialdir=init_d,
                    filetypes=[
                        ("Excel Files", "*.xlsx *.xlsm"),
                        ("All Files", "*.*"),
                    ],
                )
            else:
                selected = filedialog.askdirectory(title=title, initialdir=init_d)
            root.destroy()
            if selected:
                result_holder[0] = str(Path(selected).resolve())
        except Exception:
            result_holder[0] = ""

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=120.0)
    return result_holder[0]


@router.post("/dialog/select")
async def select_native_dialog(req: NativeDialogRequest) -> Dict[str, Any]:
    """Open OS native folder or file selection dialog on Windows 11."""
    selected = await asyncio.to_thread(_open_tk_dialog, req.mode, req.title, req.initial_dir)
    return {
        "selected_path": selected,
        "cancelled": not bool(selected),
    }


@router.get("/preprocess/sample-paths")
def get_sample_paths() -> Dict[str, Any]:
    """Return available bundled sample XRD folder and sample DIC video paths for quick testing."""
    sample_root = find_sample_data_root()
    sample_xrd = sample_root / "Seki_age_2_tensile"
    sample_dic_dir = sample_root / "dic_sample"
    sample_dic_video = sample_dic_dir / "DIC_tensile_sample.mp4"
    return {
        "sample_xrd_folder": str(sample_xrd) if sample_xrd.exists() else "",
        "sample_dic_folder": str(sample_dic_dir) if sample_dic_dir.exists() else "",
        "sample_dic_video": str(sample_dic_video) if sample_dic_video.exists() else "",
    }


@router.post("/preprocess/run")
async def run_preprocess(req: PreprocessRunRequest) -> Dict[str, Any]:
    """Separate `.tth` files into `tth/` and run Spike + Rubberband + PCHIP/arPLS BG subtraction."""
    folder = resolve_analyzed_folder(req.folder_path)
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"指定されたフォルダが存在しません: {req.folder_path}")

    try:
        sep_res = await asyncio.to_thread(separate_directory, folder)
        bg_res = await asyncio.to_thread(
            run_background_removal_batch,
            folder_path=folder,
            th_min=req.th_min,
            spike_threshold_factor=req.spike_threshold_factor,
            valley_distance=req.valley_distance,
            valley_avg_window=req.valley_avg_window,
            force_recompute=req.force_recompute,
        )
        nums: List[int] = bg_res["nums"]
        default_preview_num = 50 if 50 in nums else (nums[0] if nums else 1)
        preview = await asyncio.to_thread(
            get_preprocess_preview,
            folder_path=folder,
            target_num=default_preview_num,
            th_min=req.th_min,
            spike_threshold_factor=req.spike_threshold_factor,
            valley_distance=req.valley_distance,
            valley_avg_window=req.valley_avg_window,
        )
        specimen = req.specimen_name or infer_specimen_name(folder)
        SESSION_STORE["folder_path"] = str(folder.resolve())
        SESSION_STORE["specimen_name"] = specimen
        return {
            "status": "ok",
            "folder_path": str(folder.resolve()),
            "specimen_name": specimen,
            "separation": {
                "already_separated": sep_res.already_separated,
                "moved_tth_count": sep_res.moved_tth_count,
                "moved_others_count": sep_res.moved_others_count,
                "total_tth_count": sep_res.total_tth_count,
            },
            "background_removal": bg_res,
            "nums": nums,
            "preview": preview,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/preprocess/preview/{num}")
async def preview_preprocess_num(
    num: int,
    folder_path: str = Query(..., description="Target specimen folder path"),
    th_min: float = Query(10.2, ge=0.0, le=35.0),
    spike_threshold_factor: float = Query(5.0, ge=1.0, le=30.0),
    valley_distance: int = Query(100, ge=10, le=500),
    valley_avg_window: int = Query(11, ge=3, le=51),
) -> Dict[str, Any]:
    """Return Raw, Despiked, Rubberband anchors, PCHIP baseline, and BG-subtracted arrays for `num`."""
    try:
        preview = await asyncio.to_thread(
            get_preprocess_preview,
            folder_path=folder_path,
            target_num=num,
            th_min=th_min,
            spike_threshold_factor=spike_threshold_factor,
            valley_distance=valley_distance,
            valley_avg_window=valley_avg_window,
        )
        return preview
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
