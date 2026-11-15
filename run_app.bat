@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0"

echo ============================================================================
echo   XRD AutoFit Studio ^& DIC Utility — Native Desktop Application
echo   Zero-Localhost / Direct IPC Mode
echo ============================================================================

if exist "dist\XRD_AutoFit_Studio\XRD_AutoFit_Studio.exe" (
    echo [INFO] Launching packaged standalone executable: dist\XRD_AutoFit_Studio\XRD_AutoFit_Studio.exe
    start "" "dist\XRD_AutoFit_Studio\XRD_AutoFit_Studio.exe"
    exit /b 0
)

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment not found at .venv\Scripts\python.exe
    pause
    exit /b 1
)

if not exist "frontend\dist\index.html" (
    echo [INFO] Building frontend production bundle...
    if exist "C:\Users\sekig\AppData\Local\Programs\node-v22.23.5-win-x64\npm.cmd" (
        set "PATH=C:\Users\sekig\AppData\Local\Programs\node-v22.23.5-win-x64;%PATH%"
    )
    pushd frontend
    call npm run build
    popd
)

echo [INFO] Launching Native Windows Desktop Window...
".venv\Scripts\python.exe" run_desktop.py --desktop
endlocal
