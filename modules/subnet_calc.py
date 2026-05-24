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

"""Subnet Calculator module - IP subnet division and route summarization."""

import ipaddress
import customtkinter as ctk
import tkinter as tk

from core.base_module import ToolModule


class SubnetCalcModule(ToolModule):
    name = "子网计算"
    icon = "\U0001F310"  # 🌐
    description = "支持子网划分计算和地址汇总（路由聚合），快速获取网络地址、广播地址、可用主机范围等信息。"

    def build(self, parent):
        # ── helpers ──
        def label(master, text, font=("Helvetica", -13), fg="#333333", **kw):
            return tk.Label(master, text=text, font=font, fg=fg,
                            bg="#f9f9f9", highlightthickness=0, bd=0, **kw)

        def white_label(master, text, font=("Helvetica", -13), fg="#333333", **kw):
            return tk.Label(master, text=text, font=font, fg=fg,
                            bg="white", highlightthickness=0, bd=0, **kw)

        # ── Title ──
        label(parent, text=self.name,
              font=("Helvetica", -22, "bold"), fg="#1f1f1f").pack(anchor="w", pady=(0, 5))
        label(parent, text=self.description,
              font=("Helvetica", -13), fg="#6b6b6b",
              wraplength=620, justify="left").pack(anchor="w", pady=(0, 15))

        # ── Input card ──
        inp_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                border_width=1, border_color="#e5e5e5")
        inp_card.pack(fill="x", pady=(0, 15))
        inp_inner = ctk.CTkFrame(inp_card, fg_color="transparent")
        inp_inner.pack(fill="x", padx=15, pady=15)

        # Mode selector
        mode_row = ctk.CTkFrame(inp_inner, fg_color="transparent")
        mode_row.pack(fill="x", pady=(0, 12))
        white_label(mode_row, text="计算模式",
                    font=("Helvetica", -12, "bold"), fg="#333333").pack(anchor="w", pady=(0, 6))
        self._mode_var = ctk.StringVar(value="subnet")
        mode_btn_frame = ctk.CTkFrame(mode_row, fg_color="#f0f0f0", corner_radius=8)
        mode_btn_frame.pack(fill="x")
        self._mode_btns = {}
        for val, label_text in [("subnet", "子网划分"), ("summary", "地址汇总")]:
            btn = ctk.CTkButton(mode_btn_frame, text=label_text, width=0, height=32,
                                font=("Helvetica", 12), corner_radius=6,
                                fg_color="transparent", text_color="#333333",
                                hover_color="#e0e0e0",
                                command=lambda v=val: self._set_mode(v))
            btn.pack(side="left", expand=True, fill="x", padx=2, pady=2)
            self._mode_btns[val] = btn
        self._update_mode_buttons()

        # ── Subnet mode inputs ──
        self._subnet_frame = ctk.CTkFrame(inp_inner, fg_color="transparent")
        self._subnet_frame.pack(fill="x")

        ip_row = ctk.CTkFrame(self._subnet_frame, fg_color="transparent")
        ip_row.pack(fill="x", pady=(0, 8))
        ip_row.grid_columnconfigure(0, weight=3)
        ip_row.grid_columnconfigure(1, weight=2)

        white_label(ip_row, text="IP 地址",
                    font=("Helvetica", -11), fg="#666666").grid(row=0, column=0, sticky="w")
        self._ip_var = ctk.StringVar(value="")
        self._ip_entry = ctk.CTkEntry(ip_row, textvariable=self._ip_var,
                                      placeholder_text="例如: 192.168.1.100",
                                      font=("Helvetica", 13), corner_radius=8,
                                      height=40, border_color="#d1d5db", border_width=1)
        self._ip_entry.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self._ip_entry.bind("<KeyRelease>", lambda e: self._calc_subnet())

        white_label(ip_row, text="掩码 / CIDR",
                    font=("Helvetica", -11), fg="#666666").grid(row=0, column=1, sticky="w")
        self._mask_var = ctk.StringVar(value="24")
        self._mask_entry = ctk.CTkEntry(ip_row, textvariable=self._mask_var,
                                        placeholder_text="24 或 255.255.255.0",
                                        font=("Helvetica", 13), corner_radius=8,
                                        height=40, border_color="#d1d5db", border_width=1)
        self._mask_entry.grid(row=1, column=1, sticky="ew")
        self._mask_entry.bind("<KeyRelease>", lambda e: self._calc_subnet())

        # ── Summary mode inputs ──
        self._summary_frame = ctk.CTkFrame(inp_inner, fg_color="transparent")
        # (packed/unpacked dynamically)

        white_label(self._summary_frame, text="输入网络地址（每行一个）",
                    font=("Helvetica", -11), fg="#666666").pack(anchor="w", pady=(0, 4))

        # Use tk.Text directly to avoid CTkTextbox input limitations
        text_container = ctk.CTkFrame(self._summary_frame, corner_radius=8,
                                      fg_color="#f9f9f9", border_color="#d1d5db",
                                      border_width=1)
        text_container.pack(fill="x")
        text_inner = tk.Frame(text_container, bg="#f9f9f9", highlightthickness=0, bd=0)
        text_inner.pack(fill="both", expand=True, padx=6, pady=6)

        scrollbar = tk.Scrollbar(text_inner, orient="vertical", width=12,
                                 troughcolor="#e8e8e8", bg="#c0c0c0",
                                 activebackground="#a0a0a0", bd=0,
                                 highlightthickness=0)
        scrollbar.pack(side="right", fill="y")

        self._summary_text_tk = tk.Text(text_inner, font=("Courier", 11),
                                        fg="#333333", bg="#f9f9f9",
                                        insertbackground="#333333",
                                        selectbackground="#b3d9ff",
                                        relief="flat", bd=0,
                                        wrap="word", height=6,
                                        highlightthickness=0, spacing3=4,
                                        yscrollcommand=scrollbar.set)
        self._summary_text_tk.pack(fill="both", expand=True, side="left")
        scrollbar.config(command=self._summary_text_tk.yview)

        # Force tk.Text to handle Return key properly on macOS.
        # macOS CTk apps sometimes route Return to the default button instead of the text widget.
        # We use 'bind' at the widget level and explicitly call tk::TextInsert via tcl.
        text_widget_path = str(self._summary_text_tk)
        def _on_return(event):
            try:
                self._summary_text_tk.tk.call("tk::TextInsert", self._summary_text_tk, "\n")
            except tk.TclError:
                self._summary_text_tk.insert("insert", "\n")
            if self._summary_text_tk.cget("autoseparators"):
                self._summary_text_tk.tk.call(self._summary_text_tk, "edit", "separator")
            return "break"

        # Bind without 'add' to replace any existing binding at widget level
        self._summary_text_tk.bind("<Return>", _on_return)
        self._summary_text_tk.bind("<KP_Enter>", _on_return)

        # Insert default example text
        self._summary_text_tk.insert("1.0", "192.168.1.0/24\n192.168.2.0/24\n192.168.3.0/24")

        summary_btn_row = ctk.CTkFrame(self._summary_frame, fg_color="transparent")
        summary_btn_row.pack(fill="x", pady=(8, 0))
        self._summary_calc_btn = ctk.CTkButton(summary_btn_row, text="计算汇总",
                                                command=self._calc_summary,
                                                width=100, height=34,
                                                font=("Helvetica", 12, "bold"),
                                                corner_radius=8, fg_color="#10a37f",
                                                hover_color="#0d8c6d")
        self._summary_calc_btn.pack(side="left")

        # ── Result card ──
        result_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                   border_width=1, border_color="#e5e5e5")
        result_card.pack(fill="both", expand=True)

        self._result_inner = ctk.CTkFrame(result_card, fg_color="transparent")
        self._result_inner.pack(fill="both", expand=True, padx=15, pady=15)

        # Subnet result area
        self._subnet_result = ctk.CTkFrame(self._result_inner, fg_color="transparent")
        self._subnet_result.pack(fill="both", expand=True)

        # Results grid for subnet mode
        self._result_items = []
        result_data = [
            ("CIDR 表示", "cidr"),
            ("网络地址", "network"),
            ("广播地址", "broadcast"),
            ("子网掩码", "mask"),
            ("掩码（二进制）", "mask_bin"),
            ("第一可用 IP", "first_host"),
            ("最后可用 IP", "last_host"),
            ("可用主机数", "hosts"),
            ("IP 类别", "ip_class"),
            ("是否私有地址", "is_private"),
            ("通配符掩码", "wildcard"),
        ]

        for i, (lbl, key) in enumerate(result_data):
            row_frame = ctk.CTkFrame(self._subnet_result, fg_color="transparent")
            row_frame.pack(fill="x", pady=2)
            row_frame.grid_columnconfigure(1, weight=1)

            # Alternating row background
            bg = "#f9f9f9" if i % 2 == 0 else "white"

            tk.Label(row_frame, text=lbl, font=("Helvetica", -12, "bold"),
                     fg="#555555", bg=bg, width=14, anchor="w",
                     highlightthickness=0, bd=0).grid(row=0, column=0, sticky="w", padx=(0, 10))

            val_label = tk.Label(row_frame, text="-", font=("Helvetica", -12),
                                 fg="#1f1f1f", bg=bg, anchor="w",
                                 highlightthickness=0, bd=0)
            val_label.grid(row=0, column=1, sticky="w")

            self._result_items.append((key, val_label))

        # Binary visualization
        sep = ctk.CTkFrame(self._subnet_result, fg_color="#e5e5e5", height=1)
        sep.pack(fill="x", pady=(12, 8))

        viz_label = tk.Label(self._subnet_result, text="地址二进制视图",
                             font=("Helvetica", -12, "bold"), fg="#555555",
                             bg="white", highlightthickness=0, bd=0)
        viz_label.pack(anchor="w", pady=(0, 6))

        self._binary_viz = ctk.CTkTextbox(self._subnet_result,
                                          font=("Courier", 12), corner_radius=8,
                                          fg_color="#1e1e1e",
                                          text_color="#e0e0e0",
                                          border_width=1, border_color="#e5e5e5",
                                          spacing3=14,
                                          activate_scrollbars=True)
        self._binary_viz.pack(fill="both", expand=True)
        self._binary_viz.insert("1.0", "输入 IP 地址和掩码后自动显示...")

        # Summary result area
        self._summary_result = ctk.CTkFrame(self._result_inner, fg_color="transparent")

        tk.Label(self._summary_result, text="地址汇总结果",
                 font=("Helvetica", -12, "bold"), fg="#555555",
                 bg="white", highlightthickness=0, bd=0).pack(anchor="w", pady=(0, 8))

        self._summary_output = ctk.CTkTextbox(self._summary_result,
                                              font=("Courier", 12), corner_radius=8,
                                              fg_color="#1e1e1e",
                                              text_color="#e0e0e0",
                                              border_width=1, border_color="#e5e5e5",
                                              spacing3=14,
                                              activate_scrollbars=True)
        self._summary_output.pack(fill="both", expand=True)

        # Start in subnet mode
        self._set_mode("subnet")

    # ── Mode switching ──

    def _set_mode(self, mode):
        self._mode_var.set(mode)
        self._update_mode_buttons()
        if mode == "subnet":
            self._subnet_frame.pack(fill="x")
            self._summary_frame.pack_forget()
            self._subnet_result.pack(fill="both", expand=True)
            self._summary_result.pack_forget()
        else:
            self._subnet_frame.pack_forget()
            self._summary_frame.pack(fill="x")
            self._subnet_result.pack_forget()
            self._summary_result.pack(fill="both", expand=True)
            self._calc_summary()

    def _update_mode_buttons(self):
        current = self._mode_var.get()
        for val, btn in self._mode_btns.items():
            if val == current:
                btn.configure(fg_color="#10a37f", text_color="white", hover_color="#0d8c6d")
            else:
                btn.configure(fg_color="transparent", text_color="#333333", hover_color="#e0e0e0")

    # ── Subnet calculation ──

    def _calc_subnet(self):
        ip_str = self._ip_var.get().strip()
        mask_str = self._mask_var.get().strip()

        if not ip_str:
            self._clear_subnet_results()
            return

        # Build CIDR notation
        if mask_str:
            # Check if mask_str is a plain number (CIDR prefix length)
            if mask_str.isdigit():
                cidr_str = f"{ip_str}/{mask_str}"
            else:
                # Treat as dotted mask
                cidr_str = f"{ip_str}/{mask_str}"
        else:
            cidr_str = ip_str

        try:
            network = ipaddress.ip_network(cidr_str, strict=False)
        except ValueError:
            self._set_result("cidr", "输入格式错误")
            for key, lbl in self._result_items:
                if key != "cidr":
                    lbl.configure(text="-")
            self._binary_viz.delete("1.0", "end")
            self._binary_viz.insert("1.0", "无法解析输入，请检查格式")
            return

        # Fill results
        self._set_result("cidr", str(network))
        self._set_result("network", str(network.network_address))
        self._set_result("broadcast", str(network.broadcast_address))
        self._set_result("mask", str(network.netmask))

        # Binary mask
        prefix = network.prefixlen
        bits = '1' * prefix + '0' * (32 - prefix)
        mask_bin = '.'.join([str(int(bits[i:i+8], 2)) for i in range(0, 32, 8)])
        self._set_result("mask_bin", mask_bin + f"  (/{prefix})")

        if network.num_addresses > 2:
            first = ipaddress.IPv4Address(int(network.network_address) + 1)
            last = ipaddress.IPv4Address(int(network.broadcast_address) - 1)
            self._set_result("first_host", str(first))
            self._set_result("last_host", str(last))
            host_count = network.num_addresses - 2
            if host_count > 1000000:
                self._set_result("hosts", f"{host_count:,} 个（{host_count / 1000000:.1f}M）")
            elif host_count > 1000:
                self._set_result("hosts", f"{host_count:,} 个（{host_count / 1000:.1f}K）")
            else:
                self._set_result("hosts", f"{host_count:,} 个")
        else:
            self._set_result("first_host", "-")
            self._set_result("last_host", "-")
            self._set_result("hosts", f"{network.num_addresses - 2} 个（点对点链路）")

        # IP class
        first_octet = int(str(network.network_address).split('.')[0])
        if first_octet <= 126:
            ip_class = "A 类 (1-126)"
        elif first_octet <= 191:
            ip_class = "B 类 (128-191)"
        elif first_octet <= 223:
            ip_class = "C 类 (192-223)"
        elif first_octet <= 239:
            ip_class = "D 类 - 组播 (224-239)"
        else:
            ip_class = "E 类 - 保留 (240-255)"
        self._set_result("ip_class", ip_class)

        self._set_result("is_private", "是" if network.is_private else "否")

        # Wildcard mask
        wc = ipaddress.IPv4Address(int(network.netmask) ^ 0xFFFFFFFF)
        self._set_result("wildcard", str(wc))

        # Binary visualization
        self._draw_binary_viz(network)

    def _set_result(self, key, value):
        for k, lbl in self._result_items:
            if k == key:
                lbl.configure(text=value)
                return

    def _clear_subnet_results(self):
        for k, lbl in self._result_items:
            lbl.configure(text="-")
        self._binary_viz.delete("1.0", "end")
        self._binary_viz.insert("1.0", "输入 IP 地址和掩码后自动显示...")

    def _draw_binary_viz(self, network):
        self._binary_viz.delete("1.0", "end")

        net_addr = network.network_address
        bcast = network.broadcast_address
        mask = network.netmask
        prefix = network.prefixlen

        def ip_to_bits(ip):
            return format(int(ip), '032b')

        net_bits = ip_to_bits(net_addr)
        mask_bits = ip_to_bits(mask)
        bcast_bits = ip_to_bits(bcast)

        # Binary display with aligned labels
        labels = ["网络地址", "子网掩码", "广播地址"]
        bits_list = [net_bits, mask_bits, bcast_bits]
        lines = []
        for label, bits in zip(labels, bits_list):
            octets = [bits[i*8:(i+1)*8] for i in range(4)]
            bits_str = ".".join(octets)
            lines.append(f"  {label.ljust(6, '\u3000')}：{bits_str}")

        # Network portion vs host portion
        net_portion = net_bits[:prefix]
        host_portion = net_bits[prefix:]

        sep = "  " + "─" * 38

        viz_text = "\n".join([
            f"  {'网络部分'.ljust(6, '\u3000')}：({prefix} 位)  {net_portion}",
            f"  {'主机部分'.ljust(6, '\u3000')}：({32-prefix} 位)  {host_portion}",
            sep,
            *lines,
        ])

        self._binary_viz.insert("1.0", viz_text)

    # ── Summary calculation ──

    def _calc_summary(self):
        content = self._summary_text_tk.get("1.0", "end").strip()
        self._summary_output.delete("1.0", "end")

        if not content:
            self._summary_output.insert("1.0", "请输入至少一个网络地址")
            return

        lines = [l.strip() for l in content.splitlines() if l.strip()]

        networks = []
        for line in lines:
            try:
                net = ipaddress.ip_network(line, strict=False)
                networks.append(net)
            except ValueError:
                self._summary_output.insert("1.0", f"错误: 无法解析 \"{line}\"\n")
                return

        if len(networks) == 0:
            self._summary_output.insert("1.0", "未输入有效的网络地址")
            return

        if len(networks) == 1:
            net = networks[0]
            rows = [
                ("输入网络", str(net)),
                ("汇总结果", str(net)),
            ]
            viz_text = "\n".join(f"  {label.ljust(6, '\u3000')}：{value}" for label, value in rows)
            viz_text += "\n\n  （仅输入了一个网络，无需汇总）"
            self._summary_output.insert("1.0", viz_text)
            return

        # Sort networks by network address
        networks.sort(key=lambda n: int(n.network_address))

        # Calculate summary route
        try:
            collapsed = list(ipaddress.collapse_addresses(networks))

            # Build label-value rows
            rows = []

            # Input networks
            rows.append(("输入网络", ", ".join(str(n) for n in networks)))

            # Best summary — show which inputs each collapsed route covers
            if len(collapsed) == 1:
                rows.append(("最优汇总", str(collapsed[0])))
            else:
                detail_lines = []
                for s in collapsed:
                    covered = [str(n) for n in networks if n.subnet_of(s)]
                    if covered:
                        detail_lines.append(f"  {s}（含 {', '.join(covered)}）")
                    else:
                        detail_lines.append(f"  {s}")
                rows.append(("最优汇总", "\n" + "\n".join(detail_lines)))

            # Supernet
            all_addrs = []
            for net in networks:
                all_addrs.append(int(net.network_address))
                all_addrs.append(int(net.broadcast_address))
            min_addr = min(all_addrs)
            max_addr = max(all_addrs)
            xor = min_addr ^ max_addr
            supernet_prefix = 32 if xor == 0 else 32 - xor.bit_length()
            supernet = ipaddress.ip_network(
                f"{ipaddress.IPv4Address(min_addr)}/{supernet_prefix}", strict=False)
            rows.append(("覆盖超网", str(supernet)))

            # Render
            viz_text = "\n".join(
                f"  {label.ljust(6, '\u3000')}：{value}"
                for label, value in rows
            )
            self._summary_output.insert("1.0", viz_text)

        except Exception as e:
            self._summary_output.insert("end", f"\n  汇总计算错误: {e}\n")
