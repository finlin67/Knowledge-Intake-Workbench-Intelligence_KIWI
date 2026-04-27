# KIWI User Guide

This guide explains the day-to-day operator flow in plain language.

## Before you begin

1. Start KIWI from the parent folder using start_kiwi.bat.
2. Open http://localhost:3000.
3. Confirm Home/Setup shows Backend: Online.

## Core workflow

1. In Home/Setup Step 1, enter project details and click Save Project.
2. In Step 2, set import base path + batch folder, then click Scan Batch.
3. In Step 3 - Run Batch, review settings and click Run Batch.
4. After completion, click Start Next Batch and repeat.

## Project and batch model

- Project: persistent settings across runs.
- Batch: one folder processed in a single cycle.

Use one project for related batches. Change only the batch folder each cycle.

## Recommended path pattern

- Import batches: C:\KIWI\batches\batch_001
- Export output: C:\KIWI\exports\project_001

## Loading an existing project

1. Go to Home/Setup.
2. Open Load Existing Project.
3. Enter the existing output folder path.
4. Load, then continue with Scan Batch and Run Batch.

## AI and workspace settings

- Open Settings before your first production run.
- Configure provider/model only if AI mode is enabled.
- Keep workspace and keyword mappings current.
- Rules-only mode is valid and supported.

## Common checks

- Backend Offline: rerun start_kiwi.bat.
- Buttons inactive: confirm Save Project then Scan Batch are complete.
- Scan found 0 files: verify import base path and batch folder name.
- Batch changed and UI looks stale: refresh browser once.

## Related docs

- Quick start: QUICK_START_WINDOWS.md
- Walkthroughs: BEGINNER_WALKTHROUGHS.md
- Release checks: RELEASE_CHECKLIST.md
