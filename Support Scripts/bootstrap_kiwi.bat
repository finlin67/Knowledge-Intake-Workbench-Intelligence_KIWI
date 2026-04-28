@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI\"
set "DESKTOP_DIR=%ROOT_DIR%kiwi_desktop"
set "WEB_DIR=%ROOT_DIR%KIWI_Web"
set "VENV_DIR=%ROOT_DIR%.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "START_SCRIPT=%SCRIPT_DIR%start_kiwi.bat"
set "BOOTSTRAP_PY="
set "START_AFTER=0"
set "FORCE_WEB_INSTALL=0"

:parse_args
if "%~1"=="" goto :args_done
if /I "%~1"=="--start" (
  set "START_AFTER=1"
  shift
  goto :parse_args
)
if /I "%~1"=="--force-web" (
  set "FORCE_WEB_INSTALL=1"
  shift
  goto :parse_args
)
echo [ERROR] Unsupported argument: %~1
echo Supported arguments: --start  --force-web
exit /b 1

:args_done
echo ==================================================
echo Bootstrapping KIWI...
echo ==================================================
echo.

if not exist "%DESKTOP_DIR%" (
  echo [ERROR] Missing folder: %DESKTOP_DIR%
  goto :fail
)

if not exist "%WEB_DIR%" (
  echo [ERROR] Missing folder: %WEB_DIR%
  goto :fail
)

if not exist "%DESKTOP_DIR%\requirements.txt" (
  echo [ERROR] Missing file: %DESKTOP_DIR%\requirements.txt
  goto :fail
)

if not exist "%DESKTOP_DIR%\api\requirements.txt" (
  echo [ERROR] Missing file: %DESKTOP_DIR%\api\requirements.txt
  goto :fail
)

if not exist "%WEB_DIR%\package.json" (
  echo [ERROR] Missing file: %WEB_DIR%\package.json
  goto :fail
)

echo Checking Node.js...
where node >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js was not found.
  echo Install Node.js 20+ first, then rerun bootstrap_kiwi.bat.
  goto :fail
)

echo Checking npm...
where npm >nul 2>&1
if errorlevel 1 (
  echo [ERROR] npm was not found.
  echo Reinstall Node.js so npm is available, then rerun bootstrap_kiwi.bat.
  goto :fail
)

echo Resolving Python bootstrap runtime...
where py >nul 2>&1
if not errorlevel 1 (
  py -3.11 -c "import sys; sys.exit(0)" >nul 2>&1
  if not errorlevel 1 (
    set "BOOTSTRAP_PY=py -3.11"
    echo Using Python launcher: py -3.11
  )
)

if not defined BOOTSTRAP_PY (
  where python >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] Python was not found.
    echo Install Python 3.11+ and ensure python or py is on PATH.
    goto :fail
  )
  set "BOOTSTRAP_PY=python"
  echo Using Python from PATH.
)

if not exist "%VENV_PY%" (
  echo Creating virtual environment in .venv ...
  call %BOOTSTRAP_PY% -m venv "%VENV_DIR%"
  if errorlevel 1 goto :fail
) else (
  echo Reusing existing virtual environment: %VENV_DIR%
)

if not exist "%VENV_PY%" (
  echo [ERROR] Virtual environment creation failed: %VENV_PY% not found.
  goto :fail
)

echo.
echo Upgrading pip...
call "%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo.
echo Installing KIWI desktop/runtime requirements...
call "%VENV_PY%" -m pip install -r "%DESKTOP_DIR%\requirements.txt"
if errorlevel 1 goto :fail

echo.
echo Installing KIWI API requirements...
call "%VENV_PY%" -m pip install -r "%DESKTOP_DIR%\api\requirements.txt"
if errorlevel 1 goto :fail

echo.
if exist "%WEB_DIR%\node_modules" (
  if "%FORCE_WEB_INSTALL%"=="1" (
    echo Reinstalling KIWI web dependencies because --force-web was supplied...
    pushd "%WEB_DIR%"
    call npm install
    if errorlevel 1 (
      popd
      goto :fail
    )
    popd
  ) else (
    echo Reusing existing KIWI web dependencies: %WEB_DIR%\node_modules
  )
) else (
  echo Installing KIWI web dependencies...
  pushd "%WEB_DIR%"
  call npm install
  if errorlevel 1 (
    popd
    goto :fail
  )
  popd
)

echo.
echo ==================================================
echo KIWI bootstrap complete.
echo ==================================================
echo.
echo Next step: run Start Here.bat and choose Start KIWI
echo.

if "%START_AFTER%"=="1" (
  echo Launching KIWI now...
  call "%START_SCRIPT%" --stable
  exit /b %errorlevel%
)

exit /b 0

:fail
echo.
echo Bootstrap failed. Fix the error above and rerun Start Here.bat, then choose First-time setup.
exit /b 1