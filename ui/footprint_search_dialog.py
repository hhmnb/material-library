# -*- coding: utf-8 -*-
"""封装速查（主窗口内的一页，不是弹窗）"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os

from services import footprint_service
from services import component_service
from utils.constants import THEMES
from utils.error_handler import log_error
from ui.wrapped_table import WrappedTable


class FootprintSearchView(tk.Frame):
    """封装速查页面。parent 是 MainWindow。"""

    def __init__(self, parent):
        theme = THEMES[parent.current_theme]
        super().__init__(parent, bg=theme["bg_main"])
        self.parent = parent

        # ===== 搜索栏 =====
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

        # 右侧按钮：导出 / 智能导入 / AI 提示词 / 回填规格
        ttk.Button(top, text="导出 CSV", command=self.export_csv).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="智能导入", command=self.smart_import).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="AI 提示词", command=self.copy_ai_prompt).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="回填规格", command=self.backfill_specs).pack(side=tk.RIGHT, padx=4)

        tip = ttk.Label(
            self,
            text="关键词：tvs / esd / 退耦 / C384887 / typec / 0603 / 上拉   （双击复制封装名，右键更多操作）"
        )
        tip.pack(fill=tk.X, padx=10, pady=(0, 4))

        # ===== 表格（WrappedTable） =====
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        columns = [
            {"key": "display",  "text": "简介",   "width": 200},
            {"key": "name",     "text": "封装名", "width": 250},
            {"key": "lcsc_ids", "text": "C 编号", "width": 130},
            {"key": "specs",    "text": "规格",   "width": 180},
            {"key": "category", "text": "分类",   "width": 70},
            {"key": "pins",     "text": "引脚",   "width": 50},
            {"key": "builtin",  "text": "来源",   "width": 60},
            {"key": "note",     "text": "备注",   "width": 180},
        ]
        self.tbl = WrappedTable(
            table_frame, columns, theme,
            show_grid=True,
            on_select=self._on_row_select,
            on_double_click=self._on_row_double_click,
            on_right_click=self._on_row_right_click,
        )
        self.tbl.pack(fill=tk.BOTH, expand=True)

        # ===== 右键菜单 =====
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="复制封装名", command=self.copy_name)
        self.context_menu.add_command(label="复制 C 编号", command=self.copy_lcsc)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="编辑选中", command=self.edit_footprint)
        self.context_menu.add_command(label="删除选中", command=self.delete_footprint)

        # ===== 底部按钮 =====
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

        rows = []
        for fp in self.results:
            lcsc = fp.get("lcsc_ids", [])
            if isinstance(lcsc, list):
                lcsc_list = lcsc
                lcsc_str = ",".join(lcsc)
            else:
                lcsc_str = lcsc or ""
                lcsc_list = [t.strip() for t in lcsc_str.split(",") if t.strip()]

            # 关联元件表查询规格
            specs = component_service.get_specs_by_lcsc_ids(lcsc_list) if lcsc_list else ""

            rows.append({
                "display":  fp.get("display", ""),
                "name":     fp.get("name", ""),
                "lcsc_ids": lcsc_str,
                "specs":    specs or "",
                "category": fp.get("category", ""),
                "pins":     fp.get("pins") or "",
                "builtin":  "内置" if fp.get("is_builtin") else "自定义",
                "note":     fp.get("note", ""),
                "_fp":      fp,
            })
        self.tbl.set_data(rows)
        self.count_var.set(f"共 {len(self.results)} 条")

    def clear_search(self):
        self.query_var.set("")
        self.do_search()

    def _selected_fp(self):
        row = self.tbl.get_selected()
        if not row:
            return None
        return row.get("_fp")

    # ==================== WrappedTable 回调 ====================
    def _on_row_select(self, row_data, row_index):
        pass

    def _on_row_double_click(self, row_data, row_index):
        self.copy_name()

    def _on_row_right_click(self, event, row_data, row_index):
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

    # ==================== 导出 CSV ====================
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

    # ==================== 智能导入（自动识别封装库 / BOM） ====================
    def smart_import(self):
        path = filedialog.askopenfilename(
            title="选择要导入的 CSV（自动识别封装库 / BOM）",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
        )
        if not path:
            return

        try:
            result = component_service.smart_import_csv(path)
        except Exception as e:
            log_error(e)
            messagebox.showerror("导入失败", f"读取 CSV 时出错：\n{e}")
            return

        kind = result.get("kind")

        # 校验被拒（只可能出现在封装库分支）
        if result.get("aborted"):
            reason = result.get("reason", "已拒绝导入")
            report = result.get("report") or {}
            errs = report.get("errors") or []
            lines = [f"文件：{path}", "识别类型：封装库", f"❌ {reason}"]
            if errs:
                lines.append("")
                lines.append("错误明细（前 20 条）：")
                lines.extend(errs[:20])
                if len(errs) > 20:
                    lines.append(f"... 还有 {len(errs) - 20} 条")
            messagebox.showerror("导入未通过", "\n".join(lines))
            return

        # 正常结果
        if kind == "footprint":
            r = result["result"]
            lines = [
                f"文件：{path}",
                "识别类型：✅ 封装库",
                "",
                f"新增：{r.get('success', 0)} 条",
                f"更新：{r.get('updated', 0)} 条",
            ]
            messagebox.showinfo("智能导入 · 封装库", "\n".join(lines))
            self.do_search()
        else:
            r = result["result"]
            fails = r.get("failures", [])
            lines = [
                f"文件：{path}",
                "识别类型：✅ BOM（元件）",
                f"总行数：{r.get('total', 0)}",
                "",
                f"✅ 新增：{r.get('success', 0)} 条",
                f"🔄 更新（信息更完整）：{r.get('updated', 0)} 条",
                f"⏭ 跳过（重复且不更完整）：{r.get('skipped', 0)} 条",
            ]
            if fails:
                lines.append("")
                lines.append(f"ℹ 明细（前 30 条，共 {len(fails)}）：")
                lines.extend(fails[:30])
                if len(fails) > 30:
                    lines.append(f"... 还有 {len(fails) - 30} 条")
            messagebox.showinfo("智能导入 · BOM", "\n".join(lines))
            self.do_search()
            try:
                self.parent.refresh_table()
            except Exception:
                pass

    # ==================== AI 提示词（可选附加本地文档） ====================
    def copy_ai_prompt(self):
        """
        与主界面一致：
          是   → 选本地文档 → 提示词 + 文档内容 一起复制
          否   → 只复制提示词
          取消 → 什么都不做
        """
        choice = messagebox.askyesnocancel(
            "AI 提示词",
            "是否要附加一份本地文档？\n\n"
            "  是  = 选择文档，提示词 + 文档内容一起复制（推荐）\n"
            "  否  = 只复制提示词（你自己去 AI 那里贴原始信息）\n"
            "  取消 = 关闭"
        )
        if choice is None:
            return

        filepath = None
        if choice:
            filepath = filedialog.askopenfilename(
                title="选择要附加的文档",
                filetypes=[
                    ("文本类文件", "*.txt *.md *.log *.csv *.json *.xml *.yaml *.yml"),
                    ("所有文件", "*.*"),
                ],
            )
            if not filepath:
                # 用户取消选文件，退化为只复制提示词
                filepath = None

        try:
            text = component_service.build_ai_prompt_with_file(filepath)
            self.clipboard_clear()
            self.clipboard_append(text)

            if filepath:
                fname = os.path.basename(filepath)
                messagebox.showinfo(
                    "已复制",
                    "提示词 + 文档内容已复制到剪贴板。\n\n"
                    f"文档：{fname}\n"
                    f"总长度：{len(text)} 字符\n\n"
                    "直接粘到 AI 对话框即可，AI 会按规范解析文档里的元件信息。"
                )
            else:
                messagebox.showinfo(
                    "已复制",
                    "AI 提示词已复制到剪贴板。\n\n"
                    "使用方式：把提示词粘给 AI，再附上你要处理的原始信息。"
                )
        except Exception as e:
            log_error(e)
            messagebox.showerror("复制失败", f"复制 AI 提示词时出错：{e}")

    # ==================== 回填规格 ====================
    def backfill_specs(self):
        try:
            result = component_service.backfill_specs_from_desc(only_empty=True)
            self.do_search()
            messagebox.showinfo(
                "回填完成",
                f"扫描：{result['scanned']} 条\n"
                f"更新：{result['updated']} 条\n"
                f"跳过：{result['skipped']} 条"
            )
        except Exception as e:
            log_error(e)
            messagebox.showerror("回填失败", str(e))