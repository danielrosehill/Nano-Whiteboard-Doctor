#!/usr/bin/env python3
"""Nano Whiteboard Doctor - Clean up whiteboard photos with Fal AI Nano Banana 2."""

import base64
import json
import sys
import time
from pathlib import Path

import requests
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

CONFIG_DIR = Path.home() / ".config" / "nano-whiteboard-doctor"
CONFIG_FILE = CONFIG_DIR / "config.json"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

DEFAULT_PROMPT = (
    "Take this whiteboard photograph and convert it into a beautiful and polished "
    "graphic featuring clear labels and icons. Preserve all the original content, "
    "text, and diagrams but make them clean, well-organized, and professional looking."
)

# Synchronous endpoint - returns results directly
FAL_SYNC_URL = "https://fal.run/fal-ai/nano-banana-2/edit"
# Queue endpoint - for fallback/polling
FAL_QUEUE_URL = "https://queue.fal.run/fal-ai/nano-banana-2/edit"


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


def build_prompt(base_prompt: str, color: bool, bw: bool, handwritten: bool) -> str:
    parts = [base_prompt]
    if color:
        parts.append("Use vibrant, full color in the output.")
    if bw:
        parts.append("Render the output in black and white only.")
    if handwritten:
        parts.append("Preserve the handwritten style and character of the original writing.")
    return " ".join(parts)


def call_fal_api(img_path: str, api_key: str, prompt: str,
                 output_format: str, resolution: str, num_images: int) -> list[dict]:
    """Call Fal API. Try sync endpoint first, fall back to queue + polling."""
    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }
    data_url = image_to_data_url(img_path)
    payload = {
        "prompt": prompt,
        "image_urls": [data_url],
        "output_format": output_format,
        "resolution": resolution,
        "num_images": num_images,
    }

    # Try synchronous endpoint first
    resp = requests.post(FAL_SYNC_URL, headers=headers, json=payload, timeout=300)
    resp.raise_for_status()
    result = resp.json()

    # If we got images directly, return them
    if "images" in result and result["images"]:
        return result["images"]

    # If we got a queue response, poll for result
    request_id = result.get("request_id")
    if not request_id:
        return []

    result_url = f"{FAL_QUEUE_URL}/requests/{request_id}"
    status_url = f"{FAL_QUEUE_URL}/requests/{request_id}/status"

    for _ in range(120):  # up to ~4 minutes
        time.sleep(2)
        status_resp = requests.get(status_url, headers=headers, timeout=30)
        status_resp.raise_for_status()
        status = status_resp.json()
        if status.get("status") == "COMPLETED":
            result_resp = requests.get(result_url, headers=headers, timeout=30)
            result_resp.raise_for_status()
            return result_resp.json().get("images", [])
        if status.get("status") in ("FAILED", "CANCELLED"):
            return []

    return []


class ProcessWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal()
    error = pyqtSignal(str, str)

    def __init__(self, image_paths, api_key, prompt, output_format, resolution, num_images,
                 color, bw, handwritten):
        super().__init__()
        self.image_paths = image_paths
        self.api_key = api_key
        self.prompt = prompt
        self.output_format = output_format
        self.resolution = resolution
        self.num_images = num_images
        self.color = color
        self.bw = bw
        self.handwritten = handwritten

    def run(self):
        total = len(self.image_paths)
        full_prompt = build_prompt(self.prompt, self.color, self.bw, self.handwritten)

        for i, img_path in enumerate(self.image_paths):
            p = Path(img_path)
            name = p.stem
            self.progress.emit(i, total, name)

            try:
                images = call_fal_api(
                    img_path, self.api_key, full_prompt,
                    self.output_format, self.resolution, self.num_images,
                )

                if not images:
                    self.error.emit(name, "No output image returned")
                    continue

                for j, img_data in enumerate(images):
                    img_url = img_data["url"]
                    img_resp = requests.get(img_url, timeout=60)
                    img_resp.raise_for_status()

                    suffix = f"_edited" if len(images) == 1 else f"_edited_{j + 1}"
                    out_path = p.parent / f"{name}{suffix}.{self.output_format}"
                    with open(out_path, "wb") as f:
                        f.write(img_resp.content)

            except requests.exceptions.HTTPError as e:
                error_body = ""
                if e.response is not None:
                    try:
                        error_body = e.response.json().get("detail", e.response.text[:300])
                    except Exception:
                        error_body = e.response.text[:300]
                self.error.emit(name, str(error_body))
            except Exception as e:
                self.error.emit(name, str(e))

        self.progress.emit(total, total, "")
        self.finished.emit()


class DropListWidget(QListWidget):
    """QListWidget that accepts drag-and-drop of image files and folders."""

    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        paths = []
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.is_dir():
                for f in sorted(p.iterdir()):
                    if f.suffix.lower() in IMAGE_EXTS and not f.stem.endswith("_edited"):
                        paths.append(str(f))
            elif p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                paths.append(str(p))
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()


class ApiKeyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fal AI API Key")
        self.setFixedWidth(450)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Enter your Fal AI API key:"))
        hint = QLabel("Get one at fal.ai/dashboard/keys")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)

        self.entry = QLineEdit()
        self.entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.entry.setPlaceholderText("fal-xxxxxxxxxxxxxxxx")
        layout.addWidget(self.entry)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_key(self):
        return self.entry.text().strip()


class SettingsDialog(QDialog):
    """Dialog for editing the prompt and API key."""

    def __init__(self, config_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(550)
        self.config_data = config_data

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # API key
        key_group = QGroupBox("API Key")
        key_layout = QVBoxLayout(key_group)
        self.key_entry = QLineEdit(config_data.get("api_key", ""))
        self.key_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_entry.setPlaceholderText("fal-xxxxxxxxxxxxxxxx")
        key_layout.addWidget(self.key_entry)
        hint = QLabel("Get one at fal.ai/dashboard/keys")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        key_layout.addWidget(hint)
        layout.addWidget(key_group)

        # Prompt
        prompt_group = QGroupBox("Prompt")
        prompt_layout = QVBoxLayout(prompt_group)
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlainText(config_data.get("prompt", DEFAULT_PROMPT))
        self.prompt_edit.setMaximumHeight(120)
        prompt_layout.addWidget(self.prompt_edit)

        reset_btn = QPushButton("Reset to Default")
        reset_btn.clicked.connect(lambda: self.prompt_edit.setPlainText(DEFAULT_PROMPT))
        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset_row.addWidget(reset_btn)
        prompt_layout.addLayout(reset_row)
        layout.addWidget(prompt_group)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        return {
            "api_key": self.key_entry.text().strip(),
            "prompt": self.prompt_edit.toPlainText().strip(),
        }


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nano Whiteboard Doctor")
        self.setMinimumSize(750, 500)
        self.resize(900, 600)

        self.config_data = load_config()
        self.image_paths = []
        self.worker = None

        self._build_ui()
        self._build_menu()

        if not self.config_data.get("api_key"):
            QTimer.singleShot(300, self._open_settings)

    def _build_menu(self):
        menu = self.menuBar()
        settings_menu = menu.addMenu("File")
        settings_action = QAction("Settings...", self)
        settings_action.triggered.connect(self._open_settings)
        settings_menu.addAction(settings_action)
        settings_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        settings_menu.addAction(quit_action)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Nano Whiteboard Doctor")
        font = title.font()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)
        root.addWidget(title)

        # Main content
        content = QHBoxLayout()
        content.setSpacing(12)

        # Left: image list with drag-and-drop
        img_group = QGroupBox("Images (drag and drop files or folders here)")
        img_layout = QVBoxLayout(img_group)

        self.image_list = DropListWidget()
        self.image_list.files_dropped.connect(self._on_files_dropped)
        img_layout.addWidget(self.image_list)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        for label, slot in [("Add Images", self._add_images),
                            ("Add Folder", self._add_folder),
                            ("Remove Selected", self._remove_selected),
                            ("Clear All", self._clear_all)]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        img_layout.addLayout(btn_row)

        content.addWidget(img_group, stretch=3)

        # Right: options
        right = QVBoxLayout()
        right.setSpacing(12)

        # Output settings
        output_group = QGroupBox("Output")
        output_form = QFormLayout(output_group)
        output_form.setSpacing(8)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["png", "jpeg", "webp"])
        self.format_combo.setCurrentText(self.config_data.get("output_format", "png"))
        output_form.addRow("Format:", self.format_combo)

        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["0.5K", "1K", "2K", "4K"])
        self.resolution_combo.setCurrentText(self.config_data.get("resolution", "1K"))
        output_form.addRow("Resolution:", self.resolution_combo)

        self.num_images_spin = QSpinBox()
        self.num_images_spin.setRange(1, 4)
        self.num_images_spin.setValue(self.config_data.get("num_images", 1))
        output_form.addRow("Variants:", self.num_images_spin)

        right.addWidget(output_group)

        # Style options
        style_group = QGroupBox("Style")
        style_layout = QVBoxLayout(style_group)

        self.color_check = QCheckBox("Convert to color")
        self.color_check.setChecked(self.config_data.get("color", False))
        style_layout.addWidget(self.color_check)

        self.bw_check = QCheckBox("Convert to black && white")
        self.bw_check.setChecked(self.config_data.get("bw", False))
        style_layout.addWidget(self.bw_check)

        self.handwritten_check = QCheckBox("Preserve handwritten style")
        self.handwritten_check.setChecked(self.config_data.get("handwritten", False))
        style_layout.addWidget(self.handwritten_check)

        # Make color and B&W mutually exclusive
        self.color_check.toggled.connect(lambda on: self.bw_check.setChecked(False) if on else None)
        self.bw_check.toggled.connect(lambda on: self.color_check.setChecked(False) if on else None)

        right.addWidget(style_group)

        info_label = QLabel("Edited images are saved next to\nthe originals with an _edited suffix.")
        info_label.setStyleSheet("color: gray; font-size: 11px;")
        right.addWidget(info_label)

        right.addStretch()
        content.addLayout(right, stretch=1)
        root.addLayout(content)

        # Bottom
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        self.process_btn = QPushButton("Process")
        font = self.process_btn.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        self.process_btn.setFont(font)
        self.process_btn.clicked.connect(self._start_processing)
        bottom.addWidget(self.process_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        bottom.addWidget(self.progress_bar, stretch=1)

        self.status_label = QLabel("Ready")
        bottom.addWidget(self.status_label)

        root.addLayout(bottom)

    def _open_settings(self):
        dialog = SettingsDialog(self.config_data, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            vals = dialog.get_values()
            if vals["api_key"]:
                self.config_data["api_key"] = vals["api_key"]
            if vals["prompt"]:
                self.config_data["prompt"] = vals["prompt"]
            save_config(self.config_data)
            self.status_label.setText("Settings saved")

    def _on_files_dropped(self, paths):
        for p in paths:
            if p not in self.image_paths:
                self.image_paths.append(p)
                self.image_list.addItem(Path(p).name)

    def _add_images(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select whiteboard images", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*)")
        for p in paths:
            if p not in self.image_paths:
                self.image_paths.append(p)
                self.image_list.addItem(Path(p).name)

    def _add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Select folder with images")
        if d:
            folder = Path(d)
            for f in sorted(folder.iterdir()):
                fp = str(f)
                if f.suffix.lower() in IMAGE_EXTS and not f.stem.endswith("_edited") and fp not in self.image_paths:
                    self.image_paths.append(fp)
                    self.image_list.addItem(f.name)

    def _remove_selected(self):
        for item in reversed(self.image_list.selectedItems()):
            idx = self.image_list.row(item)
            self.image_list.takeItem(idx)
            self.image_paths.pop(idx)

    def _clear_all(self):
        self.image_list.clear()
        self.image_paths.clear()

    def _start_processing(self):
        if self.worker and self.worker.isRunning():
            return
        if not self.config_data.get("api_key"):
            self._open_settings()
            if not self.config_data.get("api_key"):
                return
        if not self.image_paths:
            QMessageBox.warning(self, "No images", "Add at least one image first.")
            return

        # Save current UI state
        self.config_data["output_format"] = self.format_combo.currentText()
        self.config_data["resolution"] = self.resolution_combo.currentText()
        self.config_data["num_images"] = self.num_images_spin.value()
        self.config_data["color"] = self.color_check.isChecked()
        self.config_data["bw"] = self.bw_check.isChecked()
        self.config_data["handwritten"] = self.handwritten_check.isChecked()
        save_config(self.config_data)

        self.process_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(self.image_paths))

        self.worker = ProcessWorker(
            list(self.image_paths),
            self.config_data["api_key"],
            self.config_data.get("prompt", DEFAULT_PROMPT),
            self.config_data.get("output_format", "png"),
            self.config_data.get("resolution", "1K"),
            self.config_data.get("num_images", 1),
            self.color_check.isChecked(),
            self.bw_check.isChecked(),
            self.handwritten_check.isChecked(),
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, current, total, name):
        self.progress_bar.setValue(current)
        if name:
            self.status_label.setText(f"Processing {current + 1}/{total}: {name}")

    def _on_error(self, name, error_msg):
        QMessageBox.critical(self, "Error", f"Failed to process {name}:\n{error_msg}")

    def _on_finished(self):
        self.process_btn.setEnabled(True)
        self.status_label.setText("Done!")
        QMessageBox.information(self, "Complete",
                                "All images processed.\nEdited files saved next to originals with _edited suffix.")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
