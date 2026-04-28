@echo off
setlocal

set "ROOT_DIR=%~dp0"

echo ==================================================
echo Stopping KIWI...
echo ==================================================
echo.

echo Closing KIWI launcher windows...
taskkill /FI "WINDOWTITLE eq KIWI API*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq KIWI Web*" /T /F >nul 2>&1

echo Checking fallback KIWI ports and terminating matching processes...
powershell -NoProfile -Command "$ports = 3000,8000,8010,8100,8200,8300; $killed = 0; $listeners = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort } | Sort-Object OwningProcess -Unique; foreach ($conn in $listeners) { $procId = [int]$conn.OwningProcess; $proc = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $procId) -ErrorAction SilentlyContinue; if ($null -eq $proc) { continue }; $name = ($proc.Name + '').ToLowerInvariant(); $cmd = ($proc.CommandLine + '').ToLowerInvariant(); if (($name -match '^(python|node|npm|cmd)\.exe$') -and ($cmd -like '*kiwi_desktop*' -or $cmd -like '*kiwi_web*' -or $cmd -like '*api.main:app*' -or $cmd -like '*next dev*' -or $cmd -like '*start_kiwi.bat*')) { try { Stop-Process -Id $procId -Force -ErrorAction Stop; $killed++; Write-Output ('Stopped PID {0} (port {1})' -f $procId, $conn.LocalPort) } catch { } } }; if ($killed -eq 0) { Write-Output 'No KIWI listener processes were found.' }"

echo KIWI stop routine finished.

echo.
echo You can now close this window.
pause
exit /b 0
