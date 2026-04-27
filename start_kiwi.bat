@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "DESKTOP_DIR=%ROOT_DIR%kiwi_desktop"
set "WEB_DIR=%ROOT_DIR%KIWI_Web"
set "BOOTSTRAP_SCRIPT=%ROOT_DIR%bootstrap_kiwi.bat"
set "ROOT_VENV_PY=%ROOT_DIR%.venv\Scripts\python.exe"
set "DESKTOP_VENV_PY=%DESKTOP_DIR%\.venv\Scripts\python.exe"
set "PYTHON_EXE="
set "API_PORT="
set "BACKEND_MODE=dev"
set "UVICORN_RELOAD_ARG=--reload"
set "BOOTSTRAP_REASON="

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

if not exist "%ROOT_VENV_PY%" if not exist "%DESKTOP_VENV_PY%" (
  set "BOOTSTRAP_REASON=the Python virtual environment (.venv)"
)

if not exist "%WEB_DIR%\node_modules" (
  if defined BOOTSTRAP_REASON (
    set "BOOTSTRAP_REASON=%BOOTSTRAP_REASON% and the web dependencies (KIWI_Web\node_modules)"
  ) else (
    set "BOOTSTRAP_REASON=the web dependencies (KIWI_Web\node_modules)"
  )
)

if defined BOOTSTRAP_REASON (
  call :offer_bootstrap
  if errorlevel 1 goto :fail
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

echo Resolving Python runtime...
if exist "%ROOT_VENV_PY%" (
  set "PYTHON_EXE=%ROOT_VENV_PY%"
  echo Using root virtual environment Python: %ROOT_VENV_PY%
) else if exist "%DESKTOP_VENV_PY%" (
  set "PYTHON_EXE=%DESKTOP_VENV_PY%"
  echo Using kiwi_desktop virtual environment Python: %DESKTOP_VENV_PY%
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] Python was not found.
    echo Install Python 3.11+ and ensure python is on PATH.
    goto :fail
  )
  set "PYTHON_EXE=python"
  echo Using system Python from PATH.
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
start "KIWI API (port %API_PORT%)" cmd /k "cd /d "%DESKTOP_DIR%" && "%PYTHON_EXE%" -m uvicorn api.main:app %UVICORN_RELOAD_ARG% --port %API_PORT%"

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

:offer_bootstrap
echo Setup looks incomplete.
echo Missing or not yet prepared: %BOOTSTRAP_REASON%
echo.

if not exist "%BOOTSTRAP_SCRIPT%" (
  echo [ERROR] Missing bootstrap helper: %BOOTSTRAP_SCRIPT%
  exit /b 1
)

choice /C YN /N /M "Run bootstrap_kiwi.bat now? [Y/N]: "
if errorlevel 2 (
  echo.
  echo Startup cancelled. Run bootstrap_kiwi.bat first, then start_kiwi.bat.
  exit /b 1
)

echo.
call "%BOOTSTRAP_SCRIPT%"
if errorlevel 1 exit /b 1

echo.
echo Bootstrap completed. Continuing startup...
echo.
exit /b 0

:fail
echo.
echo Startup failed. Fix the error above and try again.
echo If something fails, copy this window text into a GitHub issue.
echo.
pause
exit /b 1
