#!/usr/bin/env python3
"""
EchoRepo Manager GUI
A simple PyQt6 front-end for update_repo.py.
Run this from anywhere - it will look for update_repo.py in the same folder,
or let you browse for the repo.

Requirements: PyQt6  (pip install PyQt6)
"""
import sys
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QPlainTextEdit, QTableWidget,
    QTableWidgetItem, QFileDialog, QMessageBox, QGroupBox,
    QHeaderView, QSplitter, QStatusBar, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette, QTextCursor

# -- Paths --------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent.resolve()
UPDATE_SCRIPT = SCRIPT_DIR / "update_repo.py"

# -- Worker thread ------------------------------------------------------------

class Worker(QThread):
    """Runs update_repo.py in a subprocess, streams stdout/stderr to the GUI."""
    line_out = pyqtSignal(str)
    finished = pyqtSignal(int)   # exit code

    def __init__(self, repo_path: Path, args: list[str]):
        super().__init__()
        self.repo_path = repo_path
        self.args = args   # extra CLI args for update_repo.py

    def run(self):
        script = self.repo_path / "update_repo.py"
        cmd = [sys.executable, str(script)] + self.args
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.repo_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            for line in proc.stdout:
                self.line_out.emit(line.rstrip())
            proc.wait()
            self.finished.emit(proc.returncode)
        except Exception as e:
            self.line_out.emit(f"ERROR: {e}")
            self.finished.emit(1)

# -- Styling ------------------------------------------------------------------

DARK_STYLE = """
QMainWindow, QWidget {
    background: #111111;
    color: #c8c8c8;
}
QGroupBox {
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 8px;
    font-size: 11px;
    color: #555;
    text-transform: uppercase;
    letter-spacing: 1px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #7cb342;
}
QLineEdit {
    background: #0d0d0d;
    border: 1px solid #2a2a2a;
    border-radius: 3px;
    padding: 5px 8px;
    color: #bbb;
    font-family: Consolas, monospace;
    font-size: 12px;
}
QLineEdit:focus { border-color: #7cb342; }

QPushButton {
    background: #1e1e1e;
    border: 1px solid #333;
    border-radius: 3px;
    padding: 6px 16px;
    color: #bbb;
    font-size: 12px;
    min-width: 80px;
}
QPushButton:hover { background: #252525; border-color: #7cb342; color: #ddd; }
QPushButton:pressed { background: #181818; }
QPushButton:disabled { color: #444; border-color: #222; }

QPushButton#btn_push {
    background: #1a2a10;
    border-color: #7cb342;
    color: #7cb342;
    font-weight: bold;
}
QPushButton#btn_push:hover { background: #233515; }
QPushButton#btn_push:disabled { background: #141414; border-color: #2a2a2a; color: #3a3a3a; }

QPushButton#btn_bump {
    background: #1a1a2a;
    border-color: #5566aa;
    color: #7788cc;
}
QPushButton#btn_bump:hover { background: #20203a; border-color: #7788cc; }
QPushButton#btn_bump:disabled { background: #141414; border-color: #2a2a2a; color: #3a3a3a; }

QPlainTextEdit {
    background: #080808;
    border: 1px solid #1e1e1e;
    border-radius: 3px;
    color: #999;
    font-family: Consolas, monospace;
    font-size: 12px;
}
QTableWidget {
    background: #0d0d0d;
    border: 1px solid #1e1e1e;
    border-radius: 3px;
    gridline-color: #1a1a1a;
    color: #bbb;
    font-size: 12px;
    selection-background-color: #1e2e10;
    selection-color: #7cb342;
}
QTableWidget::item { padding: 4px 8px; }
QHeaderView::section {
    background: #161616;
    border: none;
    border-bottom: 1px solid #2a2a2a;
    color: #555;
    padding: 5px 8px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
}
QStatusBar {
    background: #0d0d0d;
    color: #444;
    font-size: 11px;
    border-top: 1px solid #1e1e1e;
}
QLabel { color: #999; }
QLabel#url_label { color: #7cb342; font-family: Consolas, monospace; font-size: 11px; }
QLabel#section_title { color: #555; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
QSplitter::handle { background: #1e1e1e; }
"""

# -- Main Window ---------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EchoRepo Manager")
        self.setMinimumSize(700, 580)
        self.resize(820, 660)
        self.setStyleSheet(DARK_STYLE)

        self._worker: Worker | None = None
        self._repo_path: Path | None = None

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setSpacing(10)
        root_layout.setContentsMargins(14, 12, 14, 8)

        # -- Repo path row --------------------------------------------------
        path_group = QGroupBox("Repo Location")
        path_layout = QHBoxLayout(path_group)
        path_layout.setContentsMargins(10, 12, 10, 10)
        path_layout.setSpacing(6)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Path to EchoRepo folder (contains update_repo.py)")
        self.path_edit.textChanged.connect(self._on_path_changed)

        browse_btn = QPushButton("Browse...")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_repo)

        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(browse_btn)
        root_layout.addWidget(path_group)

        # -- Splitter: addons table | log -----------------------------------
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(4)

        # Addons table
        addon_group = QGroupBox("Addons in Repo")
        addon_layout = QVBoxLayout(addon_group)
        addon_layout.setContentsMargins(10, 12, 10, 10)

        self.addon_table = QTableWidget(0, 3)
        self.addon_table.setHorizontalHeaderLabels(["Addon ID", "Name", "Version"])
        self.addon_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.addon_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.addon_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.addon_table.setColumnWidth(2, 90)
        self.addon_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.addon_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.addon_table.verticalHeader().setVisible(False)
        self.addon_table.setAlternatingRowColors(True)
        self.addon_table.setStyleSheet(
            "QTableWidget { alternate-background-color: #0a0a0a; }"
        )

        addon_layout.addWidget(self.addon_table)
        splitter.addWidget(addon_group)

        # Log output
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(10, 12, 10, 10)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)

        log_layout.addWidget(self.log)
        splitter.addWidget(log_group)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        root_layout.addWidget(splitter)

        # -- Install URL display --------------------------------------------
        url_frame = QFrame()
        url_layout = QHBoxLayout(url_frame)
        url_layout.setContentsMargins(4, 0, 4, 0)
        url_layout.setSpacing(8)

        lbl = QLabel("Install URL:")
        lbl.setObjectName("section_title")
        lbl.setFixedWidth(68)

        self.url_label = QLabel("-")
        self.url_label.setObjectName("url_label")
        self.url_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.url_label.setWordWrap(False)

        url_layout.addWidget(lbl)
        url_layout.addWidget(self.url_label, 1)
        root_layout.addWidget(url_frame)

        # -- Buttons --------------------------------------------------------
        btn_frame = QFrame()
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        self.btn_validate = QPushButton("Validate")
        self.btn_validate.setToolTip("Check addon.xml files without making any changes")
        self.btn_validate.clicked.connect(lambda: self._run("--validate"))

        self.btn_build = QPushButton("Build Only")
        self.btn_build.setToolTip("Rebuild zips and addons.xml - no version bump, no git")
        self.btn_build.clicked.connect(lambda: self._run("--no-commit"))

        self.btn_push = QPushButton("[^]  Update && Push")
        self.btn_push.setObjectName("btn_push")
        self.btn_push.setToolTip(
            "Rebuild zips, regenerate addons.xml, commit and push.\n"
            "Does NOT bump the repository.echostorm version.\n"
            "Use this for normal addon updates."
        )
        self.btn_push.clicked.connect(lambda: self._run())

        self.btn_bump = QPushButton("Bump Repo Ver")
        self.btn_bump.setObjectName("btn_bump")
        self.btn_bump.setToolTip(
            "Increment repository.echostorm version, rebuild, commit, push.\n"
            "Only needed when you change the repo addon URLs or metadata.\n"
            "NOT needed for normal addon updates."
        )
        self.btn_bump.clicked.connect(lambda: self._run("--bump-repo"))

        self.btn_refresh = QPushButton("[R] Refresh")
        self.btn_refresh.setToolTip("Re-scan addon folders and refresh the list")
        self.btn_refresh.clicked.connect(self._refresh_addon_list)

        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_validate)
        btn_layout.addWidget(self.btn_build)
        btn_layout.addWidget(self.btn_bump)
        btn_layout.addWidget(self.btn_push)

        root_layout.addWidget(btn_frame)

        # -- Status bar -----------------------------------------------------
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready - open your EchoRepo folder to start.")

        # Auto-detect if running from the repo
        if UPDATE_SCRIPT.exists():
            self.path_edit.setText(str(SCRIPT_DIR))

    # -- Helpers ---------------------------------------------------------------

    def _browse_repo(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select EchoRepo Folder",
            self.path_edit.text() or str(Path.home())
        )
        if folder:
            self.path_edit.setText(folder)

    def _on_path_changed(self, text: str):
        p = Path(text.strip())
        if p.is_dir() and (p / "update_repo.py").exists():
            self._repo_path = p
            self.status.showMessage(f"Repo: {p}")
            self._refresh_addon_list()
            self._set_buttons_enabled(True)
        else:
            self._repo_path = None
            self.addon_table.setRowCount(0)
            self.url_label.setText("-")
            self._set_buttons_enabled(False)
            if text.strip():
                self.status.showMessage("[!]  update_repo.py not found in that folder.")
            else:
                self.status.showMessage("Ready - open your EchoRepo folder to start.")

    def _set_buttons_enabled(self, enabled: bool):
        for btn in (self.btn_validate, self.btn_build, self.btn_push, self.btn_bump, self.btn_refresh):
            btn.setEnabled(enabled)

    def _refresh_addon_list(self):
        if not self._repo_path:
            return

        EXCLUDED = {
            ".git", "__pycache__", "zips", ".vscode", ".idea",
            "venv", "env", "node_modules", ".github"
        }

        self.addon_table.setRowCount(0)
        rows = []

        for item in sorted(self._repo_path.iterdir()):
            if not item.is_dir() or item.name in EXCLUDED:
                continue
            addon_xml = item / "addon.xml"
            if not addon_xml.exists():
                continue
            try:
                tree = ET.parse(addon_xml)
                root = tree.getroot()
                addon_id = root.get("id", "?")
                version = root.get("version", "?")
                name = root.get("name", addon_id)
                rows.append((addon_id, name, version))
            except Exception as e:
                rows.append((item.name, f"(parse error: {e})", "?"))

        self.addon_table.setRowCount(len(rows))
        for i, (addon_id, name, version) in enumerate(rows):
            id_item = QTableWidgetItem(addon_id)
            name_item = QTableWidgetItem(name)
            ver_item = QTableWidgetItem(version)
            ver_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            ver_item.setForeground(QColor("#7cb342"))
            self.addon_table.setItem(i, 0, id_item)
            self.addon_table.setItem(i, 1, name_item)
            self.addon_table.setItem(i, 2, ver_item)

        # Update install URL from existing zip if available
        self._refresh_install_url()

    def _refresh_install_url(self):
        if not self._repo_path:
            return
        zip_dir = self._repo_path / "zips" / "repository.echostorm"
        if zip_dir.exists():
            zips = sorted(zip_dir.glob("repository.echostorm-*.zip"))
            if zips:
                zname = zips[-1].name
                url = f"https://raw.githubusercontent.com/Echo-Storm/EchoRepo/main/zips/repository.echostorm/{zname}"
                self.url_label.setText(url)
                return
        self.url_label.setText("- (run Build to generate zip)")

    # -- Run worker ------------------------------------------------------------

    def _run(self, *args):
        if not self._repo_path:
            QMessageBox.warning(self, "No Repo", "Select a valid repo folder first.")
            return
        if self._worker and self._worker.isRunning():
            return

        extra = list(args)
        is_push = "--no-commit" not in extra and "--validate" not in extra

        if is_push:
            is_bump = "--bump-repo" in extra
            action_desc = (
                "This will bump the repository.echostorm version, rebuild, commit, and push.\n\n"
                "Only do this if you changed the repo addon's URLs or metadata.\nProceed?"
                if is_bump else
                "This will rebuild zips, regenerate addons.xml, commit, and push to GitHub.\n\nProceed?"
            )
            answer = QMessageBox.question(
                self, "Confirm Push", action_desc,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self.log.clear()
        self._log_line(f"{'='*50}")
        self._log_line(f"Running update_repo.py {' '.join(extra) or '(full update)'}")
        self._log_line(f"{'='*50}")

        self._set_buttons_enabled(False)
        self.status.showMessage("Running...")

        self._worker = Worker(self._repo_path, extra)
        self._worker.line_out.connect(self._log_line)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _log_line(self, text: str):
        self.log.appendPlainText(text)
        self.log.moveCursor(QTextCursor.MoveOperation.End)

    def _on_finished(self, exit_code: int):
        self._set_buttons_enabled(True)
        self._refresh_addon_list()
        if exit_code == 0:
            self.status.showMessage(f"[OK] Done ({datetime.now().strftime('%H:%M:%S')})")
            self._log_line("\n[OK] Complete.")
        else:
            self.status.showMessage(f"[!!] Exited with code {exit_code}")
            self._log_line(f"\n[!!] Process exited with code {exit_code}")

# -- Entry point ---------------------------------------------------------------

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Force dark palette base so native widgets don't bleed light
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#111111"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#c8c8c8"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#0d0d0d"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#0a0a0a"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#c8c8c8"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#1e1e1e"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#c8c8c8"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#7cb342"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#0d0d0d"))
    app.setPalette(palette)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
