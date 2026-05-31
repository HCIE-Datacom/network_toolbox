"""
NetTool - Network Toolbox
Version: V100R009C00SPC500
Author: Tang Wenbo (HCIE-Datacom)
Copyright (C) 2026 Tang Wenbo
License: GNU General Public License v3.0 or later

NTP client query and local NTP server module.
"""

import socket
import struct
import time
import threading
import queue
import platform
import subprocess

from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QPlainTextEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from core.base_module import ToolModule
from core.app import (
    BTN_PRIMARY, BTN_DANGER, BTN_SECONDARY, BTN_MODE_ACTIVE, BTN_MODE_INACTIVE,
    set_card_style, set_transparent_bg, set_dark_output,
    H1_STYLE, H2_STYLE, H3_STYLE, BODY_STYLE, HINT_STYLE, DESC_STYLE,
)
from core.logger import logger

# ========== Shared NTP Protocol (unchanged) ==========

NTP_EPOCH_DIFF = 2208988800
NTP_PACKET_FORMAT = "!B B B b 11I"


def _ntp_to_unix_seconds(tx_int, tx_frac):
    return (tx_int - NTP_EPOCH_DIFF) + (tx_frac / (2 ** 32))


def _create_ntp_packet(version=4, mode=3):
    first_byte = (0 << 6) | (version << 3) | mode
    return struct.pack(NTP_PACKET_FORMAT, first_byte, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)


def _query_ntp(server, port=123, timeout=5):
    packet = _create_ntp_packet(version=4, mode=3)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        local_before = time.time()
        sock.sendto(packet, (server, port))
        data, addr = sock.recvfrom(1024)
        local_after = time.time()
    finally:
        sock.close()
    if len(data) < 48:
        raise ValueError("Received packet too short")
    unpacked = struct.unpack(NTP_PACKET_FORMAT, data)
    tx_int, tx_frac = unpacked[13], unpacked[14]
    server_time = _ntp_to_unix_seconds(tx_int, tx_frac)
    rtt = local_after - local_before
    offset = server_time - (local_before + local_after) / 2
    return {
        "server": server, "server_ip": addr[0],
        "server_time": server_time, "local_time": local_after,
        "rtt": rtt, "offset": offset,
    }


def _parse_ntp_request(data):
    unpacked = struct.unpack(NTP_PACKET_FORMAT, data)
    return unpacked[13], unpacked[14]


def _create_ntp_response(origin_tx_int, origin_tx_frac, version=4):
    first_byte = (0 << 6) | (version << 3) | 4
    now = time.time()
    ntp_now = now + NTP_EPOCH_DIFF
    tx_int = int(ntp_now)
    tx_frac = int((ntp_now - tx_int) * (2 ** 32))
    ref_id = struct.unpack("!I", b"LOCL")[0]
    return struct.pack(
        NTP_PACKET_FORMAT,
        first_byte, 1, 10, 0, 0, 0, ref_id,
        tx_int, tx_frac, origin_tx_int, origin_tx_frac,
        tx_int, tx_frac, tx_int, tx_frac,
    )


class _NTPServerThread(threading.Thread):
    def __init__(self, port, log_queue):
        super().__init__(daemon=True)
        self.port = int(port)
        self.log_queue = log_queue
        self.sock = None
        self.stop_event = threading.Event()

    @staticmethod
    def _ts():
        return time.strftime("%Y-%m-%d %H:%M:%S")

    def run(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Check admin on Windows
        if platform.system() == "Windows":
            try:
                import ctypes
                is_admin = ctypes.windll.shell32.IsUserAnAdmin()
                self.log_queue.put(f"{self._ts()}  [信息] 管理员权限: {'是' if is_admin else '否'}")
            except Exception:
                pass
        bound = False
        for attempt in range(2):
            try:
                self.log_queue.put(f"{self._ts()}  [信息] 正在绑定端口 {self.port} ...")
                self.sock.bind(("0.0.0.0", self.port))
                bound = True
                break
            except (PermissionError, OSError) as e:
                errno = getattr(e, 'winerror', 0) or getattr(e, 'errno', 0)
                self.log_queue.put(f"{self._ts()}  [错误] 绑定失败 (winerror={errno})")
                # Port occupied or access denied — try stopping w32time on Windows
                if errno in (10013, 10048) and attempt == 0 and platform.system() == "Windows":
                    self.log_queue.put(f"{self._ts()}  [信息] 正在停止 Windows 时间服务 ...")
                    try:
                        import os
                        os.system("net stop w32time /y >nul 2>&1")
                        self.log_queue.put(f"{self._ts()}  [信息] 已停止，重新绑定 ...")
                        self.sock.close()
                        time.sleep(2)
                        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        continue
                    except Exception as se:
                        self.log_queue.put(f"{self._ts()}  [错误] 停止失败: {se}")
                if errno == 10048:
                    self.log_queue.put(f"{self._ts()}  [错误] 端口被占用，请更换端口")
                elif errno == 10013:
                    self.log_queue.put(f"{self._ts()}  [错误] 端口被系统或安全软件阻止")
                return

        if not bound:
            return

        self.log_queue.put(f"{self._ts()}  [启动] NTP 服务器正在监听 0.0.0.0:{self.port}")

        while not self.stop_event.is_set():
            try:
                self.sock.settimeout(1.0)
                data, addr = self.sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break
            if len(data) >= 48:
                try:
                    origin_int, origin_frac = _parse_ntp_request(data)
                    version = (data[0] >> 3) & 0x07
                    client_ts = _ntp_to_unix_seconds(origin_int, origin_frac)
                    client_str = time.strftime("%H:%M:%S", time.localtime(client_ts)) if client_ts > 0 else "N/A"
                    self.log_queue.put(f"{self._ts()}  [请求] 来自 {addr[0]}:{addr[1]}  |  客户端发送时间: {client_str}")
                    response = _create_ntp_response(origin_int, origin_frac, version)
                    self.sock.sendto(response, addr)
                    self.log_queue.put(f"{self._ts()}  [响应] 已向 {addr[0]}:{addr[1]} 发送时间同步数据")
                except Exception as e:
                    self.log_queue.put(f"{self._ts()}  [错误] 处理请求失败: {e}")
        self.log_queue.put(f"{self._ts()}  [停止] NTP 服务器已停止")

    def stop(self):
        self.stop_event.set()
        try:
            self.sock.close()
        except Exception:
            pass


# ═══════════════ Module ═══════════════


class NTPToolModule(ToolModule):
    name = "NTP 工具"
    icon = "ntp"
    description = "查询网络时间服务器或在本机启动 NTP 服务，为局域网设备提供时间同步。"

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

        # Mode selector
        mode_card = QFrame()
        set_card_style(mode_card)
        mc_layout = QVBoxLayout(mode_card)
        mc_layout.setContentsMargins(15, 12, 15, 12)
        mc_layout.setSpacing(8)

        ml = QLabel("功能模式")
        ml.setStyleSheet(H2_STYLE)
        mc_layout.addWidget(ml)

        mb_wrapper = QWidget()
        mb_wrapper.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        mb_wrapper.setStyleSheet(
            "background: #eef0f2; border: 1px solid #e2e5e9; border-radius: 8px;"
        )
        mbl = QHBoxLayout(mb_wrapper)
        mbl.setContentsMargins(4, 4, 4, 4)
        mbl.setSpacing(4)

        self._mode_btns = {}
        for val, text in [("client", "客户端"), ("server", "服务器")]:
            btn = QPushButton(text)
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, v=val: self._set_mode(v))
            mbl.addWidget(btn, stretch=1)
            self._mode_btns[val] = btn
        self._update_mode_buttons(val="client")
        mc_layout.addWidget(mb_wrapper)

        layout.addWidget(mode_card)
        layout.addSpacing(15)

        # Content card
        content_card = QFrame()
        set_card_style(content_card)
        cc_layout = QVBoxLayout(content_card)
        cc_layout.setContentsMargins(15, 12, 15, 12)

        # Client frame
        self._client_frame = QWidget()
        set_transparent_bg(self._client_frame)
        self._build_client_ui(self._client_frame)
        cc_layout.addWidget(self._client_frame)

        # Server frame
        self._server_frame = QWidget()
        set_transparent_bg(self._server_frame)
        self._build_server_ui(self._server_frame)
        cc_layout.addWidget(self._server_frame)
        self._server_frame.hide()

        layout.addWidget(content_card, stretch=1)

        self._server_thread = None

    # ── Client UI ──

    def _build_client_ui(self, parent):
        fl = QVBoxLayout(parent)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(0)

        lb = QLabel("NTP 服务器")
        lb.setStyleSheet(H2_STYLE)
        fl.addWidget(lb)
        fl.addSpacing(6)

        row = QWidget()
        set_transparent_bg(row)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(10)

        self._server_entry = QLineEdit()
        self._server_entry.setText("ntp.aliyun.com")
        self._server_entry.setPlaceholderText("例如: ntp.aliyun.com")
        self._server_entry.setMinimumHeight(38)
        self._server_entry.returnPressed.connect(self._on_test)
        rl.addWidget(self._server_entry, stretch=1)

        self._test_btn = QPushButton("测试")
        self._test_btn.setStyleSheet(BTN_PRIMARY)
        self._test_btn.setFixedSize(90, 38)
        self._test_btn.clicked.connect(self._on_test)
        rl.addWidget(self._test_btn)

        fl.addWidget(row)
        fl.addSpacing(12)

        # Result output — dark styled text area (matching subnet calc summary style)
        rh = QLabel("查询结果")
        rh.setStyleSheet(H2_STYLE)
        fl.addWidget(rh)
        fl.addSpacing(6)

        self._result_output = QTableWidget(0, 3)
        self._result_output.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._result_output.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._result_output.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._result_output.horizontalHeader().setVisible(False)
        self._result_output.verticalHeader().setVisible(False)
        self._result_output.horizontalHeader().setStretchLastSection(True)
        self._result_output.setShowGrid(False)
        self._result_output.setStyleSheet("""
            QTableWidget {
                border: 1px solid #2c2c2c; border-radius: 8px;
                background: #202020; color: #e8e8e8;
                font-family: "Cascadia Code", "Consolas", "SF Mono", "Menlo", "Microsoft YaHei", "Courier New", monospace; font-size: 12px;
                padding: 4px;
            }
            QTableWidget::viewport { background: #202020; }
            QTableWidget::item { padding: 3px 8px; border: none; }
        """)
        self._result_output.setColumnWidth(0, 100)
        self._result_output.setColumnWidth(1, 20)
        self._result_output.setRowCount(1)
        placeholder = QTableWidgetItem("输入 NTP 服务器地址后点击测试...")
        placeholder.setForeground(QColor("#888888"))
        self._result_output.setItem(0, 0, placeholder)
        self._result_output.setSpan(0, 0, 1, 3)
        fl.addWidget(self._result_output, stretch=1)

    # ── Server UI ──

    def _build_server_ui(self, parent):
        fl = QVBoxLayout(parent)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(0)

        lb = QLabel("服务配置")
        lb.setStyleSheet(H2_STYLE)
        fl.addWidget(lb)
        fl.addSpacing(8)

        pr = QWidget()
        set_transparent_bg(pr)
        prl = QHBoxLayout(pr)
        prl.setContentsMargins(0, 0, 0, 0)
        prl.setSpacing(10)

        pl = QLabel("监听端口:")
        pl.setStyleSheet(BODY_STYLE)
        prl.addWidget(pl)

        self._port_entry = QLineEdit()
        self._port_entry.setText("123")
        self._port_entry.setFixedWidth(100)
        self._port_entry.setMinimumHeight(36)
        prl.addWidget(self._port_entry)

        ph = QLabel("(1024 以下端口需要管理员权限)")
        ph.setStyleSheet(HINT_STYLE)
        prl.addWidget(ph)
        prl.addStretch(1)
        fl.addWidget(pr)

        # Toggle row
        br = QWidget()
        set_transparent_bg(br)
        brl = QHBoxLayout(br)
        brl.setContentsMargins(0, 0, 0, 0)
        brl.setSpacing(15)
        fl.addSpacing(12)
        fl.addWidget(br)

        self._toggle_btn = QPushButton("启动服务")
        self._toggle_btn.setStyleSheet(BTN_PRIMARY)
        self._toggle_btn.setFixedSize(120, 38)
        self._toggle_btn.clicked.connect(self._toggle)
        brl.addWidget(self._toggle_btn)

        self._status_label = QLabel("状态: 已停止")
        self._status_label.setStyleSheet(BODY_STYLE)
        brl.addWidget(self._status_label)
        brl.addStretch(1)

        # Log area
        fl.addSpacing(12)
        ll = QLabel("运行日志")
        ll.setStyleSheet(H2_STYLE)
        fl.addWidget(ll)
        fl.addSpacing(8)

        self._log_text = QPlainTextEdit()
        self._log_text.setReadOnly(True)
        set_dark_output(self._log_text)
        fl.addWidget(self._log_text, stretch=1)

    # ── Mode switching ──

    def _set_mode(self, mode):
        self._update_mode_buttons(mode)
        if mode == "client":
            self._client_frame.show()
            self._server_frame.hide()
        else:
            self._client_frame.hide()
            self._server_frame.show()

    def _update_mode_buttons(self, val=None):
        if val is None:
            return
        for v, btn in self._mode_btns.items():
            if v == val:
                btn.setStyleSheet(BTN_MODE_ACTIVE)
            else:
                btn.setStyleSheet(BTN_MODE_INACTIVE)

    # ── Client actions ──

    def _on_test(self):
        server = self._server_entry.text().strip()
        if not server:
            QMessageBox.warning(self.app, "提示", "请输入 NTP 服务器地址")
            return
        self._test_btn.setEnabled(False)
        self._test_btn.setText("测试中...")
        self._clear_results()
        msg = QTableWidgetItem("查询中，请稍候...")
        msg.setForeground(QColor("#888888"))
        self._result_output.setItem(0, 0, msg)
        self._result_output.setSpan(0, 0, 1, 3)
        threading.Thread(target=self._do_query, args=(server,), daemon=True).start()

    def _do_query(self, server):
        logger.info(f"[NTP客户端] 开始查询: {server}")
        try:
            result = _query_ntp(server)
            try:
                bj = _query_ntp("cn.pool.ntp.org", timeout=3)
                result["beijing_time"] = bj["server_time"]
            except Exception:
                result["beijing_time"] = result["server_time"]
            logger.info(f"[NTP客户端] 查询成功: {server} (rtt={result['rtt']*1000:.1f}ms, offset={result['offset']*1000:.1f}ms)")
            self.app.after(0, self._show_success, result)
        except socket.timeout:
            logger.warning(f"[NTP客户端] 查询超时: {server}")
            self.app.after(0, self._show_error, "连接超时，请检查网络或服务器地址")
        except socket.gaierror:
            logger.error(f"[NTP客户端] DNS 解析失败: {server}")
            self.app.after(0, self._show_error, "无法解析服务器地址，请检查输入")
        except Exception as e:
            logger.exception(f"[NTP客户端] 查询异常: {server}")
            self.app.after(0, self._show_error, f"查询失败: {e}")

    def _show_success(self, r):
        st = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["server_time"]))
        lt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["local_time"]))
        bt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["beijing_time"]))
        off = r["offset"] * 1000

        if abs(r["offset"]) < 0.001:
            conclusion = "本地时钟与服务器同步良好。"
        elif r["offset"] > 0:
            conclusion = f"本地时钟慢了约 {r['offset']:.6f} 秒，建议调快。"
        else:
            conclusion = f"本地时钟快了约 {-r['offset']:.6f} 秒，建议调慢。"

        rows = [
            ("服务器",     ":", r["server_ip"]),
            ("状态",       ":", "成功"),
            ("服务器时间", ":", f"{st} (UTC+8)"),
            ("北京时间",   ":", f"{bt} (UTC+8)"),
            ("本地时间",   ":", f"{lt} (UTC+8)"),
            ("往返时延",   ":", f"{r['rtt']*1000:.3f} ms"),
            ("时间偏移",   ":", f"{off:+.3f} ms"),
            ("结论",       ":", conclusion),
        ]
        tbl = self._result_output
        tbl.clear()
        tbl.clearSpans()
        tbl.setRowCount(len(rows))
        col_color = QColor("#e0e0e0")
        for i, (label, colon, val) in enumerate(rows):
            li = QTableWidgetItem(label)
            li.setTextAlignment(Qt.AlignmentFlag.AlignJustify | Qt.AlignmentFlag.AlignVCenter)
            li.setForeground(col_color)
            tbl.setItem(i, 0, li)

            ci = QTableWidgetItem(colon)
            ci.setForeground(col_color)
            tbl.setItem(i, 1, ci)

            vi = QTableWidgetItem(val)
            vi.setForeground(col_color)
            tbl.setItem(i, 2, vi)
        tbl.resizeRowsToContents()
        tbl.resizeColumnToContents(0)
        self._test_btn.setEnabled(True)
        self._test_btn.setText("测试")

    def _show_error(self, msg):
        tbl = self._result_output
        tbl.clear()
        tbl.clearSpans()
        tbl.setRowCount(1)
        err = QTableWidgetItem(f"查询失败\n{msg}")
        err.setForeground(QColor("#dc2626"))
        tbl.setItem(0, 0, err)
        tbl.setSpan(0, 0, 1, 3)
        self._test_btn.setEnabled(True)
        self._test_btn.setText("测试")

    def _clear_results(self):
        self._result_output.clear()
        self._result_output.clearSpans()
        self._result_output.setRowCount(0)
        logger.info("[NTP客户端] 清空查询结果")

    # ── Server actions ──

    def _toggle(self):
        if self._server_thread and not self._server_thread.stop_event.is_set():
            self._stop()
        else:
            self._start()

    def _start(self):
        port_str = self._port_entry.text().strip()
        if not port_str.isdigit() or not (1 <= int(port_str) <= 65535):
            QMessageBox.warning(self.app, "提示", "请输入有效的端口号 (1-65535)")
            return
        logger.info(f"[NTP服务器] 启动服务, 端口: {port_str}")
        self._log_clear()
        self._log_text.appendPlainText(f"正在启动 NTP 服务器，端口 {port_str} ...")
        # Thread-safe log queue
        self._srv_queue = queue.Queue()
        self._srv_timer = QTimer()
        self._srv_timer.timeout.connect(self._drain_srv_queue)
        self._srv_timer.start(100)
        self._server_thread = _NTPServerThread(int(port_str), self._srv_queue)
        self._server_thread.start()
        self._log_text.appendPlainText("服务器线程已启动，等待绑定...")
        self._toggle_btn.setText("停止服务")
        self._toggle_btn.setStyleSheet(BTN_DANGER)
        self._status_label.setText("状态: 运行中")
        self._status_label.setStyleSheet(BODY_STYLE + " color: #11a37f;")
        self._port_entry.setEnabled(False)

    def _drain_srv_queue(self):
        while not self._srv_queue.empty():
            try:
                text = self._srv_queue.get_nowait()
                self._log_text.setReadOnly(False)
                self._log_text.appendPlainText(text)
                if "[错误]" in text:
                    logger.error(f"[NTP服务器] {text}")
                elif "[提示]" in text or "[信息]" in text:
                    logger.info(f"[NTP服务器] {text}")
                else:
                    logger.info(f"[NTP服务器] {text}")
                sb = self._log_text.verticalScrollBar()
                sb.setValue(sb.maximum())
                self._log_text.setReadOnly(True)
            except queue.Empty:
                break

    def _stop(self):
        logger.info("[NTP服务器] 停止服务")
        if self._server_thread:
            self._server_thread.stop()
            self._server_thread = None
        # Drain remaining queue messages before stopping timer
        if hasattr(self, '_srv_queue'):
            import time as _t
            _t.sleep(0.3)  # Let thread finish writing "[停止]"
            self._drain_srv_queue()
        if hasattr(self, '_srv_timer'):
            self._srv_timer.stop()
        self._toggle_btn.setText("启动服务")
        self._toggle_btn.setStyleSheet(BTN_PRIMARY)
        self._status_label.setText("状态: 已停止")
        self._status_label.setStyleSheet(BODY_STYLE)
        self._port_entry.setEnabled(True)

    def _log(self, text):
        QTimer.singleShot(0, lambda t=text: self._log_safe(t))

    def _log_safe(self, text):
        self._log_text.setReadOnly(False)
        self._log_text.appendPlainText(text)
        sb = self._log_text.verticalScrollBar()
        sb.setValue(sb.maximum())
        self._log_text.setReadOnly(True)

    def _log_clear(self):
        self._log_text.setReadOnly(False)
        self._log_text.clear()
        self._log_text.setReadOnly(True)
        logger.info("[NTP服务器] 清空运行日志")
