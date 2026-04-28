@echo off
setlocal EnableExtensions

for %%I in ("%~dp0.") do set "SCRIPT_DIR=%%~fI"
for %%I in ("%SCRIPT_DIR%\..") do set "ROOT_DIR=%%~fI"
set "PY_EXE=%ROOT_DIR%\.venv\Scripts\python.exe"
set "LAUNCHER_SRC=%SCRIPT_DIR%\kiwi_launcher.py"
set "BUILD_DIR=%SCRIPT_DIR%\build"
set "DIST_DIR=%SCRIPT_DIR%\dist"
set "DIST_EXE=%SCRIPT_DIR%\dist\KIWI Launcher.exe"
set "FINAL_EXE=%ROOT_DIR%\KIWI Launcher.exe"

echo ==================================================
echo Building KIWI Launcher EXE...
echo ==================================================
echo.

if not exist "%LAUNCHER_SRC%" (
  echo [ERROR] Missing launcher source: %LAUNCHER_SRC%
  exit /b 1
)

if not exist "%PY_EXE%" (
  echo [ERROR] Missing Python virtual environment runtime: %PY_EXE%
  echo Run Start Here.bat and choose First-time setup, then try again.
  exit /b 1
)

echo Installing/updating PyInstaller in .venv ...
call "%PY_EXE%" -m pip install --upgrade pyinstaller
if errorlevel 1 exit /b 1

echo.
echo Building executable...
pushd "%SCRIPT_DIR%"
call "%PY_EXE%" -m PyInstaller --noconfirm --onefile --windowed --name "KIWI Launcher" --workpath "%BUILD_DIR%" --distpath "%DIST_DIR%" --specpath "%SCRIPT_DIR%" "kiwi_launcher.py"
set "BUILD_EXIT=%ERRORLEVEL%"
popd
if not "%BUILD_EXIT%"=="0" exit /b %BUILD_EXIT%

if not exist "%DIST_EXE%" (
  echo [ERROR] Build completed but executable was not found: %DIST_EXE%
  exit /b 1
)

copy /Y "%DIST_EXE%" "%FINAL_EXE%" >nul
if errorlevel 1 exit /b 1

echo.
echo Success: %FINAL_EXE%
echo You can now launch KIWI using KIWI Launcher.exe.
exit /b 0
