"""
NetTool - Network Toolbox
Version: V100R009C00SPC500
Author: Tang Wenbo (HCIE-Datacom)
Copyright (C) 2026 Tang Wenbo
License: GNU General Public License v3.0 or later

Subnet calculation, CIDR planning, and route summarization module.
"""

import ipaddress

from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QPlainTextEdit,
)
from PySide6.QtCore import Qt

from core.base_module import ToolModule
from core.app import (
    BTN_PRIMARY, BTN_DANGER, BTN_SECONDARY, BTN_MODE_ACTIVE, BTN_MODE_INACTIVE,
    set_card_style, set_transparent_bg, set_dark_output,
    H1_STYLE, H2_STYLE, H3_STYLE, BODY_STYLE, HINT_STYLE, DESC_STYLE,
)
from core.logger import logger

IDSP = '\u3000'

class SubnetCalcModule(ToolModule):
    name = "子网计算"
    icon = "subnet"
    description = "支持子网划分计算和地址汇总（路由聚合），快速获取网络地址、广播地址、可用主机范围等信息。"

    def build(self, parent: QWidget):
        if parent.layout() is None:
            parent.setLayout(QVBoxLayout(parent))
        layout = parent.layout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Title ──
        title = QLabel(self.name)
        title.setStyleSheet(H1_STYLE)
        layout.addWidget(title)
        layout.addSpacing(5)

        desc = QLabel(self.description)
        desc.setStyleSheet(DESC_STYLE)
        desc.setWordWrap(True)
        layout.addWidget(desc)
        layout.addSpacing(15)

        # ── Input card ──
        inp_card = QFrame()
        set_card_style(inp_card)
        ic_layout = QVBoxLayout(inp_card)
        ic_layout.setContentsMargins(15, 12, 15, 12)
        ic_layout.setSpacing(10)

        # Mode selector
        mode_label = QLabel("计算模式")
        mode_label.setStyleSheet(H2_STYLE)
        ic_layout.addWidget(mode_label)

        mode_btn_wrapper = QWidget()
        mode_btn_wrapper.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        mode_btn_wrapper.setStyleSheet(
            "background: #eef0f2; border: 1px solid #e2e5e9; border-radius: 8px;"
        )
        mbl = QHBoxLayout(mode_btn_wrapper)
        mbl.setContentsMargins(4, 4, 4, 4)
        mbl.setSpacing(4)

        self._mode_btns = {}
        for val, text in [("subnet", "子网划分"), ("summary", "地址汇总")]:
            btn = QPushButton(text)
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, v=val: self._set_mode(v))
            mbl.addWidget(btn, stretch=1)
            self._mode_btns[val] = btn
        ic_layout.addWidget(mode_btn_wrapper)

        self._update_mode_buttons(val="subnet")

        # ── Subnet inputs ──
        self._subnet_frame = QWidget()
        set_transparent_bg(self._subnet_frame)
        sfl = QVBoxLayout(self._subnet_frame)
        sfl.setContentsMargins(0, 0, 0, 0)
        sfl.setSpacing(8)
        ic_layout.addWidget(self._subnet_frame)

        ip_grid = QGridLayout()
        ip_grid.setColumnStretch(0, 3)
        ip_grid.setColumnStretch(1, 2)
        ip_grid.setContentsMargins(0, 0, 0, 0)
        sfl.addLayout(ip_grid)

        QLabel("IP 地址").setStyleSheet(HINT_STYLE)
        ip_grid.addWidget(self._make_hint("IP 地址"), 0, 0)

        self._ip_entry = QLineEdit()
        self._ip_entry.setPlaceholderText("例如: 192.168.1.100")
        self._ip_entry.setMinimumHeight(38)
        self._ip_entry.textChanged.connect(lambda: self._calc_subnet())
        ip_grid.addWidget(self._ip_entry, 1, 0)
        ip_grid.setContentsMargins(0, 0, 8, 0)

        ip_grid.addWidget(self._make_hint("掩码 / CIDR"), 0, 1)

        self._mask_entry = QLineEdit()
        self._mask_entry.setPlaceholderText("24 或 255.255.255.0")
        self._mask_entry.setText("24")
        self._mask_entry.setMinimumHeight(38)
        self._mask_entry.textChanged.connect(lambda: self._calc_subnet())
        ip_grid.addWidget(self._mask_entry, 1, 1)

        # ── Summary inputs ──
        self._summary_frame = QWidget()
        set_transparent_bg(self._summary_frame)
        sfl2 = QVBoxLayout(self._summary_frame)
        sfl2.setContentsMargins(0, 0, 0, 0)
        sfl2.setSpacing(6)
        ic_layout.addWidget(self._summary_frame)
        self._summary_frame.hide()

        sfl2.addWidget(self._make_hint("输入网络地址（每行一个）"))

        self._summary_input = QPlainTextEdit()
        self._summary_input.setStyleSheet("""
            QPlainTextEdit {
                border: 1px solid #dfe3e8; border-radius: 8px;
                background: #ffffff; color: #20242a;
                font-family: "Cascadia Code", "Consolas", "SF Mono", "Menlo", "Microsoft YaHei", "Courier New", monospace; font-size: 11px;
                padding: 6px;
            }
        """)
        self._summary_input.setFixedHeight(120)
        self._summary_input.setPlainText("192.168.1.0/24\n192.168.2.0/24\n192.168.3.0/24")
        sfl2.addWidget(self._summary_input)

        btn_row = QWidget()
        set_transparent_bg(btn_row)
        brl = QHBoxLayout(btn_row)
        brl.setContentsMargins(0, 0, 0, 0)
        self._summary_calc_btn = QPushButton("计算汇总")
        self._summary_calc_btn.setStyleSheet(BTN_PRIMARY)
        self._summary_calc_btn.setFixedSize(100, 34)
        self._summary_calc_btn.clicked.connect(self._calc_summary)
        brl.addWidget(self._summary_calc_btn)
        brl.addStretch(1)
        sfl2.addWidget(btn_row)

        layout.addWidget(inp_card)
        layout.addSpacing(15)

        # ── Result card ──
        result_card = QFrame()
        set_card_style(result_card)
        rc_layout = QVBoxLayout(result_card)
        rc_layout.setContentsMargins(15, 12, 15, 12)
        rc_layout.setSpacing(0)

        # Subnet result
        self._subnet_result = QWidget()
        set_transparent_bg(self._subnet_result)
        sr_layout = QVBoxLayout(self._subnet_result)
        sr_layout.setContentsMargins(0, 0, 0, 0)
        sr_layout.setSpacing(2)
        rc_layout.addWidget(self._subnet_result, stretch=1)

        self._result_labels = {}
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
            row = QWidget()
            set_transparent_bg(row)
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 2, 0, 2)

            l = QLabel(lbl)
            l.setStyleSheet(H3_STYLE)
            l.setFixedWidth(120)
            rl.addWidget(l)

            v = QLabel("-")
            v.setStyleSheet(BODY_STYLE)
            rl.addWidget(v, stretch=1)

            sr_layout.addWidget(row)
            self._result_labels[key] = v

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.NoFrame)
        sep.setLineWidth(0)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #e1e5e9; border: none;")
        sr_layout.addWidget(sep)
        sr_layout.addSpacing(8)

        viz_title = QLabel("地址二进制视图")
        viz_title.setStyleSheet(H3_STYLE)
        sr_layout.addWidget(viz_title)
        sr_layout.addSpacing(6)

        self._binary_viz = QPlainTextEdit()
        self._binary_viz.setReadOnly(True)
        set_dark_output(self._binary_viz)
        self._binary_viz.setPlainText("输入 IP 地址和掩码后自动显示...")
        sr_layout.addWidget(self._binary_viz, stretch=1)

        # Summary result
        self._summary_result = QWidget()
        set_transparent_bg(self._summary_result)
        smr_layout = QVBoxLayout(self._summary_result)
        smr_layout.setContentsMargins(0, 0, 0, 0)
        rc_layout.addWidget(self._summary_result, stretch=1)
        self._summary_result.hide()

        sh = QLabel("地址汇总结果")
        sh.setStyleSheet(H3_STYLE)
        smr_layout.addWidget(sh)
        smr_layout.addSpacing(8)

        self._summary_output = QPlainTextEdit()
        self._summary_output.setReadOnly(True)
        set_dark_output(self._summary_output)
        smr_layout.addWidget(self._summary_output, stretch=1)

        layout.addWidget(result_card, stretch=1)

    def _make_hint(self, text):
        l = QLabel(text)
        l.setStyleSheet(HINT_STYLE)
        return l

    # ── Mode switching ──

    def _set_mode(self, mode):
        logger.info(f"[子网计算] 切换模式: {mode}")
        self._update_mode_buttons(mode)
        if mode == "subnet":
            self._subnet_frame.show()
            self._summary_frame.hide()
            self._subnet_result.show()
            self._summary_result.hide()
        else:
            self._subnet_frame.hide()
            self._summary_frame.show()
            self._subnet_result.hide()
            self._summary_result.show()
            self._calc_summary()

    def _update_mode_buttons(self, val=None):
        if val is None:
            return
        for v, btn in self._mode_btns.items():
            if v == val:
                btn.setStyleSheet(BTN_MODE_ACTIVE)
            else:
                btn.setStyleSheet(BTN_MODE_INACTIVE)

    # ── Subnet calculation ──

    def _calc_subnet(self):
        ip_str = self._ip_entry.text().strip()
        mask_str = self._mask_entry.text().strip()

        if not ip_str:
            self._clear_subnet_results()
            return

        if mask_str.isdigit():
            cidr_str = f"{ip_str}/{mask_str}"
        elif mask_str:
            cidr_str = f"{ip_str}/{mask_str}"
        else:
            cidr_str = ip_str

        try:
            network = ipaddress.ip_network(cidr_str, strict=False)
        except ValueError:
            logger.warning(f"[子网计算] 子网输入格式错误: {cidr_str}")
            self._set_result("cidr", "输入格式错误")
            for k in self._result_labels:
                if k != "cidr":
                    self._result_labels[k].setText("-")
            self._binary_viz.setPlainText("无法解析输入，请检查格式")
            return

        self._set_result("cidr", str(network))
        self._set_result("network", str(network.network_address))
        self._set_result("broadcast", str(network.broadcast_address))
        self._set_result("mask", str(network.netmask))

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

        wc = ipaddress.IPv4Address(int(network.netmask) ^ 0xFFFFFFFF)
        self._set_result("wildcard", str(wc))

        self._draw_binary_viz(network)
        log_key = str(network)
        if getattr(self, "_last_logged_subnet", None) != log_key:
            self._last_logged_subnet = log_key
            logger.info(
                f"[子网计算] 计算完成: input={cidr_str}, network={network}, "
                f"hosts={max(network.num_addresses - 2, 0)}"
            )

    def _set_result(self, key, value):
        if key in self._result_labels:
            self._result_labels[key].setText(value)

    def _clear_subnet_results(self):
        for lbl in self._result_labels.values():
            lbl.setText("-")
        self._binary_viz.setPlainText("输入 IP 地址和掩码后自动显示...")

    def _draw_binary_viz(self, network):
        net_addr = network.network_address
        bcast = network.broadcast_address
        mask = network.netmask
        prefix = network.prefixlen

        def ip_to_bits(ip):
            return format(int(ip), '032b')

        net_bits = ip_to_bits(net_addr)
        mask_bits = ip_to_bits(mask)
        bcast_bits = ip_to_bits(bcast)

        labels = ["网络地址", "子网掩码", "广播地址"]
        bits_list = [net_bits, mask_bits, bcast_bits]
        lines = []
        for label, bits in zip(labels, bits_list):
            octets = [bits[i*8:(i+1)*8] for i in range(4)]
            bits_str = ".".join(octets)
            lines.append(f"  {label.ljust(6, IDSP)}：{bits_str}")

        net_portion = net_bits[:prefix]
        host_portion = net_bits[prefix:]
        sep_line = "  " + "\u2500" * 38

        viz_text = "\n\n".join([
            f"  {'网络部分'.ljust(6, IDSP)}：({prefix} 位)  {net_portion}",
            f"  {'主机部分'.ljust(6, IDSP)}：({32-prefix} 位)  {host_portion}",
            sep_line,
            *lines,
        ])
        self._binary_viz.setPlainText(viz_text)

    # ── Summary calculation ──

    def _calc_summary(self):
        content = self._summary_input.toPlainText().strip()

        if not content:
            logger.warning("[子网计算] 地址汇总失败: 输入为空")
            self._summary_output.setPlainText("请输入至少一个网络地址")
            return

        lines = [l.strip() for l in content.splitlines() if l.strip()]
        networks = []
        for line in lines:
            try:
                net = ipaddress.ip_network(line, strict=False)
                networks.append(net)
            except ValueError:
                logger.warning(f"[子网计算] 地址汇总解析失败: {line}")
                self._summary_output.setPlainText(f'错误: 无法解析 "{line}"')
                return

        if not networks:
            logger.warning("[子网计算] 地址汇总失败: 无有效网络")
            self._summary_output.setPlainText("未输入有效的网络地址")
            return

        if len(networks) == 1:
            net = networks[0]
            rows = [("输入网络", str(net)), ("汇总结果", str(net))]
            viz_text = "\n\n".join(f"  {l.ljust(6, IDSP)}：{v}" for l, v in rows)
            viz_text += "\n\n  （仅输入了一个网络，无需汇总）"
            self._summary_output.setPlainText(viz_text)
            logger.info(f"[子网计算] 地址汇总完成: single={net}")
            return

        networks.sort(key=lambda n: int(n.network_address))

        try:
            collapsed = list(ipaddress.collapse_addresses(networks))
            rows = [("输入网络", ", ".join(str(n) for n in networks))]

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

            viz_text = "\n\n".join(f"  {l.ljust(6, IDSP)}：{v}" for l, v in rows)
            self._summary_output.setPlainText(viz_text)
            logger.info(
                f"[子网计算] 地址汇总完成: input={len(networks)} 条, "
                f"collapsed={', '.join(str(n) for n in collapsed)}, supernet={supernet}"
            )

        except Exception as e:
            logger.exception("[子网计算] 地址汇总异常")
            self._summary_output.setPlainText(f"\n  汇总计算错误: {e}")
