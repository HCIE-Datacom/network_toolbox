"""
NetTool - Network Toolbox
Copyright (C) 2026 Tang Wenbo (HCIE-Datacom)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

"""NetworkToolboxApp - main window framework (sidebar + QStackedWidget, PySide6 edition)."""

import os

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QPlainTextEdit, QDialog, QApplication,
    QMenu, QLineEdit,
)
from PySide6.QtCore import Qt, QTimer, QSize, QMetaObject, Slot
from PySide6.QtGui import QFont, QColor, QIcon, QPalette, QKeySequence
from core.logger import logger


def set_card_style(frame: QFrame, border_color="#eeeeee", bg_color="#ffffff"):
    """Apply card style to a QFrame with macOS-safe background rendering.

    Strategy: NO palette, NO autoFillBackground — those leak macOS native
    rendering artifacts (rectangular borders). Pure QSS + WA_StyledBackground
    forces Qt to draw everything itself via stylesheets.
    """
    # Kill macOS native frame rendering
    frame.setFrameShape(QFrame.Shape.NoFrame)
    frame.setLineWidth(0)
    frame.setMidLineWidth(0)
    # Force stylesheet-only rendering on macOS
    frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    frame.setStyleSheet(
        f"QFrame {{ background-color: {bg_color}; border: none; border-radius: 12px; }}"
    )


def set_transparent_bg(widget: QWidget):
    """Set a QWidget to truly transparent background on macOS .app bundles.

    Plain setStyleSheet('background: transparent') is unreliable in the
    macOS cocoa backend — it can fall back to system gray.  This function
    pairs QPalette manipulation with autoFillBackground to guarantee the
    widget inherits its parent's background colour.
    """
    widget.setAutoFillBackground(False)
    pal = widget.palette()
    # Make all standard roles transparent / inherit from parent
    for role in (QPalette.ColorRole.Window,
                 QPalette.ColorRole.Base,
                 QPalette.ColorRole.AlternateBase):
        pal.setColor(role, QColor(0, 0, 0, 0))  # fully transparent
    widget.setPalette(pal)


# ═══════════════ Shared Button Style Constants ═══════════════
# Use these instead of QSS class selectors to avoid Qt QSS precedence issues.
# Apply with:  btn.setStyleSheet(BTN_PRIMARY)

BTN_PRIMARY = """
    QPushButton {
        background: #10a37f; color: #ffffff; border: none;
        border-radius: 8px; padding: 6px 18px; font-size: 13px; font-weight: bold;
    }
    QPushButton:hover { background: #0d8c6d; }
    QPushButton:disabled { background: #a0d5c7; color: #e0e0e0; }
"""

BTN_DANGER = """
    QPushButton {
        background: #dc2626; color: #ffffff; border: none;
        border-radius: 8px; padding: 6px 18px; font-size: 13px; font-weight: bold;
    }
    QPushButton:hover { background: #b91c1c; }
    QPushButton:disabled { background: #f0a0a0; }
"""

BTN_SECONDARY = """
    QPushButton {
        background: #f5f5f5; color: #333333;
        border: 1px solid #e5e5e5; border-radius: 8px;
        padding: 6px 18px; font-size: 13px; font-weight: bold;
    }
    QPushButton:hover { background: #e8e8e8; }
"""

BTN_MODE_ACTIVE = """
    QPushButton {
        background: #10a37f; color: #ffffff; border: none;
        border-radius: 6px; padding: 4px 16px; font-size: 12px; font-weight: bold;
    }
    QPushButton:hover { background: #0d8c6d; }
"""

BTN_MODE_INACTIVE = """
    QPushButton {
        background: transparent; color: #333333; border: none;
        border-radius: 6px; padding: 4px 16px; font-size: 12px; font-weight: bold;
    }
    QPushButton:hover { background: #e0e0e0; }
"""

BTN_NAV_ACTIVE = """
    QPushButton {
        background: #10a37f; color: #ffffff; border: none;
        border-radius: 8px; padding: 8px 12px; font-size: 13px; font-weight: bold; text-align: left;
    }
"""

BTN_NAV_INACTIVE = """
    QPushButton {
        background: transparent; color: #333333; border: none;
        border-radius: 8px; padding: 8px 12px; font-size: 13px; font-weight: bold; text-align: left;
    }
    QPushButton:hover { background: #e8f5ee; }
"""


# ═══════════════ Shared Font Style Constants ═══════════════
# Usage: label.setStyleSheet(H2_STYLE) etc.
# H1: module title, H2: card/section heading, H3: sub-label
# Body: form labels, Hint: status/secondary, Mono: code output

H1_STYLE = "font-size: 18px; font-weight: bold; color: #1f1f1f; background: transparent;"
H2_STYLE = "font-size: 14px; font-weight: bold; color: #333333; background: transparent;"
H3_STYLE = "font-size: 12px; font-weight: bold; color: #333333; background: transparent;"
BODY_STYLE = "font-size: 13px; color: #333333; background: transparent;"
HINT_STYLE = "font-size: 11px; color: #8e8e8e; background: transparent;"
DESC_STYLE = "font-size: 13px; color: #6b6b6b; background: transparent;"

# Shared dark output area style (used by all modules for code/log output)
DARK_OUTPUT = """
    QPlainTextEdit {
        border: 1px solid #e5e5e5; border-radius: 8px;
        background: #1e1e1e; color: #e0e0e0;
        font-family: "Cascadia Code", "Consolas", "SF Mono", "Menlo", "Microsoft YaHei", "Courier New", monospace; font-size: 12px;
        padding: 8px;
    }
    QPlainTextEdit QScrollBar:vertical {
        background: #2a2a2a; border: none; border-radius: 4px; width: 8px; margin: 2px;
    }
    QPlainTextEdit QScrollBar::handle:vertical {
        background: #555555; border-radius: 4px; min-height: 30px;
    }
    QPlainTextEdit QScrollBar::handle:vertical:hover {
        background: #777777;
    }
    QPlainTextEdit QScrollBar::add-line:vertical,
    QPlainTextEdit QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QPlainTextEdit QScrollBar::add-page:vertical,
    QPlainTextEdit QScrollBar::sub-page:vertical {
        background: none;
    }
"""

def set_dark_output(editor: QPlainTextEdit):
    """Apply dark output style + double line spacing to a QPlainTextEdit."""
    editor.setStyleSheet(DARK_OUTPUT)
    # Monkey-patch appendPlainText to add blank line after each line (2x spacing)
    _orig = editor.appendPlainText
    editor.appendPlainText = lambda t: _orig(t + "\n")


# ── QSS Global Stylesheet ──

GLOBAL_QSS = r"""
/* ---- Global Font & Background ---- */
QWidget {
    font-family: "PingFang SC", "Microsoft YaHei", "Hiragino Sans GB", "STHeiti", "WenQuanYi Micro Hei", sans-serif;
    font-size: 13px;
    background: transparent;
}
/* ---- QFrame: kill default rectangular border on macOS ---- */
QFrame {
    border: none;
}

/* ---- QStackedWidget: kill native macOS border ---- */
QStackedWidget {
    border: none;
    background: transparent;
}
QWidget#centralWidget {
    background: #ffffff;
}

/* ---- Main Window ---- */
QMainWindow {
    background: #ffffff;
}

/* ---- Sidebar ---- */
#sidebarCard {
    background: #ffffff;
    border: 1px solid #f0f0f0;
    border-radius: 12px;
}

/* ---- Line Edit ---- */
QLineEdit {
    border: 1px solid #e5e5e5;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    background: #ffffff;
    color: #333333;
    selection-background-color: #10a37f;
    selection-color: #ffffff;
}
QLineEdit:focus {
    border-color: #10a37f;
}

/* ---- Combo Box ---- */
QComboBox {
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 12px;
    background: #f0f0f0;
    color: #333333;
}
QComboBox:hover {
    border-color: #10a37f;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background: #ffffff;
    border: 1px solid #e5e5e5;
    border-radius: 6px;
    selection-background-color: #10a37f;
    selection-color: #ffffff;
}

/* ---- Checkbox ---- */
QCheckBox {
    spacing: 6px;
    font-size: 12px;
    color: #333333;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #d1d5db;
    border-radius: 3px;
    background: #ffffff;
}
QCheckBox::indicator:checked {
    background: #10a37f;
    border-color: #10a37f;
}

/* ---- Progress Bar ---- */
QProgressBar {
    border: none;
    border-radius: 4px;
    background: #f0f0f0;
    height: 8px;
    text-align: center;
    font-size: 10px;
}
QProgressBar::chunk {
    background: #10a37f;
    border-radius: 4px;
}

/* ---- Dialog / Message Box ---- */
QMessageBox {
    background: #ffffff;
}
QMessageBox QLabel {
    color: #333333; font-size: 13px;
}
QMessageBox QPushButton {
    background: #10a37f; color: #ffffff; border: none;
    border-radius: 6px; padding: 6px 24px; font-size: 13px; font-weight: bold;
    min-height: 32px;
}
QMessageBox QPushButton:hover {
    background: #0d8c6d;
}
QMessageBox QPushButton:pressed {
    background: #0b7d5e;
}
QDialogButtonBox QPushButton {
    background: #10a37f; color: #ffffff; border: none;
    border-radius: 6px; padding: 6px 24px; font-size: 13px; font-weight: bold;
    min-height: 32px;
}
QDialogButtonBox QPushButton:hover {
    background: #0d8c6d;
}

/* ---- Context Menu ---- */
QMenu {
    background: #ffffff;
    border: 1px solid #e5e5e5;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 32px 6px 16px;
    font-size: 13px;
    color: #333333;
    border-radius: 4px;
}
QMenu::item:selected {
    background: #e8f5ee;
    color: #10a37f;
}
QMenu::separator {
    height: 1px;
    background: #e5e5e5;
    margin: 4px 8px;
}

/* ---- Table / Tree ---- */
QTreeWidget {
    border: 1px solid #e5e5e5;
    border-radius: 6px;
    background: #ffffff;
    alternate-background-color: #f9f9f9;
    font-size: 12px;
    color: #333333;
}
QTreeWidget::item {
    padding: 4px 6px;
}
QTreeWidget::item:selected {
    background: #e8f5ee;
    color: #333333;
}
QTreeWidget::item:hover {
    background: #f5f5f5;
}
QHeaderView::section {
    background: #f5f5f5;
    border: none;
    border-bottom: 1px solid #e5e5e5;
    padding: 6px 8px;
    font-size: 12px;
    font-weight: bold;
    color: #666666;
}
"""


class NetworkToolboxApp(QMainWindow):
    """Plugin-style main window. Reads MODULE_REGISTRY and auto-generates UI."""

    VERSION = "v1.7.0"

    def __init__(self, module_registry):
        super().__init__()

        # Set app icon FIRST, before window title/style
        self._set_app_icon()

        self.setWindowTitle("NetTool")
        self.resize(1050, 880)
        self.setMinimumSize(900, 700)
        self.setStyleSheet(GLOBAL_QSS)

        # Replace native QLineEdit context menu with styled Qt menu
        self._install_context_menu_filter()

        # Thread-safe callback queue for after()
        self._pending_callbacks = []

        # Central widget holding sidebar + stack
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._build_sidebar(root_layout, module_registry)
        self._build_content_area(root_layout, module_registry)

        # Show first enabled module
        for i, mod in enumerate(self._modules):
            if not mod.disabled:
                self._switch_to(i)
                break

    def _set_app_icon(self):
        """Find and set app icon from project root."""
        logo = self._find_icon_file()
        if logo:
            icon = QIcon(logo)
            self.setWindowIcon(icon)
            QApplication.instance().setWindowIcon(icon)
            QApplication.setApplicationName("NetTool")

    def _find_icon_file(self):
        """Walk up from __file__ to find the icon image."""
        p = os.path.dirname(os.path.abspath(__file__))
        for _ in range(10):
            for name in ("image_icon.png", "icon/app.png", "image.png", "logo_alpha.png", "logo.png"):
                logo = os.path.join(p, name)
                if os.path.isfile(logo):
                    return logo
            parent = os.path.dirname(p)
            if parent == p:
                break
            p = parent
        return None

    def _resolve_icon(self, icon):
        """Resolve icon path — if it's a filename, look in icon/ directory."""
        if os.path.sep in icon or icon.endswith('.png'):
            p = os.path.dirname(os.path.abspath(__file__))
            for _ in range(10):
                full = os.path.join(p, 'icon', icon)
                if os.path.isfile(full):
                    return full
                parent = os.path.dirname(p)
                if parent == p:
                    break
                p = parent
        return icon

    # ═══════════════ Unified Context Menu ═══════════════

    def _install_context_menu_filter(self):
        """Walk all widgets and install per-widget context menu filter."""
        QApplication.instance().installEventFilter(self)
        self._install_menu_on_children(self)

    def _install_menu_on_children(self, parent):
        """Recursively set NoContextMenu and install event filter."""
        for child in parent.findChildren(QWidget):
            if isinstance(child, (QLineEdit, QPlainTextEdit)):
                child.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
                child.installEventFilter(self)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if isinstance(obj, (QLineEdit, QPlainTextEdit)):
            if event.type() == QEvent.Type.ContextMenu:
                return self._show_context_menu(obj, event.globalPos())
        return super().eventFilter(obj, event)

    def _show_context_menu(self, obj, pos):
        menu = QMenu(obj)
        menu.setStyleSheet(GLOBAL_QSS)
        menu.addAction("剪切", obj.cut, QKeySequence.StandardKey.Cut)
        menu.addAction("复制", obj.copy, QKeySequence.StandardKey.Copy)
        menu.addAction("粘贴", obj.paste, QKeySequence.StandardKey.Paste)
        if isinstance(obj, QLineEdit):
            menu.addAction("删除", lambda: obj.backspace() if not obj.hasSelectedText() else obj.del_())
        menu.addSeparator()
        menu.addAction("全选", obj.selectAll, QKeySequence.StandardKey.SelectAll)
        menu.exec_(pos)
        return True

    # ═══════════════ Sidebar ═══════════════

    def _build_sidebar(self, root_layout, module_registry):
        # Outer wrapper with padding
        sidebar_wrapper = QWidget()
        sidebar_wrapper.setFixedWidth(232)
        wrapper_layout = QHBoxLayout(sidebar_wrapper)
        wrapper_layout.setContentsMargins(12, 12, 0, 12)
        wrapper_layout.setSpacing(0)

        # White card
        sidebar_card = QFrame()
        sidebar_card.setFrameShape(QFrame.Shape.NoFrame)
        sidebar_card.setLineWidth(0)
        sidebar_card.setMidLineWidth(0)
        sidebar_card.setObjectName("sidebarCard")
        card_layout = QVBoxLayout(sidebar_card)
        card_layout.setContentsMargins(15, 18, 15, 18)
        card_layout.setSpacing(0)

        # Logo + Title row
        header_row = QWidget()
        header_row.setStyleSheet("background: transparent;")
        hr_layout = QHBoxLayout(header_row)
        hr_layout.setContentsMargins(0, 0, 0, 0)
        hr_layout.setSpacing(10)

        logo_icon = self._find_icon_file()
        if logo_icon:
            logo_lbl = QLabel()
            logo_lbl.setPixmap(QIcon(logo_icon).pixmap(36, 36))
            logo_lbl.setFixedSize(36, 36)
            logo_lbl.setStyleSheet("background: transparent;")
            hr_layout.addWidget(logo_lbl)

        title = QLabel("NetTool")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f1f1f; background: transparent;")
        hr_layout.addWidget(title)
        hr_layout.addStretch(1)

        card_layout.addWidget(header_row)
        card_layout.addSpacing(15)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.NoFrame)
        sep1.setFixedHeight(1)
        sep1.setStyleSheet("background: #e5e5e5; border: none;")
        card_layout.addWidget(sep1)
        card_layout.addSpacing(12)

        # Feature list label
        fl = QLabel("功能列表")
        fl.setStyleSheet("font-size: 11px; color: #8e8e8e; background: transparent;")
        card_layout.addWidget(fl)
        card_layout.addSpacing(8)

        # Nav button area (scrollable if needed)
        self._nav_frame = QWidget()
        nav_layout = QVBoxLayout(self._nav_frame)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(3)
        card_layout.addWidget(self._nav_frame)

        self._nav_buttons = []
        for idx, mod_cls in enumerate(module_registry):
            mod = mod_cls(self)
            btn = self._make_nav_btn(mod.icon, mod.name, idx, mod.disabled, mod.disabled_text)
            nav_layout.addWidget(btn)
            self._nav_buttons.append(btn)
            btn._module = mod

        # Log button
        log_btn = QPushButton("  📋   运行日志")
        log_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #666666; border: none;
                border-radius: 6px; padding: 6px 12px; font-size: 12px; text-align: left;
            }
            QPushButton:hover { background: #e8f5ee; }
        """)
        log_btn.clicked.connect(self._open_log_viewer)
        nav_layout.addWidget(log_btn)

        # Spacer pushes version to bottom
        card_layout.addStretch(1)

        # Bottom separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.NoFrame)
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background: #e5e5e5; border: none;")
        card_layout.addWidget(sep2)
        card_layout.addSpacing(10)

        # Version
        ver = QLabel(f"NetTool {self.VERSION}")
        ver.setStyleSheet("font-size: 11px; color: #8e8e8e; background: transparent;")
        card_layout.addWidget(ver)
        card_layout.addSpacing(2)

        # Copyright
        cr = QLabel("\u00a9 2026 Tang Wenbo. All rights reserved.")
        cr.setStyleSheet("font-size: 9px; color: #b0b0b0; background: transparent;")
        card_layout.addWidget(cr)

        wrapper_layout.addWidget(sidebar_card)
        root_layout.addWidget(sidebar_wrapper)

    def _make_nav_btn(self, icon, label, idx, disabled=False, disabled_text=""):
        label_text = label if not disabled_text else f"{label} ({disabled_text})"
        # Icon can be emoji string or image path
        btn = QPushButton(f"    {label_text}")
        if icon:
            icon_path = self._resolve_icon(icon)
            if os.path.isfile(icon_path):
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(QSize(20, 20))
            else:
                btn.setText(f"  {icon}   {label_text}")
        btn.setStyleSheet(BTN_NAV_INACTIVE)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if disabled:
            btn.setEnabled(False)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent; color: #c0c0c0; border: none;
                    border-radius: 8px; padding: 8px 12px; font-size: 13px; text-align: left;
                }
            """)
        else:
            btn.clicked.connect(lambda checked=False, i=idx: self._switch_to(i))
        return btn

    # ═══════════════ Content Area ═══════════════

    def _build_content_area(self, root_layout, module_registry):
        content_wrapper = QWidget()
        wrapper_layout = QVBoxLayout(content_wrapper)
        wrapper_layout.setContentsMargins(8, 20, 20, 20)
        wrapper_layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")
        wrapper_layout.addWidget(self._stack)

        root_layout.addWidget(content_wrapper, stretch=1)

        self._modules = []
        self._pages = []

        for btn in self._nav_buttons:
            mod = btn._module
            page = QWidget()
            page.setStyleSheet("background: transparent;")
            try:
                mod.build(page)
            except Exception as e:
                logger.exception(f"模块 {mod.name} 构建 UI 失败")
                err = QLabel(f"模块加载失败: {e}")
                err.setStyleSheet("font-size: 14px; color: #e74c3c; background: transparent;")
                page.layout = QVBoxLayout(page)
                page.layout.addWidget(err)
            self._stack.addWidget(page)
            self._modules.append(mod)
            self._pages.append(page)

    def _switch_to(self, index):
        if hasattr(self, "_active_index"):
            old_mod = self._modules[self._active_index]
            try:
                old_mod.on_hide()
            except Exception:
                logger.exception(f"模块 {old_mod.name} on_hide 异常")

        new_mod = self._modules[index]
        self._stack.setCurrentIndex(index)
        # Ensure context menu filter covers new module's widgets
        self._install_menu_on_children(self._pages[index])
        try:
            new_mod.on_show()
        except Exception:
            logger.exception(f"模块 {new_mod.name} on_show 异常")
        self._active_index = index

        # Update sidebar button styles
        for i, btn in enumerate(self._nav_buttons):
            if i == index:
                btn.setStyleSheet(BTN_NAV_ACTIVE)
            elif not btn._module.disabled:
                btn.setStyleSheet(BTN_NAV_INACTIVE)

    # ═══════════════ after() compatibility (thread-safe) ═══════════════

    def after(self, ms, callback, *args):
        """Schedule callback on the main thread after ms milliseconds.

        Thread-safe: stores the callback and triggers drain via invokeMethod
        so QTimer is always created on the main thread.
        """
        self._pending_callbacks.append((ms, callback, args))
        QMetaObject.invokeMethod(
            self, "_drain_callbacks",
            Qt.ConnectionType.QueuedConnection,
        )

    @Slot()
    def _drain_callbacks(self):
        """Called on main thread. Process accumulated callbacks."""
        while self._pending_callbacks:
            ms, cb, cb_args = self._pending_callbacks.pop(0)
            if cb_args:
                QTimer.singleShot(ms, lambda a=cb_args: cb(*a))
            else:
                QTimer.singleShot(ms, cb)

    # ═══════════════ Log Viewer ═══════════════

    def _open_log_viewer(self):
        if hasattr(self, "_log_window") and self._log_window.isVisible():
            self._log_window.raise_()
            self._log_window.activateWindow()
            self._refresh_log_viewer()
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("运行日志")
        dlg.resize(700, 450)
        dlg.setMinimumSize(500, 300)
        dlg.setStyleSheet("QDialog { background: #f9f9f9; }")
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(8)

        # Header
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        title = QLabel("运行日志")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1f1f1f; background: transparent;")
        hl.addWidget(title)
        hl.addStretch(1)

        clear_btn = QPushButton("清空")
        clear_btn.setStyleSheet(BTN_SECONDARY)
        refresh_btn = QPushButton("刷新")
        refresh_btn.setStyleSheet(BTN_PRIMARY)
        clear_btn.setMinimumWidth(50)
        refresh_btn.setMinimumWidth(50)
        refresh_btn.clicked.connect(self._refresh_log_viewer)
        clear_btn.clicked.connect(self._clear_log_viewer)
        hl.addWidget(refresh_btn)
        hl.addWidget(clear_btn)
        layout.addWidget(header)

        # Path hint
        path_hint = QLabel(f"日志文件: {logger.log_path}")
        path_hint.setStyleSheet("font-size: 10px; color: #999999; background: transparent;")
        layout.addWidget(path_hint)

        # Text area
        self._log_text = QPlainTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setObjectName("logText")
        self._log_text.setStyleSheet("""
            QPlainTextEdit {
                border: 1px solid #e5e5e5; border-radius: 8px;
                background: #1e1e1e; color: #d4d4d4;
                font-family: "Cascadia Code", "Consolas", "SF Mono", "Menlo", "Microsoft YaHei", "Courier New", monospace; font-size: 11px;
                padding: 8px;
            }
            QPlainTextEdit QScrollBar:vertical {
                background: #2a2a2a; border: none; border-radius: 4px; width: 8px; margin: 2px;
            }
            QPlainTextEdit QScrollBar::handle:vertical {
                background: #555555; border-radius: 4px; min-height: 30px;
            }
            QPlainTextEdit QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        layout.addWidget(self._log_text)

        self._log_window = dlg
        self._refresh_log_viewer()
        dlg.show()

    def _refresh_log_viewer(self):
        if not hasattr(self, "_log_text"):
            return
        lines = logger.get_recent_lines(n=300)
        self._log_text.setPlainText("\n".join(lines))
        sb = self._log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear_log_viewer(self):
        if not hasattr(self, "_log_text"):
            return
        logger.clear_memory()
        self._log_text.clear()
