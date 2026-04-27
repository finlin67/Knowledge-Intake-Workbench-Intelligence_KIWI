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

- Parent KIWI folder: launch scripts and top-level docs.
- KIWI_Web: browser UI.
- kiwi_desktop: desktop/local backend and processing tooling.

## Start KIWI

1. Open the parent KIWI folder.
2. Double-click start_kiwi.bat.
3. Open the URL shown in the script window (usually http://localhost:3000).
4. Confirm Home/Setup shows Backend: Online.

Backend: Online means the local KIWI backend service is running and the UI can process actions.

## Stop KIWI

1. Double-click stop_kiwi.bat.
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

- Re-run start_kiwi.bat.
- Confirm the backend health URL printed by the script opens.
- If needed, close old KIWI windows and rerun.

### Button looks stuck or inactive

- Refresh the browser once after changing batches.
- Confirm project is saved and the batch was scanned.

### Port already in use

- Run stop_kiwi.bat first.
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

- Full guide: USER_GUIDE.md
- Scenario walkthroughs: BEGINNER_WALKTHROUGHS.md
- GitHub overview: README.md
