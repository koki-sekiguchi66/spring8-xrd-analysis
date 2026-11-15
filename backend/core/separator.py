# -*- coding: utf-8 -*-
"""Stage 1: Directory recognition and automatic .tth / others separation.

Fixes Bug #6/#7:
- Removes the `< 50` files restriction so small test datasets work reliably.
- Ensures idempotency: if `tth/` already contains `.tth` files and no loose `.tth`
  files remain in the specimen directory, skips redundant moves.
- Preserves generated analysis Excel files (`*_initial.xlsx`, `*output*.xlsx`) in
  the specimen root directory.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List

from .utils import list_sorted_tth_files, resolve_analyzed_folder

EXCLUDED_DIRS = {"tth", "others", "bcg_removed_arpls", "__pycache__", ".git"}


@dataclass
class SeparationResult:
    folder_path: str
    tth_dir: str
    others_dir: str
    already_separated: bool
    moved_tth_count: int
    moved_others_count: int
    total_tth_count: int
    tth_nums: List[int]


def _should_keep_in_root(filename: str) -> bool:
    """Keep Excel output/initial files in the specimen root directory."""
    lower = filename.lower()
    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        return True
    if lower.endswith("_initial.csv"):
        return True
    return False


def separate_directory(folder_path: str | Path) -> SeparationResult:
    """Separate `.tth` files into `tth/` and other measurement files into `others/`.

    Works on a single specimen folder (no `< 50` file count limit) and is idempotent.
    """
    root = resolve_analyzed_folder(folder_path)
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Directory does not exist: {root}")

    tth_target_dir = root / "tth"
    others_target_dir = root / "others"

    # Check loose files in root (and any non-excluded subfolders)
    loose_tth: List[Path] = []
    loose_others: List[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        current_dir = Path(dirpath).resolve()
        # Prune excluded directories from traversal
        dirnames[:] = [
            d for d in dirnames
            if d not in EXCLUDED_DIRS
            and (current_dir / d).resolve() not in {tth_target_dir.resolve(), others_target_dir.resolve()}
        ]
        if current_dir in {tth_target_dir.resolve(), others_target_dir.resolve()}:
            continue
        if current_dir.name in EXCLUDED_DIRS:
            continue

        for fname in filenames:
            src = current_dir / fname
            if fname.lower().endswith(".tth"):
                loose_tth.append(src)
            elif not _should_keep_in_root(fname):
                loose_others.append(src)

    existing_tth = list_sorted_tth_files(tth_target_dir)
    if existing_tth and len(loose_tth) == 0:
        tth_target_dir.mkdir(exist_ok=True)
        others_target_dir.mkdir(exist_ok=True)
        return SeparationResult(
            folder_path=str(root),
            tth_dir=str(tth_target_dir),
            others_dir=str(others_target_dir),
            already_separated=True,
            moved_tth_count=0,
            moved_others_count=0,
            total_tth_count=len(existing_tth),
            tth_nums=[num for num, _ in existing_tth],
        )

    tth_target_dir.mkdir(exist_ok=True)
    others_target_dir.mkdir(exist_ok=True)

    moved_tth = 0
    moved_others = 0

    for src in loose_tth:
        dst = tth_target_dir / src.name
        if src.resolve() != dst.resolve():
            if dst.exists():
                dst.unlink()
            shutil.move(str(src), str(dst))
            moved_tth += 1

    for src in loose_others:
        dst = others_target_dir / src.name
        if src.resolve() != dst.resolve():
            if dst.exists():
                dst.unlink()
            shutil.move(str(src), str(dst))
            moved_others += 1

    final_tth = list_sorted_tth_files(tth_target_dir)
    return SeparationResult(
        folder_path=str(root),
        tth_dir=str(tth_target_dir),
        others_dir=str(others_target_dir),
        already_separated=False,
        moved_tth_count=moved_tth,
        moved_others_count=moved_others,
        total_tth_count=len(final_tth),
        tth_nums=[num for num, _ in final_tth],
    )
