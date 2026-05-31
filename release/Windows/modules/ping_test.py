"""
NetTool - Network Toolbox
Version: V100R009C00SPC500
Author: Tang Wenbo (HCIE-Datacom)
Copyright (C) 2026 Tang Wenbo
License: GNU General Public License v3.0 or later

ICMP Ping, Traceroute, and TCPing test module.
"""

import socket
import struct
import re
import threading
import subprocess
import platform
import time
import ipaddress
import errno
import shutil
import os

try:
    import ping3
    HAS_PING3 = True
except ImportError:
    HAS_PING3 = False

from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QPlainTextEdit, QMessageBox, QFileDialog, QDialog,
    QCheckBox,
)
from PySide6.QtCore import Qt

from core.base_module import ToolModule
from core.app import BTN_PRIMARY, BTN_DANGER, BTN_SECONDARY, BTN_MODE_ACTIVE, BTN_MODE_INACTIVE, set_card_style, set_transparent_bg, set_dark_output
from core.app import H1_STYLE, H2_STYLE, H3_STYLE, BODY_STYLE, HINT_STYLE, DESC_STYLE
from core.logger import logger


_PANE_STAT_TITLE = HINT_STYLE
_PANE_STAT_VALUE = H2_STYLE

_TARGET_ENTRY_QSS = """
    QLineEdit {
        border: 1px solid #dfe3e8;
        border-radius: 8px;
        padding: 0 12px;
        background: #ffffff;
        color: #20242a;
        font-size: 13px;
    }
    QLineEdit:focus { border-color: #11a37f; }
"""

_TARGET_ENTRY_ERROR_QSS = """
    QLineEdit {
        border: 1px solid #ff4d4f;
        border-radius: 8px;
        padding: 0 12px;
        background: #fff7f7;
        color: #20242a;
        font-size: 13px;
    }
    QLineEdit:focus { border-color: #ff4d4f; }
"""


class PingTestModule(ToolModule):
    name = "PING 测试"
    icon = "ping"
    description = "支持 ICMP Ping、路由追踪（Traceroute）和 TCP 端口连通性测试（TCPing）。"

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
        layout.addSpacing(15)

        # Input card
        inp_card = QFrame()
        set_card_style(inp_card)
        ic_layout = QVBoxLayout(inp_card)
        ic_layout.setContentsMargins(15, 12, 15, 12)
        ic_layout.setSpacing(8)

        # Target row
        target_label = QLabel("目标地址")
        target_label.setStyleSheet(BODY_STYLE)
        ic_layout.addWidget(target_label)

        target_row = QWidget()
        set_transparent_bg(target_row)
        trl = QHBoxLayout(target_row)
        trl.setContentsMargins(0, 0, 0, 0)
        trl.setSpacing(10)

        self._target_entry = QLineEdit()
        self._target_entry.setPlaceholderText("Ping 支持最多 5 个 IPv4，用空格、逗号或分号分隔")
        self._target_entry.setMinimumHeight(38)
        self._target_entry.setStyleSheet(_TARGET_ENTRY_QSS)
        self._target_entry.returnPressed.connect(self._start)
        self._target_entry.textChanged.connect(self._validate_target_input)
        trl.addWidget(self._target_entry, stretch=1)

        self._start_btn = QPushButton("开始")
        self._start_btn.setStyleSheet(BTN_PRIMARY)
        self._start_btn.setFixedSize(80, 38)
        self._start_btn.clicked.connect(self._start)
        trl.addWidget(self._start_btn)

        ic_layout.addWidget(target_row)
        self._target_status = QLabel("Ping 支持最多 5 个 IPv4 地址")
        self._target_status.setStyleSheet(HINT_STYLE)
        ic_layout.addWidget(self._target_status)
        ic_layout.addSpacing(10)

        # Options row (mode + count + port)
        opt_grid = QGridLayout()
        opt_grid.setSpacing(12)
        opt_grid.setContentsMargins(0, 0, 0, 0)
        ic_layout.addLayout(opt_grid)

        # Mode (column 0)
        mode_label = QLabel("模式")
        mode_label.setStyleSheet(BODY_STYLE)
        opt_grid.addWidget(mode_label, 0, 0)

        self._mode_btns = {}
        mode_wrapper = QWidget()
        mode_wrapper.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        mode_wrapper.setStyleSheet(
            "background: #eef0f2; border: 1px solid #e2e5e9; border-radius: 8px;"
        )
        mwl = QHBoxLayout(mode_wrapper)
        mwl.setContentsMargins(4, 4, 4, 4)
        mwl.setSpacing(4)
        for val, text in [("ping", "Ping"), ("tracert", "Tracert"), ("tcping", "TCPing")]:
            btn = QPushButton(text)
            btn.setFixedHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, v=val: self._set_mode(v))
            mwl.addWidget(btn, stretch=1)
            self._mode_btns[val] = btn
        self._update_mode_buttons("ping")
        opt_grid.addWidget(mode_wrapper, 1, 0)

        # Count (column 1)
        opt_grid.addWidget(QLabel("次数"), 0, 1)
        opt_grid.itemAtPosition(0, 1).widget().setStyleSheet(BODY_STYLE)
        self._count_entry = QLineEdit("4")
        self._count_entry.setFixedWidth(60)
        self._count_entry.setMinimumHeight(30)
        opt_grid.addWidget(self._count_entry, 1, 1)

        # TCP port (column 2)
        opt_grid.addWidget(QLabel("TCP 端口"), 0, 2)
        opt_grid.itemAtPosition(0, 2).widget().setStyleSheet(BODY_STYLE)
        self._port_entry = QLineEdit("80")
        self._port_entry.setFixedWidth(60)
        self._port_entry.setMinimumHeight(30)
        self._port_entry.textChanged.connect(self._validate_target_input)
        opt_grid.addWidget(self._port_entry, 1, 2)

        # Button row
        btn_row = QWidget()
        set_transparent_bg(btn_row)
        brl = QHBoxLayout(btn_row)
        brl.setContentsMargins(0, 0, 0, 0)
        brl.setSpacing(8)
        ic_layout.addWidget(btn_row)
        ic_layout.addSpacing(4)

        self._stop_btn = QPushButton("停止")
        self._stop_btn.setStyleSheet(BTN_DANGER)
        self._stop_btn.setFixedSize(70, 34)
        self._stop_btn.clicked.connect(self._stop)
        self._stop_btn.setEnabled(False)
        brl.addWidget(self._stop_btn)

        self._clear_btn = QPushButton("清空")
        self._clear_btn.setStyleSheet(BTN_SECONDARY)
        self._clear_btn.setFixedSize(70, 34)
        self._clear_btn.clicked.connect(self._clear_output)
        brl.addWidget(self._clear_btn)

        self._save_btn = QPushButton("保存结果")
        self._save_btn.setStyleSheet(BTN_SECONDARY)
        self._save_btn.setFixedSize(90, 34)
        self._save_btn.clicked.connect(lambda checked=False: self._save_outputs())
        brl.addWidget(self._save_btn)

        self._live_save_check = QCheckBox("实时保存")
        self._live_save_check.setStyleSheet("""
            QCheckBox {
                color: #394150;
                background: transparent;
                font-size: 12px;
                font-weight: 700;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
                border: 1px solid #cfd5dc;
                border-radius: 4px;
                background: #ffffff;
            }
            QCheckBox::indicator:checked {
                background: #11a37f;
                border-color: #11a37f;
            }
        """)
        brl.addWidget(self._live_save_check)
        brl.addStretch(1)

        layout.addWidget(inp_card)
        layout.addSpacing(15)

        # Output card
        out_card = QFrame()
        set_card_style(out_card)
        oc_layout = QVBoxLayout(out_card)
        oc_layout.setContentsMargins(15, 12, 15, 12)
        oc_layout.setSpacing(8)

        # Stats row
        stats_widget = QWidget()
        set_transparent_bg(stats_widget)
        sl = QHBoxLayout(stats_widget)
        sl.setContentsMargins(10, 8, 10, 8)
        sl.setSpacing(20)

        self._stats_sent = self._make_stat_label(sl, "已发送", "0")
        self._stats_recv = self._make_stat_label(sl, "已接收", "0")
        self._stats_loss = self._make_stat_label(sl, "丢包率", "0%")
        self._stats_avg = self._make_stat_label(sl, "平均延迟", "- ms")

        stats_widget.hide()
        oc_layout.addWidget(stats_widget)

        # Output area. Ping can split the main echo area into up to 5 panes.
        self._output_wrap = QWidget()
        set_transparent_bg(self._output_wrap)
        self._output_grid = QGridLayout(self._output_wrap)
        self._output_grid.setContentsMargins(0, 0, 0, 0)
        self._output_grid.setSpacing(8)
        self._outputs = []
        self._output_panes = []
        self._output_titles = []
        self._output_names = []
        self._output_started_at = []
        self._pane_stats = []
        for i in range(5):
            pane = QFrame()
            pane.setObjectName("PingOutputPane")
            pane.setStyleSheet("""
                QFrame#PingOutputPane {
                    border: 1px solid #dfe3e8;
                    border-radius: 8px;
                    background: #f8fafb;
                }
                QLabel#PingOutputTitle {
                    color: #52606d;
                    font-size: 12px;
                    font-weight: 700;
                    background: transparent;
                }
            """)
            pane_layout = QVBoxLayout(pane)
            pane_layout.setContentsMargins(0, 0, 0, 0)
            pane_layout.setSpacing(0)

            header = QWidget()
            header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            header.setStyleSheet("background: transparent; border: none;")
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(10, 7, 10, 6)
            header_layout.setSpacing(6)
            title_label = QLabel(f"目标 {i + 1}")
            title_label.setObjectName("PingOutputTitle")
            title_label.setStyleSheet("")
            header_layout.addWidget(title_label)
            header_layout.addStretch(1)
            pane_layout.addWidget(header)

            pane_stats = QWidget()
            pane_stats.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            pane_stats.setStyleSheet("background: transparent; border: none;")
            pane_stats_layout = QHBoxLayout(pane_stats)
            pane_stats_layout.setContentsMargins(10, 0, 10, 8)
            pane_stats_layout.setSpacing(14)
            stat_labels = {
                "sent": self._make_pane_stat_label(pane_stats_layout, "已发送", "0"),
                "recv": self._make_pane_stat_label(pane_stats_layout, "已接收", "0"),
                "loss": self._make_pane_stat_label(pane_stats_layout, "丢包率", "0%"),
                "avg": self._make_pane_stat_label(pane_stats_layout, "平均延迟", "- ms"),
            }
            pane_layout.addWidget(pane_stats)

            editor = QPlainTextEdit()
            editor.setReadOnly(True)
            set_dark_output(editor)
            editor.setMinimumHeight(120)
            editor.setStyleSheet(editor.styleSheet() + """
                QPlainTextEdit {
                    border-left: none;
                    border-right: none;
                    border-bottom: none;
                    border-top-left-radius: 0px;
                    border-top-right-radius: 0px;
                    border-bottom-left-radius: 8px;
                    border-bottom-right-radius: 8px;
                    background: #202020;
                }
                QPlainTextEdit QWidget {
                    background: #202020;
                }
            """)
            pane_layout.addWidget(editor, stretch=1)

            self._outputs.append(editor)
            self._output_panes.append(pane)
            self._output_titles.append(title_label)
            self._pane_stats.append(stat_labels)
            self._output_grid.addWidget(pane, 0, i)
            pane.hide()
        self._output = self._outputs[0]
        self._configure_outputs(1)
        oc_layout.addWidget(self._output_wrap, stretch=1)

        layout.addWidget(out_card, stretch=1)

        self._stop_event = threading.Event()
        self._popen = None
        self._popens = []
        self._popen_lock = threading.Lock()
        self._stats_lock = threading.Lock()
        self._live_save_lock = threading.Lock()
        self._live_save_files = []
        self._live_save_paths = []
        self._last_save_directory = os.path.expanduser("~/Desktop")
        self._active_workers = 0
        self._stats_state = [{"sent": 0, "recv": 0, "total_rtt": 0.0} for _ in range(5)]

    def _make_stat_label(self, parent_layout, title, init_val):
        wrapper = QWidget()
        set_transparent_bg(wrapper)
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet(HINT_STYLE)
        wl.addWidget(t)
        v = QLabel(init_val)
        v.setStyleSheet(H2_STYLE)
        wl.addWidget(v)
        parent_layout.addWidget(wrapper)
        return v

    def _make_pane_stat_label(self, parent_layout, title, init_val):
        wrapper = QWidget()
        set_transparent_bg(wrapper)
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(1)
        t = QLabel(title)
        t.setStyleSheet(_PANE_STAT_TITLE)
        wl.addWidget(t)
        v = QLabel(init_val)
        v.setStyleSheet(_PANE_STAT_VALUE)
        wl.addWidget(v)
        parent_layout.addWidget(wrapper, stretch=1)
        return v

    def _set_mode(self, mode):
        self._current_mode = mode
        self._update_mode_buttons(mode)
        if hasattr(self, "_target_entry"):
            if mode == "ping":
                self._target_entry.setPlaceholderText("Ping 支持最多 5 个 IPv4，用空格、逗号或分号分隔")
            elif mode == "tracert":
                self._target_entry.setPlaceholderText("Tracert 支持最多 5 个 IPv4，用空格、逗号或分号分隔")
            else:
                self._target_entry.setPlaceholderText("TCPing 支持 IPv4 或 IPv4:端口，例如: 10.0.0.1:22")
            self._validate_target_input()

    def _update_mode_buttons(self, val):
        for v, btn in self._mode_btns.items():
            if v == val:
                btn.setStyleSheet(BTN_MODE_ACTIVE)
            else:
                btn.setStyleSheet(BTN_MODE_INACTIVE)

    # ── Start / Stop ──

    def _start(self):
        target_text = self._target_entry.text().strip()
        if not target_text:
            QMessageBox.warning(self.app, "提示", "请输入目标地址")
            return

        mode = getattr(self, "_current_mode", "ping")
        targets = self._parse_targets(target_text)
        if not targets:
            self._set_target_error("请输入有效的 IPv4 地址")
            QMessageBox.warning(self.app, "提示", "请输入有效的目标地址")
            return

        try:
            count = int(self._count_entry.text().strip() or "4")
        except ValueError:
            logger.warning("[PING测试] 参数无效: 次数不是数字")
            QMessageBox.warning(self.app, "提示", "次数必须是数字")
            return
        if count <= 0:
            QMessageBox.warning(self.app, "提示", "次数必须大于 0")
            return

        tcp_endpoints = []
        if mode == "tcping":
            default_port, port_msg = self._parse_port(self._port_entry.text().strip() or "80")
            if default_port is None:
                self._set_target_error(port_msg)
                QMessageBox.warning(self.app, "提示", port_msg)
                return
            ok, tcp_endpoints, message = self._parse_tcping_endpoints(targets, default_port)
            if not ok:
                self._set_target_error(message)
                QMessageBox.warning(self.app, "提示", message)
                return
        else:
            ok, message = self._validate_targets(targets, mode)
            if not ok:
                self._set_target_error(message)
                QMessageBox.warning(self.app, "提示", message)
                return

        logger.info(f"[PING测试] 开始: mode={mode}, targets={targets}, tcp_endpoints={tcp_endpoints}, count={count}")

        self._stop_event.clear()
        self._close_live_output_files()
        self._clear_output()
        self._reset_stats_state()
        output_titles = (
            [f"{host}:{port}" for host, port in tcp_endpoints]
            if mode == "tcping" else targets
        )
        self._configure_outputs(len(output_titles))
        self._set_output_titles(output_titles)
        if self._live_save_check.isChecked():
            directory = self._choose_save_directory(
                title="实时保存",
                description="开始后会按目标创建 txt 文件，并实时写入回显。"
            )
            if not directory:
                logger.info("[PING测试] 实时保存取消: 未选择目录")
                return
            if not self._prepare_live_output_files(directory, len(output_titles)):
                return
        self._stop_btn.setEnabled(True)
        self._start_btn.setEnabled(False)
        self._live_save_check.setEnabled(False)

        if mode == "ping":
            self._set_active_workers(len(targets))
            for idx, target in enumerate(targets):
                threading.Thread(target=self._run_ping, args=(target, count, idx), daemon=True).start()
        elif mode == "tracert":
            self._set_active_workers(len(targets))
            for idx, target in enumerate(targets):
                threading.Thread(target=self._run_tracert, args=(target, idx), daemon=True).start()
        else:
            self._set_active_workers(len(tcp_endpoints))
            for idx, (target, port) in enumerate(tcp_endpoints):
                threading.Thread(target=self._run_tcping, args=(target, count, port, idx), daemon=True).start()

    def _stop(self):
        logger.info("[PING测试] 用户停止测试")
        self._stop_event.set()
        with self._popen_lock:
            popens = list(self._popens)
        for popen in popens:
            try:
                popen.terminate()
                logger.info("[PING测试] 已终止 traceroute 子进程")
            except Exception:
                logger.exception("[PING测试] 终止子进程失败")

    def _finish(self):
        done = False
        with self._stats_lock:
            self._active_workers = max(0, self._active_workers - 1)
            done = self._active_workers == 0
        if done:
            self._close_live_output_files()
            self.app.after(0, lambda: self._start_btn.setEnabled(True))
            self.app.after(0, lambda: self._stop_btn.setEnabled(False))
            self.app.after(0, lambda: self._live_save_check.setEnabled(True))

    def _set_active_workers(self, count):
        with self._stats_lock:
            self._active_workers = count

    def _reset_stats_state(self):
        with self._stats_lock:
            self._stats_state = [{"sent": 0, "recv": 0, "total_rtt": 0.0} for _ in range(5)]

    def _parse_targets(self, text):
        parts = [p.strip() for p in re.split(r"[\s,;，；]+", text) if p.strip()]
        targets = []
        seen = set()
        for part in parts:
            key = part.lower()
            if key in seen:
                continue
            targets.append(part)
            seen.add(key)
        return targets

    def _is_ipv4(self, value):
        try:
            ipaddress.IPv4Address(value)
            return True
        except Exception:
            return False

    def _validate_targets(self, targets, mode):
        mode_name = "Tracert" if mode == "tracert" else "Ping"
        if len(targets) > 5:
            return False, f"{mode_name} 最多支持 5 个 IPv4 地址"
        invalid = [target for target in targets if not self._is_ipv4(target)]
        if invalid:
            return False, f"非法 IPv4 地址: {', '.join(invalid[:3])}"
        return True, ""

    def _parse_port(self, value):
        try:
            port = int(str(value).strip())
        except Exception:
            return None, "TCP 端口必须是数字"
        if port <= 0 or port > 65535:
            return None, "TCP 端口必须在 1-65535 之间"
        return port, ""

    def _parse_tcping_endpoints(self, entries, default_port):
        if len(entries) > 5:
            return False, [], "TCPing 最多支持 5 个目标"
        endpoints = []
        seen = set()
        for entry in entries:
            host = entry
            port = default_port
            if ":" in entry:
                host, port_text = entry.rsplit(":", 1)
                host = host.strip()
                port, port_msg = self._parse_port(port_text)
                if port is None:
                    return False, [], f"{entry} 的 {port_msg}"
            if not self._is_ipv4(host):
                return False, [], f"非法 IPv4 地址: {host or entry}"
            key = (host, port)
            if key in seen:
                continue
            endpoints.append(key)
            seen.add(key)
        return True, endpoints, ""

    def _validate_target_input(self):
        if not hasattr(self, "_target_entry"):
            return True
        text = self._target_entry.text().strip()
        mode = getattr(self, "_current_mode", "ping")
        if not text:
            if mode == "ping":
                self._set_target_hint("Ping 支持最多 5 个 IPv4 地址")
            elif mode == "tracert":
                self._set_target_hint("Tracert 支持最多 5 个 IPv4 地址")
            else:
                self._set_target_hint("TCPing 支持最多 5 个目标，可写 IPv4 或 IPv4:端口")
            return True
        targets = self._parse_targets(text)
        if mode == "tcping":
            default_port, port_msg = self._parse_port(self._port_entry.text().strip() or "80")
            if default_port is None:
                self._set_target_error(port_msg)
                return False
            ok, endpoints, message = self._parse_tcping_endpoints(targets, default_port)
        else:
            ok, message = self._validate_targets(targets, mode)
        if ok:
            if mode == "tcping":
                self._set_target_hint(f"已识别 {len(endpoints)} 个 TCPing 目标")
            else:
                self._set_target_hint(f"已识别 {len(targets)} 个 IPv4 地址")
        else:
            self._set_target_error(message)
        return ok

    def _set_target_hint(self, message):
        self._target_entry.setStyleSheet(_TARGET_ENTRY_QSS)
        if hasattr(self, "_target_status"):
            self._target_status.setText(message)
            self._target_status.setStyleSheet(HINT_STYLE)

    def _set_target_error(self, message):
        self._target_entry.setStyleSheet(_TARGET_ENTRY_ERROR_QSS)
        if hasattr(self, "_target_status"):
            self._target_status.setText(message)
            self._target_status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")

    def _timestamp(self):
        return time.strftime("%Y-%m-%d %H:%M:%S")

    def _format_output(self, text):
        return f"[{self._timestamp()}] {text}"

    def _append_output(self, text, pane=0):
        pane = max(0, min(pane, len(self._outputs) - 1))
        formatted = self._format_output(text)
        self._write_live_output(pane, formatted)
        self.app.after(0, lambda p=pane, t=formatted: self._outputs[p].appendPlainText(t))

    def _configure_outputs(self, count):
        count = max(1, min(count, len(self._output_panes)))
        for pane in self._output_panes:
            self._output_grid.removeWidget(pane)
            pane.hide()

        for i in range(count):
            pane = self._output_panes[i]
            self._output_grid.addWidget(pane, 0, i)
            pane.show()

        self._output_grid.setRowStretch(0, 1)
        for row in range(1, 3):
            self._output_grid.setRowStretch(row, 0)
        for col in range(5):
            self._output_grid.setColumnStretch(col, 1 if col < count else 0)

    def _set_output_titles(self, targets):
        self._output_names = []
        self._output_started_at = []
        started_at = time.strftime("%Y%m%d_%H%M%S")
        for i, label in enumerate(self._output_titles):
            if i < len(targets):
                label.setText(f"目标 {i + 1}  {targets[i]}")
                self._output_names.append(str(targets[i]))
                self._output_started_at.append(started_at)
            else:
                label.setText(f"目标 {i + 1}")
                self._output_names.append(f"目标_{i + 1}")
                self._output_started_at.append(started_at)

    def _safe_output_part(self, value, fallback):
        safe = re.sub(r"[^0-9A-Za-z._-]+", "_", str(value).strip())
        safe = safe.replace(":", "_").strip("._-")
        return safe or fallback

    def _safe_output_filename(self, name, index):
        started_at = (
            self._output_started_at[index]
            if index < len(self._output_started_at) and self._output_started_at[index]
            else time.strftime("%Y%m%d_%H%M%S")
        )
        safe_time = self._safe_output_part(started_at, time.strftime("%Y%m%d_%H%M%S"))
        safe_target = self._safe_output_part(name, f"target_{index + 1}")
        return f"{safe_time}_{safe_target}.txt"

    def _normalize_saved_output(self, text):
        return "\n".join(line for line in text.splitlines() if line.strip())

    def _choose_save_directory(self, title="保存结果", description="每个目标会单独保存为一个 txt 文件。"):
        dialog = QDialog(self.app)
        dialog.setObjectName("SaveOutputDialog")
        dialog.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        dialog.setWindowTitle(title)
        dialog.setModal(True)
        dialog.setFixedWidth(520)
        dialog.setStyleSheet("""
            QDialog#SaveOutputDialog {
                background: #ffffff;
                color: #20242a;
            }
            QDialog#SaveOutputDialog QLabel {
                background: transparent;
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title_label = QLabel("选择保存目录")
        title_label.setStyleSheet(H2_STYLE)
        layout.addWidget(title_label)

        desc = QLabel(description)
        desc.setStyleSheet(HINT_STYLE)
        layout.addWidget(desc)

        row = QWidget()
        set_transparent_bg(row)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        path_edit = QLineEdit(self._last_save_directory or os.path.expanduser("~/Desktop"))
        path_edit.setMinimumHeight(36)
        path_edit.setStyleSheet(_TARGET_ENTRY_QSS)
        row_layout.addWidget(path_edit, stretch=1)

        browse_btn = QPushButton("浏览")
        browse_btn.setStyleSheet(BTN_SECONDARY)
        browse_btn.setFixedSize(72, 36)
        row_layout.addWidget(browse_btn)
        layout.addWidget(row)

        buttons = QWidget()
        set_transparent_bg(buttons)
        buttons_layout = QHBoxLayout(buttons)
        buttons_layout.setContentsMargins(0, 4, 0, 0)
        buttons_layout.setSpacing(8)
        buttons_layout.addStretch(1)

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(BTN_SECONDARY)
        cancel_btn.setFixedSize(82, 36)
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet(BTN_PRIMARY)
        save_btn.setFixedSize(82, 36)
        buttons_layout.addWidget(cancel_btn)
        buttons_layout.addWidget(save_btn)
        layout.addWidget(buttons)

        result = {"path": ""}

        def browse():
            start_dir = path_edit.text().strip() or os.path.expanduser("~/Desktop")
            chosen = QFileDialog.getExistingDirectory(dialog, "选择目录", start_dir)
            if chosen:
                path_edit.setText(chosen)

        def accept():
            path = os.path.expanduser(path_edit.text().strip())
            if not path or not os.path.isdir(path):
                QMessageBox.warning(dialog, "提示", "请选择有效的保存目录。")
                return
            result["path"] = path
            self._last_save_directory = path
            dialog.accept()

        browse_btn.clicked.connect(browse)
        cancel_btn.clicked.connect(dialog.reject)
        save_btn.clicked.connect(accept)
        path_edit.returnPressed.connect(accept)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return ""
        return result["path"]

    def _unique_output_path(self, directory, filename, used_names):
        base, ext = os.path.splitext(filename)
        candidate = filename
        suffix = 2
        while candidate.lower() in used_names or os.path.exists(os.path.join(directory, candidate)):
            candidate = f"{base}_{suffix}{ext}"
            suffix += 1
        used_names.add(candidate.lower())
        return os.path.join(directory, candidate)

    def _prepare_live_output_files(self, directory, count):
        self._close_live_output_files()
        files = [None] * len(self._outputs)
        paths = [""] * len(self._outputs)
        used_names = set()
        try:
            for i in range(max(0, min(count, len(self._outputs)))):
                target_name = self._output_names[i] if i < len(self._output_names) else f"target_{i + 1}"
                filename = self._safe_output_filename(target_name, i)
                path = self._unique_output_path(directory, filename, used_names)
                files[i] = open(path, "a", encoding="utf-8", buffering=1)
                paths[i] = path
            with self._live_save_lock:
                self._live_save_files = files
                self._live_save_paths = paths
            logger.info(f"[PING测试] 实时保存已启用: count={count}, dir={directory}")
            return True
        except Exception as e:
            for file_obj in files:
                if file_obj:
                    try:
                        file_obj.close()
                    except Exception:
                        pass
            logger.exception("[PING测试] 创建实时保存文件失败")
            QMessageBox.critical(self.app, "实时保存失败", f"创建保存文件失败: {e}")
            return False

    def _write_live_output(self, pane, formatted_text):
        if not formatted_text.strip():
            return
        with self._live_save_lock:
            if pane >= len(self._live_save_files):
                return
            file_obj = self._live_save_files[pane]
            if not file_obj:
                return
            try:
                file_obj.write(formatted_text.rstrip() + "\n")
            except Exception:
                logger.exception("[PING测试] 实时写入输出失败")

    def _close_live_output_files(self):
        with self._live_save_lock:
            files = list(getattr(self, "_live_save_files", []))
            paths = list(getattr(self, "_live_save_paths", []))
            self._live_save_files = []
            self._live_save_paths = []
        closed = 0
        for file_obj in files:
            if file_obj:
                try:
                    file_obj.close()
                    closed += 1
                except Exception:
                    logger.exception("[PING测试] 关闭实时保存文件失败")
        if closed:
            logger.info(f"[PING测试] 实时保存文件已关闭: count={closed}, paths={paths}")

    def _save_outputs(self):
        try:
            logger.info("[PING测试] 点击保存结果")
            visible = [
                (i, editor)
                for i, editor in enumerate(self._outputs)
                if i < len(self._output_panes) and not self._output_panes[i].isHidden()
            ]
            if not visible:
                QMessageBox.information(self.app, "提示", "当前没有可保存的输出。")
                return

            has_content = any(editor.toPlainText().strip() for _i, editor in visible)
            if not has_content:
                QMessageBox.information(self.app, "提示", "当前输出为空，无需保存。")
                return

            directory = self._choose_save_directory()
            if not directory:
                logger.info("[PING测试] 保存输出取消: 未选择目录")
                return

            saved = []
            used_names = set()
            for i, editor in visible:
                content = self._normalize_saved_output(editor.toPlainText())
                if not content:
                    continue
                target_name = self._output_names[i] if i < len(self._output_names) else f"target_{i + 1}"
                filename = self._safe_output_filename(target_name, i)
                path = self._unique_output_path(directory, filename, used_names)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content + "\n")
                saved.append(path)

            if not saved:
                QMessageBox.information(self.app, "提示", "当前输出为空，无需保存。")
                return
            logger.info(f"[PING测试] 保存输出结果: count={len(saved)}, dir={directory}")
            QMessageBox.information(self.app, "保存完成", f"已保存 {len(saved)} 个 txt 文件。")
        except Exception as e:
            logger.exception("[PING测试] 保存输出结果失败")
            QMessageBox.critical(self.app, "保存失败", f"保存结果失败: {e}")

    def _update_stats(self, pane=0, sent_delta=0, recv_delta=0, rtt_delta=0.0):
        pane = max(0, min(pane, len(self._stats_state) - 1))
        with self._stats_lock:
            state = self._stats_state[pane]
            state["sent"] += sent_delta
            state["recv"] += recv_delta
            state["total_rtt"] += rtt_delta
            sent = state["sent"]
            recv = state["recv"]
            total_rtt = state["total_rtt"]

            total_sent = sum(item["sent"] for item in self._stats_state)
            total_recv = sum(item["recv"] for item in self._stats_state)
            total_rtt_all = sum(item["total_rtt"] for item in self._stats_state)

        labels = self._pane_stats[pane] if pane < len(self._pane_stats) else None
        if labels:
            self.app.after(0, lambda s=sent, lab=labels["sent"]: lab.setText(str(s)))
            self.app.after(0, lambda r=recv, lab=labels["recv"]: lab.setText(str(r)))
        if sent > 0:
            loss = (1 - recv / sent) * 100
            color = "#27ae60" if loss < 10 else "#f59e0b" if loss < 50 else "#e74c3c"
            if labels:
                self.app.after(0, lambda l=loss, lab=labels["loss"]: lab.setText(f"{l:.1f}%"))
                self.app.after(0, lambda c=color, lab=labels["loss"]: lab.setStyleSheet(_PANE_STAT_VALUE + f" color: {c};"))
        if recv > 0:
            avg = total_rtt / recv
            if labels:
                self.app.after(0, lambda a=avg, lab=labels["avg"]: lab.setText(f"{a:.1f} ms"))

        self.app.after(0, lambda s=total_sent: self._stats_sent.setText(str(s)))
        self.app.after(0, lambda r=total_recv: self._stats_recv.setText(str(r)))
        if total_sent > 0:
            total_loss = (1 - total_recv / total_sent) * 100
            self.app.after(0, lambda l=total_loss: self._stats_loss.setText(f"{l:.1f}%"))
        if total_recv > 0:
            total_avg = total_rtt_all / total_recv
            self.app.after(0, lambda a=total_avg: self._stats_avg.setText(f"{a:.1f} ms"))

    # ── ICMP checksum ──

    @staticmethod
    def _icmp_checksum(data):
        if len(data) % 2:
            data += b'\x00'
        s = sum(struct.unpack('!' + 'H' * (len(data) // 2), data))
        s = (s >> 16) + (s & 0xFFFF)
        s += s >> 16
        return ~s & 0xFFFF

    # ── Ping ──

    def _run_ping(self, target, count, pane=0):
        self._append_output(f"--- Ping {target} ({count} 次) ---", pane)
        sent = recv = total_rtt = 0
        latencies = []
        try:
            for seq in range(count):
                if self._stop_event.is_set():
                    break
                sent += 1
                self._update_stats(pane=pane, sent_delta=1)
                try:
                    if HAS_PING3:
                        rtt = ping3.ping(target, timeout=2, unit="ms")
                        if rtt is not None:
                            recv += 1
                            total_rtt += rtt
                            latencies.append(rtt)
                            line = f"Reply from {target}: time={rtt:.1f}ms"
                            self._update_stats(pane=pane, recv_delta=1, rtt_delta=rtt)
                        else:
                            line = f"Request timed out."
                    else:
                        line = "ping3 not available"
                except Exception as e:
                    line = f"Error: {e}"

                self._append_output(line, pane)

                if seq < count - 1 and not self._stop_event.is_set():
                    time.sleep(0.5)

        except Exception as e:
            logger.exception(f"[PING测试] Ping 异常: {target}")
            self._append_output(f"Error: {e}", pane)
        finally:
            if sent > 0 and recv > 0:
                mn, mx, avg = min(latencies), max(latencies), total_rtt / recv
                loss_rate = (sent - recv) / sent * 100
                summary = (f"--- 统计: 发送={sent}, 接收={recv}, "
                           f"丢包率={loss_rate:.1f}%, "
                           f"最小={mn:.1f}ms, 最大={mx:.1f}ms, 平均={avg:.1f}ms ---")
            elif sent > 0:
                summary = f"--- 统计: 发送={sent}, 接收={recv}, 目标不可达 ---"
            else:
                summary = ""
            if summary:
                self._append_output(summary, pane)
                logger.info(f"[PING测试] Ping 完成: target={target}, {summary}")
            else:
                logger.info(f"[PING测试] Ping 结束: target={target}, 未发送请求")
            self._finish()

    # ── Traceroute ──

    def _run_tracert(self, target, pane=0):
        self._append_output(f"--- Tracert {target} ---", pane)
        if platform.system() == "Windows":
            cmd = ["tracert", "-d", target]      # -d: no DNS, faster
        else:
            cmd = ["/usr/sbin/traceroute", "-n", target]  # -n: no DNS, faster
        logger.info(f"[PING测试] Tracert 执行命令: {' '.join(cmd)}")
        # Windows: hide CMD window
        si = None
        if platform.system() == "Windows":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
        try:
            popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, bufsize=1, startupinfo=si)
            with self._popen_lock:
                self._popens.append(popen)
                self._popen = popen
            line_count = 0
            for line in popen.stdout:
                if self._stop_event.is_set():
                    break
                line = line.strip()
                if line:
                    line_count += 1
                    self._append_output(line, pane)
            popen.wait()
            logger.info(f"[PING测试] Tracert 完成: target={target}, returncode={popen.returncode}, lines={line_count}")
            if self._stop_event.is_set():
                self._append_output(f"--- Tracert 已停止: {target} ---", pane)
            elif line_count == 0:
                self._append_output("没有收到traceroute输出，请确认目标可达且网络正常", pane)
                self._append_output(f"--- Tracert 结束: {target}，无有效输出 ---", pane)
            else:
                self._append_output(f"--- Tracert 完成: {target}，共 {line_count} 行 ---", pane)
        except FileNotFoundError:
            logger.error("[PING测试] traceroute/tracert 命令不可用")
            self._append_output("traceroute 命令不可用，请确认系统已安装", pane)
        except Exception as e:
            logger.exception(f"[PING测试] Tracert 异常: {target}")
            self._append_output(f"traceroute 执行异常: {e}", pane)
        finally:
            try:
                with self._popen_lock:
                    if "popen" in locals() and popen in self._popens:
                        self._popens.remove(popen)
                    self._popen = self._popens[-1] if self._popens else None
            except Exception:
                self._popen = None
            self._finish()

    # ── TCPing ──

    def _tcp_probe_with_nc(self, target, port, timeout=2):
        nc_path = shutil.which("nc")
        if not nc_path:
            return None

        if platform.system() == "Darwin":
            cmd = [nc_path, "-4", "-z", "-G", str(timeout), "-w", str(timeout), target, str(port)]
        else:
            cmd = [nc_path, "-4", "-z", "-w", str(timeout), target, str(port)]

        start = time.perf_counter()
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout + 1,
            )
            elapsed = (time.perf_counter() - start) * 1000
            raw = (result.stdout or "").strip()
            if result.returncode == 0:
                detail = raw or "连接成功"
            else:
                detail = raw or "连接失败"
            return result.returncode == 0, elapsed, detail, " ".join(cmd)
        except subprocess.TimeoutExpired as e:
            elapsed = (time.perf_counter() - start) * 1000
            raw = (e.stdout or "").strip() if isinstance(e.stdout, str) else ""
            return False, elapsed, raw or f"nc timeout after {timeout}s", " ".join(cmd)
        except Exception:
            logger.exception(f"[PING测试] nc TCPing 执行异常: {target}:{port}")
            return None

    def _tcp_probe_with_socket(self, target, port, timeout=2):
        start = time.perf_counter()
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((target, port))
            elapsed = (time.perf_counter() - start) * 1000
            local_ip, local_port = sock.getsockname()[:2]
            return True, elapsed, f"local={local_ip}:{local_port}", "python socket.connect"
        except socket.timeout:
            elapsed = (time.perf_counter() - start) * 1000
            return False, elapsed, f"timeout={timeout:.1f}s", "python socket.connect"
        except OSError as e:
            elapsed = (time.perf_counter() - start) * 1000
            reason = "连接被拒绝" if e.errno in (errno.ECONNREFUSED, 61, 111) else str(e)
            return False, elapsed, reason, "python socket.connect"
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return False, elapsed, str(e), "python socket.connect"
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass

    def _run_tcping(self, target, count, port, pane=0):
        self._append_output(f"--- TCPing {target}:{port} ({count} 次) ---", pane)
        sent = recv = total_rtt = 0
        latencies = []
        for seq in range(count):
            if self._stop_event.is_set():
                break
            sent += 1
            self._update_stats(pane=pane, sent_delta=1)
            probe = self._tcp_probe_with_nc(target, port, timeout=2)
            if probe is None:
                probe = self._tcp_probe_with_socket(target, port, timeout=2)
            ok, rtt, detail, source = probe
            detail = detail or ("连接成功" if ok else "连接失败")
            if ok:
                recv += 1
                total_rtt += rtt
                latencies.append(rtt)
                line = f"seq={seq + 1} [成功] {target}:{port} time={rtt:.1f}ms"
                self._update_stats(pane=pane, recv_delta=1, rtt_delta=rtt)
            else:
                line = f"seq={seq + 1} [失败] {target}:{port} time={rtt:.1f}ms {detail}"

            self._append_output(line, pane)

            if seq < count - 1 and not self._stop_event.is_set():
                time.sleep(0.3)

        if sent > 0:
            success_rate = recv / sent * 100
            if recv > 0:
                mn, mx, avg = min(latencies), max(latencies), total_rtt / recv
                min_text = f"{mn:.1f}ms"
                max_text = f"{mx:.1f}ms"
                avg_text = f"{avg:.1f}ms"
            else:
                min_text = max_text = avg_text = "-"
            summary = (f"--- 统计: 发送={sent}, 接收={recv}, "
                       f"成功率={success_rate:.1f}%, "
                       f"最小={min_text}, 最大={max_text}, 平均={avg_text} ---")
        else:
            summary = ""
        if summary:
            self._append_output(summary, pane)
            logger.info(f"[PING测试] TCPing 完成: target={target}:{port}, {summary}")
        else:
            logger.info(f"[PING测试] TCPing 结束: target={target}:{port}, 未发送请求")
        self._finish()

    # ── Output ──

    def _clear_output(self):
        logger.info("[PING测试] 清空输出")
        for editor in getattr(self, "_outputs", []):
            editor.clear()
        for labels in getattr(self, "_pane_stats", []):
            labels["sent"].setText("0")
            labels["recv"].setText("0")
            labels["loss"].setText("0%")
            labels["loss"].setStyleSheet(_PANE_STAT_VALUE)
            labels["avg"].setText("- ms")
        self._stats_sent.setText("0")
        self._stats_recv.setText("0")
        self._stats_loss.setText("0%")
        self._stats_avg.setText("- ms")
        self._stats_loss.setStyleSheet(H2_STYLE)
        self._reset_stats_state()
