# -*- coding: utf-8 -*-
"""DIC Video Frame Extractor Engine (`video_exporter.py`).

Supports:
1. Single video frame extraction (`export_video_to_image.py` equivalent)
2. Folder batch video frame extraction (`export_videos_to_images.py` equivalent)

Fixes:
- Case-insensitive video extension matching (`Path.suffix.lower()` for `.mp4`, `.mov`, `.avi`, `.mkv`, `.m4v`)
  instead of `'MP4' in s` / `.removesuffix('.MP4')`.
- Unicode / Japanese Windows path compatibility by replacing `cv2.imwrite()` with
  `cv2.imencode()` + `Path.write_bytes()`.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import cv2
import numpy as np

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv"}


@dataclass
class VideoMetadata:
    video_path: str
    filename: str
    stem: str
    extension: str
    fps: float
    frame_count: int
    duration_sec: float
    width: int
    height: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_path": self.video_path,
            "filename": self.filename,
            "stem": self.stem,
            "extension": self.extension,
            "fps": round(self.fps, 4),
            "frame_count": self.frame_count,
            "duration_sec": round(self.duration_sec, 3),
            "width": self.width,
            "height": self.height,
        }


def save_image_unicode_safe(file_path: str | Path, frame: np.ndarray, ext: str = "jpg", quality: int = 95) -> bool:
    """Save an OpenCV BGR image to disk safely even when `file_path` contains Japanese/Unicode characters."""
    out_path = Path(file_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    clean_ext = ext.lower().lstrip(".")
    if clean_ext == "jpeg":
        clean_ext = "jpg"

    encode_params: List[int] = []
    if clean_ext == "jpg":
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
    elif clean_ext == "png":
        encode_params = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]

    ok, buf = cv2.imencode(f".{clean_ext}", frame, encode_params)
    if not ok:
        return False
    out_path.write_bytes(buf.tobytes())
    return True


def list_videos_in_folder(folder_path: str | Path) -> List[Path]:
    """Return sorted list of video files in `folder_path` using case-insensitive suffix matching."""
    root = Path(folder_path).resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Folder not found: {root}")

    videos = [
        p for p in root.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    ]
    videos.sort(key=lambda p: p.name.lower())
    return videos


def inspect_video_file(video_path: str | Path) -> VideoMetadata:
    """Read FPS, total frame count, duration (sec), and resolution from a video file."""
    p = Path(video_path).resolve()
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"Video file not found: {p}")

    cap = cv2.VideoCapture(str(p))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {p}")

    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        frame_count = max(0, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        cap.release()

    if fps <= 0:
        fps = 30.0
    duration_sec = (frame_count / fps) if frame_count > 0 else 0.0

    return VideoMetadata(
        video_path=str(p),
        filename=p.name,
        stem=p.stem,
        extension=p.suffix,
        fps=fps,
        frame_count=frame_count,
        duration_sec=duration_sec,
        width=width,
        height=height,
    )


def estimate_expected_frames(duration_sec: float, start_sec: float, stop_sec: float, step_sec: float) -> int:
    """Calculate how many frames will be extracted for given time range and step."""
    if step_sec <= 0:
        return 0
    effective_start = max(0.0, float(start_sec))
    effective_stop = min(float(duration_sec), float(stop_sec)) if duration_sec > 0 else float(stop_sec)
    if effective_stop <= effective_start:
        return 0
    count = 0
    sec = effective_start
    while sec < effective_stop - 1e-9:
        count += 1
        sec += step_sec
    return count


def save_frame_range_sec(
    video_path: str | Path,
    start_sec: float,
    stop_sec: float,
    step_sec: float,
    dir_path: str | Path,
    basename: str,
    ext: str = "jpg",
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Dict[str, Any]:
    """Extract frames from `[start_sec, stop_sec)` at `step_sec` intervals with Unicode-safe saving."""
    if step_sec <= 0:
        raise ValueError("step_sec must be greater than 0.")

    vpath = Path(video_path).resolve()
    out_dir = Path(dir_path).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(vpath))
    if not cap.isOpened():
        raise ValueError(f"Failed to open video: {vpath}")

    saved_files: List[str] = []
    try:
        total_frames_in_video = max(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        digit = len(str(total_frames_in_video))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        if fps <= 0:
            fps = 30.0
        fps_inv = 1.0 / fps
        duration_sec = total_frames_in_video * fps_inv

        effective_stop = min(float(stop_sec), duration_sec) if duration_sec > 0 else float(stop_sec)
        expected_total = max(1, estimate_expected_frames(duration_sec, start_sec, effective_stop, step_sec))

        clean_ext = ext.lower().lstrip(".")
        sec = max(0.0, float(start_sec))
        idx = 0

        while sec < stop_sec - 1e-9:
            n = round(fps * sec)
            if n >= total_frames_in_video:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, n)
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            file_name = f"{basename}_{str(n).zfill(digit)}_{n * fps_inv:.0f}.{clean_ext}"
            out_file_path = out_dir / file_name
            ok = save_image_unicode_safe(out_file_path, frame, ext=clean_ext)
            if ok:
                saved_files.append(str(out_file_path))
            idx += 1
            if progress_callback:
                progress_callback(idx, expected_total, str(out_file_path))
            sec += step_sec
    finally:
        cap.release()

    return {
        "video_path": str(vpath),
        "output_dir": str(out_dir),
        "basename": basename,
        "ext": ext.lower().lstrip("."),
        "saved_count": len(saved_files),
        "saved_files": saved_files,
    }


def export_videos_in_folder(
    folder_path: str | Path,
    start_sec: float,
    stop_sec: float,
    step_sec: float,
    output_root_dir: Optional[str | Path] = None,
    basename_suffix: str = "_img",
    ext: str = "jpg",
    progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
) -> Dict[str, Any]:
    """Batch-extract frames from all videos in `folder_path` (`export_videos_to_images.py` equivalent)."""
    root = Path(folder_path).resolve()
    out_base = Path(output_root_dir).resolve() if output_root_dir else root
    videos = list_videos_in_folder(root)
    if not videos:
        raise FileNotFoundError(f"No video files (.mp4, .mov, .avi) found in {root}")

    results: List[Dict[str, Any]] = []
    total_saved = 0
    n_vids = len(videos)

    for v_idx, vpath in enumerate(videos, 1):
        stem = vpath.stem
        sub_out_dir = out_base / stem
        basename = f"{stem}{basename_suffix}"

        def _on_frame(cur: int, tot: int, fpath: str, _vname: str = vpath.name, _vi: int = v_idx) -> None:
            if progress_callback:
                progress_callback(_vi, n_vids, _vname, fpath)

        res = save_frame_range_sec(
            video_path=vpath,
            start_sec=start_sec,
            stop_sec=stop_sec,
            step_sec=step_sec,
            dir_path=sub_out_dir,
            basename=basename,
            ext=ext,
            progress_callback=_on_frame,
        )
        total_saved += int(res["saved_count"])
        results.append(res)

    return {
        "folder_path": str(root),
        "output_root_dir": str(out_base),
        "video_count": n_vids,
        "total_saved_frames": total_saved,
        "results": results,
    }
