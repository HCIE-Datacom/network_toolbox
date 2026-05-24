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

"""NetworkToolboxApp - main window framework (sidebar + content area)."""

import customtkinter as ctk
import tkinter as tk
from core.logger import logger


# ── Global patch: add right-click context menu to CTkEntry ──

_original_entry_init = ctk.CTkEntry.__init__


def _patched_entry_init(self, *args, **kwargs):
    _original_entry_init(self, *args, **kwargs)
    _bind_entry_context_menu(self)


def _bind_entry_context_menu(entry):
    """Bind right-click context menu (Copy/Paste/Cut/Select All) to a CTkEntry."""
    menu = tk.Menu(entry, tearoff=0)

    def _popup(event):
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy():
        try:
            entry.clipboard_clear()
            sel = entry.selection_get()
            entry.clipboard_append(sel)
        except tk.TclError:
            pass

    def _cut():
        _copy()
        try:
            entry.delete("sel.first", "sel.last")
        except tk.TclError:
            pass

    def _paste():
        try:
            entry.insert("insert", entry.clipboard_get())
        except tk.TclError:
            pass

    def _select_all():
        entry.select_range(0, "end")
        entry.icursor("end")

    def _post(x, y):
        has_sel = False
        try:
            entry.selection_get()
            has_sel = True
        except tk.TclError:
            pass
        menu.delete(0, "end")
        menu.add_command(label="剪切", command=_cut, state="normal" if has_sel else "disabled")
        menu.add_command(label="复制", command=_copy, state="normal" if has_sel else "disabled")
        menu.add_command(label="粘贴", command=_paste)
        menu.add_separator()
        menu.add_command(label="全选", command=_select_all)
        menu.tk_popup(x, y)

    entry.bind("<Button-2>", lambda e: _post(e.x_root, e.y_root))
    entry.bind("<Button-3>", lambda e: _post(e.x_root, e.y_root))
    entry.bind("<Command-a>", lambda e: _select_all())
    entry.bind("<Control-a>", lambda e: _select_all())


ctk.CTkEntry.__init__ = _patched_entry_init


# ── Global patch: add right-click context menu to CTkTextbox ──

_original_textbox_init = ctk.CTkTextbox.__init__


def _patched_textbox_init(self, *args, **kwargs):
    _original_textbox_init(self, *args, **kwargs)
    _bind_textbox_context_menu(self)


def _bind_textbox_context_menu(textbox):
    """Bind right-click context menu (Copy/Paste/Select All) to a CTkTextbox."""
    menu = tk.Menu(textbox, tearoff=0)

    def _copy():
        try:
            textbox.clipboard_clear()
            sel = textbox.get("sel.first", "sel.last")
            textbox.clipboard_append(sel)
        except tk.TclError:
            pass

    def _cut():
        _copy()
        try:
            textbox.delete("sel.first", "sel.last")
        except tk.TclError:
            pass

    def _paste():
        try:
            textbox.insert("insert", textbox.clipboard_get())
        except tk.TclError:
            pass

    def _select_all():
        textbox.tag_add("sel", "1.0", "end")
        textbox.mark_set("insert", "end")

    def _post(x, y):
        has_sel = False
        try:
            textbox.get("sel.first", "sel.last")
            has_sel = True
        except tk.TclError:
            pass
        state = textbox.cget("state")
        editable = (state == "normal")
        menu.delete(0, "end")
        menu.add_command(label="剪切", command=_cut,
                         state="normal" if (has_sel and editable) else "disabled")
        menu.add_command(label="复制", command=_copy,
                         state="normal" if has_sel else "disabled")
        menu.add_command(label="粘贴", command=_paste,
                         state="normal" if editable else "disabled")
        menu.add_separator()
        menu.add_command(label="全选", command=_select_all)
        menu.tk_popup(x, y)

    textbox.bind("<Button-2>", lambda e: _post(e.x_root, e.y_root))
    textbox.bind("<Button-3>", lambda e: _post(e.x_root, e.y_root))
    textbox.bind("<Command-a>", lambda e: _select_all())
    textbox.bind("<Control-a>", lambda e: _select_all())


ctk.CTkTextbox.__init__ = _patched_textbox_init


class NetworkToolboxApp(ctk.CTk):
    """Plugin-style main window. Reads MODULE_REGISTRY and auto-generates UI."""

    VERSION = "v1.4.0"

    def __init__(self, module_registry):
        super().__init__()
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        self.title("NetTool")
        self.geometry("1050x880")
        self.minsize(900, 700)
        self.configure(fg_color="#f9f9f9")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._build_sidebar(module_registry)
        self._build_content_area(module_registry)

        # Keyboard shortcut: Cmd+L (macOS) or Ctrl+L to open log viewer
        self.bind("<Command-l>", lambda e: self._open_log_viewer())
        self.bind("<Control-l>", lambda e: self._open_log_viewer())

        # Show first enabled module
        for i, mod in enumerate(self._modules):
            if not mod.disabled:
                self._switch_to(i)
                break

    # ==================== Sidebar ====================

    def _build_sidebar(self, module_registry):
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="transparent")
        self.sidebar.grid(row=0, column=0, sticky="ns", padx=(12, 0), pady=12)
        self.sidebar.grid_propagate(False)

        sidebar_card = ctk.CTkFrame(self.sidebar, corner_radius=12,
                                    fg_color="white", border_width=1, border_color="#e5e5e5")
        sidebar_card.pack(fill="y", expand=True)

        sidebar_inner = ctk.CTkFrame(sidebar_card, corner_radius=0, fg_color="transparent")
        sidebar_inner.pack(fill="both", expand=True, padx=15, pady=18)

        # Title
        ctk.CTkLabel(sidebar_inner, text="NetTool",
                      font=("Helvetica", 18, "bold"), text_color="#1f1f1f").pack(anchor="w", pady=(0, 15))

        # Separator
        ctk.CTkFrame(sidebar_inner, height=1, fg_color="#e5e5e5").pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(sidebar_inner, text="功能列表",
                      font=("Helvetica", 11), text_color="#8e8e8e").pack(anchor="w", pady=(0, 8))

        # Navigation buttons (auto-generated from registry)
        self._nav_frame = ctk.CTkFrame(sidebar_inner, fg_color="transparent")
        self._nav_frame.pack(fill="x")

        self._nav_buttons = []
        for idx, mod_cls in enumerate(module_registry):
            mod = mod_cls(self)
            btn = self._make_nav_btn(mod.icon, mod.name, idx, mod.disabled, mod.disabled_text)
            self._nav_buttons.append(btn)
            btn._module = mod

        # Log button (small, at bottom of nav)
        log_btn = ctk.CTkButton(self._nav_frame, text="  📋   运行日志",
                                 font=("Helvetica", 12), corner_radius=6, height=32,
                                 fg_color="transparent", hover_color="#e8f5ee",
                                 text_color="#666666", anchor="w",
                                 command=self._open_log_viewer)
        log_btn.pack(fill="x", pady=(8, 0))

        # Copyright + version at bottom (pack order is reversed for side="bottom")
        ctk.CTkLabel(sidebar_inner, text=f"© 2026 Tang Wenbo. All rights reserved.",
                      font=("Helvetica", 9), text_color="#b0b0b0").pack(side="bottom", anchor="w", pady=(2, 0))
        ctk.CTkLabel(sidebar_inner, text=f"NetTool {self.VERSION}",
                      font=("Helvetica", 11), text_color="#8e8e8e").pack(side="bottom", anchor="w", pady=(0, 0))
        ctk.CTkFrame(sidebar_inner, height=1, fg_color="#e5e5e5").pack(side="bottom", fill="x", pady=(10, 0))

    def _make_nav_btn(self, icon, label, idx, disabled=False, disabled_text=""):
        label_text = label if not disabled_text else f"{label} ({disabled_text})"
        btn = ctk.CTkButton(self._nav_frame, text=f"  {icon}   {label_text}",
                               font=("Helvetica", 13), corner_radius=8, height=40,
                               fg_color="transparent", hover_color="#e8f5ee",
                               text_color="#333333", anchor="w")
        btn.pack(fill="x", pady=(0, 4))
        if disabled:
            btn.configure(state="disabled", text_color="#c0c0c0")
        else:
            btn.configure(command=lambda idx=idx: self._switch_to(idx))
        return btn

    # ==================== Content Area ====================

    def _build_content_area(self, module_registry):
        self._modules = []
        self._frames = []

        main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main_frame.grid(row=0, column=1, sticky="nsew")
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)

        self._cw = ctk.CTkFrame(main_frame, corner_radius=0, fg_color="transparent")
        self._cw.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self._cw.grid_rowconfigure(0, weight=1)
        self._cw.grid_columnconfigure(0, weight=1)

        # Instantiate modules and build their frames
        for btn in self._nav_buttons:
            mod = btn._module
            frame = ctk.CTkFrame(self._cw, corner_radius=0, fg_color="transparent")
            try:
                mod.build(frame)
            except Exception as e:
                logger.exception(f"模块 {mod.name} 构建 UI 失败")
                ctk.CTkLabel(frame, text=f"模块加载失败: {e}",
                             font=("Helvetica", 14), text_color="#e74c3c").pack(pady=40)
            frame.grid(row=0, column=0, sticky="nsew")
            frame.grid_remove()  # hidden by default
            self._modules.append(mod)
            self._frames.append(frame)

    def _switch_to(self, index):
        # Hide current
        if hasattr(self, "_active_index"):
            old_mod = self._modules[self._active_index]
            try:
                old_mod.on_hide()
            except Exception:
                logger.exception(f"模块 {old_mod.name} on_hide 异常")
            self._frames[self._active_index].grid_remove()

        # Show target
        new_mod = self._modules[index]
        self._frames[index].grid()
        try:
            new_mod.on_show()
        except Exception:
            logger.exception(f"模块 {new_mod.name} on_show 异常")
        self._active_index = index

        # Update sidebar button colors
        for i, btn in enumerate(self._nav_buttons):
            if i == index:
                btn.configure(fg_color="#10a37f", text_color="white")
            elif not btn._module.disabled:
                btn.configure(fg_color="transparent", text_color="#333333")

    # ==================== Log Viewer ====================

    def _open_log_viewer(self):
        """Open a floating window showing recent log lines."""
        if hasattr(self, "_log_window") and self._log_window.winfo_exists():
            self._log_window.lift()
            self._refresh_log_viewer()
            return

        self._log_window = ctk.CTkToplevel(self)
        self._log_window.title("运行日志")
        self._log_window.geometry("700x450")
        self._log_window.minsize(500, 300)
        self._log_window.configure(fg_color="#f9f9f9")

        # Header
        header = ctk.CTkFrame(self._log_window, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(12, 8))

        ctk.CTkLabel(header, text="运行日志",
                     font=("Helvetica", 16, "bold"), text_color="#1f1f1f").pack(side="left")

        ctk.CTkButton(header, text="刷新", width=60, height=28,
                      font=("Helvetica", 11), corner_radius=6,
                      fg_color="#10a37f", hover_color="#0d8c6d",
                      command=self._refresh_log_viewer).pack(side="right", padx=(8, 0))

        ctk.CTkButton(header, text="清空", width=60, height=28,
                      font=("Helvetica", 11), corner_radius=6,
                      fg_color="#f5f5f5", text_color="#333333",
                      hover_color="#e0e0e0", border_width=1, border_color="#e5e5e5",
                      command=self._clear_log_viewer).pack(side="right")

        # Log path hint
        ctk.CTkLabel(self._log_window,
                     text=f"日志文件: {logger.log_path}",
                     font=("Helvetica", 10), text_color="#999999").pack(anchor="w", padx=15)

        # Text area
        self._log_text = ctk.CTkTextbox(self._log_window, font=("Courier", 11),
                                        corner_radius=8, fg_color="#1e1e1e",
                                        text_color="#d4d4d4",
                                        border_width=1, border_color="#e5e5e5")
        self._log_text.pack(fill="both", expand=True, padx=15, pady=(8, 12))

        self._refresh_log_viewer()

    def _refresh_log_viewer(self):
        if not hasattr(self, "_log_text") or not self._log_text.winfo_exists():
            return
        lines = logger.get_recent_lines(n=300)
        self._log_text.delete("0.0", "end")
        self._log_text.insert("0.0", "\n".join(lines))
        self._log_text.see("end")

    def _clear_log_viewer(self):
        if not hasattr(self, "_log_text") or not self._log_text.winfo_exists():
            return
        logger.clear_memory()
        self._log_text.delete("0.0", "end")
