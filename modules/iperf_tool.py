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

"""iPerf bandwidth test - pure Python TCP/UDP throughput measurement."""

import socket
import struct
import threading
import time
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from core.base_module import ToolModule
from core.logger import logger


class IperfToolModule(ToolModule):
    """Pure Python iPerf bandwidth test with client and server modes."""

    name = "iPerf 带宽测试"
    icon = "📶"
    description = "纯 Python 实现的网络带宽测试工具，支持 TCP/UDP 客户端和服务器模式。"

    def build(self, parent):
        """Build the UI into the given parent CTkFrame."""

        def label(master, text, font=("Helvetica", -13), fg="#333333", **kw):
            return tk.Label(master, text=text, font=font, fg=fg,
                            bg="#f9f9f9", highlightthickness=0, bd=0, **kw)

        def white_label(master, text, font=("Helvetica", -13), fg="#333333", **kw):
            return tk.Label(master, text=text, font=font, fg=fg,
                            bg="white", highlightthickness=0, bd=0, **kw)

        self._running = False
        self._stop_event = threading.Event()

        # ── Title + Description ──
        label(parent, text=self.name,
              font=("Helvetica", -22, "bold"), fg="#1f1f1f").pack(anchor="w", pady=(0, 5))
        label(parent, text=self.description,
              font=("Helvetica", -13), fg="#6b6b6b",
              wraplength=620, justify="left").pack(anchor="w", pady=(0, 15))

        # ── Mode Card ──
        mode_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                 border_width=1, border_color="#e5e5e5")
        mode_card.pack(fill="x", pady=(0, 15))
        mode_inner = ctk.CTkFrame(mode_card, fg_color="transparent")
        mode_inner.pack(fill="x", padx=15, pady=12)

        self._mode_var = ctk.StringVar(value="client")
        mode_btn_frame = ctk.CTkFrame(mode_inner, fg_color="#f0f0f0", corner_radius=8)
        mode_btn_frame.pack(fill="x")
        self._mode_btns = {}
        for val, label_text in [("client", "客户端"), ("server", "服务器")]:
            btn = ctk.CTkButton(mode_btn_frame, text=label_text, width=0, height=28,
                                font=("Helvetica", 11), corner_radius=6,
                                fg_color="transparent", text_color="#333333",
                                hover_color="#e0e0e0",
                                command=lambda v=val: self._set_mode(v))
            btn.pack(side="left", expand=True, fill="x", padx=2, pady=2)
            self._mode_btns[val] = btn
        self._update_mode_buttons()

        # ── Content Card (hosts both client and server frames) ──
        content_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                    border_width=1, border_color="#e5e5e5")
        content_card.pack(fill="x", pady=(0, 15))

        self._client_frame = ctk.CTkFrame(content_card, fg_color="transparent")
        self._server_frame = ctk.CTkFrame(content_card, fg_color="transparent")
        self._build_client_ui(self._client_frame)
        self._build_server_ui(self._server_frame)
        self._client_frame.pack(fill="x", padx=15, pady=15)

        # ── Output Card ──
        out_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                border_width=1, border_color="#e5e5e5")
        out_card.pack(fill="both", expand=True)
        out_inner = ctk.CTkFrame(out_card, fg_color="transparent")
        out_inner.pack(fill="both", expand=True, padx=15, pady=15)

        white_label(out_inner, text="测试结果",
                    font=("Helvetica", -14, "bold"), fg="#1f1f1f").pack(anchor="w", pady=(0, 8))

        self._output = ctk.CTkTextbox(out_inner, font=("Courier", 13), corner_radius=8,
                                      fg_color="#1e1e1e", text_color="#e0e0e0",
                                      border_width=1, border_color="#e5e5e5")
        self._output.pack(fill="both", expand=True)

    # ── Client UI ──

    def _build_client_ui(self, parent):
        def wl(master, text, font=("Helvetica", -12), fg="#333333", **kw):
            return tk.Label(master, text=text, font=font, fg=fg,
                            bg="white", highlightthickness=0, bd=0, **kw)

        # Use a grid layout aligned to the left, matching other modules' style
        grid = ctk.CTkFrame(parent, fg_color="transparent")
        grid.pack(anchor="w", fill="x")
        grid.grid_columnconfigure(1, weight=1)

        # Row 1: Server address
        wl(grid, text="服务器地址").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self._host_var = ctk.StringVar(value="127.0.0.1")
        ctk.CTkEntry(grid, textvariable=self._host_var, font=("Helvetica", 12),
                     width=160, height=32, corner_radius=6,
                     border_color="#d1d5db", border_width=1).grid(row=0, column=1, sticky="w", pady=(0, 8), padx=(8, 0))

        # Row 2: Port + Protocol
        wl(grid, text="端口").grid(row=1, column=0, sticky="w", pady=(0, 8))
        port_proto = ctk.CTkFrame(grid, fg_color="transparent")
        port_proto.grid(row=1, column=1, sticky="w", pady=(0, 8), padx=(8, 0))
        self._port_var = ctk.StringVar(value="5201")
        ctk.CTkEntry(port_proto, textvariable=self._port_var, font=("Helvetica", 12),
                     width=80, height=32, corner_radius=6,
                     border_color="#d1d5db", border_width=1).pack(side="left")
        wl(port_proto, text="协议").pack(side="left", padx=(16, 4))
        self._proto_var = ctk.StringVar(value="TCP")
        ctk.CTkOptionMenu(port_proto, variable=self._proto_var, values=["TCP", "UDP"],
                          font=("Helvetica", 11), width=80, height=28,
                          corner_radius=6, fg_color="#f0f0f0",
                          text_color="#333333", button_color="#e0e0e0",
                          button_hover_color="#d0d0d0",
                          command=self._on_proto_change).pack(side="left")

        # Row 3: Duration + Streams
        wl(grid, text="时长(秒)").grid(row=2, column=0, sticky="w", pady=(0, 8))
        dur_stream = ctk.CTkFrame(grid, fg_color="transparent")
        dur_stream.grid(row=2, column=1, sticky="w", pady=(0, 8), padx=(8, 0))
        self._duration_var = ctk.StringVar(value="60")
        ctk.CTkEntry(dur_stream, textvariable=self._duration_var, font=("Helvetica", 12),
                     width=80, height=32, corner_radius=6,
                     border_color="#d1d5db", border_width=1).pack(side="left")
        wl(dur_stream, text="并行流").pack(side="left", padx=(16, 4))
        self._streams_var = ctk.StringVar(value="1")
        ctk.CTkEntry(dur_stream, textvariable=self._streams_var, font=("Helvetica", 12),
                     width=80, height=32, corner_radius=6,
                     border_color="#d1d5db", border_width=1).pack(side="left")

        # Row 4: Buffer size
        wl(grid, text="缓冲(KB)").grid(row=3, column=0, sticky="w", pady=(0, 8))
        self._buffer_var = ctk.StringVar(value="128")
        ctk.CTkEntry(grid, textvariable=self._buffer_var, font=("Helvetica", 12),
                     width=80, height=32, corner_radius=6,
                     border_color="#d1d5db", border_width=1).grid(row=3, column=1, sticky="w", pady=(0, 8), padx=(8, 0))

        # UDP-only row
        self._udp_row = ctk.CTkFrame(grid, fg_color="transparent")
        self._udp_row.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 8))
        wl(self._udp_row, text="UDP带宽(Mbps)").pack(side="left")
        self._bw_var = ctk.StringVar(value="1")
        self._bw_entry = ctk.CTkEntry(self._udp_row, textvariable=self._bw_var,
                                       font=("Helvetica", 12), width=80, height=32,
                                       corner_radius=6, border_color="#d1d5db", border_width=1)
        self._bw_entry.pack(side="left", padx=(8, 0))
        # Hidden by default (TCP selected)

        # Buttons
        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(anchor="w", fill="x", pady=(12, 0))
        self._start_btn = ctk.CTkButton(btn_row, text="开始测试", command=self._start_client,
                                        width=100, height=34, font=("Helvetica", 13, "bold"),
                                        corner_radius=8, fg_color="#10a37f", hover_color="#0d8c6d")
        self._start_btn.pack(side="left", padx=(0, 8))
        self._stop_btn = ctk.CTkButton(btn_row, text="停止", command=self._stop,
                                       width=80, height=34, font=("Helvetica", 13),
                                       corner_radius=8, fg_color="#dc2626", hover_color="#b91c1c",
                                       state="disabled")
        self._stop_btn.pack(side="left")

    # ── Server UI ──

    def _build_server_ui(self, parent):
        def wl(master, text, font=("Helvetica", -12), fg="#333333", **kw):
            return tk.Label(master, text=text, font=font, fg=fg,
                            bg="white", highlightthickness=0, bd=0, **kw)

        # Use a grid layout aligned to the left
        grid = ctk.CTkFrame(parent, fg_color="transparent")
        grid.pack(anchor="w", fill="x")
        grid.grid_columnconfigure(1, weight=1)

        wl(grid, text="绑定地址").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self._srv_bind_var = ctk.StringVar(value="0.0.0.0")
        ctk.CTkEntry(grid, textvariable=self._srv_bind_var, font=("Helvetica", 12),
                     width=160, height=32, corner_radius=6,
                     border_color="#d1d5db", border_width=1).grid(row=0, column=1, sticky="w", pady=(0, 8), padx=(8, 0))

        wl(grid, text="端口").grid(row=1, column=0, sticky="w", pady=(0, 8))
        self._srv_port_var = ctk.StringVar(value="5201")
        ctk.CTkEntry(grid, textvariable=self._srv_port_var, font=("Helvetica", 12),
                     width=80, height=32, corner_radius=6,
                     border_color="#d1d5db", border_width=1).grid(row=1, column=1, sticky="w", pady=(0, 8), padx=(8, 0))

        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(anchor="w", fill="x", pady=(12, 0))
        self._srv_start_btn = ctk.CTkButton(btn_row, text="启动服务器", command=self._start_server,
                                            width=100, height=34, font=("Helvetica", 13, "bold"),
                                            corner_radius=8, fg_color="#10a37f", hover_color="#0d8c6d")
        self._srv_start_btn.pack(side="left", padx=(0, 8))
        self._srv_stop_btn = ctk.CTkButton(btn_row, text="停止", command=self._stop,
                                           width=80, height=34, font=("Helvetica", 13),
                                           corner_radius=8, fg_color="#dc2626", hover_color="#b91c1c",
                                           state="disabled")
        self._srv_stop_btn.pack(side="left")

    # ── Mode switch ──

    def _set_mode(self, mode):
        self._mode_var.set(mode)
        self._update_mode_buttons()
        if mode == "client":
            self._client_frame.pack(fill="x", padx=15, pady=15)
            self._server_frame.pack_forget()
        else:
            self._client_frame.pack_forget()
            self._server_frame.pack(fill="x", padx=15, pady=15)

    def _update_mode_buttons(self):
        current = self._mode_var.get()
        for val, btn in self._mode_btns.items():
            if val == current:
                btn.configure(fg_color="#10a37f", text_color="white", hover_color="#0d8c6d")
            else:
                btn.configure(fg_color="transparent", text_color="#333333", hover_color="#e0e0e0")

    def _on_proto_change(self, proto):
        if proto == "UDP":
            self._udp_row.pack(fill="x", pady=(0, 8))
        else:
            self._udp_row.pack_forget()

    # ── Output helpers ──

    def _append_output(self, text):
        self._output.insert("end", text + "\n")
        self._output.see("end")

    def _clear_output(self):
        self._output.delete("1.0", "end")

    def _finish(self):
        self._running = False
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._srv_start_btn.configure(state="normal")
        self._srv_stop_btn.configure(state="disabled")

    # ── Stop ──

    def _stop(self):
        if not self._running:
            return
        self._stop_event.set()
        self._append_output("[INFO] 正在停止...")

    # ── Client start ──

    def _start_client(self):
        if self._running:
            return

        host = self._host_var.get().strip()
        port_str = self._port_var.get().strip()
        duration_str = self._duration_var.get().strip()
        streams_str = self._streams_var.get().strip()
        buf_str = self._buffer_var.get().strip()
        proto = self._proto_var.get()

        if not host:
            messagebox.showwarning("提示", "请输入服务器地址")
            return
        if not port_str.isdigit() or not (1 <= int(port_str) <= 65535):
            messagebox.showwarning("提示", "请输入有效的端口号 (1-65535)")
            return
        if not duration_str.isdigit() or int(duration_str) < 1:
            messagebox.showwarning("提示", "测试时长必须为正整数(秒)")
            return
        if not streams_str.isdigit() or not (1 <= int(streams_str) <= 10):
            messagebox.showwarning("提示", "并行流数量为 1-10")
            return
        try:
            buf_kb = int(buf_str)
            if buf_kb < 1 or buf_kb > 1024:
                raise ValueError
        except ValueError:
            messagebox.showwarning("提示", "缓冲区大小为 1-1024 KB")
            return

        port = int(port_str)
        duration = int(duration_str)
        streams = int(streams_str)
        buf_size = buf_kb * 1024

        bw_mbps = 0
        if proto == "UDP":
            try:
                bw_mbps = float(self._bw_var.get())
                if bw_mbps <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("提示", "请输入有效的 UDP 目标带宽")
                return

        self._running = True
        self._stop_event.clear()
        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._clear_output()

        self._append_output(f"[INFO] 连接到 {host}:{port}，协议: {proto}")
        if streams > 1:
            self._append_output(f"[INFO] 并行流: {streams}，缓冲: {buf_kb} KB")
        self._append_output("-" * 50)

        if proto == "TCP":
            target = self._run_tcp_client
            args = (host, port, duration, streams, buf_size)
        else:
            target = self._run_udp_client
            args = (host, port, duration, streams, buf_size, bw_mbps)

        threading.Thread(target=target, args=args, daemon=True).start()

    # ── Server start ──

    def _start_server(self):
        if self._running:
            return

        bind_addr = self._srv_bind_var.get().strip()
        port_str = self._srv_port_var.get().strip()

        if not bind_addr:
            bind_addr = "0.0.0.0"
        if not port_str.isdigit() or not (1 <= int(port_str) <= 65535):
            messagebox.showwarning("提示", "请输入有效的端口号 (1-65535)")
            return

        port = int(port_str)

        self._running = True
        self._stop_event.clear()
        self._srv_start_btn.configure(state="disabled")
        self._srv_stop_btn.configure(state="normal")
        self._clear_output()

        self._append_output(f"[INFO] 启动服务器: {bind_addr}:{port}")
        self._append_output("[INFO] 等待客户端连接...")
        self._append_output("-" * 50)

        threading.Thread(target=self._run_server, args=(bind_addr, port), daemon=True).start()

    # ══════════════ TCP Client ══════════════

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

                seq = 0
                while not self._stop_event.is_set() and time.time() - start_time < duration:
                    try:
                        # Update sequence in header
                        header = struct.pack("!II", stream_id, seq)
                        payload = header + b"\x00" * (buf_size - len(header))
                        sock.sendall(payload)
                        total_bytes += buf_size
                        seq += 1

                        # Report per-second bandwidth
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

        threads = []
        for sid in range(streams):
            t = threading.Thread(target=do_stream, args=(sid,), daemon=True)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        # Final report
        elapsed = time.time() - start_time
        if elapsed > 0:
            avg_bw = total_bytes * 8 / elapsed / 1e6
            total_mb = total_bytes / 1e6
            self.app.after(0, self._append_output, "-" * 50)
            self.app.after(0, self._append_output,
                           f"总计: {total_mb:.1f} MB  时长: {elapsed:.1f} 秒  平均带宽: {avg_bw:.1f} Mbps")
            logger.info(f"[iPerf客户端] TCP {host}:{port} {elapsed:.1f}s {avg_bw:.1f}Mbps")

        self.app.after(0, self._finish)

    # ══════════════ UDP Client ══════════════

    def _run_udp_client(self, host, port, duration, streams, buf_size, bw_mbps):
        total_bytes = 0
        total_packets = 0
        start_time = time.time()
        last_report = start_time
        last_bytes = 0

        # Calculate packets per second based on target bandwidth
        bits_per_second = bw_mbps * 1e6
        bytes_per_second = bits_per_second / 8
        packets_per_second = bytes_per_second / buf_size
        interval = 1.0 / max(packets_per_second, 1)  # seconds between packets
        if interval < 0.0001:
            interval = 0.0001  # safety floor

        def do_stream(stream_id):
            nonlocal total_bytes, last_report, last_bytes, total_packets
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(0.1)

                seq = 0
                while not self._stop_event.is_set() and time.time() - start_time < duration:
                    ts = time.time()
                    header = struct.pack("!IId", stream_id, seq, ts)
                    padding = b"\x00" * max(0, buf_size - len(header))
                    data = header + padding
                    try:
                        sock.sendto(data, (host, port))
                        total_bytes += len(data)
                        total_packets += 1
                        seq += 1
                    except socket.timeout:
                        continue

                    # Report
                    now = time.time()
                    if now - last_report >= 1.0:
                        bw = (total_bytes - last_bytes) * 8 / (now - last_report) / 1e6
                        elapsed = int(now - start_time)
                        self.app.after(0, self._append_output,
                                       f"  [{elapsed:2d}] {elapsed-1:.0f}-{elapsed:.0f} sec  带宽: {bw:7.1f} Mbps")
                        last_report = now
                        last_bytes = total_bytes

                    # Rate limiting
                    time.sleep(interval / streams)

                sock.close()
            except Exception as e:
                self.app.after(0, self._append_output, f"[ERROR] UDP流{stream_id}: {e}")

        threads = []
        for sid in range(streams):
            t = threading.Thread(target=do_stream, args=(sid,), daemon=True)
            t.start()
            threads.append(t)

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

    # ══════════════ Server ══════════════

    def _run_server(self, bind_addr, port):
        """TCP + UDP server - listens on both protocols."""
        tcp_sock = None
        udp_sock = None
        start_time = time.time()
        tcp_bytes = [0]
        udp_bytes = [0]
        udp_packets = [0]
        udp_lost = [0]

        try:
            # TCP socket
            tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            tcp_sock.settimeout(0.5)
            tcp_sock.bind((bind_addr, port))
            tcp_sock.listen(5)

            # UDP socket
            udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp_sock.settimeout(0.5)
            udp_sock.bind((bind_addr, port))

            self.app.after(0, self._append_output, f"[INFO] 服务器已启动，监听 TCP+UDP :{port}")
            self.app.after(0, self._append_output, "[INFO] 等待客户端连接...")

            # Stats counters (per-second reporting)
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
                        # Parse sequence for loss detection
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

            # Start UDP handler and reporter
            udp_thread = threading.Thread(target=handle_udp, daemon=True)
            udp_thread.start()
            reporter = threading.Thread(target=report_loop, daemon=True)
            reporter.start()

            # Accept TCP connections
            while not self._stop_event.is_set():
                try:
                    client_sock, addr = tcp_sock.accept()
                    self.app.after(0, self._append_output, f"[INFO] TCP 客户端连接: {addr[0]}:{addr[1]}")
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
