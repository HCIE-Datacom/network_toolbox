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

"""FTP Tool module - combined FTP/SFTP client and FTP server."""

import os
import time
import threading
import platform
import stat
import ftplib
import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox

try:
    import paramiko
except ImportError:
    paramiko = None

from core.base_module import ToolModule
from core.logger import logger


class FTPToolModule(ToolModule):
    name = "FTP 工具"
    icon = "📁"
    description = "FTP/SFTP 客户端连接远程服务器，或在本地启动 FTP 服务供局域网文件共享。"

    def build(self, parent):
        ctk.CTkLabel(parent, text=self.name,
                      font=("Helvetica", 22, "bold"), text_color="#1f1f1f").pack(anchor="w", pady=(0, 5))
        ctk.CTkLabel(parent, text=self.description,
                      font=("Helvetica", 13), text_color="#6b6b6b",
                      wraplength=620, justify="left").pack(anchor="w", pady=(0, 12))

        # ===== Top-level Mode Selector =====
        mode_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                 border_width=1, border_color="#e5e5e5")
        mode_card.pack(fill="x", pady=(0, 10))
        mode_inner = ctk.CTkFrame(mode_card, fg_color="transparent")
        mode_inner.pack(fill="x", padx=12, pady=10)

        ctk.CTkLabel(mode_inner, text="功能模式",
                     font=("Helvetica", 11, "bold"), text_color="#333333").pack(anchor="w", pady=(0, 4))

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

        # ===== Content Container =====
        content_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                    border_width=1, border_color="#e5e5e5")
        content_card.pack(fill="both", expand=True)

        content_inner = ctk.CTkFrame(content_card, fg_color="transparent")
        content_inner.pack(fill="both", expand=True, padx=12, pady=10)

        self._client_frame = ctk.CTkFrame(content_inner, fg_color="transparent")
        self._build_client_ui(self._client_frame)

        self._server_frame = ctk.CTkFrame(content_inner, fg_color="transparent")
        self._build_server_ui(self._server_frame)

        self._client = None
        self._sftp = None
        self._current_remote_dir = "/"
        self._server_thread = None

        self._set_mode("client")

    # ================================================================
    #  Client UI
    # ================================================================

    def _build_client_ui(self, parent):
        # --- Protocol selector ---
        ctk.CTkLabel(parent, text="协议", font=("Helvetica", 10, "bold"),
                     text_color="#333333").pack(anchor="w", pady=(0, 2))
        proto_row = ctk.CTkFrame(parent, fg_color="#f0f0f0", corner_radius=6)
        proto_row.pack(fill="x", pady=(0, 6))
        self._proto_var = ctk.StringVar(value="ftp")
        self._proto_btns = {}
        for val, txt in [("ftp", "FTP"), ("sftp", "SFTP")]:
            btn = ctk.CTkButton(proto_row, text=txt, width=0, height=24,
                                font=("Helvetica", 10), corner_radius=4,
                                fg_color="transparent", text_color="#333333",
                                hover_color="#e0e0e0",
                                command=lambda v=val: self._set_proto(v))
            btn.pack(side="left", expand=True, fill="x", padx=1, pady=1)
            self._proto_btns[val] = btn
        self._update_proto_buttons()

        # --- Connection form ---
        conn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        conn_frame.pack(fill="x", pady=(0, 6))
        conn_frame.grid_columnconfigure(0, weight=1)

        r1 = ctk.CTkFrame(conn_frame, fg_color="transparent")
        r1.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        r1.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(r1, text="服务器", font=("Helvetica", 10, "bold"),
                     text_color="#333333", width=45, anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self._host_var = ctk.StringVar(value="")
        self._host_entry = ctk.CTkEntry(r1, textvariable=self._host_var,
                                         placeholder_text="IP 或域名", font=("Helvetica", 11),
                                         corner_radius=6, height=28, border_color="#d1d5db", border_width=1)
        self._host_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ctk.CTkLabel(r1, text="端口", font=("Helvetica", 10, "bold"),
                     text_color="#333333", width=30, anchor="w").grid(row=0, column=2, sticky="w", padx=(0, 4))
        self._port_var = ctk.StringVar(value="21")
        self._port_entry = ctk.CTkEntry(r1, textvariable=self._port_var, width=55,
                                         font=("Helvetica", 11), corner_radius=6,
                                         height=28, border_color="#d1d5db", border_width=1)
        self._port_entry.grid(row=0, column=3)

        r2 = ctk.CTkFrame(conn_frame, fg_color="transparent")
        r2.grid(row=1, column=0, sticky="ew")
        r2.grid_columnconfigure(1, weight=1)
        r2.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(r2, text="账号", font=("Helvetica", 10, "bold"),
                     text_color="#333333", width=45, anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self._user_var = ctk.StringVar(value="")
        self._user_entry = ctk.CTkEntry(r2, textvariable=self._user_var,
                                         placeholder_text="用户名", font=("Helvetica", 11),
                                         corner_radius=6, height=28, border_color="#d1d5db", border_width=1)
        self._user_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ctk.CTkLabel(r2, text="密码", font=("Helvetica", 10, "bold"),
                     text_color="#333333", width=30, anchor="w").grid(row=0, column=2, sticky="w", padx=(0, 4))
        self._pass_var = ctk.StringVar(value="")
        self._pass_entry = ctk.CTkEntry(r2, textvariable=self._pass_var,
                                         placeholder_text="密码", font=("Helvetica", 11),
                                         corner_radius=6, height=28, border_color="#d1d5db", border_width=1)
        self._pass_entry.grid(row=0, column=3, sticky="ew", padx=(0, 6))
        self._connect_btn = ctk.CTkButton(r2, text="连接", command=self._toggle_connect,
                                           width=65, height=28, font=("Helvetica", 11, "bold"),
                                           corner_radius=6, fg_color="#10a37f", hover_color="#0d8c6d")
        self._connect_btn.grid(row=0, column=4)

        self._conn_status = ctk.CTkLabel(conn_frame, text="状态: 未连接",
                                          font=("Helvetica", 9), text_color="#999999")
        self._conn_status.grid(row=2, column=0, sticky="w", pady=(1, 0))

        # --- Remote browser ---
        ctk.CTkLabel(parent, text="远程文件", font=("Helvetica", 10, "bold"),
                     text_color="#666666").pack(anchor="w", pady=(6, 1))

        nav = ctk.CTkFrame(parent, fg_color="transparent")
        nav.pack(fill="x", pady=(0, 2))
        self._path_label = ctk.CTkLabel(nav, text="/", font=("Courier", 10),
                                         text_color="#333333", anchor="w")
        self._path_label.pack(side="left", fill="x", expand=True)
        for txt, cmd in [("🔄", self._refresh_dir), ("⬆", self._go_up)]:
            ctk.CTkButton(nav, text=txt, command=cmd, width=28, height=20,
                          font=("Helvetica", 10), corner_radius=4,
                          fg_color="#e5e5e5", hover_color="#d1d5db",
                          text_color="#333333").pack(side="right", padx=(2, 0))

        remote_container = ctk.CTkFrame(parent, fg_color="#f9f9f9",
                                         corner_radius=6, border_width=1, border_color="#e5e5e5")
        remote_container.pack(fill="both", expand=True)

        style = ttk.Style()
        style.configure("Treeview", font=("Helvetica", 10), rowheight=20,
                        background="#f9f9f9", fieldbackground="#f9f9f9")
        style.configure("Treeview.Heading", font=("Helvetica", 9, "bold"))

        self._tree = ttk.Treeview(remote_container, columns=("name", "size", "date"),
                                   show="headings", selectmode="browse")
        self._tree.heading("name", text="名称", anchor="w")
        self._tree.heading("size", text="大小", anchor="e")
        self._tree.heading("date", text="修改时间", anchor="w")
        self._tree.column("name", width=240, anchor="w")
        self._tree.column("size", width=70, anchor="e")
        self._tree.column("date", width=130, anchor="w")

        vsb = ttk.Scrollbar(remote_container, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True, padx=(2, 0), pady=2)
        vsb.pack(side="right", fill="y", padx=(0, 2), pady=2)
        self._tree.bind("<Double-1>", self._on_tree_double_click)

        # --- Separator + Action buttons ---
        sep_frame = ctk.CTkFrame(parent, fg_color="transparent")
        sep_frame.pack(fill="x", pady=(4, 1))
        ctk.CTkFrame(sep_frame, height=1, fg_color="#e5e5e5").pack(fill="x")

        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 4))
        self._upload_btn = ctk.CTkButton(btn_row, text="⬆ 上传到远程", command=self._upload_file,
                                          width=110, height=22, font=("Helvetica", 10, "bold"),
                                          corner_radius=4, fg_color="#10a37f", hover_color="#0d8c6d")
        self._upload_btn.pack(side="left")
        self._download_btn = ctk.CTkButton(btn_row, text="⬇ 下载到本地", command=self._download_file,
                                            width=110, height=22, font=("Helvetica", 10, "bold"),
                                            corner_radius=4, fg_color="#3b82f6", hover_color="#2563eb")
        self._download_btn.pack(side="left", padx=(8, 0))
        self._delete_btn = ctk.CTkButton(btn_row, text="🗑 删除远程", command=self._delete_file,
                                          width=85, height=22, font=("Helvetica", 10),
                                          corner_radius=4, fg_color="#ef4444", hover_color="#dc2626")
        self._delete_btn.pack(side="right")

        # --- Local browser ---
        self._local_label = ctk.CTkLabel(parent, text="本地文件", font=("Helvetica", 10, "bold"),
                     text_color="#666666").pack(anchor="w", pady=(2, 1))

        local_nav = ctk.CTkFrame(parent, fg_color="transparent")
        local_nav.pack(fill="x", pady=(0, 2))
        self._local_path_label = ctk.CTkLabel(local_nav, text=os.path.expanduser("~/Desktop"),
                                               font=("Courier", 10), text_color="#333333", anchor="w")
        self._local_path_label.pack(side="left", fill="x", expand=True)
        for txt, cmd in [("...", self._browse_local), ("🔄", self._refresh_local), ("⬆", self._go_up_local)]:
            ctk.CTkButton(local_nav, text=txt, command=cmd, width=28, height=20,
                          font=("Helvetica", 10), corner_radius=4,
                          fg_color="#e5e5e5", hover_color="#d1d5db",
                          text_color="#333333").pack(side="right", padx=(2, 0))

        local_container = ctk.CTkFrame(parent, fg_color="#f9f9f9",
                                        corner_radius=6, border_width=1, border_color="#e5e5e5")
        local_container.pack(fill="both", expand=True)

        self._local_tree = ttk.Treeview(local_container, columns=("name", "size", "date"),
                                         show="headings", selectmode="browse")
        self._local_tree.heading("name", text="名称", anchor="w")
        self._local_tree.heading("size", text="大小", anchor="e")
        self._local_tree.heading("date", text="修改时间", anchor="w")
        self._local_tree.column("name", width=240, anchor="w")
        self._local_tree.column("size", width=70, anchor="e")
        self._local_tree.column("date", width=130, anchor="w")

        local_vsb = ttk.Scrollbar(local_container, orient="vertical", command=self._local_tree.yview)
        self._local_tree.configure(yscrollcommand=local_vsb.set)
        self._local_tree.pack(side="left", fill="both", expand=True, padx=(2, 0), pady=2)
        local_vsb.pack(side="right", fill="y", padx=(0, 2), pady=2)
        self._local_tree.bind("<Double-1>", self._on_local_double_click)

        self._local_dir = os.path.expanduser("~/Desktop")

        # --- Log area ---
        mono = ("SF Mono", max(9, 9)) if platform.system() == "Darwin" else ("Consolas", max(9, 9))
        self._clog = ctk.CTkTextbox(parent, font=mono, wrap="word", corner_radius=6,
                                     fg_color="#f9f9f9", text_color="#333333",
                                     border_width=1, border_color="#e5e5e5", height=50)
        self._clog.pack(fill="x")

        self._refresh_local()

    # ================================================================
    #  Server UI
    # ================================================================

    def _build_server_ui(self, parent):
        ctk.CTkLabel(parent, text="服务配置",
                     font=("Helvetica", 12, "bold"), text_color="#333333").pack(anchor="w", pady=(0, 8))

        pr = ctk.CTkFrame(parent, fg_color="transparent")
        pr.pack(fill="x")
        pr.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(pr, text="监听端口:", font=("Helvetica", 13),
                     text_color="#333333").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self._srv_port_var = ctk.StringVar(value="21")
        self._srv_port_entry = ctk.CTkEntry(pr, textvariable=self._srv_port_var, width=100,
                                             font=("Helvetica", 13), corner_radius=8,
                                             height=38, border_color="#d1d5db", border_width=1)
        self._srv_port_entry.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(pr, text="(FTP 默认端口)", font=("Helvetica", 11),
                     text_color="#8e8e8e").grid(row=0, column=2, sticky="w", padx=(10, 0))

        dr = ctk.CTkFrame(parent, fg_color="transparent")
        dr.pack(fill="x", pady=(12, 0))
        dr.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(dr, text="根目录:", font=("Helvetica", 13),
                     text_color="#333333").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self._srv_dir_var = ctk.StringVar(value=os.path.expanduser("~/Desktop"))
        self._srv_dir_entry = ctk.CTkEntry(dr, textvariable=self._srv_dir_var,
                                            font=("Helvetica", 13), corner_radius=8,
                                            height=38, border_color="#d1d5db", border_width=1)
        self._srv_dir_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ctk.CTkButton(dr, text="浏览", command=self._browse_srv_dir, width=70, height=38,
                       font=("Helvetica", 13), corner_radius=8, fg_color="#e5e5e5",
                       hover_color="#d1d5db", text_color="#333333").grid(row=0, column=2)

        ap = ctk.CTkFrame(parent, fg_color="transparent")
        ap.pack(fill="x", pady=(12, 0))
        ctk.CTkLabel(ap, text="用户名:", font=("Helvetica", 13), text_color="#333333").pack(side="left", padx=(0, 10))
        self._srv_user_var = ctk.StringVar(value="admin")
        ctk.CTkEntry(ap, textvariable=self._srv_user_var, width=120,
                      font=("Helvetica", 13), corner_radius=8,
                      height=38, border_color="#d1d5db", border_width=1).pack(side="left")
        ctk.CTkLabel(ap, text="  密码:", font=("Helvetica", 13), text_color="#333333").pack(side="left", padx=(10, 10))
        self._srv_pass_var = ctk.StringVar(value="123456")
        ctk.CTkEntry(ap, textvariable=self._srv_pass_var, width=120,
                      font=("Helvetica", 13), corner_radius=8,
                      height=38, border_color="#d1d5db", border_width=1).pack(side="left")

        tr = ctk.CTkFrame(parent, fg_color="transparent")
        tr.pack(fill="x", pady=(15, 0))
        self._srv_toggle_btn = ctk.CTkButton(tr, text="启动服务", command=self._toggle_server,
                                              width=120, height=38, font=("Helvetica", 13, "bold"),
                                              corner_radius=8, fg_color="#10a37f", hover_color="#0d8c6d")
        self._srv_toggle_btn.pack(side="left")
        self._srv_status_label = ctk.CTkLabel(tr, text="状态: 已停止",
                                               font=("Helvetica", 13), text_color="#666666")
        self._srv_status_label.pack(side="left", padx=(15, 0))

        ctk.CTkLabel(parent, text="运行日志", font=("Helvetica", 12, "bold"),
                     text_color="#333333").pack(anchor="w", pady=(12, 8))
        mono = ("SF Mono", max(11, 11)) if platform.system() == "Darwin" else ("Consolas", max(11, 11))
        self._srv_log = ctk.CTkTextbox(parent, font=mono, wrap="word", corner_radius=8,
                                        fg_color="white", text_color="#333333",
                                        border_width=1, border_color="#e5e5e5", activate_scrollbars=True)
        self._srv_log.pack(fill="both", expand=True, pady=(0, 8))
        self._srv_log.configure(state="disabled")

    # ================================================================
    #  Mode Switching
    # ================================================================

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

    def _set_proto(self, proto):
        self._proto_var.set(proto)
        self._update_proto_buttons()
        if proto == "ftp" and self._port_var.get() in ("", "22"):
            self._port_var.set("21")
        elif proto == "sftp" and self._port_var.get() in ("", "21"):
            self._port_var.set("22")

    def _update_proto_buttons(self):
        current = self._proto_var.get()
        for val, btn in self._proto_btns.items():
            if val == current:
                btn.configure(fg_color="#10a37f", text_color="white", hover_color="#0d8c6d")
            else:
                btn.configure(fg_color="transparent", text_color="#333333", hover_color="#e0e0e0")

    # ================================================================
    #  Client - Connect / Disconnect
    # ================================================================

    def _log(self, msg):
        def _up():
            self._clog.insert("end", msg + "\n")
            self._clog.see("end")
        self.app.after(0, _up)

    @staticmethod
    def _ts():
        return time.strftime("%H:%M:%S")

    def _toggle_connect(self):
        if self._client is not None:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        host = self._host_var.get().strip()
        port_str = self._port_var.get().strip()
        proto = self._proto_var.get()
        if not host:
            messagebox.showwarning("提示", "请输入主机地址")
            return
        if not port_str.isdigit() or not (1 <= int(port_str) <= 65535):
            messagebox.showwarning("提示", "请输入有效的端口号 (1-65535)")
            return
        port = int(port_str)
        if proto == "sftp" and paramiko is None:
            messagebox.showerror("错误", "SFTP 需要 paramiko 库，请执行: pip3 install paramiko")
            return
        self._connect_btn.configure(state="disabled", text="连接中...")
        threading.Thread(target=self._do_connect, args=(host, port, proto), daemon=True).start()

    def _do_connect(self, host, port, proto):
        user = self._user_var.get().strip()
        pwd = self._pass_var.get()
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
                logger.info(f"[FTP客户端] 登录成功: {host} ({user or '匿名'})")
                self._sftp = None
            else:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(host, port=port, username=user, password=pwd, timeout=10)
                self._client = ssh
                self._sftp = ssh.open_sftp()
                self.app.after(0, self._log, f"{ts}  [SFTP] 已连接到 {host}:{port}")
                logger.info(f"[SFTP客户端] 已连接到 {host}:{port}")
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
        self._connect_btn.configure(text="断开", fg_color="#dc2626", hover_color="#b91c1c", state="normal")
        addr = f"{self._host_var.get().strip()}:{self._port_var.get().strip()}"
        proto = "FTP" if isinstance(self._client, ftplib.FTP) else "SFTP"
        self._conn_status.configure(text=f"状态: 已连接 → {addr} ({proto})", text_color="#10a37f")

    def _on_disconnected(self):
        self._connect_btn.configure(text="连接", fg_color="#10a37f", hover_color="#0d8c6d", state="normal")
        self._conn_status.configure(text="状态: 未连接", text_color="#999999")
        self._tree.delete(*self._tree.get_children())

    # ================================================================
    #  Client - Remote File Browser
    # ================================================================

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
        self._tree.delete(*self._tree.get_children())
        if error:
            self._log(f"{self._ts()}  [错误] 列出目录失败: {error}")
            return

        dirs = []
        files = []
        for name, is_dir, size, date_str in items:
            (dirs if is_dir else files).append((name, size, date_str))

        dirs.sort(key=lambda x: x[0].lower())
        files.sort(key=lambda x: x[0].lower())

        if self._current_remote_dir != "/":
            self._tree.insert("", "end", iid="__up__", values=("..", "", ""), tags=("dir",))

        for name, size, date_str in dirs:
            self._tree.insert("", "end", iid=name,
                              values=(f"📁 {name}", self._fmt_size(size), date_str), tags=("dir",))
        for name, size, date_str in files:
            self._tree.insert("", "end", iid=name,
                              values=(f"📄 {name}", self._fmt_size(size), date_str), tags=("file",))
        self._path_label.configure(text=self._current_remote_dir)

    def _fmt_size(self, size):
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f} GB"

    def _on_tree_double_click(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid == "__up__":
            self._go_up()
            return
        if "dir" in self._tree.item(iid, "tags"):
            if self._current_remote_dir == "/":
                self._current_remote_dir = "/" + iid
            else:
                self._current_remote_dir = self._current_remote_dir.rstrip("/") + "/" + iid
            self._refresh_dir()

    def _go_up(self):
        if self._current_remote_dir and self._current_remote_dir != "/":
            parent = os.path.dirname(self._current_remote_dir.rstrip("/"))
            self._current_remote_dir = parent if parent else "/"
            self._refresh_dir()

    # ================================================================
    #  Client - Upload / Download / Delete
    # ================================================================

    def _selected_file(self):
        sel = self._tree.selection()
        if not sel or sel[0] == "__up__":
            return None
        if "dir" in self._tree.item(sel[0], "tags"):
            return None
        return sel[0]

    def _selected_local_file(self):
        sel = self._local_tree.selection()
        if not sel or sel[0] == "__up__":
            return None
        if "dir" in self._local_tree.item(sel[0], "tags"):
            return None
        return sel[0]

    # -- Local browser --

    def _browse_local(self):
        path = filedialog.askdirectory(title="选择本地目录")
        if path:
            self._local_dir = path
            self._refresh_local()

    def _refresh_local(self):
        self._do_list_local()

    def _do_list_local(self):
        items = []
        try:
            for entry in sorted(os.listdir(self._local_dir), key=lambda x: x.lower()):
                full = os.path.join(self._local_dir, entry)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                is_dir = stat.S_ISDIR(st.st_mode)
                mt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
                items.append((entry, is_dir, st.st_size, mt))
        except Exception as e:
            self.app.after(0, self._log, f"{self._ts()}  [错误] 列出本地目录失败: {e}")
            return
        self.app.after(0, self._show_local_list, items)

    def _show_local_list(self, items):
        self._local_tree.delete(*self._local_tree.get_children())
        dirs = [(n, s, d) for n, i, s, d in items if i]
        files = [(n, s, d) for n, i, s, d in items if not i]

        parent_dir = os.path.dirname(self._local_dir)
        if parent_dir != self._local_dir:
            self._local_tree.insert("", "end", iid="__up__", values=("..", "", ""), tags=("dir",))

        for name, size, date_str in dirs:
            self._local_tree.insert("", "end", iid=name,
                                     values=(f"📁 {name}", self._fmt_size(size), date_str), tags=("dir",))
        for name, size, date_str in files:
            self._local_tree.insert("", "end", iid=name,
                                     values=(f"📄 {name}", self._fmt_size(size), date_str), tags=("file",))
        self._local_path_label.configure(text=self._local_dir)

    def _on_local_double_click(self, event):
        sel = self._local_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid == "__up__":
            self._go_up_local()
            return
        if "dir" in self._local_tree.item(iid, "tags"):
            self._local_dir = os.path.join(self._local_dir, iid)
            self._refresh_local()

    def _go_up_local(self):
        parent = os.path.dirname(self._local_dir)
        if parent != self._local_dir:
            self._local_dir = parent
            self._refresh_local()

    # -- Upload / Download --

    def _upload_file(self):
        if self._client is None:
            messagebox.showwarning("提示", "请先连接到服务器")
            return
        name = self._selected_local_file()
        if name is None:
            messagebox.showwarning("提示", "请先在本地文件中选择要上传的文件")
            return
        local_path = os.path.join(self._local_dir, name)
        threading.Thread(target=self._do_upload, args=(local_path, name), daemon=True).start()

    def _download_file(self):
        name = self._selected_file()
        if name is None:
            messagebox.showwarning("提示", "请先在远程文件中选择要下载的文件")
            return
        if not os.path.isdir(self._local_dir):
            messagebox.showwarning("提示", "本地目录不存在，请重新选择")
            return
        threading.Thread(target=self._do_download, args=(name,), daemon=True).start()

    # ========== Transfer dialog ==========

    def _open_transfer_window(self, direction, fname, fsize):
        """Open a floating transfer progress dialog."""
        win = ctk.CTkToplevel(self.app)
        win.title("传输进度")
        win.geometry("420x200")
        win.resizable(False, False)
        win.configure(fg_color="#f9f9f9")
        win.transient(self.app)

        # Content
        inner = ctk.CTkFrame(win, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(inner, text=f"{direction}: {fname}",
                     font=("Helvetica", 13, "bold"), text_color="#1f1f1f").pack(anchor="w")

        ctk.CTkLabel(inner, text=f"大小: {self._fmt_size(fsize)}",
                     font=("Helvetica", 11), text_color="#888888").pack(anchor="w", pady=(4, 12))

        self._xfer_bar = ctk.CTkProgressBar(inner, height=12,
                                             fg_color="#e5e5e5", progress_color="#10a37f")
        self._xfer_bar.pack(fill="x", pady=(0, 6))
        self._xfer_bar.set(0)

        self._xfer_info = ctk.CTkLabel(inner, text="0%  —  —",
                                        font=("Courier", 12), text_color="#333333")
        self._xfer_info.pack(anchor="w")

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x", pady=(12, 0))

        ctk.CTkButton(btn_row, text="取消传输", command=lambda: self._cancel_transfer(win),
                       width=100, height=30, font=("Helvetica", 11),
                       corner_radius=6, fg_color="#ef4444", hover_color="#dc2626").pack(side="right")

        self._xfer_window = win
        self._xfer_cancel = False

    def _cancel_transfer(self, win=None):
        self._xfer_cancel = True
        if win and win.winfo_exists():
            ctk.CTkLabel(win, text="正在取消...", font=("Helvetica", 12, "bold"),
                         text_color="#e74c3c").pack(pady=10)
            # Close after a short delay
            win.after(1500, win.destroy)

    def _update_transfer_window(self, transferred, total, start_time):
        if not hasattr(self, "_xfer_window") or not self._xfer_window.winfo_exists():
            return
        pct = min(transferred / total, 1.0) if total > 0 else 0
        elapsed = time.time() - start_time
        speed = transferred / elapsed if elapsed > 0 else 0
        if speed >= 1024 * 1024:
            speed_str = f"{speed / (1024*1024):.1f} MB/s"
        elif speed >= 1024:
            speed_str = f"{speed / 1024:.1f} KB/s"
        else:
            speed_str = f"{speed:.0f} B/s"
        self._xfer_bar.set(pct)
        self._xfer_info.configure(text=f"{pct*100:.0f}%  |  {speed_str}")

    def _close_transfer_window(self):
        if hasattr(self, "_xfer_window") and self._xfer_window.winfo_exists():
            self._xfer_window.destroy()
        self._xfer_cancel = False

    # ========== Transfer ==========

    def _do_upload(self, local_path, fname):
        ts = self._ts()
        remote_path = self._current_remote_dir.rstrip("/") + "/" + fname
        try:
            fsize = os.path.getsize(local_path)
        except Exception as e:
            self.app.after(0, self._log, f"{ts}  [上传] 失败: 无法读取本地文件 ({e})")
            logger.error(f"[FTP/SFTP上传] 无法读取本地文件 {fname}: {e}")
            return

        self.app.after(0, self._log, f"{ts}  [上传] 开始: {fname} ({self._fmt_size(fsize)})")
        self.app.after(0, self._open_transfer_window, "⬆ 上传", fname, fsize)

        self._xfer_cancel = False
        try:
            if isinstance(self._client, ftplib.FTP):
                transferred = [0]
                start = [time.time()]

                def cb(data):
                    if self._xfer_cancel:
                        self._client.abort()
                        return
                    transferred[0] += len(data)
                    self.app.after(0, self._update_transfer_window, transferred[0], fsize, start[0])

                with open(local_path, "rb") as f:
                    self._client.storbinary(f"STOR {remote_path}", f, blocksize=8192, callback=cb)
            else:
                start = [time.time()]
                transferred = [0]

                def cb(done, total):
                    if self._xfer_cancel:
                        raise KeyboardInterrupt()
                    transferred[0] = done
                    self.app.after(0, self._update_transfer_window, done, total, start[0])

                self._sftp.put(local_path, remote_path, callback=cb)

            self.app.after(0, self._log, f"{ts}  [上传] 完成: {fname}")
            logger.info(f"[FTP/SFTP上传] 完成: {fname} ({self._fmt_size(fsize)})")
            self.app.after(0, self._refresh_dir)
        except Exception as e:
            self.app.after(0, self._log, f"{ts}  [上传] 失败: {e}")
            logger.error(f"[FTP/SFTP上传] 失败: {fname}: {e}")
        finally:
            self.app.after(0, self._close_transfer_window)

    def _do_download(self, name):
        ts = self._ts()
        remote_path = self._current_remote_dir.rstrip("/") + "/" + name
        local_path = os.path.join(self._local_dir, name)

        try:
            if isinstance(self._client, ftplib.FTP):
                fsize = self._client.size(remote_path)
            else:
                fsize = self._sftp.stat(remote_path).st_size
        except Exception as e:
            self.app.after(0, self._log, f"{ts}  [下载] 失败: 无法获取文件信息 ({e})")
            return

        self.app.after(0, self._log, f"{ts}  [下载] 开始: {name}")
        self.app.after(0, self._open_transfer_window, "⬇ 下载", name, fsize)

        self._xfer_cancel = False
        try:
            if isinstance(self._client, ftplib.FTP):
                transferred = [0]
                start = [time.time()]

                def cb(data):
                    if self._xfer_cancel:
                        self._client.abort()
                        return
                    transferred[0] += len(data)
                    self.app.after(0, self._update_transfer_window, transferred[0], fsize, start[0])

                with open(local_path, "wb") as f:
                    self._client.retrbinary(f"RETR {remote_path}", cb, blocksize=8192)
            else:
                start = [time.time()]
                transferred = [0]

                def cb(done, total):
                    if self._xfer_cancel:
                        raise KeyboardInterrupt()
                    transferred[0] = done
                    self.app.after(0, self._update_transfer_window, done, total, start[0])

                self._sftp.get(remote_path, local_path, callback=cb)

            self.app.after(0, self._log, f"{ts}  [下载] 完成: {name} → {local_path}")
            logger.info(f"[FTP/SFTP下载] 完成: {name}")
        except Exception as e:
            self.app.after(0, self._log, f"{ts}  [下载] 失败: {e}")
            logger.error(f"[FTP/SFTP下载] 失败: {name}: {e}")
        finally:
            self.app.after(0, self._close_transfer_window)

    def _delete_file(self):
        name = self._selected_file()
        if name is None:
            messagebox.showwarning("提示", "请先选择要删除的文件")
            return
        if not messagebox.askyesno("确认", f"确定要删除远程文件 {name} 吗？"):
            return
        threading.Thread(target=self._do_delete, args=(name,), daemon=True).start()

    def _do_delete(self, name):
        ts = self._ts()
        remote_path = self._current_remote_dir.rstrip("/") + "/" + name
        try:
            if isinstance(self._client, ftplib.FTP):
                self._client.delete(remote_path)
            else:
                self._sftp.remove(remote_path)
            self.app.after(0, self._log, f"{ts}  [删除] 已删除: {name}")
            self.app.after(0, self._refresh_dir)
        except Exception as e:
            self.app.after(0, self._log, f"{ts}  [删除] 失败: {e}")

    # ================================================================
    #  Server
    # ================================================================

    def _toggle_server(self):
        if self._server_thread and self._server_thread.is_alive():
            self._stop_server()
        else:
            self._start_server()

    def _start_server(self):
        from pyftpdlib.authorizers import DummyAuthorizer
        from pyftpdlib.handlers import FTPHandler
        from pyftpdlib.servers import FTPServer

        port_str = self._srv_port_var.get().strip()
        if not port_str.isdigit() or not (1 <= int(port_str) <= 65535):
            messagebox.showwarning("提示", "请输入有效的端口号 (1-65535)")
            return
        root_dir = self._srv_dir_var.get().strip()
        if not root_dir or not os.path.isdir(root_dir):
            messagebox.showwarning("提示", "请选择一个有效的目录作为 FTP 根目录")
            return
        user = self._srv_user_var.get().strip() or "admin"
        pwd = self._srv_pass_var.get().strip() or "123456"

        self._srv_log_clear()

        authorizer = DummyAuthorizer()
        authorizer.add_user(user, pwd, root_dir, perm="elradfmw")
        authorizer.add_anonymous(root_dir, perm="elr")

        _log_cb = self._srv_log_append
        _ts_func = self._ts

        class _FTPHandler(FTPHandler):
            def on_connect(inner):
                super(_FTPHandler, inner).on_connect()
                t = _ts_func()
                ip, pr = inner.remote_ip, inner.remote_port
                _log_cb(f"{t}  [连接] 新客户端连接  |  {ip}:{pr}")

            def on_disconnect(inner):
                t = _ts_func()
                ip, pr = inner.remote_ip, inner.remote_port
                _log_cb(f"{t}  [断开] 客户端断开  |  {ip}:{pr}")
                super(_FTPHandler, inner).on_disconnect()

            def ftp_PASS(inner, line):
                result = super(_FTPHandler, inner).ftp_PASS(line)
                if inner.authenticated:
                    t = _ts_func()
                    ip, pr = inner.remote_ip, inner.remote_port
                    _log_cb(f"{t}  [登录] 用户 '{inner.username}' 认证成功  |  {ip}:{pr}")
                return result

            def ftp_RETR(inner, file):
                t = _ts_func()
                _log_cb(f"{t}  [下载] {inner.username or '匿名'} 下载文件: {file}")
                return super(_FTPHandler, inner).ftp_RETR(file)

            def ftp_STOR(inner, file):
                t = _ts_func()
                _log_cb(f"{t}  [上传] {inner.username or '匿名'} 上传文件: {file}")
                return super(_FTPHandler, inner).ftp_STOR(file)

            def ftp_DELE(inner, path):
                t = _ts_func()
                _log_cb(f"{t}  [删除] {inner.username or '匿名'} 删除文件: {path}")
                return super(_FTPHandler, inner).ftp_DELE(path)

            def ftp_RNTO(inner, line):
                t = _ts_func()
                _log_cb(f"{t}  [重命名] {inner.username or '匿名'} 重命名: {line}")
                return super(_FTPHandler, inner).ftp_RnTO(line)

            def ftp_MKD(inner, path):
                t = _ts_func()
                _log_cb(f"{t}  [新建目录] {inner.username or '匿名'} 创建目录: {path}")
                return super(_FTPHandler, inner).ftp_MKD(path)

            def ftp_RMD(inner, path):
                t = _ts_func()
                _log_cb(f"{t}  [删除目录] {inner.username or '匿名'} 删除目录: {path}")
                return super(_FTPHandler, inner).ftp_RMD(path)

        _FTPHandler.authorizer = authorizer
        _FTPHandler.passive_ports = range(60000, 60100)

        try:
            server = FTPServer(("0.0.0.0", int(port_str)), _FTPHandler)
        except Exception as e:
            messagebox.showerror("错误", f"FTP 服务器启动失败: {e}")
            return

        self._server_instance = server

        logger.info(f"[FTP服务器] 启动服务, 端口: {port_str}, 根目录: {root_dir}")
        ts = self._ts()
        for line in [
            f"{ts}  [启动] FTP 服务器正在监听 0.0.0.0:{port_str}",
            f"{ts}  [信息] 根目录: {root_dir}",
            f"{ts}  [信息] 用户: {user} / 匿名访问已启用",
            f"{ts}  [信息] 被动端口: 60000-60099",
        ]:
            self._srv_log_append(line)

        self._srv_toggle_btn.configure(text="停止服务", fg_color="#dc2626", hover_color="#b91c1c")
        self._srv_status_label.configure(text="状态: 运行中", text_color="#10a37f")
        self._srv_port_entry.configure(state="disabled")
        self._srv_dir_entry.configure(state="disabled")

        self._server_thread = threading.Thread(target=self._serve_loop, args=(server,), daemon=True)
        self._server_thread.start()

    def _serve_loop(self, server):
        try:
            server.serve_forever()
        except Exception as e:
            self.app.after(0, self._srv_log_append, f"{self._ts()}  [错误] {e}")

    def _stop_server(self):
        if hasattr(self, "_server_instance") and self._server_instance:
            try:
                self._server_instance.close_all()
            except Exception:
                pass
            self._server_instance = None
        self._srv_toggle_btn.configure(text="启动服务", fg_color="#10a37f", hover_color="#0d8c6d")
        self._srv_status_label.configure(text="状态: 已停止", text_color="#666666")
        self._srv_port_entry.configure(state="normal")
        self._srv_dir_entry.configure(state="normal")
        self._srv_log_append(f"{self._ts()}  [停止] FTP 服务器已停止")
        logger.info("[FTP服务器] 停止服务")

    def _srv_log_append(self, text):
        def _up():
            self._srv_log.configure(state="normal")
            self._srv_log.insert("end", text + "\n")
            self._srv_log.see("end")
            self._srv_log.configure(state="disabled")
        self.app.after(0, _up)

    def _srv_log_clear(self):
        self._srv_log.configure(state="normal")
        self._srv_log.delete("0.0", "end")
        self._srv_log.configure(state="disabled")

    def _browse_srv_dir(self):
        path = filedialog.askdirectory(title="选择 FTP 根目录")
        if path:
            self._srv_dir_var.set(path)

    def on_hide(self):
        if self._client is not None:
            self._disconnect()
        if self._server_thread and self._server_thread.is_alive():
            self._stop_server()
