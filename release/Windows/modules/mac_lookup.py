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

"""MAC address vendor lookup using IEEE OUI database (PySide6 edition)."""

import json
import os
import re

from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QPlainTextEdit,
)
from PySide6.QtCore import Qt

from core.base_module import ToolModule
from core.app import BTN_PRIMARY, BTN_DANGER, BTN_SECONDARY, set_card_style, set_transparent_bg, set_dark_output
from core.app import H1_STYLE, H2_STYLE, H3_STYLE, BODY_STYLE, HINT_STYLE, DESC_STYLE
from core.logger import logger


def _load_oui():
    """Load OUI database from JSON. Returns dict: {prefix_hex: {name, addr}}."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    db_path = os.path.join(data_dir, "oui.json")
    if not os.path.exists(db_path):
        return {}
    with open(db_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_mac(mac: str):
    """Parse a MAC address string and return the 6-char uppercase hex OUI.

    Accepted formats:
        XX:XX:XX:XX:XX:XX, XX-XX-XX-XX-XX-XX,
        XXXX.XXXX.XXXX (Cisco), XXXXXXXXXXXX (bare),
        XX:XX:XX (OUI only)

    Returns (oui_hex, full_hex) or (None, None) on failure.
    """
    s = mac.strip()
    cleaned = re.sub(r'[:\-.]', '', s).upper()
    if not re.fullmatch(r'[0-9A-F]{6,12}', cleaned):
        return None, None
    if len(cleaned) < 6:
        return None, None
    oui = cleaned[:6]
    full = cleaned[:12] if len(cleaned) >= 12 else cleaned
    return oui, full


def _format_mac(hex_str: str):
    """Format a hex string as XX:XX:XX:XX:XX:XX."""
    chunks = [hex_str[i:i + 2] for i in range(0, len(hex_str), 2)]
    return ":".join(chunks)


class MACLookupModule(ToolModule):
    """MAC address vendor lookup tool."""

    name = "MAC 地址查询"
    icon = "\U0001f4cd"  # 📍
    description = "基于 IEEE OUI 数据库查询 MAC 地址厂商信息，支持多种 MAC 格式输入。"

    def build(self, parent: QWidget):
        """Build the UI into the given parent QWidget."""
        # Ensure parent has a layout
        if parent.layout() is None:
            parent.setLayout(QVBoxLayout(parent))
        layout = parent.layout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Load database
        self._oui_db = _load_oui()
        logger.info(f"[MAC查询] 加载 OUI 数据库: {len(self._oui_db)} 条记录")

        # ── Title + Description ──
        title = QLabel(self.name)
        title.setStyleSheet(H1_STYLE)
        layout.addWidget(title)
        layout.addSpacing(5)

        desc = QLabel(self.description)
        desc.setStyleSheet(DESC_STYLE)
        desc.setWordWrap(True)
        layout.addWidget(desc)
        layout.addSpacing(15)

        # ── Input Card ──
        inp_card = QFrame()
        set_card_style(inp_card)
        inp_card_layout = QVBoxLayout(inp_card)
        inp_card_layout.setContentsMargins(15, 12, 15, 12)
        inp_card_layout.setSpacing(6)

        lb = QLabel("MAC 地址")
        lb.setStyleSheet(BODY_STYLE)
        inp_card_layout.addWidget(lb)

        entry_row = QWidget()
        set_transparent_bg(entry_row)
        er_layout = QHBoxLayout(entry_row)
        er_layout.setContentsMargins(0, 0, 0, 0)
        er_layout.setSpacing(10)

        self._mac_entry = QLineEdit()
        self._mac_entry.setPlaceholderText("例如: 28:6F:B9:00:00:01 或 286FB9")
        self._mac_entry.setMinimumHeight(40)
        self._mac_entry.returnPressed.connect(self._do_lookup)
        er_layout.addWidget(self._mac_entry, stretch=1)

        self._lookup_btn = QPushButton("查询")
        self._lookup_btn.setStyleSheet(BTN_PRIMARY)
        self._lookup_btn.setFixedSize(80, 40)
        self._lookup_btn.clicked.connect(self._do_lookup)
        er_layout.addWidget(self._lookup_btn)

        inp_card_layout.addWidget(entry_row)

        hint = QLabel("支持格式: XX:XX:XX:XX:XX:XX  |  XX-XX-XX-XX-XX-XX  |  XXXX.XXXX.XXXX  |  纯十六进制")
        hint.setStyleSheet(HINT_STYLE)
        inp_card_layout.addWidget(hint)

        layout.addWidget(inp_card)
        layout.addSpacing(15)

        # ── Result Card ──
        result_card = QFrame()
        set_card_style(result_card)
        rc_layout = QVBoxLayout(result_card)
        rc_layout.setContentsMargins(15, 12, 15, 12)
        rc_layout.setSpacing(4)

        rh = QLabel("查询结果")
        rh.setStyleSheet(H2_STYLE + " color: #1f1f1f;")
        rc_layout.addWidget(rh)
        rc_layout.addSpacing(8)

        self._result_oui_label = QLabel("")
        self._result_oui_label.setStyleSheet(H3_STYLE + " color: #666666;")
        rc_layout.addWidget(self._result_oui_label)

        self._result_name_label = QLabel("")
        self._result_name_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #10a37f; background: transparent;")
        rc_layout.addWidget(self._result_name_label)

        self._result_addr_label = QLabel("")
        self._result_addr_label.setStyleSheet(H3_STYLE + " color: #666666;")
        self._result_addr_label.setWordWrap(True)
        rc_layout.addWidget(self._result_addr_label)

        self._result_full_label = QLabel("")
        self._result_full_label.setStyleSheet(HINT_STYLE + " color: #999999;")
        rc_layout.addWidget(self._result_full_label)

        layout.addWidget(result_card)
        layout.addSpacing(15)

        # Placeholder
        self._show_placeholder()

        # ── History Card ──
        hist_card = QFrame()
        set_card_style(hist_card)
        hc_layout = QVBoxLayout(hist_card)
        hc_layout.setContentsMargins(15, 12, 15, 12)
        hc_layout.setSpacing(8)

        hh = QLabel("查询历史")
        hh.setStyleSheet(H2_STYLE + " color: #1f1f1f;")
        hc_layout.addWidget(hh)

        self._history_list = QPlainTextEdit()
        self._history_list.setReadOnly(True)
        set_dark_output(self._history_list)
        hc_layout.addWidget(self._history_list, stretch=1)

        layout.addWidget(hist_card, stretch=1)

        self._history = []

    def _show_placeholder(self):
        self._result_oui_label.setText("")
        self._result_name_label.setText("输入 MAC 地址并点击查询")
        self._result_name_label.setStyleSheet(BODY_STYLE + " color: #999999;")
        self._result_addr_label.setText("")
        self._result_full_label.setText("")

    def _do_lookup(self):
        mac_str = self._mac_entry.text().strip()
        if not mac_str:
            self._show_placeholder()
            return

        oui, full = _normalize_mac(mac_str)
        if oui is None:
            self._show_placeholder()
            self._result_name_label.setText("无效的 MAC 地址格式")
            self._result_name_label.setStyleSheet(BODY_STYLE + " color: #dc2626; font-weight: bold;")
            return

        oui_display = _format_mac(oui + "000000")[:8] + "..."
        full_display = _format_mac(full) if len(full) == 12 else oui_display

        info = self._oui_db.get(oui)
        if info:
            self._result_oui_label.setText(f"OUI: {oui_display}")
            self._result_name_label.setText(info["name"])
            self._result_name_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #10a37f; background: transparent;")
            addr = info.get("addr", "").replace("\n", "  |  ")
            self._result_addr_label.setText(addr if addr else "")
            self._result_full_label.setText(f"完整 MAC: {full_display}")
            logger.info(f"[MAC查询] {mac_str} -> {oui} -> {info['name']}")
            name = info["name"]
        else:
            self._result_oui_label.setText(f"OUI: {oui_display}")
            self._result_name_label.setText("未找到匹配的厂商")
            self._result_name_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #f59e0b; background: transparent;")
            self._result_addr_label.setText("")
            self._result_full_label.setText(f"完整 MAC: {full_display}")
            logger.info(f"[MAC查询] {mac_str} -> {oui} -> 未找到")
            name = "未找到匹配的厂商"

        # Add to history
        entry = (full_display, oui, name)
        self._history.insert(0, entry)
        if len(self._history) > 50:
            self._history = self._history[:50]
        self._update_history()

    def _update_history(self):
        self._history_list.setReadOnly(False)
        self._history_list.clear()
        for full_mac, oui, name in self._history:
            oui_display = _format_mac(oui)
            line = f"{oui_display:<18} {name:<30} ({full_mac})"
            self._history_list.appendPlainText(line)
        self._history_list.setReadOnly(True)
