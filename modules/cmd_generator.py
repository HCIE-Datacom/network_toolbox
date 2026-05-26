"""
NetTool - Network Toolbox
Copyright (C) 2026 Tang Wenbo (HCIE-Datacom)

Command generator module - template-based batch command generation (PySide6 edition).
"""

import json
import os

from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QPlainTextEdit, QComboBox,
    QCheckBox, QProgressBar, QMenu, QInputDialog, QFileDialog, QMessageBox,
    QApplication,
)
from PySide6.QtCore import Qt

from core.base_module import ToolModule
from core.app import BTN_PRIMARY, BTN_DANGER, BTN_SECONDARY, set_card_style, set_transparent_bg, set_dark_output
from core.app import H1_STYLE, H2_STYLE, H3_STYLE, BODY_STYLE, HINT_STYLE, DESC_STYLE
from core.logger import logger




BUILTIN_TEMPLATES = {
    "自定义": "",
    "VLANIF 接口配置": "interface Vlanif{1}\n ip address 10.10.{2}.254 255.255.255.0",
    "Eth-Trunk 接口配置": (
        "interface Eth-Trunk{1}\n"
        " mode lacp\n"
        " trunkport XG 1/8/0/{2}\n"
        " trunkport XG 2/8/0/{3}\n"
        " port link-type trunk\n"
        " undo port trunk allow-pass vlan 1\n"
        " port trunk allow-pass vlan 3162\n"
        " quit"
    ),
}

def _get_project_root():
    """Find project root by walking up until we find the data/ directory."""
    p = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):  # safety limit
        if os.path.isdir(os.path.join(p, "data")):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    # Fallback: use known path
    return "/Users/tangwenbo/Desktop/project/network_toolbox"

_user_templates_file = os.path.join(_get_project_root(), "templates", "templates_user.json")


def _load_user_templates():
    try:
        if os.path.exists(_user_templates_file):
            with open(_user_templates_file, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_user_templates(data):
    os.makedirs(os.path.dirname(_user_templates_file), exist_ok=True)
    with open(_user_templates_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"[CmdGen] 模板已保存到: {_user_templates_file}")


class CmdGeneratorModule(ToolModule):
    name = "命令生成器"
    icon = "\u2328\ufe0f"
    description = "基于模板批量生成网络配置命令，支持内置/自定义模板，变量步进和同步循环生成。"

    def build(self, parent: QWidget):
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

        # Template card
        templ_card = QFrame()
        set_card_style(templ_card)
        tc_layout = QVBoxLayout(templ_card)
        tc_layout.setContentsMargins(15, 12, 15, 12)
        tc_layout.setSpacing(6)

        th = QLabel("命令模板")
        th.setStyleSheet(H2_STYLE + " color: #1f1f1f;")
        tc_layout.addWidget(th)

        # Template selector + save
        sel_row = QWidget()
        set_transparent_bg(sel_row)
        srl = QHBoxLayout(sel_row)
        srl.setContentsMargins(0, 0, 0, 0)
        srl.setSpacing(8)

        self._templ_combo = QComboBox()
        self._templ_combo.setMinimumWidth(160)
        self._templ_combo.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._templ_combo.customContextMenuRequested.connect(self._show_template_menu)
        self._rebuild_combo()
        self._templ_combo.currentIndexChanged.connect(self._on_template_select)
        srl.addWidget(self._templ_combo)

        save_btn = QPushButton("\u2795 \u53e6\u5b58\u4e3a\u6a21\u677f...")
        save_btn.setStyleSheet("""
            QPushButton { background: #f0f0f0; color: #333; border: 1px solid #d1d5db;
            border-radius: 6px; padding: 4px 12px; font-size: 11px; }
            QPushButton:hover { background: #e0e0e0; }
        """)
        save_btn.clicked.connect(self._save_current_template)
        srl.addWidget(save_btn)
        srl.addStretch(1)
        tc_layout.addWidget(sel_row)

        # Hint label
        hint = QLabel("提示：使用 {1} ~ {5} 作为参数占位符，分别对应下方参数 1~5")
        hint.setStyleSheet("font-size: 11px; color: #888; background: transparent; padding: 2px 0;")
        tc_layout.addWidget(hint)

        # Template input
        self._templ_text = QPlainTextEdit()
        self._templ_text.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._templ_text.customContextMenuRequested.connect(self._show_templ_menu)
        self._templ_text.setPlaceholderText("提示: 请输入命令模板，参数格式为：{1}, {2}, {3}, {4}, {5}")
        self._templ_text.setStyleSheet("""
            QPlainTextEdit {
                border: 1px solid #e5e5e5; border-radius: 8px;
                background: #ffffff; color: #333333;
                font-family: "Courier", monospace; font-size: 13px;
                padding: 8px;
            }
        """)
        self._templ_text.setFixedHeight(120)
        tc_layout.addWidget(self._templ_text)

        layout.addWidget(templ_card)
        layout.addSpacing(15)

        # Params card
        param_card = QFrame()
        set_card_style(param_card)
        pc_layout = QVBoxLayout(param_card)
        pc_layout.setContentsMargins(15, 12, 15, 12)
        pc_layout.setSpacing(6)

        ph = QLabel("参数设置")
        ph.setStyleSheet(H2_STYLE + " color: #1f1f1f;")
        pc_layout.addWidget(ph)

        self._advanced_visible = False
        self._advanced_btn = QPushButton("高级选项")
        self._advanced_btn.setStyleSheet("""
            QPushButton { background: #10a37f; color: white; border: none;
            border-radius: 6px; padding: 4px 12px; font-size: 11px; }
            QPushButton:hover { background: #0d8c6d; }
        """)
        self._advanced_btn.clicked.connect(self._toggle_advanced)

        # Parameter columns grid (5 cols)
        param_grid = QGridLayout()
        param_grid.setSpacing(8)
        for i in range(5):
            param_grid.setColumnStretch(i, 1)
        pc_layout.addLayout(param_grid)

        self._param_base = []
        self._param_step = []
        self._param_repeat_cb = []
        self._param_repeat_val = []
        self._param_count_cb = []
        self._param_count_val = []
        self._param_repeat_widgets = []
        self._param_count_widgets = []

        for col in range(5):
            card = QFrame()
            card.setFrameShape(QFrame.Shape.NoFrame)
            card.setLineWidth(0)
            card.setMidLineWidth(0)
            card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            card.setStyleSheet(
                "QFrame { background-color: #f9f9f9; border: 1px solid #e5e5e5; border-radius: 8px; }"
            )
            clayout = QVBoxLayout(card)
            clayout.setContentsMargins(10, 8, 10, 8)
            clayout.setSpacing(6)

            # Title - centered with border matching input style
            ct = QLabel(f"参数 {col+1}")
            ct.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ct.setStyleSheet("font-size: 12px; font-weight: bold; color: #1f1f1f; background: #ffffff; border: 1px solid #d1d5db; border-radius: 6px; padding: 4px 0px;")
            clayout.addWidget(ct)

            # Base row: "基数: [input]"
            b_row = QWidget()
            brl = QHBoxLayout(b_row)
            brl.setContentsMargins(0, 0, 0, 0)
            brl.setSpacing(4)
            bl = QLabel("基数:")
            bl.setFixedWidth(40)
            bl.setStyleSheet("font-size: 11px; color: #666; background: transparent;")
            brl.addWidget(bl)
            be = QLineEdit("1")
            be.setFixedHeight(28)
            be.setStyleSheet("QLineEdit { background: #ffffff; border: 1px solid #d1d5db; border-radius: 6px; padding: 4px 6px; font-size: 12px; }")
            brl.addWidget(be, stretch=1)
            clayout.addWidget(b_row)
            self._param_base.append(be)

            # Step row: "步长: [input]"
            s_row = QWidget()
            srl = QHBoxLayout(s_row)
            srl.setContentsMargins(0, 0, 0, 0)
            srl.setSpacing(4)
            sl = QLabel("步长:")
            sl.setFixedWidth(40)
            sl.setStyleSheet("font-size: 11px; color: #666; background: transparent;")
            srl.addWidget(sl)
            se = QLineEdit("1")
            se.setFixedHeight(28)
            se.setStyleSheet("QLineEdit { background: #ffffff; border: 1px solid #d1d5db; border-radius: 6px; padding: 4px 6px; font-size: 12px; }")
            srl.addWidget(se, stretch=1)
            clayout.addWidget(s_row)
            self._param_step.append(se)

            # Repeat row (hidden)
            r_row = QWidget()
            rrl = QHBoxLayout(r_row)
            rrl.setContentsMargins(0, 0, 0, 0)
            rrl.setSpacing(4)
            rcb = QCheckBox()
            rcb.setStyleSheet("QCheckBox::indicator { width: 14px; height: 14px; }")
            rcb.toggled.connect(lambda checked, e=re if 're' in dir() else None: None)
            rrl.addWidget(rcb)
            rl = QLabel("重复:")
            rl.setStyleSheet("font-size: 11px; color: #666;")
            rrl.addWidget(rl)
            re = QLineEdit("1")
            re.setFixedHeight(28)
            re.setFixedWidth(50)
            re.setEnabled(False)
            re.setStyleSheet("QLineEdit { background: #f0f0f0; border: 1px solid #d1d5db; border-radius: 6px; padding: 4px 6px; font-size: 11px; }")
            rcb.toggled.connect(lambda checked, e=re: e.setEnabled(checked))
            rrl.addWidget(re)
            rrl.addStretch(1)
            clayout.addWidget(r_row)
            r_row.hide()
            self._param_repeat_cb.append(rcb)
            self._param_repeat_val.append(re)
            self._param_repeat_widgets.append(r_row)

            # Count row (hidden)
            c_row = QWidget()
            crl = QHBoxLayout(c_row)
            crl.setContentsMargins(0, 0, 0, 0)
            crl.setSpacing(4)
            ccb = QCheckBox()
            ccb.setStyleSheet("QCheckBox::indicator { width: 14px; height: 14px; }")
            crl.addWidget(ccb)
            cl2 = QLabel("计数:")
            cl2.setStyleSheet("font-size: 11px; color: #666;")
            crl.addWidget(cl2)
            ce = QLineEdit("1")
            ce.setFixedHeight(28)
            ce.setFixedWidth(50)
            ce.setEnabled(False)
            ce.setStyleSheet("QLineEdit { background: #f0f0f0; border: 1px solid #d1d5db; border-radius: 6px; padding: 4px 6px; font-size: 11px; }")
            ccb.toggled.connect(lambda checked, e=ce: e.setEnabled(checked))
            crl.addWidget(ce)
            crl.addStretch(1)
            clayout.addWidget(c_row)
            c_row.hide()
            self._param_count_cb.append(ccb)
            self._param_count_val.append(ce)
            self._param_count_widgets.append(c_row)

            param_grid.addWidget(card, 0, col)

        # Advanced button placed after grid
        self._btn_row = QWidget()
        set_transparent_bg(self._btn_row)
        brl = QHBoxLayout(self._btn_row)
        brl.setContentsMargins(0, 8, 0, 0)
        brl.addWidget(self._advanced_btn)
        brl.addStretch(1)
        pc_layout.addWidget(self._btn_row)

        layout.addWidget(param_card)
        layout.addSpacing(15)

        # Output card
        out_card = QFrame()
        set_card_style(out_card)
        oc_layout = QVBoxLayout(out_card)
        oc_layout.setContentsMargins(15, 12, 15, 12)
        oc_layout.setSpacing(6)

        oh = QLabel("命令输出")
        oh.setStyleSheet(H2_STYLE + " color: #1f1f1f;")
        oc_layout.addWidget(oh)

        # Command count + buttons
        ctrl_row = QWidget()
        set_transparent_bg(ctrl_row)
        crl = QHBoxLayout(ctrl_row)
        crl.setContentsMargins(0, 0, 0, 0)
        crl.setSpacing(8)

        cl = QLabel("命令数量")
        cl.setStyleSheet(H3_STYLE + " color: #333;")
        crl.addWidget(cl)
        self._cmd_count = QLineEdit("30")
        self._cmd_count.setFixedWidth(60)
        self._cmd_count.setFixedHeight(30)
        crl.addWidget(self._cmd_count)

        self._gen_btn = QPushButton("生成")
        self._gen_btn.setStyleSheet(BTN_PRIMARY)
        self._gen_btn.setFixedSize(70, 28)
        self._gen_btn.clicked.connect(self._generate_commands)
        crl.addWidget(self._gen_btn)

        self._save_btn = QPushButton("保存")
        self._save_btn.setStyleSheet("""
            QPushButton { background: #f5f5f5; color: #333; border: 1px solid #e5e5e5;
            border-radius: 6px; padding: 4px 12px; font-size: 12px; }
            QPushButton:hover { background: #e8e8e8; }
        """)
        self._save_btn.setFixedSize(60, 28)
        self._save_btn.clicked.connect(self._save_output)
        crl.addWidget(self._save_btn)

        self._clear_btn = QPushButton("清空")
        self._clear_btn.setStyleSheet("""
            QPushButton { background: #f5f5f5; color: #333; border: 1px solid #e5e5e5;
            border-radius: 6px; padding: 4px 12px; font-size: 12px; }
            QPushButton:hover { background: #e8e8e8; }
        """)
        self._clear_btn.setFixedSize(60, 28)
        self._clear_btn.clicked.connect(lambda: self._result_text.clear())
        crl.addWidget(self._clear_btn)
        crl.addStretch(1)
        oc_layout.addWidget(ctrl_row)

        # Result text
        self._result_text = QPlainTextEdit()
        self._result_text.setReadOnly(True)
        set_dark_output(self._result_text)
        oc_layout.addWidget(self._result_text, stretch=1)

        # Progress
        self._progress = QProgressBar()
        self._progress.hide()
        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet(HINT_STYLE + " color: #666;")
        self._progress_label.hide()
        oc_layout.addWidget(self._progress)
        oc_layout.addWidget(self._progress_label)

        layout.addWidget(out_card, stretch=1)

    # ── Template management ──

    def _rebuild_combo(self):
        self._templ_combo.blockSignals(True)
        self._templ_combo.clear()
        user_tmpl = _load_user_templates()
        for name in BUILTIN_TEMPLATES:
            icon = "\U0001f516 " if name != "自定义" else "\u270f\ufe0f "
            self._templ_combo.addItem(icon + name)
        if user_tmpl:
            for name in user_tmpl:
                self._templ_combo.addItem("\U0001f4c4 " + name)
        self._templ_combo.blockSignals(False)

    def _get_template_name(self):
        text = self._templ_combo.currentText()
        for prefix in ["\U0001f516 ", "\u270f\ufe0f ", "\U0001f4c4 "]:
            if text.startswith(prefix):
                return text[len(prefix):]
        return text

    def _on_template_select(self, idx):
        if idx < 0:
            return
        name = self._get_template_name()
        user_tmpl = _load_user_templates()
        if name in BUILTIN_TEMPLATES:
            content = BUILTIN_TEMPLATES[name]
        elif name in user_tmpl:
            content = user_tmpl[name]
        else:
            content = ""
        self._templ_text.setPlainText(content)

    def _show_templ_menu(self, pos):
        menu = QMenu(self._templ_text)
        menu.setStyleSheet("""
            QMenu { background: #ffffff; border: 1px solid #e5e5e5; border-radius: 8px; padding: 4px; }
            QMenu::item { padding: 6px 32px 6px 16px; font-size: 13px; color: #333; border-radius: 4px; }
            QMenu::item:selected { background: #e8f5ee; color: #10a37f; }
            QMenu::separator { height: 1px; background: #e5e5e5; margin: 4px 8px; }
        """)
        menu.addAction("撤销", self._templ_text.undo)
        menu.addAction("重做", self._templ_text.redo)
        menu.addSeparator()
        menu.addAction("剪切", self._templ_text.cut)
        menu.addAction("复制", self._templ_text.copy)
        menu.addAction("粘贴", self._templ_text.paste)
        menu.addSeparator()
        menu.addAction("全选", self._templ_text.selectAll)
        menu.exec_(self._templ_text.mapToGlobal(pos))

    def _save_current_template(self):
        name, ok = QInputDialog.getText(self.app, "保存模板", "输入模板名称:")
        if not ok or not name.strip():
            return

        name = name.strip()
        user_tmpl = _load_user_templates()
        if name in BUILTIN_TEMPLATES or name in user_tmpl:
            reply = QMessageBox.question(self.app, "覆盖确认",
                                         f"模板 '{name}' 已存在，是否覆盖?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return

        user_tmpl[name] = self._templ_text.toPlainText()
        try:
            _save_user_templates(user_tmpl)
        except Exception as e:
            QMessageBox.critical(self.app, "错误", f"保存模板失败: {e}")
            return
        self._rebuild_combo()
        # Select the new template
        for i in range(self._templ_combo.count()):
            if self._templ_combo.itemText(i).endswith(name) or self._templ_combo.itemText(i) == "\U0001f4c4 " + name:
                self._templ_combo.setCurrentIndex(i)
                break
        QMessageBox.information(self.app, "成功", f"模板 '{name}' 已保存")
        logger.info(f"[命令生成器] 保存用户模板: {name}")

    def _show_template_menu(self, pos):
        name = self._get_template_name()
        user_tmpl = _load_user_templates()
        if name in BUILTIN_TEMPLATES:
            return  # no right-click for built-in

        menu = QMenu()
        rename_action = menu.addAction("重命名")
        delete_action = menu.addAction("删除")
        action = menu.exec(self._templ_combo.mapToGlobal(pos))

        if action == rename_action:
            new_name, ok = QInputDialog.getText(self.app, "重命名模板", "新名称:", text=name)
            if ok and new_name.strip() and new_name.strip() != name:
                new_name = new_name.strip()
                user_tmpl[new_name] = user_tmpl.pop(name)
                _save_user_templates(user_tmpl)
                self._rebuild_combo()
                logger.info(f"[命令生成器] 重命名模板: {name} -> {new_name}")
        elif action == delete_action:
            reply = QMessageBox.question(self.app, "确认删除",
                                         f"确定要删除模板 '{name}' 吗?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                del user_tmpl[name]
                _save_user_templates(user_tmpl)
                self._rebuild_combo()
                self._templ_combo.setCurrentIndex(0)
                logger.info(f"[命令生成器] 删除模板: {name}")

    def _toggle_advanced(self):
        self._advanced_visible = not self._advanced_visible
        for w in self._param_repeat_widgets + self._param_count_widgets:
            w.setVisible(self._advanced_visible)
        if self._advanced_visible:
            self._advanced_btn.setText("收起高级选项")
        else:
            self._advanced_btn.setText("高级选项")

    # ── Generate ──

    def _generate_commands(self):
        template = self._templ_text.toPlainText().strip()
        if not template:
            QMessageBox.warning(self.app, "提示", "请输入命令模板")
            return

        try:
            count = int(self._cmd_count.text().strip() or "1")
            if count < 1:
                count = 1
        except ValueError:
            count = 1

        params = []
        for i in range(5):
            base_s = self._param_base[i].text().strip()
            step_s = self._param_step[i].text().strip()
            try:
                base = int(base_s) if base_s else 1
            except ValueError:
                base = 1
            try:
                step = int(step_s) if step_s else 1
            except ValueError:
                step = 1

            repeat = int(self._param_repeat_val[i].text() or "1") if self._param_repeat_cb[i].isChecked() else 1
            cnt = int(self._param_count_val[i].text() or "1") if self._param_count_cb[i].isChecked() else count
            params.append({"base": base, "step": step, "repeat": repeat, "count": cnt})

        self._progress.setMaximum(count)
        self._progress.setValue(0)
        self._progress.show()
        self._progress_label.show()

        self._result_text.setReadOnly(False)
        self._result_text.clear()

        lines = []
        for i in range(count):
            values = [""]  # dummy for 0-index offset
            for p in params:
                val = p["base"] + (i % p["count"]) // p["repeat"] * p["step"]
                values.append(str(val))

            try:
                cmd = template.format(*values)
            except (IndexError, KeyError) as e:
                cmd = f"# Error: {e}"

            lines.append(cmd)

            if (i + 1) % 100 == 0 or i == count - 1:
                self._result_text.appendPlainText("\n".join(lines))
                lines.clear()
                self._progress.setValue(i + 1)
                self._progress_label.setText(f"已生成 {i+1}/{count}")
                QApplication.processEvents()

        self._result_text.appendPlainText("")
        self._result_text.setReadOnly(True)
        self._progress.hide()
        self._progress_label.hide()
        logger.info(f"[命令生成器] 生成了 {count} 条命令")

    def _save_output(self):
        text = self._result_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self.app, "提示", "没有可保存的内容")
            return

        path, _ = QFileDialog.getSaveFileName(self.app, "保存命令", "commands.txt",
                                               "Text files (*.txt);;All files (*)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            logger.info(f"[命令生成器] 保存到: {path}")
