$ErrorActionPreference = "Stop"

param(
    [string]$BackendRoot = $env:KIWI_BACKEND_ROOT,
    [string]$BackendRelativePath = "",
    [switch]$SkipBackend
)

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspaceParent = Split-Path -Parent $projectRoot
$frontendCommand = @"
cd "$projectRoot"
npm run dev
"@

function Test-BackendRoot([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    $apiMain = Join-Path $Path "api\main.py"
    $servicesProject = Join-Path $Path "services\project_service.py"
    $pythonExe = Join-Path $Path ".venv\Scripts\python.exe"
    return (Test-Path $apiMain) -and (Test-Path $servicesProject) -and (Test-Path $pythonExe)
}

function Resolve-BackendRoot() {
    if (-not [string]::IsNullOrWhiteSpace($BackendRoot)) {
        return $BackendRoot
    }

    if (-not [string]::IsNullOrWhiteSpace($BackendRelativePath)) {
        return (Join-Path $workspaceParent $BackendRelativePath)
    }

    $candidates = Get-ChildItem -Path $workspaceParent -Directory | Where-Object {
        $_.FullName -ne $projectRoot -and (Test-BackendRoot $_.FullName)
    }

    if ($candidates.Count -eq 1) {
        return $candidates[0].FullName
    }

    if ($candidates.Count -gt 1) {
        Write-Host "Backend auto-discovery found multiple candidates:" -ForegroundColor Yellow
        $candidates | ForEach-Object { Write-Host " - $($_.FullName)" -ForegroundColor Yellow }
    }

    return ""
}

Write-Host "Starting KIWI frontend..." -ForegroundColor Cyan

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", $frontendCommand
)

if (-not $SkipBackend) {
    $resolvedBackendRoot = Resolve-BackendRoot
    if ([string]::IsNullOrWhiteSpace($resolvedBackendRoot)) {
        Write-Host "Backend not started: pass -BackendRoot <path>, set KIWI_BACKEND_ROOT, or place backend as a sibling folder with api/main.py + services/project_service.py." -ForegroundColor Yellow
    } else {
        $backendPython = Join-Path $resolvedBackendRoot ".venv\Scripts\python.exe"
        $backendApiRoot = Join-Path $resolvedBackendRoot "api"
        $backendMain = Join-Path $backendApiRoot "main.py"

        if (-not (Test-Path $backendPython)) {
            Write-Host "Backend not started: missing '$backendPython'." -ForegroundColor Yellow
        } elseif (-not (Test-Path $backendMain)) {
            Write-Host "Backend not started: missing '$backendMain'." -ForegroundColor Yellow
        } else {
            Write-Host "Starting KIWI backend from '$resolvedBackendRoot'..." -ForegroundColor Cyan
            $backendCommand = @"
cd "$backendApiRoot"
& "$backendPython" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
"@
            Start-Process powershell -ArgumentList @(
                "-NoExit",
                "-ExecutionPolicy", "Bypass",
                "-Command", $backendCommand
            )
        }
    }
}

Write-Host "Done. Frontend: http://localhost:3000  Backend: http://127.0.0.1:8000" -ForegroundColor Green
