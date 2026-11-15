# -*- coding: utf-8 -*-
"""Stage 2: Spike removal + Rubberband lower convex hull + PCHIP / arPLS background subtraction."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from pybaselines.whittaker import arpls
from scipy.interpolate import PchipInterpolator
from scipy.signal import find_peaks

from .utils import find_file_by_num, list_sorted_bcg_files, list_sorted_tth_files, resolve_analyzed_folder


def remove_spikes(y: np.ndarray, threshold_factor: float = 5.0) -> np.ndarray:
    """Detect downward spike noise and replace with neighbor average.

    Matches `remove_bcgs_arpls+rubberband_ver2.py` (`threshold_factor=5` in loop).
    """
    y_corrected = np.copy(y)
    if len(y) < 3:
        return y_corrected
    diffs = np.abs(np.diff(y))
    median_diff = float(np.median(diffs))
    threshold = median_diff * threshold_factor

    for i in range(1, len(y) - 1):
        if (y[i] < y[i - 1] - threshold) and (y[i] < y[i + 1] - threshold):
            y_corrected[i] = 0.5 * (y[i - 1] + y[i + 1])

    return y_corrected


def rubberband_filter(
    x_anchors: List[float] | np.ndarray,
    y_anchors: List[float] | np.ndarray,
) -> Tuple[List[float], List[float]]:
    """Compute the lower convex hull (rubberband envelope) of anchor points."""
    x_list = list(x_anchors)
    y_list = list(y_anchors)
    if len(x_list) < 3:
        return x_list, y_list

    final_x = [float(x_list[0])]
    final_y = [float(y_list[0])]

    current_idx = 0
    n_pts = len(x_list)
    while current_idx < n_pts - 1:
        min_slope = float("inf")
        best_next_idx = -1

        for i in range(current_idx + 1, n_pts):
            dx = x_list[i] - x_list[current_idx]
            dy = y_list[i] - y_list[current_idx]
            if dx > 0:
                slope = dy / dx
                if slope < min_slope:
                    min_slope = slope
                    best_next_idx = i

        if best_next_idx != -1:
            current_idx = best_next_idx
            final_x.append(float(x_list[current_idx]))
            final_y.append(float(y_list[current_idx]))
        else:
            break

    return final_x, final_y


@dataclass
class BgRemovalPreview:
    num: int
    filename: str
    th_min: float
    x_sub: np.ndarray
    y_raw: np.ndarray
    y_despiked: np.ndarray
    anchors_x: List[float]
    anchors_y: List[float]
    monotonic_x: List[float]
    monotonic_y: List[float]
    y_background: np.ndarray
    y_corrected: np.ndarray
    method_used: str

    def to_dict(self, max_points: Optional[int] = None) -> Dict:
        step = 1
        if max_points and len(self.x_sub) > max_points:
            step = max(1, len(self.x_sub) // max_points)
        return {
            "num": self.num,
            "filename": self.filename,
            "th_min": self.th_min,
            "method_used": self.method_used,
            "x": np.round(self.x_sub[::step], 5).tolist(),
            "y_raw": np.round(self.y_raw[::step], 4).tolist(),
            "y_despiked": np.round(self.y_despiked[::step], 4).tolist(),
            "anchors_x": [round(v, 5) for v in self.anchors_x],
            "anchors_y": [round(v, 4) for v in self.anchors_y],
            "monotonic_x": [round(v, 5) for v in self.monotonic_x],
            "monotonic_y": [round(v, 4) for v in self.monotonic_y],
            "y_background": np.round(self.y_background[::step], 4).tolist(),
            "y_corrected": np.round(self.y_corrected[::step], 4).tolist(),
        }


def process_single_tth(
    tth_path: Path,
    num: int,
    th_min: float = 10.2,
    spike_threshold_factor: float = 5.0,
    valley_distance: int = 100,
    valley_avg_window: int = 11,
    arpls_lam: float = 1e7,
    out_dir: Optional[Path] = None,
) -> BgRemovalPreview:
    """Process a single `.tth` file through spike removal + Rubberband + PCHIP/arPLS."""
    data = np.loadtxt(tth_path)
    mask = data[:, 0] > th_min
    x_sub = data[mask, 0]
    y_sub = data[mask, 1]

    if len(x_sub) < 10:
        raise ValueError(f"Insufficient data points above th_min={th_min} in {tth_path.name}")

    # Step 1: Spike removal
    y_despiked = remove_spikes(y_sub, threshold_factor=spike_threshold_factor)

    # Step 2: Find local valleys
    minima_indices, _ = find_peaks(-y_despiked, distance=valley_distance)

    # Step 3: Build window-averaged anchor points
    x_anchors: List[float] = []
    y_anchors: List[float] = []
    candidate_indices = np.unique(np.concatenate(([0], minima_indices, [len(y_despiked) - 1])))
    half_window = valley_avg_window // 2

    for idx in candidate_indices:
        idx_int = int(idx)
        start = max(0, idx_int - half_window)
        end = min(len(y_despiked), idx_int + half_window + 1)
        x_anchors.append(float(np.mean(x_sub[start:end])))
        y_anchors.append(float(np.mean(y_despiked[start:end])))

    # Step 4: Rubberband lower convex hull
    monotonic_x, monotonic_y = rubberband_filter(x_anchors, y_anchors)

    # Step 5: PCHIP interpolation with arPLS fallback
    # Deduplicate any strictly identical x coordinates for PchipInterpolator safety
    dedup_x: List[float] = []
    dedup_y: List[float] = []
    for mx, my in zip(monotonic_x, monotonic_y):
        if not dedup_x or mx > dedup_x[-1] + 1e-9:
            dedup_x.append(mx)
            dedup_y.append(my)

    if len(dedup_x) >= 2:
        pchip_model = PchipInterpolator(dedup_x, dedup_y)
        y_background_final = pchip_model(x_sub)
        method_used = "PCHIP"
    else:
        y_background_final = arpls(y_despiked, lam=arpls_lam)[0]
        method_used = "arPLS"

    y_corrected_sub = y_despiked - y_background_final

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = np.column_stack([x_sub, y_corrected_sub])
        out_file_path = out_dir / f"{tth_path.stem}bcg.csv"
        np.savetxt(out_file_path, out_file, delimiter=",", fmt="%.5f")

    return BgRemovalPreview(
        num=num,
        filename=tth_path.name,
        th_min=th_min,
        x_sub=x_sub,
        y_raw=y_sub,
        y_despiked=y_despiked,
        anchors_x=x_anchors,
        anchors_y=y_anchors,
        monotonic_x=dedup_x,
        monotonic_y=dedup_y,
        y_background=y_background_final,
        y_corrected=y_corrected_sub,
        method_used=method_used,
    )


def run_background_removal_batch(
    folder_path: str | Path,
    th_min: float = 10.2,
    spike_threshold_factor: float = 5.0,
    valley_distance: int = 100,
    valley_avg_window: int = 11,
    force_recompute: bool = False,
    max_workers: int = 8,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Dict:
    """Run background subtraction across all `.tth` files in `folder_path/tth`."""
    root = resolve_analyzed_folder(folder_path)
    tth_dir = root / "tth"
    bcg_dir = root / "bcg_removed_arpls"
    bcg_dir.mkdir(parents=True, exist_ok=True)

    tth_files = list_sorted_tth_files(tth_dir)
    if not tth_files:
        raise FileNotFoundError(f"No .tth files found in {tth_dir}")

    # Check if already processed with matching th_min
    existing_bcg = list_sorted_bcg_files(bcg_dir)
    if not force_recompute and len(existing_bcg) == len(tth_files):
        # Verify the first file starts near th_min
        first_bcg = np.loadtxt(existing_bcg[0][1], delimiter=",", max_rows=5)
        if first_bcg.ndim == 2 and abs(float(first_bcg[0, 0]) - th_min) < 0.05:
            return {
                "folder_path": str(root),
                "bcg_dir": str(bcg_dir),
                "processed_count": len(existing_bcg),
                "skipped_cached": True,
                "nums": [num for num, _ in existing_bcg],
                "th_min": th_min,
            }

    total = len(tth_files)
    completed = 0

    def _worker(item: Tuple[int, Path]) -> int:
        num, p = item
        process_single_tth(
            tth_path=p,
            num=num,
            th_min=th_min,
            spike_threshold_factor=spike_threshold_factor,
            valley_distance=valley_distance,
            valley_avg_window=valley_avg_window,
            out_dir=bcg_dir,
        )
        return num

    nums_out: List[int] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for num in pool.map(_worker, tth_files):
            completed += 1
            nums_out.append(num)
            if progress_callback:
                progress_callback(completed, total, f"Processed #{num}")

    nums_out.sort()
    return {
        "folder_path": str(root),
        "bcg_dir": str(bcg_dir),
        "processed_count": len(nums_out),
        "skipped_cached": False,
        "nums": nums_out,
        "th_min": th_min,
    }


def get_preprocess_preview(
    folder_path: str | Path,
    target_num: int,
    th_min: float = 10.2,
    spike_threshold_factor: float = 5.0,
    valley_distance: int = 100,
    valley_avg_window: int = 11,
) -> Dict:
    """Generate interactive preview arrays for a specific `num` file."""
    root = resolve_analyzed_folder(folder_path)
    tth_dir = root / "tth"
    tth_files = list_sorted_tth_files(tth_dir)
    if not tth_files:
        raise FileNotFoundError(f"No .tth files found in {tth_dir}")

    idx, path = find_file_by_num(tth_files, target_num)
    if path is None:
        raise FileNotFoundError(f"File number {target_num} not found in {tth_dir}")
    actual_num = tth_files[idx][0]

    preview = process_single_tth(
        tth_path=path,
        num=actual_num,
        th_min=th_min,
        spike_threshold_factor=spike_threshold_factor,
        valley_distance=valley_distance,
        valley_avg_window=valley_avg_window,
        out_dir=None,
    )
    return preview.to_dict()
