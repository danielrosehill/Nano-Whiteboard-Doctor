#!/usr/bin/env python3
"""Nano Whiteboard Doctor - Clean up whiteboard photos with Fal AI Nano Banana 2."""

import base64
import json
import sys
from pathlib import Path

import requests
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QVBoxLayout, QWidget,
)

CONFIG_DIR = Path.home() / ".config" / "nano-whiteboard-doctor"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_PROMPT = (
    "Take this whiteboard photograph and convert it into a beautiful and polished "
    "graphic featuring clear labels and icons. Preserve all the original content, "
    "text, and diagrams but make them clean, well-organized, and professional looking."
)

FAL_SUBMIT_URL = "https://queue.fal.run/fal-ai/nano-banana-2/edit"

STYLESHEET = """
QMainWindow {
    background: #1e1e2e;
}
QWidget {
    font-family: 'Segoe UI', 'Ubuntu', sans-serif;
    font-size: 13px;
    color: #cdd6f4;
}
QGroupBox {
    border: 1px solid #45475a;
    border-radius: 8px;
    margin-top: 12px;
    padding: 16px 12px 12px 12px;
    background: #313244;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #89b4fa;
    font-weight: bold;
}
QListWidget {
    background: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 4px;
    outline: none;
}
QListWidget::item {
    padding: 6px 8px;
    border-radius: 4px;
}
QListWidget::item:selected {
    background: #45475a;
    color: #cdd6f4;
}
QListWidget::item:hover {
    background: #363647;
}
QPushButton {
    background: #45475a;
    border: 1px solid #585b70;
    border-radius: 6px;
    padding: 8px 18px;
    color: #cdd6f4;
    font-weight: 500;
}
QPushButton:hover {
    background: #585b70;
    border-color: #6c7086;
}
QPushButton:pressed {
    background: #313244;
}
QPushButton:disabled {
    background: #313244;
    color: #585b70;
    border-color: #45475a;
}
QPushButton#processBtn {
    background: #89b4fa;
    color: #1e1e2e;
    font-weight: bold;
    font-size: 14px;
    padding: 10px 28px;
    border: none;
}
QPushButton#processBtn:hover {
    background: #74c7ec;
}
QPushButton#processBtn:pressed {
    background: #89dceb;
}
QPushButton#processBtn:disabled {
    background: #45475a;
    color: #585b70;
}
QPlainTextEdit {
    background: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px;
    color: #cdd6f4;
    font-size: 12px;
}
QLineEdit {
    background: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 10px;
    color: #cdd6f4;
}
QLineEdit:focus, QPlainTextEdit:focus {
    border-color: #89b4fa;
}
QComboBox {
    background: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 10px;
    color: #cdd6f4;
    min-width: 100px;
}
QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}
QComboBox QAbstractItemView {
    background: #313244;
    border: 1px solid #45475a;
    selection-background-color: #45475a;
    color: #cdd6f4;
}
QProgressBar {
    background: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 6px;
    height: 22px;
    text-align: center;
    color: #cdd6f4;
}
QProgressBar::chunk {
    background: #89b4fa;
    border-radius: 5px;
}
QLabel#statusLabel {
    color: #a6adc8;
    font-size: 12px;
}
QLabel#titleLabel {
    font-size: 20px;
    font-weight: bold;
    color: #89b4fa;
}
"""


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


class ProcessWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str, str)

    def __init__(self, image_paths, api_key, prompt, output_format, resolution, output_dir):
        super().__init__()
        self.image_paths = image_paths
        self.api_key = api_key
        self.prompt = prompt
        self.output_format = output_format
        self.resolution = resolution
        self.output_dir = Path(output_dir)

    def run(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        headers = {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json",
        }
        total = len(self.image_paths)

        for i, img_path in enumerate(self.image_paths):
            name = Path(img_path).stem
            self.progress.emit(i, total, name)

            try:
                data_url = image_to_data_url(img_path)
                payload = {
                    "prompt": self.prompt,
                    "image_urls": [data_url],
                    "output_format": self.output_format,
                    "resolution": self.resolution,
                    "sync_mode": True,
                }

                resp = requests.post(FAL_SUBMIT_URL, headers=headers, json=payload, timeout=120)
                resp.raise_for_status()
                result = resp.json()

                images = result.get("images", [])
                if not images:
                    self.error.emit(name, "No output image returned")
                    continue

                img_url = images[0]["url"]
                img_resp = requests.get(img_url, timeout=60)
                img_resp.raise_for_status()

                out_path = self.output_dir / f"{name}_cleaned.{self.output_format}"
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
        self.finished.emit(str(self.output_dir))


class ApiKeyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fal AI API Key")
        self.setFixedWidth(450)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Enter your Fal AI API key:"))
        hint = QLabel("Get one at fal.ai/dashboard/keys")
        hint.setStyleSheet("color: #a6adc8; font-size: 11px;")
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nano Whiteboard Doctor")
        self.setMinimumSize(800, 600)
        self.resize(950, 700)

        self.config_data = load_config()
        self.image_paths = []
        self.worker = None

        self._build_ui()
        self._build_menu()

        if not self.config_data.get("api_key"):
            QTimer.singleShot(300, self._prompt_api_key)

    def _build_menu(self):
        menu = self.menuBar()
        settings = menu.addMenu("Settings")
        key_action = QAction("Set API Key...", self)
        key_action.triggered.connect(self._prompt_api_key)
        settings.addAction(key_action)
        settings.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        settings.addAction(quit_action)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Nano Whiteboard Doctor")
        title.setObjectName("titleLabel")
        root.addWidget(title)

        # Main content
        content = QHBoxLayout()
        content.setSpacing(12)

        # Left: image list
        img_group = QGroupBox("Images")
        img_layout = QVBoxLayout(img_group)

        self.image_list = QListWidget()
        self.image_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        img_layout.addWidget(self.image_list)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        for label, slot in [("Add Images", self._add_images),
                            ("Remove Selected", self._remove_selected),
                            ("Clear All", self._clear_all)]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        img_layout.addLayout(btn_row)

        content.addWidget(img_group, stretch=3)

        # Right: settings
        settings_group = QGroupBox("Settings")
        settings_form = QFormLayout(settings_group)
        settings_form.setSpacing(10)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["png", "jpeg", "webp"])
        self.format_combo.setCurrentText(self.config_data.get("output_format", "png"))
        settings_form.addRow("Output Format:", self.format_combo)

        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["0.5K", "1K", "2K", "4K"])
        self.resolution_combo.setCurrentText(self.config_data.get("resolution", "1K"))
        settings_form.addRow("Resolution:", self.resolution_combo)

        dir_row = QHBoxLayout()
        self.output_dir_edit = QLineEdit(
            self.config_data.get("output_dir", str(Path.home() / "Pictures" / "whiteboard-doctor")))
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(36)
        browse_btn.clicked.connect(self._pick_output_dir)
        dir_row.addWidget(self.output_dir_edit)
        dir_row.addWidget(browse_btn)
        settings_form.addRow("Output Dir:", dir_row)

        content.addWidget(settings_group, stretch=1)
        root.addLayout(content)

        # Prompt
        prompt_group = QGroupBox("Prompt")
        prompt_layout = QVBoxLayout(prompt_group)
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlainText(self.config_data.get("prompt", DEFAULT_PROMPT))
        self.prompt_edit.setMaximumHeight(100)
        prompt_layout.addWidget(self.prompt_edit)

        reset_btn = QPushButton("Reset to Default")
        reset_btn.clicked.connect(lambda: self.prompt_edit.setPlainText(DEFAULT_PROMPT))
        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset_row.addWidget(reset_btn)
        prompt_layout.addLayout(reset_row)
        root.addWidget(prompt_group)

        # Bottom
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        self.process_btn = QPushButton("Process")
        self.process_btn.setObjectName("processBtn")
        self.process_btn.clicked.connect(self._start_processing)
        bottom.addWidget(self.process_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        bottom.addWidget(self.progress_bar, stretch=1)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        bottom.addWidget(self.status_label)

        root.addLayout(bottom)

    def _prompt_api_key(self):
        dialog = ApiKeyDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            key = dialog.get_key()
            if key:
                self.config_data["api_key"] = key
                save_config(self.config_data)
                self.status_label.setText("API key saved")

    def _add_images(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select whiteboard images", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*)")
        for p in paths:
            if p not in self.image_paths:
                self.image_paths.append(p)
                self.image_list.addItem(Path(p).name)

    def _remove_selected(self):
        for item in reversed(self.image_list.selectedItems()):
            idx = self.image_list.row(item)
            self.image_list.takeItem(idx)
            self.image_paths.pop(idx)

    def _clear_all(self):
        self.image_list.clear()
        self.image_paths.clear()

    def _pick_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select output directory")
        if d:
            self.output_dir_edit.setText(d)

    def _start_processing(self):
        if self.worker and self.worker.isRunning():
            return
        if not self.config_data.get("api_key"):
            self._prompt_api_key()
            if not self.config_data.get("api_key"):
                return
        if not self.image_paths:
            QMessageBox.warning(self, "No images", "Add at least one image first.")
            return

        self.config_data["output_format"] = self.format_combo.currentText()
        self.config_data["resolution"] = self.resolution_combo.currentText()
        self.config_data["output_dir"] = self.output_dir_edit.text()
        self.config_data["prompt"] = self.prompt_edit.toPlainText().strip()
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
            self.config_data.get("output_dir", str(Path.home() / "Pictures" / "whiteboard-doctor")),
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

    def _on_finished(self, output_dir):
        self.process_btn.setEnabled(True)
        self.status_label.setText("Done!")
        QMessageBox.information(self, "Complete", f"Processed images saved to:\n{output_dir}")


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
