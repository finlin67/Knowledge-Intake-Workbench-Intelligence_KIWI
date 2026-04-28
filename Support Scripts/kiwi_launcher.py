from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox


def get_root_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def run_start_here(flag: str) -> None:
    root_dir = get_root_dir()
    start_here = root_dir / "Start Here.bat"

    if not start_here.exists():
        messagebox.showerror("KIWI Launcher", f"Missing file:\n{start_here}")
        return

    try:
        subprocess.Popen(["cmd", "/c", str(start_here), flag], cwd=str(root_dir))
    except OSError as exc:
        messagebox.showerror("KIWI Launcher", f"Failed to launch:\n{exc}")


def main() -> None:
    root = tk.Tk()
    root.title("KIWI Launcher")
    root.geometry("420x250")
    root.resizable(False, False)

    container = tk.Frame(root, padx=18, pady=18)
    container.pack(fill="both", expand=True)

    title = tk.Label(container, text="KIWI Launcher", font=("Segoe UI", 16, "bold"))
    title.pack(anchor="w")

    subtitle = tk.Label(
        container,
        text="Use this to run setup, start KIWI, or stop KIWI.",
        font=("Segoe UI", 10),
    )
    subtitle.pack(anchor="w", pady=(4, 14))

    start_button = tk.Button(
        container,
        text="Start KIWI",
        width=28,
        height=2,
        command=lambda: run_start_here("--start"),
    )
    start_button.pack(pady=4)

    setup_button = tk.Button(
        container,
        text="First-time Setup",
        width=28,
        height=2,
        command=lambda: run_start_here("--setup"),
    )
    setup_button.pack(pady=4)

    stop_button = tk.Button(
        container,
        text="Stop KIWI",
        width=28,
        height=2,
        command=lambda: run_start_here("--stop"),
    )
    stop_button.pack(pady=4)

    note = tk.Label(
        container,
        text="This launcher calls Start Here.bat. Core KIWI behavior is unchanged.",
        font=("Segoe UI", 9),
        fg="#444444",
    )
    note.pack(anchor="w", pady=(14, 0))

    root.mainloop()


if __name__ == "__main__":
    main()
