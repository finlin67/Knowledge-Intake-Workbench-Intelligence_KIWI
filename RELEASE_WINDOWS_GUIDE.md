# Windows Release Guide (GitHub)

This guide explains how to publish KIWI on GitHub so non-technical users can download a ZIP and run it with minimal setup.

## What users should do

1. Open the latest GitHub Release.
2. Download `KIWI-windows-portable-<version>.zip`.
3. Extract it.
4. Double-click `start_kiwi.bat`.
5. Open `http://localhost:3000` in a browser.

## Maintainer workflow

The repository includes a GitHub Actions workflow:

- `.github/workflows/windows-release.yml`

It creates a portable ZIP and publishes it to Releases when you push a tag such as `v1.0.0`.

### Option A: Publish from a tag (recommended)

1. Update docs/changelog.
2. Create and push a tag:

```powershell
git tag v1.0.0
git push origin v1.0.0
```

3. Wait for the **Windows Release Package** workflow to finish.
4. Confirm the Release has `KIWI-windows-portable-v1.0.0.zip`.

### Option B: Manual dry-run package

1. Go to **Actions** -> **Windows Release Package**.
2. Click **Run workflow**.
3. Download the artifact from the run.

## What gets packaged

- Root scripts and docs (including `start_kiwi.bat`, `stop_kiwi.bat`, `QUICK_START_WINDOWS.md`)
- `KIWI_Web`
- `kiwi_desktop`

The package excludes heavy/dev directories (`.git`, `.github`, `node_modules`, `.next`, `.venv`, `__pycache__`, etc.).

## Recommended release notes template

Use this template in GitHub Release notes:

```text
Download: KIWI-windows-portable-<version>.zip

Quick Start (Windows):
1) Extract ZIP
2) Double-click start_kiwi.bat
3) Open http://localhost:3000

Requirements:
- Windows 10/11
- Node.js LTS
- Python 3.10+
- Optional: Ollama for local AI mode

Troubleshooting:
- If backend shows Offline, rerun start_kiwi.bat
- If port conflict appears, close prior KIWI windows and try again
```
