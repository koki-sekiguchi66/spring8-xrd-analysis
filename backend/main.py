# -*- coding: utf-8 -*-
"""Zero-Localhost Native Desktop Entry Point (PyWebView + Direct IPC Bridge) & FastAPI Application."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Ensure repo root is importable when invoked as `python backend/main.py`
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.api.routes_fitting import router as fitting_router
from backend.api.routes_initial import router as initial_router
from backend.api.routes_preprocess import router as preprocess_router
from backend.api.routes_video import router as video_router
from backend.core.utils import get_bundle_root
from backend.desktop_bridge import DesktopBridge

app = FastAPI(
    title="XRD AutoFit Studio & DIC Utility",
    description="Metastable Austenitic Steel In-situ XRD Automated Analysis & DIC Video Frame Extractor",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(preprocess_router)
app.include_router(initial_router)
app.include_router(fitting_router)
app.include_router(video_router)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "app": "XRD AutoFit Studio & DIC Utility",
        "version": "2.0.0",
        "mode": "desktop-serverless-ready",
    }


BUNDLE_ROOT = get_bundle_root()
FRONTEND_DIST = BUNDLE_ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(FRONTEND_DIST / "index.html"))


def start_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    uvicorn.run(app, host=host, port=port, log_level="info")


def launch_desktop() -> None:
    """Launch native Windows 11 desktop application with ZERO localhost / ZERO TCP ports.

    Loads `frontend/dist/index.html` directly from local disk via `file://` and communicates
    with Python in-process via PyWebView's `js_api` (`window.pywebview.api`).
    """
    os.environ.setdefault("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--allow-file-access-from-files")
    index_html = (FRONTEND_DIST / "index.html").resolve()
    if not index_html.exists():
        raise FileNotFoundError(f"Built frontend bundle not found at {index_html}. Run `npm run build` in frontend/.")

    import webview

    bridge = DesktopBridge(app)
    window = webview.create_window(
        "XRD AutoFit Studio & DIC Utility — SPring-8 In-situ Desktop Suite",
        url=index_html.as_uri(),
        js_api=bridge,
        width=1620,
        height=980,
        min_size=(1280, 800),
        background_color="#09090B",
        text_select=True,
    )
    bridge.attach_window(window)
    webview.start(debug=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="XRD AutoFit Studio & DIC Utility")
    parser.add_argument("--desktop", action="store_true", help="Launch Serverless Native Desktop App (default)")
    parser.add_argument("--server", action="store_true", help="Run as HTTP server instead of serverless desktop")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host for --server mode")
    parser.add_argument("--port", type=int, default=8000, help="Bind port for --server mode")
    args = parser.parse_args()

    if args.server:
        start_server(host=args.host, port=args.port)
    else:
        launch_desktop()
