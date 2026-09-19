# -*- coding: utf-8 -*-
"""封装 添加/编辑 对话框"""
import tkinter as tk
from tkinter import ttk, messagebox

from utils.constants import THEMES


class FootprintEditDialog(tk.Toplevel):
    """footprint=None 表示添加，否则编辑"""

    def __init__(self, parent, footprint: dict = None):
        super().__init__(parent)
        self.parent = parent
        self.footprint = footprint
        self.result = False

        self.title("编辑封装" if footprint else "添加封装")
        self.geometry("560x500")
        self.resizable(False, False)

        theme = THEMES[parent.current_theme]
        self.configure(bg=theme["bg_main"])
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TLabel', background=theme["bg_main"], foreground=theme["fg_text"])
        style.configure('TFrame', background=theme["bg_main"])
        style.configure('TButton', background=theme["bg_button"], foreground=theme["fg_text"],
                        bordercolor=theme["border"])
        style.map('TButton',
                  background=[('active', theme["bg_button_hover"]), ('pressed', theme["bg_main"])],
                  foreground=[('active', theme["fg_white"])])
        style.configure('TEntry',
                        fieldbackground=theme["bg_input"],
                        foreground=theme["fg_text"],
                        insertcolor=theme["fg_text"])

        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True, padx=15, pady=12)

        fp = footprint or {}

        tags_val = fp.get("tags", "")
        if isinstance(tags_val, list):
            tags_val = ",".join(tags_val)

        lcsc_val = fp.get("lcsc_ids", "")
        if isinstance(lcsc_val, list):
            lcsc_val = ",".join(lcsc_val)

        self.vars = {
            "name": tk.StringVar(value=fp.get("name", "")),
            "display": tk.StringVar(value=fp.get("display", "")),
            "category": tk.StringVar(value=fp.get("category", "")),
            "pins": tk.StringVar(value=str(fp.get("pins", 0) or "")),
            "tags": tk.StringVar(value=tags_val or ""),
            "lcsc_ids": tk.StringVar(value=lcsc_val or ""),
            "note": tk.StringVar(value=fp.get("note", "")),
        }

        rows = [
            ("封装名 *", "name", "例如 USB-C-SMD_16P"),
            ("中文简介", "display", "例如 Type-C 母座 16P 贴片"),
            ("分类", "category", "例如 USB / 连接器 / 阻容"),
            ("引脚数", "pins", "0 表示不固定"),
            ("搜索关键词", "tags", "逗号分隔，例如 typec,type-c,c口,16p"),
            ("关联 C 编号", "lcsc_ids", "逗号分隔，例如 C384887,C7519"),
            ("备注", "note", "任意说明"),
        ]

        for i, (label, key, hint) in enumerate(rows):
            ttk.Label(body, text=label).grid(row=i, column=0, sticky=tk.W, pady=6)
            e = ttk.Entry(body, textvariable=self.vars[key], width=48)
            e.grid(row=i, column=1, sticky=tk.EW, padx=(8, 0), pady=6)
            if key == "name":
                e.focus_set()
            ttk.Label(body, text=hint, foreground=theme.get("fg_hint", "#888")) \
                .grid(row=i + 1, column=1, sticky=tk.W, padx=(8, 0))

        body.columnconfigure(1, weight=1)

        btns = ttk.Frame(self)
        btns.pack(fill=tk.X, padx=15, pady=(0, 15))
        ttk.Button(btns, text="保存", command=self.save).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=4)

        self.transient(parent)
        self.grab_set()

    def save(self):
        from services import footprint_service
        data = {
            "name": self.vars["name"].get().strip(),
            "display": self.vars["display"].get().strip(),
            "category": self.vars["category"].get().strip(),
            "pins": self.vars["pins"].get().strip() or 0,
            "tags": self.vars["tags"].get().strip(),
            "lcsc_ids": self.vars["lcsc_ids"].get().strip(),
            "note": self.vars["note"].get().strip(),
        }
        if not data["name"]:
            messagebox.showerror("错误", "封装名不能为空")
            return
        try:
            data["pins"] = int(data["pins"])
        except ValueError:
            messagebox.showerror("错误", "引脚数必须是整数")
            return

        try:
            if self.footprint:
                footprint_service.update(self.footprint["id"], **data)
            else:
                footprint_service.add(data)
            self.result = True
            self.destroy()
        except Exception as e:
            messagebox.showerror("保存失败", str(e))