# -*- coding: utf-8 -*-
"""封装速查（主窗口内的一页，不是弹窗）"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from services import footprint_service
from utils.constants import THEMES
from utils.error_handler import log_error


class FootprintSearchView(tk.Frame):
    """封装速查页面。parent 是 MainWindow。"""

    def __init__(self, parent):
        theme = THEMES[parent.current_theme]
        super().__init__(parent, bg=theme["bg_main"])
        self.parent = parent

        # 搜索栏
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=10, pady=(10, 4))
        ttk.Label(top, text="搜索封装：").pack(side=tk.LEFT)

        self.query_var = tk.StringVar(value=parent.last_footprint_query)
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
            text="关键词：tvs / esd / 退耦 / C384887 / typec / 0603 / 上拉   （双击复制封装名，右键更多操作）"
        )
        tip.pack(fill=tk.X, padx=10, pady=(0, 4))

        # 表格
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        cols = ("display", "name", "lcsc_ids", "category", "pins", "builtin", "note")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        for key, text, width in [
            ("display", "简介", 200),
            ("name", "封装名", 220),
            ("lcsc_ids", "C 编号", 140),
            ("category", "分类", 60),
            ("pins", "引脚", 45),
            ("builtin", "来源", 55),
            ("note", "备注", 180),
        ]:
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width, anchor=tk.W)

        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self.on_double_click)

        # 右键菜单
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="复制封装名", command=self.copy_name)
        self.context_menu.add_command(label="复制 C 编号", command=self.copy_lcsc)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="编辑选中", command=self.edit_footprint)
        self.context_menu.add_command(label="删除选中", command=self.delete_footprint)
        self.tree.bind("<Button-3>", self.show_context_menu)

        # 底部按钮
        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X, padx=10, pady=(4, 10))
        ttk.Button(bottom, text="添加封装", command=self.add_footprint).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="编辑选中", command=self.edit_footprint).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="删除选中", command=self.delete_footprint).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="复制封装名", command=self.copy_name).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="复制 C 编号", command=self.copy_lcsc).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="应用到选中元件", command=self.apply_to_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="← 返回主界面", command=self.parent.show_main_view).pack(side=tk.RIGHT, padx=4)

        self.results = []
        self.do_search()

    # ==================== 搜索 ====================
    def do_search(self):
        query = self.query_var.get()
        self.parent.last_footprint_query = query
        self.results = footprint_service.search(query)
        for i in self.tree.get_children():
            self.tree.delete(i)
        for fp in self.results:
            lcsc = fp.get("lcsc_ids", [])
            if isinstance(lcsc, list):
                lcsc = ",".join(lcsc)
            self.tree.insert("", tk.END, values=(
                fp.get("display", ""),
                fp.get("name", ""),
                lcsc or "",
                fp.get("category", ""),
                fp.get("pins") or "",
                "内置" if fp.get("is_builtin") else "自定义",
                fp.get("note", ""),
            ))
        self.count_var.set(f"共 {len(self.results)} 条")

    def clear_search(self):
        self.query_var.set("")
        self.do_search()

    def _selected_fp(self):
        sel = self.tree.selection()
        if not sel:
            return None
        idx = self.tree.index(sel[0])
        return self.results[idx] if 0 <= idx < len(self.results) else None

    def on_double_click(self, event):
        self.copy_name()

    # ==================== 右键菜单 ====================
    def show_context_menu(self, event):
        """右键：先选中鼠标所在行，再弹出菜单"""
        row_id = self.tree.identify_row(event.y)
        if row_id:
            self.tree.selection_set(row_id)
        if not self.tree.selection():
            return
        self.context_menu.post(event.x_root, event.y_root)

    # ==================== 复制 ====================
    def copy_name(self):
        fp = self._selected_fp()
        if not fp:
            messagebox.showwarning("提示", "请先选中一行")
            return
        self.clipboard_clear()
        self.clipboard_append(fp["name"])
        messagebox.showinfo("已复制", f"已复制封装名：\n{fp['name']}")

    def copy_lcsc(self):
        fp = self._selected_fp()
        if not fp:
            messagebox.showwarning("提示", "请先选中一行")
            return
        lcsc = fp.get("lcsc_ids", [])
        if isinstance(lcsc, str):
            lcsc = [t.strip() for t in lcsc.split(",") if t.strip()]
        if not lcsc:
            messagebox.showwarning("提示", "这一行没有填 C 编号\n可以去「编辑选中」里补上")
            return
        text = ",".join(lcsc)
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("已复制", f"已复制 C 编号：\n{text}")

    # ==================== 应用到选中元件 ====================
    def apply_to_selected(self):
        fp = self._selected_fp()
        if not fp:
            messagebox.showwarning("提示", "请先选中一行封装")
            return

        comp = self.parent.get_selected_component()
        if comp is None:
            messagebox.showwarning("提示", "请先在主界面选中一个元件")
            return

        try:
            from services import component_service
            component_service.update_component(comp.id, package=fp["name"])
            self.parent.refresh_table()
            messagebox.showinfo("成功", f"已将 {comp.model} 的封装更新为：\n{fp['name']}")
        except Exception as e:
            log_error(e)
            messagebox.showerror("失败", f"更新封装时出错：{e}")

    # ==================== 增删改 ====================
    def add_footprint(self):
        from ui.footprint_edit_dialog import FootprintEditDialog
        dlg = FootprintEditDialog(self.parent, None)
        self.parent.wait_window(dlg)
        if dlg.result:
            self.do_search()

    def edit_footprint(self):
        fp = self._selected_fp()
        if not fp:
            messagebox.showwarning("提示", "请先选中一行")
            return
        from ui.footprint_edit_dialog import FootprintEditDialog
        dlg = FootprintEditDialog(self.parent, fp)
        self.parent.wait_window(dlg)
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

        report = footprint_service.validate_csv(path)

        if report["file_error"]:
            messagebox.showerror("文件错误", report["file_error"])
            return

        if report["errors"]:
            lines = [f"文件：{path}", f"总行数：{report['total']}", ""]
            lines.append(f"❌ 发现 {len(report['errors'])} 条错误，已拒绝导入。")
            lines.append("")
            lines.append("错误明细（前 20 条）：")
            lines.extend(report["errors"][:20])
            if len(report["errors"]) > 20:
                lines.append(f"... 还有 {len(report['errors']) - 20} 条")
            lines.append("")
            lines.append("请修正 CSV 后重新导入，数据未做任何修改。")
            messagebox.showerror("校验未通过", "\n".join(lines))
            return

        lines = [f"文件：{path}", f"总行数：{report['total']}", f"有效行：{report['valid']}", ""]
        if report["warnings"]:
            lines.append(f"⚠️ 警告 {len(report['warnings'])} 条（前 5 条）：")
            lines.extend(report["warnings"][:5])
            lines.append("")
        lines.append("所有行通过校验，可以导入。")

        if not messagebox.askyesno("确认导入", "\n".join(lines)):
            return

        try:
            result = footprint_service.import_from_csv(path, strict=True)
            if result.get("aborted"):
                messagebox.showerror("导入已终止", result.get("reason", "导入被拒绝"))
                return
            msg = f"新增 {result['success']} 条\n更新 {result['updated']} 条"
            messagebox.showinfo("导入结果", msg)
            self.do_search()
        except Exception as e:
            log_error(e)
            messagebox.showerror("导入失败", str(e))