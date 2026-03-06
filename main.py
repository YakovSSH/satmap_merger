import sys
import json
import os
import threading
from PIL import Image
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QFileDialog, QVBoxLayout, QHBoxLayout, QFrame, QSizePolicy, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


SETTINGS_FILE = os.path.join(get_base_dir(), "settings.json")
OUTPUT_FILE = os.path.join(get_base_dir(), "MergedImages.png")


def merge_by_color_with_tolerance(img1_path, img2_path, output_path, tolerance=15):
    hex_color = "7E7E7E"
    target_r, target_g, target_b = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

    img1 = Image.open(img1_path).convert("RGBA")
    img2 = Image.open(img2_path).convert("RGBA")

    if img1.size != img2.size:
        img2 = img2.resize(img1.size, Image.LANCZOS)

    arr1 = np.array(img1)
    arr2 = np.array(img2)

    r = arr1[:, :, 0].astype(np.int32)
    g = arr1[:, :, 1].astype(np.int32)
    b = arr1[:, :, 2].astype(np.int32)

    mask = (np.abs(r - target_r) <= tolerance) & \
           (np.abs(g - target_g) <= tolerance) & \
           (np.abs(b - target_b) <= tolerance)

    arr1[mask] = arr2[mask]
    Image.fromarray(arr1, "RGBA").save(output_path, format="PNG")


class WorkerSignals(QObject):
    finished = pyqtSignal(str, bool)


class App(QWidget):
    def __init__(self):
        super().__init__()
        self.img1_path = ""
        self.img2_path = ""
        self.signals = WorkerSignals()
        self.signals.finished.connect(self.on_done)
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        self.setWindowTitle("Picture Merge Tool")
        self.setFixedSize(540, 420)
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: Segoe UI;
                font-size: 13px;
            }
            QFrame#card {
                background-color: #2a2a3e;
                border-radius: 10px;
            }
            QPushButton#browse {
                background-color: #3b3b58;
                color: #cdd6f4;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton#browse:hover {
                background-color: #4e4e72;
            }
            QPushButton#merge {
                background-color: #7287fd;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton#merge:hover {
                background-color: #8a9aff;
            }
            QPushButton#merge:disabled {
                background-color: #44475a;
                color: #6272a4;
            }
            QComboBox {
                background-color: #3b3b58;
                border: none;
                border-radius: 6px;
                padding: 5px 10px;
                color: #cdd6f4;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a3e;
                color: #cdd6f4;
                selection-background-color: #7287fd;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(15)

        title = QLabel("Picture Merge Tool")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        subtitle = QLabel("Merges two images together")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #6272a4;")
        main_layout.addWidget(subtitle)

        # File picker card
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(15, 15, 15, 15)
        card_layout.setSpacing(10)

        self.img1_label = self.add_file_row(card_layout, "Base Image (with grey areas)", self.pick_img1)
        self.img2_label = self.add_file_row(card_layout, "Overlay Image (to paste over grey)", self.pick_img2)

        main_layout.addWidget(card)

        # Mode card
        opt_card = QFrame()
        opt_card.setObjectName("card")
        opt_layout = QHBoxLayout(opt_card)
        opt_layout.setContentsMargins(15, 12, 15, 12)
        opt_layout.setSpacing(10)

        opt_layout.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("With Lines", 15)
        self.mode_combo.addItem("Without Lines", 30)
        opt_layout.addWidget(self.mode_combo)
        opt_layout.addStretch()

        main_layout.addWidget(opt_card)

        self.merge_btn = QPushButton("Merge Images")
        self.merge_btn.setObjectName("merge")
        self.merge_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.merge_btn.clicked.connect(self.run_merge)
        main_layout.addWidget(self.merge_btn)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #6272a4;")
        main_layout.addWidget(self.status_label)

    def add_file_row(self, layout, label_text, slot):
        layout.addWidget(QLabel(f"<b>{label_text}</b>"))
        row = QHBoxLayout()
        path_label = QLabel("No file selected")
        path_label.setStyleSheet("color: #6272a4;")
        path_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        path_label.setWordWrap(True)
        btn = QPushButton("Browse")
        btn.setObjectName("browse")
        btn.setFixedWidth(90)
        btn.clicked.connect(slot)
        row.addWidget(path_label)
        row.addWidget(btn)
        layout.addLayout(row)
        return path_label

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    s = json.load(f)
                if s.get('img1') and os.path.exists(s['img1']):
                    self.img1_path = s['img1']
                    self.img1_label.setText(s['img1'])
                    self.img1_label.setStyleSheet("color: #cdd6f4;")
                if s.get('img2') and os.path.exists(s['img2']):
                    self.img2_path = s['img2']
                    self.img2_label.setText(s['img2'])
                    self.img2_label.setStyleSheet("color: #cdd6f4;")
            except Exception:
                pass

    def save_settings(self):
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump({'img1': self.img1_path, 'img2': self.img2_path}, f)
        except Exception:
            pass

    def pick_img1(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Base Image", "", "PNG Images (*.png);;All Files (*)")
        if path:
            self.img1_path = path
            self.img1_label.setText(path)
            self.img1_label.setStyleSheet("color: #cdd6f4;")

    def pick_img2(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Overlay Image", "", "PNG Images (*.png);;All Files (*)")
        if path:
            self.img2_path = path
            self.img2_label.setText(path)
            self.img2_label.setStyleSheet("color: #cdd6f4;")

    def run_merge(self):
        if not self.img1_path or not self.img2_path:
            self.set_status("Please select both images.", "#f9e2af")
            return

        tolerance = self.mode_combo.currentData()

        self.merge_btn.setEnabled(False)
        self.merge_btn.setText("Processing...")
        self.set_status("Processing... please wait.", "#6272a4")

        def task():
            try:
                merge_by_color_with_tolerance(self.img1_path, self.img2_path, OUTPUT_FILE, tolerance)
                self.signals.finished.emit(f"Merge complete! Saved as MergedImages.png", True)
                self.save_settings()
            except Exception as e:
                self.signals.finished.emit(f"Error: {e}", False)

        threading.Thread(target=task, daemon=True).start()

    def on_done(self, message, success):
        self.set_status(message, "#a6e3a1" if success else "#f38ba8")
        self.merge_btn.setEnabled(True)
        self.merge_btn.setText("Merge Images")

    def set_status(self, msg, color):
        self.status_label.setText(msg)
        self.status_label.setStyleSheet(f"color: {color};")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec())