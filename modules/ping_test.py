"""PING Test module - Ping, Traceroute, and TCPing utilities."""

import socket
import time
import struct
import re
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

try:
    import ping3
except ImportError:
    ping3 = None

from core.base_module import ToolModule


# ---------- Pure Python ICMP helpers ----------

def _icmp_checksum(data):
    """Calculate ICMP checksum."""
    if len(data) % 2:
        data += b'\x00'
    s = 0
    for i in range(0, len(data), 2):
        w = (data[i] << 8) + data[i + 1]
        s += w
    s = (s >> 16) + (s & 0xffff)
    s += s >> 16
    return ~s & 0xffff


def _raw_ping(dest, timeout=3, seq=0, ttl=None, size=56):
    """Send one ICMP echo request and wait for reply. Returns (rtt_ms, error_msg)."""
    try:
        dest_ip = socket.gethostbyname(dest)
    except socket.gaierror:
        return None, "Cannot resolve target address"

    sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    sock.settimeout(timeout)
    if ttl is not None:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)

    # Build ICMP echo request
    pid = os.getpid() & 0xffff
    header = struct.pack("!BBHHH", 8, 0, 0, pid, seq)
    data = (size - 8) * b'Q'
    pkt = header + data
    chk = _icmp_checksum(pkt)
    pkt = struct.pack("!BBHHH", 8, 0, chk, pid, seq) + data

    send_time = time.time()
    try:
        sock.sendto(pkt, (dest_ip, 0))
    except PermissionError:
        sock.close()
        return None, "需要管理员权限 (ICMP raw socket)"
    except OSError as e:
        sock.close()
        return None, f"发送失败: {e}"

    try:
        while True:
            buf, addr = sock.recvfrom(1024)
            recv_time = time.time()
            if addr[0] != dest_ip:
                continue
            # Parse ICMP header from IP payload (IP header is typically 20 bytes)
            icmp_header = buf[20:28]
            icmp_type, icmp_code, icmp_checksum, icmp_id, icmp_seq = struct.unpack("!BBHHH", icmp_header)
            if icmp_type == 0 and icmp_id == pid and icmp_seq == seq:
                rtt = (recv_time - send_time) * 1000
                return rtt, None
            elif icmp_type == 11:  # Time Exceeded (TTL expired)
                rtt = (recv_time - send_time) * 1000
                return rtt, None
    except socket.timeout:
        return None, "请求超时"
    except Exception as e:
        return None, str(e)
    finally:
        sock.close()


import os


def _do_ping(dest, count=4, timeout=3):
    """Perform ICMP ping. Returns list of (seq, rtt_ms, error) tuples."""
    results = []
    try:
        dest_ip = socket.gethostbyname(dest)
    except socket.gaierror:
        return [(0, None, "无法解析目标地址")]

    # Try ping3 first (more reliable across platforms)
    if ping3 is not None:
        for i in range(count):
            try:
                rtt = ping3.ping(dest, timeout=timeout, unit='ms', seq=i)
                if rtt is not None and rtt is not False:
                    results.append((i + 1, rtt, None))
                else:
                    results.append((i + 1, None, "请求超时"))
            except PermissionError:
                results.append((i + 1, None, "需要管理员权限"))
                break
            except Exception as e:
                results.append((i + 1, None, str(e)))
            if i < count - 1:
                time.sleep(0.5)
        return results

    # Fallback: raw socket
    for i in range(count):
        rtt, err = _raw_ping(dest, timeout=timeout, seq=i)
        results.append((i + 1, rtt, err))
        if i < count - 1:
            time.sleep(0.5)
    return results


def _do_traceroute(dest, max_hops=30, timeout=3):
    """Perform traceroute using system command. Returns list of (hop, ip, rtt_ms, error)."""
    import subprocess
    import platform

    results = []
    try:
        dest_ip = socket.gethostbyname(dest)
    except socket.gaierror:
        return [(0, dest, None, "无法解析目标地址")]

    system = platform.system()
    if system == "Windows":
        cmd = ["tracert", "-d", "-w", str(timeout * 1000), "-h", str(max_hops), dest_ip]
    else:
        cmd = ["traceroute", "-n", "-w", str(timeout), "-q", "1", "-m", str(max_hops), dest_ip]

    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, bufsize=1)
        for line in p.stdout:
            line = line.rstrip()
            if not line:
                continue
            # Parse macOS/Linux traceroute output:
            # " 1  192.168.1.1  0.523 ms"
            # " 1  * * *"
            m = re.match(r'\s*(\d+)\s+(\S+)\s+([\d.]+)\s*ms', line)
            if m:
                hop = int(m.group(1))
                ip = m.group(2)
                rtt = float(m.group(3))
                results.append((hop, ip, rtt, None))
            else:
                m_star = re.match(r'\s*(\d+)\s+\*', line)
                if m_star:
                    hop = int(m_star.group(1))
                    results.append((hop, "*", None, "超时"))
                # Skip header/summary lines
        p.wait()
    except FileNotFoundError:
        return [(0, dest, None, "系统未找到 traceroute 命令")]
    except Exception as e:
        return [(0, dest, None, f"执行失败: {e}")]

    return results


def _do_tcping(dest, port=80, count=4, timeout=3):
    """Perform TCP ping. Returns list of (seq, rtt_ms, error) tuples."""
    results = []
    try:
        dest_ip = socket.gethostbyname(dest)
    except socket.gaierror:
        return [(0, None, "无法解析目标地址")]

    for i in range(count):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            start = time.time()
            result = sock.connect_ex((dest_ip, port))
            elapsed = (time.time() - start) * 1000
            sock.close()

            if result == 0:
                results.append((i + 1, elapsed, None))
            else:
                results.append((i + 1, None, "连接被拒绝"))
        except socket.timeout:
            results.append((i + 1, None, "请求超时"))
        except Exception as e:
            results.append((i + 1, None, str(e)))

        if i < count - 1:
            time.sleep(0.5)
    return results


# ---------- Module ----------

class PingTestModule(ToolModule):
    name = "PING 测试"
    icon = "\U0001F4E1"       # 📡
    description = "支持 Ping、Traceroute 和 TCP Ping 三种网络探测方式，用于检测网络连通性和路由路径。"

    def build(self, parent):
        # Helper: create standard tkinter.Label (avoids CTkLabel Canvas descender clipping)
        # Use negative size for pt units to match CTkLabel rendering
        def label(master, text, font=("Helvetica", -13), fg="#333333", **kw):
            return tk.Label(master, text=text, font=font, fg=fg,
                            bg="#f9f9f9", highlightthickness=0, bd=0, **kw)

        # Title
        label(parent, text=self.name,
              font=("Helvetica", -22, "bold"), fg="#1f1f1f").pack(anchor="w", pady=(0, 5))
        # Description
        label(parent, text=self.description,
              font=("Helvetica", -13), fg="#6b6b6b",
              wraplength=620, justify="left").pack(anchor="w", pady=(0, 15))

        # ---------- Input card ----------
        inp_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                border_width=1, border_color="#e5e5e5")
        inp_card.pack(fill="x", pady=(0, 15))
        inp_inner = ctk.CTkFrame(inp_card, fg_color="transparent")
        inp_inner.pack(fill="x", padx=15, pady=15)

        def white_label(master, text, font=("Helvetica", -13), fg="#333333", **kw):
            return tk.Label(master, text=text, font=font, fg=fg,
                            bg="white", highlightthickness=0, bd=0, **kw)

        # Target
        white_label(inp_inner, text="目标地址",
                    font=("Helvetica", -12, "bold"), fg="#333333").pack(anchor="w", pady=(0, 8))
        target_row = ctk.CTkFrame(inp_inner, fg_color="transparent")
        target_row.pack(fill="x")
        target_row.grid_columnconfigure(0, weight=1)

        self._target_var = ctk.StringVar(value="")
        self._target_entry = ctk.CTkEntry(target_row, textvariable=self._target_var,
                                          placeholder_text="例如: www.baidu.com 或 8.8.8.8",
                                          font=("Helvetica", 13), corner_radius=8,
                                          height=42, border_color="#d1d5db", border_width=1)
        self._target_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self._target_entry.bind("<Return>", lambda e: self._on_start())

        # Options row
        opt_row = ctk.CTkFrame(inp_inner, fg_color="transparent")
        opt_row.pack(fill="x", pady=(10, 0))
        opt_row.grid_columnconfigure(0, weight=1)
        opt_row.grid_columnconfigure(1, weight=1)
        opt_row.grid_columnconfigure(2, weight=1)

        # Mode selector (segmented buttons)
        mode_card = ctk.CTkFrame(opt_row, fg_color="transparent")
        mode_card.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        white_label(mode_card, text="测试模式", font=("Helvetica", -11),
                    fg="#666666").pack(anchor="w", pady=(0, 4))
        self._mode_var = ctk.StringVar(value="ping")
        mode_btn_frame = ctk.CTkFrame(mode_card, fg_color="#f0f0f0", corner_radius=8)
        mode_btn_frame.pack(fill="x")
        self._mode_btns = {}
        for val, label_text in [("ping", "Ping"), ("tracert", "Traceroute"), ("tcping", "TCPing")]:
            btn = ctk.CTkButton(mode_btn_frame, text=label_text, width=0, height=32,
                                font=("Helvetica", 12), corner_radius=6,
                                fg_color="transparent", text_color="#333333",
                                hover_color="#e0e0e0",
                                command=lambda v=val: self._set_mode(v))
            btn.pack(side="left", expand=True, fill="x", padx=2, pady=2)
            self._mode_btns[val] = btn
        self._update_mode_buttons()

        # Count
        count_card = ctk.CTkFrame(opt_row, fg_color="transparent")
        count_card.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        white_label(count_card, text="发送次数", font=("Helvetica", -11),
                    fg="#666666").pack(anchor="w", pady=(0, 4))
        self._count_var = ctk.StringVar(value="4")
        self._count_entry = ctk.CTkEntry(count_card, textvariable=self._count_var,
                                         font=("Helvetica", 12), corner_radius=8,
                                         height=34, border_color="#d1d5db", border_width=1)
        self._count_entry.pack(fill="x")

        # TCP port
        port_card = ctk.CTkFrame(opt_row, fg_color="transparent")
        port_card.grid(row=0, column=2, sticky="ew")
        white_label(port_card, text="TCP 端口", font=("Helvetica", -11),
                    fg="#666666").pack(anchor="w", pady=(0, 4))
        self._port_var = ctk.StringVar(value="80")
        self._port_entry = ctk.CTkEntry(port_card, textvariable=self._port_var,
                                        font=("Helvetica", 12), corner_radius=8,
                                        height=34, border_color="#d1d5db", border_width=1)
        self._port_entry.pack(fill="x")

        # Buttons row
        btn_row = ctk.CTkFrame(inp_inner, fg_color="transparent")
        btn_row.pack(fill="x", pady=(12, 0))

        self._start_btn = ctk.CTkButton(btn_row, text="开始测试", command=self._on_start,
                                        width=100, height=36, font=("Helvetica", 13, "bold"),
                                        corner_radius=8, fg_color="#10a37f", hover_color="#0d8c6d")
        self._start_btn.pack(side="left")

        self._stop_btn = ctk.CTkButton(btn_row, text="停止", command=self._on_stop,
                                       width=80, height=36, font=("Helvetica", 13, "bold"),
                                       corner_radius=8, fg_color="#e74c3c", hover_color="#c0392b",
                                       state="disabled")
        self._stop_btn.pack(side="left", padx=(10, 0))

        self._clear_btn = ctk.CTkButton(btn_row, text="清空", command=self._on_clear,
                                        width=80, height=36, font=("Helvetica", 13),
                                        corner_radius=8, fg_color="#f5f5f5",
                                        text_color="#333333", hover_color="#e0e0e0",
                                        border_width=1, border_color="#e5e5e5")
        self._clear_btn.pack(side="right")

        # ---------- Output card ----------
        out_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                border_width=1, border_color="#e5e5e5")
        out_card.pack(fill="both", expand=True)

        out_inner = ctk.CTkFrame(out_card, fg_color="transparent")
        out_inner.pack(fill="both", expand=True, padx=15, pady=15)

        # Stats row
        self._stats_frame = ctk.CTkFrame(out_inner, fg_color="#f9f9f9", corner_radius=8)
        self._stats_frame.pack(fill="x", pady=(0, 10))
        stats_inner = ctk.CTkFrame(self._stats_frame, fg_color="transparent")
        stats_inner.pack(fill="x", padx=12, pady=8)
        stats_inner.grid_columnconfigure(0, weight=1)
        stats_inner.grid_columnconfigure(1, weight=1)
        stats_inner.grid_columnconfigure(2, weight=1)
        stats_inner.grid_columnconfigure(3, weight=1)

        def stats_label(master, text, **grid_kw):
            lbl = tk.Label(master, text=text, font=("Helvetica", -11),
                           fg="#666666", bg="#f9f9f9", highlightthickness=0, bd=0)
            lbl.grid(**grid_kw)
            return lbl

        self._stat_sent = stats_label(stats_inner, "已发送: -",
                                      row=0, column=0, sticky="w", padx=(0, 12))
        self._stat_recv = stats_label(stats_inner, "已接收: -",
                                      row=0, column=1, sticky="w", padx=(0, 12))
        self._stat_loss = stats_label(stats_inner, "丢包率: -",
                                      row=0, column=2, sticky="w", padx=(0, 12))
        self._stat_avg = stats_label(stats_inner, "平均延迟: -",
                                     row=0, column=3, sticky="w")

        # Text output
        self._output = ctk.CTkTextbox(out_inner, font=("Courier", 14), corner_radius=8,
                                      fg_color="#1e1e1e", text_color="#e0e0e0",
                                      border_width=1, border_color="#e5e5e5",
                                      height=250, activate_scrollbars=True,
                                      spacing3=4)
        self._output.pack(fill="both", expand=True)

        self._running = False
        self._stop_event = threading.Event()

    # ---------- UI callbacks ----------

    def _append_output(self, text):
        self._output.insert("end", text + "\n")
        self._output.see("end")

    def _update_stats(self, sent, recv, avg):
        self._stat_sent.configure(text=f"已发送: {sent}")
        self._stat_recv.configure(text=f"已接收: {recv}")
        if isinstance(sent, int) and sent > 0:
            loss = (sent - recv) / sent * 100
            self._stat_loss.configure(text=f"丢包率: {loss:.1f}%")
            color = "#e74c3c" if loss > 20 else ("#f39c12" if loss > 0 else "#27ae60")
            self._stat_loss.configure(fg=color)
        if avg is not None:
            self._stat_avg.configure(text=f"平均延迟: {avg:.1f} ms")
        else:
            self._stat_avg.configure(text="平均延迟: -")

    def _set_mode(self, mode):
        self._mode_var.set(mode)
        self._update_mode_buttons()

    def _update_mode_buttons(self):
        current = self._mode_var.get()
        for val, btn in self._mode_btns.items():
            if val == current:
                btn.configure(fg_color="#10a37f", text_color="white", hover_color="#0d8c6d")
            else:
                btn.configure(fg_color="transparent", text_color="#333333", hover_color="#e0e0e0")

    def _on_clear(self):
        self._output.delete("0.0", "end")
        self._update_stats("-", "-", None)
        self._stat_loss.configure(fg="#666666")

    def _on_start(self):
        target = self._target_var.get().strip()
        if not target:
            messagebox.showwarning("提示", "请输入目标地址")
            return

        mode = self._mode_var.get()

        count = self._count_var.get().strip()
        if not count.isdigit() or int(count) < 1:
            messagebox.showwarning("提示", "发送次数必须为正整数")
            return

        self._on_clear()
        self._running = True
        self._stop_event.clear()
        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")

        if mode == "ping":
            threading.Thread(target=self._run_ping, args=(target, int(count)), daemon=True).start()
        elif mode == "tracert":
            threading.Thread(target=self._run_tracert, args=(target,), daemon=True).start()
        elif mode == "tcping":
            port_str = self._port_var.get().strip()
            if not port_str.isdigit() or not (1 <= int(port_str) <= 65535):
                messagebox.showwarning("提示", "TCP 端口必须为 1-65535 之间的整数")
                self._finish()
                return
            threading.Thread(target=self._run_tcping, args=(target, int(count), int(port_str)), daemon=True).start()

    def _on_stop(self):
        self._stop_event.set()
        self._running = False
        self._finish()

    def _finish(self):
        self._running = False
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")

    # ---------- Ping ----------

    def _run_ping(self, target, count):
        from core.logger import logger
        self.app.after(0, self._append_output, f"--- Ping {target} ({count} 次) ---")
        logger.info(f"[Ping] 开始测试: {target} x{count}")

        try:
            dest_ip = socket.gethostbyname(target)
        except socket.gaierror:
            self.app.after(0, self._append_output, f"错误: 无法解析 {target}")
            logger.error(f"[Ping] DNS 解析失败: {target}")
            self.app.after(0, self._finish)
            return

        # Real-time ping: send one at a time and output immediately
        sent = 0
        recv = 0
        latencies = []

        for i in range(count):
            if self._stop_event.is_set():
                break

            sent += 1
            rtt = None
            err = None

            # Send single ping
            if ping3 is not None:
                try:
                    rtt = ping3.ping(dest_ip, timeout=3, unit='ms', seq=i)
                    if rtt is not None and rtt is not False:
                        latencies.append(rtt)
                    else:
                        err = "请求超时"
                except PermissionError:
                    err = "需要管理员权限"
                except Exception as e:
                    err = str(e)
            else:
                # Fallback: raw socket
                rtt_val, err = _raw_ping(dest_ip, timeout=3, seq=i)
                if rtt_val is not None:
                    rtt = rtt_val
                    latencies.append(rtt)

            # Output immediately
            if rtt is not None:
                recv += 1
                line = f"来自 {dest_ip} 的回复: 字节=56 时间={rtt:.1f}ms TTL=64 seq={i + 1}"
            elif err:
                line = f"请求超时: seq={i + 1} ({err})"
                logger.warning(f"[Ping] seq={i + 1} 错误: {err}")
            else:
                line = f"请求超时: seq={i + 1}"
            self.app.after(0, self._append_output, line)
            cur_avg = sum(latencies) / len(latencies) if latencies else None
            self.app.after(0, self._update_stats, sent, recv, cur_avg)

            if i < count - 1 and not self._stop_event.is_set():
                time.sleep(0.5)

        # Summary
        self.app.after(0, self._append_output, "")
        if latencies:
            avg = sum(latencies) / len(latencies)
            mn, mx = min(latencies), max(latencies)
            self.app.after(0, self._append_output,
                           f"--- 统计: 发送={sent}, 接收={recv}, "
                           f"丢包率={(sent - recv) / sent * 100:.1f}%, "
                           f"最小={mn:.1f}ms, 最大={mx:.1f}ms, 平均={avg:.1f}ms ---")
        else:
            self.app.after(0, self._append_output, f"--- 统计: 发送={sent}, 接收={recv}, 目标不可达 ---")

        logger.info(f"[Ping] 完成: 发送={sent}, 接收={recv}")
        self.app.after(0, self._finish)

    # ---------- Traceroute ----------

    def _run_tracert(self, target):
        import subprocess
        import platform
        from core.logger import logger

        self.app.after(0, self._append_output, f"--- Traceroute {target} ---")
        logger.info(f"[Traceroute] 开始追踪: {target}")

        try:
            dest_ip = socket.gethostbyname(target)
            self.app.after(0, self._append_output, f"追踪路由到 {target} [{dest_ip}], 最多 30 跳:\n")
        except socket.gaierror:
            self.app.after(0, self._append_output, f"错误: 无法解析 {target}")
            logger.error(f"[Traceroute] DNS 解析失败: {target}")
            self.app.after(0, self._finish)
            return

        system = platform.system()
        if system == "Windows":
            cmd = ["tracert", "-d", "-w", "3000", target]
        else:
            cmd = ["traceroute", "-n", "-w", "3", "-q", "1", "-m", "30", dest_ip]

        logger.info(f"[Traceroute] 执行命令: {' '.join(cmd)}")

        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, bufsize=1)
            for line in p.stdout:
                if self._stop_event.is_set():
                    p.terminate()
                    break
                line = line.rstrip()
                if not line:
                    continue
                logger.debug(f"[Traceroute] raw: {line}")
                # Parse: " 1  192.168.1.1  0.523 ms"
                m = re.match(r'\s*(\d+)\s+(\S+)\s+([\d.]+)\s*ms', line)
                if m:
                    hop, ip, rtt = int(m.group(1)), m.group(2), float(m.group(3))
                    self.app.after(0, self._append_output, f"  {hop:>2}   {ip:<16}  {rtt:.1f} ms")
                elif re.match(r'\s*\d+\s+\*', line):
                    m2 = re.match(r'\s*(\d+)', line)
                    hop = int(m2.group(1)) if m2 else '?'
                    self.app.after(0, self._append_output, f"  {hop:>2}   {'*':<16}  超时")
                # Skip header/summary lines
            rc = p.wait()
            logger.info(f"[Traceroute] 命令退出码: {rc}")
        except FileNotFoundError:
            err_msg = "错误: 系统未找到 traceroute 命令"
            self.app.after(0, self._append_output, err_msg)
            logger.error(f"[Traceroute] {err_msg}")
        except Exception as e:
            err_msg = f"错误: {e}"
            self.app.after(0, self._append_output, err_msg)
            logger.exception(f"[Traceroute] 执行异常")

        self.app.after(0, self._append_output, "\n--- Traceroute 完成 ---")
        self.app.after(0, self._finish)

    # ---------- TCPing ----------

    def _run_tcping(self, target, count, port):
        from core.logger import logger
        self.app.after(0, self._append_output, f"--- TCPing {target}:{port} ({count} 次) ---")
        logger.info(f"[TCPing] 开始测试: {target}:{port} x{count}")

        try:
            dest_ip = socket.gethostbyname(target)
        except socket.gaierror:
            self.app.after(0, self._append_output, f"错误: 无法解析 {target}")
            logger.error(f"[TCPing] DNS 解析失败: {target}")
            self.app.after(0, self._finish)
            return

        # Real-time TCPing: send one at a time and output immediately
        sent = 0
        recv = 0
        latencies = []

        for i in range(count):
            if self._stop_event.is_set():
                break

            sent += 1
            rtt = None
            err = None

            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                start = time.time()
                result = sock.connect_ex((dest_ip, port))
                elapsed = (time.time() - start) * 1000
                sock.close()

                if result == 0:
                    rtt = elapsed
                    recv += 1
                    latencies.append(rtt)
                else:
                    err = "连接被拒绝"
            except socket.timeout:
                err = "请求超时"
            except Exception as e:
                err = str(e)

            # Output immediately
            if rtt is not None:
                line = f"TCP 连接到 {target}:{port} 成功 - 时间={rtt:.1f}ms seq={i + 1}"
            elif err:
                line = f"TCP 连接到 {target}:{port} 失败 - {err}"
            else:
                line = f"TCP 连接到 {target}:{port} 失败 - 超时"
            self.app.after(0, self._append_output, line)
            cur_avg = sum(latencies) / len(latencies) if latencies else None
            self.app.after(0, self._update_stats, sent, recv, cur_avg)

            if i < count - 1 and not self._stop_event.is_set():
                time.sleep(0.5)

        # Summary
        self.app.after(0, self._append_output, "")
        if latencies:
            avg = sum(latencies) / len(latencies)
            mn, mx = min(latencies), max(latencies)
            self.app.after(0, self._append_output,
                           f"--- 统计: 发送={sent}, 接收={recv}, "
                           f"成功率={recv / sent * 100:.1f}%, "
                           f"最小={mn:.1f}ms, 最大={mx:.1f}ms, 平均={avg:.1f}ms ---")
        else:
            self.app.after(0, self._append_output, f"--- 统计: 发送={sent}, 接收={recv}, 目标不可达 ---")

        logger.info(f"[TCPing] 完成: 发送={sent}, 接收={recv}")
        self.app.after(0, self._finish)
