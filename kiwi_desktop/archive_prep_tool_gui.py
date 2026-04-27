
import csv
import shutil
import threading
import queue
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


TEXT_EXTENSIONS = {".md", ".txt", ".markdown", ".json", ".yaml", ".yml", ".csv"}
DEFAULT_MIN_TEXT_CHARS = 20


class PrepToolApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Archive Prep Tool")
        self.root.geometry("980x760")

        self.log_queue = queue.Queue()
        self.worker_thread = None

        self.source_var = tk.StringVar()
        self.output_var = tk.StringVar()

        self.copy_mode_var = tk.StringVar(value="copy")
        self.recursive_var = tk.BooleanVar(value=True)
        self.remove_empty_var = tk.BooleanVar(value=True)
        self.detect_near_empty_var = tk.BooleanVar(value=True)
        self.create_manifest_var = tk.BooleanVar(value=True)
        self.prepare_for_app_var = tk.BooleanVar(value=True)

        self.batch_mode_var = tk.StringVar(value="fixed")
        self.fixed_batch_size_var = tk.IntVar(value=300)
        self.pattern_var = tk.StringVar(value="300,400,500")
        self.min_text_chars_var = tk.IntVar(value=DEFAULT_MIN_TEXT_CHARS)

        self.preview_summary_var = tk.StringVar(value="No preview yet.")
        self.status_var = tk.StringVar(value="Ready.")

        self._build_ui()
        self.root.after(150, self._drain_log_queue)

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        title = ttk.Label(main, text="Archive Prep Tool", font=("Segoe UI", 16, "bold"))
        title.pack(anchor="w")

        subtitle = ttk.Label(
            main,
            text="Remove empty files, batch files, generate a manifest, and prepare output for your app.",
        )
        subtitle.pack(anchor="w", pady=(0, 12))

        kiwi_banner = tk.Frame(main, background="#1a3a5c", padx=12, pady=8)
        kiwi_banner.pack(fill="x", pady=(0, 12))
        tk.Button(
            kiwi_banner,
            text="Open KIWI →",
            background="#1f6feb",
            foreground="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=12,
            pady=4,
            command=self.open_kiwi,
        ).pack(side="right")
        tk.Label(
            kiwi_banner,
            text="✅ After prep is complete, open KIWI to scan and classify your batches.",
            foreground="#90caf9",
            background="#1a3a5c",
            font=("Segoe UI", 10),
        ).pack(side="left", fill="x", expand=True)

        paths = ttk.LabelFrame(main, text="Folders", padding=10)
        paths.pack(fill="x", pady=(0, 10))

        ttk.Label(paths, text="Source folder").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(paths, textvariable=self.source_var, width=90).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(paths, text="Browse", command=self.pick_source).grid(row=0, column=2, padx=(8, 0), pady=4)

        ttk.Label(paths, text="Output folder").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(paths, textvariable=self.output_var, width=90).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(paths, text="Browse", command=self.pick_output).grid(row=1, column=2, padx=(8, 0), pady=4)
        paths.columnconfigure(1, weight=1)

        options = ttk.Frame(main)
        options.pack(fill="x", pady=(0, 10))

        left = ttk.LabelFrame(options, text="Cleanup and preparation", padding=10)
        left.pack(side="left", fill="both", expand=True, padx=(0, 5))
        right = ttk.LabelFrame(options, text="Batch settings", padding=10)
        right.pack(side="left", fill="both", expand=True, padx=(5, 0))

        ttk.Checkbutton(left, text="Search subfolders recursively", variable=self.recursive_var).pack(anchor="w")
        ttk.Checkbutton(left, text="Move empty files to _empty_files", variable=self.remove_empty_var).pack(anchor="w")
        ttk.Checkbutton(left, text="Treat near-empty text files as empty", variable=self.detect_near_empty_var).pack(anchor="w")
        ttk.Checkbutton(left, text="Generate CSV manifest", variable=self.create_manifest_var).pack(anchor="w")
        ttk.Checkbutton(left, text="Prepare output layout for app", variable=self.prepare_for_app_var).pack(anchor="w")

        mode_row = ttk.Frame(left)
        mode_row.pack(anchor="w", pady=(8, 0))
        ttk.Label(mode_row, text="File action:").pack(side="left")
        ttk.Radiobutton(mode_row, text="Copy", variable=self.copy_mode_var, value="copy").pack(side="left", padx=(10, 0))
        ttk.Radiobutton(mode_row, text="Move", variable=self.copy_mode_var, value="move").pack(side="left", padx=(10, 0))

        min_row = ttk.Frame(left)
        min_row.pack(anchor="w", pady=(10, 0))
        ttk.Label(min_row, text="Near-empty text threshold (characters):").pack(side="left")
        ttk.Entry(min_row, textvariable=self.min_text_chars_var, width=8).pack(side="left", padx=(8, 0))

        ttk.Radiobutton(right, text="Fixed batch size", variable=self.batch_mode_var, value="fixed").pack(anchor="w")
        fixed_row = ttk.Frame(right)
        fixed_row.pack(anchor="w", pady=(4, 10))
        ttk.Label(fixed_row, text="Files per batch:").pack(side="left")
        ttk.Entry(fixed_row, textvariable=self.fixed_batch_size_var, width=8).pack(side="left", padx=(8, 0))

        ttk.Radiobutton(right, text="Repeating pattern", variable=self.batch_mode_var, value="pattern").pack(anchor="w")
        pattern_row = ttk.Frame(right)
        pattern_row.pack(anchor="w", pady=(4, 0))
        ttk.Label(pattern_row, text="Pattern:").pack(side="left")
        ttk.Entry(pattern_row, textvariable=self.pattern_var, width=24).pack(side="left", padx=(8, 0))
        ttk.Label(right, text='Example: "300,400,500"').pack(anchor="w", pady=(4, 0))

        preview_box = ttk.LabelFrame(main, text="Preview", padding=10)
        preview_box.pack(fill="x", pady=(0, 10))
        ttk.Label(preview_box, textvariable=self.preview_summary_var, wraplength=920, justify="left").pack(anchor="w")

        actions = ttk.Frame(main)
        actions.pack(fill="x", pady=(0, 10))
        ttk.Button(actions, text="Preview", command=self.preview).pack(side="left")
        ttk.Button(actions, text="Run", command=self.run).pack(side="left", padx=(8, 0))

        run_big = tk.Button(
            actions,
            text="RUN PREP",
            font=("Segoe UI", 12, "bold"),
            padx=18,
            pady=10,
            bg="#1f6feb",
            fg="white",
            activebackground="#1658b5",
            activeforeground="white",
            relief="raised",
            command=self.run,
        )
        run_big.pack(side="right")

        ttk.Label(actions, textvariable=self.status_var).pack(side="right", padx=(0, 12))

        log_frame = ttk.LabelFrame(main, text="Log", padding=10)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_frame, wrap="word", height=24)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scroll.set)

    def pick_source(self):
        path = filedialog.askdirectory(title="Select source folder")
        if path:
            self.source_var.set(path)

    def pick_output(self):
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            self.output_var.set(path)

    def open_kiwi(self):
        import subprocess
        import sys

        kiwi_script = Path(__file__).parent / "main.py"
        if not kiwi_script.exists():
            messagebox.showwarning(
                "KIWI not found",
                f"Could not find main.py at:\n{kiwi_script}\n\n"
                "Please ensure KIWI is installed in the same directory.",
            )
            return
        subprocess.Popen(
            [sys.executable, str(kiwi_script)],
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )

    def log(self, message: str):
        self.log_queue.put(message)

    def _drain_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.insert("end", msg + "\n")
                self.log_text.see("end")
        except queue.Empty:
            pass
        self.root.after(150, self._drain_log_queue)

    def get_config(self):
        source = Path(self.source_var.get().strip())
        output = Path(self.output_var.get().strip())

        if not source.exists() or not source.is_dir():
            raise ValueError("Please select a valid source folder.")
        if not output:
            raise ValueError("Please select a valid output folder.")

        if self.batch_mode_var.get() == "fixed":
            batch_sizes = [int(self.fixed_batch_size_var.get())]
            if batch_sizes[0] <= 0:
                raise ValueError("Fixed batch size must be greater than zero.")
        else:
            raw = self.pattern_var.get().strip()
            if not raw:
                raise ValueError("Please enter a valid batch pattern.")
            batch_sizes = [int(x.strip()) for x in raw.split(",") if x.strip()]
            if not batch_sizes or any(x <= 0 for x in batch_sizes):
                raise ValueError("Batch pattern must contain positive integers.")

        min_chars = int(self.min_text_chars_var.get())
        if min_chars < 0:
            raise ValueError("Near-empty threshold must be zero or more.")

        return {
            "source": source,
            "output": output,
            "recursive": self.recursive_var.get(),
            "remove_empty": self.remove_empty_var.get(),
            "detect_near_empty": self.detect_near_empty_var.get(),
            "create_manifest": self.create_manifest_var.get(),
            "prepare_for_app": self.prepare_for_app_var.get(),
            "copy_mode": self.copy_mode_var.get(),
            "batch_mode": self.batch_mode_var.get(),
            "batch_sizes": batch_sizes,
            "min_chars": min_chars,
        }

    def iter_files(self, root: Path, recursive: bool):
        if recursive:
            for p in root.rglob("*"):
                if p.is_file():
                    yield p
        else:
            for p in root.iterdir():
                if p.is_file():
                    yield p

    def is_near_empty_text(self, path: Path, min_chars: int) -> bool:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            return True
        cleaned = (
            text.replace("#", "")
                .replace("-", "")
                .replace("*", "")
                .replace("`", "")
                .replace("_", "")
                .strip()
        )
        return len(cleaned) < min_chars

    def collect_preview(self, config):
        files = sorted(self.iter_files(config["source"], config["recursive"]))
        empty_files = []
        usable_files = []

        for f in files:
            try:
                size = f.stat().st_size
            except Exception:
                continue

            is_empty = size == 0
            if (not is_empty and config["detect_near_empty"]
                and f.suffix.lower() in TEXT_EXTENSIONS):
                is_empty = self.is_near_empty_text(f, config["min_chars"])

            if is_empty:
                empty_files.append(f)
            else:
                usable_files.append(f)

        batch_counts = []
        remaining = len(usable_files)
        idx = 0
        batch_no = 0
        while remaining > 0:
            size = config["batch_sizes"][0] if config["batch_mode"] == "fixed" else config["batch_sizes"][batch_no % len(config["batch_sizes"])]
            take = min(size, remaining)
            batch_counts.append(take)
            remaining -= take
            idx += take
            batch_no += 1

        return {
            "total_files": len(files),
            "empty_files": len(empty_files),
            "usable_files": len(usable_files),
            "batch_counts": batch_counts,
        }

    def preview(self):
        try:
            config = self.get_config()
            info = self.collect_preview(config)
            batch_preview = ", ".join(str(x) for x in info["batch_counts"][:10])
            if len(info["batch_counts"]) > 10:
                batch_preview += ", ..."

            app_layout = "yes" if config["prepare_for_app"] else "no"
            empty_action = "move to _empty_files" if config["remove_empty"] else "leave in place"

            summary = (
                f"Source has {info['total_files']} files. "
                f"{info['empty_files']} look empty or near-empty. "
                f"{info['usable_files']} usable files would be processed. "
                f"They would be split into {len(info['batch_counts'])} batches "
                f"with counts like: {batch_preview}. "
                f"Empty files action: {empty_action}. "
                f"Manifest: {'yes' if config['create_manifest'] else 'no'}. "
                f"Prepare layout for app: {app_layout}. "
                f"File mode: {config['copy_mode']}."
            )
            self.preview_summary_var.set(summary)
            self.status_var.set("Preview ready.")
            self.log("Preview generated.")
        except Exception as e:
            messagebox.showerror("Preview error", str(e))
            self.status_var.set("Preview failed.")

    def run(self):
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo("Already running", "A run is already in progress.")
            return

        try:
            config = self.get_config()
        except Exception as e:
            messagebox.showerror("Configuration error", str(e))
            return

        self.worker_thread = threading.Thread(target=self._run_worker, args=(config,), daemon=True)
        self.worker_thread.start()
        self.status_var.set("Running...")

    def safe_dest(self, dest: Path) -> Path:
        if not dest.exists():
            return dest
        counter = 1
        while True:
            candidate = dest.parent / f"{dest.stem}_{counter}{dest.suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    def write_manifest(self, rows, manifest_path: Path):
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with manifest_path.open("w", newline="", encoding="utf-8") as f:
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
            writer.writerows(rows)

    def _run_worker(self, config):
        try:
            info = self.collect_preview(config)
            self.log(f"Starting run. Total files: {info['total_files']}. Usable: {info['usable_files']}. Empty: {info['empty_files']}.")

            source = config["source"]
            output = config["output"]
            output.mkdir(parents=True, exist_ok=True)

            empty_dir = output / "_empty_files"
            prepared_root = output / "prepared_for_app"
            batches_root = prepared_root / "source_batches" if config["prepare_for_app"] else output / "batches"
            manifests_root = output / "manifests"

            manifest_rows = []

            all_files = sorted(self.iter_files(source, config["recursive"]))
            empty_files = []
            usable_files = []

            for f in all_files:
                try:
                    size = f.stat().st_size
                except Exception:
                    continue

                is_empty = size == 0
                if (not is_empty and config["detect_near_empty"]
                    and f.suffix.lower() in TEXT_EXTENSIONS):
                    is_empty = self.is_near_empty_text(f, config["min_chars"])

                if is_empty:
                    empty_files.append(f)
                else:
                    usable_files.append(f)

            if config["remove_empty"]:
                empty_dir.mkdir(parents=True, exist_ok=True)
                for f in empty_files:
                    try:
                        dest = self.safe_dest(empty_dir / f.name)
                        shutil.move(str(f), str(dest))
                        manifest_rows.append({
                            "batch_name": "_empty_files",
                            "original_path": str(f),
                            "output_path": str(dest),
                            "action": "moved_empty",
                            "was_empty": True,
                            "size_bytes": f.stat().st_size if f.exists() else 0,
                        })
                    except Exception as e:
                        self.log(f"Could not move empty file: {f} ({e})")
            else:
                for f in empty_files:
                    manifest_rows.append({
                        "batch_name": "_empty_files",
                        "original_path": str(f),
                        "output_path": "",
                        "action": "detected_empty_only",
                        "was_empty": True,
                        "size_bytes": f.stat().st_size if f.exists() else 0,
                    })

            batches_root.mkdir(parents=True, exist_ok=True)

            batch_no = 1
            index = 0
            pattern_index = 0

            while index < len(usable_files):
                current_size = (
                    config["batch_sizes"][0]
                    if config["batch_mode"] == "fixed"
                    else config["batch_sizes"][pattern_index % len(config["batch_sizes"])]
                )
                pattern_index += 1

                batch_files = usable_files[index:index + current_size]
                batch_name = f"batch_{batch_no:03d}"
                batch_dir = batches_root / batch_name
                batch_dir.mkdir(parents=True, exist_ok=True)

                self.log(f"Creating {batch_name} with {len(batch_files)} files...")

                for f in batch_files:
                    try:
                        dest = self.safe_dest(batch_dir / f.name)
                        action = "copied"
                        if config["copy_mode"] == "move":
                            shutil.move(str(f), str(dest))
                            action = "moved"
                        else:
                            shutil.copy2(str(f), str(dest))

                        manifest_rows.append({
                            "batch_name": batch_name,
                            "original_path": str(f),
                            "output_path": str(dest),
                            "action": action,
                            "was_empty": False,
                            "size_bytes": dest.stat().st_size if dest.exists() else 0,
                        })
                    except Exception as e:
                        self.log(f"Could not process file: {f} ({e})")

                index += len(batch_files)
                batch_no += 1

            if config["prepare_for_app"]:
                (prepared_root / "open_webui_uploads").mkdir(parents=True, exist_ok=True)
                (prepared_root / "anythingllm_uploads").mkdir(parents=True, exist_ok=True)

                readme = prepared_root / "README_prepared_for_app.txt"
                readme.write_text(
                    "prepared_for_app/source_batches contains the batched source files.\n"
                    "prepared_for_app/open_webui_uploads is a placeholder for files you want to stage for Open WebUI.\n"
                    "prepared_for_app/anythingllm_uploads is a placeholder for files you want to stage for AnythingLLM.\n"
                    "Use the manifest CSV to see exactly what was moved or copied.\n",
                    encoding="utf-8",
                )

            if config["create_manifest"]:
                manifests_root.mkdir(parents=True, exist_ok=True)
                manifest_path = manifests_root / "prep_manifest.csv"
                self.write_manifest(manifest_rows, manifest_path)
                self.log(f"Manifest written to: {manifest_path}")

            self.status_var.set("Completed.")
            self.log("Run completed successfully.")
            result = messagebox.askyesno(
                "Prep complete — open KIWI?",
                f"Archive prep completed successfully.\n\n"
                f"Your batches are ready in:\n{config['output']}\n\n"
                "Would you like to open KIWI now to start scanning?",
            )
            if result:
                self.open_kiwi()
        except Exception as e:
            self.status_var.set("Failed.")
            self.log(f"Run failed: {e}")
            messagebox.showerror("Run failed", str(e))


def main():
    root = tk.Tk()
    style = ttk.Style()
    try:
        style.theme_use("vista")
    except Exception:
        pass
    app = PrepToolApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
