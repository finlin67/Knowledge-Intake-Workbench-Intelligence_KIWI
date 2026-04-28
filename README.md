# KIWI

- KIWI is a Windows local-first workflow for organizing large document sets into repeatable batches.
- KIWI is currently packaged as a Windows local-first V1 using Start Here.bat (recommended).
- The web UI is the primary operator interface. Desktop/local tooling supports the local processing workflow.
  
<img width="533" height="300" alt="image" src="https://github.com/user-attachments/assets/76272620-fa7c-41ab-b249-130545a1139d" />

## What is KIWI?

KIWI helps you process documents in predictable cycles:

- Save project settings once.
- Scan one batch folder at a time.
- Run Batch to classify and export files.
- Start Next Batch and repeat.

Exports are designed for downstream use in tools such as AnythingLLM and Open WebUI.

## Who is it for?

- Non-technical operators who need a repeatable batch workflow.
- Teams managing ongoing document intake.
- Users who want optional AI support, but still need rules-first processing.

## Current status

- Windows local-first V1 release path.
- Browser UI served from KIWI_Web.
- Local API/processing services served from kiwi_desktop.
- Started and stopped from the parent folder scripts.

## Repository structure

```text
KIWI/
  Start Here.bat
  README.md
  QUICK_START_WINDOWS.md
  Support Scripts/
    bootstrap_kiwi.bat
    start_kiwi.bat
    stop_kiwi.bat
    kiwi_launcher.py
    build_launcher_exe.bat
  Support Documents/
    .env.example
    KIWI.code-workspace
    USER_GUIDE.md
    BEGINNER_WALKTHROUGHS.md
    RELEASE_CHECKLIST.md
    RELEASE_WINDOWS_GUIDE.md
    DOCUMENTATION_MAP.md
  KIWI_Web/
  kiwi_desktop/
  sample_batches/
  sample_exports/
```

## How KIWI is organized

### KIWI_Web

- Next.js web interface.
- Main operator flow: Home/Setup, Settings, Triage, Inventory, Help.

### kiwi_desktop

- Local backend/API and processing services.
- Desktop/local tooling and deeper developer-facing internals.

### Shared launch scripts

- Start Here.bat: beginner-friendly launcher (recommended for most users).
- Support Scripts/start_kiwi.bat: starts backend and web services (advanced/direct use).
- Support Scripts/stop_kiwi.bat: stops KIWI windows/services with safe checks (advanced/direct use).

### Optional EXE launcher

If you prefer an executable launcher for non-technical users, you can build one from source:

```powershell
& ".\Support Scripts\build_launcher_exe.bat"
```

This creates KIWI Launcher.exe in the repository root. The EXE simply calls Start Here.bat with setup/start/stop flags, so it does not change KIWI runtime behavior.

## Requirements

- Windows 10 or 11
- Node.js 20+ (npm 10+ recommended)
- Python 3.11+ on PATH
- Optional: Ollama (for local AI mode)

## Get Started Install

If you downloaded a fresh ZIP or cloned the repo from GitHub, KIWI will not start until you install the Python and Node.js dependencies once.

### Fastest path: one-command bootstrap

From the repository root, run:

```powershell
& ".\Start Here.bat" --setup
```

This script will:

- create `.venv` if missing
- upgrade `pip`
- install `kiwi_desktop\requirements.txt`
- install `kiwi_desktop\api\requirements.txt`
- install `KIWI_Web` npm dependencies if `node_modules` is missing

If you want it to bootstrap and immediately launch KIWI after setup:

```powershell
& ".\Support Scripts\bootstrap_kiwi.bat" --start
```

If you want to force a fresh web dependency install:

```powershell
& ".\Support Scripts\bootstrap_kiwi.bat" --force-web
```

### 1. Download or clone the repository

- GitHub ZIP: download and extract the repository to a normal folder such as `C:\Tools\KIWI`
- Git clone:

```powershell
git clone https://github.com/finlin67/Knowledge-Intake-Workbench-Intelligence_KIWI.git
cd Knowledge-Intake-Workbench-Intelligence_KIWI
```

### 2. Manual setup path

Use this only if you do not want to use `Start Here.bat --setup`.

### 3. Create the Python virtual environment

From the repository root:

```powershell
py -3.11 -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run this once in the current terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

### 4. Install the Python dependencies

Install both the desktop/runtime dependencies and the API dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r kiwi_desktop\requirements.txt
python -m pip install -r kiwi_desktop\api\requirements.txt
```

Optional developer/test tools:

```powershell
python -m pip install -r kiwi_desktop\requirements-dev.txt
```

### 5. Install the web UI dependencies

In a new command prompt or in the same terminal:

```powershell
cd KIWI_Web
npm install
cd ..
```

### 6. Start KIWI

After the installs complete:

```powershell
& ".\Start Here.bat" --stable
```

Then open:

- `http://localhost:3000`

The startup flow will also auto-open your default browser to `http://localhost:3000`.
If you prefer not to auto-open, use:

```powershell
& ".\Support Scripts\start_kiwi.bat" --no-browser
```

You should also see a backend health URL printed by the script, such as:

- `http://127.0.0.1:8000/api/health`

### 7. Stop KIWI

When finished:

```powershell
& ".\Start Here.bat" --stop
```

## Fresh GitHub Download Troubleshooting

If `Start Here.bat` opens a browser window but KIWI does not work correctly, the most common cause is that one of these steps was skipped:

- `Start Here.bat --setup` was never run
- Python virtual environment was not created
- `kiwi_desktop\requirements.txt` was not installed
- `kiwi_desktop\api\requirements.txt` was not installed
- `KIWI_Web\npm install` was not run

Quick checks:

```powershell
Test-Path .\.venv\Scripts\python.exe
Test-Path KIWI_Web\node_modules
```

If either check returns `False`, the bootstrap install is incomplete.

## Can This Be Packaged As One Portable Install?

Yes, but the current repository is still a source checkout, not a fully portable release.

The cleanest packaging options are:

1. A Windows release ZIP that already includes:
  - a prebuilt `.venv`
  - installed `KIWI_Web\node_modules`
  - the launch scripts
2. A proper Windows installer using a packager such as Inno Setup or NSIS
3. A bundled desktop release where the Python backend and web frontend are shipped together as one app

For this repo today, the fastest path is still:

1. Create `.venv`
2. Install Python requirements
3. Run `npm install` in `KIWI_Web`
4. Launch with `Start Here.bat`

If you want a true one-click portable build, the next engineering step would be to add a release script that:

- creates the virtual environment automatically
- installs Python requirements automatically
- installs/builds the web app automatically
- outputs a distributable Windows folder or installer

## Quick Start for Windows

1. Open the parent KIWI folder.
2. Double-click Start Here.bat.
3. Open http://localhost:3000.
4. Confirm Home/Setup shows Backend: Online.
5. Use Save Project -> Scan Batch -> Run Batch.
6. When done, run Start Here.bat and choose Stop KIWI.

For beginner-first instructions, see QUICK_START_WINDOWS.md.

## Typical workflow

1. Save Project
2. Scan Batch
3. Run Batch
4. Start Next Batch

Repeat steps 2 to 4 for batch_002, batch_003, and so on.

## Project vs Batch explanation

- Project: persistent settings such as project name, export folder, export profile, and AI-related configuration.
- Batch: one import folder processed in a single cycle (for example batch_001).

Project settings persist across batches. Only the current batch folder changes.

## AI and workspace settings

- AI is optional. Rules-only mode works without Ollama or cloud keys.
- Configure provider/model in Settings if AI is enabled.
- Review workspace and keyword mappings early to improve match quality.

## Documentation map

- README.md: GitHub overview and repo orientation.
- QUICK_START_WINDOWS.md: fastest path for first run.
- Support Documents/USER_GUIDE.md: full operator guide.
- Support Documents/BEGINNER_WALKTHROUGHS.md: scenario-based step-by-step examples.
- Support Documents/DOCUMENTATION_MAP.md: where each doc belongs and who should use it.
- KIWI_Web/app/help/page.tsx: in-app help content.
- kiwi_desktop/docs/: deeper local tooling and architecture notes.

## Known limitations

- Windows is the primary supported path for V1 packaging.
- No installer/Docker default in this release.
- Very large archives should be split into manageable batches.
- If backend is offline, scan/run actions are unavailable.

## Roadmap

- Better first-run diagnostics
- Additional packaging options after V1
- Continued workflow polish for beginner operators

## Troubleshooting

- Backend offline: rerun Start Here.bat and check the printed backend health URL.
- Buttons look stuck after switching batches: refresh the browser once.
- Port conflict: run Start Here.bat and choose Stop KIWI, then start again.
- Ollama missing: continue in rules-only mode, or install/start Ollama.
- Scan returns 0 files: verify import base path and batch folder name.

## Contributing

- Keep changes small and focused.
- Do not commit secrets, private paths, or private datasets.
- Prefer beginner-friendly language in docs and UI copy.

If reporting issues, use the templates in .github/ISSUE_TEMPLATE/.
