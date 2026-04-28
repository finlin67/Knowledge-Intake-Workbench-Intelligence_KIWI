# KIWI Quick Start for Windows

## What KIWI does

KIWI helps you process document collections in repeatable batches, then export organized results for downstream tools.

Current release status: Windows local-first V1.

## Requirements

- Windows 10 or 11
- Node.js LTS (includes npm)
- Python 3.10+
- Optional: Ollama (only if you want local AI mode)

## Folder structure (what each folder is for)

- Parent KIWI folder: Start Here launcher and top-level docs.
- KIWI_Web: browser UI.
- kiwi_desktop: desktop/local backend and processing tooling.

## Optional EXE launcher

If you prefer an EXE over a BAT launcher, build it once from the parent folder:

```powershell
& ".\Support Scripts\build_launcher_exe.bat"
```

This creates KIWI Launcher.exe in the parent folder. It uses the same setup/start/stop flow as Start Here.bat.

## Start KIWI

If this is your first time using a fresh GitHub ZIP or clone, run this once first:

```powershell
& ".\Start Here.bat" --setup
```

1. Open the parent KIWI folder.
2. Double-click Start Here.bat.
3. Your default browser opens automatically to http://localhost:3000 (or open the URL shown in the script window).
4. Confirm Home/Setup shows Backend: Online.

Backend: Online means the local KIWI backend service is running and the UI can process actions.

## Stop KIWI

1. Run Start Here.bat and choose Stop KIWI.
2. Wait for the script to report KIWI stopped.

## First workflow

1. Save Project
2. Scan Batch
3. Run Batch
4. Start Next Batch

Example paths:

- Batches: C:\KIWI\batches\batch_001
- Exports: C:\KIWI\exports\project_001

## Troubleshooting

### Backend offline

- Re-run Start Here.bat.
- Confirm the backend health URL printed by the script opens.
- If needed, close old KIWI windows and rerun.

### Button looks stuck or inactive

- Refresh the browser once after changing batches.
- Confirm project is saved and the batch was scanned.

### Port already in use

- Run Start Here.bat and choose Stop KIWI first.
- Close other tools using port 3000 or 8000-8300.
- Start KIWI again.

### Ollama not running

- Ollama is optional.
- Use rules-only mode if Ollama is not available.
- If using Ollama, start it and retry.

### Scan finds 0 files

- Verify import base path and batch folder name.
- Confirm files exist in that folder.
- Retry Scan Batch.

## Need more detail?

- Full guide: Support Documents/USER_GUIDE.md
- Scenario walkthroughs: Support Documents/BEGINNER_WALKTHROUGHS.md
- GitHub overview: README.md
