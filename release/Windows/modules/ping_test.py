"""
NetTool - Network Toolbox
Version: V100R008C00SPC600
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

try:
    import ping3
    HAS_PING3 = True
except ImportError:
    HAS_PING3 = False

from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QPlainTextEdit, QMessageBox,
)
from PySide6.QtCore import Qt

from core.base_module import ToolModule
from core.app import BTN_PRIMARY, BTN_DANGER, BTN_SECONDARY, BTN_MODE_ACTIVE, BTN_MODE_INACTIVE, set_card_style, set_transparent_bg, set_dark_output
from core.app import H1_STYLE, H2_STYLE, H3_STYLE, BODY_STYLE, HINT_STYLE, DESC_STYLE
from core.logger import logger



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
        self._target_entry.setPlaceholderText("例如: 8.8.8.8 或 www.baidu.com")
        self._target_entry.setMinimumHeight(38)
        self._target_entry.returnPressed.connect(self._start)
        trl.addWidget(self._target_entry, stretch=1)

        self._start_btn = QPushButton("开始")
        self._start_btn.setStyleSheet(BTN_PRIMARY)
        self._start_btn.setFixedSize(80, 38)
        self._start_btn.clicked.connect(self._start)
        trl.addWidget(self._start_btn)

        ic_layout.addWidget(target_row)
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

        oc_layout.addWidget(stats_widget)

        # Output area
        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        set_dark_output(self._output)
        oc_layout.addWidget(self._output, stretch=1)

        layout.addWidget(out_card, stretch=1)

        self._stop_event = threading.Event()
        self._popen = None

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

    def _set_mode(self, mode):
        self._current_mode = mode
        self._update_mode_buttons(mode)

    def _update_mode_buttons(self, val):
        for v, btn in self._mode_btns.items():
            if v == val:
                btn.setStyleSheet(BTN_MODE_ACTIVE)
            else:
                btn.setStyleSheet(BTN_MODE_INACTIVE)

    # ── Start / Stop ──

    def _start(self):
        target = self._target_entry.text().strip()
        if not target:
            QMessageBox.warning(self.app, "提示", "请输入目标地址")
            return

        # Determine mode
        mode = getattr(self, "_current_mode", "ping")

        try:
            count = int(self._count_entry.text().strip() or "4")
            port = int(self._port_entry.text().strip() or "80")
        except ValueError:
            logger.warning("[PING测试] 参数无效: 次数或端口不是数字")
            QMessageBox.warning(self.app, "提示", "次数和端口必须是数字")
            return
        logger.info(f"[PING测试] 开始: mode={mode}, target={target}, count={count}, port={port}")

        self._stop_event.clear()
        self._clear_output()
        self._stop_btn.setEnabled(True)
        self._start_btn.setEnabled(False)

        if mode == "ping":
            threading.Thread(target=self._run_ping, args=(target, count), daemon=True).start()
        elif mode == "tracert":
            threading.Thread(target=self._run_tracert, args=(target,), daemon=True).start()
        else:
            threading.Thread(target=self._run_tcping, args=(target, count, port), daemon=True).start()

    def _stop(self):
        logger.info("[PING测试] 用户停止测试")
        self._stop_event.set()
        if self._popen:
            try:
                self._popen.terminate()
                logger.info("[PING测试] 已终止 traceroute 子进程")
            except Exception:
                logger.exception("[PING测试] 终止子进程失败")

    def _finish(self):
        self.app.after(0, lambda: self._start_btn.setEnabled(True))
        self.app.after(0, lambda: self._stop_btn.setEnabled(False))

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

    def _run_ping(self, target, count):
        self.app.after(0, lambda: self._output.appendPlainText(
            f"--- Ping {target} ({count} 次) ---"))
        sent = recv = total_rtt = 0
        latencies = []
        try:
            for seq in range(count):
                if self._stop_event.is_set():
                    break
                sent += 1
                self.app.after(0, lambda s=sent: self._stats_sent.setText(str(s)))
                try:
                    if HAS_PING3:
                        rtt = ping3.ping(target, timeout=2, unit="ms")
                        if rtt is not None:
                            recv += 1
                            total_rtt += rtt
                            latencies.append(rtt)
                            line = f"Reply from {target}: time={rtt:.1f}ms"
                        else:
                            line = f"Request timed out."
                    else:
                        line = "ping3 not available"
                except Exception as e:
                    line = f"Error: {e}"

                self.app.after(0, lambda l=line: self._output.appendPlainText(l))
                self.app.after(0, lambda r=recv: self._stats_recv.setText(str(r)))
                if recv > 0:
                    avg = total_rtt / recv
                    loss = (1 - recv / sent) * 100
                    self.app.after(0, lambda a=avg: self._stats_avg.setText(f"{a:.1f} ms"))
                    self.app.after(0, lambda l=loss: self._stats_loss.setText(f"{l:.1f}%"))
                    self.app.after(0, lambda: self._stats_loss.setStyleSheet(
                        H2_STYLE + f" color: {'#27ae60' if loss < 10 else '#f59e0b' if loss < 50 else '#e74c3c'};"
                    ))

                if seq < count - 1 and not self._stop_event.is_set():
                    time.sleep(0.5)

        except Exception as e:
            logger.exception(f"[PING测试] Ping 异常: {target}")
            self.app.after(0, lambda: self._output.appendPlainText(f"Error: {e}"))
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
                self.app.after(0, lambda s=summary: self._output.appendPlainText(s))
                logger.info(f"[PING测试] Ping 完成: target={target}, {summary}")
            else:
                logger.info(f"[PING测试] Ping 结束: target={target}, 未发送请求")
            self._finish()

    # ── Traceroute ──

    def _run_tracert(self, target):
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
            self._popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           text=True, bufsize=1, startupinfo=si)
            line_count = 0
            for line in self._popen.stdout:
                if self._stop_event.is_set():
                    break
                line = line.strip()
                if line:
                    line_count += 1
                    self.app.after(0, lambda l=line: self._output.appendPlainText(l))
            self._popen.wait()
            logger.info(f"[PING测试] Tracert 完成: target={target}, returncode={self._popen.returncode}, lines={line_count}")
            if line_count == 0:
                self.app.after(0, lambda: self._output.appendPlainText(
                    "没有收到traceroute输出，请确认目标可达且网络正常"))
        except FileNotFoundError:
            logger.error("[PING测试] traceroute/tracert 命令不可用")
            self.app.after(0, lambda: self._output.appendPlainText(
                "traceroute 命令不可用，请确认系统已安装"))
        except Exception as e:
            logger.exception(f"[PING测试] Tracert 异常: {target}")
            self.app.after(0, lambda m=str(e): self._output.appendPlainText(
                f"traceroute 执行异常: {m}"))
        finally:
            self._popen = None
            self._finish()

    # ── TCPing ──

    def _run_tcping(self, target, count, port):
        self.app.after(0, lambda: self._output.appendPlainText(
            f"--- TCPing {target}:{port} ({count} 次) ---"))
        sent = recv = total_rtt = 0
        latencies = []
        for seq in range(count):
            if self._stop_event.is_set():
                break
            sent += 1
            self.app.after(0, lambda s=sent: self._stats_sent.setText(str(s)))
            start = time.time()
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect((target, port))
                rtt = (time.time() - start) * 1000
                sock.close()
                recv += 1
                total_rtt += rtt
                latencies.append(rtt)
                line = f"Connected to {target}:{port} time={rtt:.1f}ms"
            except socket.timeout:
                line = f"Connection to {target}:{port} timed out"
            except Exception as e:
                line = f"Error: {e}"

            self.app.after(0, lambda l=line: self._output.appendPlainText(l))
            self.app.after(0, lambda r=recv: self._stats_recv.setText(str(r)))
            if recv > 0:
                avg = total_rtt / recv
                loss = (1 - recv / sent) * 100
                self.app.after(0, lambda a=avg: self._stats_avg.setText(f"{a:.1f} ms"))
                self.app.after(0, lambda l=loss: self._stats_loss.setText(f"{l:.1f}%"))
                self.app.after(0, lambda: self._stats_loss.setStyleSheet(
                    H2_STYLE + f" color: {'#27ae60' if loss < 10 else '#f59e0b' if loss < 50 else '#e74c3c'};"
                ))

            if seq < count - 1 and not self._stop_event.is_set():
                time.sleep(0.3)

        if sent > 0 and recv > 0:
            mn, mx, avg = min(latencies), max(latencies), total_rtt / recv
            success_rate = recv / sent * 100
            summary = (f"--- 统计: 发送={sent}, 接收={recv}, "
                       f"成功率={success_rate:.1f}%, "
                       f"最小={mn:.1f}ms, 最大={mx:.1f}ms, 平均={avg:.1f}ms ---")
        elif sent > 0:
            summary = f"--- 统计: 发送={sent}, 接收={recv}, 目标不可达 ---"
        else:
            summary = ""
        if summary:
            self.app.after(0, lambda s=summary: self._output.appendPlainText(s))
            logger.info(f"[PING测试] TCPing 完成: target={target}:{port}, {summary}")
        else:
            logger.info(f"[PING测试] TCPing 结束: target={target}:{port}, 未发送请求")
        self._finish()

    # ── Output ──

    def _clear_output(self):
        logger.info("[PING测试] 清空输出")
        self._output.clear()
        self._stats_sent.setText("0")
        self._stats_recv.setText("0")
        self._stats_loss.setText("0%")
        self._stats_avg.setText("- ms")
        self._stats_loss.setStyleSheet(H2_STYLE)
