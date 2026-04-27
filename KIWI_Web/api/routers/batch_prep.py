from __future__ import annotations

import csv
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

router = APIRouter(tags=["batch_prep"])

TEXT_EXTENSIONS = {".md", ".txt", ".markdown", ".json", ".yaml", ".yml", ".csv"}


class BatchPrepRequest(BaseModel):
    source_folder: str
    output_folder: str
    batch_size: int = 300
    batch_mode: str = "fixed"  # "fixed" or "pattern"
    pattern: str = "300,400,500"  # used when batch_mode = "pattern"
    copy_mode: str = "copy"  # "copy" or "move"
    remove_empty: bool = True
    detect_near_empty: bool = True
    min_text_chars: int = 20
    create_manifest: bool = True
    prepare_for_app: bool = True


class BatchPrepResult(BaseModel):
    total_files: int
    usable_files: int
    empty_files: int
    batches_created: int
    batch_names: list[str]
    manifest_path: str | None
    output_folder: str
    message: str


def is_near_empty(path: Path, min_chars: int) -> bool:
    try:
        return len(path.read_text(encoding="utf-8", errors="ignore").strip()) < min_chars
    except Exception:
        return False


def safe_dest(dest: Path) -> Path:
    if not dest.exists():
        return dest
    counter = 1
    while True:
        candidate = dest.parent / f"{dest.stem}_{counter}{dest.suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


@router.post("/batch-prep/preview")
def preview_batch(request: BatchPrepRequest) -> dict:
    source = Path(request.source_folder)
    if not source.exists() or not source.is_dir():
        return {"error": f"Source folder not found: {request.source_folder}"}

    all_files = sorted(source.rglob("*") if True else source.glob("*"))
    all_files = [f for f in all_files if f.is_file()]

    empty = []
    usable = []
    for f in all_files:
        is_empty = f.stat().st_size == 0
        if not is_empty and request.detect_near_empty and f.suffix.lower() in TEXT_EXTENSIONS:
            is_empty = is_near_empty(f, request.min_text_chars)
        if is_empty:
            empty.append(f)
        else:
            usable.append(f)

    if request.batch_mode == "fixed":
        sizes = [request.batch_size]
    else:
        sizes = [int(x.strip()) for x in request.pattern.split(",") if x.strip()]

    batches = []
    index = 0
    pattern_index = 0
    batch_no = 1
    while index < len(usable):
        sz = sizes[pattern_index % len(sizes)]
        pattern_index += 1
        batches.append({"name": f"batch_{batch_no:03d}", "count": len(usable[index : index + sz])})
        index += sz
        batch_no += 1

    return {
        "total_files": len(all_files),
        "usable_files": len(usable),
        "empty_files": len(empty),
        "batches_preview": batches,
        "estimated_batches": len(batches),
    }


@router.post("/batch-prep/run")
def run_batch(request: BatchPrepRequest) -> BatchPrepResult:
    source = Path(request.source_folder)
    output = Path(request.output_folder)

    if not source.exists() or not source.is_dir():
        return BatchPrepResult(
            total_files=0,
            usable_files=0,
            empty_files=0,
            batches_created=0,
            batch_names=[],
            manifest_path=None,
            output_folder=str(output),
            message=f"Source folder not found: {source}",
        )

    output.mkdir(parents=True, exist_ok=True)

    prepared_root = output / "prepared_for_app"
    batches_root = prepared_root / "source_batches" if request.prepare_for_app else output / "batches"
    batches_root.mkdir(parents=True, exist_ok=True)

    all_files = sorted(source.rglob("*"))
    all_files = [f for f in all_files if f.is_file()]

    empty_files = []
    usable_files = []
    for f in all_files:
        is_empty = f.stat().st_size == 0
        if not is_empty and request.detect_near_empty and f.suffix.lower() in TEXT_EXTENSIONS:
            is_empty = is_near_empty(f, request.min_text_chars)
        if is_empty:
            empty_files.append(f)
        else:
            usable_files.append(f)

    if request.remove_empty and empty_files:
        empty_dir = output / "_empty_files"
        empty_dir.mkdir(parents=True, exist_ok=True)
        for f in empty_files:
            try:
                shutil.move(str(f), str(safe_dest(empty_dir / f.name)))
            except Exception:
                pass

    if request.batch_mode == "fixed":
        sizes = [request.batch_size]
    else:
        sizes = [int(x.strip()) for x in request.pattern.split(",") if x.strip()]

    manifest_rows = []
    batch_names = []
    index = 0
    pattern_index = 0
    batch_no = 1

    while index < len(usable_files):
        sz = sizes[pattern_index % len(sizes)]
        pattern_index += 1
        batch_files = usable_files[index : index + sz]
        batch_name = f"batch_{batch_no:03d}"
        batch_dir = batches_root / batch_name
        batch_dir.mkdir(parents=True, exist_ok=True)
        batch_names.append(batch_name)

        for f in batch_files:
            try:
                dest = safe_dest(batch_dir / f.name)
                if request.copy_mode == "move":
                    shutil.move(str(f), str(dest))
                    action = "moved"
                else:
                    shutil.copy2(str(f), str(dest))
                    action = "copied"
                manifest_rows.append(
                    {
                        "batch_name": batch_name,
                        "original_path": str(f),
                        "output_path": str(dest),
                        "action": action,
                        "was_empty": False,
                        "size_bytes": dest.stat().st_size if dest.exists() else 0,
                    }
                )
            except Exception:
                pass

        index += len(batch_files)
        batch_no += 1

    if request.prepare_for_app:
        (prepared_root / "open_webui_uploads").mkdir(parents=True, exist_ok=True)
        (prepared_root / "anythingllm_uploads").mkdir(parents=True, exist_ok=True)

    manifest_path = None
    if request.create_manifest and manifest_rows:
        manifests_root = output / "manifests"
        manifests_root.mkdir(parents=True, exist_ok=True)
        manifest_path = str(manifests_root / "prep_manifest.csv")
        with open(manifest_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "batch_name",
                    "original_path",
                    "output_path",
                    "action",
                    "was_empty",
                    "size_bytes",
                ],
            )
            writer.writeheader()
            writer.writerows(manifest_rows)

    return BatchPrepResult(
        total_files=len(all_files),
        usable_files=len(usable_files),
        empty_files=len(empty_files),
        batches_created=len(batch_names),
        batch_names=batch_names,
        manifest_path=manifest_path,
        output_folder=str(output),
        message=f"Created {len(batch_names)} batches from {len(usable_files)} files.",
    )
