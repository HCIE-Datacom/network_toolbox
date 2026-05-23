"""NTP Client module - query NTP server and display results."""

import socket
import struct
import time
import threading
import customtkinter as ctk
from tkinter import messagebox

from core.base_module import ToolModule

# ---------- NTP Protocol ----------

NTP_EPOCH_DIFF = 2208988800
NTP_PACKET_FORMAT = "!B B B b 11I"


def _create_ntp_packet(version=4, mode=3):
    first_byte = (0 << 6) | (version << 3) | mode
    return struct.pack(NTP_PACKET_FORMAT, first_byte, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)


def _ntp_to_unix_seconds(tx_int, tx_frac):
    return (tx_int - NTP_EPOCH_DIFF) + (tx_frac / (2 ** 32))


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


# ---------- Module ----------

class NTPClientModule(ToolModule):
    name = "NTP 客户端"
    icon = "🕐"
    description = "输入 NTP 服务器地址，点击测试即可查询服务器时间并计算本地时钟偏移。"

    def build(self, parent):
        # Title
        ctk.CTkLabel(parent, text=self.name,
                      font=("Helvetica", 22, "bold"), text_color="#1f1f1f").pack(anchor="w", pady=(0, 5))
        ctk.CTkLabel(parent, text=self.description,
                      font=("Helvetica", 13), text_color="#6b6b6b",
                      wraplength=620, justify="left").pack(anchor="w", pady=(0, 20))

        # Input card
        inp_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                 border_width=1, border_color="#e5e5e5")
        inp_card.pack(fill="x", pady=(0, 15))
        inp_inner = ctk.CTkFrame(inp_card, fg_color="transparent")
        inp_inner.pack(fill="x", padx=15, pady=15)
        ctk.CTkLabel(inp_inner, text="NTP 服务器",
                      font=("Helvetica", 12, "bold"), text_color="#333333").pack(anchor="w", pady=(0, 8))

        row = ctk.CTkFrame(inp_inner, fg_color="transparent")
        row.pack(fill="x")
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

        # Result card
        res_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                 border_width=1, border_color="#e5e5e5")
        res_card.pack(fill="both", expand=False)
        res_card.configure(height=360)
        res_inner = ctk.CTkFrame(res_card, fg_color="transparent")
        res_inner.pack(fill="both", expand=True, padx=15, pady=15)

        self._result_grid = ctk.CTkFrame(res_inner, fg_color="transparent")
        self._result_grid.pack(fill="both", expand=True)
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
        try:
            result = _query_ntp(server)
            try:
                bj = _query_ntp("cn.pool.ntp.org", timeout=3)
                result["beijing_time"] = bj["server_time"]
            except Exception:
                result["beijing_time"] = result["server_time"]
            self.app.after(0, self._show_success, result)
        except socket.timeout:
            self.app.after(0, self._show_error, "连接超时，请检查网络或服务器地址")
        except socket.gaierror:
            self.app.after(0, self._show_error, "无法解析服务器地址，请检查输入")
        except Exception as e:
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
