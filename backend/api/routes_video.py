# -*- coding: utf-8 -*-
"""API & WebSocket routes for Mode 2: DIC Video Frame Extractor (`routes_video.py`)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ..core.video_exporter import (
    estimate_expected_frames,
    export_videos_in_folder,
    inspect_video_file,
    list_videos_in_folder,
    save_frame_range_sec,
)

router = APIRouter(tags=["video"])


class VideoInspectRequest(BaseModel):
    mode: str = Field(default="single", description="'single' | 'folder'")
    target_path: str
    start_sec: float = 0.0
    stop_sec: Optional[float] = None
    step_sec: float = 1.0


class VideoExportRequest(BaseModel):
    mode: str = Field(default="single", description="'single' | 'folder'")
    target_path: str
    start_sec: float = Field(default=0.0, ge=0.0)
    stop_sec: float = Field(default=600.0, gt=0.0)
    step_sec: float = Field(default=1.0, gt=0.0)
    output_dir: Optional[str] = None
    basename: Optional[str] = None
    ext: str = Field(default="jpg", pattern="^(jpg|jpeg|png|JPG|PNG)$")


@router.post("/api/video/inspect")
async def api_video_inspect(req: VideoInspectRequest) -> Dict[str, Any]:
    """Inspect a single video file or a folder of video files and calculate expected frame counts."""
    try:
        p = Path(req.target_path).resolve()
        if req.mode == "single":
            meta = await asyncio.to_thread(inspect_video_file, p)
            stop_val = req.stop_sec if (req.stop_sec is not None and req.stop_sec > 0) else meta.duration_sec
            expected = estimate_expected_frames(meta.duration_sec, req.start_sec, stop_val, req.step_sec)
            default_out_dir = str(p.parent / p.stem)
            default_basename = f"{p.stem}_img"
            return {
                "mode": "single",
                "target_path": str(p),
                "video_count": 1,
                "videos": [meta.to_dict()],
                "total_duration_sec": round(meta.duration_sec, 3),
                "recommended_stop_sec": round(meta.duration_sec, 2),
                "expected_total_frames": expected,
                "default_output_dir": default_out_dir,
                "default_basename": default_basename,
            }
        else:
            videos = await asyncio.to_thread(list_videos_in_folder, p)
            metas = []
            total_dur = 0.0
            total_expected = 0
            for vp in videos:
                m = await asyncio.to_thread(inspect_video_file, vp)
                metas.append(m.to_dict())
                total_dur += m.duration_sec
                stop_val = req.stop_sec if (req.stop_sec is not None and req.stop_sec > 0) else m.duration_sec
                total_expected += estimate_expected_frames(m.duration_sec, req.start_sec, stop_val, req.step_sec)

            max_dur = max((m["duration_sec"] for m in metas), default=0.0)
            return {
                "mode": "folder",
                "target_path": str(p),
                "video_count": len(metas),
                "videos": metas,
                "total_duration_sec": round(total_dur, 3),
                "recommended_stop_sec": round(max_dur, 2),
                "expected_total_frames": total_expected,
                "default_output_dir": str(p),
                "default_basename": "_img",
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/video/export")
async def api_video_export_sync(req: VideoExportRequest) -> Dict[str, Any]:
    """Execute single-video or folder-batch frame extraction via REST API."""
    try:
        p = Path(req.target_path).resolve()
        if req.mode == "single":
            out_dir = Path(req.output_dir).resolve() if req.output_dir else (p.parent / p.stem)
            bname = req.basename if req.basename else f"{p.stem}_img"
            res = await asyncio.to_thread(
                save_frame_range_sec,
                video_path=p,
                start_sec=req.start_sec,
                stop_sec=req.stop_sec,
                step_sec=req.step_sec,
                dir_path=out_dir,
                basename=bname,
                ext=req.ext,
            )
            return {"status": "ok", "mode": "single", **res}
        else:
            out_root = Path(req.output_dir).resolve() if req.output_dir else p
            suffix = req.basename if req.basename else "_img"
            res = await asyncio.to_thread(
                export_videos_in_folder,
                folder_path=p,
                start_sec=req.start_sec,
                stop_sec=req.stop_sec,
                step_sec=req.step_sec,
                output_root_dir=out_root,
                basename_suffix=suffix,
                ext=req.ext,
            )
            return {"status": "ok", "mode": "folder", **res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.websocket("/ws/video/export")
async def ws_video_export(websocket: WebSocket) -> None:
    """Stream real-time progress and output frame count during DIC video frame extraction."""
    await websocket.accept()
    loop = asyncio.get_running_loop()
    try:
        raw_req = await websocket.receive_json()
        req = VideoExportRequest(**raw_req)
        p = Path(req.target_path).resolve()
        queue: asyncio.Queue = asyncio.Queue()

        if req.mode == "single":
            out_dir = Path(req.output_dir).resolve() if req.output_dir else (p.parent / p.stem)
            bname = req.basename if req.basename else f"{p.stem}_img"

            def _on_progress(cur: int, tot: int, fpath: str) -> None:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {
                        "type": "progress",
                        "current": cur,
                        "total": tot,
                        "progress_pct": round(100.0 * cur / max(1, tot), 1),
                        "video_name": p.name,
                        "last_file": fpath,
                    },
                )

            def _run_single():
                return save_frame_range_sec(
                    video_path=p,
                    start_sec=req.start_sec,
                    stop_sec=req.stop_sec,
                    step_sec=req.step_sec,
                    dir_path=out_dir,
                    basename=bname,
                    ext=req.ext,
                    progress_callback=_on_progress,
                )

            fut = loop.run_in_executor(None, _run_single)
        else:
            out_root = Path(req.output_dir).resolve() if req.output_dir else p
            suffix = req.basename if req.basename else "_img"

            def _on_folder_progress(v_idx: int, v_tot: int, vname: str, fpath: str) -> None:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {
                        "type": "progress",
                        "current": v_idx,
                        "total": v_tot,
                        "progress_pct": round(100.0 * v_idx / max(1, v_tot), 1),
                        "video_name": vname,
                        "last_file": fpath,
                    },
                )

            def _run_folder():
                return export_videos_in_folder(
                    folder_path=p,
                    start_sec=req.start_sec,
                    stop_sec=req.stop_sec,
                    step_sec=req.step_sec,
                    output_root_dir=out_root,
                    basename_suffix=suffix,
                    ext=req.ext,
                    progress_callback=_on_folder_progress,
                )

            fut = loop.run_in_executor(None, _run_folder)

        while not fut.done():
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=0.05)
                await websocket.send_json(msg)
            except asyncio.TimeoutError:
                continue

        while not queue.empty():
            await websocket.send_json(queue.get_nowait())

        result = await fut
        await websocket.send_json({
            "type": "complete",
            "mode": req.mode,
            **result,
        })
    except WebSocketDisconnect:
        return
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "detail": str(e)})
        except Exception:
            pass
