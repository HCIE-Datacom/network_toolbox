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

"""Batch Command Generator - generate network commands from template and parameters."""

import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

import customtkinter as ctk

from core.base_module import ToolModule
from core.logger import logger


class CmdGeneratorModule(ToolModule):
    """Generate batch commands from a template with 5 synchronized parameters."""

    name = "命令生成器"
    icon = "⌨️"
    description = "基于模板和参数配置批量生成网络命令，支持5组变量同步递增。"

    _USER_TEMPLATES_FILE = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "templates_user.json"
    )

    BUILTIN_TEMPLATES = {
        "自定义": {
            "template": "",
            "params": [
                {"base": 0, "step": 1, "repeat": 1, "count": 1, "repeat_on": False, "count_on": False},
                {"base": 0, "step": 1, "repeat": 1, "count": 1, "repeat_on": False, "count_on": False},
                {"base": 0, "step": 1, "repeat": 1, "count": 1, "repeat_on": False, "count_on": False},
                {"base": 0, "step": 1, "repeat": 1, "count": 1, "repeat_on": False, "count_on": False},
                {"base": 0, "step": 1, "repeat": 1, "count": 1, "repeat_on": False, "count_on": False},
            ],
        },
        "VLANIF 接口配置": {
            "template": "interface Vlanif{1}\n ip address 10.10.{2}.254 255.255.255.0\n#",
            "params": [
                {"base": 1, "step": 1, "repeat": 1, "count": 1, "repeat_on": False, "count_on": False},
                {"base": 0, "step": 1, "repeat": 1, "count": 1, "repeat_on": False, "count_on": False},
                {"base": 0, "step": 1, "repeat": 1, "count": 1, "repeat_on": False, "count_on": False},
                {"base": 0, "step": 1, "repeat": 1, "count": 1, "repeat_on": False, "count_on": False},
                {"base": 0, "step": 1, "repeat": 1, "count": 1, "repeat_on": False, "count_on": False},
            ],
        },
        "Eth-Trunk 接口配置": {
            "template": (
                "interface Eth-Trunk{1}\n"
                " mode lacp\n"
                " trunkport XG 1/8/0/{2}\n"
                " trunkport XG 2/8/0/{3}\n"
                " port link-type trunk\n"
                " undo port trunk allow-pass vlan 1\n"
                " port trunk allow-pass vlan 3162 \n"
                " quit"
            ),
            "params": [
                {"base": 1, "step": 1, "repeat": 1, "count": 1, "repeat_on": False, "count_on": False},
                {"base": 0, "step": 1, "repeat": 1, "count": 1, "repeat_on": False, "count_on": False},
                {"base": 0, "step": 1, "repeat": 1, "count": 1, "repeat_on": False, "count_on": False},
                {"base": 0, "step": 1, "repeat": 1, "count": 1, "repeat_on": False, "count_on": False},
                {"base": 0, "step": 1, "repeat": 1, "count": 1, "repeat_on": False, "count_on": False},
            ],
        },
    }

    def build(self, parent):
        """Build the UI into the given parent CTkFrame."""

        def label(master, text, font=("Helvetica", -13), fg="#333333", **kw):
            return tk.Label(master, text=text, font=font, fg=fg,
                            bg="#f9f9f9", highlightthickness=0, bd=0, **kw)

        def white_label(master, text, font=("Helvetica", -13), fg="#333333", **kw):
            return tk.Label(master, text=text, font=font, fg=fg,
                            bg="white", highlightthickness=0, bd=0, **kw)

        # ── Title + Description ──
        label(parent, text=self.name,
              font=("Helvetica", -22, "bold"), fg="#1f1f1f").pack(anchor="w", pady=(0, 5))
        label(parent, text=self.description,
              font=("Helvetica", -13), fg="#6b6b6b",
              wraplength=620, justify="left").pack(anchor="w", pady=(0, 15))

        # ── Command Template Card ──
        tmpl_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                 border_width=1, border_color="#e5e5e5")
        tmpl_card.pack(fill="x", pady=(0, 15))
        tmpl_inner = ctk.CTkFrame(tmpl_card, fg_color="transparent")
        tmpl_inner.pack(fill="x", padx=15, pady=15)

        # Template title row with dropdown
        tmpl_header = ctk.CTkFrame(tmpl_inner, fg_color="transparent")
        tmpl_header.pack(fill="x", pady=(0, 6))

        white_label(tmpl_header, text="命令模板",
                    font=("Helvetica", -14, "bold"), fg="#1f1f1f").pack(side="left")

        # Load user templates and merge with built-in
        self._all_templates = dict(self.BUILTIN_TEMPLATES)
        self._user_template_names = self._load_user_templates()
        for name in self._user_template_names:
            pass  # already merged in _load_user_templates

        self._tmpl_var = ctk.StringVar(value="自定义")
        dropdown_values = list(self._all_templates.keys()) + ["➕ 另存为模板..."]
        self._tmpl_menu = ctk.CTkOptionMenu(
            tmpl_header, variable=self._tmpl_var,
            values=dropdown_values,
            font=("Helvetica", 11), width=180, height=28,
            corner_radius=6, fg_color="#10a37f", button_color="#10a37f",
            button_hover_color="#0d8c6d", dropdown_fg_color="white",
            dropdown_text_color="#333333", dropdown_hover_color="#e8f5ee",
            text_color="white", command=self._on_template_select
        )
        self._tmpl_menu.pack(side="right")

        # Right-click context menu for template management
        self._tmpl_menu.bind("<Button-2>", self._show_template_context_menu)
        self._tmpl_menu.bind("<Button-3>", self._show_template_context_menu)

        white_label(tmpl_inner,
                    text="提示: 请输入命令模板，参数格式为：{1}, {2}, {3}, {4}, {5}",
                    font=("Helvetica", -11), fg="#8e8e8e").pack(anchor="w", pady=(0, 8))

        self._template_text = ctk.CTkTextbox(
            tmpl_inner, font=("Courier", 12),
            corner_radius=8, fg_color="#fafafa",
            text_color="#333333", border_width=1, border_color="#d1d5db",
            height=120, wrap="word"
        )
        self._template_text.pack(fill="x")

        # ── Parameters Card ──
        param_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                  border_width=1, border_color="#e5e5e5")
        param_card.pack(fill="x", pady=(0, 15))
        param_inner = ctk.CTkFrame(param_card, fg_color="transparent")
        param_inner.pack(fill="x", padx=15, pady=15)

        param_header = ctk.CTkFrame(param_inner, fg_color="transparent")
        param_header.pack(fill="x", pady=(0, 10))

        white_label(param_header, text="参数设置",
                    font=("Helvetica", -14, "bold"), fg="#1f1f1f").pack(side="left")

        self._advanced_visible = ctk.BooleanVar(value=False)
        self._advanced_btn = ctk.CTkButton(
            param_header, text="▸ 高级选项", width=100, height=26,
            font=("Helvetica", 11), corner_radius=6,
            fg_color="#f0f0f0", text_color="#666666",
            hover_color="#e0e0e0", border_width=1, border_color="#e5e5e5",
            command=self._toggle_advanced
        )
        self._advanced_btn.pack(side="right")

        # Parameter columns container
        param_cols = ctk.CTkFrame(param_inner, fg_color="transparent")
        param_cols.pack(fill="x")
        param_cols.grid_columnconfigure(tuple(range(5)), weight=1)

        self._base_vars = []
        self._step_vars = []
        self._repeat_vars = []
        self._repeat_checks = []
        self._count_vars = []
        self._count_checks = []
        self._advanced_rows = []  # (repeat_row, count_row) per column

        defaults = [
            ("参数1", 1, 1, 1, 10),
            ("参数2", 0, 1, 1, 10),
            ("参数3", 0, 1, 1, 10),
            ("参数4", 0, 1, 1, 10),
            ("参数5", 0, 1, 1, 10),
        ]

        for idx, (name, base, step, repeat, count) in enumerate(defaults):
            col = ctk.CTkFrame(param_cols, fg_color="#f9f9f9", corner_radius=8,
                               border_width=1, border_color="#e5e5e5")
            col.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 6, 0), pady=0)

            # Column title
            ctk.CTkLabel(col, text=name, font=("Helvetica", 12, "bold"),
                         text_color="#1f1f1f").pack(anchor="w", padx=10, pady=(8, 6))

            # Base
            row1 = ctk.CTkFrame(col, fg_color="transparent")
            row1.pack(fill="x", padx=10, pady=(0, 4))
            ctk.CTkLabel(row1, text="基数:", font=("Helvetica", 11),
                         text_color="#666666", width=40).pack(side="left")
            bv = ctk.StringVar(value=str(base))
            self._base_vars.append(bv)
            ctk.CTkEntry(row1, textvariable=bv, font=("Helvetica", 11),
                         width=60, height=28, corner_radius=6,
                         border_color="#d1d5db", border_width=1).pack(side="left", padx=(4, 0))

            # Step
            row2 = ctk.CTkFrame(col, fg_color="transparent")
            row2.pack(fill="x", padx=10, pady=(0, 4))
            ctk.CTkLabel(row2, text="步长:", font=("Helvetica", 11),
                         text_color="#666666", width=40).pack(side="left")
            sv = ctk.StringVar(value=str(step))
            self._step_vars.append(sv)
            ctk.CTkEntry(row2, textvariable=sv, font=("Helvetica", 11),
                         width=60, height=28, corner_radius=6,
                         border_color="#d1d5db", border_width=1).pack(side="left", padx=(4, 0))

            # Repeat checkbox + entry
            row3 = ctk.CTkFrame(col, fg_color="transparent")
            row3.pack(fill="x", padx=10, pady=(0, 4))
            rc = ctk.BooleanVar(value=False)
            self._repeat_checks.append(rc)
            cb_repeat = ctk.CTkCheckBox(row3, text="", variable=rc, width=20,
                                        checkbox_height=16, checkbox_width=16,
                                        border_width=2, corner_radius=4,
                                        fg_color="#10a37f", hover_color="#0d8c6d",
                                        command=self._on_repeat_toggle)
            cb_repeat.pack(side="left")
            ctk.CTkLabel(row3, text="重复:", font=("Helvetica", 11),
                         text_color="#666666").pack(side="left", padx=(2, 0))
            rv = ctk.StringVar(value=str(repeat))
            self._repeat_vars.append(rv)
            ent_repeat = ctk.CTkEntry(row3, textvariable=rv, font=("Helvetica", 11),
                                      width=50, height=28, corner_radius=6,
                                      border_color="#d1d5db", border_width=1,
                                      state="disabled", fg_color="#f0f0f0")
            ent_repeat.pack(side="left", padx=(4, 0))
            self._repeat_entries = getattr(self, '_repeat_entries', [])
            self._repeat_entries.append(ent_repeat)

            # Count checkbox + entry
            row4 = ctk.CTkFrame(col, fg_color="transparent")
            row4.pack(fill="x", padx=10, pady=(0, 8))
            cc = ctk.BooleanVar(value=False)
            self._count_checks.append(cc)
            cb_count = ctk.CTkCheckBox(row4, text="", variable=cc, width=20,
                                       checkbox_height=16, checkbox_width=16,
                                       border_width=2, corner_radius=4,
                                       fg_color="#10a37f", hover_color="#0d8c6d",
                                       command=self._on_count_toggle)
            cb_count.pack(side="left")
            ctk.CTkLabel(row4, text="循环:", font=("Helvetica", 11),
                         text_color="#666666").pack(side="left", padx=(2, 0))
            cv = ctk.StringVar(value=str(count))
            self._count_vars.append(cv)
            ent_count = ctk.CTkEntry(row4, textvariable=cv, font=("Helvetica", 11),
                                     width=50, height=28, corner_radius=6,
                                     border_color="#d1d5db", border_width=1,
                                     state="disabled", fg_color="#f0f0f0")
            ent_count.pack(side="left", padx=(4, 0))
            self._count_entries = getattr(self, '_count_entries', [])
            self._count_entries.append(ent_count)

            # Track rows for collapse
            self._advanced_rows.append((row3, row4))

        # Hide advanced rows by default
        for r3, r4 in self._advanced_rows:
            r3.pack_forget()
            r4.pack_forget()

        # ── Output Card ──
        out_card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white",
                                border_width=1, border_color="#e5e5e5")
        out_card.pack(fill="both", expand=True)
        out_inner = ctk.CTkFrame(out_card, fg_color="transparent")
        out_inner.pack(fill="both", expand=True, padx=15, pady=15)

        # Output header row
        out_header = ctk.CTkFrame(out_inner, fg_color="transparent")
        out_header.pack(fill="x", pady=(0, 10))

        white_label(out_header, text="命令生成",
                    font=("Helvetica", -14, "bold"), fg="#1f1f1f").pack(side="left")

        # Command count display
        count_frame = ctk.CTkFrame(out_header, fg_color="transparent")
        count_frame.pack(side="left", padx=(15, 0))
        white_label(count_frame, text="命令数量:",
                    font=("Helvetica", -12), fg="#666666").pack(side="left")
        self._cmd_count_var = ctk.StringVar(value="0")
        ctk.CTkEntry(count_frame, textvariable=self._cmd_count_var,
                     font=("Helvetica", 11), width=60, height=28,
                     corner_radius=6, border_color="#d1d5db", border_width=1).pack(side="left", padx=(6, 0))

        # Buttons
        btn_frame = ctk.CTkFrame(out_header, fg_color="transparent")
        btn_frame.pack(side="right")

        ctk.CTkButton(btn_frame, text="生成命令", command=self._generate_commands,
                      width=90, height=32, font=("Helvetica", 12, "bold"),
                      corner_radius=8, fg_color="#10a37f", hover_color="#0d8c6d").pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_frame, text="保存结果", command=self._save_results,
                      width=90, height=32, font=("Helvetica", 12),
                      corner_radius=8, fg_color="#f5f5f5", text_color="#333333",
                      hover_color="#e0e0e0", border_width=1, border_color="#e5e5e5").pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_frame, text="清空", command=self._clear_all,
                      width=70, height=32, font=("Helvetica", 12),
                      corner_radius=8, fg_color="#f5f5f5", text_color="#333333",
                      hover_color="#e0e0e0", border_width=1, border_color="#e5e5e5").pack(side="left")

        # Result text area
        self._result_text = ctk.CTkTextbox(
            out_inner, font=("Courier", 12),
            corner_radius=8, fg_color="#1e1e1e",
            text_color="#e0e0e0", border_width=1, border_color="#e5e5e5",
            wrap="none"
        )
        self._result_text.pack(fill="both", expand=True)

        # Progress bar at bottom
        progress_frame = ctk.CTkFrame(out_inner, fg_color="transparent")
        progress_frame.pack(fill="x", pady=(8, 0))

        self._progress_bar = ctk.CTkProgressBar(
            progress_frame, width=200, height=6,
            corner_radius=3, fg_color="#e5e5e5",
            progress_color="#10a37f"
        )
        self._progress_bar.pack(side="left")
        self._progress_bar.set(0)

        self._progress_label = white_label(progress_frame, text="进度: 0%",
                                           font=("Helvetica", -11), fg="#666666")
        self._progress_label.pack(side="left", padx=(8, 0))

    # ── Checkbox toggles ──

    def _on_repeat_toggle(self):
        for i, cb in enumerate(self._repeat_checks):
            if cb.get():
                self._repeat_entries[i].configure(state="normal", fg_color="white")
            else:
                self._repeat_entries[i].configure(state="disabled", fg_color="#f0f0f0")

    def _on_count_toggle(self):
        for i, cb in enumerate(self._count_checks):
            if cb.get():
                self._count_entries[i].configure(state="normal", fg_color="white")
            else:
                self._count_entries[i].configure(state="disabled", fg_color="#f0f0f0")

    def _toggle_advanced(self):
        """Show or hide repeat and count rows in all parameter columns."""
        show = not self._advanced_visible.get()
        self._advanced_visible.set(show)

        if show:
            self._advanced_btn.configure(text="▾ 高级选项", fg_color="#10a37f",
                                         text_color="white", hover_color="#0d8c6d")
            for r3, r4 in self._advanced_rows:
                r3.pack(fill="x", padx=10, pady=(0, 4))
                r4.pack(fill="x", padx=10, pady=(0, 8))
        else:
            self._advanced_btn.configure(text="▸ 高级选项", fg_color="#f0f0f0",
                                         text_color="#666666", hover_color="#e0e0e0")
            for r3, r4 in self._advanced_rows:
                r3.pack_forget()
                r4.pack_forget()

    def _on_template_select(self, choice):
        """Load a template or trigger save-as."""
        if choice == "➕ 另存为模板...":
            self._save_current_template()
            self._tmpl_var.set("自定义")
            return

        tmpl = self._all_templates.get(choice)
        if not tmpl:
            return

        # Fill template text
        self._template_text.delete("1.0", "end")
        if tmpl["template"]:
            self._template_text.insert("1.0", tmpl["template"])

        # Set parameter defaults
        for i, p in enumerate(tmpl["params"]):
            self._base_vars[i].set(str(p["base"]))
            self._step_vars[i].set(str(p["step"]))
            self._repeat_vars[i].set(str(p["repeat"]))
            self._count_vars[i].set(str(p["count"]))
            self._repeat_checks[i].set(p["repeat_on"])
            self._count_checks[i].set(p["count_on"])

        self._on_repeat_toggle()
        self._on_count_toggle()

        logger.info(f"[批量命令] 加载模板: {choice}")

    def _load_user_templates(self):
        """Load user-saved templates from JSON file."""
        try:
            os.makedirs(os.path.dirname(self._USER_TEMPLATES_FILE), exist_ok=True)
            if os.path.exists(self._USER_TEMPLATES_FILE):
                with open(self._USER_TEMPLATES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for name, tmpl in data.items():
                    if name not in self._all_templates:
                        self._all_templates[name] = tmpl
                return list(data.keys())
        except Exception as e:
            logger.error(f"[批量命令] 加载用户模板失败: {e}")
        return []

    def _save_user_templates(self):
        """Persist user templates to JSON file."""
        user_data = {}
        for name in self._user_template_names:
            if name in self._all_templates:
                user_data[name] = self._all_templates[name]
        try:
            os.makedirs(os.path.dirname(self._USER_TEMPLATES_FILE), exist_ok=True)
            with open(self._USER_TEMPLATES_FILE, "w", encoding="utf-8") as f:
                json.dump(user_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[批量命令] 保存用户模板失败: {e}")

    def _save_current_template(self):
        """Save the current template and parameters as a named template."""
        name = simpledialog.askstring("保存模板", "请输入模板名称:", parent=self._tmpl_menu.winfo_toplevel())
        if not name:
            return
        name = name.strip()
        if not name:
            return
        if name in ("自定义", "➕ 另存为模板..."):
            messagebox.showwarning("提示", "该名称已被系统使用，请换一个名称")
            return
        if name in self._all_templates:
            ok = messagebox.askyesno("覆盖确认", f"模板「{name}」已存在，是否覆盖？")
            if not ok:
                return

        # Collect current parameter state
        params = []
        for i in range(5):
            params.append({
                "base": int(self._base_vars[i].get() or 0),
                "step": int(self._step_vars[i].get() or 1),
                "repeat": int(self._repeat_vars[i].get() or 1),
                "count": int(self._count_vars[i].get() or 10),
                "repeat_on": bool(self._repeat_checks[i].get()),
                "count_on": bool(self._count_checks[i].get()),
            })

        template_text = self._template_text.get("1.0", "end").strip()
        self._all_templates[name] = {"template": template_text, "params": params}
        if name not in self._user_template_names:
            self._user_template_names.append(name)

        # Persist
        self._save_user_templates()

        # Refresh dropdown
        self._rebuild_dropdown()
        self._tmpl_var.set(name)

        logger.info(f"[批量命令] 已保存用户模板: {name}")
        messagebox.showinfo("保存成功", f"模板「{name}」已保存")

    def _rebuild_dropdown(self):
        """Refresh the dropdown options to include newly added templates."""
        values = list(self._all_templates.keys()) + ["➕ 另存为模板..."]
        self._tmpl_menu.configure(values=values)

    def _show_template_context_menu(self, event):
        """Show right-click context menu for template management."""
        current = self._tmpl_var.get()
        builtin_names = {"自定义", "➕ 另存为模板...", "VLANIF 接口配置", "Eth-Trunk 接口配置"}

        menu = tk.Menu(self._tmpl_menu, tearoff=0, font=("Helvetica", 12))

        if current in builtin_names:
            menu.add_command(label="无法操作内置模板", state="disabled")
        else:
            menu.add_command(label="✏️ 重命名", command=lambda: self._rename_template(current))
            menu.add_command(label="🗑 删除", command=lambda: self._delete_template(current))

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _rename_template(self, old_name):
        """Rename a user template."""
        new_name = simpledialog.askstring(
            "重命名模板", "请输入新名称:",
            initialvalue=old_name, parent=self._tmpl_menu.winfo_toplevel()
        )
        if not new_name or new_name.strip() == old_name:
            return
        new_name = new_name.strip()
        builtin_names = {"自定义", "➕ 另存为模板...", "VLANIF 接口配置", "Eth-Trunk 接口配置"}
        if new_name in builtin_names or new_name in self._all_templates:
            messagebox.showwarning("提示", "该名称已存在，请换一个名称")
            return

        self._all_templates[new_name] = self._all_templates.pop(old_name)
        idx = self._user_template_names.index(old_name)
        self._user_template_names[idx] = new_name
        self._save_user_templates()
        self._rebuild_dropdown()
        self._tmpl_var.set(new_name)
        logger.info(f"[批量命令] 模板已重命名: {old_name} -> {new_name}")

    def _delete_template(self, name):
        """Delete a user template after confirmation."""
        ok = messagebox.askyesno("删除确认", f"确定删除模板「{name}」？")
        if not ok:
            return

        del self._all_templates[name]
        self._user_template_names.remove(name)
        self._save_user_templates()
        self._rebuild_dropdown()
        self._tmpl_var.set("自定义")
        logger.info(f"[批量命令] 已删除模板: {name}")

    # ── Core Logic ──

    def _generate_commands(self):
        """Generate commands from template and parameters."""
        template = self._template_text.get("1.0", "end").strip()
        if not template:
            messagebox.showwarning("提示", "请输入命令模板")
            return

        # Parse parameters
        params = []
        for i in range(5):
            try:
                base = int(self._base_vars[i].get() or 0)
            except ValueError:
                base = 0
            try:
                step = int(self._step_vars[i].get() or 1)
            except ValueError:
                step = 1

            if self._repeat_checks[i].get():
                try:
                    repeat = int(self._repeat_vars[i].get() or 1)
                except ValueError:
                    repeat = 1
            else:
                repeat = 1

            if self._count_checks[i].get():
                try:
                    count = int(self._count_vars[i].get() or 10)
                except ValueError:
                    count = 10
            else:
                count = 1

            params.append({"base": base, "step": step, "repeat": repeat, "count": count})

        # Determine total iterations from command count field
        try:
            max_count = int(self._cmd_count_var.get())
        except ValueError:
            max_count = 0

        # If command count is empty/0, fall back to max param loop count
        if max_count <= 0:
            param_max = max(p["count"] for p in params)
            if param_max <= 1:
                messagebox.showwarning("提示", "请设置命令数量或勾选参数的循环个数")
                return
            max_count = param_max

        self._result_text.delete("1.0", "end")
        self._cmd_count_var.set(str(max_count))

        generated = 0
        for i in range(max_count):
            values = [""]  # dummy for 0-index, so {1}=param1, {2}=param2...
            for p in params:
                val = p["base"] + i * p["step"]
                values.append(str(val))

            for _ in range(params[0]["repeat"]):
                for raw_line in template.split("\n"):
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        cmd = raw_line.format(*values)
                        self._result_text.insert("end", cmd + "\n")
                        generated += 1
                    except (IndexError, KeyError, ValueError) as e:
                        self._result_text.insert("end", f"[格式错误] {raw_line}  (错误: {e})\n")

            # Update progress
            progress = (i + 1) / max_count
            self._progress_bar.set(progress)
            self._progress_label.configure(text=f"进度: {int(progress * 100)}%")
            self.app.update_idletasks()

        logger.info(f"[批量命令] 生成完成，共 {generated} 条命令")
        self._progress_bar.set(1.0)
        self._progress_label.configure(text="进度: 100%")

    def _save_results(self):
        """Save generated commands to a text file."""
        content = self._result_text.get("1.0", "end").strip()
        if not content:
            messagebox.showwarning("提示", "没有可保存的内容，请先生成命令")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            title="保存命令列表"
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"[批量命令] 命令列表已保存到: {file_path}")
            messagebox.showinfo("保存成功", f"命令列表已保存到:\n{file_path}")
        except Exception as e:
            logger.error(f"[批量命令] 保存失败: {e}")
            messagebox.showerror("保存失败", f"保存文件时出错:\n{e}")

    def _clear_all(self):
        """Clear template, results, and reset progress."""
        self._template_text.delete("1.0", "end")
        self._result_text.delete("1.0", "end")
        self._cmd_count_var.set("0")
        self._progress_bar.set(0)
        self._progress_label.configure(text="进度: 0%")

        # Reset parameters to defaults
        defaults = [(1, 1, 1, 10), (0, 1, 1, 10), (0, 1, 1, 10), (0, 1, 1, 10), (0, 1, 1, 10)]
        for i, (base, step, repeat, count) in enumerate(defaults):
            self._base_vars[i].set(str(base))
            self._step_vars[i].set(str(step))
            self._repeat_vars[i].set(str(repeat))
            self._count_vars[i].set(str(count))
            self._repeat_checks[i].set(False)
            self._count_checks[i].set(True)

        self._on_repeat_toggle()
        self._on_count_toggle()
        logger.info("[批量命令] 已清空所有内容")
