# KIWI

KIWI is a Windows local-first workflow for organizing large document sets into repeatable batches.

KIWI is currently packaged as a Windows local-first V1 using start_kiwi.bat and stop_kiwi.bat.

The web UI is the primary operator interface. Desktop/local tooling supports the local processing workflow.

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
  README.md
  USER_GUIDE.md
  BEGINNER_WALKTHROUGHS.md
  QUICK_START_WINDOWS.md
  RELEASE_CHECKLIST.md
  start_kiwi.bat
  stop_kiwi.bat
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

- start_kiwi.bat: starts backend and web services.
- stop_kiwi.bat: stops KIWI windows/services with safe checks.

## Requirements

- Windows 10 or 11
- Node.js LTS (includes npm)
- Python 3.10+ on PATH
- Optional: Ollama (for local AI mode)

## Quick Start for Windows

1. Open the parent KIWI folder.
2. Double-click start_kiwi.bat.
3. Open http://localhost:3000.
4. Confirm Home/Setup shows Backend: Online.
5. Use Save Project -> Scan Batch -> Run Batch.
6. When done, double-click stop_kiwi.bat.

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
- USER_GUIDE.md: full operator guide.
- BEGINNER_WALKTHROUGHS.md: scenario-based step-by-step examples.
- DOCUMENTATION_MAP.md: where each doc belongs and who should use it.
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

- Backend offline: rerun start_kiwi.bat and check the printed backend health URL.
- Buttons look stuck after switching batches: refresh the browser once.
- Port conflict: close previous KIWI windows, then run stop_kiwi.bat and start again.
- Ollama missing: continue in rules-only mode, or install/start Ollama.
- Scan returns 0 files: verify import base path and batch folder name.

## Contributing

- Keep changes small and focused.
- Do not commit secrets, private paths, or private datasets.
- Prefer beginner-friendly language in docs and UI copy.

If reporting issues, use the templates in .github/ISSUE_TEMPLATE/.
