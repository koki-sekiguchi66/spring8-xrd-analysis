# -*- coding: utf-8 -*-
"""Utility functions for strict file number extraction, sorting, and path handling."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

FILE_NUM_PATTERN = re.compile(r"(\d+)(?:bcg)?\.(?:csv|tth)$", re.IGNORECASE)


def get_bundle_root() -> Path:
    """Return the root directory containing bundled assets (`frontend/dist`, etc.)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parents[2]


def find_sample_data_root() -> Path:
    """Locate the `sample_data` directory across frozen .exe and source layouts."""
    candidates: List[Path] = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend([
            exe_dir / "sample_data",
            exe_dir.parent / "sample_data",
            exe_dir.parent.parent / "sample_data",
        ])
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(getattr(sys, "_MEIPASS")).resolve() / "sample_data")
    repo_root = Path(__file__).resolve().parents[2]
    candidates.append(repo_root / "sample_data")
    candidates.append(Path.cwd() / "sample_data")
    for cand in candidates:
        if cand.exists() and cand.is_dir():
            return cand
    return repo_root / "sample_data"


def extract_file_num(fname: str | Path) -> Optional[int]:
    """Extract integer file number strictly from the end of a .tth or bcg.csv filename.

    Addresses Bug #5: Replaces substring matching (`target_str in fname`) and
    fixed 4-char slicing (`[-4:]`) with strict regex matching.
    """
    name = fname.name if isinstance(fname, Path) else str(fname)
    match = FILE_NUM_PATTERN.search(name)
    if match:
        return int(match.group(1))
    return None


def list_sorted_tth_files(tth_dir: Path) -> List[Tuple[int, Path]]:
    """Return a list of (num, Path) sorted by integer file number for .tth files."""
    if not tth_dir.exists():
        return []
    items: List[Tuple[int, Path]] = []
    for p in tth_dir.iterdir():
        if p.is_file() and p.suffix.lower() == ".tth":
            num = extract_file_num(p.name)
            if num is not None:
                items.append((num, p))
    items.sort(key=lambda pair: (pair[0], pair[1].name))
    return items


def list_sorted_bcg_files(bcg_dir: Path) -> List[Tuple[int, Path]]:
    """Return a list of (num, Path) sorted by integer file number for *bcg.csv files."""
    if not bcg_dir.exists():
        return []
    items: List[Tuple[int, Path]] = []
    for p in bcg_dir.iterdir():
        if p.is_file() and p.name.lower().endswith("bcg.csv"):
            num = extract_file_num(p.name)
            if num is not None:
                items.append((num, p))
    items.sort(key=lambda pair: (pair[0], pair[1].name))
    return items


def find_file_by_num(files: List[Tuple[int, Path]], target_num: int) -> Tuple[int, Optional[Path]]:
    """Find index and path for exact integer file number `target_num` in sorted list.

    If exact match is not present, falls back to the closest available number.
    """
    if not files:
        return -1, None
    for idx, (num, path) in enumerate(files):
        if num == target_num:
            return idx, path
    # Closest match fallback
    closest_idx = min(range(len(files)), key=lambda i: abs(files[i][0] - target_num))
    return closest_idx, files[closest_idx][1]


def resolve_analyzed_folder(folder_path: str | Path) -> Path:
    """Resolve the analyzed specimen root directory from a user-supplied folder path.

    If the user selected a subfolder such as `tth/`, `bcg_removed_arpls/`, or `others/`,
    automatically resolves to the parent specimen directory so all output files
    (`_initial.xlsx`, `output.xlsx`, `bcg_removed_arpls/`) are placed in the analyzed specimen directory.
    """
    raw = Path(folder_path)
    if not raw.is_absolute() and not raw.exists():
        # Check relative to sample_data parent if user passed 'sample_data/...'
        sample_root = find_sample_data_root()
        alt = sample_root.parent / raw
        if alt.exists():
            raw = alt
    p = raw.resolve()
    if p.name.lower() in {"tth", "bcg_removed_arpls", "others"}:
        return p.parent
    return p


def infer_specimen_name(folder_path: str | Path) -> str:
    """Infer specimen name from the analyzed specimen folder name."""
    return resolve_analyzed_folder(folder_path).name
