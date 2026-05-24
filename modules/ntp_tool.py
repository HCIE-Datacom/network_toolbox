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

"""NTP Tool module - combined NTP client and server."""

import socket
import struct
import time
import threading
import platform
import customtkinter as ctk
from tkinter import messagebox

from core.base_module import ToolModule
from core.logger import logger

# ========== Shared NTP Protocol ==========

NTP_EPOCH_DIFF = 2208988800
NTP_PACKET_FORMAT = "!B B B b 11I"


def _ntp_to_unix_seconds(tx_int, tx_frac):
    return (tx_int - NTP_EPOCH_DIFF) + (tx_frac / (2 ** 32))


# ========== Client helpers ==========

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


# ========== Server helpers ==========

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
    def __init__(self, port, log_callback):
        super().__init__(daemon=True)
        self.port = int(port)
        self.log_callback = log_callback
        self.sock = None
        self.stop_event = threading.Event()

    @staticmethod
    def _ts():
        return time.strftime("%Y-%m-%d %H:%M:%S")

    def run(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.bind(("0.0.0.0", self.port))
        except PermissionError:
            self.log_callback(f"{self._ts()}  [错误] 绑定端口 {self.port} 需要管理员权限")
            return
        except Exception as e:
            self.log_callback(f"{self._ts()}  [错误] 绑定失败: {e}")
            return

        self.log_callback(f"{self._ts()}  [启动] NTP 服务器正在监听 0.0.0.0:{self.port}")
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
                    self.log_callback(f"{self._ts()}  [请求] 来自 {addr[0]}:{addr[1]}  |  客户端发送时间: {client_str}")
                    response = _create_ntp_response(origin_int, origin_frac, version)
                    self.sock.sendto(response, addr)
                    self.log_callback(f"{self._ts()}  [响应] 已向 {addr[0]}:{addr[1]} 发送时间同步数据")
                except Exception as e:
                    self.log_callback(f"{self._ts()}  [错误] 处理请求失败: {e}")
        self.log_callback(f"{self._ts()}  [停止] NTP 服务器已停止")

    def stop(self):
        self.stop_event.set()
        try:
            self.sock.close()
        except Exception:
            pass


# ========== Module ==========

class NTPToolModule(ToolModule):
    name = "NTP 工具"
    icon = "🕐"
    description = "查询网络时间服务器或在本机启动 NTP 服务，为局域网设备提供时间同步。"

    def build(self, parent):
        # Title
        ctk.CTkLabel(parent, text=self.name,
                      font=("Helvetica", 22, "bold"), text_color="#1f1f1f").pack(anchor="w", pady=(0, 5))
        ctk.CTkLabel(parent, text=self.description,
                      font=("Helvetica", 13), text_color="#6b6b6b",
                      wraplength=620, justify="left").pack(anchor="w", pady=(0, 15))

        # ===== Mode selector =====
        mode_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                 border_width=1, border_color="#e5e5e5")
        mode_card.pack(fill="x", pady=(0, 15))
        mode_inner = ctk.CTkFrame(mode_card, fg_color="transparent")
        mode_inner.pack(fill="x", padx=15, pady=15)

        ctk.CTkLabel(mode_inner, text="功能模式",
                     font=("Helvetica", 12, "bold"), text_color="#333333").pack(anchor="w", pady=(0, 8))

        self._mode_var = ctk.StringVar(value="client")
        mode_btn_frame = ctk.CTkFrame(mode_inner, fg_color="#f0f0f0", corner_radius=8)
        mode_btn_frame.pack(fill="x")
        self._mode_btns = {}
        for val, label_text in [("client", "客户端"), ("server", "服务器")]:
            btn = ctk.CTkButton(mode_btn_frame, text=label_text, width=0, height=32,
                                font=("Helvetica", 12), corner_radius=6,
                                fg_color="transparent", text_color="#333333",
                                hover_color="#e0e0e0",
                                command=lambda v=val: self._set_mode(v))
            btn.pack(side="left", expand=True, fill="x", padx=2, pady=2)
            self._mode_btns[val] = btn
        self._update_mode_buttons()

        # ===== Content container =====
        content_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                    border_width=1, border_color="#e5e5e5")
        content_card.pack(fill="both", expand=True)

        content_inner = ctk.CTkFrame(content_card, fg_color="transparent")
        content_inner.pack(fill="both", expand=True, padx=15, pady=15)

        # ----- Client UI -----
        self._client_frame = ctk.CTkFrame(content_inner, fg_color="transparent")
        self._build_client_ui(self._client_frame)

        # ----- Server UI -----
        self._server_frame = ctk.CTkFrame(content_inner, fg_color="transparent")
        self._build_server_ui(self._server_frame)

        # Start in client mode
        self._set_mode("client")

    # ========== Client UI ==========

    def _build_client_ui(self, parent):
        # Label
        ctk.CTkLabel(parent, text="NTP 服务器",
                     font=("Helvetica", 12, "bold"), text_color="#333333").pack(anchor="w", pady=(0, 6))

        # Input + button on same row
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 12))
        row.grid_columnconfigure(0, weight=1)

        self._server_var = ctk.StringVar(value="ntp.aliyun.com")
        self._server_entry = ctk.CTkEntry(row, textvariable=self._server_var,
                                           placeholder_text="例如: ntp.aliyun.com",
                                           font=("Helvetica", 13), corner_radius=8,
                                           height=38, border_color="#d1d5db", border_width=1)
        self._server_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self._server_entry.bind("<Return>", lambda e: self._on_test())

        self._test_btn = ctk.CTkButton(row, text="测试", command=self._on_test,
                                        width=90, height=38, font=("Helvetica", 13, "bold"),
                                        corner_radius=8, fg_color="#10a37f", hover_color="#0d8c6d")
        self._test_btn.grid(row=0, column=1)

        # Result area
        self._result_grid = ctk.CTkFrame(parent, fg_color="transparent")
        self._result_grid.pack(fill="both", expand=True, pady=(12, 0))
        self._result_grid.grid_columnconfigure(1, weight=1)
        self._result_labels = {}

        ctk.CTkLabel(self._result_grid, text="查询结果",
                      font=("Helvetica", 12, "bold"), text_color="#333333").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        keys = ["服务器:", "状态:", "服务器时间:", "北京时间:", "本地时间:", "往返时延:", "时间偏移:", "结论:"]
        for i, key in enumerate(keys):
            ctk.CTkLabel(self._result_grid, text=key, font=("Helvetica", 12),
                          text_color="#666666", width=90, anchor="e").grid(
                row=i + 1, column=0, sticky="ne", padx=(0, 12), pady=4)
            lbl = ctk.CTkLabel(self._result_grid, text="", font=("Helvetica", 12),
                                text_color="#333333", anchor="w", justify="left")
            lbl.grid(row=i + 1, column=1, sticky="nw", pady=4)
            self._result_labels[key] = lbl

    # ========== Server UI ==========

    def _build_server_ui(self, parent):
        ctk.CTkLabel(parent, text="服务配置",
                     font=("Helvetica", 12, "bold"), text_color="#333333").pack(anchor="w", pady=(0, 8))

        # Port row
        pr = ctk.CTkFrame(parent, fg_color="transparent")
        pr.pack(fill="x")
        pr.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(pr, text="监听端口:", font=("Helvetica", 13),
                     text_color="#333333").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self._port_var = ctk.StringVar(value="123")
        self._port_entry = ctk.CTkEntry(pr, textvariable=self._port_var, width=100,
                                         font=("Helvetica", 13), corner_radius=8,
                                         height=38, border_color="#d1d5db", border_width=1)
        self._port_entry.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(pr, text="(1024 以下端口需要管理员权限)",
                     font=("Helvetica", 11), text_color="#8e8e8e").grid(row=0, column=2, sticky="w", padx=(10, 0))

        # Toggle row
        br = ctk.CTkFrame(parent, fg_color="transparent")
        br.pack(fill="x", pady=(12, 0))
        self._toggle_btn = ctk.CTkButton(br, text="启动服务", command=self._toggle,
                                          width=120, height=38, font=("Helvetica", 13, "bold"),
                                          corner_radius=8, fg_color="#10a37f", hover_color="#0d8c6d")
        self._toggle_btn.pack(side="left")
        self._status_label = ctk.CTkLabel(br, text="状态: 已停止",
                                           font=("Helvetica", 13), text_color="#666666")
        self._status_label.pack(side="left", padx=(15, 0))

        # Log area
        ctk.CTkLabel(parent, text="运行日志",
                     font=("Helvetica", 12, "bold"), text_color="#333333").pack(anchor="w", pady=(12, 8))

        mono = ("SF Mono", max(11, 11)) if platform.system() == "Darwin" else ("Consolas", max(11, 11))
        self._log_text = ctk.CTkTextbox(parent, font=mono, wrap="word", corner_radius=8,
                                         fg_color="white", text_color="#333333",
                                         border_width=1, border_color="#e5e5e5",
                                         activate_scrollbars=True)
        self._log_text.pack(fill="both", expand=True, pady=(0, 8))
        self._log_text.configure(state="disabled")

        # State
        self._server_thread = None

    # ========== Mode switching ==========

    def _set_mode(self, mode):
        self._mode_var.set(mode)
        self._update_mode_buttons()
        if mode == "client":
            self._client_frame.pack(fill="both", expand=True)
            self._server_frame.pack_forget()
        else:
            self._client_frame.pack_forget()
            self._server_frame.pack(fill="both", expand=True)

    def _update_mode_buttons(self):
        current = self._mode_var.get()
        for val, btn in self._mode_btns.items():
            if val == current:
                btn.configure(fg_color="#10a37f", text_color="white", hover_color="#0d8c6d")
            else:
                btn.configure(fg_color="transparent", text_color="#333333", hover_color="#e0e0e0")

    # ========== Client actions ==========

    def _on_test(self):
        server = self._server_var.get().strip()
        if not server:
            messagebox.showwarning("提示", "请输入 NTP 服务器地址")
            return
        self._test_btn.configure(state="disabled", text="测试中...")
        self._clear_results()
        self._result_labels["状态:"].configure(text="查询中，请稍候...")
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
        self._clear_results()
        st = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["server_time"]))
        lt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["local_time"]))
        bt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["beijing_time"]))
        rtt = r["rtt"] * 1000
        off = r["offset"] * 1000

        if abs(r["offset"]) < 0.001:
            conclusion = "本地时钟与服务器同步良好。"
        elif r["offset"] > 0:
            conclusion = f"本地时钟慢了约 {r['offset']:.6f} 秒，建议调快。"
        else:
            conclusion = f"本地时钟快了约 {-r['offset']:.6f} 秒，建议调慢。"

        for k, v in [
            ("服务器:", r["server_ip"]), ("状态:", "成功"),
            ("服务器时间:", f"{st} (UTC+8)"), ("北京时间:", f"{bt} (UTC+8)"),
            ("本地时间:", f"{lt} (UTC+8)"), ("往返时延:", f"{rtt:.3f} ms"),
            ("时间偏移:", f"{off:+.3f} ms"), ("结论:", conclusion),
        ]:
            self._result_labels[k].configure(text=v)
        self._test_btn.configure(state="normal", text="测试")

    def _show_error(self, msg):
        self._clear_results()
        self._result_labels["状态:"].configure(text="查询失败")
        self._result_labels["结论:"].configure(text=msg)
        self._test_btn.configure(state="normal", text="测试")

    def _clear_results(self):
        for lbl in self._result_labels.values():
            lbl.configure(text="")

    # ========== Server actions ==========

    def _toggle(self):
        if self._server_thread and not self._server_thread.stop_event.is_set():
            self._stop()
        else:
            self._start()

    def _start(self):
        port_str = self._port_var.get().strip()
        if not port_str.isdigit() or not (1 <= int(port_str) <= 65535):
            messagebox.showwarning("提示", "请输入有效的端口号 (1-65535)")
            return
        logger.info(f"[NTP服务器] 启动服务, 端口: {port_str}")
        self._log_clear()
        self._server_thread = _NTPServerThread(int(port_str), self._log)
        self._server_thread.start()
        self._toggle_btn.configure(text="停止服务", fg_color="#dc2626", hover_color="#b91c1c")
        self._status_label.configure(text="状态: 运行中", text_color="#10a37f")
        self._port_entry.configure(state="disabled")

    def _stop(self):
        logger.info("[NTP服务器] 停止服务")
        if self._server_thread:
            self._server_thread.stop()
            self._server_thread = None
        self._toggle_btn.configure(text="启动服务", fg_color="#10a37f", hover_color="#0d8c6d")
        self._status_label.configure(text="状态: 已停止", text_color="#666666")
        self._port_entry.configure(state="normal")

    def _log(self, text):
        def _up():
            self._log_text.configure(state="normal")
            self._log_text.insert("end", text + "\n")
            self._log_text.see("end")
            self._log_text.configure(state="disabled")
        self.app.after(0, _up)

    def _log_clear(self):
        self._log_text.configure(state="normal")
        self._log_text.delete("0.0", "end")
        self._log_text.configure(state="disabled")
