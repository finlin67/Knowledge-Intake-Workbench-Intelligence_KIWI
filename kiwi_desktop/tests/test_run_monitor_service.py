"""Tests for RunMonitorService worker lifecycle transitions."""

from __future__ import annotations

import time
from pathlib import Path

from db.session import Database
from models.enums import RunnerStatus
from db.repositories import FileRepository
from services import run_monitor_service as rms


def _wait_until(predicate, *, timeout_s: float = 2.0, interval_s: float = 0.01) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval_s)
    return predicate()


def _configure_monitor(tmp_path: Path) -> tuple[rms.RunMonitorService, Path]:
    db_path = tmp_path / "state.sqlite3"
    Database(db_path).connect()
    raw = tmp_path / "raw"
    out = tmp_path / "out"
    raw.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    monitor = rms.RunMonitorService()
    monitor.configure(db_path=db_path, raw_folder=raw, output_folder=out, log=lambda _m: None)
    return monitor, db_path


def test_run_monitor_transitions_running_to_completed_and_cleans_up(tmp_path: Path, monkeypatch) -> None:
    monitor, _db_path = _configure_monitor(tmp_path)

    class FakeRunner:
        calls = 0

        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def run(self, *, max_files: int | None = None):
            del max_files
            FakeRunner.calls += 1
            if FakeRunner.calls == 1:
                time.sleep(0.12)  # keep worker in running state long enough to observe

                class FirstResult:
                    job_id = 1
                    files_started = 1
                    files_finished_ok = 1
                    files_marked_failed = 0

                return FirstResult()

            class DoneResult:
                job_id = 2
                files_started = 0
                files_finished_ok = 0
                files_marked_failed = 0

            return DoneResult()

    monkeypatch.setattr(rms, "PipelineRunner", FakeRunner)

    monitor.start(scan_first=False)
    assert _wait_until(lambda: monitor.snapshot().state == "running")
    assert _wait_until(lambda: not monitor.is_running())

    snap = monitor.snapshot()
    assert snap.state == "completed"
    assert monitor._thread is None

    logs = monitor.drain_logs()
    joined = " | ".join(logs)
    assert "Run started." in joined
    assert "Job #1: started=1, ok=1, failed=0" in joined
    assert "Run completed." in joined
    assert "Thread/worker cleanup complete." in joined


def test_run_monitor_transitions_to_failed_and_cleans_up(tmp_path: Path, monkeypatch) -> None:
    monitor, _db_path = _configure_monitor(tmp_path)

    class FailingRunner:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def run(self, *, max_files: int | None = None):
            del max_files
            raise RuntimeError("synthetic failure")

    monkeypatch.setattr(rms, "PipelineRunner", FailingRunner)

    monitor.start(scan_first=False)
    assert _wait_until(lambda: not monitor.is_running())

    snap = monitor.snapshot()
    assert snap.state == "failed"
    assert monitor._thread is None

    logs = monitor.drain_logs()
    joined = " | ".join(logs)
    assert "Run started." in joined
    assert "Run failed: RuntimeError: synthetic failure" in joined
    assert "Thread/worker cleanup complete." in joined


def test_run_monitor_stop_transitions_to_stopping_and_cleans_up(tmp_path: Path, monkeypatch) -> None:
    monitor, _db_path = _configure_monitor(tmp_path)

    class BlockingRunner:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def run(self, *, max_files: int | None = None):
            del max_files
            # Simulate in-flight work until stop is requested.
            while not monitor._stop.is_set():
                time.sleep(0.01)

            class StoppedResult:
                job_id = 9
                files_started = 1
                files_finished_ok = 0
                files_marked_failed = 0

            return StoppedResult()

    monkeypatch.setattr(rms, "PipelineRunner", BlockingRunner)

    monitor.start(scan_first=False)
    assert _wait_until(lambda: monitor.snapshot().state == "running")

    monitor.stop()
    # stop() should immediately update requested state.
    assert monitor._final_state == "stopping"
    assert _wait_until(lambda: not monitor.is_running())

    snap = monitor.snapshot()
    assert snap.state == "stopping"
    assert monitor._thread is None

    logs = monitor.drain_logs()
    joined = " | ".join(logs)
    assert "Run started." in joined
    assert "Stopping..." in joined
    assert "Thread/worker cleanup complete." in joined


def test_requeue_all_resets_completed_files_to_new(tmp_path: Path) -> None:
    monitor, db_path = _configure_monitor(tmp_path)
    db = Database(db_path)
    db.connect()
    files = FileRepository(db)

    sample = tmp_path / "sample.md"
    sample.write_text("# sample", encoding="utf-8")
    rec = files.insert(path=str(sample.resolve()), display_name="sample.md")
    files.commit_pipeline_stage_success(rec.id, next_stage=None)
    done = files.get_by_id(rec.id)
    assert done is not None
    assert done.runner_status == RunnerStatus.COMPLETED.value
    assert done.pipeline_next_stage is None

    updated = monitor.requeue_all()
    assert updated >= 1

    again = files.get_by_id(rec.id)
    assert again is not None
    assert again.runner_status == RunnerStatus.NEW.value
    assert again.pipeline_next_stage == "classified"


def test_requeue_all_is_profile_scoped(tmp_path: Path) -> None:
    monitor, db_path = _configure_monitor(tmp_path)
    monitor.configure(
        db_path=db_path,
        raw_folder=tmp_path / "raw",
        output_folder=tmp_path / "out",
        export_profile="open_webui",
        log=lambda _m: None,
    )
    db = Database(db_path)
    conn = db.connect()
    sample = tmp_path / "scoped.md"
    sample.write_text("# scoped", encoding="utf-8")
    FileRepository(db).insert(path=str(sample.resolve()), display_name="scoped.md")
    conn.execute(
        """
        UPDATE files
        SET runner_status_anythingllm = 'completed',
            pipeline_next_stage_anythingllm = NULL,
            runner_status_open_webui = 'completed',
            pipeline_next_stage_open_webui = NULL
        """
    )
    conn.commit()

    monitor.requeue_all()

    row = conn.execute(
        """
        SELECT runner_status_anythingllm, pipeline_next_stage_anythingllm,
               runner_status_open_webui, pipeline_next_stage_open_webui
        FROM files
        LIMIT 1
        """
    ).fetchone()
    assert row is not None
    assert row["runner_status_anythingllm"] == "completed"
    assert row["pipeline_next_stage_anythingllm"] is None
    assert row["runner_status_open_webui"] == "new"
    assert row["pipeline_next_stage_open_webui"] == "classified"


def test_preflight_summary_reports_counts_and_preview(tmp_path: Path) -> None:
    monitor, db_path = _configure_monitor(tmp_path)
    db = Database(db_path)
    db.connect()
    files = FileRepository(db)
    p1 = tmp_path / "a.md"
    p2 = tmp_path / "b.md"
    p1.write_text("# a", encoding="utf-8")
    p2.write_text("# b", encoding="utf-8")
    rec1 = files.insert(path=str(p1.resolve()), display_name="a.md")
    rec2 = files.insert(path=str(p2.resolve()), display_name="b.md")
    files.set_review_required(rec1.id, True)
    files.commit_pipeline_stage_success(rec2.id, next_stage=None)

    summary = monitor.build_preflight_summary(preview_limit=5)
    assert summary.total_files == 2
    assert summary.pending_files == 1
    assert summary.processed_files == 1
    assert summary.estimated_review_count >= 1
    assert summary.active_export_profile == "anythingllm"
    assert summary.previews
    assert "If you click Run" in summary.human_summary
    assert 0.0 <= summary.classification_wiki_share <= 1.0
    assert summary.preflight_wiki_share_cap > 0.0


def test_preflight_summary_flags_wiki_share_cap_exceeded(tmp_path: Path) -> None:
    monitor, db_path = _configure_monitor(tmp_path)
    out_kiw = tmp_path / "out" / ".kiw"
    out_kiw.mkdir(parents=True, exist_ok=True)
    (out_kiw / "classification_rules.json").write_text(
        '{"preflight_wiki_share_cap": 0.20, "small_file_char_threshold": 500, "relevance_min_score": 10}',
        encoding="utf-8",
    )
    db = Database(db_path)
    db.connect()
    files = FileRepository(db)
    for idx in range(5):
        p = tmp_path / f"frag_{idx}.md"
        p.write_text("todo note\n", encoding="utf-8")
        files.insert(path=str(p.resolve()), display_name=p.name)

    summary = monitor.build_preflight_summary(preview_limit=5)
    assert summary.classification_total_files == 5
    assert summary.classification_wiki_share > summary.preflight_wiki_share_cap
    assert summary.wiki_share_cap_exceeded is True


def test_pending_batch_overview_detects_next_source_batch_folder(tmp_path: Path) -> None:
    monitor, db_path = _configure_monitor(tmp_path)
    raw_current = tmp_path / "raw" / "source_batches" / "batch_001"
    raw_next = tmp_path / "raw" / "source_batches" / "batch_002"
    raw_current.mkdir(parents=True, exist_ok=True)
    raw_next.mkdir(parents=True, exist_ok=True)
    monitor.configure(
        db_path=db_path,
        raw_folder=raw_current,
        output_folder=tmp_path / "out",
        export_profile="anythingllm",
        log=lambda _m: None,
    )

    db = Database(db_path)
    db.connect()
    files = FileRepository(db)
    current_file = raw_current / "doc_a.md"
    next_nested = raw_next / "subfolder" / "doc_b.md"
    next_nested.parent.mkdir(parents=True, exist_ok=True)
    current_file.write_text("# current", encoding="utf-8")
    next_nested.write_text("# next", encoding="utf-8")
    files.insert(path=str(current_file.resolve()), display_name="doc_a.md")
    files.insert(path=str(next_nested.resolve()), display_name="doc_b.md")

    overview = monitor.pending_batch_overview()
    assert overview.current_pending == 1
    assert overview.other_pending == 1
    assert overview.next_batch_folder is not None
    assert overview.next_batch_folder.resolve() == raw_next.resolve()


def test_pending_batch_overview_prefers_lowest_batch_number(tmp_path: Path) -> None:
    monitor, db_path = _configure_monitor(tmp_path)
    raw_current = tmp_path / "raw" / "source_batches" / "batch_001"
    raw_two = tmp_path / "raw" / "source_batches" / "batch_002"
    raw_ten = tmp_path / "raw" / "source_batches" / "batch_010"
    raw_current.mkdir(parents=True, exist_ok=True)
    raw_two.mkdir(parents=True, exist_ok=True)
    raw_ten.mkdir(parents=True, exist_ok=True)
    monitor.configure(
        db_path=db_path,
        raw_folder=raw_current,
        output_folder=tmp_path / "out",
        export_profile="anythingllm",
        log=lambda _m: None,
    )

    db = Database(db_path)
    db.connect()
    files = FileRepository(db)
    p2 = raw_two / "doc_b.md"
    p10 = raw_ten / "doc_c.md"
    p2.write_text("# two", encoding="utf-8")
    p10.write_text("# ten", encoding="utf-8")
    files.insert(path=str(p10.resolve()), display_name="doc_c.md")
    files.insert(path=str(p2.resolve()), display_name="doc_b.md")

    overview = monitor.pending_batch_overview()
    assert overview.current_pending == 0
    assert overview.other_pending == 2
    assert overview.next_batch_folder is not None
    assert overview.next_batch_folder.resolve() == raw_two.resolve()
