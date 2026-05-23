"""FTP Server module - run local FTP file server for LAN file sharing."""

import os
import time
import threading
import platform
import customtkinter as ctk
from tkinter import messagebox, filedialog
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

from core.base_module import ToolModule


class FTPServerModule(ToolModule):
    name = "FTP 服务器"
    icon = "📁"
    description = "在本机启动 FTP 文件服务器，允许局域网内其他设备上传和下载文件。"

    def build(self, parent):
        # Title
        ctk.CTkLabel(parent, text=self.name,
                      font=("Helvetica", 22, "bold"), text_color="#1f1f1f").pack(anchor="w", pady=(0, 5))
        ctk.CTkLabel(parent, text=self.description,
                      font=("Helvetica", 13), text_color="#6b6b6b",
                      wraplength=620, justify="left").pack(anchor="w", pady=(0, 20))

        # Config card
        ftp_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                 border_width=1, border_color="#e5e5e5")
        ftp_card.pack(fill="x", pady=(0, 15))
        ftp_inner = ctk.CTkFrame(ftp_card, fg_color="transparent")
        ftp_inner.pack(fill="x", padx=15, pady=15)
        ctk.CTkLabel(ftp_inner, text="服务配置",
                      font=("Helvetica", 12, "bold"), text_color="#333333").pack(anchor="w", pady=(0, 8))

        # Port
        pr = ctk.CTkFrame(ftp_inner, fg_color="transparent")
        pr.pack(fill="x")
        pr.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(pr, text="监听端口:", font=("Helvetica", 13),
                      text_color="#333333").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self._port_var = ctk.StringVar(value="21")
        self._port_entry = ctk.CTkEntry(pr, textvariable=self._port_var, width=100,
                                         font=("Helvetica", 13), corner_radius=8,
                                         height=38, border_color="#d1d5db", border_width=1)
        self._port_entry.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(pr, text="(FTP 默认端口)",
                      font=("Helvetica", 11), text_color="#8e8e8e").grid(row=0, column=2, sticky="w", padx=(10, 0))

        # Root dir
        dr = ctk.CTkFrame(ftp_inner, fg_color="transparent")
        dr.pack(fill="x", pady=(12, 0))
        dr.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(dr, text="根目录:", font=("Helvetica", 13),
                      text_color="#333333").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self._dir_var = ctk.StringVar(value=os.path.expanduser("~/Desktop"))
        self._dir_entry = ctk.CTkEntry(dr, textvariable=self._dir_var,
                                        font=("Helvetica", 13), corner_radius=8,
                                        height=38, border_color="#d1d5db", border_width=1)
        self._dir_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ctk.CTkButton(dr, text="浏览", command=self._browse_dir,
                       width=70, height=38, font=("Helvetica", 13), corner_radius=8,
                       fg_color="#e5e5e5", hover_color="#d1d5db",
                       text_color="#333333").grid(row=0, column=2)

        # User / Pass
        ap = ctk.CTkFrame(ftp_inner, fg_color="transparent")
        ap.pack(fill="x", pady=(12, 0))
        ctk.CTkLabel(ap, text="用户名:", font=("Helvetica", 13),
                      text_color="#333333").pack(side="left", padx=(0, 10))
        self._user_var = ctk.StringVar(value="admin")
        ctk.CTkEntry(ap, textvariable=self._user_var, width=120,
                      font=("Helvetica", 13), corner_radius=8,
                      height=38, border_color="#d1d5db", border_width=1).pack(side="left")
        ctk.CTkLabel(ap, text="  密码:", font=("Helvetica", 13),
                      text_color="#333333").pack(side="left", padx=(10, 10))
        self._pass_var = ctk.StringVar(value="123456")
        ctk.CTkEntry(ap, textvariable=self._pass_var, width=120,
                      font=("Helvetica", 13), corner_radius=8,
                      height=38, border_color="#d1d5db", border_width=1).pack(side="left")

        # Toggle
        tr = ctk.CTkFrame(ftp_inner, fg_color="transparent")
        tr.pack(fill="x", pady=(15, 0))
        self._toggle_btn = ctk.CTkButton(tr, text="启动服务", command=self._toggle,
                                          width=120, height=38, font=("Helvetica", 13, "bold"),
                                          corner_radius=8, fg_color="#10a37f", hover_color="#0d8c6d")
        self._toggle_btn.pack(side="left")
        self._status_label = ctk.CTkLabel(tr, text="状态: 已停止",
                                           font=("Helvetica", 13), text_color="#666666")
        self._status_label.pack(side="left", padx=(15, 0))

        # Log card
        log_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                 border_width=1, border_color="#e5e5e5")
        log_card.pack(fill="both", expand=False)
        log_card.configure(height=260)
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
        self._server_instance = None

    def _browse_dir(self):
        path = filedialog.askdirectory(title="选择 FTP 根目录")
        if path:
            self._dir_var.set(path)

    def _toggle(self):
        if self._server_instance is not None:
            self._stop()
        else:
            self._start()

    @staticmethod
    def _ts():
        return time.strftime("%Y-%m-%d %H:%M:%S")

    def _start(self):
        port_str = self._port_var.get().strip()
        if not port_str.isdigit() or not (1 <= int(port_str) <= 65535):
            messagebox.showwarning("提示", "请输入有效的端口号 (1-65535)")
            return
        root_dir = self._dir_var.get().strip()
        if not root_dir or not os.path.isdir(root_dir):
            messagebox.showwarning("提示", "请选择一个有效的目录作为 FTP 根目录")
            return
        user = self._user_var.get().strip() or "admin"
        pwd = self._pass_var.get().strip() or "123456"

        self._log_clear()
        ts = self._ts()

        authorizer = DummyAuthorizer()
        authorizer.add_user(user, pwd, root_dir, perm="elradfmw")
        authorizer.add_anonymous(root_dir, perm="elr")

        # Closure-captured callbacks for custom FTP handler
        _log_cb = self._log_append
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
            self._server_instance = FTPServer(("0.0.0.0", int(port_str)), _FTPHandler)
        except Exception as e:
            messagebox.showerror("错误", f"FTP 服务器启动失败: {e}")
            self._server_instance = None
            return

        for line in [
            f"{ts}  [启动] FTP 服务器正在监听 0.0.0.0:{port_str}",
            f"{ts}  [信息] 根目录: {root_dir}",
            f"{ts}  [信息] 用户: {user} / 匿名访问已启用",
            f"{ts}  [信息] 被动端口: 60000-60099",
        ]:
            self._log_append(line)

        self._toggle_btn.configure(text="停止服务", fg_color="#dc2626", hover_color="#b91c1c")
        self._status_label.configure(text="状态: 运行中", text_color="#10a37f")
        self._port_entry.configure(state="disabled")
        self._dir_entry.configure(state="disabled")

        threading.Thread(target=self._serve_loop, daemon=True).start()

    def _serve_loop(self):
        try:
            self._server_instance.serve_forever()
        except Exception as e:
            self.app.after(0, self._log_append, f"{self._ts()}  [错误] {e}")

    def _stop(self):
        if self._server_instance:
            try:
                self._server_instance.close_all()
            except Exception:
                pass
            self._server_instance = None
        self._toggle_btn.configure(text="启动服务", fg_color="#10a37f", hover_color="#0d8c6d")
        self._status_label.configure(text="状态: 已停止", text_color="#666666")
        self._port_entry.configure(state="normal")
        self._dir_entry.configure(state="normal")
        self._log_append(f"{self._ts()}  [停止] FTP 服务器已停止")

    def _log_append(self, text):
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
