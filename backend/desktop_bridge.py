# -*- coding: utf-8 -*-
"""Zero-Localhost Native Desktop IPC Bridge (`desktop_bridge.py`).

Provides direct in-process Python <-> PyWebView JavaScript communication (`window.pywebview.api`)
so the desktop application runs completely without any `localhost` / HTTP server / TCP port.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi.testclient import TestClient

from .api.routes_fitting import (
    BatchRunRequest,
    SESSION_STORE,
    _extract_bcc211_guide_from_session,
    _instantiate_fitter,
    _order_groups_for_bcc211_dependency,
    export_session_to_analyzed_directory,
)
from .api.routes_video import VideoExportRequest
from .core.fitters import FitStepPayload
from .core.utils import infer_specimen_name, resolve_analyzed_folder
from .core.video_exporter import export_videos_in_folder, save_frame_range_sec


class DesktopBridge:
    """Exposed as `window.pywebview.api` inside the native desktop window."""

    def __init__(self, app: Optional[Any] = None) -> None:
        if app is None:
            from .main import app as default_app
            app = default_app
        self._client = TestClient(app)
        self._window: Optional[Any] = None

    def attach_window(self, window: Any) -> None:
        self._window = window

    def _emit_js(self, callback_name: str, payload: Dict[str, Any]) -> None:
        if self._window is None:
            return
        try:
            serialized = json.dumps(payload, ensure_ascii=False)
            js_code = f"if (window.{callback_name}) {{ window.{callback_name}({serialized}); }}"
            self._window.evaluate_js(js_code)
        except Exception:
            pass

    def api_get(self, url: str) -> Dict[str, Any]:
        """Execute a GET request in-process without any network or localhost socket."""
        res = self._client.get(url)
        if res.status_code >= 400:
            detail = f"Error {res.status_code}"
            try:
                detail = res.json().get("detail", detail)
            except Exception:
                pass
            raise RuntimeError(str(detail))
        return res.json()

    def api_post(self, url: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a POST request in-process without any network or localhost socket."""
        res = self._client.post(url, json=body)
        if res.status_code >= 400:
            detail = f"Error {res.status_code}"
            try:
                detail = res.json().get("detail", detail)
            except Exception:
                pass
            raise RuntimeError(str(detail))
        return res.json()

    def start_fitting_stream(self, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Start continuous XRD Voigt fitting in a background worker thread and push events via JS."""

        def _worker() -> None:
            try:
                req = BatchRunRequest(**raw_payload)
                root = resolve_analyzed_folder(req.folder_path)
                bcg_dir = root / "bcg_removed_arpls"
                if not bcg_dir.exists():
                    raise FileNotFoundError(f"bcg_removed_arpls directory not found in {root}")

                specimen = req.specimen_name or infer_specimen_name(root)
                SESSION_STORE["folder_path"] = str(root)
                SESSION_STORE["specimen_name"] = specimen
                SESSION_STORE["groups"] = {}

                ordered_groups = _order_groups_for_bcc211_dependency(req.groups)
                total_groups = len(ordered_groups)
                summary_groups: Dict[str, Any] = {}

                for g_idx, cfg in enumerate(ordered_groups):
                    bcc211_guide = _extract_bcc211_guide_from_session(SESSION_STORE["groups"])
                    fitter = _instantiate_fitter(bcg_dir, cfg, bcc211_guide_by_num=bcc211_guide)
                    n_files = len(fitter.files)
                    emit_stride = max(1, n_files // 45)

                    self._emit_js(
                        "__onDesktopFittingEvent",
                        {
                            "type": "group_start",
                            "group_index": g_idx,
                            "total_groups": total_groups,
                            "group_id": cfg.group_id,
                            "engine": fitter.engine_name,
                            "dimt_onset_num": cfg.dimt_onset_num,
                            "peaks": fitter.peaks,
                            "total_files": n_files,
                        },
                    )

                    def _on_progress(step: FitStepPayload) -> None:
                        include_wf = (
                            step.completed_files == 1
                            or step.completed_files == step.total_files
                            or step.is_outlier
                            or (step.completed_files % emit_stride == 0)
                        )
                        msg = {
                            "type": "step",
                            "group_index": g_idx,
                            "total_groups": total_groups,
                            **step.to_stream_dict(include_waveform=include_wf),
                        }
                        self._emit_js("__onDesktopFittingEvent", msg)

                    res = fitter.run_all(step_callback=_on_progress)
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

                    self._emit_js(
                        "__onDesktopFittingEvent",
                        {
                            "type": "group_complete",
                            "group_index": g_idx,
                            "total_groups": total_groups,
                            "group_summary": summary_groups[cfg.group_id],
                        },
                    )

                saved_output_path = ""
                try:
                    auto_exp = export_session_to_analyzed_directory(
                        folder_path=str(root),
                        specimen_name=specimen,
                    )
                    saved_output_path = auto_exp.get("saved_path", "")
                except Exception:
                    saved_output_path = str(root / f"{specimen}output.xlsx")

                self._emit_js(
                    "__onDesktopFittingEvent",
                    {
                        "type": "all_complete",
                        "folder_path": str(root),
                        "specimen_name": specimen,
                        "saved_output_path": saved_output_path,
                        "groups": summary_groups,
                    },
                )
            except Exception as e:
                self._emit_js("__onDesktopFittingEvent", {"type": "error", "detail": str(e)})

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        return {"status": "started"}

    def start_video_export_stream(self, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Start DIC video frame extraction in a background worker thread and push events via JS."""

        def _worker() -> None:
            try:
                req = VideoExportRequest(**raw_payload)
                p = Path(req.target_path).resolve()
                if req.mode == "single":
                    out_dir = Path(req.output_dir).resolve() if req.output_dir else (p.parent / p.stem)
                    bname = req.basename if req.basename else f"{p.stem}_img"

                    def _on_progress(cur: int, tot: int, fpath: str) -> None:
                        self._emit_js(
                            "__onDesktopVideoEvent",
                            {
                                "type": "progress",
                                "current": cur,
                                "total": tot,
                                "progress_pct": round(100.0 * cur / max(1, tot), 1),
                                "video_name": p.name,
                                "last_file": fpath,
                            },
                        )

                    res = save_frame_range_sec(
                        video_path=p,
                        start_sec=req.start_sec,
                        stop_sec=req.stop_sec,
                        step_sec=req.step_sec,
                        dir_path=out_dir,
                        basename=bname,
                        ext=req.ext,
                        progress_callback=_on_progress,
                    )
                else:
                    out_root = Path(req.output_dir).resolve() if req.output_dir else p
                    suffix = req.basename if req.basename else "_img"

                    def _on_folder_progress(v_idx: int, v_tot: int, vname: str, fpath: str) -> None:
                        self._emit_js(
                            "__onDesktopVideoEvent",
                            {
                                "type": "progress",
                                "current": v_idx,
                                "total": v_tot,
                                "progress_pct": round(100.0 * v_idx / max(1, v_tot), 1),
                                "video_name": vname,
                                "last_file": fpath,
                            },
                        )

                    res = export_videos_in_folder(
                        folder_path=p,
                        start_sec=req.start_sec,
                        stop_sec=req.stop_sec,
                        step_sec=req.step_sec,
                        output_root_dir=out_root,
                        basename_suffix=suffix,
                        ext=req.ext,
                        progress_callback=_on_folder_progress,
                    )

                self._emit_js(
                    "__onDesktopVideoEvent",
                    {
                        "type": "complete",
                        "mode": req.mode,
                        **res,
                    },
                )
            except Exception as e:
                self._emit_js("__onDesktopVideoEvent", {"type": "error", "detail": str(e)})

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        return {"status": "started"}
