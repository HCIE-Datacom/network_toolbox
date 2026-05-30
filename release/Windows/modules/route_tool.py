"""
NetTool - Network Toolbox
Version: V100R008C00SPC700
Author: Tang Wenbo (HCIE-Datacom)
Copyright (C) 2026 Tang Wenbo
License: GNU General Public License v3.0 or later

System network module for routes, hosts, and NIC IP management.
"""

import subprocess
import ipaddress
import platform
import os
import shlex
import json
import re
import locale

from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QMessageBox, QComboBox, QInputDialog,
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal

from core.base_module import ToolModule
from core.app import (
    BTN_PRIMARY, BTN_DANGER, BTN_SECONDARY, BTN_MODE_ACTIVE, BTN_MODE_INACTIVE,
    set_card_style, set_transparent_bg,
    H1_STYLE, H2_STYLE, H3_STYLE, BODY_STYLE, HINT_STYLE, DESC_STYLE,
)
from core.logger import logger


def _os():
    return platform.system()


def _hosts_path():
    return (r"C:\Windows\System32\drivers\etc\hosts"
            if _os() == "Windows" else "/etc/hosts")


def _escape_osa_string(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _run_admin(cmd_args, timeout=15, password=None):
    """Run command with admin privileges, auto-elevating on macOS."""
    si = None
    kwargs = dict(capture_output=True, text=True, timeout=timeout)
    if _os() == "Windows":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs["encoding"] = "gbk"
        kwargs["errors"] = "replace"
        kwargs["startupinfo"] = si
        return subprocess.run(cmd_args, **kwargs)
    shell_args = cmd_args[1:] if cmd_args and cmd_args[0] == "sudo" else cmd_args
    shell_cmd = " ".join(shlex.quote(str(arg)) for arg in shell_args)
    apple_script_cmd = _escape_osa_string(shell_cmd)
    if password is None:
        script = f'do shell script "{apple_script_cmd}" with administrator privileges'
    else:
        script = (
            f'do shell script "{apple_script_cmd}" '
            f'password "{_escape_osa_string(password)}" with administrator privileges'
        )
    osa = ["osascript", "-e", script]
    return subprocess.run(osa, capture_output=True, text=True, timeout=timeout)


def _run(cmd_args, timeout=15):
    """Run a subprocess without admin, hiding CMD window on Windows."""
    si = None
    if _os() == "Windows":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        result = subprocess.run(
            cmd_args,
            capture_output=True,
            timeout=timeout,
            startupinfo=si,
        )
        return subprocess.CompletedProcess(
            result.args,
            result.returncode,
            _decode_windows_output(result.stdout),
            _decode_windows_output(result.stderr),
        )
    return subprocess.run(cmd_args, capture_output=True, text=True, timeout=timeout)


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


def _extract_ipv4(value):
    match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", str(value))
    if not match:
        return ""
    ip = match.group(0)
    try:
        ipaddress.IPv4Address(ip)
    except Exception:
        return ""
    return ip


def _is_link_local_ipv4(value):
    try:
        ip = ipaddress.IPv4Address(str(value).strip())
    except Exception:
        return False
    return ip.is_link_local


def _mask_from_prefix_line(line):
    match = re.search(r"(?:mask|掩码)\s+(\d+\.\d+\.\d+\.\d+)", line, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"/(\d{1,2})", line)
    if match:
        try:
            return str(ipaddress.IPv4Network(f"0.0.0.0/{int(match.group(1))}").netmask)
        except Exception:
            return ""
    return ""


def _windows_gateway_from_powershell(iface):
    if _os() != "Windows" or not iface:
        return ""
    ps = (
        "$iface = " + json.dumps(str(iface), ensure_ascii=False) + "; "
        "$cfg = Get-NetIPConfiguration -InterfaceAlias $iface -ErrorAction SilentlyContinue; "
        "$gw = [string](@($cfg.IPv4DefaultGateway.NextHop | "
        "Where-Object { $_ -and $_ -ne '0.0.0.0' } | Select-Object -First 1)[0]); "
        "if ($gw) { $gw }"
    )
    try:
        result = _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], timeout=5)
        if result.returncode == 0:
            return _extract_ipv4(result.stdout)
    except Exception:
        logger.exception(f"[系统网络] PowerShell 查询 Windows 网关失败: iface={iface}")
    return ""




class _BackgroundTask(QThread):
    """Run slow system commands outside the UI thread."""
    ok = Signal(object)
    fail = Signal(str)

    def __init__(self, func, parent=None):
        super().__init__(parent)
        self._func = func

    def run(self):
        try:
            self.ok.emit(self._func())
        except Exception as e:
            self.fail.emit(str(e))

_TREE_QSS = """
    QTreeWidget {
        border: 1px solid #dfe3e8; border-radius: 8px;
        background: #ffffff; color: #20242a;
        alternate-background-color: #f8fafb; font-size: 12px;
    }
    QTreeWidget::item { padding: 3px 6px; }
    QTreeWidget::item:selected { background: #e7f5f1; color: #0b745c; }
    QTreeWidget::item:hover { background: #f4f6f7; }
    QTreeWidget::item:alternate { background: #f8fafb; }
    QTreeWidget QHeaderView::section {
        background: #f7f8f9; border: none; border-bottom: 1px solid #e1e5e9;
        padding: 6px 4px; font-size: 11px; font-weight: bold; color: #697281;
    }
    QTreeWidget QScrollBar:vertical {
        background: #f2f3f4; border: none; border-radius: 4px; width: 8px; margin: 2px;
    }
    QTreeWidget QScrollBar::handle:vertical {
        background: #cfd5dc; border-radius: 4px; min-height: 30px;
    }
    QTreeWidget QScrollBar::handle:vertical:hover { background: #aeb6c0; }
    QTreeWidget QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
"""

_COMBO_QSS = """
    QComboBox {
        border: 1px solid #dfe3e8;
        border-radius: 8px;
        padding: 4px 10px;
        font-size: 13px;
        background: #ffffff;
        color: #20242a;
        selection-background-color: #e7f5f1;
        selection-color: #0b745c;
    }
    QComboBox:hover { border-color: #11a37f; }
    QComboBox::drop-down { border: none; width: 24px; background: transparent; }
    QComboBox QAbstractItemView {
        background: #ffffff;
        color: #20242a;
        border: 1px solid #dfe3e8;
        outline: 0;
        selection-background-color: #e7f5f1;
        selection-color: #0b745c;
    }
"""

_NIC_FIELD_STYLE = "font-size: 12px;"
_NIC_FIELD_ERROR_STYLE = """
    QLineEdit {
        font-size: 12px;
        border: 1px solid #e1272d;
        border-radius: 8px;
        padding: 6px 10px;
        background: #fff7f7;
        color: #20242a;
    }
    QLineEdit:focus { border-color: #e1272d; }
"""


class RouteToolModule(ToolModule):
    name = "系统网络"
    icon = "route"
    description = "静态路由 + HOSTS 编辑 + 网卡 IP 管理，支持 macOS / Windows。"

    def build(self, parent: QWidget):
        if not hasattr(self, "_admin_password"):
            self._admin_password = None
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

        # ══ Mode selector ══
        mode_card = QFrame()
        set_card_style(mode_card)
        mc_layout = QVBoxLayout(mode_card)
        mc_layout.setContentsMargins(15, 12, 15, 12)
        mc_layout.setSpacing(8)

        ml = QLabel("功能模式")
        ml.setStyleSheet(H2_STYLE)
        mc_layout.addWidget(ml)

        mb_wrapper = QWidget()
        mb_wrapper.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        mb_wrapper.setStyleSheet(
            "background: #eef0f2; border: 1px solid #e2e5e9; border-radius: 8px;"
        )
        mbl = QHBoxLayout(mb_wrapper)
        mbl.setContentsMargins(4, 4, 4, 4)
        mbl.setSpacing(4)

        self._mode_btns = {}
        for val, text in [("route", "路由管理"), ("hosts", "HOSTS 文件")]:
            btn = QPushButton(text)
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, v=val: self._switch_tab(v))
            mbl.addWidget(btn, stretch=1)
            self._mode_btns[val] = btn
        self._update_mode_buttons(val="route")
        mc_layout.addWidget(mb_wrapper)

        layout.addWidget(mode_card)
        layout.addSpacing(15)

        # ══ Content card ══
        content_card = QFrame()
        set_card_style(content_card)
        cc_layout = QVBoxLayout(content_card)
        cc_layout.setContentsMargins(15, 12, 15, 12)

        # Route frame
        self._route_frame = QWidget()
        set_transparent_bg(self._route_frame)
        self._build_route_ui(self._route_frame)
        cc_layout.addWidget(self._route_frame)

        # Hosts frame
        self._hosts_frame = QWidget()
        set_transparent_bg(self._hosts_frame)
        self._build_hosts_ui(self._hosts_frame)
        cc_layout.addWidget(self._hosts_frame)
        self._hosts_frame.hide()

        layout.addWidget(content_card, stretch=1)

    @staticmethod
    def _lbl(text, style):
        lb = QLabel(text)
        lb.setStyleSheet(style)
        return lb

    def _switch_tab(self, mode):
        self._update_mode_buttons(mode)
        self._route_frame.setVisible(mode == "route")
        self._hosts_frame.setVisible(mode == "hosts")

    def _update_mode_buttons(self, val):
        if val is None:
            return
        for v, btn in self._mode_btns.items():
            if v == val:
                btn.setStyleSheet(BTN_MODE_ACTIVE)
            else:
                btn.setStyleSheet(BTN_MODE_INACTIVE)

    # ═══════════ Route Tab ═══════════

    def _build_route_ui(self, parent):
        fl = QVBoxLayout(parent)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(8)

        # ══ Top row: route add + NIC side-by-side ══
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        # ── Route add card (left) ──
        card = QFrame()
        set_card_style(card)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(15, 12, 15, 12)
        cl.setSpacing(8)

        cl.addWidget(self._lbl("添加静态路由", H2_STYLE))

        grid = QGridLayout()
        grid.setSpacing(6)
        fields = [
            ("目标网络", "192.168.1.0"),
            ("子网掩码", "255.255.255.0"),
            ("下一跳 / 网关", "192.168.1.1"),
            ("跃点数", "1"),
        ]
        self._entries = {}
        for row, (label, placeholder) in enumerate(fields):
            lb = self._lbl(label, "font-size: 12px; color: #555; background: transparent;")
            grid.addWidget(lb, row, 0)
            entry = QLineEdit()
            entry.setPlaceholderText(placeholder)
            entry.setMinimumHeight(34)
            entry.setStyleSheet("font-size: 13px;")
            grid.addWidget(entry, row, 1)
            self._entries[label] = entry
        cl.addLayout(grid)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._add_btn = QPushButton("添加")
        self._add_btn.setStyleSheet(BTN_PRIMARY)
        self._add_btn.setMinimumHeight(34)
        self._add_btn.clicked.connect(self._add_route)
        btn_row.addWidget(self._add_btn)

        self._refresh_btn = QPushButton("刷新")
        self._refresh_btn.setStyleSheet(BTN_SECONDARY)
        self._refresh_btn.setMinimumHeight(34)
        self._refresh_btn.clicked.connect(self._refresh_routes)
        btn_row.addWidget(self._refresh_btn)

        self._delete_btn = QPushButton("删除选中")
        self._delete_btn.setStyleSheet(BTN_DANGER)
        self._delete_btn.setMinimumHeight(34)
        self._delete_btn.clicked.connect(self._delete_route)
        btn_row.addWidget(self._delete_btn)
        btn_row.addStretch(1)
        cl.addLayout(btn_row)

        self._status = self._lbl("", HINT_STYLE)
        cl.addWidget(self._status)

        top_row.addWidget(card, stretch=1)

        # ── NIC card (right) ──
        nic_card = QFrame()
        set_card_style(nic_card)
        ncl = QVBoxLayout(nic_card)
        ncl.setContentsMargins(15, 12, 15, 12)
        ncl.setSpacing(8)

        ncl.addWidget(self._lbl("网卡 IP 管理", H2_STYLE))

        nic_top = QHBoxLayout()
        nic_top.setSpacing(6)
        self._nic_combo = QComboBox()
        self._nic_combo.setMinimumHeight(34)
        self._nic_combo.setStyleSheet(_COMBO_QSS)
        self._nic_combo.view().setStyleSheet(
            "QAbstractItemView { background: #ffffff; color: #20242a; "
            "selection-background-color: #e7f5f1; selection-color: #0b745c; "
            "border: 1px solid #dfe3e8; outline: 0; }"
        )
        self._nic_combo.currentIndexChanged.connect(self._on_nic_changed)
        nic_top.addWidget(self._nic_combo, stretch=1)

        self._nic_refresh = QPushButton("刷新")
        self._nic_refresh.setStyleSheet(BTN_SECONDARY)
        self._nic_refresh.setMinimumHeight(34)
        self._nic_refresh.clicked.connect(self._refresh_nics)
        nic_top.addWidget(self._nic_refresh)
        ncl.addLayout(nic_top)

        self._nic_tree = QTreeWidget()
        self._nic_tree.setColumnCount(3)
        self._nic_tree.setHeaderLabels(["IP 地址", "子网掩码", "网关"])
        self._nic_tree.setRootIsDecorated(False)
        self._nic_tree.setAlternatingRowColors(True)
        self._nic_tree.setStyleSheet(_TREE_QSS)
        self._nic_tree.setMaximumHeight(100)
        ncl.addWidget(self._nic_tree)

        nic_form = QHBoxLayout()
        nic_form.setSpacing(6)
        self._nic_ip = QLineEdit()
        self._nic_ip.setPlaceholderText("IP")
        self._nic_ip.setMinimumHeight(32)
        self._nic_ip.setStyleSheet(_NIC_FIELD_STYLE)
        nic_form.addWidget(self._nic_ip)

        self._nic_mask = QLineEdit()
        self._nic_mask.setPlaceholderText("掩码")
        self._nic_mask.setMinimumHeight(32)
        self._nic_mask.setStyleSheet(_NIC_FIELD_STYLE)
        nic_form.addWidget(self._nic_mask)

        self._nic_gw = QLineEdit()
        self._nic_gw.setPlaceholderText("网关")
        self._nic_gw.setMinimumHeight(32)
        self._nic_gw.setStyleSheet(_NIC_FIELD_STYLE)
        nic_form.addWidget(self._nic_gw)
        self._nic_ip.textChanged.connect(self._validate_nic_fields_live)
        self._nic_mask.textChanged.connect(self._validate_nic_fields_live)
        self._nic_gw.textChanged.connect(self._validate_nic_fields_live)

        self._nic_add_btn = QPushButton("添加")
        self._nic_add_btn.setStyleSheet(BTN_PRIMARY)
        self._nic_add_btn.setMinimumHeight(32)
        self._nic_add_btn.setFixedWidth(60)
        self._nic_add_btn.clicked.connect(self._add_nic_ip)
        nic_form.addWidget(self._nic_add_btn)

        self._nic_del_btn = QPushButton("删除")
        self._nic_del_btn.setStyleSheet(BTN_DANGER)
        self._nic_del_btn.setMinimumHeight(32)
        self._nic_del_btn.setFixedWidth(60)
        self._nic_del_btn.clicked.connect(self._delete_nic_ip)
        nic_form.addWidget(self._nic_del_btn)
        ncl.addLayout(nic_form)

        self._nic_status = self._lbl("", HINT_STYLE)
        ncl.addWidget(self._nic_status)
        self._nic_last_status = ""

        top_row.addWidget(nic_card, stretch=1)
        fl.addLayout(top_row)

        # Route table
        self._tree = QTreeWidget()
        if _os() == "Windows":
            self._tree.setColumnCount(5)
            self._tree.setHeaderLabels(["目标网络", "掩码", "网关", "接口", "跃点数"])
        else:
            self._tree.setColumnCount(4)
            self._tree.setHeaderLabels(["目标网络", "掩码/CIDR", "网关", "接口"])
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSelectionMode(self._tree.SelectionMode.SingleSelection)
        self._tree.setStyleSheet(_TREE_QSS)
        fl.addWidget(self._tree, stretch=1)

        QTimer.singleShot(100, self._refresh_routes)
        QTimer.singleShot(250, self._refresh_nics)

    # ── Route operations ──

    def _add_route(self):
        dest = self._entries["目标网络"].text().strip()
        mask = self._entries["子网掩码"].text().strip()
        gw = self._entries["下一跳 / 网关"].text().strip()
        metric = self._entries["跃点数"].text().strip() or "1"

        if not dest or not mask or not gw:
            logger.warning("[系统网络] 添加路由失败: 必填项为空")
            QMessageBox.warning(self.app, "提示", "目标网络、子网掩码和网关不能为空")
            return

        if mask.isdigit():
            cidr = mask
        else:
            try:
                cidr = str(ipaddress.IPv4Network(f"0.0.0.0/{mask}").prefixlen)
            except ValueError:
                logger.warning(f"[系统网络] 添加路由失败: 掩码无效 mask={mask}")
                QMessageBox.warning(self.app, "提示", f"子网掩码格式不正确: {mask}\n支持: 24, 16, 255.255.255.0 等")
                return

        try:
            network = ipaddress.IPv4Network(f"{dest}/{cidr}", strict=False)
        except ValueError:
            logger.warning(f"[系统网络] 添加路由失败: 目标地址无效 dest={dest}, cidr={cidr}")
            QMessageBox.warning(self.app, "提示", "IP 地址格式不正确")
            return

        m = str(network.netmask)
        self._status.setText("正在添加路由...")
        self._status.setStyleSheet("font-size: 11px; color: #11a37f; background: transparent;")

        if _os() == "Windows":
            cmd = ["route", "add", str(network.network_address), "mask", str(m), gw]
            if metric != "1":
                cmd += ["metric", metric]
        else:
            cmd = ["sudo", "/sbin/route", "-n", "add", "-net", str(network.network_address), gw, m]
        logger.info(f"[系统网络] 添加路由: network={network.network_address}, mask={m}, gw={gw}, metric={metric}, cmd={' '.join(cmd)}")

        try:
            result = self._run_admin_cached(cmd)
            if result.returncode == 0:
                logger.info(f"[系统网络] 路由添加成功: {network.network_address}/{m} -> {gw}")
                self._status.setText("路由添加成功")
                self._status.setStyleSheet("font-size: 11px; color: #11a37f; background: transparent;")
                self._refresh_routes()
            else:
                err = result.stderr.strip() or result.stdout.strip() or "未知错误"
                logger.error(f"[系统网络] 路由添加失败: returncode={result.returncode}, error={err}")
                self._status.setText(f"添加失败: {err}")
                self._status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")
        except Exception as e:
            logger.exception("[系统网络] 添加路由执行异常")
            self._status.setText(f"执行失败: {e}")
            self._status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")

    def _refresh_routes(self):
        logger.info("[系统网络] 刷新路由表")
        self._tree.clear()
        self._status.setText("正在刷新路由表...")
        self._status.setStyleSheet("font-size: 11px; color: #11a37f; background: transparent;")
        QTimer.singleShot(50, self._do_refresh_routes)

    def _do_refresh_routes(self):
        cmd = ["route", "print"] if _os() == "Windows" else ["netstat", "-rn", "-f", "inet"]
        try:
            result = _run(cmd)
            self._parse_routes(result.stdout.split("\n"))
            count = self._tree.topLevelItemCount()
            logger.info(f"[系统网络] 路由表刷新完成: cmd={' '.join(cmd)}, count={count}, returncode={result.returncode}")
            if count == 0 and _os() == "Windows":
                # Debug: show first 200 chars of raw output
                raw = result.stdout[:300].replace("\n", "\\n")
                self._status.setText(f"0 条路由 | 原始输出: {raw}")
            else:
                self._status.setText(f"共 {count} 条路由")
            self._status.setStyleSheet(HINT_STYLE)
        except Exception as e:
            logger.exception("[系统网络] 路由表刷新异常")
            self._status.setText(f"刷新失败: {e}")
            self._status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")

    def _parse_routes(self, lines):
        self._tree.clear()
        if _os() == "Windows":
            # Windows: find lines with 5 tokens where first is a valid IP
            in_table = False
            seen = False
            for s in lines:
                s = s.strip()
                if "IPv4" in s and ("Route" in s or "路由" in s):
                    in_table = True
                    continue
                if not in_table or not s:
                    continue
                # Only break on === after seeing route data
                if s.startswith("Persistent") or s.startswith("永久") or \
                   (s.startswith("=") and seen):
                    break
                parts = s.split()
                if len(parts) >= 5 and self._is_ip(parts[0]):
                    seen = True
                    dest, mask, gw, iface, metric = parts[0], parts[1], parts[2], parts[3], parts[4]
                    self._tree.addTopLevelItem(QTreeWidgetItem([dest, mask, gw, iface, metric]))
        else:
            in_table = False
            for line in lines:
                line = line.strip()
                if line.startswith("Destination"):
                    in_table = True
                    continue
                if not in_table or not line:
                    continue
                parts = line.split()
                if len(parts) >= 4:
                    dest, gw, flags = parts[0], parts[1], parts[2]
                    iface = parts[3] if len(parts) > 3 else ""
                    if self._is_bsd_route_dest(dest):
                        net, m = self._parse_bsd_dest(dest)
                        display = f"{net}/{self._mask_to_cidr(m)}" if m and m != "0.0.0.0" else net
                        self._tree.addTopLevelItem(QTreeWidgetItem([display, m if m else "-", gw, iface]))

        for i in range(self._tree.columnCount()):
            self._tree.header().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

    @staticmethod
    def _mask_to_cidr(mask):
        try:
            return str(ipaddress.IPv4Network(f"0.0.0.0/{mask}").prefixlen)
        except ValueError:
            return mask

    @staticmethod
    def _is_ip(s):
        try:
            ipaddress.IPv4Address(s.split("/")[0])
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_bsd_route_dest(dest):
        if dest == "default":
            return True
        base = dest.split("/")[0]
        parts = base.split(".")
        return 1 <= len(parts) <= 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)

    @staticmethod
    def _parse_bsd_dest(dest):
        if "/" in dest:
            net, bits = dest.split("/")
            bits = int(bits)
            mask = str(ipaddress.IPv4Network(f"0.0.0.0/{bits}").netmask)
            parts = net.split(".")
            if 1 <= len(parts) < 4 and all(p.isdigit() for p in parts):
                net = ".".join(parts + ["0"] * (4 - len(parts)))
            return net, mask
        if dest == "default":
            return "0.0.0.0", "0.0.0.0"
        parts = dest.split(".")
        if 1 <= len(parts) < 4 and all(p.isdigit() for p in parts):
            net = ".".join(parts + ["0"] * (4 - len(parts)))
            cidr = len(parts) * 8
            mask = str(ipaddress.IPv4Network(f"0.0.0.0/{cidr}").netmask)
            return net, mask
        return dest, ""

    def _delete_route(self):
        item = self._tree.currentItem()
        if not item:
            logger.warning("[系统网络] 删除路由失败: 未选择路由")
            QMessageBox.warning(self.app, "提示", "请先选择一条路由")
            return

        dest = item.text(0)
        mask = item.text(1)
        gw = item.text(2)

        if "/" in dest:
            net, bits = dest.split("/")
            if not mask or mask == "-":
                try:
                    mask = str(ipaddress.IPv4Network(f"0.0.0.0/{bits}").netmask)
                except ValueError:
                    mask = "0.0.0.0"
            dest = net

        if dest == "0.0.0.0" and mask == "0.0.0.0":
            logger.warning("[系统网络] 拒绝删除默认路由")
            QMessageBox.warning(self.app, "提示", "不能删除默认路由")
            return

        reply = QMessageBox.question(
            self.app, "确认删除",
            f"确认删除路由 {dest}/{mask} → {gw}？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            logger.info(f"[系统网络] 用户取消删除路由: {dest}/{mask} -> {gw}")
            return

        if _os() == "Windows":
            cmd = ["route", "delete", dest]
            if mask != "0.0.0.0":
                cmd += ["mask", mask]
        else:
            cmd = ["sudo", "/sbin/route", "-n", "delete"]
            if mask and mask not in ("-", "0.0.0.0"):
                cmd += ["-net", dest, gw, mask]
            else:
                route_kind = "-host" if self._is_ip(dest) and dest.count(".") == 3 else "-net"
                cmd += [route_kind, dest, gw]
        logger.info(f"[系统网络] 删除路由: {dest}/{mask} -> {gw}, cmd={' '.join(cmd)}")

        try:
            result = self._run_admin_cached(cmd)
            if result.returncode == 0:
                logger.info(f"[系统网络] 路由删除成功: {dest}/{mask} -> {gw}")
                self._status.setText("路由已删除")
                self._status.setStyleSheet("font-size: 11px; color: #11a37f; background: transparent;")
                self._refresh_routes()
            else:
                err = result.stderr.strip() or result.stdout.strip() or "未知错误"
                logger.error(f"[系统网络] 路由删除失败: returncode={result.returncode}, error={err}")
                self._status.setText(f"删除失败: {err}")
                self._status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")
        except Exception as e:
            logger.exception("[系统网络] 删除路由执行异常")
            self._status.setText(f"执行失败: {e}")
            self._status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")

    # ═══════════ NIC helpers ═══════════

    @staticmethod
    def _lbl(text, style):
        lb = QLabel(text)
        lb.setStyleSheet(style)
        return lb

    def _run_bg(self, func, on_ok, on_fail=None):
        """Start a background task and keep a reference to avoid GC."""
        if not hasattr(self, "_bg_threads"):
            self._bg_threads = []
        th = _BackgroundTask(func, self.app)
        self._bg_threads.append(th)

        def _cleanup():
            try:
                self._bg_threads.remove(th)
            except ValueError:
                pass
            th.deleteLater()

        th.ok.connect(on_ok)
        th.fail.connect(on_fail or (lambda msg: self._nic_status.setText(f"错误: {msg}")))
        th.finished.connect(_cleanup)
        th.start()
        return th

    @staticmethod
    def _is_auth_error(result):
        text = f"{getattr(result, 'stderr', '')}\n{getattr(result, 'stdout', '')}".lower()
        return (
            "password" in text
            or "administrator" in text
            or "authentication" in text
            or "not allowed to assistive" in text
            or "user canceled" in text
            or "用户已取消" in text
            or "密码" in text
        )

    @staticmethod
    def _valid_ipv4(value):
        try:
            ipaddress.IPv4Address(str(value).strip())
            return True
        except Exception:
            return False

    @staticmethod
    def _valid_mask(value):
        text = str(value).strip()
        if text.isdigit():
            try:
                bits = int(text)
                return 0 <= bits <= 32
            except Exception:
                return False
        try:
            ipaddress.IPv4Network(f"0.0.0.0/{text}")
            return True
        except Exception:
            return False

    def _set_nic_field_error(self, widget, has_error):
        widget.setStyleSheet(_NIC_FIELD_ERROR_STYLE if has_error else _NIC_FIELD_STYLE)

    def _validate_nic_fields_live(self):
        ip = self._nic_ip.text().strip()
        mask = self._nic_mask.text().strip()
        gw = self._nic_gw.text().strip()
        ip_bad = bool(ip) and not self._valid_ipv4(ip)
        mask_bad = bool(mask) and not self._valid_mask(mask)
        gw_bad = bool(gw) and not self._valid_ipv4(gw)
        self._set_nic_field_error(self._nic_ip, ip_bad)
        self._set_nic_field_error(self._nic_mask, mask_bad)
        self._set_nic_field_error(self._nic_gw, gw_bad)
        if ip_bad:
            self._nic_status.setText("IP 地址格式不正确")
            self._nic_status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")
        elif mask_bad:
            self._nic_status.setText("掩码格式不正确，支持 24 或 255.255.255.0")
            self._nic_status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")
        elif gw_bad:
            self._nic_status.setText("网关格式不正确")
            self._nic_status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")
        else:
            status = getattr(self, "_nic_last_status", "")
            if status:
                self._nic_status.setText(status)
                self._nic_status.setStyleSheet(HINT_STYLE)
            elif ip or mask or gw:
                self._nic_status.setText("输入格式正常")
                self._nic_status.setStyleSheet("font-size: 11px; color: #11a37f; background: transparent;")
            else:
                self._nic_status.setText("")
                self._nic_status.setStyleSheet(HINT_STYLE)
        return not (ip_bad or mask_bad or gw_bad)

    def _validate_nic_fields_required(self, ip, mask_raw, gw):
        ok = self._validate_nic_fields_live()
        missing_ip = not ip
        missing_mask = not mask_raw
        self._set_nic_field_error(self._nic_ip, missing_ip or (bool(ip) and not self._valid_ipv4(ip)))
        self._set_nic_field_error(self._nic_mask, missing_mask or (bool(mask_raw) and not self._valid_mask(mask_raw)))
        self._set_nic_field_error(self._nic_gw, bool(gw) and not self._valid_ipv4(gw))
        if missing_ip or missing_mask:
            self._nic_status.setText("IP 地址和掩码不能为空")
            self._nic_status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")
            return False
        if not self._valid_ipv4(ip):
            self._nic_status.setText("IP 地址格式不正确")
            self._nic_status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")
            return False
        if not self._valid_mask(mask_raw):
            self._nic_status.setText("掩码格式不正确，支持 24 或 255.255.255.0")
            self._nic_status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")
            return False
        if gw and not self._valid_ipv4(gw):
            self._nic_status.setText("网关格式不正确")
            self._nic_status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")
            return False
        return ok

    def _get_admin_password(self):
        if _os() != "Darwin":
            return None
        if self._admin_password:
            return self._admin_password
        pwd, ok = QInputDialog.getText(
            self.app,
            "管理员权限",
            "请输入本机管理员密码（软件关闭前会记住）:",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return None
        self._admin_password = pwd
        return self._admin_password

    def _run_admin_cached(self, cmd, timeout=15):
        if _os() != "Darwin":
            return _run_admin(cmd, timeout=timeout)
        password = self._get_admin_password()
        if password is None:
            raise RuntimeError("用户取消了管理员验证")
        result = _run_admin(cmd, timeout=timeout, password=password)
        if result.returncode != 0 and self._is_auth_error(result):
            self._admin_password = None
        return result

    def _set_nic_controls_enabled(self, enabled: bool):
        for w in (self._nic_combo, self._nic_refresh, self._nic_add_btn, self._nic_del_btn):
            try:
                w.setEnabled(enabled)
            except Exception:
                pass

    def _load_nics_data(self):
        """Return [(display_label, system_iface_name), ...]. No UI operations here."""
        items = []
        if _os() == "Windows":
            logger.info("[系统网络] 加载 Windows 网卡列表")
            # Prefer netsh on Windows: it starts much faster than PowerShell.
            result = _run(["netsh", "interface", "ipv4", "show", "interfaces"], timeout=5)
            seen = set()
            for line in result.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) < 5 or not parts[0].isdigit():
                    continue
                iface = " ".join(parts[4:]).strip()
                if not iface or iface.lower().startswith("loopback"):
                    continue
                state = parts[3].lower()
                label_status = "已连接" if state in ("connected", "已连接") else "已断开"
                seen.add(iface)
                items.append((f"{iface} ({label_status})", iface))
            if items:
                logger.info(f"[系统网络] Windows 网卡加载完成(netsh): count={len(items)}")
                return items

            # Fallback: PowerShell gives structured data but is slower to launch.
            ps = (
                "Get-NetAdapter | "
                "Sort-Object ifIndex | "
                "Select-Object -Property Name, Status | "
                "ConvertTo-Json -Compress"
            )
            result = _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], timeout=8)
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())
                if isinstance(data, dict):
                    data = [data]
                for row in data:
                    iface = str(row.get("Name", "")).strip()
                    status = str(row.get("Status", "")).strip()
                    if not iface:
                        continue
                    label_status = "已连接" if status.lower() == "up" else "已断开"
                    items.append((f"{iface} ({label_status})", iface))
                logger.info(f"[系统网络] Windows 网卡加载完成(PowerShell): count={len(items)}")
                return items

            # Fallback: localized netsh parsing.
            result = _run(["netsh", "interface", "ip", "show", "interfaces"], timeout=8)
            for line in result.stdout.split("\n"):
                parts = line.strip().split()
                if len(parts) >= 5 and parts[0].isdigit():
                    state = parts[3].lower()
                    if state in ("connected", "disconnected", "已连接", "已断开"):
                        iface = " ".join(parts[4:])
                        label = f"{iface} ({'已连接' if state in ('connected','已连接') else '已断开'})"
                        items.append((label, iface))
            return items

        # macOS
        logger.info("[系统网络] 加载 macOS 网卡列表")
        labels = {}
        try:
            r = _run(["networksetup", "-listallhardwareports"], timeout=8)
            current_label = ""
            for line in r.stdout.split("\n"):
                s = line.strip()
                if s.startswith("Hardware Port:"):
                    current_label = s.split(":", 1)[1].strip()
                elif s.startswith("Device:") and current_label:
                    dev = s.split(":", 1)[1].strip()
                    labels[dev] = current_label
        except Exception:
            pass

        result = _run(["ifconfig"], timeout=8)
        for line in result.stdout.split("\n"):
            if line and not line.startswith("\t") and not line.startswith(" "):
                parts = line.split(":")
                if parts:
                    iface = parts[0].strip()
                    if iface and iface.startswith("en"):
                        tag = labels.get(iface, "")
                        display = f"{iface} ({tag})" if tag else iface
                        items.append((display, iface))
        logger.info(f"[系统网络] macOS 网卡加载完成: count={len(items)}")
        return items

    @staticmethod
    def _network_service_for_iface(iface):
        if _os() != "Darwin":
            return ""
        # Prefer the active service list; it maps user-visible service names
        # to devices more reliably than hardware-port labels alone.
        try:
            r = _run(["networksetup", "-listnetworkserviceorder"], timeout=8)
            current_service = ""
            for line in r.stdout.split("\n"):
                s = line.strip()
                service_match = re.match(r"\(\d+\)\s+(.+)", s)
                if service_match:
                    current_service = service_match.group(1).strip()
                    continue
                device_match = re.search(r"Device:\s*([^)]+)", s)
                if current_service and device_match and device_match.group(1).strip() == iface:
                    return current_service
        except Exception:
            logger.exception(f"[系统网络] 查询 macOS 网络服务顺序失败: iface={iface}")
        try:
            r = _run(["networksetup", "-listallhardwareports"], timeout=8)
            current_label = ""
            for line in r.stdout.split("\n"):
                s = line.strip()
                if s.startswith("Hardware Port:"):
                    current_label = s.split(":", 1)[1].strip()
                elif s.startswith("Device:"):
                    dev = s.split(":", 1)[1].strip()
                    if dev == iface:
                        return current_label
        except Exception:
            logger.exception(f"[系统网络] 查询 macOS 网络服务失败: iface={iface}")
        return ""

    @staticmethod
    def _network_service_router(service):
        if _os() != "Darwin" or not service:
            return ""
        return RouteToolModule._network_service_info(service).get("router", "")

    @staticmethod
    def _network_service_info(service):
        info = {"ip": "", "mask": "", "router": ""}
        if _os() != "Darwin" or not service:
            return info
        try:
            r = _run(["networksetup", "-getinfo", service], timeout=8)
            for line in r.stdout.split("\n"):
                s = line.strip()
                if ":" not in s:
                    continue
                key, value = [p.strip() for p in s.split(":", 1)]
                value = "" if value.lower() == "none" else value
                if key == "IP address":
                    info["ip"] = value
                elif key == "Subnet mask":
                    info["mask"] = value
                elif key == "Router":
                    info["router"] = value
        except Exception:
            logger.exception(f"[系统网络] 查询 macOS 网络服务配置失败: service={service}")
        return info

    def _load_nic_ips_data(self, iface):
        """Return [(ip, mask, gw), ...] for the selected adapter. No UI operations here."""
        rows = []
        logger.info(f"[系统网络] 加载网卡 IP: iface={iface}")
        if _os() == "Windows":
            gw = ""
            result = _run(["netsh", "interface", "ipv4", "show", "addresses", f'name="{iface}"'], timeout=5)
            current = {}
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.splitlines():
                    s = line.strip()
                    if not s:
                        continue
                    if "Default Gateway" in s or "默认网关" in s:
                        gw_value = _extract_ipv4(s.split(":", 1)[-1] if ":" in s else s)
                        if gw_value and gw_value != "0.0.0.0":
                            gw = gw_value
                    if ("IP Address" in s or "IP 地址" in s) and ":" in s:
                        ip = _extract_ipv4(s.split(":", 1)[-1])
                        if ip and ip != "127.0.0.1" and not _is_link_local_ipv4(ip):
                            current = {"ip": ip}
                        else:
                            current = {}
                    elif ("Subnet Prefix" in s or "子网前缀" in s) and current.get("ip"):
                        mask = _mask_from_prefix_line(s)
                        rows.append((current["ip"], mask, gw))
                        current = {}
                    elif ("Subnet Mask" in s or "子网掩码" in s) and current.get("ip"):
                        mask = s.split(":", 1)[-1].strip()
                        rows.append((current["ip"], mask, gw))
                        current = {}
                if current.get("ip"):
                    rows.append((current["ip"], "", gw))
                if rows and gw:
                    rows = [(ip, mask, row_gw or gw) for ip, mask, row_gw in rows]
                if rows and not any(row_gw for _, _, row_gw in rows):
                    gw = _windows_gateway_from_powershell(iface)
                    if gw:
                        rows = [(ip, mask, gw) for ip, mask, _ in rows]
                if rows:
                    logger.info(f"[系统网络] 网卡 IP 加载完成(netsh): iface={iface}, count={len(rows)}, gw={gw or '-'}")
                    return rows

            ps = (
                "$iface = " + json.dumps(str(iface), ensure_ascii=False) + "; "
                "$cfg = Get-NetIPConfiguration -InterfaceAlias $iface -ErrorAction SilentlyContinue; "
                "$gw = [string](@($cfg.IPv4DefaultGateway.NextHop | "
                "Where-Object { $_ -and $_ -ne '0.0.0.0' } | Select-Object -First 1)[0]); "
                "Get-NetIPAddress -InterfaceAlias $iface -AddressFamily IPv4 | "
                "Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254.*' } | "
                "Select-Object IPAddress, PrefixLength, @{Name='Gateway';Expression={$gw}} | "
                "ConvertTo-Json -Compress"
            )
            result = _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], timeout=8)

            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())
                if isinstance(data, dict):
                    data = [data]
                for row in data:
                    ip = str(row.get("IPAddress", "")).strip()
                    if not ip or _is_link_local_ipv4(ip):
                        continue
                    bits = int(row.get("PrefixLength", 32))
                    mask = str(ipaddress.IPv4Network(f"0.0.0.0/{bits}").netmask)
                    gw = str(row.get("Gateway") or "").strip()
                    rows.append((ip, mask, gw))
                logger.info(f"[系统网络] 网卡 IP 加载完成(PowerShell): iface={iface}, count={len(rows)}")
                return rows

            # Fallback: netsh output, supporting Chinese and English.
            result = _run(["netsh", "interface", "ip", "show", "addresses", str(iface)], timeout=8)
            current = {}
            for line in result.stdout.split("\n"):
                s = line.strip()
                if "Default Gateway" in s or "默认网关" in s:
                    gw_value = _extract_ipv4(s.split(":", 1)[-1] if ":" in s else s)
                    if gw_value:
                        gw = gw_value
                for kw, key in [("IP 地址:", "ip"), ("IP Address:", "ip"),
                                ("子网掩码:", "mask"), ("Subnet Mask:", "mask")]:
                    if kw in s:
                        value = s.split(":", 1)[-1].strip()
                        current[key] = _extract_ipv4(value) if key == "ip" else value
                if len(current) >= 2:
                    ip = current.get("ip", "")
                    if ip and not _is_link_local_ipv4(ip):
                        rows.append((ip, current.get("mask", ""), gw))
                    current = {}
            if current.get("ip") and not _is_link_local_ipv4(current.get("ip", "")):
                rows.append((current.get("ip", ""), current.get("mask", ""), gw))
            if rows and gw:
                rows = [(ip, mask, row_gw or gw) for ip, mask, row_gw in rows]
            if rows and not any(row_gw for _, _, row_gw in rows):
                gw = _windows_gateway_from_powershell(iface)
                if gw:
                    rows = [(ip, mask, gw) for ip, mask, _ in rows]
            return rows

        # macOS
        gw = ""
        service = self._network_service_for_iface(iface)
        service_info = self._network_service_info(service) if service else {}
        if service:
            gw = service_info.get("router", "")
        try:
            r = _run(["netstat", "-rn", "-f", "inet"], timeout=8)
            for line in r.stdout.split("\n"):
                parts = line.strip().split()
                netif = parts[4] if len(parts) >= 5 else (parts[3] if len(parts) >= 4 else "")
                if len(parts) >= 4 and parts[0] == "default" and netif == iface:
                    gw = parts[1]
                    break
        except Exception:
            pass

        result = _run(["ifconfig", iface], timeout=8)
        seen_ips = set()
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line.startswith("inet "):
                parts = line.split()
                if len(parts) >= 4:
                    ip = parts[1]
                    mask_hex = parts[3]
                    if mask_hex.startswith("0x"):
                        try:
                            mask_int = int(mask_hex, 16)
                            mask = f"{(mask_int>>24)&0xff}.{(mask_int>>16)&0xff}.{(mask_int>>8)&0xff}.{mask_int&0xff}"
                        except ValueError:
                            mask = mask_hex
                    else:
                        mask = mask_hex
                    rows.append((ip, mask, gw))
                    seen_ips.add(ip)
        service_ip = service_info.get("ip", "")
        service_mask = service_info.get("mask", "")
        service_router = service_info.get("router", "")
        if service_ip and service_mask and service_ip not in seen_ips:
            rows.insert(0, (service_ip, service_mask, service_router))
        elif service_router:
            rows = [(ip, mask, service_router if not row_gw else row_gw) for ip, mask, row_gw in rows]
        logger.info(f"[系统网络] 网卡 IP 加载完成: iface={iface}, count={len(rows)}")
        return rows

    def _refresh_nics(self, keep_iface=None):
        logger.info("[系统网络] 刷新网卡列表")
        selected_iface = keep_iface or self._nic_combo.currentData(Qt.ItemDataRole.UserRole) or self._nic_combo.currentText()
        self._nic_status.setText("正在刷新网卡...")
        self._set_nic_controls_enabled(False)

        def _apply(items):
            logger.info(f"[系统网络] 网卡列表刷新完成: count={len(items)}")
            self._nic_combo.blockSignals(True)
            self._nic_combo.clear()
            target_index = 0
            for display, iface in items:
                self._nic_combo.addItem(display)
                self._nic_combo.setItemData(self._nic_combo.count() - 1, iface, Qt.ItemDataRole.UserRole)
                if selected_iface and iface == selected_iface:
                    target_index = self._nic_combo.count() - 1
            self._nic_combo.blockSignals(False)
            self._set_nic_controls_enabled(True)
            if self._nic_combo.count() > 0:
                self._nic_combo.setCurrentIndex(target_index)
                self._on_nic_changed(target_index)
            else:
                self._nic_tree.clear()
                self._nic_last_status = "未发现网卡"
                self._nic_status.setText("未发现网卡")

        def _fail(msg):
            logger.error(f"[系统网络] 网卡列表刷新失败: {msg}")
            self._set_nic_controls_enabled(True)
            self._nic_status.setText(f"刷新失败: {msg}")

        self._run_bg(self._load_nics_data, _apply, _fail)

    def _on_nic_changed(self, idx):
        self._nic_tree.clear()
        if idx < 0:
            return
        iface = self._nic_combo.currentData(Qt.ItemDataRole.UserRole) or self._nic_combo.currentText()
        if not iface:
            return
        logger.info(f"[系统网络] 选择网卡: {iface}")
        self._nic_status.setText("正在加载 IP...")
        self._nic_refresh.setEnabled(False)

        def _apply(rows):
            current_iface = self._nic_combo.currentData(Qt.ItemDataRole.UserRole) or self._nic_combo.currentText()
            if current_iface != iface:
                return
            self._nic_tree.clear()
            for ip, mask, gw in rows:
                self._nic_tree.addTopLevelItem(QTreeWidgetItem([ip, mask, gw]))
            for i in range(3):
                self._nic_tree.header().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            self._nic_refresh.setEnabled(True)
            self._nic_last_status = f"共 {self._nic_tree.topLevelItemCount()} 个 IP"
            self._nic_status.setText(self._nic_last_status)
            self._nic_status.setStyleSheet(HINT_STYLE)
            logger.info(f"[系统网络] 网卡 IP 显示完成: iface={iface}, count={len(rows)}")

        def _fail(msg):
            logger.error(f"[系统网络] 网卡 IP 加载失败: iface={iface}, error={msg}")
            self._nic_refresh.setEnabled(True)
            self._nic_status.setText(f"加载失败: {msg}")
            self._nic_status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")

        self._run_bg(lambda: self._load_nic_ips_data(iface), _apply, _fail)

    def _add_nic_ip(self):
        iface = self._nic_combo.currentData(Qt.ItemDataRole.UserRole) or self._nic_combo.currentText()
        if not iface:
            logger.warning("[系统网络] 添加网卡 IP 失败: 未选择网卡")
            return QMessageBox.warning(self.app, "提示", "请先选择网卡")
        ip = self._nic_ip.text().strip()
        mask_raw = self._nic_mask.text().strip()
        gw = self._nic_gw.text().strip() if hasattr(self, '_nic_gw') else ""
        if not self._validate_nic_fields_required(ip, mask_raw, gw):
            logger.warning("[系统网络] 添加网卡 IP 失败: IP 或掩码为空")
            return

        # Auto-detect mask: "24" → "255.255.255.0"
        if mask_raw.isdigit():
            mask = str(ipaddress.IPv4Network(f"0.0.0.0/{mask_raw}").netmask)
        else:
            mask = mask_raw

        self._nic_status.setText("正在添加...")
        self._nic_status.setStyleSheet("font-size: 11px; color: #11a37f; background: transparent;")
        self._set_nic_controls_enabled(False)

        if _os() == "Windows":
            cmd = ["netsh", "interface", "ip", "add", "address", iface, ip, mask]
            if gw:
                cmd += [gw]
            cmds = [cmd]
        elif gw:
            service = self._network_service_for_iface(iface)
            if not service:
                self._set_nic_controls_enabled(True)
                self._set_nic_field_error(self._nic_gw, True)
                self._nic_status.setText(f"无法找到 {iface} 对应的网络服务，网关未写入")
                self._nic_status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")
                logger.error(f"[系统网络] 添加网卡 IP 失败: 找不到 macOS 网络服务 iface={iface}")
                return
            cmd = ["sudo", "networksetup", "-setmanual", service, ip, mask, gw]
            cmds = [cmd]
        else:
            cmd = ["sudo", "ifconfig", iface, "inet", ip, "netmask", mask, "alias"]
            cmds = [cmd]
        logger.info(f"[系统网络] 添加网卡 IP: iface={iface}, ip={ip}, mask={mask}, gw={gw or '-'}, cmd={' && '.join(' '.join(c) for c in cmds)}")

        password = self._get_admin_password()
        if _os() == "Darwin" and password is None:
            logger.info("[系统网络] 添加网卡 IP 取消: 用户取消管理员验证")
            self._set_nic_controls_enabled(True)
            self._nic_status.setText("已取消管理员验证")
            self._nic_status.setStyleSheet(HINT_STYLE)
            return

        def _work():
            stdout_parts = []
            stderr_parts = []
            for one_cmd in cmds:
                result = _run_admin(one_cmd, password=password)
                stdout_parts.append(result.stdout or "")
                stderr_parts.append(result.stderr or "")
                if result.returncode != 0:
                    return subprocess.CompletedProcess(one_cmd, result.returncode, "".join(stdout_parts), "".join(stderr_parts))
            return subprocess.CompletedProcess(cmds[-1], 0, "".join(stdout_parts), "".join(stderr_parts))

        def _apply(result):
            self._set_nic_controls_enabled(True)
            if result.returncode == 0:
                logger.info(f"[系统网络] 网卡 IP 添加成功: iface={iface}, ip={ip}, mask={mask}")
                self._nic_status.setText("IP 添加成功")
                self._nic_status.setStyleSheet("font-size: 11px; color: #11a37f; background: transparent;")
                self._nic_ip.clear(); self._nic_mask.clear()
                if hasattr(self, '_nic_gw'):
                    self._nic_gw.clear()
                self._on_nic_changed(self._nic_combo.currentIndex())
            else:
                err = result.stderr.strip() or result.stdout.strip() or "未知错误"
                logger.error(f"[系统网络] 网卡 IP 添加失败: returncode={result.returncode}, error={err}")
                if self._is_auth_error(result):
                    self._admin_password = None
                self._nic_status.setText(f"添加失败: {err}")
                self._nic_status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")

        def _fail(msg):
            logger.error(f"[系统网络] 网卡 IP 添加执行失败: {msg}")
            self._set_nic_controls_enabled(True)
            self._nic_status.setText(f"执行失败: {msg}")
            self._nic_status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")

        self._run_bg(_work, _apply, _fail)

    def _delete_nic_ip(self):
        iface = self._nic_combo.currentData(Qt.ItemDataRole.UserRole) or self._nic_combo.currentText()
        item = self._nic_tree.currentItem()
        if not item:
            logger.warning("[系统网络] 删除网卡 IP 失败: 未选择 IP")
            return QMessageBox.warning(self.app, "提示", "请先选择要删除的 IP")
        ip = item.text(0)
        reply = QMessageBox.question(self.app, "确认删除",
            f"确认从 {iface} 删除 IP {ip}？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            logger.info(f"[系统网络] 用户取消删除网卡 IP: iface={iface}, ip={ip}")
            return
        self._nic_status.setText("正在删除...")
        self._set_nic_controls_enabled(False)
        if _os() == "Windows":
            cmd = ["netsh", "interface", "ip", "delete", "address", iface, ip]
        else:
            service = self._network_service_for_iface(iface)
            service_info = self._network_service_info(service) if service else {}
            if service and service_info.get("ip") == ip:
                cmd = ["sudo", "networksetup", "-setdhcp", service]
                logger.info(f"[系统网络] 删除 macOS 主 IP 配置: service={service}, ip={ip}")
            else:
                cmd = ["sudo", "ifconfig", iface, "inet", ip, "delete"]
        logger.info(f"[系统网络] 删除网卡 IP: iface={iface}, ip={ip}, cmd={' '.join(cmd)}")

        password = self._get_admin_password()
        if _os() == "Darwin" and password is None:
            logger.info("[系统网络] 删除网卡 IP 取消: 用户取消管理员验证")
            self._set_nic_controls_enabled(True)
            self._nic_status.setText("已取消管理员验证")
            self._nic_status.setStyleSheet(HINT_STYLE)
            return

        def _work():
            return _run_admin(cmd, password=password)

        def _apply(result):
            self._set_nic_controls_enabled(True)
            if result.returncode == 0:
                logger.info(f"[系统网络] 网卡 IP 删除成功: iface={iface}, ip={ip}")
                self._nic_status.setText("IP 已删除")
                self._nic_status.setStyleSheet("font-size: 11px; color: #11a37f; background: transparent;")
                self._on_nic_changed(self._nic_combo.currentIndex())
            else:
                err = result.stderr.strip() or result.stdout.strip() or "未知错误"
                logger.error(f"[系统网络] 网卡 IP 删除失败: returncode={result.returncode}, error={err}")
                if self._is_auth_error(result):
                    self._admin_password = None
                self._nic_status.setText(f"删除失败: {err}")
                self._nic_status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")

        def _fail(msg):
            logger.error(f"[系统网络] 网卡 IP 删除执行失败: {msg}")
            self._set_nic_controls_enabled(True)
            self._nic_status.setText(f"执行失败: {msg}")
            self._nic_status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")

        self._run_bg(_work, _apply, _fail)

    # ═══════════ Hosts Tab ═══════════

    def _build_hosts_ui(self, parent):
        fl = QVBoxLayout(parent)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(8)

        card = QFrame()
        set_card_style(card)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(15, 12, 15, 12)
        cl.setSpacing(8)

        cl.addWidget(self._lbl("HOSTS 文件编辑", H2_STYLE))
        p = _hosts_path()
        cl.addWidget(self._lbl(f"路径: {p}", "font-size: 11px; color: #888; background: transparent;"))

        # Add form
        hf = QHBoxLayout()
        hf.setSpacing(8)

        self._hosts_ip = QLineEdit()
        self._hosts_ip.setPlaceholderText("IP 地址 (如 192.168.1.100)")
        self._hosts_ip.setMinimumHeight(34)
        self._hosts_ip.setStyleSheet("font-size: 13px;")
        hf.addWidget(self._hosts_ip)

        self._hosts_name = QLineEdit()
        self._hosts_name.setPlaceholderText("主机名 (如 dev.local)")
        self._hosts_name.setMinimumHeight(34)
        self._hosts_name.setStyleSheet("font-size: 13px;")
        hf.addWidget(self._hosts_name)

        self._hosts_add_btn = QPushButton("添加")
        self._hosts_add_btn.setStyleSheet(BTN_PRIMARY)
        self._hosts_add_btn.setMinimumHeight(34)
        self._hosts_add_btn.setFixedWidth(60)
        self._hosts_add_btn.clicked.connect(self._hosts_add)
        hf.addWidget(self._hosts_add_btn)
        cl.addLayout(hf)

        # Table
        self._hosts_tree = QTreeWidget()
        self._hosts_tree.setColumnCount(2)
        self._hosts_tree.setHeaderLabels(["IP 地址", "主机名"])
        self._hosts_tree.setRootIsDecorated(False)
        self._hosts_tree.setAlternatingRowColors(True)
        self._hosts_tree.setSelectionMode(self._hosts_tree.SelectionMode.SingleSelection)
        self._hosts_tree.setStyleSheet(_TREE_QSS)
        cl.addWidget(self._hosts_tree)

        # Buttons
        hbr = QHBoxLayout()
        hbr.setSpacing(8)

        self._hosts_del_btn = QPushButton("删除选中")
        self._hosts_del_btn.setStyleSheet(BTN_DANGER)
        self._hosts_del_btn.setMinimumHeight(34)
        self._hosts_del_btn.clicked.connect(self._hosts_delete)
        hbr.addWidget(self._hosts_del_btn)

        self._hosts_save_btn = QPushButton("保存到文件")
        self._hosts_save_btn.setStyleSheet(BTN_PRIMARY)
        self._hosts_save_btn.setMinimumHeight(34)
        self._hosts_save_btn.clicked.connect(self._hosts_save)
        hbr.addWidget(self._hosts_save_btn)

        self._hosts_reload_btn = QPushButton("重新加载")
        self._hosts_reload_btn.setStyleSheet(BTN_SECONDARY)
        self._hosts_reload_btn.setMinimumHeight(34)
        self._hosts_reload_btn.clicked.connect(self._load_hosts)
        hbr.addWidget(self._hosts_reload_btn)
        hbr.addStretch(1)
        cl.addLayout(hbr)

        self._hosts_status = self._lbl("", HINT_STYLE)
        cl.addWidget(self._hosts_status)

        fl.addWidget(card, stretch=1)
        QTimer.singleShot(200, self._load_hosts)

    # ── Hosts operations ──

    def _load_hosts(self):
        logger.info(f"[系统网络] 加载 HOSTS 文件: {_hosts_path()}")
        self._hosts_tree.clear()
        hp = _hosts_path()
        try:
            with open(hp, "r", encoding="utf-8-sig") as f:
                lines = f.readlines()
        except Exception as e:
            logger.exception(f"[系统网络] HOSTS 读取失败: {hp}")
            self._hosts_status.setText(f"读取失败 ({hp}): {e}")
            self._hosts_status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")
            return

        count = 0
        for line in lines:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = s.split()
            if len(parts) >= 2 and self._is_ip(parts[0]):
                ip = parts[0]
                for host in parts[1:]:
                    if host.startswith("#"):
                        break
                    self._hosts_tree.addTopLevelItem(QTreeWidgetItem([ip, host]))
                    count += 1

        for i in range(2):
            self._hosts_tree.header().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        if count == 0:
            raw = "".join(lines[:5]).replace("\n", "|")[:200]
            self._hosts_status.setText(f"共 {count} 条记录（点击「添加」新建）")
            self._hosts_status.setStyleSheet(HINT_STYLE)
        else:
            self._hosts_status.setText(f"共 {count} 条记录")
            self._hosts_status.setStyleSheet(HINT_STYLE)
        self._hosts_raw = lines
        logger.info(f"[系统网络] HOSTS 加载完成: count={count}")

    def _hosts_add(self):
        ip = self._hosts_ip.text().strip()
        host = self._hosts_name.text().strip()
        if not ip or not host:
            logger.warning("[系统网络] HOSTS 添加失败: IP 或主机名为空")
            QMessageBox.warning(self.app, "提示", "IP 地址和主机名不能为空")
            return
        if not self._is_ip(ip):
            logger.warning(f"[系统网络] HOSTS 添加失败: IP 无效 ip={ip}")
            QMessageBox.warning(self.app, "提示", "IP 地址格式不正确")
            return
        self._hosts_tree.addTopLevelItem(QTreeWidgetItem([ip, host]))
        self._hosts_ip.clear()
        self._hosts_name.clear()
        self._hosts_status.setText("已添加到列表，点击「保存到文件」写入磁盘")
        self._hosts_status.setStyleSheet("font-size: 11px; color: #11a37f; background: transparent;")
        logger.info(f"[系统网络] HOSTS 添加到列表: {ip} {host}")

    def _hosts_delete(self):
        item = self._hosts_tree.currentItem()
        if not item:
            logger.warning("[系统网络] HOSTS 删除失败: 未选择记录")
            QMessageBox.warning(self.app, "提示", "请先选择一条 HOSTS 记录")
            return
        ip, host = item.text(0), item.text(1)
        idx = self._hosts_tree.indexOfTopLevelItem(item)
        self._hosts_tree.takeTopLevelItem(idx)
        self._hosts_status.setText("已从列表移除，点击「保存到文件」写入磁盘")
        self._hosts_status.setStyleSheet("font-size: 11px; color: #11a37f; background: transparent;")
        logger.info(f"[系统网络] HOSTS 从列表删除: {ip} {host}")

    def _hosts_save(self):
        hp = _hosts_path()
        logger.info(f"[系统网络] 保存 HOSTS 文件: {hp}")
        new_lines = []
        if hasattr(self, '_hosts_raw'):
            for line in self._hosts_raw:
                s = line.strip()
                if not s or s.startswith("#"):
                    new_lines.append(line.rstrip())
                else:
                    parts = s.split()
                    if len(parts) < 2 or not self._is_ip(parts[0]):
                        new_lines.append(line.rstrip())

        seen = set()
        for i in range(self._hosts_tree.topLevelItemCount()):
            item = self._hosts_tree.topLevelItem(i)
            ip, host = item.text(0), item.text(1)
            key = f"{ip}\t{host}"
            if key not in seen:
                new_lines.append(f"{ip}\t{host}")
                seen.add(key)

        content = "\n".join(new_lines) + "\n"

        if _os() == "Windows":
            tmp = os.path.join(os.environ.get("TEMP", os.path.dirname(hp)), "_hosts_tmp")
        else:
            tmp = "/tmp/_hosts_tmp"
        try:
            with open(tmp, "w") as f:
                f.write(content)
        except Exception as e:
            logger.exception(f"[系统网络] HOSTS 临时文件写入失败: {tmp}")
            self._hosts_status.setText(f"写入临时文件失败: {e}")
            self._hosts_status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")
            return

        if _os() == "Windows":
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                   "-Command", f"Copy-Item -Path '{tmp}' -Destination '{hp}' -Force"]
        else:
            cmd = ["sudo", "cp", tmp, hp]

        try:
            result = self._run_admin_cached(cmd)
            if os.path.exists(tmp):
                os.remove(tmp)
            if result.returncode == 0:
                logger.info(f"[系统网络] HOSTS 保存成功: count={self._hosts_tree.topLevelItemCount()}")
                self._hosts_status.setText("HOSTS 文件已保存")
                self._hosts_status.setStyleSheet("font-size: 11px; color: #11a37f; background: transparent;")
                self._load_hosts()
            else:
                err = result.stderr.strip() or result.stdout.strip() or "未知错误"
                logger.error(f"[系统网络] HOSTS 保存失败: returncode={result.returncode}, error={err}")
                self._hosts_status.setText(f"保存失败: {err}")
                self._hosts_status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")
        except Exception as e:
            logger.exception("[系统网络] HOSTS 保存执行异常")
            self._hosts_status.setText(f"执行失败: {e}")
            self._hosts_status.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")
