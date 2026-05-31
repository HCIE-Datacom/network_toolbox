"""
NetTool - Network Toolbox
Version: V100R009C00SPC500
Author: Tang Wenbo (HCIE-Datacom)
Copyright (C) 2026 Tang Wenbo
License: GNU General Public License v3.0 or later

Plain text configuration file comparison module.
"""

import difflib
import os
import re

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QFont, QTextCursor, QTextFormat, QTextOption
from PySide6.QtWidgets import (
    QFileDialog,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.app import (
    BODY_STYLE,
    BTN_PRIMARY,
    BTN_SECONDARY,
    DESC_STYLE,
    H1_STYLE,
    H2_STYLE,
    H3_STYLE,
    HINT_STYLE,
    set_card_style,
    set_transparent_bg,
)
from core.base_module import ToolModule
from core.logger import logger


MAX_WARN_BYTES = 20 * 1024 * 1024
MAX_PREVIEW_BYTES = 80 * 1024 * 1024
TEXT_EXT_FILTER = "文本配置文件 (*.txt *.cfg *.conf *.log);;所有文件 (*)"


class DropPathEdit(QLineEdit):
    """Line edit that accepts a dropped local file path."""

    fileDropped = Signal(str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            super().dropEvent(event)
            return
        path = urls[0].toLocalFile()
        if path and os.path.isfile(path):
            self.fileDropped.emit(path)
            event.acceptProposedAction()


class DropTextEdit(QPlainTextEdit):
    """Text editor that accepts dropped local files without breaking text drops."""

    fileDropped = Signal(str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.viewport().installEventFilter(self)

    def _local_file_from_event(self, event):
        if not event.mimeData().hasUrls():
            return ""
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and os.path.isfile(path):
                return path
        return ""

    def _handle_drop_event(self, event):
        if event.type() not in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop):
            return False
        path = self._local_file_from_event(event)
        if not path:
            return False
        if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            event.acceptProposedAction()
            return True
        if event.type() == QEvent.Type.Drop:
            self.fileDropped.emit(path)
            event.acceptProposedAction()
            return True
        return False

    def eventFilter(self, watched, event):
        if watched == self.viewport() and self._handle_drop_event(event):
            return True
        return super().eventFilter(watched, event)

    def dragEnterEvent(self, event):
        if self._handle_drop_event(event):
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self._handle_drop_event(event):
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        if self._handle_drop_event(event):
            return
        super().dropEvent(event)


class ConfigCompareModule(ToolModule):
    name = "配置对比"
    icon = "compare"
    description = "对比 txt、cfg、conf、log 等普通文本配置文件，支持忽略规则、差异高亮和差异跳转。"

    def build(self, parent: QWidget):
        if parent.layout() is None:
            parent.setLayout(QVBoxLayout(parent))
        layout = parent.layout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel(self.name)
        title.setStyleSheet(H1_STYLE)
        layout.addWidget(title)
        layout.addSpacing(5)

        desc = QLabel(self.description)
        desc.setStyleSheet(DESC_STYLE)
        desc.setWordWrap(True)
        layout.addWidget(desc)
        layout.addSpacing(14)

        self._old_path = ""
        self._new_path = ""
        self._rows = []
        self._diff_rows = []
        self._current_diff_index = -1
        self._syncing_scroll = False
        self._rendering = False
        self._old_source_text = ""
        self._new_source_text = ""

        control_card = QFrame()
        set_card_style(control_card)
        control_layout = QVBoxLayout(control_card)
        control_layout.setContentsMargins(15, 12, 15, 12)
        control_layout.setSpacing(10)

        control_layout.addWidget(self._make_path_row())
        control_layout.addWidget(self._make_option_row())

        layout.addWidget(control_card)
        layout.addSpacing(14)

        summary_row = QWidget()
        set_transparent_bg(summary_row)
        summary_layout = QHBoxLayout(summary_row)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(8)

        self._summary_label = QLabel("选择文件或直接在下方粘贴配置后点击开始对比")
        self._summary_label.setStyleSheet(H3_STYLE)
        summary_layout.addWidget(self._summary_label, stretch=1)

        self._prev_btn = QPushButton("上一个差异")
        self._prev_btn.setStyleSheet(BTN_SECONDARY)
        self._prev_btn.setFixedHeight(36)
        self._prev_btn.clicked.connect(lambda: self._jump_diff(-1))
        self._prev_btn.setEnabled(False)
        summary_layout.addWidget(self._prev_btn)

        self._next_btn = QPushButton("下一个差异")
        self._next_btn.setStyleSheet(BTN_SECONDARY)
        self._next_btn.setFixedHeight(36)
        self._next_btn.clicked.connect(lambda: self._jump_diff(1))
        self._next_btn.setEnabled(False)
        summary_layout.addWidget(self._next_btn)

        layout.addWidget(summary_row)
        layout.addSpacing(8)

        compare_card = QFrame()
        set_card_style(compare_card)
        compare_layout = QVBoxLayout(compare_card)
        compare_layout.setContentsMargins(14, 12, 14, 14)
        compare_layout.setSpacing(8)

        header = QWidget()
        set_transparent_bg(header)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)
        header_layout.addWidget(self._make_pane_title("旧配置"))
        header_layout.addWidget(self._make_pane_title("新配置"))
        compare_layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(10)
        splitter.setStyleSheet("""
            QSplitter { background: transparent; }
            QSplitter::handle {
                background: #eef2f6;
                width: 10px;
                margin: 6px 3px;
                border-radius: 5px;
            }
            QSplitter::handle:hover {
                background: #dce5ec;
            }
        """)

        self._old_view = self._make_text_view("old")
        self._new_view = self._make_text_view("new")
        self._old_view.textChanged.connect(lambda: self._on_editor_changed("old"))
        self._new_view.textChanged.connect(lambda: self._on_editor_changed("new"))
        splitter.addWidget(self._old_view)
        splitter.addWidget(self._new_view)
        splitter.setSizes([1, 1])
        compare_layout.addWidget(splitter, stretch=1)

        layout.addWidget(compare_card, stretch=1)

        self._old_view.verticalScrollBar().valueChanged.connect(
            lambda value: self._sync_scroll(self._old_view, self._new_view, value)
        )
        self._new_view.verticalScrollBar().valueChanged.connect(
            lambda value: self._sync_scroll(self._new_view, self._old_view, value)
        )

    def _make_path_row(self):
        row = QWidget()
        set_transparent_bg(row)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)

        self._old_path_edit = self._make_path_group(row_layout, "旧配置", "old")
        self._new_path_edit = self._make_path_group(row_layout, "新配置", "new")
        return row

    def _make_path_group(self, row_layout, label_text, side):
        label = QLabel(label_text)
        label.setStyleSheet(H3_STYLE)
        label.setFixedWidth(48)
        row_layout.addWidget(label)

        path_edit = DropPathEdit()
        path_edit.setReadOnly(True)
        path_edit.setPlaceholderText("选择或拖入 .txt / .cfg / .conf / .log 文件")
        path_edit.setMinimumHeight(38)
        path_edit.fileDropped.connect(lambda path, s=side: self._set_file(s, path))
        row_layout.addWidget(path_edit, stretch=1)

        choose_btn = QPushButton("选择")
        choose_btn.setStyleSheet(BTN_SECONDARY)
        choose_btn.setFixedSize(78, 38)
        choose_btn.clicked.connect(lambda checked=False, s=side: self._choose_file(s))
        row_layout.addWidget(choose_btn)

        return path_edit

    def _make_option_row(self):
        row = QWidget()
        set_transparent_bg(row)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(12)

        self._ignore_blank = self._make_check("忽略空行", checked=False)
        self._trim_space = self._make_check("忽略首尾空格", checked=True)
        self._ignore_case = self._make_check("忽略大小写", checked=False)
        self._ignore_multi_space = self._make_check("忽略连续空格", checked=False)
        self._diff_only = self._make_check("只显示差异", checked=False)

        for check in (
            self._ignore_blank,
            self._trim_space,
            self._ignore_case,
            self._ignore_multi_space,
            self._diff_only,
        ):
            check.stateChanged.connect(self._compare_if_ready)
            row_layout.addWidget(check)

        row_layout.addStretch(1)

        clear_btn = QPushButton("清空")
        clear_btn.setStyleSheet(BTN_SECONDARY)
        clear_btn.setFixedSize(78, 38)
        clear_btn.clicked.connect(self._clear)
        row_layout.addWidget(clear_btn)

        compare_btn = QPushButton("开始对比")
        compare_btn.setStyleSheet(BTN_PRIMARY)
        compare_btn.setFixedSize(100, 38)
        compare_btn.clicked.connect(self._compare)
        row_layout.addWidget(compare_btn)

        return row

    def _make_check(self, text, checked=False):
        check = QCheckBox(text)
        check.setChecked(checked)
        check.setStyleSheet("background: transparent;")
        return check

    def _make_pane_title(self, text):
        label = QLabel(text)
        label.setStyleSheet(H2_STYLE)
        return label

    def _make_text_view(self, side):
        view = DropTextEdit()
        view.setReadOnly(False)
        view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        view.setWordWrapMode(QTextOption.WrapMode.NoWrap)
        view.setTabStopDistance(32)
        view.setFont(QFont("Menlo", 12))
        view.setStyleSheet("""
            QPlainTextEdit {
                border: 1px solid #dfe3e8;
                border-radius: 8px;
                background: #ffffff;
                color: #1f2933;
                font-family: "Cascadia Code", "Consolas", "SF Mono", "Menlo", "Microsoft YaHei", monospace;
                font-size: 12px;
                padding: 8px;
                selection-background-color: #b8e5d9;
            }
            QPlainTextEdit QScrollBar:vertical {
                background: transparent;
                border: none;
                width: 10px;
                margin: 7px 3px 7px 2px;
            }
            QPlainTextEdit QScrollBar::handle:vertical {
                background: #cfd8e3;
                border-radius: 5px;
                min-height: 34px;
            }
            QPlainTextEdit QScrollBar::handle:vertical:hover {
                background: #a9b7c6;
            }
            QPlainTextEdit QScrollBar::add-line:vertical,
            QPlainTextEdit QScrollBar::sub-line:vertical {
                height: 0px;
                width: 0px;
                background: transparent;
                border: none;
            }
            QPlainTextEdit QScrollBar::add-page:vertical,
            QPlainTextEdit QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QPlainTextEdit QScrollBar:horizontal {
                background: transparent;
                border: none;
                height: 10px;
                margin: 2px 7px 3px 7px;
            }
            QPlainTextEdit QScrollBar::handle:horizontal {
                background: #cfd8e3;
                border-radius: 5px;
                min-width: 34px;
            }
            QPlainTextEdit QScrollBar::handle:horizontal:hover {
                background: #a9b7c6;
            }
            QPlainTextEdit QScrollBar::add-line:horizontal,
            QPlainTextEdit QScrollBar::sub-line:horizontal {
                height: 0px;
                width: 0px;
                background: transparent;
                border: none;
            }
            QPlainTextEdit QScrollBar::add-page:horizontal,
            QPlainTextEdit QScrollBar::sub-page:horizontal {
                background: transparent;
            }
        """)
        view.setPlaceholderText("选择文件、拖入文件，或直接粘贴配置文本...")
        view.fileDropped.connect(lambda path, s=side: self._set_file(s, path))
        return view

    def _choose_file(self, side):
        path, _ = QFileDialog.getOpenFileName(
            self.app,
            "选择配置文件",
            os.path.expanduser("~"),
            TEXT_EXT_FILTER,
        )
        if path:
            self._set_file(side, path)

    def _set_file(self, side, path):
        if not os.path.isfile(path):
            QMessageBox.warning(self.app, "文件不存在", "请选择有效的文本文件。")
            return
        if os.path.getsize(path) > MAX_PREVIEW_BYTES:
            QMessageBox.warning(self.app, "文件过大", "文件超过 80 MB，暂不建议在界面中直接对比。")
            return

        lines = self._read_lines(path)
        if lines is None:
            return

        if side == "old":
            self._old_path = path
            self._old_path_edit.setText(path)
            self._set_editor_text("old", "\n".join(lines), update_source=True)
            self._old_view.setExtraSelections([])
        else:
            self._new_path = path
            self._new_path_edit.setText(path)
            self._set_editor_text("new", "\n".join(lines), update_source=True)
            self._new_view.setExtraSelections([])
        logger.info(f"[配置对比] 选择{('旧' if side == 'old' else '新')}配置: {path}")
        self._compare_if_ready()

    def _compare_if_ready(self):
        if self._old_source_text.strip() and self._new_source_text.strip():
            self._compare()

    def _on_editor_changed(self, side):
        if self._rendering:
            return
        if side == "old":
            self._old_source_text = self._old_view.toPlainText()
        else:
            self._new_source_text = self._new_view.toPlainText()

    def _set_editor_text(self, side, text, update_source=False):
        if update_source:
            if side == "old":
                self._old_source_text = text
            else:
                self._new_source_text = text
        self._rendering = True
        try:
            if side == "old":
                self._old_view.setPlainText(text)
            else:
                self._new_view.setPlainText(text)
        finally:
            self._rendering = False

    def _clear(self):
        self._old_path = ""
        self._new_path = ""
        self._rows = []
        self._diff_rows = []
        self._current_diff_index = -1
        self._old_source_text = ""
        self._new_source_text = ""
        self._old_path_edit.clear()
        self._new_path_edit.clear()
        self._set_editor_text("old", "")
        self._set_editor_text("new", "")
        self._old_view.setExtraSelections([])
        self._new_view.setExtraSelections([])
        self._summary_label.setText("选择文件或直接在下方粘贴配置后点击开始对比")
        self._prev_btn.setEnabled(False)
        self._next_btn.setEnabled(False)
        logger.info("[配置对比] 清空对比结果")

    def _read_lines(self, path):
        size = os.path.getsize(path)
        if size > MAX_WARN_BYTES:
            ret = QMessageBox.question(
                self.app,
                "文件较大",
                f"{os.path.basename(path)} 超过 20 MB，继续对比可能需要较长时间，是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ret != QMessageBox.StandardButton.Yes:
                return None

        for encoding in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
            try:
                with open(path, "r", encoding=encoding) as f:
                    return f.read().splitlines()
            except UnicodeDecodeError:
                continue
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()

    def _normalize(self, line):
        value = line
        if self._trim_space.isChecked():
            value = value.strip()
        if self._ignore_multi_space.isChecked():
            value = re.sub(r"\s+", " ", value)
        if self._ignore_case.isChecked():
            value = value.lower()
        return value

    def _prepare_lines(self, lines):
        prepared = []
        for number, text in enumerate(lines, start=1):
            norm = self._normalize(text)
            if self._ignore_blank.isChecked() and not norm:
                continue
            prepared.append({"number": number, "text": text, "norm": norm})
        return prepared

    def _compare(self):
        old_text = self._old_source_text
        new_text = self._new_source_text
        if not old_text.strip() or not new_text.strip():
            QMessageBox.information(self.app, "缺少配置内容", "请选择两个文件，或直接在下方左右配置框中粘贴配置内容。")
            return
        old_raw = old_text.splitlines()
        new_raw = new_text.splitlines()

        old_lines = self._prepare_lines(old_raw)
        new_lines = self._prepare_lines(new_raw)
        old_norms = [item["norm"] for item in old_lines]
        new_norms = [item["norm"] for item in new_lines]
        rows = []
        stats = {"equal": 0, "delete": 0, "insert": 0, "replace": 0}

        matcher = difflib.SequenceMatcher(None, old_norms, new_norms, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for old_item, new_item in zip(old_lines[i1:i2], new_lines[j1:j2]):
                    rows.append(("equal", old_item, new_item))
                    stats["equal"] += 1
            elif tag == "delete":
                for old_item in old_lines[i1:i2]:
                    rows.append(("delete", old_item, None))
                    stats["delete"] += 1
            elif tag == "insert":
                for new_item in new_lines[j1:j2]:
                    rows.append(("insert", None, new_item))
                    stats["insert"] += 1
            else:
                old_chunk = old_lines[i1:i2]
                new_chunk = new_lines[j1:j2]
                max_len = max(len(old_chunk), len(new_chunk))
                for idx in range(max_len):
                    old_item = old_chunk[idx] if idx < len(old_chunk) else None
                    new_item = new_chunk[idx] if idx < len(new_chunk) else None
                    if old_item is None:
                        status = "insert"
                        stats["insert"] += 1
                    elif new_item is None:
                        status = "delete"
                        stats["delete"] += 1
                    else:
                        status = "replace"
                        stats["replace"] += 1
                    rows.append((status, old_item, new_item))

        if self._diff_only.isChecked():
            rows = [row for row in rows if row[0] != "equal"]

        self._rows = rows
        self._render_rows(stats, len(old_raw), len(new_raw))
        logger.info(
            "[配置对比] 完成对比: "
            f"{self._display_source_name('old')} vs {self._display_source_name('new')}, "
            f"不同行 {stats['replace']} / 右侧新增 {stats['insert']} / 左侧新增 {stats['delete']}"
        )

    def _display_source_name(self, side):
        path = self._old_path if side == "old" else self._new_path
        return os.path.basename(path) if path else ("旧配置文本" if side == "old" else "新配置文本")

    def _format_line(self, item):
        if item is None:
            return ""
        return item["text"]

    def _render_rows(self, stats, old_total, new_total):
        old_text = []
        new_text = []
        old_marks = []
        new_marks = []
        self._diff_rows = []
        for idx, (status, old_item, new_item) in enumerate(self._rows):
            old_text.append(self._format_line(old_item))
            new_text.append(self._format_line(new_item))
            if status != "equal":
                self._diff_rows.append(idx)
            old_marks.append(status if old_item is not None else "blank")
            new_marks.append(status if new_item is not None else "blank")

        if not self._rows:
            old_text = ["无差异行"]
            new_text = ["无差异行"]
            old_marks = ["equal"]
            new_marks = ["equal"]

        self._set_editor_text("old", "\n".join(old_text))
        self._set_editor_text("new", "\n".join(new_text))
        self._highlight(self._old_view, old_marks, left=True)
        self._highlight(self._new_view, new_marks, left=False)

        total_diff = stats["delete"] + stats["insert"] + stats["replace"]
        self._summary_label.setText(
            f"旧配置 {old_total} 行，新配置 {new_total} 行 | "
            f"不同行 {stats['replace']}，右侧新增 {stats['insert']}，左侧新增 {stats['delete']}，差异合计 {total_diff}"
        )
        self._prev_btn.setEnabled(bool(self._diff_rows))
        self._next_btn.setEnabled(bool(self._diff_rows))
        self._current_diff_index = -1
        if self._diff_rows:
            self._jump_diff(1)

    def _highlight(self, editor, marks, left):
        colors = {
            "delete": QColor("#ffe4e6"),
            "insert": QColor("#ffe4e6"),
            "replace": QColor("#ffe4e6"),
            "blank": QColor("#fff1f2"),
        }
        selections = []
        doc = editor.document()
        for row, status in enumerate(marks):
            if status == "equal":
                continue
            cursor = QTextCursor(doc.findBlockByNumber(row))
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format.setBackground(colors.get(status, QColor("#ffffff")))
            if status != "blank":
                sel.format.setForeground(QColor("#dc2626"))
            sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selections.append(sel)
        editor.setExtraSelections(selections)

    def _jump_diff(self, direction):
        if not self._diff_rows:
            return
        if self._current_diff_index < 0:
            self._current_diff_index = 0 if direction > 0 else len(self._diff_rows) - 1
        else:
            self._current_diff_index = (self._current_diff_index + direction) % len(self._diff_rows)
        row = self._diff_rows[self._current_diff_index]
        self._scroll_to_row(row)
        self._summary_label.setText(
            self._summary_label.text().split(" | 当前差异")[0]
            + f" | 当前差异 {self._current_diff_index + 1}/{len(self._diff_rows)}"
        )

    def _scroll_to_row(self, row):
        for editor in (self._old_view, self._new_view):
            cursor = QTextCursor(editor.document().findBlockByNumber(row))
            editor.moveCursor(QTextCursor.MoveOperation.Start)
            editor.setTextCursor(cursor)
            editor.centerCursor()
            cursor.clearSelection()
            editor.setTextCursor(cursor)

    def _sync_scroll(self, source, target, value):
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        source_bar = source.verticalScrollBar()
        target_bar = target.verticalScrollBar()
        if source_bar.maximum() == 0:
            target_bar.setValue(0)
        else:
            ratio = value / source_bar.maximum()
            target_bar.setValue(int(target_bar.maximum() * ratio))
        self._syncing_scroll = False
