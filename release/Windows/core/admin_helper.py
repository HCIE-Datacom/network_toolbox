"""
NetTool - Network Toolbox
Version: V100R009C00SPC500
Author: Tang Wenbo (HCIE-Datacom)
Copyright (C) 2026 Tang Wenbo
License: GNU General Public License v3.0 or later

Windows elevated helper process used for privileged system commands.
"""

import ctypes
import json
import locale
import os
import socket
import subprocess
import sys
import threading
import time
import uuid


HELPER_ARG = "--nettool-admin-helper"


def _is_windows():
    return sys.platform.startswith("win")


def _is_admin():
    if not _is_windows():
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _decode_windows_output(data):
    if isinstance(data, str):
        return data
    if not data:
        return ""
    encodings = [
        "utf-8-sig",
        locale.getpreferredencoding(False),
        "mbcs",
        "gbk",
        "cp936",
        "cp950",
    ]
    for enc in encodings:
        if not enc:
            continue
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("utf-8", errors="replace")


def _startupinfo():
    if not _is_windows():
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    return si


def _json_line(obj):
    return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")


def _read_json_line(file_obj):
    line = file_obj.readline()
    if not line:
        raise ConnectionError("管理员 Helper 连接已断开")
    return json.loads(line.decode("utf-8"))


def _run_command(cmd, timeout):
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            startupinfo=_startupinfo(),
        )
        return {
            "returncode": result.returncode,
            "stdout": _decode_windows_output(result.stdout),
            "stderr": _decode_windows_output(result.stderr),
            "args": result.args,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": 124,
            "stdout": _decode_windows_output(exc.stdout),
            "stderr": f"命令执行超时: {timeout} 秒",
            "args": cmd,
        }
    except Exception as exc:
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": str(exc),
            "args": cmd,
        }


def run_windows_admin_helper(port, token):
    """Connect back to the main process and execute JSON-line command requests."""
    if not _is_windows():
        return 2
    if not _is_admin():
        return 5

    sock = socket.create_connection(("127.0.0.1", int(port)), timeout=20)
    with sock:
        sock.settimeout(None)
        file_obj = sock.makefile("rwb", buffering=0)
        file_obj.write(_json_line({"type": "hello", "token": token, "admin": True}))
        while True:
            try:
                req = _read_json_line(file_obj)
            except Exception:
                return 0
            if req.get("type") == "shutdown":
                return 0
            if req.get("token") != token:
                file_obj.write(_json_line({
                    "id": req.get("id"),
                    "returncode": 403,
                    "stdout": "",
                    "stderr": "管理员 Helper token 校验失败",
                    "args": req.get("cmd") or [],
                }))
                continue
            cmd = req.get("cmd") or []
            timeout = int(req.get("timeout") or 15)
            resp = _run_command(cmd, timeout)
            resp["id"] = req.get("id")
            file_obj.write(_json_line(resp))


class WindowsAdminHelper:
    """Owns one elevated helper connection for the current app lifetime."""

    def __init__(self):
        self._lock = threading.RLock()
        self._sock = None
        self._file = None
        self._token = ""
        self._request_id = 0

    def close(self):
        with self._lock:
            try:
                if self._file:
                    self._file.write(_json_line({"type": "shutdown", "token": self._token}))
            except Exception:
                pass
            try:
                if self._sock:
                    self._sock.close()
            except Exception:
                pass
            self._sock = None
            self._file = None
            self._token = ""

    def run(self, cmd, timeout=15):
        if not _is_windows():
            raise RuntimeError("Windows 管理员 Helper 只能在 Windows 下使用")
        if _is_admin():
            result = _run_command(cmd, timeout)
            return subprocess.CompletedProcess(
                result.get("args") or cmd,
                result.get("returncode", 1),
                result.get("stdout", ""),
                result.get("stderr", ""),
            )
        with self._lock:
            self._ensure_started()
            self._request_id += 1
            req_id = self._request_id
            req = {
                "id": req_id,
                "type": "run",
                "token": self._token,
                "cmd": list(cmd),
                "timeout": int(timeout),
            }
            try:
                self._file.write(_json_line(req))
                resp = _read_json_line(self._file)
            except Exception:
                self.close()
                raise
            return subprocess.CompletedProcess(
                resp.get("args") or cmd,
                int(resp.get("returncode", 1)),
                resp.get("stdout", ""),
                resp.get("stderr", ""),
            )

    def _ensure_started(self):
        if self._sock and self._file:
            return

        self._token = uuid.uuid4().hex
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(90)
        port = listener.getsockname()[1]

        try:
            self._launch_elevated(port, self._token)
            try:
                sock, _addr = listener.accept()
            except socket.timeout as exc:
                raise RuntimeError("管理员 Helper 启动超时，可能已取消 UAC 授权") from exc
            sock.settimeout(None)
            file_obj = sock.makefile("rwb", buffering=0)
            hello = _read_json_line(file_obj)
            if hello.get("token") != self._token or not hello.get("admin"):
                sock.close()
                raise RuntimeError("管理员 Helper 校验失败")
            self._sock = sock
            self._file = file_obj
        finally:
            listener.close()

    def _launch_elevated(self, port, token):
        if getattr(sys, "frozen", False):
            exe = sys.executable
            params = f'{HELPER_ARG} {port} {token}'
        else:
            exe = sys.executable
            script = os.path.abspath(sys.argv[0])
            params = f'"{script}" {HELPER_ARG} {port} {token}'

        rc = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            exe,
            params,
            os.getcwd(),
            0,
        )
        if rc <= 32:
            if rc == 1223:
                raise RuntimeError("用户取消了管理员授权")
            raise RuntimeError(f"管理员 Helper 启动失败: ShellExecuteW={rc}")

        # Give Windows a tiny moment to display UAC before accept() starts waiting.
        time.sleep(0.2)


_WINDOWS_ADMIN_HELPER = WindowsAdminHelper()


def run_windows_admin_command(cmd, timeout=15):
    return _WINDOWS_ADMIN_HELPER.run(cmd, timeout=timeout)


def close_windows_admin_helper():
    _WINDOWS_ADMIN_HELPER.close()
