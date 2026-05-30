"""
NetTool - Network Toolbox
Version: V100R008C00SPC600
Author: Tang Wenbo (HCIE-Datacom)
Copyright (C) 2026 Tang Wenbo
License: GNU General Public License v3.0 or later

Main window, shared styles, sidebar navigation, and module container.
"""

import os
import sys
import threading

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QPlainTextEdit, QDialog, QApplication,
    QMenu, QLineEdit,
)
from PySide6.QtCore import Qt, QTimer, QSize, QMetaObject, Slot
from PySide6.QtGui import QFont, QColor, QIcon, QPalette, QKeySequence
from core.logger import logger
from core.icons import icon as drawn_icon


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
    frame.setObjectName("cardSurface")
    frame.setStyleSheet(
        "QFrame#cardSurface {"
        " background-color: #ffffff;"
        " border: 1px solid #e6e8eb;"
        " border-radius: 10px;"
        "}"
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
        background: #11a37f; color: #ffffff; border: none;
        border-radius: 8px; padding: 7px 18px; font-size: 13px; font-weight: 700;
    }
    QPushButton:hover { background: #0f9273; }
    QPushButton:pressed { background: #0b745c; }
    QPushButton:disabled { background: #b9dfd5; color: rgba(255,255,255,0.82); }
"""

BTN_DANGER = """
    QPushButton {
        background: #dc2626; color: #ffffff; border: none;
        border-radius: 8px; padding: 7px 18px; font-size: 13px; font-weight: 700;
    }
    QPushButton:hover { background: #b91c1c; }
    QPushButton:disabled { background: #f0a0a0; }
"""

BTN_SECONDARY = """
    QPushButton {
        background: #ffffff; color: #22252a;
        border: 1px solid #dfe3e8; border-radius: 8px;
        padding: 7px 18px; font-size: 13px; font-weight: 700;
    }
    QPushButton:hover { background: #f6f7f8; border-color: #cfd5dc; }
"""

BTN_MODE_ACTIVE = """
    QPushButton {
        background: #11a37f; color: #ffffff; border: none;
        border-radius: 7px; padding: 5px 16px; font-size: 12px; font-weight: 700;
    }
    QPushButton:hover { background: #0f9273; }
"""

BTN_MODE_INACTIVE = """
    QPushButton {
        background: transparent; color: #4b5563; border: none;
        border-radius: 7px; padding: 5px 16px; font-size: 12px; font-weight: 700;
    }
    QPushButton:hover { background: #ffffff; color: #22252a; }
"""

BTN_NAV_ACTIVE = """
    QPushButton {
        background: #ffffff; color: #111827; border: 1px solid #e4e8ec;
        border-radius: 10px; padding: 9px 12px; font-size: 14px; font-weight: 700; text-align: left;
    }
    QPushButton:hover { background: #ffffff; }
"""

BTN_NAV_INACTIVE = """
    QPushButton {
        background: transparent; color: #4f5966; border: 1px solid transparent;
        border-radius: 10px; padding: 9px 12px; font-size: 14px; font-weight: 700; text-align: left;
    }
    QPushButton:hover { background: #ffffff; color: #111827; }
"""


# ═══════════════ Shared Font Style Constants ═══════════════
# Usage: label.setStyleSheet(H2_STYLE) etc.
# H1: module title, H2: card/section heading, H3: sub-label
# Body: form labels, Hint: status/secondary, Mono: code output

H1_STYLE = "font-size: 32px; font-weight: 700; color: #20242a; background: transparent;"
H2_STYLE = "font-size: 15px; font-weight: 700; color: #22252a; background: transparent; border: none;"
H3_STYLE = "font-size: 12px; font-weight: 700; color: #394150; background: transparent;"
BODY_STYLE = "font-size: 13px; color: #394150; background: transparent;"
HINT_STYLE = "font-size: 11px; color: #8a929d; background: transparent;"
DESC_STYLE = "font-size: 15px; color: #687385; background: transparent;"

# Shared dark output area style (used by all modules for code/log output)
DARK_OUTPUT = """
    QPlainTextEdit {
        border: 1px solid #e1e5e9; border-radius: 8px;
        background: #202020; color: #e8e8e8;
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
    background: #f3f4f4;
    border: none;
    border-radius: 0px;
}

/* ---- Line Edit ---- */
QLineEdit {
    border: 1px solid #dfe3e8;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 13px;
    background: #ffffff;
    color: #20242a;
    selection-background-color: #11a37f;
    selection-color: #ffffff;
}
QLineEdit:focus {
    border-color: #11a37f;
}

/* ---- Combo Box ---- */
QComboBox {
    border: 1px solid #dfe3e8;
    border-radius: 8px;
    padding: 4px 10px;
    font-size: 12px;
    background: #ffffff;
    color: #20242a;
}
QComboBox:hover {
    border-color: #11a37f;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background: #ffffff;
    border: 1px solid #dfe3e8;
    border-radius: 6px;
    selection-background-color: #e7f5f1;
    selection-color: #0b745c;
    color: #20242a;
    outline: 0;
}
QAbstractItemView {
    background: #ffffff;
    color: #20242a;
    selection-background-color: #e7f5f1;
    selection-color: #0b745c;
    outline: 0;
}

/* ---- Checkbox ---- */
QCheckBox {
    spacing: 6px;
    font-size: 12px;
    color: #394150;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #cfd5dc;
    border-radius: 3px;
    background: #ffffff;
}
QCheckBox::indicator:checked {
    background: #11a37f;
    border-color: #11a37f;
}

/* ---- Progress Bar ---- */
QProgressBar {
    border: none;
    border-radius: 4px;
    background: #e8ecef;
    height: 8px;
    text-align: center;
    font-size: 10px;
}
QProgressBar::chunk {
    background: #11a37f;
    border-radius: 4px;
}

/* ---- Dialog / Message Box ---- */
QMessageBox {
    background: #ffffff;
}
QMessageBox QLabel {
    color: #334155; font-size: 13px;
}
QMessageBox QPushButton {
    background: #11a37f; color: #ffffff; border: none;
    border-radius: 6px; padding: 6px 24px; font-size: 13px; font-weight: bold;
    min-height: 32px;
}
QMessageBox QPushButton:hover {
    background: #0f9273;
}
QMessageBox QPushButton:pressed {
    background: #0b745c;
}
QDialogButtonBox QPushButton {
    background: #11a37f; color: #ffffff; border: none;
    border-radius: 6px; padding: 6px 24px; font-size: 13px; font-weight: bold;
    min-height: 32px;
}
QDialogButtonBox QPushButton:hover {
    background: #0f9273;
}

/* ---- Context Menu ---- */
QMenu {
    background: #ffffff;
    border: 1px solid #d7e7e1;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 32px 6px 16px;
    font-size: 13px;
    color: #334155;
    border-radius: 4px;
}
QMenu::item:selected {
    background: #e7f5f1;
    color: #0b745c;
}
QMenu::separator {
    height: 1px;
    background: #d9e2ec;
    margin: 4px 8px;
}

/* ---- Table / Tree ---- */
QTreeWidget {
    border: 1px solid #dfe3e8;
    border-radius: 8px;
    background: #ffffff;
    alternate-background-color: #f8fafb;
    font-size: 12px;
    color: #20242a;
}
QTreeWidget::item {
    padding: 4px 6px;
}
QTreeWidget::item:selected {
    background: #e7f5f1;
    color: #0b745c;
}
QTreeWidget::item:hover {
    background: #f4f6f7;
}
QHeaderView::section {
    background: #f7f8f9;
    border: none;
    border-bottom: 1px solid #e1e5e9;
    padding: 6px 8px;
    font-size: 12px;
    font-weight: bold;
    color: #697281;
}
"""


class NetworkToolboxApp(QMainWindow):
    """Plugin-style main window. Reads MODULE_REGISTRY and auto-generates UI."""

    VERSION = "V100R008C00SPC600"

    def __init__(self, module_registry):
        super().__init__()

        # Set app icon FIRST, before window title/style
        self._set_app_icon()

        self.setWindowTitle("NetTool")
        self.resize(1040, 820)
        self.setMinimumSize(900, 640)
        self.setStyleSheet(GLOBAL_QSS)

        # Replace native QLineEdit context menu with styled Qt menu
        self._install_context_menu_filter()

        # Thread-safe callback queue for after()
        self._pending_callbacks = []
        self._pending_callbacks_lock = threading.Lock()

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
            if not (sys.platform == "darwin" and getattr(sys, "frozen", False)):
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
        sidebar_wrapper.setFixedWidth(260)
        wrapper_layout = QHBoxLayout(sidebar_wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)

        # White card
        sidebar_card = QFrame()
        sidebar_card.setFrameShape(QFrame.Shape.NoFrame)
        sidebar_card.setLineWidth(0)
        sidebar_card.setMidLineWidth(0)
        sidebar_card.setObjectName("sidebarCard")
        card_layout = QVBoxLayout(sidebar_card)
        card_layout.setContentsMargins(26, 30, 22, 24)
        card_layout.setSpacing(0)

        # Logo + Title row
        header_row = QWidget()
        header_row.setStyleSheet("background: transparent;")
        hr_layout = QHBoxLayout(header_row)
        hr_layout.setContentsMargins(0, 0, 0, 0)
        hr_layout.setSpacing(10)

        logo_lbl = QLabel()
        logo_icon = self._find_icon_file()
        logo_lbl.setPixmap(QIcon(logo_icon).pixmap(40, 40) if logo_icon else drawn_icon("app", 40).pixmap(40, 40))
        logo_lbl.setFixedSize(42, 42)
        logo_lbl.setStyleSheet("background: transparent;")
        hr_layout.addWidget(logo_lbl)

        title = QLabel("NetTool")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #20242a; background: transparent;")
        hr_layout.addWidget(title)
        hr_layout.addStretch(1)

        card_layout.addWidget(header_row)
        subtitle = QLabel("Network Toolbox")
        subtitle.setStyleSheet("font-size: 11px; color: #8a929d; background: transparent; padding-left: 52px;")
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(20)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.NoFrame)
        sep1.setFixedHeight(1)
        sep1.setStyleSheet("background: #e0e3e7; border: none;")
        card_layout.addWidget(sep1)
        card_layout.addSpacing(18)

        # Feature list label
        fl = QLabel("功能列表")
        fl.setStyleSheet("font-size: 11px; color: #a0a7b1; background: transparent; letter-spacing: 0px;")
        card_layout.addWidget(fl)
        card_layout.addSpacing(10)

        # Nav button area (scrollable if needed)
        self._nav_frame = QWidget()
        nav_layout = QVBoxLayout(self._nav_frame)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(6)
        card_layout.addWidget(self._nav_frame)

        self._nav_buttons = []
        for idx, mod_cls in enumerate(module_registry):
            mod = mod_cls(self)
            btn = self._make_nav_btn(mod.icon, mod.name, idx, mod.disabled, mod.disabled_text)
            nav_layout.addWidget(btn)
            self._nav_buttons.append(btn)
            btn._module = mod

        # Log button
        log_btn = QPushButton("  运行日志")
        log_btn.setIcon(drawn_icon("log", 22, fg="#8d96a1", accent="#8d96a1", bg="transparent"))
        log_btn.setIconSize(QSize(22, 22))
        log_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #4f5966; border: 1px solid transparent;
                border-radius: 10px; padding: 9px 12px; font-size: 13px; font-weight: 700; text-align: left;
            }
            QPushButton:hover { background: #ffffff; color: #111827; }
        """)
        log_btn.clicked.connect(self._open_log_viewer)
        nav_layout.addWidget(log_btn)

        # Spacer pushes version to bottom
        card_layout.addStretch(1)

        # Bottom separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.NoFrame)
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background: #e0e3e7; border: none;")
        card_layout.addWidget(sep2)
        card_layout.addSpacing(10)

        # Version
        ver = QLabel(f"NetTool {self.VERSION}")
        ver.setStyleSheet("font-size: 11px; color: #7d8793; background: transparent;")
        card_layout.addWidget(ver)
        card_layout.addSpacing(2)

        # Copyright
        cr = QLabel("\u00a9 2026 Tang Wenbo. All rights reserved.")
        cr.setStyleSheet("font-size: 9px; color: #a0a7b1; background: transparent;")
        card_layout.addWidget(cr)

        wrapper_layout.addWidget(sidebar_card)
        root_layout.addWidget(sidebar_wrapper)

    def _make_nav_btn(self, icon, label, idx, disabled=False, disabled_text=""):
        label_text = label if not disabled_text else f"{label} ({disabled_text})"
        btn = QPushButton(f"  {label_text}")
        if icon:
            icon_path = self._resolve_icon(icon)
            if os.path.isfile(icon_path):
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(QSize(20, 20))
            else:
                btn.setIcon(drawn_icon(icon, 24, fg="#8d96a1", accent="#8d96a1", bg="transparent"))
                btn.setIconSize(QSize(24, 24))
                btn._icon_key = icon
        btn.setStyleSheet(BTN_NAV_INACTIVE)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(48)
        if disabled:
            btn.setEnabled(False)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent; color: #a0a7b1; border: none;
                    border-radius: 10px; padding: 9px 12px; font-size: 14px; text-align: left;
                }
            """)
        else:
            btn.clicked.connect(lambda checked=False, i=idx: self._switch_to(i))
        return btn

    # ═══════════════ Content Area ═══════════════

    def _build_content_area(self, root_layout, module_registry):
        content_wrapper = QWidget()
        wrapper_layout = QVBoxLayout(content_wrapper)
        wrapper_layout.setContentsMargins(34, 40, 36, 30)
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
                err_layout = QVBoxLayout(page)
                err_layout.addWidget(err)
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
        old_name = getattr(self._modules[getattr(self, "_active_index", index)], "name", "无")
        if not hasattr(self, "_active_index") or old_name != new_mod.name:
            logger.info(f"[应用] 切换模块: {old_name} -> {new_mod.name}")
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
                if hasattr(btn, "_icon_key"):
                    btn.setIcon(drawn_icon(btn._icon_key, 24, fg="#11a37f", accent="#11a37f", bg="transparent"))
            elif not btn._module.disabled:
                btn.setStyleSheet(BTN_NAV_INACTIVE)
                if hasattr(btn, "_icon_key"):
                    btn.setIcon(drawn_icon(btn._icon_key, 24, fg="#8d96a1", accent="#8d96a1", bg="transparent"))

    # ═══════════════ after() compatibility (thread-safe) ═══════════════

    def after(self, ms, callback, *args):
        """Schedule callback on the main thread after ms milliseconds.

        Thread-safe: stores the callback and triggers drain via invokeMethod
        so QTimer is always created on the main thread.
        """
        with self._pending_callbacks_lock:
            self._pending_callbacks.append((ms, callback, args))
        QMetaObject.invokeMethod(
            self, "_drain_callbacks",
            Qt.ConnectionType.QueuedConnection,
        )

    @Slot()
    def _drain_callbacks(self):
        """Called on main thread. Process accumulated callbacks."""
        with self._pending_callbacks_lock:
            callbacks = self._pending_callbacks
            self._pending_callbacks = []
        for ms, cb, cb_args in callbacks:
            if cb_args:
                QTimer.singleShot(ms, lambda c=cb, a=cb_args: c(*a))
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
        dlg.setStyleSheet("QDialog { background: #ffffff; }")
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(8)

        # Header
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        title = QLabel("运行日志")
        title.setStyleSheet(H2_STYLE)
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
        path_hint.setStyleSheet("font-size: 10px; color: #8a929d; background: transparent;")
        layout.addWidget(path_hint)

        # Text area
        self._log_text = QPlainTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setObjectName("logText")
        self._log_text.setStyleSheet("""
            QPlainTextEdit {
                border: 1px solid #e1e5e9; border-radius: 8px;
                background: #202020; color: #d4d4d4;
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
