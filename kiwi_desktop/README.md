# kiwi_desktop

This folder contains KIWI local backend and processing tooling.

For most users, start from the parent folder and run start_kiwi.bat.

## Role in the product

- Provides local API and processing services used by the web UI.
- Supports project creation/loading, scanning, queue operations, settings, and exports.
- Hosts local-first processing logic and developer-facing internals.

The primary operator interface is the browser UI in KIWI_Web.

## Typical use

- Non-technical users: do not run this folder directly; use parent launch scripts.
- Developers: run/debug services here as needed.

## Developer quick start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn api.main:app --reload --port 8000
```

Then run KIWI_Web separately or use parent scripts from the repo root.

## Related docs

- Parent overview: ../README.md
- Windows quick start: ../QUICK_START_WINDOWS.md
- Operator guide: ../USER_GUIDE.md
- Architecture notes: docs/architecture.md
- Desktop developer details: DEVELOPER_GUIDE.md
