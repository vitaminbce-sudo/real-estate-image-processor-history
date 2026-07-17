import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from watcher import ImageFolderWatcher


APP_NAME = "Real Estate Image Processor"
DEFAULT_WATCH_FOLDER = Path.home() / "Downloads" / "ImageInbox"


class LuxuryButton(tk.Button):
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            relief="flat",
            bd=0,
            font=("Yu Gothic UI", 10, "bold"),
            cursor="hand2",
            padx=18,
            pady=8,
            **kwargs,
        )


class RealEstateImageApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(APP_NAME)
        self.geometry("820x520")
        self.resizable(False, False)

        self._watch_folder = tk.StringVar(value=str(DEFAULT_WATCH_FOLDER))
        self._status = tk.StringVar(value="停止中")
        self._watcher = None
        self._watch_thread = None
        self._log_queue = queue.Queue()

        self.bg_dark = "#1f1713"
        self.bg_panel = "#2b211b"
        self.bg_entry = "#f7f3ed"
        self.gold = "#c8a45d"
        self.gold_dark = "#9f7f3f"
        self.text_main = "#f4eee6"
        self.text_sub = "#cfc3b6"
        self.danger = "#8b3a2f"

        self.configure(bg=self.bg_dark)
        self._build_ui()
        self._poll_log_queue()

    def _build_ui(self):
        header = tk.Frame(self, bg=self.bg_dark)
        header.pack(fill="x", padx=28, pady=(24, 10))

        tk.Label(
            header,
            text=APP_NAME,
            bg=self.bg_dark,
            fg=self.text_main,
            font=("Yu Gothic UI", 22, "bold"),
        ).pack(anchor="w")

        tk.Label(
            header,
            text="不動産写真を自然な明るさへ。HP / SUUMO 用に自動生成。",
            bg=self.bg_dark,
            fg=self.text_sub,
            font=("Yu Gothic UI", 10),
        ).pack(anchor="w", pady=(4, 0))

        panel = tk.Frame(self, bg=self.bg_panel, bd=0)
        panel.pack(fill="x", padx=28, pady=(18, 14))

        tk.Label(
            panel,
            text="監視フォルダ",
            bg=self.bg_panel,
            fg=self.gold,
            font=("Yu Gothic UI", 10, "bold"),
        ).pack(anchor="w", padx=20, pady=(18, 6))

        folder_row = tk.Frame(panel, bg=self.bg_panel)
        folder_row.pack(fill="x", padx=20, pady=(0, 18))

        self.folder_entry = tk.Entry(
            folder_row,
            textvariable=self._watch_folder,
            bg=self.bg_entry,
            fg="#1a1a1a",
            insertbackground="#1a1a1a",
            relief="flat",
            font=("Yu Gothic UI", 10),
            bd=0,
        )
        self.folder_entry.pack(side="left", fill="x", expand=True, ipady=8)

        LuxuryButton(
            folder_row,
            text="参照",
            command=self._browse_folder,
            bg=self.gold,
            fg="#1f1713",
            activebackground=self.gold_dark,
            activeforeground="#ffffff",
        ).pack(side="left", padx=(10, 0))

        card_row = tk.Frame(self, bg=self.bg_dark)
        card_row.pack(fill="x", padx=28, pady=(0, 14))
        self._create_card(card_row, "出力先", "物件フォルダ内に HP / SUUMO を自動作成", 0)
        self._create_card(card_row, "補正", "自然な明るさ・白飛び抑制・軽い水平補正", 1)
        self._create_card(card_row, "安全性", "HP / SUUMO 配下は絶対スキップ", 2)

        control = tk.Frame(self, bg=self.bg_dark)
        control.pack(fill="x", padx=28, pady=(0, 14))

        status_box = tk.Frame(control, bg=self.bg_panel)
        status_box.pack(side="left", fill="x", expand=True)

        tk.Label(
            status_box,
            text="STATUS",
            bg=self.bg_panel,
            fg=self.gold,
            font=("Yu Gothic UI", 8, "bold"),
        ).pack(anchor="w", padx=16, pady=(10, 0))

        tk.Label(
            status_box,
            textvariable=self._status,
            bg=self.bg_panel,
            fg=self.text_main,
            font=("Yu Gothic UI", 14, "bold"),
        ).pack(anchor="w", padx=16, pady=(0, 10))

        self.start_btn = LuxuryButton(
            control,
            text="監視開始",
            command=self._start_watching,
            bg=self.gold,
            fg="#1f1713",
            activebackground=self.gold_dark,
            activeforeground="#ffffff",
        )
        self.start_btn.pack(side="left", padx=(14, 8))

        self.stop_btn = LuxuryButton(
            control,
            text="監視停止",
            command=self._stop_watching,
            bg=self.danger,
            fg="#ffffff",
            activebackground="#6e2f27",
            activeforeground="#ffffff",
            state="disabled",
        )
        self.stop_btn.pack(side="left")

        log_panel = tk.Frame(self, bg=self.bg_panel)
        log_panel.pack(fill="both", expand=True, padx=28, pady=(0, 20))

        tk.Label(
            log_panel,
            text="処理ログ",
            bg=self.bg_panel,
            fg=self.gold,
            font=("Yu Gothic UI", 10, "bold"),
        ).pack(anchor="w", padx=18, pady=(14, 6))

        self.log_text = tk.Text(
            log_panel,
            height=10,
            bg="#15100d",
            fg="#eee6dc",
            insertbackground="#ffffff",
            relief="flat",
            bd=0,
            wrap="word",
            font=("Consolas", 9),
        )
        self.log_text.pack(fill="both", expand=True, padx=18, pady=(0, 18))

    def _create_card(self, parent, title, body, column):
        card = tk.Frame(parent, bg=self.bg_panel)
        card.grid(row=0, column=column, sticky="nsew", padx=6)
        parent.grid_columnconfigure(column, weight=1)

        tk.Label(
            card,
            text=title,
            bg=self.bg_panel,
            fg=self.gold,
            font=("Yu Gothic UI", 9, "bold"),
        ).pack(anchor="w", padx=16, pady=(12, 2))

        tk.Label(
            card,
            text=body,
            bg=self.bg_panel,
            fg=self.text_sub,
            font=("Yu Gothic UI", 9),
            wraplength=220,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 12))

    def _browse_folder(self):
        initial = self._watch_folder.get()
        if not os.path.isdir(initial):
            initial = os.path.expanduser("~")
        folder = filedialog.askdirectory(initialdir=initial)
        if folder:
            self._watch_folder.set(folder)

    def _start_watching(self):
        watch_folder = self._watch_folder.get().strip()
        if not watch_folder:
            messagebox.showerror("エラー", "監視フォルダを指定してください。")
            return
        if not os.path.isdir(watch_folder):
            messagebox.showerror("エラー", f"監視フォルダが存在しません。\n{watch_folder}")
            return
        if self._watcher is not None:
            return

        self._watcher = ImageFolderWatcher(
            watch_folder=watch_folder,
            log_callback=self._enqueue_log,
        )
        self._watch_thread = threading.Thread(target=self._watcher.start, daemon=True)
        self._watch_thread.start()

        self._status.set("監視中")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self._append_log(f"[START] 監視開始: {watch_folder}")

    def _stop_watching(self):
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None
        self._status.set("停止中")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self._append_log("[STOP] 監視停止")

    def _enqueue_log(self, message):
        self._log_queue.put(message)

    def _poll_log_queue(self):
        try:
            while True:
                self._append_log(self._log_queue.get_nowait())
        except queue.Empty:
            pass
        self.after(200, self._poll_log_queue)

    def _append_log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def on_closing(self):
        self._stop_watching()
        self.destroy()


if __name__ == "__main__":
    app = RealEstateImageApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
