"""
NetTool - Network Toolbox
Version: V100R008C00SPC600
Author: Tang Wenbo (HCIE-Datacom)
Copyright (C) 2026 Tang Wenbo
License: GNU General Public License v3.0 or later

Pure Python TCP/UDP bandwidth test module.
"""

import socket
import struct
import time
import threading

from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QPlainTextEdit, QComboBox, QMessageBox,
)
from PySide6.QtCore import Qt

from core.base_module import ToolModule
from core.app import BTN_PRIMARY, BTN_DANGER, BTN_SECONDARY, BTN_MODE_ACTIVE, BTN_MODE_INACTIVE, set_card_style, set_transparent_bg, set_dark_output
from core.app import H1_STYLE, H2_STYLE, H3_STYLE, BODY_STYLE, HINT_STYLE, DESC_STYLE
from core.logger import logger



class IperfToolModule(ToolModule):
    name = "iPerf 带宽测试"
    icon = "iperf"
    description = "纯 Python TCP/UDP 带宽测试工具，支持客户端和服务器模式，多流并发测试。"

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

        self._mode_btns = {}
        mb_wrapper = QWidget()
        mb_wrapper.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        mb_wrapper.setStyleSheet(
            "background: #eef0f2; border: 1px solid #e2e5e9; border-radius: 8px;"
        )
        mbl = QHBoxLayout(mb_wrapper)
        mbl.setContentsMargins(4, 4, 4, 4)
        mbl.setSpacing(4)
        for val, text in [("client", "客户端"), ("server", "服务器")]:
            btn = QPushButton(text)
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, v=val: self._set_mode(v))
            mbl.addWidget(btn, stretch=1)
            self._mode_btns[val] = btn
        self._update_mode_buttons("client")
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

        layout.addWidget(content_card)

        # Output card
        out_card = QFrame()
        set_card_style(out_card)
        oc_layout = QVBoxLayout(out_card)
        oc_layout.setContentsMargins(15, 12, 15, 12)

        ol = QLabel("测试结果")
        ol.setStyleSheet(H2_STYLE)
        oc_layout.addWidget(ol)
        oc_layout.addSpacing(6)

        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        set_dark_output(self._output)
        oc_layout.addWidget(self._output, stretch=1)

        layout.addSpacing(15)
        layout.addWidget(out_card, stretch=1)

        self._running = False
        self._stop_event = threading.Event()

    def _build_client_ui(self, parent):
        fl = QVBoxLayout(parent)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(6)

        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        fl.addLayout(grid)

        # Row 0: Server address
        grid.addWidget(self._lbl("服务器地址"), 0, 0)
        self._host_entry = QLineEdit("127.0.0.1")
        self._host_entry.setMinimumHeight(32)
        grid.addWidget(self._host_entry, 0, 1)

        # Row 1: Port + Protocol
        grid.addWidget(self._lbl("端口"), 1, 0)
        pp_row = QWidget()
        set_transparent_bg(pp_row)
        ppl = QHBoxLayout(pp_row)
        ppl.setContentsMargins(0, 0, 0, 0)
        ppl.setSpacing(12)
        self._port_entry = QLineEdit("5201")
        self._port_entry.setFixedWidth(80)
        self._port_entry.setMinimumHeight(32)
        ppl.addWidget(self._port_entry)

        ppl.addWidget(self._lbl("协议"))
        self._proto_combo = QComboBox()
        self._proto_combo.addItems(["TCP", "UDP"])
        self._proto_combo.setFixedWidth(80)
        self._proto_combo.setFixedHeight(30)
        self._proto_combo.currentTextChanged.connect(self._on_proto_change)
        ppl.addWidget(self._proto_combo)
        ppl.addStretch(1)
        grid.addWidget(pp_row, 1, 1)

        # Row 2: Duration + Streams
        grid.addWidget(self._lbl("时长(秒)"), 2, 0)
        ds_row = QWidget()
        set_transparent_bg(ds_row)
        dsl = QHBoxLayout(ds_row)
        dsl.setContentsMargins(0, 0, 0, 0)
        dsl.setSpacing(12)
        self._duration_entry = QLineEdit("60")
        self._duration_entry.setFixedWidth(80)
        self._duration_entry.setMinimumHeight(32)
        dsl.addWidget(self._duration_entry)

        dsl.addWidget(self._lbl("并行流"))
        self._streams_entry = QLineEdit("1")
        self._streams_entry.setFixedWidth(80)
        self._streams_entry.setMinimumHeight(32)
        dsl.addWidget(self._streams_entry)
        dsl.addStretch(1)
        grid.addWidget(ds_row, 2, 1)

        # Row 3: Buffer
        grid.addWidget(self._lbl("缓冲(KB)"), 3, 0)
        self._buffer_entry = QLineEdit("128")
        self._buffer_entry.setFixedWidth(80)
        self._buffer_entry.setMinimumHeight(32)
        grid.addWidget(self._buffer_entry, 3, 1)

        # UDP row
        self._udp_row = QWidget()
        set_transparent_bg(self._udp_row)
        udpl = QHBoxLayout(self._udp_row)
        udpl.setContentsMargins(0, 0, 0, 0)
        udpl.setSpacing(8)
        udpl.addWidget(self._lbl("UDP带宽(Mbps)"))
        self._bw_entry = QLineEdit("1")
        self._bw_entry.setFixedWidth(80)
        self._bw_entry.setMinimumHeight(32)
        udpl.addWidget(self._bw_entry)
        udpl.addStretch(1)
        grid.addWidget(self._udp_row, 4, 0, 1, 2)
        self._udp_row.hide()

        # Buttons
        btn_row = QWidget()
        set_transparent_bg(btn_row)
        brl = QHBoxLayout(btn_row)
        brl.setContentsMargins(0, 0, 0, 0)
        brl.setSpacing(8)
        fl.addSpacing(8)
        fl.addWidget(btn_row)

        self._start_btn = QPushButton("开始测试")
        self._start_btn.setStyleSheet(BTN_PRIMARY)
        self._start_btn.setFixedSize(100, 34)
        self._start_btn.clicked.connect(self._start_client)
        brl.addWidget(self._start_btn)

        self._stop_btn = QPushButton("停止")
        self._stop_btn.setStyleSheet(BTN_DANGER)
        self._stop_btn.setFixedSize(80, 34)
        self._stop_btn.clicked.connect(self._stop)
        self._stop_btn.setEnabled(False)
        brl.addWidget(self._stop_btn)
        brl.addStretch(1)

    def _build_server_ui(self, parent):
        fl = QVBoxLayout(parent)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(6)

        grid = QGridLayout()
        fl.addLayout(grid)
        grid.setColumnStretch(1, 1)

        grid.addWidget(self._lbl("绑定地址"), 0, 0)
        self._srv_bind_entry = QLineEdit("0.0.0.0")
        self._srv_bind_entry.setMinimumHeight(32)
        grid.addWidget(self._srv_bind_entry, 0, 1)

        grid.addWidget(self._lbl("端口"), 1, 0)
        self._srv_port_entry = QLineEdit("5201")
        self._srv_port_entry.setFixedWidth(80)
        self._srv_port_entry.setMinimumHeight(32)
        grid.addWidget(self._srv_port_entry, 1, 1)

        btn_row = QWidget()
        set_transparent_bg(btn_row)
        brl = QHBoxLayout(btn_row)
        brl.setContentsMargins(0, 0, 0, 0)
        brl.setSpacing(8)
        fl.addSpacing(8)
        fl.addWidget(btn_row)

        self._srv_start_btn = QPushButton("启动服务器")
        self._srv_start_btn.setStyleSheet(BTN_PRIMARY)
        self._srv_start_btn.setFixedSize(100, 34)
        self._srv_start_btn.clicked.connect(self._start_server)
        brl.addWidget(self._srv_start_btn)

        self._srv_stop_btn = QPushButton("停止")
        self._srv_stop_btn.setStyleSheet(BTN_DANGER)
        self._srv_stop_btn.setFixedSize(80, 34)
        self._srv_stop_btn.clicked.connect(self._stop)
        self._srv_stop_btn.setEnabled(False)
        brl.addWidget(self._srv_stop_btn)
        brl.addStretch(1)

    def _lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet(BODY_STYLE)
        return l

    # ── Mode ──

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

    def _on_proto_change(self, proto):
        if proto == "UDP":
            self._udp_row.show()
        else:
            self._udp_row.hide()

    # ── Output ──

    def _append_output(self, text):
        self._output.appendPlainText(text)
        sb = self._output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear_output(self):
        self._output.clear()

    def _finish(self):
        self._running = False
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._srv_start_btn.setEnabled(True)
        self._srv_stop_btn.setEnabled(False)

    def _stop(self):
        if not self._running:
            return
        logger.info("[iPerf] 用户停止测试/服务器")
        self._stop_event.set()
        self._append_output("[INFO] 正在停止...")

    # ── Validation ──

    def _validate_port(self, s, title="端口"):
        if not s.isdigit() or not (1 <= int(s) <= 65535):
            QMessageBox.warning(self.app, "提示", f"请输入有效的{title}号 (1-65535)")
            return None
        return int(s)

    def _validate_int_range(self, s, lo, hi, name):
        if not s.isdigit() or not (lo <= int(s) <= hi):
            QMessageBox.warning(self.app, "提示", f"{name}范围为 {lo}-{hi}")
            return None
        return int(s)

    # ── Client ──

    def _start_client(self):
        if self._running:
            return

        host = self._host_entry.text().strip()
        port = self._validate_port(self._port_entry.text().strip())
        if port is None:
            return
        duration = self._validate_int_range(self._duration_entry.text().strip(), 1, 9999, "测试时长(秒)")
        if duration is None:
            return
        streams = self._validate_int_range(self._streams_entry.text().strip(), 1, 10, "并行流数量")
        if streams is None:
            return

        try:
            buf_kb = int(self._buffer_entry.text().strip())
            if buf_kb < 1 or buf_kb > 1024:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self.app, "提示", "缓冲区大小为 1-1024 KB")
            return

        proto = self._proto_combo.currentText()
        bw_mbps = 0
        if proto == "UDP":
            try:
                bw_mbps = float(self._bw_entry.text())
                if bw_mbps <= 0:
                    raise ValueError
            except ValueError:
                QMessageBox.warning(self.app, "提示", "请输入有效的 UDP 目标带宽")
                return

        self._running = True
        self._stop_event.clear()
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._clear_output()

        self._append_output(f"[INFO] 连接到 {host}:{port}，协议: {proto}")
        if streams > 1:
            self._append_output(f"[INFO] 并行流: {streams}，缓冲: {buf_kb} KB")
        self._append_output("-" * 50)
        logger.info(
            f"[iPerf客户端] 开始测试: proto={proto}, host={host}, port={port}, "
            f"duration={duration}, streams={streams}, buffer_kb={buf_kb}, udp_bw={bw_mbps or '-'}"
        )

        if proto == "TCP":
            threading.Thread(target=self._run_tcp_client,
                             args=(host, port, duration, streams, buf_kb * 1024), daemon=True).start()
        else:
            threading.Thread(target=self._run_udp_client,
                             args=(host, port, duration, streams, buf_kb * 1024, bw_mbps), daemon=True).start()

    # ── Server ──

    def _start_server(self):
        if self._running:
            return
        bind_addr = self._srv_bind_entry.text().strip() or "0.0.0.0"
        port = self._validate_port(self._srv_port_entry.text().strip())
        if port is None:
            return

        self._running = True
        self._stop_event.clear()
        self._srv_start_btn.setEnabled(False)
        self._srv_stop_btn.setEnabled(True)
        self._clear_output()
        self._append_output(f"[INFO] 启动服务器: {bind_addr}:{port}")
        self._append_output("[INFO] 等待客户端连接...")
        self._append_output("-" * 50)
        logger.info(f"[iPerf服务器] 启动请求: bind={bind_addr}, port={port}")

        threading.Thread(target=self._run_server, args=(bind_addr, port), daemon=True).start()

    # ══════════════ TCP Client (unchanged business logic) ══════════════

    def _run_tcp_client(self, host, port, duration, streams, buf_size):
        total_bytes = 0
        start_time = time.time()
        last_report = start_time
        last_bytes = 0

        def do_stream(stream_id):
            nonlocal total_bytes, last_report, last_bytes
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                sock.connect((host, port))
                header = struct.pack("!II", stream_id, 0)
                payload = header + b"\x00" * (buf_size - len(header))
                while not self._stop_event.is_set() and time.time() - start_time < duration:
                    try:
                        header = struct.pack("!II", stream_id, 0)
                        payload = header + b"\x00" * (buf_size - len(header))
                        sock.sendall(payload)
                        total_bytes += buf_size
                        now = time.time()
                        if now - last_report >= 1.0:
                            bw = (total_bytes - last_bytes) * 8 / (now - last_report) / 1e6
                            elapsed = int(now - start_time)
                            self.app.after(0, self._append_output,
                                           f"  [{elapsed:2d}] {elapsed-1:.0f}-{elapsed:.0f} sec  带宽: {bw:7.1f} Mbps")
                            last_report = now
                            last_bytes = total_bytes
                    except socket.timeout:
                        continue
                    except (BrokenPipeError, ConnectionResetError):
                        break
                sock.close()
            except Exception as e:
                self.app.after(0, self._append_output, f"[ERROR] TCP流{stream_id}: {e}")
                logger.exception(f"[iPerf客户端] TCP 流异常: stream={stream_id}, host={host}, port={port}")

        threads = [threading.Thread(target=do_stream, args=(sid,), daemon=True) for sid in range(streams)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        elapsed = time.time() - start_time
        if elapsed > 0:
            avg_bw = total_bytes * 8 / elapsed / 1e6
            total_mb = total_bytes / 1e6
            self.app.after(0, self._append_output, "-" * 50)
            self.app.after(0, self._append_output,
                           f"总计: {total_mb:.1f} MB  时长: {elapsed:.1f} 秒  平均带宽: {avg_bw:.1f} Mbps")
            logger.info(f"[iPerf客户端] TCP {host}:{port} {elapsed:.1f}s {avg_bw:.1f}Mbps")
        self.app.after(0, self._finish)

    # ══════════════ UDP Client (unchanged business logic) ══════════════

    def _run_udp_client(self, host, port, duration, streams, buf_size, bw_mbps):
        total_bytes = 0
        total_packets = 0
        start_time = time.time()
        last_report = start_time
        last_bytes = 0

        bits_per_second = bw_mbps * 1e6
        bytes_per_second = bits_per_second / 8
        packets_per_second = bytes_per_second / buf_size
        interval = 1.0 / max(packets_per_second, 1)
        if interval < 0.0001:
            interval = 0.0001

        def do_stream(stream_id):
            nonlocal total_bytes, last_report, last_bytes, total_packets
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(0.1)
                seq = 0
                while not self._stop_event.is_set() and time.time() - start_time < duration:
                    ts = time.time()
                    header = struct.pack("!IId", stream_id, seq, ts)
                    data = header + b"\x00" * max(0, buf_size - len(header))
                    try:
                        sock.sendto(data, (host, port))
                        total_bytes += len(data)
                        total_packets += 1
                        seq += 1
                    except socket.timeout:
                        continue
                    now = time.time()
                    if now - last_report >= 1.0:
                        bw = (total_bytes - last_bytes) * 8 / (now - last_report) / 1e6
                        elapsed = int(now - start_time)
                        self.app.after(0, self._append_output,
                                       f"  [{elapsed:2d}] {elapsed-1:.0f}-{elapsed:.0f} sec  带宽: {bw:7.1f} Mbps")
                        last_report = now
                        last_bytes = total_bytes
                    time.sleep(interval / streams)
                sock.close()
            except Exception as e:
                self.app.after(0, self._append_output, f"[ERROR] UDP流{stream_id}: {e}")
                logger.exception(f"[iPerf客户端] UDP 流异常: stream={stream_id}, host={host}, port={port}")

        threads = [threading.Thread(target=do_stream, args=(sid,), daemon=True) for sid in range(streams)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        elapsed = time.time() - start_time
        if elapsed > 0:
            avg_bw = total_bytes * 8 / elapsed / 1e6
            total_mb = total_bytes / 1e6
            self.app.after(0, self._append_output, "-" * 50)
            self.app.after(0, self._append_output,
                           f"发送: {total_mb:.1f} MB  {total_packets} 数据报  时长: {elapsed:.1f} 秒  平均带宽: {avg_bw:.1f} Mbps")
            logger.info(f"[iPerf客户端] UDP {host}:{port} {elapsed:.1f}s {avg_bw:.1f}Mbps {total_packets}pkts")
        self.app.after(0, self._finish)

    # ══════════════ Server (unchanged business logic) ══════════════

    def _run_server(self, bind_addr, port):
        tcp_sock = None
        udp_sock = None
        start_time = time.time()
        tcp_bytes = [0]
        udp_bytes = [0]
        udp_packets = [0]
        udp_lost = [0]

        try:
            tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            tcp_sock.settimeout(0.5)
            tcp_sock.bind((bind_addr, port))
            tcp_sock.listen(5)

            udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp_sock.settimeout(0.5)
            udp_sock.bind((bind_addr, port))

            self.app.after(0, self._append_output, f"[INFO] 服务器已启动，监听 TCP+UDP :{port}")
            logger.info(f"[iPerf服务器] 已启动: bind={bind_addr}, port={port}")

            last_report = [start_time]
            last_tcp = [0]
            last_udp = [0]

            def handle_tcp(client_sock, addr):
                try:
                    client_sock.settimeout(0.5)
                    while not self._stop_event.is_set():
                        try:
                            data = client_sock.recv(65536)
                            if not data:
                                break
                            tcp_bytes[0] += len(data)
                        except socket.timeout:
                            continue
                except Exception:
                    pass
                finally:
                    try:
                        client_sock.close()
                    except Exception:
                        pass

            def handle_udp():
                last_seq = -1
                seq_base = -1
                while not self._stop_event.is_set():
                    try:
                        data, addr = udp_sock.recvfrom(65536)
                        udp_bytes[0] += len(data)
                        udp_packets[0] += 1
                        if len(data) >= 4:
                            seq = struct.unpack("!I", data[:4])[0]
                            if seq_base < 0:
                                seq_base = seq
                            elif last_seq >= 0 and seq != last_seq + 1:
                                udp_lost[0] += max(0, seq - last_seq - 1)
                            last_seq = seq
                    except socket.timeout:
                        continue

            def report_loop():
                while not self._stop_event.is_set():
                    time.sleep(1.0)
                    now = time.time()
                    if now - last_report[0] >= 1.0:
                        tcp_bw = (tcp_bytes[0] - last_tcp[0]) * 8 / (now - last_report[0]) / 1e6
                        udp_bw = (udp_bytes[0] - last_udp[0]) * 8 / (now - last_report[0]) / 1e6
                        elapsed = int(now - start_time)
                        line = f"  [{elapsed:2d}] TCP: {tcp_bw:7.1f} Mbps  |  UDP: {udp_bw:7.1f} Mbps"
                        if udp_lost[0] > 0:
                            line += f"  丢包: {udp_lost[0]}"
                        self.app.after(0, self._append_output, line)
                        last_report[0] = now
                        last_tcp[0] = tcp_bytes[0]
                        last_udp[0] = udp_bytes[0]

            udp_thread = threading.Thread(target=handle_udp, daemon=True)
            udp_thread.start()
            reporter = threading.Thread(target=report_loop, daemon=True)
            reporter.start()

            while not self._stop_event.is_set():
                try:
                    client_sock, addr = tcp_sock.accept()
                    self.app.after(0, self._append_output, f"[INFO] TCP 客户端连接: {addr[0]}:{addr[1]}")
                    logger.info(f"[iPerf服务器] TCP 客户端连接: {addr[0]}:{addr[1]}")
                    t = threading.Thread(target=handle_tcp, args=(client_sock, addr), daemon=True)
                    t.start()
                except socket.timeout:
                    continue

        except Exception as e:
            self.app.after(0, self._append_output, f"[ERROR] 服务器异常: {e}")
            logger.error(f"[iPerf服务器] {bind_addr}:{port} 异常: {e}")
        finally:
            elapsed = time.time() - start_time
            if tcp_bytes[0] > 0 or udp_bytes[0] > 0:
                tcp_mb = tcp_bytes[0] / 1e6
                udp_mb = udp_bytes[0] / 1e6
                self.app.after(0, self._append_output, "-" * 50)
                self.app.after(0, self._append_output,
                               f"TCP 接收: {tcp_mb:.1f} MB  |  UDP 接收: {udp_mb:.1f} MB  {udp_packets[0]} 包")
                if elapsed > 0:
                    tcp_avg = tcp_bytes[0] * 8 / elapsed / 1e6
                    udp_avg = udp_bytes[0] * 8 / elapsed / 1e6
                    self.app.after(0, self._append_output,
                                   f"平均带宽: TCP {tcp_avg:.1f} Mbps  |  UDP {udp_avg:.1f} Mbps")
                if udp_lost[0] > 0:
                    loss_pct = udp_lost[0] / max(udp_packets[0] + udp_lost[0], 1) * 100
                    self.app.after(0, self._append_output, f"UDP 丢包: {udp_lost[0]} ({loss_pct:.1f}%)")
            else:
                self.app.after(0, self._append_output, "[INFO] 服务器已停止，无数据传输")

            logger.info(f"[iPerf服务器] {bind_addr}:{port} 已停止")
            for s in (tcp_sock, udp_sock):
                if s:
                    try:
                        s.close()
                    except Exception:
                        pass
            self.app.after(0, self._finish)
