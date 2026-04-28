@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0"
set "SUPPORT_SCRIPTS=%ROOT_DIR%Support Scripts"
set "START_SCRIPT=%SUPPORT_SCRIPTS%\start_kiwi.bat"
set "STOP_SCRIPT=%SUPPORT_SCRIPTS%\stop_kiwi.bat"
set "BOOTSTRAP_SCRIPT=%SUPPORT_SCRIPTS%\bootstrap_kiwi.bat"

if /I "%~1"=="--start" (
	shift
	call :run_start %*
	exit /b %errorlevel%
)

if /I "%~1"=="--stable" (
	call :run_start --stable
	exit /b %errorlevel%
)

if /I "%~1"=="--stop" (
	call :run_stop
	exit /b %errorlevel%
)

if /I "%~1"=="--setup" (
	call :run_setup
	exit /b %errorlevel%
)

if /I "%~1"=="--bootstrap" (
	call :run_setup
	exit /b %errorlevel%
)

echo ==================================================
echo  KIWI - START HERE
echo ==================================================
echo Choose an option:
echo [1] Start KIWI
echo [2] First-time setup
echo [3] Stop KIWI
echo [4] Exit
echo.

choice /C 1234 /N /M "Select 1-4: "
if errorlevel 4 goto :done
if errorlevel 3 (
	call :run_stop
	goto :done
)
if errorlevel 2 (
	call :run_setup
	goto :done
)
if errorlevel 1 (
	call :run_start
	goto :done
)

:run_start
if not exist "%START_SCRIPT%" (
	echo [ERROR] Missing script: %START_SCRIPT%
	exit /b 1
)
call "%START_SCRIPT%" %*
exit /b %errorlevel%

:run_stop
if not exist "%STOP_SCRIPT%" (
	echo [ERROR] Missing script: %STOP_SCRIPT%
	exit /b 1
)
call "%STOP_SCRIPT%"
exit /b %errorlevel%

:run_setup
if not exist "%BOOTSTRAP_SCRIPT%" (
	echo [ERROR] Missing script: %BOOTSTRAP_SCRIPT%
	exit /b 1
)
call "%BOOTSTRAP_SCRIPT%"
exit /b %errorlevel%

:done

endlocal
