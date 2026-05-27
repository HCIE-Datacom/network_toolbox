"""
NetTool - Network Toolbox
Copyright (C) 2026 Tang Wenbo (HCIE-Datacom)

FTP Tool module - combined FTP/SFTP client and FTP server (PySide6 edition).
"""

import os
import time
import threading
import stat
import ftplib

from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QPlainTextEdit,
    QTreeWidget, QTreeWidgetItem, QHeaderView,
    QDialog, QProgressBar, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon

import queue

try:
    import paramiko
except ImportError:
    paramiko = None

from core.base_module import ToolModule
from core.app import BTN_PRIMARY, BTN_DANGER, BTN_SECONDARY, BTN_MODE_ACTIVE, BTN_MODE_INACTIVE, set_card_style, set_transparent_bg, set_dark_output
from core.app import H1_STYLE, H2_STYLE, H3_STYLE, BODY_STYLE, HINT_STYLE, DESC_STYLE
from core.logger import logger

class FTPToolModule(ToolModule):
    name = "FTP \u5de5\u5177"
    icon = "\U0001f4c1"
    description = "FTP/SFTP \u5ba2\u6237\u7aef\u8fde\u63a5\u8fdc\u7a0b\u670d\u52a1\u5668\uff0c\u6216\u5728\u672c\u5730\u542f\u52a8 FTP \u670d\u52a1\u4f9b\u5c40\u57df\u7f51\u6587\u4ef6\u5171\u4eab\u3002"

    @staticmethod
    def _ico(name):
        import os
        p = os.path.dirname(os.path.abspath(__file__))
        for _ in range(10):
            full = os.path.join(p, 'icon', name)
            if os.path.isfile(full):
                return QIcon(full)
            parent = os.path.dirname(p)
            if parent == p: break
            p = parent
        return QIcon()

    def build(self, parent: QWidget):
        if parent.layout() is None:
            parent.setLayout(QVBoxLayout(parent))
        layout = parent.layout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title
        title = QLabel(self.name)
        title.setStyleSheet(H1_STYLE)
        layout.addWidget(title)
        layout.addSpacing(5)

        desc = QLabel(self.description)
        desc.setStyleSheet(DESC_STYLE)
        desc.setWordWrap(True)
        layout.addWidget(desc)
        layout.addSpacing(10)

        # Mode card
        mode_card = QFrame()
        set_card_style(mode_card)
        mc_layout = QVBoxLayout(mode_card)
        mc_layout.setContentsMargins(15, 12, 15, 12)

        ml = QLabel("功能模式")
        ml.setStyleSheet(H2_STYLE)
        mc_layout.addWidget(ml)

        self._mode_btns = {}
        mb_wrapper = QWidget()
        mb_wrapper.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        mb_wrapper.setStyleSheet("background: #f0f0f0; border-radius: 8px;")
        mbl = QHBoxLayout(mb_wrapper)
        mbl.setContentsMargins(4, 4, 4, 4)
        mbl.setSpacing(4)
        for val, text in [("client", "客户端"), ("server", "服务器")]:
            btn = QPushButton(text)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, v=val: self._set_mode(v))
            mbl.addWidget(btn, stretch=1)
            self._mode_btns[val] = btn
        self._update_mode_buttons("client")
        mc_layout.addWidget(mb_wrapper)

        layout.addWidget(mode_card)
        layout.addSpacing(10)

        # Content card
        content_card = QFrame()
        set_card_style(content_card)
        cc_layout = QVBoxLayout(content_card)
        cc_layout.setContentsMargins(15, 12, 15, 12)

        self._client_frame = QWidget()
        set_transparent_bg(self._client_frame)
        self._build_client_ui(self._client_frame)
        cc_layout.addWidget(self._client_frame)

        self._server_frame = QWidget()
        set_transparent_bg(self._server_frame)
        self._build_server_ui(self._server_frame)
        cc_layout.addWidget(self._server_frame)
        self._server_frame.hide()

        layout.addWidget(content_card, stretch=1)

        self._client = None
        self._sftp = None
        self._current_remote_dir = "/"
        self._server_thread = None
        self._xfer_cancel = False

    # ── Client UI ──

    def _build_client_ui(self, parent):
        fl = QVBoxLayout(parent)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(4)

        # Protocol selector
        pl = QLabel("协议")
        pl.setStyleSheet(H3_STYLE)
        fl.addWidget(pl)

        self._proto_btns = {}
        pw = QWidget()
        pw.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        pw.setStyleSheet("background: #f0f0f0; border-radius: 6px;")
        pwl = QHBoxLayout(pw)
        pwl.setContentsMargins(4, 4, 4, 4)
        pwl.setSpacing(2)
        for val, txt in [("ftp", "FTP"), ("sftp", "SFTP")]:
            btn = QPushButton(txt)
            btn.setFixedHeight(24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, v=val: self._set_proto(v))
            pwl.addWidget(btn, stretch=1)
            self._proto_btns[val] = btn
        self._update_proto_buttons("ftp")
        fl.addWidget(pw)
        fl.addSpacing(4)

        # Connection form
        conn = QGridLayout()
        conn.setSpacing(4)
        conn.setContentsMargins(0, 0, 0, 0)
        fl.addLayout(conn)

        # Row 1: Host + Port
        conn.addWidget(self._lbl("服务器", 45), 0, 0)
        self._host_entry = QLineEdit()
        self._host_entry.setPlaceholderText("IP 或域名")
        self._host_entry.setMinimumHeight(28)
        conn.addWidget(self._host_entry, 0, 1)

        conn.addWidget(self._lbl("端口", 30), 0, 2)
        self._port_entry = QLineEdit("21")
        self._port_entry.setFixedWidth(55)
        self._port_entry.setMinimumHeight(28)
        conn.addWidget(self._port_entry, 0, 3)

        # Row 2: User + Pass + Connect
        conn.addWidget(self._lbl("账号", 45), 1, 0)
        self._user_entry = QLineEdit()
        self._user_entry.setPlaceholderText("用户名")
        self._user_entry.setMinimumHeight(28)
        conn.addWidget(self._user_entry, 1, 1)

        conn.addWidget(self._lbl("密码", 30), 1, 2)
        self._pass_entry = QLineEdit()
        self._pass_entry.setPlaceholderText("密码")
        self._pass_entry.setMinimumHeight(28)
        conn.addWidget(self._pass_entry, 1, 3)

        self._connect_btn = QPushButton("连接")
        self._connect_btn.setStyleSheet(BTN_PRIMARY)
        self._connect_btn.setFixedSize(65, 28)
        self._connect_btn.clicked.connect(self._toggle_connect)
        conn.addWidget(self._connect_btn, 1, 4)

        self._conn_status = QLabel("状态: 未连接")
        self._conn_status.setStyleSheet(HINT_STYLE + " color: #999;")
        fl.addWidget(self._conn_status)

        # Remote browser header
        fl.addSpacing(4)
        rh = QLabel("远程文件")
        rh.setStyleSheet(H3_STYLE + " color: #666;")
        fl.addWidget(rh)

        nav = QWidget()
        set_transparent_bg(nav)
        nl = QHBoxLayout(nav)
        nl.setContentsMargins(0, 0, 0, 0)
        nl.setSpacing(2)
        self._path_label = QLabel("/")
        self._path_label.setStyleSheet("font-family: 'Cascadia Code', 'Consolas', 'SF Mono', 'Menlo', 'Microsoft YaHei', 'Courier New', monospace; font-size: 11px; color: #333; background: transparent;")
        nl.addWidget(self._path_label, stretch=1)

        for txt, cmd in [("\U0001f504", self._refresh_dir), ("\u2b06", self._go_up)]:
            b = QPushButton(txt)
            b.setFixedSize(28, 20)
            b.setStyleSheet("background: #e5e5e5; border: none; border-radius: 4px; font-size: 12px;")
            b.clicked.connect(cmd)
            nl.addWidget(b)
        fl.addWidget(nav)

        # Remote tree
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["名称", "大小", "修改时间"])
        self._tree.setColumnWidth(0, 240)
        self._tree.setColumnWidth(1, 70)
        self._tree.setColumnWidth(2, 130)
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(False)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self._tree.itemDoubleClicked.connect(self._on_tree_double_click)
        self._tree.setStyleSheet("""
            QTreeWidget { border: 1px solid #e5e5e5; border-radius: 6px; font-size: 11px; }
            QTreeWidget::item { padding: 2px 4px; }
            QTreeWidget::item:selected { background: #e8f5ee; color: #333; }
            QTreeWidget QScrollBar:vertical { background: #f0f0f0; border: none; border-radius: 4px; width: 8px; margin: 2px; }
            QTreeWidget QScrollBar::handle:vertical { background: #c0c0c0; border-radius: 4px; min-height: 30px; }
            QTreeWidget QScrollBar::handle:vertical:hover { background: #a0a0a0; }
            QTreeWidget QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        fl.addWidget(self._tree, stretch=1)

        # Action buttons
        fl.addSpacing(4)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.NoFrame)
        sep.setLineWidth(0)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #e5e5e5; border: none;")
        fl.addWidget(sep)

        btn_row = QWidget()
        set_transparent_bg(btn_row)
        brl = QHBoxLayout(btn_row)
        brl.setContentsMargins(0, 4, 0, 0)
        brl.setSpacing(8)

        self._upload_btn = QPushButton("\u2b06 上传到远程")
        self._upload_btn.setStyleSheet(BTN_PRIMARY)
        self._upload_btn.setFixedHeight(28)
        self._upload_btn.clicked.connect(self._upload_file)
        brl.addWidget(self._upload_btn)

        self._download_btn = QPushButton("\u2b07 下载到本地")
        self._download_btn.setStyleSheet("""
            QPushButton { background: #3b82f6; color: white; border: none;
            border-radius: 8px; padding: 6px 18px; font-size: 13px; font-weight: bold; }
            QPushButton:hover { background: #2563eb; }
        """)
        self._download_btn.setFixedHeight(28)
        self._download_btn.clicked.connect(self._download_file)
        brl.addWidget(self._download_btn)

        self._delete_btn = QPushButton("\U0001f5d1 删除远程")
        self._delete_btn.setStyleSheet(BTN_DANGER)
        self._delete_btn.setFixedHeight(28)
        self._delete_btn.clicked.connect(self._delete_file)
        brl.addWidget(self._delete_btn)
        brl.addStretch(1)
        fl.addWidget(btn_row)

        # Local browser
        fl.addSpacing(4)
        ll = QLabel("本地文件")
        ll.setStyleSheet(H3_STYLE + " color: #666;")
        fl.addWidget(ll)

        local_nav = QWidget()
        set_transparent_bg(local_nav)
        lnl = QHBoxLayout(local_nav)
        lnl.setContentsMargins(0, 0, 0, 0)
        lnl.setSpacing(2)
        self._local_dir = os.path.expanduser("~/Desktop")
        self._local_path_label = QLabel(self._local_dir)
        self._local_path_label.setStyleSheet("font-family: 'Cascadia Code', 'Consolas', 'SF Mono', 'Menlo', 'Microsoft YaHei', 'Courier New', monospace; font-size: 11px; color: #333; background: transparent;")
        lnl.addWidget(self._local_path_label, stretch=1)

        for txt, cmd in [("...", self._browse_local), ("\U0001f504", self._refresh_local), ("\u2b06", self._go_up_local)]:
            b = QPushButton(txt)
            b.setFixedSize(28, 20)
            b.setStyleSheet("background: #e5e5e5; border: none; border-radius: 4px; font-size: 12px;")
            b.clicked.connect(cmd)
            lnl.addWidget(b)
        fl.addWidget(local_nav)

        # Local tree
        self._local_tree = QTreeWidget()
        self._local_tree.setHeaderLabels(["名称", "大小", "修改时间"])
        self._local_tree.setColumnWidth(0, 240)
        self._local_tree.setColumnWidth(1, 70)
        self._local_tree.setColumnWidth(2, 130)
        self._local_tree.setAlternatingRowColors(True)
        self._local_tree.setRootIsDecorated(False)
        self._local_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self._local_tree.itemDoubleClicked.connect(self._on_local_double_click)
        self._local_tree.setStyleSheet("""
            QTreeWidget { border: 1px solid #e5e5e5; border-radius: 6px; font-size: 11px; }
            QTreeWidget::item { padding: 2px 4px; }
            QTreeWidget::item:selected { background: #e8f5ee; color: #333; }
            QTreeWidget QScrollBar:vertical { background: #f0f0f0; border: none; border-radius: 4px; width: 8px; margin: 2px; }
            QTreeWidget QScrollBar::handle:vertical { background: #c0c0c0; border-radius: 4px; min-height: 30px; }
            QTreeWidget QScrollBar::handle:vertical:hover { background: #a0a0a0; }
            QTreeWidget QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        fl.addWidget(self._local_tree, stretch=1)

        # Client log
        fl.addSpacing(4)
        self._clog = QPlainTextEdit()
        self._clog.setReadOnly(True)
        self._clog.setFixedHeight(50)
        set_dark_output(self._clog)
        fl.addWidget(self._clog)

        self._refresh_local()

    # ── Server UI ──

    def _build_server_ui(self, parent):
        fl = QVBoxLayout(parent)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(8)

        sl = QLabel("服务配置")
        sl.setStyleSheet(H3_STYLE)
        fl.addWidget(sl)

        # Port
        pr = QWidget()
        set_transparent_bg(pr)
        prl = QHBoxLayout(pr)
        prl.setContentsMargins(0, 0, 0, 0)
        prl.setSpacing(10)
        prl.addWidget(self._lbl("监听端口:", 60))
        self._srv_port_entry = QLineEdit("21")
        self._srv_port_entry.setFixedWidth(80)
        self._srv_port_entry.setMinimumHeight(32)
        prl.addWidget(self._srv_port_entry)
        prl.addWidget(QLabel("(FTP 默认端口)"))
        prl.itemAt(2).widget().setStyleSheet(HINT_STYLE)
        prl.addStretch(1)
        fl.addWidget(pr)

        # Directory
        dr = QWidget()
        set_transparent_bg(dr)
        drl = QHBoxLayout(dr)
        drl.setContentsMargins(0, 0, 0, 0)
        drl.setSpacing(8)
        drl.addWidget(self._lbl("根目录:", 60))
        self._srv_dir_entry = QLineEdit(os.path.expanduser("~/Desktop"))
        self._srv_dir_entry.setMinimumHeight(32)
        drl.addWidget(self._srv_dir_entry, stretch=1)
        browse_btn = QPushButton("浏览")
        browse_btn.setStyleSheet("background: #e5e5e5; border: none; border-radius: 6px; padding: 4px 12px; font-size: 12px;")
        browse_btn.clicked.connect(self._browse_srv_dir)
        drl.addWidget(browse_btn)
        fl.addWidget(dr)

        # Auth
        ap = QWidget()
        set_transparent_bg(ap)
        apl = QHBoxLayout(ap)
        apl.setContentsMargins(0, 0, 0, 0)
        apl.setSpacing(10)
        apl.addWidget(self._lbl("用户名:", 60))
        self._srv_user_entry = QLineEdit("admin")
        self._srv_user_entry.setFixedWidth(120)
        self._srv_user_entry.setMinimumHeight(32)
        apl.addWidget(self._srv_user_entry)
        apl.addWidget(self._lbl("密码:", 35))
        self._srv_pass_entry = QLineEdit("123456")
        self._srv_pass_entry.setFixedWidth(120)
        self._srv_pass_entry.setMinimumHeight(32)
        apl.addWidget(self._srv_pass_entry)
        apl.addStretch(1)
        fl.addWidget(ap)

        # Toggle
        tr = QWidget()
        set_transparent_bg(tr)
        trl = QHBoxLayout(tr)
        trl.setContentsMargins(0, 0, 0, 0)
        trl.setSpacing(15)
        self._srv_toggle_btn = QPushButton("启动服务")
        self._srv_toggle_btn.setStyleSheet(BTN_PRIMARY)
        self._srv_toggle_btn.setFixedSize(120, 36)
        self._srv_toggle_btn.clicked.connect(self._toggle_server)
        trl.addWidget(self._srv_toggle_btn)
        self._srv_status_label = QLabel("状态: 已停止")
        self._srv_status_label.setStyleSheet(BODY_STYLE + " color: #666;")
        trl.addWidget(self._srv_status_label)
        trl.addStretch(1)
        fl.addWidget(tr)

        # Server log
        fl.addSpacing(8)
        sll = QLabel("运行日志")
        sll.setStyleSheet(H3_STYLE)
        fl.addWidget(sll)

        self._srv_log = QPlainTextEdit()
        self._srv_log.setReadOnly(True)
        set_dark_output(self._srv_log)
        fl.addWidget(self._srv_log, stretch=1)

    # ── Helpers ──

    @staticmethod
    def _lbl(text, w=None):
        l = QLabel(text)
        if w:
            l.setFixedWidth(w)
        l.setStyleSheet(BODY_STYLE)
        return l

    @staticmethod
    def _ts():
        return time.strftime("%H:%M:%S")

    @staticmethod
    def _fmt_size(size):
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f} GB"

    # ── Mode / Protocol switching ──

    def _set_mode(self, mode):
        self._update_mode_buttons(mode)
        if mode == "client":
            self._client_frame.show()
            self._server_frame.hide()
        else:
            self._client_frame.hide()
            self._server_frame.show()

    def _update_mode_buttons(self, val):
        for v, btn in self._mode_btns.items():
            if v == val:
                btn.setStyleSheet(BTN_MODE_ACTIVE)
            else:
                btn.setStyleSheet(BTN_MODE_INACTIVE)

    def _set_proto(self, proto):
        self._update_proto_buttons(proto)
        p = self._port_entry.text()
        if proto == "ftp" and p in ("", "22"):
            self._port_entry.setText("21")
        elif proto == "sftp" and p in ("", "21"):
            self._port_entry.setText("22")

    def _update_proto_buttons(self, val):
        for v, btn in self._proto_btns.items():
            if v == val:
                btn.setStyleSheet(BTN_MODE_ACTIVE)
            else:
                btn.setStyleSheet(BTN_MODE_INACTIVE)

    # ── Log ──

    def _log(self, msg):
        self.app.after(0, lambda: self._clog.appendPlainText(msg))

    # ── Connect / Disconnect ──

    def _toggle_connect(self):
        if self._client is not None:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        host = self._host_entry.text().strip()
        port_str = self._port_entry.text().strip()
        for v, btn in self._proto_btns.items():
            btn_style = btn.styleSheet()
            if "#10a37f" in btn_style:
                proto = v
                break
        else:
            proto = "ftp"

        if not host:
            QMessageBox.warning(self.app, "提示", "请输入主机地址")
            return
        if not port_str.isdigit() or not (1 <= int(port_str) <= 65535):
            QMessageBox.warning(self.app, "提示", "请输入有效的端口号 (1-65535)")
            return
        if proto == "sftp" and paramiko is None:
            QMessageBox.critical(self.app, "错误", "SFTP 需要 paramiko 库，请执行: pip3 install paramiko")
            return
        self._connect_btn.setEnabled(False)
        self._connect_btn.setText("连接中...")
        threading.Thread(target=self._do_connect, args=(host, int(port_str), proto), daemon=True).start()

    def _do_connect(self, host, port, proto):
        user = self._user_entry.text().strip()
        pwd = self._pass_entry.text()
        ts = self._ts()
        try:
            if proto == "ftp":
                self._client = ftplib.FTP()
                self._client.connect(host, port, timeout=10)
                self.app.after(0, self._log, f"{ts}  [FTP] 已连接到 {host}:{port}")
                logger.info(f"[FTP客户端] 已连接到 {host}:{port}")
                if user:
                    self._client.login(user, pwd)
                else:
                    self._client.login()
                self.app.after(0, self._log, f"{ts}  [FTP] 登录成功 ({user or '匿名'})")
                self._sftp = None
            else:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(host, port=port, username=user, password=pwd, timeout=10)
                self._client = ssh
                self._sftp = ssh.open_sftp()
                self.app.after(0, self._log, f"{ts}  [SFTP] 已连接到 {host}:{port}")
            self._current_remote_dir = "/"
            self.app.after(0, self._on_connected)
            self.app.after(0, self._refresh_dir)
        except Exception as e:
            logger.error(f"[FTP/SFTP] 连接失败 {host}:{port}: {e}")
            self._client = None
            self._sftp = None
            self.app.after(0, self._log, f"{ts}  [错误] 连接失败: {e}")
            self.app.after(0, self._on_disconnected)

    def _disconnect(self):
        ts = self._ts()
        try:
            if self._sftp:
                self._sftp.close()
            if self._client:
                if isinstance(self._client, ftplib.FTP):
                    self._client.quit()
                else:
                    self._client.close()
        except Exception:
            pass
        self._client = None
        self._sftp = None
        self._log(f"{ts}  [断开] 已断开连接")
        logger.info("[FTP/SFTP] 已断开连接")
        self._on_disconnected()

    def _on_connected(self):
        self._connect_btn.setText("断开")
        self._connect_btn.setStyleSheet(BTN_DANGER)
        self._connect_btn.setEnabled(True)
        addr = f"{self._host_entry.text().strip()}:{self._port_entry.text().strip()}"
        self._conn_status.setText(f"状态: 已连接 -> {addr}")
        self._conn_status.setStyleSheet(HINT_STYLE + " color: #10a37f;")

    def _on_disconnected(self):
        self._connect_btn.setText("连接")
        self._connect_btn.setStyleSheet(BTN_PRIMARY)
        self._connect_btn.setEnabled(True)
        self._conn_status.setText("状态: 未连接")
        self._conn_status.setStyleSheet(HINT_STYLE + " color: #999;")
        self._tree.clear()

    # ── Remote file browser ──

    def _refresh_dir(self):
        if self._client is None:
            return
        threading.Thread(target=self._do_list_dir, daemon=True).start()

    def _do_list_dir(self):
        items = []
        error = None
        try:
            is_ftp = isinstance(self._client, ftplib.FTP)
            if is_ftp:
                lines = []
                self._client.dir(self._current_remote_dir, lines.append)
                for line in lines:
                    parts = line.split()
                    if len(parts) < 9:
                        continue
                    perms = parts[0]
                    name = " ".join(parts[8:])
                    size_str = parts[4]
                    is_dir = perms.startswith("d")
                    date_str = " ".join(parts[5:8])
                    size = int(size_str) if size_str.isdigit() else 0
                    items.append((name, is_dir, size, date_str))
            else:
                for entry in self._sftp.listdir_attr(self._current_remote_dir):
                    mt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry.st_mtime))
                    is_dir = stat.S_ISDIR(entry.st_mode)
                    items.append((entry.filename, is_dir, entry.st_size, mt))
        except Exception as e:
            error = str(e)
        self.app.after(0, self._show_dir_list, items, error)

    def _show_dir_list(self, items, error):
        self._tree.clear()
        if error:
            self._log(f"{self._ts()}  [错误] 列出目录失败: {error}")
            return

        dirs, files = [], []
        for name, is_dir, size, date_str in items:
            if name.startswith("."):
                continue
            (dirs if is_dir else files).append((name, size, date_str))
        dirs.sort(key=lambda x: x[0].lower())
        files.sort(key=lambda x: x[0].lower())

        if self._current_remote_dir != "/":
            item = QTreeWidgetItem(["..", "", ""])
            item.setData(0, Qt.ItemDataRole.UserRole, "__up__")
            item.setData(0, Qt.ItemDataRole.UserRole + 1, "dir")
            self._tree.addTopLevelItem(item)

        for name, size, date_str in dirs:
            item = QTreeWidgetItem([name, self._fmt_size(size), date_str])
            item.setIcon(0, self._ico('folder.png'))
            item.setData(0, Qt.ItemDataRole.UserRole, name)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, "dir")
            self._tree.addTopLevelItem(item)

        for name, size, date_str in files:
            item = QTreeWidgetItem([name, self._fmt_size(size), date_str])
            item.setIcon(0, self._ico('file.png'))
            item.setData(0, Qt.ItemDataRole.UserRole, name)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, "file")
            self._tree.addTopLevelItem(item)

        self._path_label.setText(self._current_remote_dir)

    def _on_tree_double_click(self, item):
        iid = item.data(0, Qt.ItemDataRole.UserRole)
        tag = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if iid == "__up__":
            self._go_up()
            return
        if tag == "dir":
            if self._current_remote_dir == "/":
                self._current_remote_dir = "/" + iid
            else:
                self._current_remote_dir = self._current_remote_dir.rstrip("/") + "/" + iid
            self._refresh_dir()

    def _go_up(self):
        if self._current_remote_dir and self._current_remote_dir != "/":
            parent_dir = os.path.dirname(self._current_remote_dir.rstrip("/"))
            self._current_remote_dir = parent_dir if parent_dir else "/"
            self._refresh_dir()

    # ── Local file browser ──

    def _browse_local(self):
        d = QFileDialog.getExistingDirectory(self.app, "选择本地目录", self._local_dir)
        if d:
            self._local_dir = d
            self._local_path_label.setText(d)
            self._refresh_local()

    def _refresh_local(self):
        self._local_tree.clear()
        try:
            entries = [e for e in os.listdir(self._local_dir) if not e.startswith(".")]
        except Exception:
            return

        entries.sort(key=lambda x: x.lower())
        for name in entries:
            full = os.path.join(self._local_dir, name)
            try:
                st = os.stat(full)
                is_dir = os.path.isdir(full)
                size = st.st_size
                mt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
                item = QTreeWidgetItem([name, self._fmt_size(size) if not is_dir else "", mt])
                item.setIcon(0, self._ico('folder.png' if is_dir else 'file.png'))
                item.setData(0, Qt.ItemDataRole.UserRole, name)
                item.setData(0, Qt.ItemDataRole.UserRole + 1, "dir" if is_dir else "file")
                self._local_tree.addTopLevelItem(item)
            except Exception:
                pass
        self._local_path_label.setText(self._local_dir)

    def _on_local_double_click(self, item):
        name = item.data(0, Qt.ItemDataRole.UserRole)
        tag = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if tag == "dir":
            self._local_dir = os.path.join(self._local_dir, name)
            self._local_path_label.setText(self._local_dir)
            self._refresh_local()

    def _go_up_local(self):
        parent_dir = os.path.dirname(self._local_dir)
        if parent_dir and parent_dir != self._local_dir:
            self._local_dir = parent_dir
            self._local_path_label.setText(self._local_dir)
            self._refresh_local()

    # ── Upload / Download / Delete ──

    def _upload_file(self):
        if self._client is None:
            QMessageBox.warning(self.app, "提示", "请先连接服务器")
            return
        item = self._local_tree.currentItem()
        if not item:
            QMessageBox.warning(self.app, "提示", "请先选择本地文件")
            return
        name = item.data(0, Qt.ItemDataRole.UserRole)
        tag = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if tag == "dir":
            QMessageBox.warning(self.app, "提示", "暂不支持上传文件夹")
            return
        local_path = os.path.join(self._local_dir, name)
        self._start_transfer("upload", local_path, name)

    def _download_file(self):
        if self._client is None:
            QMessageBox.warning(self.app, "提示", "请先连接服务器")
            return
        item = self._tree.currentItem()
        if not item:
            QMessageBox.warning(self.app, "提示", "请先选择远程文件")
            return
        name = item.data(0, Qt.ItemDataRole.UserRole)
        tag = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if tag == "dir":
            QMessageBox.warning(self.app, "提示", "暂不支持下载文件夹")
            return
        local_path = os.path.join(self._local_dir, name)
        self._start_transfer("download", local_path, name)

    def _delete_file(self):
        if self._client is None:
            QMessageBox.warning(self.app, "提示", "请先连接服务器")
            return
        item = self._tree.currentItem()
        if not item:
            return
        name = item.data(0, Qt.ItemDataRole.UserRole)
        tag = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if tag == "dir":
            reply = QMessageBox.question(self.app, "确认", f"确定要删除远程目录 '{name}' 吗?")
        else:
            reply = QMessageBox.question(self.app, "确认", f"确定要删除远程文件 '{name}' 吗?")
        if reply != QMessageBox.StandardButton.Yes:
            return
        threading.Thread(target=self._do_delete, args=(name, tag == "dir"), daemon=True).start()

    def _do_delete(self, name, is_dir):
        ts = self._ts()
        remote_path = self._current_remote_dir.rstrip("/") + "/" + name
        try:
            if isinstance(self._client, ftplib.FTP):
                if is_dir:
                    self._client.rmd(remote_path)
                else:
                    self._client.delete(remote_path)
            else:
                if is_dir:
                    self._sftp.rmdir(remote_path)
                else:
                    self._sftp.remove(remote_path)
            self.app.after(0, self._log, f"{ts}  [删除] {name} 删除成功")
            self.app.after(0, self._refresh_dir)
        except Exception as e:
            self.app.after(0, self._log, f"{ts}  [错误] 删除失败: {e}")

    # ── Transfer dialog ──

    def _start_transfer(self, direction, local_path, name):
        self._xfer_cancel = False
        dlg = QDialog(self.app)
        dlg.setWindowTitle("传输中...")
        dlg.setFixedSize(420, 200)
        dlg.setStyleSheet("QDialog { background: #f9f9f9; }")
        dl = QVBoxLayout(dlg)
        dl.setContentsMargins(20, 20, 20, 20)
        dl.setSpacing(10)

        fn_label = QLabel(name)
        fn_label.setStyleSheet(H2_STYLE)
        dl.addWidget(fn_label)

        self._xfer_info = QLabel("准备传输...")
        self._xfer_info.setStyleSheet(HINT_STYLE + " color: #666;")
        dl.addWidget(self._xfer_info)

        self._xfer_bar = QProgressBar()
        dl.addWidget(self._xfer_bar)

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(BTN_DANGER)
        cancel_btn.clicked.connect(lambda: setattr(self, '_xfer_cancel', True))
        dl.addWidget(cancel_btn, alignment=Qt.AlignmentFlag.AlignRight)

        dlg.show()

        remote_path = self._current_remote_dir.rstrip("/") + "/" + name
        if direction == "upload":
            threading.Thread(target=self._do_upload, args=(local_path, remote_path, dlg), daemon=True).start()
        else:
            threading.Thread(target=self._do_download, args=(local_path, remote_path, dlg), daemon=True).start()

    def _update_xfer(self, dlg, done, total):
        if dlg.isVisible():
            pct = min(100, int(done / max(total, 1) * 100))
            self._xfer_bar.setValue(pct)
            speed = done / max(time.time() - getattr(self, '_xfer_start', time.time()), 0.001)
            self._xfer_info.setText(f"{self._fmt_size(done)} / {self._fmt_size(total)}  ({self._fmt_size(int(speed))}/s)")

    def _do_upload(self, local_path, remote_path, dlg):
        ts = self._ts()
        self._xfer_start = time.time()
        try:
            total = os.path.getsize(local_path)
            self._xfer_bar.setMaximum(100)
            done = [0]

            if isinstance(self._client, ftplib.FTP):
                def cb(block):
                    done[0] += len(block)
                    if self._xfer_cancel:
                        raise Exception("cancelled")
                    self.app.after(0, lambda: self._update_xfer(dlg, done[0], total))

                with open(local_path, "rb") as f:
                    self._client.storbinary(f"STOR {os.path.basename(remote_path)}", f,
                                             blocksize=8192, callback=cb)
            else:
                def cb(transferred, _total):
                    done[0] = transferred
                    if self._xfer_cancel:
                        raise Exception("cancelled")
                    self.app.after(0, lambda: self._update_xfer(dlg, done[0], total))

                self._sftp.put(local_path, remote_path, callback=cb)

            self.app.after(0, self._log, f"{ts}  [上传] {os.path.basename(local_path)} 完成")
            self.app.after(0, self._refresh_dir)
        except Exception as e:
            if str(e) != "cancelled":
                self.app.after(0, self._log, f"{ts}  [错误] 上传失败: {e}")
        finally:
            self.app.after(0, dlg.close)

    def _do_download(self, local_path, remote_path, dlg):
        ts = self._ts()
        self._xfer_start = time.time()

        if isinstance(self._client, ftplib.FTP):
            total = self._client.size(os.path.basename(remote_path))
        else:
            total = self._sftp.stat(remote_path).st_size

        self._xfer_bar.setMaximum(100)
        done = [0]

        try:
            if isinstance(self._client, ftplib.FTP):
                def cb(block):
                    done[0] += len(block)
                    if self._xfer_cancel:
                        raise Exception("cancelled")
                    self.app.after(0, lambda: self._update_xfer(dlg, done[0], total))

                with open(local_path, "wb") as f:
                    self._client.retrbinary(f"RETR {os.path.basename(remote_path)}", cb, blocksize=8192)
            else:
                def cb(transferred, _total):
                    done[0] = transferred
                    if self._xfer_cancel:
                        raise Exception("cancelled")
                    self.app.after(0, lambda: self._update_xfer(dlg, done[0], total))

                self._sftp.get(remote_path, local_path, callback=cb)

            self.app.after(0, self._log, f"{ts}  [下载] {os.path.basename(remote_path)} 完成")
            self.app.after(0, self._refresh_local)
        except Exception as e:
            if str(e) != "cancelled":
                self.app.after(0, self._log, f"{ts}  [错误] 下载失败: {e}")
        finally:
            self.app.after(0, dlg.close)

    # ── Server ──

    def _toggle_server(self):
        if self._server_thread and self._server_thread.is_alive():
            self._stop_server()
        else:
            self._start_server()

    def _start_server(self):
        from pyftpdlib.authorizers import DummyAuthorizer
        from pyftpdlib.handlers import FTPHandler
        from pyftpdlib.servers import FTPServer

        port_str = self._srv_port_entry.text().strip()
        if not port_str.isdigit() or not (1 <= int(port_str) <= 65535):
            QMessageBox.warning(self.app, "提示", "请输入有效端口号")
            return
        port = int(port_str)
        root_dir = self._srv_dir_entry.text().strip() or os.path.expanduser("~/Desktop")
        user = self._srv_user_entry.text().strip() or "admin"
        pwd = self._srv_pass_entry.text() or "123456"

        authorizer = DummyAuthorizer()
        authorizer.add_user(user, pwd, root_dir, perm="elradfmw")
        handler = FTPHandler
        handler.authorizer = authorizer
        self._server_instance = FTPServer(("0.0.0.0", port), handler)

        self._srv_toggle_btn.setText("停止服务")
        self._srv_toggle_btn.setStyleSheet(BTN_DANGER)
        self._srv_status_label.setText("状态: 运行中")
        self._srv_status_label.setStyleSheet(BODY_STYLE + " color: #10a37f;")
        self._srv_port_entry.setEnabled(False)
        self._srv_dir_entry.setEnabled(False)
        self._srv_user_entry.setEnabled(False)
        self._srv_pass_entry.setEnabled(False)

        self._srv_log.setReadOnly(False)
        self._srv_log.clear()
        self._srv_log.appendPlainText(f"{self._ts_now()} [启动] 正在启动 FTP 服务器 0.0.0.0:{port} ...")
        self._srv_log.setReadOnly(True)

        self._srv_queue = queue.Queue()
        self._srv_timer = QTimer()
        self._srv_timer.timeout.connect(self._drain_srv_queue)
        self._srv_timer.start(100)

        self._server_thread = threading.Thread(target=self._serve_loop, daemon=True)
        self._server_thread.start()
        logger.info(f"[FTP服务器] 启动: {port}")

    @staticmethod
    def _ts_now():
        import datetime
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _serve_loop(self):
        try:
            self._server_instance.serve_forever()
        except PermissionError:
            self._srv_queue.put(f"{self._ts_now()} [错误] 端口需要管理员权限")
            self._srv_queue.put(f"{self._ts_now()} [提示] 右键以管理员身份运行本程序")
        except OSError as e:
            msg = str(e)
            self._srv_queue.put(f"{self._ts_now()} [错误] {msg}")
            if "10048" in msg:
                self._srv_queue.put(f"{self._ts_now()} [提示] 端口已被占用")
            elif "10013" in msg:
                self._srv_queue.put(f"{self._ts_now()} [提示] 权限不足，以管理员身份运行")
        except Exception as e:
            self._srv_queue.put(f"{self._ts_now()} [错误] {e}")

    def _drain_srv_queue(self):
        while not self._srv_queue.empty():
            try:
                text = self._srv_queue.get_nowait()
                self._srv_log.setReadOnly(False)
                self._srv_log.appendPlainText(text)
                self._srv_log.setReadOnly(True)
            except queue.Empty:
                break

    def _stop_server(self):
        if hasattr(self, '_server_instance'):
            self._server_instance.close_all()
        if hasattr(self, '_srv_timer'):
            self._srv_timer.stop()
        self._srv_toggle_btn.setText("启动服务")
        self._srv_toggle_btn.setStyleSheet(BTN_PRIMARY)
        self._srv_status_label.setText("状态: 已停止")
        self._srv_status_label.setStyleSheet(BODY_STYLE + " color: #666;")
        self._srv_port_entry.setEnabled(True)
        self._srv_dir_entry.setEnabled(True)
        self._srv_user_entry.setEnabled(True)
        self._srv_pass_entry.setEnabled(True)
        self._srv_log.setReadOnly(False)
        self._srv_log.appendPlainText(f"{self._ts_now()} [停止] FTP 服务器已停止")
        self._srv_log.setReadOnly(True)
        logger.info("[FTP服务器] 已停止")

    def _browse_srv_dir(self):
        d = QFileDialog.getExistingDirectory(self.app, "选择根目录")
        if d:
            self._srv_dir_entry.setText(d)

    def on_hide(self):
        try:
            self._disconnect()
        except Exception:
            pass
