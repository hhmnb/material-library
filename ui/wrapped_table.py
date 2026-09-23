# -*- coding: utf-8 -*-
"""
支持自动换行、行高自适应的轻量级表格控件。
用于替代 ttk.Treeview 无法做到的：
  - 单元格内多行自动换行
  - 行高按该行最高单元格自适应
  - 列宽按内容适配
  - 网格线 / 交替行底色

用法：
    columns = [
        {"key": "purpose", "text": "用途", "width": 110},
        {"key": "model",   "text": "型号", "width": 130},
        ...
    ]
    tbl = WrappedTable(parent, columns, theme_dict,
                       show_grid=True,
                       on_double_click=..., on_right_click=...)
    tbl.pack(fill="both", expand=True)
    tbl.set_data(list_of_dicts)
"""
import tkinter as tk
from tkinter import ttk


class WrappedTable(tk.Frame):

    def __init__(self, parent, columns, theme, *,
                 on_select=None, on_double_click=None, on_right_click=None,
                 show_grid=False, zebra=False):
        super().__init__(parent, bg=theme["bg_table"])
        self.columns = columns
        self.theme = theme
        self.on_select = on_select
        self.on_double_click = on_double_click
        self.on_right_click = on_right_click
        self.show_grid = show_grid
        self.zebra = zebra

        self.data = []
        self.cell_labels = []        # cell_labels[row][col]
        self.selected_row = -1

        # 表头
        self.header_frame = tk.Frame(self, bg=theme["bg_heading"], height=28)
        self.header_frame.pack(fill=tk.X)
        self.header_frame.pack_propagate(False)
        self._build_header()

        # 主体
        body = tk.Frame(self, bg=theme["bg_table"])
        body.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(body, bg=theme["bg_table"],
                                highlightthickness=0, bd=0)
        self.vbar = ttk.Scrollbar(body, orient=tk.VERTICAL,
                                  command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.inner = tk.Frame(self.canvas, bg=theme["bg_table"])
        self._win_id = self.canvas.create_window((0, 0), window=self.inner,
                                                 anchor="nw")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # 鼠标滚轮
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.inner.bind("<MouseWheel>", self._on_wheel)

    # ---------- 布局 ----------
    def _on_inner_configure(self, _):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._win_id, width=event.width)

    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _build_header(self):
        for w in self.header_frame.winfo_children():
            w.destroy()
        border = self.theme.get("border", "#3a3a3a")
        x = 0
        for col in self.columns:
            lbl = tk.Label(self.header_frame, text=col["text"],
                           bg=self.theme["bg_heading"],
                           fg=self.theme["fg_text"],
                           font=("TkDefaultFont", 10, "bold"),
                           anchor="w", padx=6, pady=4,
                           highlightthickness=1 if self.show_grid else 0,
                           highlightbackground=border if self.show_grid else self.theme["bg_heading"],
                           highlightcolor=border if self.show_grid else self.theme["bg_heading"],
                           bd=0)
            lbl.place(x=x, y=0, width=col["width"], height=28)
            x += col["width"]

    # ---------- 数据 ----------
    def clear(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.data = []
        self.cell_labels = []
        self.selected_row = -1

    @staticmethod
    def _get_value(item, key):
        if isinstance(item, dict):
            return item.get(key, "")
        return getattr(item, key, "")

    def _row_bg(self, r):
        """交替行底色（zebra 关闭时统一用 bg_table）"""
        if not self.zebra:
            return self.theme["bg_table"]
        alt = self.theme.get("bg_table_alt")
        if not alt:
            return self.theme["bg_table"]
        return self.theme["bg_table"] if r % 2 == 0 else alt

    def set_data(self, items):
        self.clear()
        self.data = list(items)

        # 配置每一列的 min 宽度
        for i, col in enumerate(self.columns):
            self.inner.grid_columnconfigure(i, weight=0, minsize=col["width"])

        border = self.theme.get("border", "#3a3a3a")

        # 每一行每一格用 Label，wraplength 让超长文本在列内自动换行
        # 全部放在 self.inner 的同一 grid 中 → 同一行自动等高
        for r, item in enumerate(self.data):
            row_labels = []
            row_bg = self._row_bg(r)
            for c, col in enumerate(self.columns):
                text = self._get_value(item, col["key"])
                if text is None:
                    text = ""
                lbl = tk.Label(
                    self.inner,
                    text=str(text),
                    bg=row_bg,
                    fg=self.theme["fg_text"],
                    wraplength=col["width"] - 12,
                    justify=tk.LEFT,
                    anchor="nw",
                    padx=4, pady=2,
                    highlightthickness=1 if self.show_grid else 0,
                    highlightbackground=border if self.show_grid else row_bg,
                    highlightcolor=border if self.show_grid else row_bg,
                    bd=0,
                )
                lbl.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)
                lbl.bind("<Button-1>", lambda e, rr=r: self._on_click(rr))
                lbl.bind("<Double-1>", lambda e, rr=r: self._on_dbl(rr))
                lbl.bind("<Button-3>", lambda e, rr=r: self._on_right(e, rr))
                row_labels.append(lbl)
            self.cell_labels.append(row_labels)

    # ---------- 交互 ----------
    def _highlight(self, row):
        if 0 <= self.selected_row < len(self.cell_labels):
            old_bg = self._row_bg(self.selected_row)
            for lbl in self.cell_labels[self.selected_row]:
                lbl.configure(bg=old_bg, fg=self.theme["fg_text"])
        if 0 <= row < len(self.cell_labels):
            for lbl in self.cell_labels[row]:
                lbl.configure(bg=self.theme["bg_select"],
                              fg=self.theme["fg_white"])
        self.selected_row = row

    def _on_click(self, row):
        self._highlight(row)
        if self.on_select:
            self.on_select(self.data[row], row)

    def _on_dbl(self, row):
        if self.on_double_click:
            self.on_double_click(self.data[row], row)

    def _on_right(self, event, row):
        self._highlight(row)
        if self.on_right_click:
            self.on_right_click(event, self.data[row], row)

    # ---------- 外部 API ----------
    def get_selected(self):
        if 0 <= self.selected_row < len(self.data):
            return self.data[self.selected_row]
        return None

    def set_columns(self, columns):
        """
        运行时切换列定义。
        columns 是 [{"key": ..., "text": ..., "width": ...}, ...] 列表。
        切换后会重建表头，并用现有 data 重绘。
        """
        self.columns = columns
        self._build_header()
        if self.data:
            self.set_data(self.data)

    def update_theme(self, theme):
        """主题切换时调用，重建显示"""
        self.theme = theme
        self.configure(bg=theme["bg_table"])
        self.header_frame.configure(bg=theme["bg_heading"])
        self.inner.configure(bg=theme["bg_table"])
        self.canvas.configure(bg=theme["bg_table"])
        self._build_header()
        if self.data:
            self.set_data(self.data)