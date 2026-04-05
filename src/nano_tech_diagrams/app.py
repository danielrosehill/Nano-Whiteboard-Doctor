#!/usr/bin/env python3
"""Nano Tech Diagrams - Create and edit tech diagrams with Nano Banana 2 (via Fal AI)."""

import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

import requests
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent, QPixmap, QIcon
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QScrollArea, QSpinBox, QSystemTrayIcon, QTabWidget, QVBoxLayout,
    QWidget,
)

from .core import (
    ASPECT_RATIOS, DIAGRAM_TYPE_BY_KEY, DIAGRAM_TYPE_CATEGORIES, DIAGRAM_TYPES,
    IMAGE_EXTS, STYLE_BY_KEY, STYLE_CATEGORIES, STYLE_PRESETS,
    build_img2img_prompt, build_txt2img_prompt, build_whiteboard_prompt,
    call_fal_img2img, call_fal_txt2img, load_config, save_config,
)

# --- Help content ---

HELP_HTML = """
<h2>Nano Tech Diagrams - How to Use</h2>

<p>A desktop tool for creating and editing tech diagrams using
<b>Nano Banana 2</b> (via Fal AI). Three modes are available as tabs.</p>

<h3>Whiteboard Cleanup</h3>
<p>Transform messy whiteboard photos into polished diagrams:</p>
<ul>
  <li>Drag-and-drop or browse to add whiteboard photos</li>
  <li>Double-click an image to add a <b>Word Dictionary</b> for spelling correction</li>
  <li>Select one or more <b>Style Presets</b> (each image is processed per style)</li>
  <li>Click <b>Process</b></li>
</ul>

<h3>Image to Image</h3>
<p>Transform any existing image using a combination of:</p>
<ul>
  <li><b>Diagram Type</b> (optional) - target format like Network Diagram, Flowchart, etc.</li>
  <li><b>Freehand Prompt</b> (optional) - your custom instructions</li>
  <li><b>Style Preset</b> (optional) - visual style to apply</li>
</ul>
<p>At least one of the above must be provided. They are concatenated into a single prompt.</p>

<h3>Text to Image</h3>
<p>Generate a diagram from scratch (no input image) using:</p>
<ul>
  <li><b>Diagram Type</b> (optional) - what kind of diagram to generate</li>
  <li><b>Freehand Prompt</b> (optional) - describe what you want</li>
  <li><b>Style Preset</b> (optional) - visual style to apply</li>
</ul>
<p>At least one of the above must be provided.</p>

<h3>Style Presets</h3>
<p>24 built-in visual styles across categories:</p>
<ul>
  <li><b>Professional</b> - Clean & Polished, Corporate Clean, Minimalist Mono, etc.</li>
  <li><b>Creative</b> - Neon Sign, Comic Book, Pixel Art, Watercolor, etc.</li>
  <li><b>Technical</b> - Blueprint, Terminal Hacker, Dark Mode, GitHub README, etc.</li>
  <li><b>Retro & Fun</b> - Chalkboard, Synthwave, Psychedelic, Woodcut, etc.</li>
  <li><b>Language</b> - Bilingual Hebrew, Translated Hebrew</li>
</ul>

<h3>Diagram Types</h3>
<p>Common tech diagram formats (for Image-to-Image and Text-to-Image):</p>
<ul>
  <li><b>Infrastructure</b> - Network Diagram, Cloud Architecture, Kubernetes, Server Rack</li>
  <li><b>Software</b> - System Architecture, Microservices, API, Database/ER Diagram</li>
  <li><b>Process</b> - Flowchart, Decision Tree, Sequence Diagram, State Machine, CI/CD</li>
  <li><b>Conceptual</b> - Mind Map, Wireframe, Gantt Chart, Comparison Table, Org Chart</li>
</ul>

<h3>Style Editor Tab</h3>
<p>Use the <b>Style Editor</b> tab to view and customise the prompt text for any
style preset. Changes persist across sessions. These styles are shared across all modes.</p>

<h3>Output Settings</h3>
<ul>
  <li><b>Format</b> - PNG, JPEG, or WebP</li>
  <li><b>Resolution</b> - 0.5K, 1K, 2K, or 4K</li>
  <li><b>Variants</b> - Generate 1-4 different outputs per job</li>
  <li><b>Aspect Ratio</b> - Auto or a fixed ratio like 16:9, 4:3, etc.</li>
</ul>

<h3>System Tray</h3>
<p>Closing the window minimises to the system tray. Right-click the tray icon
for options, or click it to restore the window.</p>

<h3>CLI Mode</h3>
<p>Run from the command line for batch processing:</p>
<pre>nano-tech-diagrams image1.jpg --style blueprint
nano-tech-diagrams folder/ --format webp --resolution 2K
nano-tech-diagrams --text "kubernetes cluster with 3 nodes" --style corporate_clean
nano-tech-diagrams --list-styles
nano-tech-diagrams --list-diagram-types</pre>
"""


# --- Workers ---

class Img2ImgWorker(QThread):
    """Background worker for image-to-image jobs (whiteboard cleanup and img2img)."""
    progress = pyqtSignal(int, int, str)
    image_started = pyqtSignal(str)
    image_saved = pyqtSignal(str, str)  # (output_path, source_path)
    finished = pyqtSignal(list)
    error = pyqtSignal(str, str)

    def __init__(self, image_paths, api_key, prompts, output_format, resolution,
                 num_images, aspect_ratio, output_suffixes=None):
        super().__init__()
        self.image_paths = image_paths
        self.api_key = api_key
        self.prompts = prompts
        self.output_format = output_format
        self.resolution = resolution
        self.num_images = num_images
        self.aspect_ratio = aspect_ratio
        self.output_suffixes = output_suffixes or [None] * len(image_paths)

    def run(self):
        total = len(self.image_paths)
        output_paths = []

        for i, img_path in enumerate(self.image_paths):
            p = Path(img_path)
            name = p.stem
            self.progress.emit(i, total, name)
            self.image_started.emit(img_path)

            try:
                images = call_fal_img2img(
                    img_path, self.api_key, self.prompts[i],
                    self.output_format, self.resolution, self.num_images,
                    self.aspect_ratio,
                )

                if not images:
                    self.error.emit(name, "No output image returned")
                    continue

                out_dir = p.parent / "processed"
                out_dir.mkdir(exist_ok=True)

                custom_suffix = self.output_suffixes[i]

                for j, img_data in enumerate(images):
                    img_url = img_data["url"]
                    img_resp = requests.get(img_url, timeout=60)
                    img_resp.raise_for_status()

                    if custom_suffix:
                        suffix = custom_suffix if len(images) == 1 else f"{custom_suffix}_{j + 1}"
                    else:
                        suffix = "_edited" if len(images) == 1 else f"_edited_{j + 1}"

                    out_path = out_dir / f"{name}{suffix}.{self.output_format}"
                    with open(out_path, "wb") as f:
                        f.write(img_resp.content)
                    output_paths.append(str(out_path))
                    self.image_saved.emit(str(out_path), img_path)

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
        self.finished.emit(output_paths)


class Txt2ImgWorker(QThread):
    """Background worker for text-to-image jobs."""
    progress = pyqtSignal(int, int, str)
    image_saved = pyqtSignal(str)  # output_path
    finished = pyqtSignal(list)
    error = pyqtSignal(str, str)

    def __init__(self, prompt, api_key, output_format, resolution,
                 num_images, aspect_ratio, output_dir, name_prefix="generated"):
        super().__init__()
        self.prompt = prompt
        self.api_key = api_key
        self.output_format = output_format
        self.resolution = resolution
        self.num_images = num_images
        self.aspect_ratio = aspect_ratio
        self.output_dir = Path(output_dir)
        self.name_prefix = name_prefix

    def run(self):
        self.progress.emit(0, 1, self.name_prefix)
        output_paths = []

        try:
            images = call_fal_txt2img(
                self.api_key, self.prompt,
                self.output_format, self.resolution, self.num_images,
                self.aspect_ratio,
            )

            if not images:
                self.error.emit(self.name_prefix, "No output image returned")
                self.finished.emit([])
                return

            self.output_dir.mkdir(parents=True, exist_ok=True)

            for j, img_data in enumerate(images):
                img_url = img_data["url"]
                img_resp = requests.get(img_url, timeout=60)
                img_resp.raise_for_status()

                # Find next available filename
                version = 1
                while True:
                    suffix = "" if version == 1 else f"_{version}"
                    variant = "" if len(images) == 1 else f"_{j + 1}"
                    out_path = self.output_dir / f"{self.name_prefix}{suffix}{variant}.{self.output_format}"
                    if not out_path.exists():
                        break
                    version += 1

                with open(out_path, "wb") as f:
                    f.write(img_resp.content)
                output_paths.append(str(out_path))
                self.image_saved.emit(str(out_path))

        except requests.exceptions.HTTPError as e:
            error_body = ""
            if e.response is not None:
                try:
                    error_body = e.response.json().get("detail", e.response.text[:300])
                except Exception:
                    error_body = e.response.text[:300]
            self.error.emit(self.name_prefix, str(error_body))
        except Exception as e:
            self.error.emit(self.name_prefix, str(e))

        self.progress.emit(1, 1, "")
        self.finished.emit(output_paths)


# --- Reusable widgets ---

class ClickableLabel(QLabel):
    """QLabel that emits a clicked signal."""
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class DropListWidget(QListWidget):
    """QListWidget that accepts drag-and-drop of image files and folders, shown as thumbnails."""

    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(False)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setIconSize(QSize(100, 100))
        self.setSpacing(8)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setWrapping(True)
        self.setMovement(QListWidget.Movement.Static)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def _resolve_local_path(self, url):
        """Extract a local file path from a QUrl, with Wayland fallbacks."""
        local = url.toLocalFile()
        if local:
            return local
        raw = url.toString()
        if raw.startswith("file://"):
            return unquote(raw[7:])
        return None

    def dropEvent(self, event: QDropEvent):
        paths = []
        urls = event.mimeData().urls()
        if not urls and event.mimeData().hasText():
            for line in event.mimeData().text().strip().splitlines():
                line = line.strip()
                if line.startswith("file://"):
                    local = unquote(line[7:])
                    p = Path(local)
                    if p.is_dir():
                        for f in sorted(p.iterdir()):
                            if f.suffix.lower() in IMAGE_EXTS and not f.stem.endswith("_edited"):
                                paths.append(str(f))
                    elif p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                        paths.append(str(p))
        else:
            for url in urls:
                local = self._resolve_local_path(url)
                if not local:
                    continue
                p = Path(local)
                if p.is_dir():
                    for f in sorted(p.iterdir()):
                        if f.suffix.lower() in IMAGE_EXTS and not f.stem.endswith("_edited"):
                            paths.append(str(f))
                elif p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                    paths.append(str(p))
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()

    def add_image(self, path: str, has_dict=False):
        """Add an image with a thumbnail icon."""
        pixmap = QPixmap(path)
        if pixmap.isNull():
            icon = QIcon()
        else:
            icon = QIcon(pixmap.scaled(
                100, 100,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        label = Path(path).name
        if has_dict:
            label += " [dict]"
        item = QListWidgetItem(icon, label)
        item.setSizeHint(QSize(120, 130))
        self.addItem(item)


# --- Shared widget builders ---

def build_style_preset_list(config_data, parent=None):
    """Build a QListWidget with checkable style presets organized by category."""
    preset_list = QListWidget(parent)
    preset_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)

    saved_presets = config_data.get("selected_presets")
    if not saved_presets:
        old_preset = config_data.get("preset", "clean_polished")
        saved_presets = [old_preset] if old_preset and old_preset != "custom" else ["clean_polished"]
    if isinstance(saved_presets, str):
        saved_presets = [saved_presets]

    for cat in STYLE_CATEGORIES:
        header = QListWidgetItem(cat)
        header.setFlags(Qt.ItemFlag.NoItemFlags)
        hfont = header.font()
        hfont.setBold(True)
        header.setFont(hfont)
        preset_list.addItem(header)

        for p in STYLE_PRESETS:
            if p[2] == cat:
                item = QListWidgetItem(f"  {p[1]}")
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked if p[0] in saved_presets else Qt.CheckState.Unchecked
                )
                item.setData(Qt.ItemDataRole.UserRole, p[0])
                preset_list.addItem(item)

    return preset_list


def build_diagram_type_combo(parent=None):
    """Build a QComboBox with diagram types organized by category."""
    combo = QComboBox(parent)
    combo.addItem("(None - no diagram type)", "")
    for cat in DIAGRAM_TYPE_CATEGORIES:
        combo.addItem(f"--- {cat} ---", "__separator__")
        idx = combo.count() - 1
        combo.model().item(idx).setEnabled(False)

        for dt in DIAGRAM_TYPES:
            if dt[2] == cat:
                combo.addItem(f"  {dt[1]}", dt[0])
    return combo


def build_output_settings(config_data, parent_layout):
    """Build output format/resolution/variants/aspect-ratio controls. Returns dict of widgets."""
    output_group = QGroupBox("Output Settings")
    output_form = QFormLayout(output_group)
    output_form.setSpacing(8)

    format_combo = QComboBox()
    format_combo.addItems(["png", "jpeg", "webp"])
    format_combo.setCurrentText(config_data.get("output_format", "png"))
    output_form.addRow("Format:", format_combo)

    resolution_combo = QComboBox()
    resolution_combo.addItems(["0.5K", "1K", "2K", "4K"])
    resolution_combo.setCurrentText(config_data.get("resolution", "1K"))
    output_form.addRow("Resolution:", resolution_combo)

    num_images_spin = QSpinBox()
    num_images_spin.setRange(1, 4)
    num_images_spin.setValue(config_data.get("num_images", 1))
    output_form.addRow("Variants:", num_images_spin)

    parent_layout.addWidget(output_group)

    # Aspect ratio
    ar_group = QGroupBox("Aspect Ratio")
    ar_layout = QVBoxLayout(ar_group)
    ar_row1 = QHBoxLayout()
    ar_row2 = QHBoxLayout()
    ar_buttons = {}
    saved_ar = config_data.get("aspect_ratio", "auto")
    for i, ar in enumerate(ASPECT_RATIOS):
        btn = QPushButton(ar)
        btn.setCheckable(True)
        btn.setChecked(ar == saved_ar)
        btn.setMinimumWidth(50)
        ar_buttons[ar] = btn
        if i < 5:
            ar_row1.addWidget(btn)
        else:
            ar_row2.addWidget(btn)
    ar_layout.addLayout(ar_row1)
    ar_layout.addLayout(ar_row2)
    parent_layout.addWidget(ar_group)

    return {
        "format_combo": format_combo,
        "resolution_combo": resolution_combo,
        "num_images_spin": num_images_spin,
        "ar_buttons": ar_buttons,
    }


def wire_ar_buttons(ar_buttons):
    """Connect AR buttons so only one is selected at a time."""
    def select(ratio):
        for ar, btn in ar_buttons.items():
            btn.setChecked(ar == ratio)
    for ar, btn in ar_buttons.items():
        btn.clicked.connect(lambda checked, a=ar: select(a))


def get_selected_ar(ar_buttons):
    for ar, btn in ar_buttons.items():
        if btn.isChecked():
            return ar
    return "auto"


def get_checked_styles(preset_list):
    """Return list of checked style preset keys from a preset QListWidget."""
    selected = []
    for i in range(preset_list.count()):
        item = preset_list.item(i)
        key = item.data(Qt.ItemDataRole.UserRole)
        if key and item.checkState() == Qt.CheckState.Checked:
            selected.append(key)
    return selected


def build_results_area():
    """Build a results thumbnail area. Returns (group, scroll, thumb_layout, new_job_btn, open_folder_btn)."""
    results_group = QGroupBox("Results (click to enlarge)")
    results_layout = QVBoxLayout(results_group)

    results_scroll = QScrollArea()
    results_scroll.setWidgetResizable(True)
    results_scroll.setMinimumHeight(140)
    results_scroll.setMaximumHeight(180)
    results_container = QWidget()
    results_thumb_layout = QHBoxLayout(results_container)
    results_thumb_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
    results_thumb_layout.setSpacing(8)
    results_scroll.setWidget(results_container)
    results_layout.addWidget(results_scroll)

    results_btn_row = QHBoxLayout()
    results_btn_row.addStretch()
    new_job_btn = QPushButton("New Job")
    results_btn_row.addWidget(new_job_btn)
    open_folder_btn = QPushButton("Open Output Folder")
    results_btn_row.addWidget(open_folder_btn)
    results_layout.addLayout(results_btn_row)

    results_group.setVisible(False)

    return results_group, results_scroll, results_thumb_layout, new_job_btn, open_folder_btn


# --- Dialogs ---

class SettingsDialog(QDialog):
    def __init__(self, config_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(450)
        self.config_data = config_data

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        key_group = QGroupBox("Fal AI API Key")
        key_layout = QVBoxLayout(key_group)
        self.key_entry = QLineEdit(config_data.get("api_key", ""))
        self.key_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_entry.setPlaceholderText("fal-xxxxxxxxxxxxxxxx")
        key_layout.addWidget(self.key_entry)
        hint = QLabel("Get one at fal.ai/dashboard/keys")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        key_layout.addWidget(hint)
        layout.addWidget(key_group)

        # Tray behavior
        tray_group = QGroupBox("System Tray")
        tray_layout = QVBoxLayout(tray_group)
        self.minimize_to_tray_cb = QCheckBox("Minimize to system tray on close")
        self.minimize_to_tray_cb.setChecked(config_data.get("minimize_to_tray", True))
        tray_layout.addWidget(self.minimize_to_tray_cb)
        layout.addWidget(tray_group)

        # Default output directory for txt2img
        dir_group = QGroupBox("Text-to-Image Output Directory")
        dir_layout = QHBoxLayout(dir_group)
        self.output_dir_entry = QLineEdit(config_data.get("txt2img_output_dir", ""))
        self.output_dir_entry.setPlaceholderText("(defaults to ~/Pictures/nano-tech-diagrams)")
        dir_layout.addWidget(self.output_dir_entry)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_output_dir)
        dir_layout.addWidget(browse_btn)
        layout.addWidget(dir_group)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select output directory")
        if d:
            self.output_dir_entry.setText(d)

    def get_values(self):
        return {
            "api_key": self.key_entry.text().strip(),
            "minimize_to_tray": self.minimize_to_tray_cb.isChecked(),
            "txt2img_output_dir": self.output_dir_entry.text().strip(),
        }


class DictionaryDialog(QDialog):
    def __init__(self, image_path, current_words=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Word Dictionary - {Path(image_path).name}")
        self.setMinimumWidth(420)
        self.setMinimumHeight(350)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        info = QLabel(
            "Add words, names, or technical terms that appear in this image. "
            "The AI will use these exact spellings instead of guessing."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(info)

        input_row = QHBoxLayout()
        self.word_entry = QLineEdit()
        self.word_entry.setPlaceholderText("Type a word and press Enter...")
        self.word_entry.returnPressed.connect(self._add_word)
        input_row.addWidget(self.word_entry)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_word)
        input_row.addWidget(add_btn)
        layout.addLayout(input_row)

        self.word_list = QListWidget()
        self.word_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        if current_words:
            for w in current_words:
                self.word_list.addItem(w)
        layout.addWidget(self.word_list)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        remove_row = QHBoxLayout()
        remove_row.addStretch()
        remove_row.addWidget(remove_btn)
        layout.addLayout(remove_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_word(self):
        word = self.word_entry.text().strip()
        if word:
            existing = [self.word_list.item(i).text() for i in range(self.word_list.count())]
            if word not in existing:
                self.word_list.addItem(word)
            self.word_entry.clear()

    def _remove_selected(self):
        for item in reversed(self.word_list.selectedItems()):
            self.word_list.takeItem(self.word_list.row(item))

    def get_words(self):
        return [self.word_list.item(i).text() for i in range(self.word_list.count())]


class ImageViewDialog(QDialog):
    touchup_requested = pyqtSignal(str)

    def __init__(self, image_path, source_path=None, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.source_path = source_path
        self.setWindowTitle(Path(image_path).name)
        self.setMinimumSize(600, 400)

        screen = self.screen().geometry() if self.screen() else None
        if screen:
            self.resize(int(screen.width() * 0.8), int(screen.height() * 0.8))
        else:
            self.resize(1200, 800)

        layout = QVBoxLayout(self)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            max_w = self.width() - 40
            max_h = self.height() - 120
            self.image_label.setPixmap(pixmap.scaled(
                max_w, max_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        scroll = QScrollArea()
        scroll.setWidget(self.image_label)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        name_label = QLabel(Path(image_path).name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("font-size: 12px; color: gray;")
        layout.addWidget(name_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        if source_path:
            touchup_btn = QPushButton("Send Back for Touchups")
            touchup_btn.clicked.connect(self._request_touchup)
            btn_row.addWidget(touchup_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _request_touchup(self):
        self.touchup_requested.emit(self.image_path)
        self.accept()


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("How to Use - Nano Tech Diagrams")
        self.setMinimumSize(650, 550)

        layout = QVBoxLayout(self)
        text = QLabel(HELP_HTML)
        text.setWordWrap(True)
        text.setTextFormat(Qt.TextFormat.RichText)

        scroll = QScrollArea()
        scroll.setWidget(text)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


# --- Main Window ---

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nano Tech Diagrams")
        self.setMinimumSize(950, 650)
        self.resize(1100, 750)

        self.config_data = load_config()
        self.worker = None
        self._really_quit = False

        # Whiteboard tab state
        self.wb_image_paths = []
        self.wb_image_dictionaries = {}
        self._wb_output_paths = []
        self._wb_output_to_source = {}

        # Img2img tab state
        self.i2i_image_paths = []
        self.i2i_image_dictionaries = {}
        self._i2i_output_paths = []
        self._i2i_output_to_source = {}

        # Txt2img tab state
        self._t2i_output_paths = []

        # Style editor state
        self._prompt_editors = {}

        # Animation
        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._animate_status)
        self._anim_dots = 0
        self._anim_base_text = ""
        self._active_status_label = None
        self._active_progress_bar = None
        self._active_process_btn = None

        self._last_output_dir = None

        self._build_ui()
        self._build_menu()
        self._setup_tray()

        if not self.config_data.get("api_key"):
            QTimer.singleShot(300, self._open_settings)

    # --- Menu ---

    def _build_menu(self):
        menu = self.menuBar()
        file_menu = menu.addMenu("File")
        settings_action = QAction("Settings...", self)
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)
        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit_app)
        file_menu.addAction(quit_action)

        help_menu = menu.addMenu("Help")
        how_to_action = QAction("How to Use", self)
        how_to_action.triggered.connect(self._show_help)
        help_menu.addAction(how_to_action)

    # --- System Tray ---

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("Nano Tech Diagrams")

        icon = QIcon.fromTheme("applications-graphics")
        if icon.isNull():
            icon = self.windowIcon()
        if icon.isNull():
            icon = QIcon.fromTheme("image-x-generic")
        self.tray_icon.setIcon(icon)

        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show")
        show_action.triggered.connect(self._show_from_tray)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(self._quit_app)
        self.tray_icon.setContextMenu(tray_menu)

        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_from_tray()

    def _show_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _quit_app(self):
        self._really_quit = True
        self.close()

    def closeEvent(self, event):
        if self._really_quit or not self.config_data.get("minimize_to_tray", True):
            self.tray_icon.hide()
            event.accept()
        else:
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "Nano Tech Diagrams",
                "Minimized to system tray. Right-click the icon to quit.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )

    # --- Help / Settings ---

    def _show_help(self):
        HelpDialog(self).exec()

    def _open_settings(self):
        dialog = SettingsDialog(self.config_data, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            vals = dialog.get_values()
            if vals["api_key"]:
                self.config_data["api_key"] = vals["api_key"]
            self.config_data["minimize_to_tray"] = vals["minimize_to_tray"]
            if vals["txt2img_output_dir"]:
                self.config_data["txt2img_output_dir"] = vals["txt2img_output_dir"]
            save_config(self.config_data)

    # --- Animation ---

    def _animate_status(self):
        self._anim_dots = (self._anim_dots + 1) % 4
        dots = "." * (self._anim_dots + 1)
        if self._active_status_label:
            self._active_status_label.setText(f"{self._anim_base_text}{dots}")

    # --- UI Building ---

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Title row
        title_row = QHBoxLayout()
        title = QLabel("Nano Tech Diagrams")
        font = title.font()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)
        title_row.addWidget(title)

        subtitle = QLabel("Powered by Nano Banana 2 via Fal AI")
        subtitle.setStyleSheet("color: gray; font-size: 11px; padding-top: 8px;")
        title_row.addWidget(subtitle)

        title_row.addStretch()

        settings_btn = QPushButton("Settings")
        settings_btn.setToolTip("API key and configuration")
        settings_btn.clicked.connect(self._open_settings)
        title_row.addWidget(settings_btn)

        help_btn = QPushButton("Help")
        help_btn.clicked.connect(self._show_help)
        title_row.addWidget(help_btn)

        root.addLayout(title_row)

        # Tab widget
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, stretch=1)

        self._build_whiteboard_tab()
        self._build_img2img_tab()
        self._build_txt2img_tab()
        self._build_style_editor_tab()

    # ======================================================================
    # TAB 1: WHITEBOARD CLEANUP
    # ======================================================================

    def _build_whiteboard_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)

        content = QHBoxLayout()
        content.setSpacing(12)

        # Left: image list
        img_group = QGroupBox("Whiteboard Photos (drag and drop files or folders)")
        img_layout = QVBoxLayout(img_group)

        self.wb_image_list = DropListWidget()
        self.wb_image_list.files_dropped.connect(self._wb_on_files_dropped)
        self.wb_image_list.itemDoubleClicked.connect(self._wb_open_dictionary)
        img_layout.addWidget(self.wb_image_list)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        for label, slot in [("Add Images", self._wb_add_images),
                            ("Add Folder", self._wb_add_folder),
                            ("Remove Selected", self._wb_remove_selected),
                            ("Clear All", self._wb_clear_all)]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        img_layout.addLayout(btn_row)

        dict_hint = QLabel("Double-click an image to add a word dictionary")
        dict_hint.setStyleSheet("color: gray; font-size: 10px;")
        img_layout.addWidget(dict_hint)

        content.addWidget(img_group, stretch=3)

        # Right: options
        right = QVBoxLayout()
        right.setSpacing(12)

        preset_group = QGroupBox("Style Presets (select one or more)")
        preset_layout = QVBoxLayout(preset_group)
        self.wb_preset_list = build_style_preset_list(self.config_data)
        preset_layout.addWidget(self.wb_preset_list)

        preset_btn_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._select_all_presets(self.wb_preset_list))
        clear_presets_btn = QPushButton("Clear All")
        clear_presets_btn.clicked.connect(lambda: self._clear_all_presets(self.wb_preset_list))
        preset_btn_row.addWidget(select_all_btn)
        preset_btn_row.addWidget(clear_presets_btn)
        preset_btn_row.addStretch()
        preset_layout.addLayout(preset_btn_row)
        right.addWidget(preset_group)

        self.wb_output = build_output_settings(self.config_data, right)
        wire_ar_buttons(self.wb_output["ar_buttons"])

        info_label = QLabel("Outputs saved to processed/ subfolder.")
        info_label.setStyleSheet("color: gray; font-size: 11px;")
        right.addWidget(info_label)

        right.addStretch()
        content.addLayout(right, stretch=1)
        layout.addLayout(content)

        # Bottom bar
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        self.wb_process_btn = QPushButton("Process")
        pfont = self.wb_process_btn.font()
        pfont.setBold(True)
        pfont.setPointSize(pfont.pointSize() + 1)
        self.wb_process_btn.setFont(pfont)
        self.wb_process_btn.clicked.connect(self._wb_start_processing)
        bottom.addWidget(self.wb_process_btn)

        self.wb_progress_bar = QProgressBar()
        self.wb_progress_bar.setValue(0)
        bottom.addWidget(self.wb_progress_bar, stretch=1)

        self.wb_status_label = QLabel("Ready")
        self.wb_status_label.setMinimumWidth(220)
        bottom.addWidget(self.wb_status_label)

        layout.addLayout(bottom)

        # Results
        (self.wb_results_group, _, self.wb_results_thumb_layout,
         wb_new_job_btn, wb_open_folder_btn) = build_results_area()
        wb_new_job_btn.clicked.connect(lambda: self._new_job("wb"))
        wb_open_folder_btn.clicked.connect(self._open_output_folder)
        layout.addWidget(self.wb_results_group)

        self.tabs.addTab(tab, "Whiteboard Cleanup")

    # Whiteboard actions
    def _wb_on_files_dropped(self, paths):
        for p in paths:
            if p not in self.wb_image_paths:
                self.wb_image_paths.append(p)
                has_dict = p in self.wb_image_dictionaries and bool(self.wb_image_dictionaries[p])
                self.wb_image_list.add_image(p, has_dict=has_dict)

    def _wb_add_images(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select whiteboard images", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*)")
        for p in paths:
            if p not in self.wb_image_paths:
                self.wb_image_paths.append(p)
                self.wb_image_list.add_image(p)

    def _wb_add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Select folder with images")
        if d:
            for f in sorted(Path(d).iterdir()):
                fp = str(f)
                if f.suffix.lower() in IMAGE_EXTS and not f.stem.endswith("_edited") and fp not in self.wb_image_paths:
                    self.wb_image_paths.append(fp)
                    self.wb_image_list.add_image(fp)

    def _wb_remove_selected(self):
        for item in reversed(self.wb_image_list.selectedItems()):
            idx = self.wb_image_list.row(item)
            self.wb_image_list.takeItem(idx)
            removed = self.wb_image_paths.pop(idx)
            self.wb_image_dictionaries.pop(removed, None)

    def _wb_clear_all(self):
        self.wb_image_list.clear()
        self.wb_image_paths.clear()
        self.wb_image_dictionaries.clear()

    def _wb_open_dictionary(self, item):
        idx = self.wb_image_list.row(item)
        if idx < 0 or idx >= len(self.wb_image_paths):
            return
        path = self.wb_image_paths[idx]
        current = self.wb_image_dictionaries.get(path, [])
        dialog = DictionaryDialog(path, current, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            words = dialog.get_words()
            if words:
                self.wb_image_dictionaries[path] = words
            elif path in self.wb_image_dictionaries:
                del self.wb_image_dictionaries[path]
            label = Path(path).name
            if words:
                label += " [dict]"
            item.setText(label)

    def _wb_start_processing(self):
        if self.worker and self.worker.isRunning():
            return
        if not self._ensure_api_key():
            return
        if not self.wb_image_paths:
            QMessageBox.warning(self, "No images", "Add at least one whiteboard image.")
            return

        selected_styles = get_checked_styles(self.wb_preset_list)
        if not selected_styles:
            QMessageBox.warning(self, "No styles", "Select at least one style preset.")
            return

        self.config_data["selected_presets"] = selected_styles
        self._save_output_settings(self.wb_output)

        overrides = self.config_data.get("prompt_overrides", {})
        multi = len(selected_styles) > 1
        expanded_paths = []
        expanded_prompts = []
        expanded_suffixes = []

        for img_path in self.wb_image_paths:
            for style_key in selected_styles:
                style_text = overrides.get(style_key, STYLE_BY_KEY[style_key][3])
                words = self.wb_image_dictionaries.get(img_path, [])
                prompt = build_whiteboard_prompt(style_text, words)

                expanded_paths.append(img_path)
                expanded_prompts.append(prompt)
                expanded_suffixes.append(f"_{style_key}_edited" if multi else None)

        self._start_img2img_job(
            expanded_paths, expanded_prompts, expanded_suffixes,
            self.wb_output, self.wb_process_btn, self.wb_progress_bar,
            self.wb_status_label, self.wb_results_group, self.wb_results_thumb_layout,
            self._wb_output_paths, self._wb_output_to_source,
        )

    # ======================================================================
    # TAB 2: IMAGE TO IMAGE
    # ======================================================================

    def _build_img2img_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)

        content = QHBoxLayout()
        content.setSpacing(12)

        # Left: image + prompt
        left = QVBoxLayout()
        left.setSpacing(12)

        img_group = QGroupBox("Input Image (drag and drop)")
        img_layout = QVBoxLayout(img_group)

        self.i2i_image_list = DropListWidget()
        self.i2i_image_list.files_dropped.connect(self._i2i_on_files_dropped)
        self.i2i_image_list.itemDoubleClicked.connect(self._i2i_open_dictionary)
        img_layout.addWidget(self.i2i_image_list)

        btn_row = QHBoxLayout()
        for label, slot in [("Add Images", self._i2i_add_images),
                            ("Remove Selected", self._i2i_remove_selected),
                            ("Clear All", self._i2i_clear_all)]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        img_layout.addLayout(btn_row)

        dict_hint = QLabel("Double-click an image to add a word dictionary")
        dict_hint.setStyleSheet("color: gray; font-size: 10px;")
        img_layout.addWidget(dict_hint)

        left.addWidget(img_group)

        # Diagram type
        dt_group = QGroupBox("Diagram Type (optional)")
        dt_layout = QVBoxLayout(dt_group)
        self.i2i_diagram_type = build_diagram_type_combo()
        dt_layout.addWidget(self.i2i_diagram_type)
        dt_hint = QLabel("Target diagram format to transform the image into")
        dt_hint.setStyleSheet("color: gray; font-size: 10px;")
        dt_layout.addWidget(dt_hint)
        left.addWidget(dt_group)

        # Freehand prompt
        prompt_group = QGroupBox("Freehand Prompt (optional)")
        prompt_layout = QVBoxLayout(prompt_group)
        self.i2i_prompt = QPlainTextEdit()
        self.i2i_prompt.setMaximumHeight(100)
        self.i2i_prompt.setPlaceholderText(
            "Describe how you want the image transformed...\n"
            "e.g. 'Convert this rough sketch into a polished system architecture diagram'"
        )
        prompt_layout.addWidget(self.i2i_prompt)
        left.addWidget(prompt_group)

        content.addLayout(left, stretch=3)

        # Right: style + output
        right = QVBoxLayout()
        right.setSpacing(12)

        style_group = QGroupBox("Style Preset (optional)")
        style_layout = QVBoxLayout(style_group)
        self.i2i_style_combo = QComboBox()
        self.i2i_style_combo.addItem("(None - no style)", "")
        for cat in STYLE_CATEGORIES:
            self.i2i_style_combo.addItem(f"--- {cat} ---", "__separator__")
            idx = self.i2i_style_combo.count() - 1
            self.i2i_style_combo.model().item(idx).setEnabled(False)
            for p in STYLE_PRESETS:
                if p[2] == cat:
                    self.i2i_style_combo.addItem(f"  {p[1]}", p[0])
        style_layout.addWidget(self.i2i_style_combo)
        right.addWidget(style_group)

        self.i2i_output = build_output_settings(self.config_data, right)
        wire_ar_buttons(self.i2i_output["ar_buttons"])

        info_label = QLabel("At least one of: diagram type, prompt, or style required.")
        info_label.setStyleSheet("color: gray; font-size: 11px;")
        info_label.setWordWrap(True)
        right.addWidget(info_label)

        right.addStretch()
        content.addLayout(right, stretch=1)
        layout.addLayout(content)

        # Bottom bar
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        self.i2i_process_btn = QPushButton("Transform")
        pfont = self.i2i_process_btn.font()
        pfont.setBold(True)
        pfont.setPointSize(pfont.pointSize() + 1)
        self.i2i_process_btn.setFont(pfont)
        self.i2i_process_btn.clicked.connect(self._i2i_start_processing)
        bottom.addWidget(self.i2i_process_btn)

        self.i2i_progress_bar = QProgressBar()
        self.i2i_progress_bar.setValue(0)
        bottom.addWidget(self.i2i_progress_bar, stretch=1)

        self.i2i_status_label = QLabel("Ready")
        self.i2i_status_label.setMinimumWidth(220)
        bottom.addWidget(self.i2i_status_label)

        layout.addLayout(bottom)

        # Results
        (self.i2i_results_group, _, self.i2i_results_thumb_layout,
         i2i_new_job_btn, i2i_open_folder_btn) = build_results_area()
        i2i_new_job_btn.clicked.connect(lambda: self._new_job("i2i"))
        i2i_open_folder_btn.clicked.connect(self._open_output_folder)
        layout.addWidget(self.i2i_results_group)

        self.tabs.addTab(tab, "Image to Image")

    # Img2img actions
    def _i2i_on_files_dropped(self, paths):
        for p in paths:
            if p not in self.i2i_image_paths:
                self.i2i_image_paths.append(p)
                has_dict = p in self.i2i_image_dictionaries and bool(self.i2i_image_dictionaries[p])
                self.i2i_image_list.add_image(p, has_dict=has_dict)

    def _i2i_add_images(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select images", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*)")
        for p in paths:
            if p not in self.i2i_image_paths:
                self.i2i_image_paths.append(p)
                self.i2i_image_list.add_image(p)

    def _i2i_remove_selected(self):
        for item in reversed(self.i2i_image_list.selectedItems()):
            idx = self.i2i_image_list.row(item)
            self.i2i_image_list.takeItem(idx)
            removed = self.i2i_image_paths.pop(idx)
            self.i2i_image_dictionaries.pop(removed, None)

    def _i2i_clear_all(self):
        self.i2i_image_list.clear()
        self.i2i_image_paths.clear()
        self.i2i_image_dictionaries.clear()

    def _i2i_open_dictionary(self, item):
        idx = self.i2i_image_list.row(item)
        if idx < 0 or idx >= len(self.i2i_image_paths):
            return
        path = self.i2i_image_paths[idx]
        current = self.i2i_image_dictionaries.get(path, [])
        dialog = DictionaryDialog(path, current, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            words = dialog.get_words()
            if words:
                self.i2i_image_dictionaries[path] = words
            elif path in self.i2i_image_dictionaries:
                del self.i2i_image_dictionaries[path]
            label = Path(path).name
            if words:
                label += " [dict]"
            item.setText(label)

    def _i2i_start_processing(self):
        if self.worker and self.worker.isRunning():
            return
        if not self._ensure_api_key():
            return
        if not self.i2i_image_paths:
            QMessageBox.warning(self, "No images", "Add at least one image.")
            return

        style_key = self.i2i_style_combo.currentData()
        if style_key == "__separator__":
            style_key = ""
        dt_key = self.i2i_diagram_type.currentData()
        if dt_key == "__separator__":
            dt_key = ""
        user_prompt = self.i2i_prompt.toPlainText().strip()

        if not style_key and not dt_key and not user_prompt:
            QMessageBox.warning(self, "No instructions",
                                "Provide at least one of: diagram type, freehand prompt, or style preset.")
            return

        self._save_output_settings(self.i2i_output)
        overrides = self.config_data.get("prompt_overrides", {})

        expanded_paths = []
        expanded_prompts = []
        expanded_suffixes = []

        for img_path in self.i2i_image_paths:
            words = self.i2i_image_dictionaries.get(img_path, [])
            prompt = build_img2img_prompt(
                user_prompt=user_prompt,
                style_key=style_key or None,
                diagram_type_key=dt_key or None,
                style_overrides=overrides,
                dictionary_words=words or None,
            )
            expanded_paths.append(img_path)
            expanded_prompts.append(prompt)
            suffix_parts = []
            if dt_key:
                suffix_parts.append(dt_key)
            if style_key:
                suffix_parts.append(style_key)
            expanded_suffixes.append(f"_{'_'.join(suffix_parts)}_edited" if suffix_parts else None)

        self._start_img2img_job(
            expanded_paths, expanded_prompts, expanded_suffixes,
            self.i2i_output, self.i2i_process_btn, self.i2i_progress_bar,
            self.i2i_status_label, self.i2i_results_group, self.i2i_results_thumb_layout,
            self._i2i_output_paths, self._i2i_output_to_source,
        )

    # ======================================================================
    # TAB 3: TEXT TO IMAGE
    # ======================================================================

    def _build_txt2img_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 0)
        layout.setSpacing(12)

        content = QHBoxLayout()
        content.setSpacing(12)

        # Left: prompt inputs
        left = QVBoxLayout()
        left.setSpacing(12)

        dt_group = QGroupBox("Diagram Type (optional)")
        dt_layout = QVBoxLayout(dt_group)
        self.t2i_diagram_type = build_diagram_type_combo()
        dt_layout.addWidget(self.t2i_diagram_type)
        dt_hint = QLabel("Selects a template prompt for common tech diagram formats")
        dt_hint.setStyleSheet("color: gray; font-size: 10px;")
        dt_layout.addWidget(dt_hint)
        left.addWidget(dt_group)

        prompt_group = QGroupBox("Freehand Prompt (optional)")
        prompt_layout = QVBoxLayout(prompt_group)
        self.t2i_prompt = QPlainTextEdit()
        self.t2i_prompt.setMinimumHeight(120)
        self.t2i_prompt.setPlaceholderText(
            "Describe the diagram you want to generate...\n\n"
            "e.g. 'A Kubernetes cluster with 3 worker nodes, an ingress controller,\n"
            "a Redis cache, and a PostgreSQL database. Show the pod networking.'"
        )
        prompt_layout.addWidget(self.t2i_prompt)
        left.addWidget(prompt_group)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Output name:"))
        self.t2i_name_prefix = QLineEdit("generated_diagram")
        self.t2i_name_prefix.setPlaceholderText("generated_diagram")
        name_row.addWidget(self.t2i_name_prefix)
        left.addLayout(name_row)

        left.addStretch()
        content.addLayout(left, stretch=3)

        # Right: style + output
        right = QVBoxLayout()
        right.setSpacing(12)

        style_group = QGroupBox("Style Preset (optional)")
        style_layout = QVBoxLayout(style_group)
        self.t2i_style_combo = QComboBox()
        self.t2i_style_combo.addItem("(None - no style)", "")
        for cat in STYLE_CATEGORIES:
            self.t2i_style_combo.addItem(f"--- {cat} ---", "__separator__")
            idx = self.t2i_style_combo.count() - 1
            self.t2i_style_combo.model().item(idx).setEnabled(False)
            for p in STYLE_PRESETS:
                if p[2] == cat:
                    self.t2i_style_combo.addItem(f"  {p[1]}", p[0])
        style_layout.addWidget(self.t2i_style_combo)
        right.addWidget(style_group)

        self.t2i_output = build_output_settings(self.config_data, right)
        wire_ar_buttons(self.t2i_output["ar_buttons"])

        info_label = QLabel("At least one of: diagram type, prompt, or style required.\n"
                            "Output saved to configured directory or ~/Pictures/nano-tech-diagrams/")
        info_label.setStyleSheet("color: gray; font-size: 11px;")
        info_label.setWordWrap(True)
        right.addWidget(info_label)

        right.addStretch()
        content.addLayout(right, stretch=1)
        layout.addLayout(content)

        # Bottom bar
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        self.t2i_process_btn = QPushButton("Generate")
        pfont = self.t2i_process_btn.font()
        pfont.setBold(True)
        pfont.setPointSize(pfont.pointSize() + 1)
        self.t2i_process_btn.setFont(pfont)
        self.t2i_process_btn.clicked.connect(self._t2i_start_processing)
        bottom.addWidget(self.t2i_process_btn)

        self.t2i_progress_bar = QProgressBar()
        self.t2i_progress_bar.setValue(0)
        bottom.addWidget(self.t2i_progress_bar, stretch=1)

        self.t2i_status_label = QLabel("Ready")
        self.t2i_status_label.setMinimumWidth(220)
        bottom.addWidget(self.t2i_status_label)

        layout.addLayout(bottom)

        # Results
        (self.t2i_results_group, _, self.t2i_results_thumb_layout,
         t2i_new_job_btn, t2i_open_folder_btn) = build_results_area()
        t2i_new_job_btn.clicked.connect(lambda: self._new_job("t2i"))
        t2i_open_folder_btn.clicked.connect(self._open_output_folder)
        layout.addWidget(self.t2i_results_group)

        self.tabs.addTab(tab, "Text to Image")

    def _t2i_start_processing(self):
        if self.worker and self.worker.isRunning():
            return
        if not self._ensure_api_key():
            return

        style_key = self.t2i_style_combo.currentData()
        if style_key == "__separator__":
            style_key = ""
        dt_key = self.t2i_diagram_type.currentData()
        if dt_key == "__separator__":
            dt_key = ""
        user_prompt = self.t2i_prompt.toPlainText().strip()

        if not style_key and not dt_key and not user_prompt:
            QMessageBox.warning(self, "No instructions",
                                "Provide at least one of: diagram type, freehand prompt, or style preset.")
            return

        self._save_output_settings(self.t2i_output)
        overrides = self.config_data.get("prompt_overrides", {})

        prompt = build_txt2img_prompt(
            user_prompt=user_prompt,
            style_key=style_key or None,
            diagram_type_key=dt_key or None,
            style_overrides=overrides,
        )

        output_dir = self.config_data.get("txt2img_output_dir", "")
        if not output_dir:
            output_dir = str(Path.home() / "Pictures" / "nano-tech-diagrams")

        name_prefix = self.t2i_name_prefix.text().strip() or "generated_diagram"

        # Clear previous results
        self._clear_thumb_layout(self.t2i_results_thumb_layout)
        self._t2i_output_paths.clear()
        self.t2i_results_group.setVisible(True)

        self.t2i_process_btn.setEnabled(False)
        self.t2i_progress_bar.setMaximum(1)
        self.t2i_progress_bar.setValue(0)

        self._active_status_label = self.t2i_status_label
        self._active_progress_bar = self.t2i_progress_bar
        self._active_process_btn = self.t2i_process_btn
        self._anim_base_text = "Generating"
        self._anim_dots = 0
        self._anim_timer.start(400)

        self.worker = Txt2ImgWorker(
            prompt, self.config_data["api_key"],
            self.t2i_output["format_combo"].currentText(),
            self.t2i_output["resolution_combo"].currentText(),
            self.t2i_output["num_images_spin"].value(),
            get_selected_ar(self.t2i_output["ar_buttons"]),
            output_dir, name_prefix,
        )
        self.worker.progress.connect(self._on_progress_generic)
        self.worker.image_saved.connect(self._t2i_on_image_saved)
        self.worker.error.connect(self._on_error_generic)
        self.worker.finished.connect(self._t2i_on_finished)
        self.worker.start()

    def _t2i_on_image_saved(self, path):
        self._t2i_output_paths.append(path)
        self._last_output_dir = str(Path(path).parent)
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            thumb = ClickableLabel()
            thumb.setCursor(Qt.CursorShape.PointingHandCursor)
            thumb.setPixmap(pixmap.scaled(
                120, 120,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
            thumb.setToolTip(f"{Path(path).name} (click to enlarge)")
            thumb.setStyleSheet("border: 1px solid #ccc; padding: 2px;")
            thumb.clicked.connect(lambda p=path: self._show_enlarged_simple(p))
            self.t2i_results_thumb_layout.addWidget(thumb)

    def _t2i_on_finished(self, output_paths):
        self._anim_timer.stop()
        self.t2i_process_btn.setEnabled(True)
        count = len(output_paths)
        self.t2i_status_label.setText(f"Done! {count} output(s) saved.")

    # ======================================================================
    # TAB 4: STYLE EDITOR
    # ======================================================================

    def _build_style_editor_tab(self):
        editor_tab = QWidget()
        editor_layout = QVBoxLayout(editor_tab)
        editor_layout.setContentsMargins(8, 8, 8, 8)
        editor_layout.setSpacing(8)

        info = QLabel(
            "Edit the visual style prompts used by each preset. Changes are saved when you "
            "click Save All and persist across sessions. These styles are shared across all modes."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: gray; font-size: 11px;")
        editor_layout.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(12)

        overrides = self.config_data.get("prompt_overrides", {})

        default_preset = STYLE_PRESETS[0]
        default_header = QLabel("Default Preset")
        dfont = default_header.font()
        dfont.setBold(True)
        dfont.setPointSize(dfont.pointSize() + 2)
        default_header.setFont(dfont)
        scroll_layout.addWidget(default_header)
        self._add_style_editor_entry(scroll_layout, default_preset, overrides)

        sep = QLabel("")
        sep.setFixedHeight(8)
        scroll_layout.addWidget(sep)

        for cat in STYLE_CATEGORIES:
            cat_label = QLabel(cat)
            cfont = cat_label.font()
            cfont.setBold(True)
            cfont.setPointSize(cfont.pointSize() + 1)
            cat_label.setFont(cfont)
            cat_label.setStyleSheet("margin-top: 8px;")
            scroll_layout.addWidget(cat_label)

            for p in STYLE_PRESETS:
                if p[2] == cat and p[0] != default_preset[0]:
                    self._add_style_editor_entry(scroll_layout, p, overrides)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        editor_layout.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton("Save All Styles")
        save_btn.clicked.connect(self._save_style_overrides)
        btn_row.addWidget(save_btn)
        reset_all_btn = QPushButton("Reset All to Defaults")
        reset_all_btn.clicked.connect(self._reset_all_styles)
        btn_row.addWidget(reset_all_btn)
        editor_layout.addLayout(btn_row)

        self.tabs.addTab(editor_tab, "Style Editor")

    def _add_style_editor_entry(self, layout, preset, overrides):
        key, name, cat, default_prompt, default_ar = preset

        header_row = QHBoxLayout()
        name_label = QLabel(name)
        name_label.setStyleSheet("font-weight: bold;")
        header_row.addWidget(name_label)
        cat_label = QLabel(f"({cat}, default AR: {default_ar})")
        cat_label.setStyleSheet("color: gray; font-size: 11px;")
        header_row.addWidget(cat_label)
        header_row.addStretch()
        reset_btn = QPushButton("Reset")
        reset_btn.setToolTip("Reset this style to its built-in default")
        reset_btn.clicked.connect(lambda checked, k=key: self._reset_single_style(k))
        header_row.addWidget(reset_btn)
        layout.addLayout(header_row)

        editor = QPlainTextEdit()
        editor.setPlainText(overrides.get(key, default_prompt))
        editor.setMaximumHeight(100)
        self._prompt_editors[key] = editor
        layout.addWidget(editor)

    def _save_style_overrides(self):
        overrides = {}
        for key, editor in self._prompt_editors.items():
            text = editor.toPlainText().strip()
            if key in STYLE_BY_KEY and text != STYLE_BY_KEY[key][3]:
                overrides[key] = text
        self.config_data["prompt_overrides"] = overrides
        save_config(self.config_data)

    def _reset_single_style(self, key):
        if key in STYLE_BY_KEY and key in self._prompt_editors:
            self._prompt_editors[key].setPlainText(STYLE_BY_KEY[key][3])

    def _reset_all_styles(self):
        for key, editor in self._prompt_editors.items():
            if key in STYLE_BY_KEY:
                editor.setPlainText(STYLE_BY_KEY[key][3])
        self.config_data.pop("prompt_overrides", None)
        save_config(self.config_data)

    # ======================================================================
    # SHARED PROCESSING HELPERS
    # ======================================================================

    def _ensure_api_key(self):
        if not self.config_data.get("api_key"):
            self._open_settings()
        return bool(self.config_data.get("api_key"))

    def _save_output_settings(self, output_widgets):
        self.config_data["output_format"] = output_widgets["format_combo"].currentText()
        self.config_data["resolution"] = output_widgets["resolution_combo"].currentText()
        self.config_data["num_images"] = output_widgets["num_images_spin"].value()
        self.config_data["aspect_ratio"] = get_selected_ar(output_widgets["ar_buttons"])
        save_config(self.config_data)

    def _start_img2img_job(self, paths, prompts, suffixes, output_widgets,
                           process_btn, progress_bar, status_label,
                           results_group, thumb_layout, output_paths_list, output_to_source):
        self._clear_thumb_layout(thumb_layout)
        output_paths_list.clear()
        output_to_source.clear()
        results_group.setVisible(True)

        process_btn.setEnabled(False)
        progress_bar.setValue(0)
        progress_bar.setMaximum(len(paths))

        self._active_status_label = status_label
        self._active_progress_bar = progress_bar
        self._active_process_btn = process_btn
        self._anim_base_text = "Working on it"
        self._anim_dots = 0
        self._anim_timer.start(400)

        self._current_thumb_layout = thumb_layout
        self._current_output_paths = output_paths_list
        self._current_output_to_source = output_to_source

        self.worker = Img2ImgWorker(
            paths, self.config_data["api_key"], prompts,
            output_widgets["format_combo"].currentText(),
            output_widgets["resolution_combo"].currentText(),
            output_widgets["num_images_spin"].value(),
            get_selected_ar(output_widgets["ar_buttons"]),
            output_suffixes=suffixes,
        )
        self.worker.progress.connect(self._on_progress_generic)
        self.worker.image_saved.connect(self._on_image_saved_generic)
        self.worker.error.connect(self._on_error_generic)
        self.worker.finished.connect(self._on_finished_generic)
        self.worker.start()

    def _on_progress_generic(self, current, total, name):
        if self._active_progress_bar:
            self._active_progress_bar.setValue(current)
        if name:
            self._anim_base_text = f"Working on {current + 1}/{total}: {name}"
            self._anim_dots = 0

    def _on_image_saved_generic(self, path, source_path):
        self._current_output_paths.append(path)
        self._current_output_to_source[path] = source_path
        self._last_output_dir = str(Path(path).parent)
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            thumb = ClickableLabel()
            thumb.setCursor(Qt.CursorShape.PointingHandCursor)
            thumb.setPixmap(pixmap.scaled(
                120, 120,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
            thumb.setToolTip(f"{Path(path).name} (click to enlarge)")
            thumb.setStyleSheet("border: 1px solid #ccc; padding: 2px;")
            thumb.clicked.connect(lambda p=path: self._show_enlarged(p))
            self._current_thumb_layout.addWidget(thumb)

    def _on_error_generic(self, name, error_msg):
        QMessageBox.critical(self, "Error", f"Failed to process {name}:\n{error_msg}")

    def _on_finished_generic(self, output_paths):
        self._anim_timer.stop()
        if self._active_process_btn:
            self._active_process_btn.setEnabled(True)
        if self._active_status_label:
            count = len(output_paths)
            self._active_status_label.setText(f"Done! {count} output(s) saved.")

    def _show_enlarged(self, output_path):
        source = None
        for m in (self._wb_output_to_source, self._i2i_output_to_source):
            if output_path in m:
                source = m[output_path]
                break
        dialog = ImageViewDialog(output_path, source_path=source, parent=self)
        dialog.touchup_requested.connect(self._touchup_image)
        dialog.exec()

    def _show_enlarged_simple(self, output_path):
        dialog = ImageViewDialog(output_path, parent=self)
        dialog.exec()

    def _touchup_image(self, output_path):
        source_path = None
        for m in (self._wb_output_to_source, self._i2i_output_to_source):
            if output_path in m:
                source_path = m[output_path]
                break
        if not source_path:
            QMessageBox.warning(self, "Error", "Original source image not found.")
            return

        overrides = self.config_data.get("prompt_overrides", {})
        style_key = "clean_polished"
        wb_styles = get_checked_styles(self.wb_preset_list)
        if wb_styles:
            style_key = wb_styles[0]

        style_text = overrides.get(style_key, STYLE_BY_KEY[style_key][3])
        prompt = build_whiteboard_prompt(style_text)

        stem = Path(source_path).stem
        out_dir = Path(source_path).parent / "processed"
        fmt = self.config_data.get("output_format", "png")
        version = 2
        while (out_dir / f"{stem}_edited_v{version}.{fmt}").exists():
            version += 1
        suffix = f"_edited_v{version}"

        tab_idx = self.tabs.currentIndex()
        if tab_idx == 0:
            process_btn, status_label, progress_bar = self.wb_process_btn, self.wb_status_label, self.wb_progress_bar
        else:
            process_btn, status_label, progress_bar = self.i2i_process_btn, self.i2i_status_label, self.i2i_progress_bar

        process_btn.setEnabled(False)
        self._active_status_label = status_label
        self._active_progress_bar = progress_bar
        self._active_process_btn = process_btn
        self._anim_base_text = f"Touchup: {Path(source_path).name}"
        self._anim_dots = 0
        self._anim_timer.start(400)
        progress_bar.setMaximum(1)
        progress_bar.setValue(0)

        if tab_idx == 0:
            self._current_thumb_layout = self.wb_results_thumb_layout
            self._current_output_paths = self._wb_output_paths
            self._current_output_to_source = self._wb_output_to_source
        else:
            self._current_thumb_layout = self.i2i_results_thumb_layout
            self._current_output_paths = self._i2i_output_paths
            self._current_output_to_source = self._i2i_output_to_source

        self.worker = Img2ImgWorker(
            [source_path], self.config_data["api_key"], [prompt],
            fmt, self.config_data.get("resolution", "1K"),
            self.config_data.get("num_images", 1),
            get_selected_ar(self.wb_output["ar_buttons"]),
            output_suffixes=[suffix],
        )
        self.worker.progress.connect(self._on_progress_generic)
        self.worker.image_saved.connect(self._on_image_saved_generic)
        self.worker.error.connect(self._on_error_generic)
        self.worker.finished.connect(self._on_finished_generic)
        self.worker.start()

    # --- Utility ---

    def _select_all_presets(self, preset_list):
        for i in range(preset_list.count()):
            item = preset_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole):
                item.setCheckState(Qt.CheckState.Checked)

    def _clear_all_presets(self, preset_list):
        for i in range(preset_list.count()):
            item = preset_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole):
                item.setCheckState(Qt.CheckState.Unchecked)

    def _clear_thumb_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _new_job(self, mode):
        if mode == "wb":
            self._clear_thumb_layout(self.wb_results_thumb_layout)
            self.wb_results_group.setVisible(False)
            self.wb_progress_bar.setValue(0)
            self.wb_status_label.setText("Ready")
            self._wb_output_paths.clear()
            self._wb_output_to_source.clear()
        elif mode == "i2i":
            self._clear_thumb_layout(self.i2i_results_thumb_layout)
            self.i2i_results_group.setVisible(False)
            self.i2i_progress_bar.setValue(0)
            self.i2i_status_label.setText("Ready")
            self._i2i_output_paths.clear()
            self._i2i_output_to_source.clear()
        elif mode == "t2i":
            self._clear_thumb_layout(self.t2i_results_thumb_layout)
            self.t2i_results_group.setVisible(False)
            self.t2i_progress_bar.setValue(0)
            self.t2i_status_label.setText("Ready")
            self._t2i_output_paths.clear()

    def _open_output_folder(self):
        if self._last_output_dir and Path(self._last_output_dir).is_dir():
            subprocess.Popen(["xdg-open", self._last_output_dir])


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Nano Tech Diagrams")
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
