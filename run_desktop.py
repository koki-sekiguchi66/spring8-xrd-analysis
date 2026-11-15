# -*- coding: utf-8 -*-
"""Top-level launcher for XRD AutoFit Studio & DIC Utility (Desktop & PyInstaller .exe Entry Point)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# In PyInstaller windowed mode (console=False), sys.stdout and sys.stderr are None.
# Redirect them safely so logging/print/uvicorn never fail on NoneType.write.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

from backend.main import FRONTEND_DIST, app, launch_desktop, start_server


def main() -> int:
    parser = argparse.ArgumentParser(description="XRD AutoFit Studio & DIC Utility")
    parser.add_argument("--desktop", action="store_true", help="Launch Serverless Native Desktop App (default)")
    parser.add_argument("--server", action="store_true", help="Run as HTTP server instead of serverless desktop")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host for --server mode")
    parser.add_argument("--port", type=int, default=8000, help="Bind port for --server mode")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Verify bundled frontend/dist and scientific backend modules then exit 0",
    )
    args = parser.parse_args()

    if args.self_test:
        index_html = (FRONTEND_DIST / "index.html").resolve()
        if not index_html.exists():
            return 1
        from backend.desktop_bridge import DesktopBridge

        bridge = DesktopBridge(app)
        health = bridge.api_get("/api/health")
        sample_paths = bridge.api_get("/api/preprocess/sample-paths")
        if health.get("status") != "ok":
            return 2
        report_path = Path(sys.executable).resolve().parent / "selftest_ok.json" if getattr(sys, "frozen", False) else Path("selftest_ok.json")
        report_path.write_text(
            json.dumps(
                {
                    "status": "ok",
                    "frontend_index": str(index_html),
                    "health": health,
                    "sample_paths": sample_paths,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"[SELF-TEST OK] Frontend={index_html} | Health={health}")
        return 0

    if args.server:
        start_server(host=args.host, port=args.port)
    else:
        launch_desktop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
