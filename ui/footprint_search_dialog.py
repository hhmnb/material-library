# -*- coding: utf-8 -*-
"""封装速查对话框（数据库版，支持增删改）"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from services import footprint_service
from utils.constants import THEMES
from utils.error_handler import log_error


class FootprintSearchDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("封装速查")
        self.geometry("960x620")
        self.minsize(800, 500)

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
        style.configure('Treeview',
                        background=theme["bg_table"],
                        foreground=theme["fg_text"],
                        fieldbackground=theme["bg_table"])
        style.configure('Treeview.Heading',
                        background=theme["bg_heading"],
                        foreground=theme["fg_text"],
                        relief='flat')
        style.map('Treeview',
                  background=[('selected', theme["bg_select"])],
                  foreground=[('selected', theme["fg_white"])])

        # 搜索栏
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=10, pady=(10, 4))
        ttk.Label(top, text="搜索封装：").pack(side=tk.LEFT)
        self.query_var = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.query_var, width=42)
        entry.pack(side=tk.LEFT, padx=5)
        entry.bind("<Return>", lambda e: self.do_search())
        entry.focus_set()

        ttk.Button(top, text="搜索", command=self.do_search).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="清空", command=self.clear_search).pack(side=tk.LEFT, padx=4)

        self.count_var = tk.StringVar()
        ttk.Label(top, textvariable=self.count_var).pack(side=tk.LEFT, padx=10)

        ttk.Button(top, text="导出 CSV", command=self.export_csv).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="导入 CSV", command=self.import_csv).pack(side=tk.RIGHT, padx=4)

        tip = ttk.Label(
            self,
            text="关键词示例：typec / c口 / 0603 / sop16 / 排针 / usb / 贴片 / 直插    （双击行复制封装名）"
        )
        tip.pack(fill=tk.X, padx=10, pady=(0, 4))

        # 表格
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        cols = ("display", "name", "category", "pins", "builtin", "note")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        for key, text, width in [
            ("display", "简介", 220),
            ("name", "封装名", 240),
            ("category", "分类", 70),
            ("pins", "引脚", 50),
            ("builtin", "来源", 60),
            ("note", "备注", 200),
        ]:
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width, anchor=tk.W)

        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self.on_double_click)

        # 底部按钮
        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X, padx=10, pady=(4, 10))
        ttk.Button(bottom, text="添加封装", command=self.add_footprint).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="编辑选中", command=self.edit_footprint).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="删除选中", command=self.delete_footprint).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="复制封装名", command=self.copy_name).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="应用到选中元件", command=self.apply_to_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="关闭", command=self.destroy).pack(side=tk.RIGHT, padx=4)

        self.results = []
        self.do_search()

    # ==================== 搜索 ====================
    def do_search(self):
        query = self.query_var.get()
        self.results = footprint_service.search(query)
        for i in self.tree.get_children():
            self.tree.delete(i)
        for fp in self.results:
            self.tree.insert("", tk.END, values=(
                fp.get("display", ""),
                fp.get("name", ""),
                fp.get("category", ""),
                fp.get("pins") or "",
                "内置" if fp.get("is_builtin") else "自定义",
                fp.get("note", ""),
            ))
        self.count_var.set(f"共 {len(self.results)} 条")

    def clear_search(self):
        self.query_var.set("")
        self.do_search()

    # ==================== 选中 ====================
    def _selected_fp(self):
        sel = self.tree.selection()
        if not sel:
            return None
        idx = self.tree.index(sel[0])
        return self.results[idx] if 0 <= idx < len(self.results) else None

    def on_double_click(self, event):
        self.copy_name()

    # ==================== 复制 ====================
    def copy_name(self):
        fp = self._selected_fp()
        if not fp:
            messagebox.showwarning("提示", "请先选中一行")
            return
        self.clipboard_clear()
        self.clipboard_append(fp["name"])
        messagebox.showinfo("已复制", f"已复制封装名：\n{fp['name']}")

    # ==================== 应用到选中元件 ====================
    def apply_to_selected(self):
        fp = self._selected_fp()
        if not fp:
            messagebox.showwarning("提示", "请先选中一行封装")
            return

        parent = self.parent
        sel = parent.tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先在主窗口选中一个元件")
            return

        values = parent.tree.item(sel[0], "values")
        if len(values) < 4:
            messagebox.showwarning("提示", "选中的元件数据不完整")
            return

        lcsc_id = values[3]
        model = values[1]

        try:
            from services import component_service
            comp = component_service.get_component_by_lcsc_id(lcsc_id) if lcsc_id else None
            if comp is None and model:
                comp = component_service.get_component_by_model(model)
            if comp is None:
                messagebox.showerror("错误", "未找到对应元件")
                return

            component_service.update_component(comp.id, package=fp["name"])
            parent.refresh_table()
            messagebox.showinfo("成功", f"已将 {comp.model} 的封装更新为：\n{fp['name']}")
        except Exception as e:
            log_error(e)
            messagebox.showerror("失败", f"更新封装时出错：{e}")

    # ==================== 增删改 ====================
    def add_footprint(self):
        from ui.footprint_edit_dialog import FootprintEditDialog
        dlg = FootprintEditDialog(self, None)
        self.wait_window(dlg)
        if dlg.result:
            self.do_search()

    def edit_footprint(self):
        fp = self._selected_fp()
        if not fp:
            messagebox.showwarning("提示", "请先选中一行")
            return
        from ui.footprint_edit_dialog import FootprintEditDialog
        dlg = FootprintEditDialog(self, fp)
        self.wait_window(dlg)
        if dlg.result:
            self.do_search()

    def delete_footprint(self):
        fp = self._selected_fp()
        if not fp:
            messagebox.showwarning("提示", "请先选中一行")
            return
        if fp.get("is_builtin"):
            if not messagebox.askyesno("提示", "这是内置封装，删除后不会自动恢复。\n确定要删除吗？"):
                return
        else:
            if not messagebox.askyesno("确认", f"确定要删除封装：{fp['name']} 吗？"):
                return
        try:
            footprint_service.delete(fp["id"])
            self.do_search()
        except Exception as e:
            messagebox.showerror("删除失败", str(e))

    # ==================== 导入导出 ====================
    def export_csv(self):
        path = filedialog.asksaveasfilename(
            title="导出封装库",
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")],
            initialfile="footprints.csv",
        )
        if not path:
            return
        try:
            n = footprint_service.export_to_csv(path)
            messagebox.showinfo("成功", f"已导出 {n} 条封装到：\n{path}")
        except Exception as e:
            log_error(e)
            messagebox.showerror("导出失败", str(e))

    def import_csv(self):
        path = filedialog.askopenfilename(
            title="导入封装库",
            filetypes=[("CSV 文件", "*.csv")],
        )
        if not path:
            return
        try:
            result = footprint_service.import_from_csv(path)
            msg = f"成功 {result['success']} 条"
            if result["skipped"]:
                msg += f"\n跳过 {result['skipped']} 条"
            if result["failures"]:
                msg += f"\n失败 {len(result['failures'])} 条：\n" + "\n".join(result["failures"][:5])
            messagebox.showinfo("导入结果", msg)
            self.do_search()
        except Exception as e:
            log_error(e)
            messagebox.showerror("导入失败", str(e))