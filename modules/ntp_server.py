"""NTP Server module - run local NTP server for LAN time sync."""

import socket
import struct
import time
import threading
import platform
import customtkinter as ctk
from tkinter import messagebox

from core.base_module import ToolModule

# ---------- NTP Protocol ----------

NTP_EPOCH_DIFF = 2208988800
NTP_PACKET_FORMAT = "!B B B b 11I"


def _parse_ntp_request(data):
    unpacked = struct.unpack(NTP_PACKET_FORMAT, data)
    return unpacked[13], unpacked[14]


def _ntp_to_unix_seconds(tx_int, tx_frac):
    return (tx_int - NTP_EPOCH_DIFF) + (tx_frac / (2 ** 32))


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


# ---------- Server Thread ----------

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


# ---------- Module ----------

class NTPServerModule(ToolModule):
    name = "NTP 服务器"
    icon = "⚙️"
    description = "将本机作为 NTP 服务器运行，为局域网内的其他设备提供时间同步服务。"

    def build(self, parent):
        # Title
        ctk.CTkLabel(parent, text=self.name,
                      font=("Helvetica", 22, "bold"), text_color="#1f1f1f").pack(anchor="w", pady=(0, 5))
        ctk.CTkLabel(parent, text=self.description,
                      font=("Helvetica", 13), text_color="#6b6b6b",
                      wraplength=620, justify="left").pack(anchor="w", pady=(0, 20))

        # Config card
        srv_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                 border_width=1, border_color="#e5e5e5")
        srv_card.pack(fill="x", pady=(0, 15))
        srv_inner = ctk.CTkFrame(srv_card, fg_color="transparent")
        srv_inner.pack(fill="x", padx=15, pady=15)
        ctk.CTkLabel(srv_inner, text="服务配置",
                      font=("Helvetica", 12, "bold"), text_color="#333333").pack(anchor="w", pady=(0, 8))

        pr = ctk.CTkFrame(srv_inner, fg_color="transparent")
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

        br = ctk.CTkFrame(srv_inner, fg_color="transparent")
        br.pack(fill="x", pady=(15, 0))
        self._toggle_btn = ctk.CTkButton(br, text="启动服务", command=self._toggle,
                                          width=120, height=38, font=("Helvetica", 13, "bold"),
                                          corner_radius=8, fg_color="#10a37f", hover_color="#0d8c6d")
        self._toggle_btn.pack(side="left")
        self._status_label = ctk.CTkLabel(br, text="状态: 已停止",
                                           font=("Helvetica", 13), text_color="#666666")
        self._status_label.pack(side="left", padx=(15, 0))

        # Log card
        log_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                 border_width=1, border_color="#e5e5e5")
        log_card.pack(fill="both", expand=False)
        log_card.configure(height=320)
        log_inner = ctk.CTkFrame(log_card, fg_color="transparent")
        log_inner.pack(fill="both", expand=True, padx=15, pady=15)
        ctk.CTkLabel(log_inner, text="运行日志",
                      font=("Helvetica", 12, "bold"), text_color="#333333").pack(anchor="w", pady=(0, 10))

        mono = ("SF Mono", 11) if platform.system() == "Darwin" else ("Consolas", 11)
        self._log_text = ctk.CTkTextbox(log_inner, font=mono, wrap="word", corner_radius=0,
                                         fg_color="white", text_color="#333333",
                                         border_width=0, activate_scrollbars=True)
        self._log_text.pack(fill="both", expand=True)
        self._log_text.configure(state="disabled")

        # State
        self._server_thread = None

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
        self._log_clear()
        self._server_thread = _NTPServerThread(int(port_str), self._log)
        self._server_thread.start()
        self._toggle_btn.configure(text="停止服务", fg_color="#dc2626", hover_color="#b91c1c")
        self._status_label.configure(text="状态: 运行中", text_color="#10a37f")
        self._port_entry.configure(state="disabled")

    def _stop(self):
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
