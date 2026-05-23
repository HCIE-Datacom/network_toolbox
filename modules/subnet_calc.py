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
        self._summary_text = ctk.CTkTextbox(self._summary_frame,
                                            font=("Courier", 13), corner_radius=8,
                                            height=120, fg_color="#f9f9f9",
                                            text_color="#333333",
                                            border_color="#d1d5db", border_width=1,
                                            activate_scrollbars=True)
        self._summary_text.pack(fill="x")
        self._summary_text.insert("0.0", "192.168.1.0/24\n192.168.2.0/24\n192.168.3.0/24")
        self._summary_text.bind("<KeyRelease>", lambda e: self._calc_summary())

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

            val_label = tk.Label(row_frame, text="-", font=("Courier", -12),
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
                                          height=80, fg_color="#1e1e1e",
                                          text_color="#e0e0e0",
                                          border_width=1, border_color="#e5e5e5",
                                          activate_scrollbars=True)
        self._binary_viz.pack(fill="x")
        self._binary_viz.insert("0.0", "输入 IP 地址和掩码后自动显示...")

        # Summary result area
        self._summary_result = ctk.CTkFrame(self._result_inner, fg_color="transparent")

        tk.Label(self._summary_result, text="地址汇总结果",
                 font=("Helvetica", -12, "bold"), fg="#555555",
                 bg="white", highlightthickness=0, bd=0).pack(anchor="w", pady=(0, 8))

        self._summary_output = ctk.CTkTextbox(self._summary_result,
                                              font=("Courier", 13), corner_radius=8,
                                              height=200, fg_color="#1e1e1e",
                                              text_color="#e0e0e0",
                                              border_width=1, border_color="#e5e5e5",
                                              activate_scrollbars=True)
        self._summary_output.pack(fill="both", expand=True)

        # Start in subnet mode
        self._set_mode("subnet")

    # ── Mode switching ──

    def _set_mode(self, mode):
        self._mode_var.set(mode)
        self._update_mode_buttons()
        if mode == "subnet":
            self._subnet_frame.pack(fill="x", before=self._summary_frame)
            self._summary_frame.pack_forget()
            self._subnet_result.pack(fill="both", expand=True)
            self._summary_result.pack_forget()
        else:
            self._subnet_frame.pack_forget()
            self._summary_frame.pack(fill="x")
            self._subnet_result.pack_forget()
            self._summary_result.pack(fill="both", expand=True)

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
            self._binary_viz.delete("0.0", "end")
            self._binary_viz.insert("0.0", "无法解析输入，请检查格式")
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
            first = list(network.hosts())[0]
            last = list(network.hosts())[-1]
            self._set_result("first_host", str(first))
            self._set_result("last_host", str(last))
            self._set_result("hosts", f"{network.num_addresses - 2} 个")
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
        self._binary_viz.delete("0.0", "end")
        self._binary_viz.insert("0.0", "输入 IP 地址和掩码后自动显示...")

    def _draw_binary_viz(self, network):
        self._binary_viz.delete("0.0", "end")

        net_addr = network.network_address
        bcast = network.broadcast_address
        mask = network.netmask
        prefix = network.prefixlen

        def ip_to_bits(ip):
            return format(int(ip), '032b')

        net_bits = ip_to_bits(net_addr)
        mask_bits = ip_to_bits(mask)
        bcast_bits = ip_to_bits(bcast)

        # Color-coded binary display
        net_display = "网络地址:  "
        mask_display = "子网掩码:  "
        bcast_display = "广播地址: "

        for i in range(4):
            start = i * 8
            end = start + 8
            net_display += net_bits[start:end] + "."
            mask_display += mask_bits[start:end] + "."
            bcast_display += bcast_bits[start:end] + "."

        net_display = net_display.rstrip(".")
        mask_display = mask_display.rstrip(".")
        bcast_display = bcast_display.rstrip(".")

        # Network portion vs host portion
        net_portion = net_bits[:prefix]
        host_portion = net_bits[prefix:]

        viz_text = (
            f"  网络部分 ({prefix} 位): {net_portion}  |  主机部分 ({32-prefix} 位): {host_portion}\n"
            f"\n"
            f"  {net_display}\n"
            f"  {mask_display}\n"
            f"  {bcast_display}"
        )

        self._binary_viz.insert("0.0", viz_text)

    # ── Summary calculation ──

    def _calc_summary(self):
        content = self._summary_text.get("0.0", "end").strip()
        self._summary_output.delete("0.0", "end")

        if not content:
            self._summary_output.insert("0.0", "请输入至少一个网络地址")
            return

        lines = [l.strip() for l in content.splitlines() if l.strip()]

        networks = []
        for line in lines:
            try:
                net = ipaddress.ip_network(line, strict=False)
                networks.append(net)
            except ValueError:
                self._summary_output.insert("0.0", f"错误: 无法解析 \"{line}\"\n")
                return

        if len(networks) == 0:
            self._summary_output.insert("0.0", "未输入有效的网络地址")
            return

        if len(networks) == 1:
            net = networks[0]
            self._summary_output.insert("0.0",
                f"  输入网络: {net}\n"
                f"  汇总结果: {net}\n"
                f"\n"
                f"  （仅输入了一个网络，无需汇总）"
            )
            return

        # Sort networks by network address
        networks.sort(key=lambda n: int(n.network_address))

        # Show individual networks
        self._summary_output.insert("0.0", "  输入网络:\n")
        for net in networks:
            self._summary_output.insert("end", f"    {net:>20s}  (掩码: {net.netmask})\n")

        # Calculate summary route
        try:
            # Use ipaddress.collapse_addresses for best summary
            collapsed = list(ipaddress.collapse_addresses(networks))

            self._summary_output.insert("end", f"\n")

            if len(collapsed) == 1:
                summary = collapsed[0]
                self._summary_output.insert("end",
                    f"  汇总结果: {summary}\n"
                    f"  网络地址: {summary.network_address}\n"
                    f"  广播地址: {summary.broadcast_address}\n"
                    f"  覆盖范围: {summary.num_addresses} 个地址\n"
                    f"  可用主机: {max(0, summary.num_addresses - 2)} 个\n"
                )
            else:
                self._summary_output.insert("end",
                    f"  最优汇总（无法合并为单条路由）:\n"
                )
                for s in collapsed:
                    self._summary_output.insert("end", f"    {s}\n")

            # Also calculate the minimal supernet that covers all
            all_addrs = []
            for net in networks:
                all_addrs.append(int(net.network_address))
                all_addrs.append(int(net.broadcast_address))

            min_addr = min(all_addrs)
            max_addr = max(all_addrs)

            # Find the common prefix
            xor = min_addr ^ max_addr
            if xor == 0:
                supernet_prefix = 32
            else:
                supernet_prefix = 32 - xor.bit_length()

            supernet = ipaddress.ip_network(f"{ipaddress.IPv4Address(min_addr)}/{supernet_prefix}", strict=False)

            if len(collapsed) > 1 or str(collapsed[0]) != str(supernet):
                self._summary_output.insert("end",
                    f"\n  覆盖超网: {supernet} "
                    f"(包含所有输入网络的超网，可能覆盖额外地址)\n"
                )

        except Exception as e:
            self._summary_output.insert("end", f"\n  汇总计算错误: {e}\n")
