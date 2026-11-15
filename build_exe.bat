@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0"

echo ============================================================================
echo   XRD AutoFit Studio ^& DIC Utility — Standalone .exe Package Builder
echo ============================================================================

if exist "C:\Users\sekig\AppData\Local\Programs\node-v22.23.5-win-x64\npm.cmd" (
    set "PATH=C:\Users\sekig\AppData\Local\Programs\node-v22.23.5-win-x64;%PATH%"
)

echo [1/3] Building Frontend Production Assets (frontend/dist)...
pushd frontend
call npm run build
if errorlevel 1 (
    popd
    echo [ERROR] Frontend build failed.
    exit /b 1
)
popd

echo [2/3] Packaging Standalone Windows Application (.exe) with PyInstaller...
".\.venv\Scripts\pyinstaller.exe" --noconfirm --clean XRD_AutoFit_Studio.spec
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    exit /b 1
)

echo [3/3] Verifying Packaged Executable...
".\dist\XRD_AutoFit_Studio\XRD_AutoFit_Studio.exe" --self-test
if errorlevel 1 (
    echo [WARNING] Self-test returned non-zero code.
)

echo ============================================================================
echo   [COMPLETE] Distributable package created at:
echo   %CD%\dist\XRD_AutoFit_Studio\XRD_AutoFit_Studio.exe
echo   ^(Zip the 'dist\XRD_AutoFit_Studio' folder to distribute to other PCs^)
echo ============================================================================
endlocal
