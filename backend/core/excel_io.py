# -*- coding: utf-8 -*-
"""Excel I/O module for `(specimen)_initial.xlsx` and `(specimen)output.xlsx`.

Follows:
- Implementation Plan Section 3.3 (4), Section 4 (#4), Section 5 (Step 4)
- Unified output column order: `[num, 2th_{peak}, I_{peak}, wG_{peak}, wL_{peak}, FWHM_{peak}]`
- Professional formatting (Arial font, clean header styling, embedded summary charts)
- Safe fallback saving when file is locked in Excel (`PermissionError`).
"""

from __future__ import annotations

import io
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import openpyxl
from openpyxl.drawing.image import Image as OpenpyxlImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
import pandas as pd

from .origin_voigt import calc_origin_fwhm, wG_to_sigma, wL_to_gamma
from .utils import resolve_analyzed_folder

ARIAL_FONT = Font(name="Arial", size=10)
HEADER_FONT = Font(name="Arial", size=10, bold=True, color="FFFFFF")
SUBHEADER_FONT = Font(name="Arial", size=10, bold=True, color="1E293B")
HEADER_FILL = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
SUBHEADER_FILL = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
THIN_BORDER = Border(
    left=Side(style="thin", color="CBD5E1"),
    right=Side(style="thin", color="CBD5E1"),
    top=Side(style="thin", color="CBD5E1"),
    bottom=Side(style="thin", color="CBD5E1"),
)


def build_unified_columns(peaks: List[str]) -> List[str]:
    """Return unified column names for any fitting mode (Bug #4 + Item 7-3 residual output).

    Strictly `[num, 2th_{peak}, I_{peak}, wG_{peak}, wL_{peak}, FWHM_{peak}, ..., residual]`.
    """
    cols = ["num"]
    for pk in peaks:
        cols.extend([
            f"2th_{pk}",
            f"I_{pk}",
            f"wG_{pk}",
            f"wL_{pk}",
            f"FWHM_{pk}",
        ])
    cols.append("residual")
    return cols


def save_initial_excel(
    folder_path: str | Path,
    specimen_name: str,
    peaks_data: List[Dict[str, Any]],
    num_ratio_sets: int = 5,
) -> str:
    """Generate `(specimen_name)_initial.xlsx` with 2-row header blocks compatible with legacy scripts.

    Args:
        folder_path: Target specimen directory.
        specimen_name: Specimen identifier.
        peaks_data: List of dicts with keys:
            `peak_name` (str), `No` (int), `y0` (float), `xc` (float),
            `A` (float), `wG` (float), `wL` (float), `FWHM` (optional float).
        num_ratio_sets: Number of stacked initial rows to write for multi-row ratio search compatibility.
    Returns:
        Saved Excel file path as string.
    """
    root = resolve_analyzed_folder(folder_path)
    root.mkdir(parents=True, exist_ok=True)
    excel_path = root / f"{specimen_name}_initial.xlsx"

    # Group peaks by their source file number `No` so each `No` forms a 2-row header block
    grouped_by_no: Dict[int, List[Dict[str, Any]]] = {}
    for item in peaks_data:
        no_val = int(item.get("No", 50))
        grouped_by_no.setdefault(no_val, []).append(item)

    wb = openpyxl.Workbook()
    ws = wb.active
    sheet_title = f"{specimen_name}_initial"[:31]
    ws.title = sheet_title

    current_row = 1
    ratio_multipliers = [1.0, 0.90, 0.95, 1.05, 1.10]

    for no_val, items in sorted(grouped_by_no.items(), key=lambda kv: kv[0]):
        # Row 1 of block: Peak names at col 2, 8, 14, ... (every 6 columns)
        ws.cell(row=current_row, column=1, value=None)
        # Row 2 of block: 'No' at col 1, then ['y0', 'xc', 'A', 'wG', 'wL', 'FWHM'] repeated
        c_no = ws.cell(row=current_row + 1, column=1, value="No")
        c_no.font = SUBHEADER_FONT
        c_no.fill = SUBHEADER_FILL
        c_no.alignment = Alignment(horizontal="center")
        c_no.border = THIN_BORDER

        for idx, pk in enumerate(items):
            base_col = 2 + idx * 6
            pk_name = str(pk["peak_name"])
            c_main = ws.cell(row=current_row, column=base_col, value=pk_name)
            c_main.font = HEADER_FONT
            c_main.fill = HEADER_FILL
            c_main.alignment = Alignment(horizontal="center")

            sub_cols = ["y0", "xc", "A", "wG", "wL", "FWHM"]
            for offset, sh in enumerate(sub_cols):
                c_sub = ws.cell(row=current_row + 1, column=base_col + offset, value=sh)
                c_sub.font = SUBHEADER_FONT
                c_sub.fill = SUBHEADER_FILL
                c_sub.alignment = Alignment(horizontal="center")
                c_sub.border = THIN_BORDER

        # Write data rows (Row 1 is exact fit; Rows 2..num_ratio_sets provide slight R perturbations for 2PeaksRatio)
        has_pair = len(items) >= 2
        n_rows_to_write = max(1, num_ratio_sets) if has_pair else 1

        for r_idx in range(n_rows_to_write):
            data_row = current_row + 2 + r_idx
            c_num = ws.cell(row=data_row, column=1, value=int(no_val))
            c_num.font = ARIAL_FONT
            c_num.border = THIN_BORDER

            mult = ratio_multipliers[r_idx % len(ratio_multipliers)]
            for idx, pk in enumerate(items):
                base_col = 2 + idx * 6
                y0 = float(pk.get("y0", 0.0))
                xc = float(pk["xc"])
                A = float(pk["A"])
                # Perturb second peak slightly in extra rows so ratio2_fitter explores multiple initial R sets
                if r_idx > 0 and idx == 1:
                    A = A * mult
                wG = float(pk["wG"])
                wL = float(pk["wL"])
                fwhm = float(pk.get("FWHM") or calc_origin_fwhm(wG, wL))

                vals = [round(y0, 5), round(xc, 5), round(A, 5), round(wG, 5), round(wL, 5), round(fwhm, 5)]
                for offset, val in enumerate(vals):
                    cell = ws.cell(row=data_row, column=base_col + offset, value=val)
                    cell.font = ARIAL_FONT
                    cell.border = THIN_BORDER

        current_row += 2 + n_rows_to_write

    # Auto-fit column widths
    for col_idx in range(1, ws.max_column + 1):
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = 12

    try:
        wb.save(excel_path)
        return str(excel_path)
    except PermissionError:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback = root / f"{specimen_name}_initial_{ts}.xlsx"
        wb.save(fallback)
        return str(fallback)


def load_initial_excel(
    excel_path: str | Path,
    peaks: List[str],
    row_index: int = 1,
) -> Tuple[Dict[str, float], Dict[str, List[float]]]:
    """Read `(specimen_name)_initial.xlsx` with the 2-row header structure.

    Compatible with `import_initial_values(n, folder_path, N)` from the legacy scripts.
    `row_index` is 1-based offset from the `y0` subheader row.
    """
    path = Path(excel_path)
    if not path.exists():
        raise FileNotFoundError(f"Initial Excel file not found: {path}")

    temp_df = pd.read_excel(path, header=None, engine="openpyxl")
    temp_df_str = temp_df.astype(str)
    sub_header_marker = "y0"
    sub_header_indices = temp_df_str[
        temp_df_str.apply(lambda col: col.str.contains(sub_header_marker, na=False)).any(axis=1)
    ].index

    if len(sub_header_indices) == 0:
        raise ValueError(f"Sub-header marker '{sub_header_marker}' not found in {path}")

    all_peak_data: Dict[str, pd.DataFrame] = {}

    for i, sub_header_idx in enumerate(sub_header_indices):
        main_header_idx = sub_header_idx - 1
        start_row = sub_header_idx + 1
        end_row = sub_header_indices[i + 1] - 1 if (i + 1 < len(sub_header_indices)) else len(temp_df)

        main_header = temp_df.iloc[main_header_idx].ffill()
        sub_header = temp_df.iloc[sub_header_idx]
        data_block = temp_df.iloc[start_row:end_row]
        if data_block.empty:
            continue

        multi_index = pd.MultiIndex.from_arrays([main_header, sub_header])
        block_df = pd.DataFrame(data_block.values, columns=multi_index).dropna(axis=1, how="all")
        if block_df.empty or len(block_df.columns) == 0:
            continue

        no_col_series = None
        first_col_top, first_col_sub = block_df.columns[0]
        if pd.isna(first_col_top) and str(first_col_sub).strip() == "No":
            no_col_series = block_df.iloc[:, 0]

        for peak_name in block_df.columns.get_level_values(0).unique():
            if pd.notna(peak_name):
                peak_str = str(peak_name).strip()
                peak_df = block_df[peak_name].copy()
                if no_col_series is not None:
                    peak_df.insert(0, "No", no_col_series.values)
                cleaned = peak_df.dropna(how="all").reset_index(drop=True)
                if not cleaned.empty and peak_str not in all_peak_data:
                    all_peak_data[peak_str] = cleaned

    init_pars: Dict[str, float] = {}
    for idx, peak in enumerate(peaks):
        # Support alias matching (e.g. fcc111a -> fcc111, bcc101 -> bcc110, bcc112 -> bcc211)
        lookup_candidates = [peak]
        if peak.endswith("a"):
            lookup_candidates.append(peak[:-1])
        if peak == "bcc110":
            lookup_candidates.append("bcc101")
        elif peak == "bcc211":
            lookup_candidates.append("bcc112")
        elif peak == "bcc1102":
            lookup_candidates.extend(["bcc110", "bcc101"])

        matched_df = None
        for cand in lookup_candidates:
            if cand in all_peak_data:
                matched_df = all_peak_data[cand]
                break

        if matched_df is None or matched_df.empty:
            raise KeyError(f"Peak '{peak}' not found in {path.name} (available: {list(all_peak_data.keys())})")

        r_pos = min(max(0, row_index - 1), len(matched_df) - 1)
        row_vals = matched_df.iloc[r_pos]

        wG_val = float(row_vals["wG"])
        wL_val = float(row_vals["wL"])
        init_pars["num"] = float(row_vals["No"])
        init_pars[f"v{idx + 1}_center"] = float(row_vals["xc"])
        init_pars[f"v{idx + 1}_amplitude"] = float(row_vals["A"])
        init_pars[f"v{idx + 1}_sigma"] = wG_to_sigma(wG_val)
        init_pars[f"v{idx + 1}_gamma"] = wL_to_gamma(wL_val)

    param_names = ["center", "amplitude", "sigma", "gamma"]
    n_peaks = len(peaks)
    prev_params: Dict[str, List[float]] = {
        name: [float(init_pars[f"v{q}_{name}"]) for q in range(1, n_peaks + 1)]
        for name in param_names
    }
    return init_pars, prev_params


def _create_trend_chart_png(
    df: pd.DataFrame,
    peaks: List[str],
    history_R: Optional[List[float]] = None,
    history_residual: Optional[List[float]] = None,
    best_R: Optional[float] = None,
) -> bytes:
    """Render summary parameter trend plots (and R optimization history if present) to PNG bytes."""
    n_peaks = len(peaks)
    extra_row = 1 if (history_R and history_residual) else 0
    total_rows = 3 * n_peaks + extra_row

    fig, axes = plt.subplots(total_rows, 1, figsize=(7.5, 2.2 * total_rows), dpi=110)
    if total_rows == 1:
        axes = [axes]
    else:
        axes = list(np.ravel(axes))

    for idx, pk in enumerate(peaks):
        color = "#0284C7" if "fcc" in pk else "#D97706"
        ax_2th = axes[idx * 3 + 0]
        ax_I = axes[idx * 3 + 1]
        ax_fwhm = axes[idx * 3 + 2]

        ax_2th.plot(df["num"], df[f"2th_{pk}"], ".", color=color, markersize=4, label=f"2th_{pk}")
        ax_2th.set_ylabel("2theta (deg)")
        ax_2th.legend(loc="best", fontsize=8)
        ax_2th.grid(True, linestyle="--", alpha=0.4)

        ax_I.plot(df["num"], df[f"I_{pk}"], ".", color=color, markersize=4, label=f"I_{pk}")
        ax_I.set_ylabel("Area I (a.u.)")
        ax_I.legend(loc="best", fontsize=8)
        ax_I.grid(True, linestyle="--", alpha=0.4)

        ax_fwhm.plot(df["num"], df[f"FWHM_{pk}"], ".", color=color, markersize=4, label=f"FWHM_{pk}")
        ax_fwhm.set_ylabel("FWHM (deg)")
        ax_fwhm.set_xlabel("File Number (num)")
        ax_fwhm.legend(loc="best", fontsize=8)
        ax_fwhm.grid(True, linestyle="--", alpha=0.4)

    if extra_row and history_R and history_residual:
        ax_r = axes[-1]
        label = f"Residual History (best_R={best_R:.4f})" if best_R is not None else "Residual History"
        ax_r.plot(history_R, history_residual, "o-", color="#10B981", markersize=4, label=label)
        ax_r.set_xlabel("R value (I_v2 / I_v1)")
        ax_r.set_ylabel("Total Residual")
        ax_r.set_title("Intensity Ratio R Optimization History", fontsize=9)
        ax_r.legend(loc="best", fontsize=8)
        ax_r.grid(True, linestyle="--", alpha=0.4)

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _create_physics_chart_png(phys: Dict[str, Any]) -> bytes:
    """Render 3-panel physical metallurgy summary chart (Phase Fraction, Dislocation Density, Lattice Strain)."""
    nums = phys.get("nums", [])
    fig, axes = plt.subplots(3, 1, figsize=(8.0, 7.5), dpi=110)

    # 1. Phase Fraction
    ax0 = axes[0]
    ax0.plot(nums, phys.get("f_gamma", []), ".-", color="#0284C7", markersize=4, label="γ-FCC Fraction (f_γ)")
    ax0.plot(nums, phys.get("f_alpha_prime", []), ".-", color="#D97706", markersize=4, label="α'-BCC Martensite Fraction (f_α')")
    kin = phys.get("kinetics_fit")
    if kin and kin.get("fitted_curve"):
        ax0.plot(nums, kin["fitted_curve"], "--", color="#DC2626", lw=1.8, label="Olson-Cohen Fit")
    ax0.set_ylabel("Volume Fraction")
    ax0.set_ylim(-0.05, 1.05)
    ax0.set_title("Martensite Transformation & Phase Fraction Evolution", fontsize=10, fontweight="bold")
    ax0.legend(loc="best", fontsize=8)
    ax0.grid(True, linestyle="--", alpha=0.4)

    # 2. Dislocation Density
    ax1 = axes[1]
    rho_g = [v if v is not None else np.nan for v in phys.get("rho_gamma_m2", [])]
    rho_a = [v if v is not None else np.nan for v in phys.get("rho_alpha_prime_m2", [])]
    if not np.all(np.isnan(rho_g)):
        ax1.plot(nums, rho_g, "o-", color="#0284C7", markersize=3.5, label="γ-FCC Dislocation Density ρ_γ")
    if not np.all(np.isnan(rho_a)):
        ax1.plot(nums, rho_a, "s-", color="#D97706", markersize=3.5, label="α'-BCC Dislocation Density ρ_α'")
    ax1.set_yscale("log")
    ax1.set_ylabel("Dislocation Density (m^-2)")
    ax1.set_title("Dislocation Density Evolution per Phase", fontsize=10, fontweight="bold")
    ax1.legend(loc="best", fontsize=8)
    ax1.grid(True, linestyle="--", alpha=0.4)

    # 3. Elastic Lattice Strain
    ax2 = axes[2]
    strains = phys.get("lattice_strains_ue", {})
    for pk, s_vals in strains.items():
        clean_s = [v if v is not None else np.nan for v in s_vals]
        if not np.all(np.isnan(clean_s)):
            col = "#0284C7" if "fcc" in pk else "#D97706"
            ax2.plot(nums, clean_s, ".-", markersize=3, alpha=0.85, label=f"ε_{pk} (με)", color=col if len(strains) <= 2 else None)
    ax2.set_xlabel("File Number (num)")
    ax2.set_ylabel("Lattice Strain (με)")
    ax2.set_title("Elastic Lattice Strain Partitioning", fontsize=10, fontweight="bold")
    ax2.legend(loc="best", fontsize=8, ncol=2)
    ax2.grid(True, linestyle="--", alpha=0.4)

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def export_fitting_results_excel(
    out_path: str | Path,
    sheet_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Export one or more fitting sheets with unified column order and embedded plots to `output.xlsx`."""
    from .physics_analyzer import compute_physical_analysis

    raw_target = Path(out_path).resolve()
    analyzed_dir = resolve_analyzed_folder(raw_target.parent)
    analyzed_dir.mkdir(parents=True, exist_ok=True)
    target_path = analyzed_dir / raw_target.name

    # Prepare physical analysis data across all sheets
    groups_map = {
        str(item.get("sheet_name") or "".join(item["peaks"])): {
            "peaks": item["peaks"],
            "rows": item["rows"].to_dict(orient="records") if isinstance(item["rows"], pd.DataFrame) else item["rows"],
        }
        for item in sheet_results
    }
    phys_data: Optional[Dict[str, Any]] = None
    try:
        phys_data = compute_physical_analysis(groups_map)
    except Exception:
        phys_data = None

    def _write_to_path(p: Path) -> None:
        mode = "a" if p.exists() else "w"
        writer_kwargs: Dict[str, Any] = {"engine": "openpyxl", "mode": mode}
        if mode == "a":
            writer_kwargs["if_sheet_exists"] = "replace"

        with pd.ExcelWriter(p, **writer_kwargs) as writer:
            for item in sheet_results:
                peaks: List[str] = item["peaks"]
                sheet_name: str = str(item.get("sheet_name") or "".join(peaks))[:31]
                unified_cols = build_unified_columns(peaks)

                raw_rows = item["rows"]
                if isinstance(raw_rows, pd.DataFrame):
                    df = raw_rows[unified_cols].copy()
                else:
                    df = pd.DataFrame(raw_rows)
                    for c in unified_cols:
                        if c not in df.columns:
                            df[c] = np.nan
                    df = df[unified_cols].copy()

                df = df.sort_values("num").reset_index(drop=True)
                df.to_excel(writer, sheet_name=sheet_name, index=False)

                ws = writer.book[sheet_name]
                # Style header and data cells with Arial font
                for col_idx in range(1, len(unified_cols) + 1):
                    hdr_cell = ws.cell(row=1, column=col_idx)
                    hdr_cell.font = HEADER_FONT
                    hdr_cell.fill = HEADER_FILL
                    hdr_cell.alignment = Alignment(horizontal="center")
                    col_letter = get_column_letter(col_idx)
                    ws.column_dimensions[col_letter].width = 15

                for r_idx in range(2, len(df) + 2):
                    for col_idx in range(1, len(unified_cols) + 1):
                        c = ws.cell(row=r_idx, column=col_idx)
                        c.font = ARIAL_FONT

                # Embed trend & R-history chart PNG
                png_bytes = _create_trend_chart_png(
                    df=df,
                    peaks=peaks,
                    history_R=item.get("history_R"),
                    history_residual=item.get("history_residual"),
                    best_R=item.get("best_R"),
                )
                img = OpenpyxlImage(io.BytesIO(png_bytes))
                anchor_col = get_column_letter(len(unified_cols) + 2)
                ws.add_image(img, f"{anchor_col}2")

            # Also write Physical_Analysis sheet if available
            if phys_data and phys_data.get("summary_rows"):
                phys_df = pd.DataFrame(phys_data["summary_rows"])
                phys_sheet = "Physical_Analysis"
                phys_df.to_excel(writer, sheet_name=phys_sheet, index=False)
                ws_p = writer.book[phys_sheet]
                for col_idx in range(1, len(phys_df.columns) + 1):
                    hdr_cell = ws_p.cell(row=1, column=col_idx)
                    hdr_cell.font = HEADER_FONT
                    hdr_cell.fill = HEADER_FILL
                    hdr_cell.alignment = Alignment(horizontal="center")
                    ws_p.column_dimensions[get_column_letter(col_idx)].width = 18
                for r_idx in range(2, len(phys_df) + 2):
                    for col_idx in range(1, len(phys_df.columns) + 1):
                        ws_p.cell(row=r_idx, column=col_idx).font = ARIAL_FONT
                phys_png = _create_physics_chart_png(phys_data)
                img_p = OpenpyxlImage(io.BytesIO(phys_png))
                anchor_p = get_column_letter(len(phys_df.columns) + 2)
                ws_p.add_image(img_p, f"{anchor_p}2")

    used_fallback = False
    saved_path = target_path
    try:
        _write_to_path(target_path)
    except (PermissionError, OSError):
        used_fallback = True
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_path = target_path.with_name(f"{target_path.stem}_fallback_{ts}{target_path.suffix}")
        _write_to_path(saved_path)

    return {
        "saved_path": str(saved_path),
        "used_fallback": used_fallback,
        "sheets": [str(item.get("sheet_name") or "".join(item["peaks"]))[:31] for item in sheet_results],
    }
