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

"""MAC address vendor lookup using IEEE OUI database."""

import json
import os
import re
import tkinter as tk
import customtkinter as ctk

from core.base_module import ToolModule
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
    # Strip whitespace
    s = mac.strip()
    # Remove all delimiters
    cleaned = re.sub(r'[:\-.]', '', s).upper()

    # Must be hexadecimal
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

    def build(self, parent):
        """Build the UI into the given parent CTkFrame."""

        def label(master, text, font=("Helvetica", -13), fg="#333333", **kw):
            return tk.Label(master, text=text, font=font, fg=fg,
                            bg="#f9f9f9", highlightthickness=0, bd=0, **kw)

        def white_label(master, text, font=("Helvetica", -13), fg="#333333", **kw):
            return tk.Label(master, text=text, font=font, fg=fg,
                            bg="white", highlightthickness=0, bd=0, **kw)

        # Load database
        self._oui_db = _load_oui()
        logger.info(f"[MAC查询] 加载 OUI 数据库: {len(self._oui_db)} 条记录")

        # ── Title + Description ──
        label(parent, text=self.name,
              font=("Helvetica", -22, "bold"), fg="#1f1f1f").pack(anchor="w", pady=(0, 5))
        label(parent, text=self.description,
              font=("Helvetica", -13), fg="#6b6b6b",
              wraplength=620, justify="left").pack(anchor="w", pady=(0, 15))

        # ── Input Card ──
        inp_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                border_width=1, border_color="#e5e5e5")
        inp_card.pack(fill="x", pady=(0, 15))
        inp_inner = ctk.CTkFrame(inp_card, fg_color="transparent")
        inp_inner.pack(fill="x", padx=15, pady=15)

        white_label(inp_inner, text="MAC 地址",
                    font=("Helvetica", -12, "bold"), fg="#333333").pack(anchor="w", pady=(0, 8))

        entry_row = ctk.CTkFrame(inp_inner, fg_color="transparent")
        entry_row.pack(fill="x")

        self._mac_var = ctk.StringVar()
        self._mac_entry = ctk.CTkEntry(entry_row, textvariable=self._mac_var,
                                        placeholder_text="例如: 28:6F:B9:00:00:01 或 286FB9",
                                        font=("Helvetica", 13), corner_radius=8,
                                        height=42, border_color="#d1d5db", border_width=1)
        self._mac_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self._mac_entry.bind("<Return>", lambda e: self._do_lookup())

        self._lookup_btn = ctk.CTkButton(entry_row, text="查询", command=self._do_lookup,
                                         width=80, height=42, font=("Helvetica", 13, "bold"),
                                         corner_radius=8, fg_color="#10a37f", hover_color="#0d8c6d")
        self._lookup_btn.pack(side="right")

        # Format hint
        hint_row = ctk.CTkFrame(inp_inner, fg_color="transparent")
        hint_row.pack(fill="x", pady=(6, 0))
        white_label(hint_row, text="支持格式: XX:XX:XX:XX:XX:XX  |  XX-XX-XX-XX-XX-XX  |  XXXX.XXXX.XXXX  |  纯十六进制",
                    font=("Helvetica", -10), fg="#999999").pack(anchor="w")

        # ── Result Card ──
        result_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                   border_width=1, border_color="#e5e5e5")
        result_card.pack(fill="x", pady=(0, 15))
        result_inner = ctk.CTkFrame(result_card, fg_color="transparent")
        result_inner.pack(fill="x", padx=15, pady=15)

        white_label(result_inner, text="查询结果",
                    font=("Helvetica", -14, "bold"), fg="#1f1f1f").pack(anchor="w", pady=(0, 12))

        self._result_frame = ctk.CTkFrame(result_inner, fg_color="transparent")
        self._result_frame.pack(fill="x")

        self._result_oui_label = white_label(self._result_frame, text="",
                                              font=("Helvetica", -12), fg="#666666")
        self._result_oui_label.pack(anchor="w")
        self._result_name_label = white_label(self._result_frame, text="",
                                              font=("Helvetica", -20, "bold"), fg="#10a37f")
        self._result_name_label.pack(anchor="w", pady=(4, 0))
        self._result_addr_label = white_label(self._result_frame, text="",
                                              font=("Helvetica", -12), fg="#666666",
                                              wraplength=600, justify="left")
        self._result_addr_label.pack(anchor="w", pady=(4, 0))
        self._result_full_label = white_label(self._result_frame, text="",
                                              font=("Helvetica", -11), fg="#999999")
        self._result_full_label.pack(anchor="w", pady=(8, 0))

        # Show placeholder
        self._show_placeholder()

        # ── Recent History Card ──
        hist_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                  border_width=1, border_color="#e5e5e5")
        hist_card.pack(fill="both", expand=True)
        hist_inner = ctk.CTkFrame(hist_card, fg_color="transparent")
        hist_inner.pack(fill="both", expand=True, padx=15, pady=15)

        hist_header = ctk.CTkFrame(hist_inner, fg_color="transparent")
        hist_header.pack(fill="x", pady=(0, 8))
        white_label(hist_header, text="查询历史",
                    font=("Helvetica", -14, "bold"), fg="#1f1f1f").pack(side="left")

        self._history_list = ctk.CTkTextbox(hist_inner, font=("Courier", 12),
                                            corner_radius=8, fg_color="#f9f9f9",
                                            text_color="#333333", border_width=1,
                                            border_color="#e5e5e5")
        self._history_list.pack(fill="both", expand=True)
        self._history_list.configure(state="disabled")

        self._history = []  # list of (mac, oui, name)

    def _show_placeholder(self):
        """Show default placeholder in result area."""
        self._result_oui_label.configure(text="")
        self._result_name_label.configure(text="输入 MAC 地址并点击查询", fg="#999999",
                                          font=("Helvetica", -13))
        self._result_addr_label.configure(text="")
        self._result_full_label.configure(text="")

    def _do_lookup(self):
        """Perform MAC address lookup."""
        mac_str = self._mac_var.get().strip()
        if not mac_str:
            self._show_placeholder()
            return

        oui, full = _normalize_mac(mac_str)
        if oui is None:
            self._show_placeholder()
            self._result_name_label.configure(text="无效的 MAC 地址格式", fg="#dc2626",
                                              font=("Helvetica", -13))
            return

        # Format display
        oui_display = _format_mac(oui + "000000")[:8] + "..."
        full_display = _format_mac(full) if len(full) == 12 else oui_display

        info = self._oui_db.get(oui)
        if info:
            self._result_oui_label.configure(text=f"OUI: {oui_display}")
            self._result_name_label.configure(text=info["name"], fg="#10a37f",
                                              font=("Helvetica", -20, "bold"))
            addr = info.get("addr", "").replace("\n", "  |  ")
            self._result_addr_label.configure(text=addr if addr else "")
            self._result_full_label.configure(text=f"完整 MAC: {full_display}")
            logger.info(f"[MAC查询] {mac_str} -> {oui} -> {info['name']}")
        else:
            self._result_oui_label.configure(text=f"OUI: {oui_display}")
            self._result_name_label.configure(text="未找到匹配的厂商", fg="#f59e0b",
                                              font=("Helvetica", -16))
            self._result_addr_label.configure(text="")
            self._result_full_label.configure(text=f"完整 MAC: {full_display}")
            logger.info(f"[MAC查询] {mac_str} -> {oui} -> 未找到")

        # Add to history
        entry = (full_display, oui, self._result_name_label.cget("text"))
        if info:
            entry = (full_display, oui, info["name"])
        self._history.insert(0, entry)
        if len(self._history) > 50:
            self._history = self._history[:50]
        self._update_history()

    def _update_history(self):
        """Refresh history list."""
        self._history_list.configure(state="normal")
        self._history_list.delete("1.0", "end")

        for full_mac, oui, name in self._history:
            oui_display = _format_mac(oui)
            line = f"{oui_display:<18} {name:<30} ({full_mac})\n"
            self._history_list.insert("end", line)

        self._history_list.configure(state="disabled")
