@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "DESKTOP_DIR=%ROOT_DIR%kiwi_desktop"
set "WEB_DIR=%ROOT_DIR%KIWI_Web"
set "API_PORT="
set "BACKEND_MODE=dev"
set "UVICORN_RELOAD_ARG=--reload"

if /I "%~1"=="--stable" (
  set "BACKEND_MODE=stable"
  set "UVICORN_RELOAD_ARG="
)

if /I "%KIWI_STABLE_BACKEND%"=="1" (
  set "BACKEND_MODE=stable"
  set "UVICORN_RELOAD_ARG="
)

echo ==================================================
echo Starting KIWI...
echo ==================================================
echo.

echo Checking required folders...
if not exist "%DESKTOP_DIR%" (
  echo [ERROR] Missing folder: %DESKTOP_DIR%
  goto :fail
)

if not exist "%WEB_DIR%" (
  echo [ERROR] Missing folder: %WEB_DIR%
  goto :fail
)

if not exist "%DESKTOP_DIR%\api\main.py" (
  echo [ERROR] Missing backend entrypoint: %DESKTOP_DIR%\api\main.py
  goto :fail
)

if not exist "%WEB_DIR%\package.json" (
  echo [ERROR] Missing frontend package.json: %WEB_DIR%\package.json
  goto :fail
)

echo Checking Node.js...
where node >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js was not found.
  echo Install Node.js LTS, then try again.
  goto :fail
)

echo Checking npm...
where npm >nul 2>&1
if errorlevel 1 (
  echo [ERROR] npm was not found.
  echo Reinstall Node.js LTS, then try again.
  goto :fail
)

echo Checking Python...
where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python was not found.
  echo Install Python 3.10+ and ensure python is on PATH.
  goto :fail
)

echo Selecting API port...
for %%P in (8000 8010 8100 8200) do (
  powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort %%P -State Listen -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }" >nul 2>&1
  if not errorlevel 1 (
    set "API_PORT=%%P"
    goto :port_selected
  )
)

if not defined API_PORT set "API_PORT=8300"

:port_selected
echo Using backend API port: %API_PORT%
echo Backend mode: %BACKEND_MODE%
echo Starting backend...
start "KIWI API (port %API_PORT%)" cmd /k "cd /d "%DESKTOP_DIR%" && if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat" && python -m uvicorn api.main:app %UVICORN_RELOAD_ARG% --port %API_PORT%"

timeout /t 2 /nobreak >nul

echo Starting web app...
start "KIWI Web (port 3000)" cmd /k "cd /d "%WEB_DIR%" && set NEXT_PUBLIC_KIWI_API_BASE=http://127.0.0.1:%API_PORT% && npm run dev"

echo.
echo Open KIWI here: http://localhost:3000
echo Backend health: http://127.0.0.1:%API_PORT%/api/health
echo In Home/Setup, "Backend: Online" means the local KIWI API is reachable and ready.
echo.
echo Keep both terminal windows open while using KIWI.
echo Tip: run start_kiwi.bat --stable to disable backend auto-reload.
echo If something fails, copy this window text into a GitHub issue.
echo.
pause
exit /b 0

:fail
echo.
echo Startup failed. Fix the error above and try again.
echo If something fails, copy this window text into a GitHub issue.
echo.
pause
exit /b 1
