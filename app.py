#!/usr/bin/env python3
"""Nano Whiteboard Doctor - Clean up whiteboard photos with Fal AI Nano Banana 2."""

import base64
import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

import requests
from PIL import Image, ImageTk

CONFIG_DIR = Path.home() / ".config" / "nano-whiteboard-doctor"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_PROMPT = (
    "Take this whiteboard photograph and convert it into a beautiful and polished "
    "graphic featuring clear labels and icons. Preserve all the original content, "
    "text, and diagrams but make them clean, well-organized, and professional looking."
)

FAL_SUBMIT_URL = "https://queue.fal.run/fal-ai/nano-banana-2/edit"
FAL_STATUS_URL = "https://queue.fal.run/fal-ai/nano-banana-2/edit/requests/{request_id}/status"
FAL_RESULT_URL = "https://queue.fal.run/fal-ai/nano-banana-2/edit/requests/{request_id}"


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def image_to_data_url(path: str) -> str:
    ext = Path(path).suffix.lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "webp": "image/webp", "bmp": "image/bmp"}.get(ext.lstrip("."), "image/png")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{b64}"


class ApiKeyDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Fal AI API Key")
        self.result = None
        self.resizable(False, False)
        self.grab_set()

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Enter your Fal AI API key:").pack(anchor=tk.W)
        ttk.Label(frame, text="Get one at fal.ai/dashboard/keys",
                  foreground="gray").pack(anchor=tk.W, pady=(0, 10))

        self.entry = ttk.Entry(frame, width=50, show="*")
        self.entry.pack(fill=tk.X, pady=(0, 10))
        self.entry.focus_set()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)

        self.bind("<Return>", lambda e: self._save())
        self.wait_window()

    def _save(self):
        key = self.entry.get().strip()
        if key:
            self.result = key
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Nano Whiteboard Doctor")
        self.geometry("900x700")
        self.minsize(700, 500)

        self.config_data = load_config()
        self.image_paths = []
        self.processing = False

        self._build_ui()

        if not self.config_data.get("api_key"):
            self.after(200, self._prompt_api_key)

    def _build_ui(self):
        # Menu bar
        menubar = tk.Menu(self)
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Set API Key...", command=self._prompt_api_key)
        settings_menu.add_separator()
        settings_menu.add_command(label="Quit", command=self.quit)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        self.configure(menu=menubar)

        main = ttk.Frame(self, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # Top: image list + controls
        top = ttk.Frame(main)
        top.pack(fill=tk.BOTH, expand=True)

        # Left: image list
        left = ttk.LabelFrame(top, text="Images", padding=5)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.image_listbox = tk.Listbox(left, selectmode=tk.EXTENDED)
        self.image_listbox.pack(fill=tk.BOTH, expand=True)

        btn_row = ttk.Frame(left)
        btn_row.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(btn_row, text="Add Images", command=self._add_images).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_row, text="Remove Selected", command=self._remove_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_row, text="Clear All", command=self._clear_all).pack(side=tk.LEFT)

        # Right: settings
        right = ttk.LabelFrame(top, text="Settings", padding=10)
        right.pack(side=tk.RIGHT, fill=tk.Y, ipadx=5)

        ttk.Label(right, text="Output Format:").pack(anchor=tk.W)
        self.format_var = tk.StringVar(value=self.config_data.get("output_format", "png"))
        fmt_combo = ttk.Combobox(right, textvariable=self.format_var,
                                 values=["png", "jpeg", "webp"], state="readonly", width=12)
        fmt_combo.pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(right, text="Resolution:").pack(anchor=tk.W)
        self.resolution_var = tk.StringVar(value=self.config_data.get("resolution", "1K"))
        res_combo = ttk.Combobox(right, textvariable=self.resolution_var,
                                 values=["0.5K", "1K", "2K", "4K"], state="readonly", width=12)
        res_combo.pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(right, text="Output Directory:").pack(anchor=tk.W)
        self.output_dir_var = tk.StringVar(
            value=self.config_data.get("output_dir", str(Path.home() / "Pictures" / "whiteboard-doctor")))
        dir_frame = ttk.Frame(right)
        dir_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Entry(dir_frame, textvariable=self.output_dir_var, width=20).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(dir_frame, text="...", width=3, command=self._pick_output_dir).pack(side=tk.RIGHT)

        # Prompt
        prompt_frame = ttk.LabelFrame(main, text="Prompt", padding=5)
        prompt_frame.pack(fill=tk.X, pady=(10, 5))

        self.prompt_text = tk.Text(prompt_frame, height=4, wrap=tk.WORD)
        self.prompt_text.insert("1.0", self.config_data.get("prompt", DEFAULT_PROMPT))
        self.prompt_text.pack(fill=tk.X)

        ttk.Button(prompt_frame, text="Reset to Default",
                   command=lambda: (self.prompt_text.delete("1.0", tk.END),
                                    self.prompt_text.insert("1.0", DEFAULT_PROMPT))).pack(anchor=tk.E, pady=(3, 0))

        # Process button + progress
        bottom = ttk.Frame(main)
        bottom.pack(fill=tk.X, pady=(5, 0))

        self.process_btn = ttk.Button(bottom, text="Process", command=self._start_processing)
        self.process_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(bottom, textvariable=self.status_var).pack(side=tk.RIGHT)

    def _prompt_api_key(self):
        dialog = ApiKeyDialog(self)
        if dialog.result:
            self.config_data["api_key"] = dialog.result
            save_config(self.config_data)
            self.status_var.set("API key saved")

    def _add_images(self):
        paths = filedialog.askopenfilenames(
            title="Select whiteboard images",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")])
        for p in paths:
            if p not in self.image_paths:
                self.image_paths.append(p)
                self.image_listbox.insert(tk.END, Path(p).name)

    def _remove_selected(self):
        for idx in reversed(self.image_listbox.curselection()):
            self.image_listbox.delete(idx)
            self.image_paths.pop(idx)

    def _clear_all(self):
        self.image_listbox.delete(0, tk.END)
        self.image_paths.clear()

    def _pick_output_dir(self):
        d = filedialog.askdirectory(title="Select output directory")
        if d:
            self.output_dir_var.set(d)

    def _start_processing(self):
        if self.processing:
            return
        if not self.config_data.get("api_key"):
            self._prompt_api_key()
            if not self.config_data.get("api_key"):
                return
        if not self.image_paths:
            messagebox.showwarning("No images", "Add at least one image first.")
            return

        # Save current settings
        self.config_data["output_format"] = self.format_var.get()
        self.config_data["resolution"] = self.resolution_var.get()
        self.config_data["output_dir"] = self.output_dir_var.get()
        self.config_data["prompt"] = self.prompt_text.get("1.0", tk.END).strip()
        save_config(self.config_data)

        self.processing = True
        self.process_btn.configure(state=tk.DISABLED)
        self.progress["value"] = 0
        self.progress["maximum"] = len(self.image_paths)

        thread = threading.Thread(target=self._process_images, daemon=True)
        thread.start()

    def _process_images(self):
        api_key = self.config_data["api_key"]
        prompt = self.config_data.get("prompt", DEFAULT_PROMPT)
        output_format = self.config_data.get("output_format", "png")
        resolution = self.config_data.get("resolution", "1K")
        output_dir = Path(self.config_data.get("output_dir",
                                                str(Path.home() / "Pictures" / "whiteboard-doctor")))
        output_dir.mkdir(parents=True, exist_ok=True)

        headers = {
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        }

        total = len(self.image_paths)
        for i, img_path in enumerate(list(self.image_paths)):
            name = Path(img_path).stem
            self.after(0, lambda n=name, idx=i: self.status_var.set(f"Processing {idx+1}/{total}: {n}"))

            try:
                data_url = image_to_data_url(img_path)
                payload = {
                    "prompt": prompt,
                    "image_urls": [data_url],
                    "output_format": output_format,
                    "resolution": resolution,
                    "sync_mode": True,
                }

                resp = requests.post(FAL_SUBMIT_URL, headers=headers, json=payload, timeout=120)
                resp.raise_for_status()
                result = resp.json()

                # sync_mode returns result directly
                images = result.get("images", [])
                if not images:
                    self.after(0, lambda n=name: self.status_var.set(f"No output for {n}"))
                    continue

                img_url = images[0]["url"]
                img_resp = requests.get(img_url, timeout=60)
                img_resp.raise_for_status()

                out_path = output_dir / f"{name}_cleaned.{output_format}"
                with open(out_path, "wb") as f:
                    f.write(img_resp.content)

            except requests.exceptions.HTTPError as e:
                error_body = ""
                if e.response is not None:
                    try:
                        error_body = e.response.json().get("detail", e.response.text[:200])
                    except Exception:
                        error_body = e.response.text[:200]
                self.after(0, lambda n=name, err=error_body: messagebox.showerror(
                    "API Error", f"Failed to process {n}:\n{err}"))
            except Exception as e:
                self.after(0, lambda n=name, err=str(e): messagebox.showerror(
                    "Error", f"Failed to process {n}:\n{err}"))

            self.after(0, lambda idx=i: self.progress.configure(value=idx + 1))

        self.after(0, self._processing_done, output_dir)

    def _processing_done(self, output_dir):
        self.processing = False
        self.process_btn.configure(state=tk.NORMAL)
        self.status_var.set("Done!")
        messagebox.showinfo("Complete", f"Processed images saved to:\n{output_dir}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
