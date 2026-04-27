@echo off
setlocal

set "ROOT_DIR=%~dp0"

echo ==================================================
echo Stopping KIWI...
echo ==================================================
echo.

set "FOUND_ANY=0"

echo Closing KIWI launcher windows...
taskkill /FI "WINDOWTITLE eq KIWI API*" /T /F >nul 2>&1
if not errorlevel 1 set "FOUND_ANY=1"
taskkill /FI "WINDOWTITLE eq KIWI Web*" /T /F >nul 2>&1
if not errorlevel 1 set "FOUND_ANY=1"

echo Checking fallback KIWI ports...
for %%R in (8000 8010 8100 8200 8300) do for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":%%R" ^| findstr "LISTENING"') do (
  call :maybe_kill_pid %%P "backend listener on port %%R"
)

for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do (
  call :maybe_kill_pid %%P "web listener on port 3000"
)

if "%FOUND_ANY%"=="0" (
  echo No KIWI processes were found.
) else (
  echo KIWI stopped.
)

echo.
echo You can now close this window.
pause
exit /b 0

:maybe_kill_pid
set "TARGET_PID=%~1"
set "TARGET_DESC=%~2"
set "KILL_DECISION="

for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process -Filter 'ProcessId=%TARGET_PID%' -ErrorAction SilentlyContinue; if (-not $p) { 'MISSING' } elseif (($p.Name -match '^(python|node|npm|cmd)\.exe$') -and ($p.CommandLine -like '*kiwi_desktop*' -or $p.CommandLine -like '*KIWI_Web*' -or $p.CommandLine -like '*api.main:app*' -or $p.CommandLine -like '*next dev*' -or $p.CommandLine -like '*start_kiwi.bat*')) { 'SAFE' } else { 'SKIP' }"`) do (
  set "KILL_DECISION=%%D"
)

if /I "%KILL_DECISION%"=="SAFE" (
  echo Stopping %TARGET_DESC% (PID %TARGET_PID%)...
  taskkill /PID %TARGET_PID% /F >nul 2>&1
  if not errorlevel 1 set "FOUND_ANY=1"
) else if /I "%KILL_DECISION%"=="SKIP" (
  echo Skipping PID %TARGET_PID% on %TARGET_DESC% ^(not identified as KIWI^).
)

exit /b 0
