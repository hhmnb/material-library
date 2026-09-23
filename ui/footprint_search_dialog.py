# -*- coding: utf-8 -*-
"""封装速查（主窗口内的一页）——数据从 components 表聚合展示"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import csv
import io

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

        # 右侧按钮
        ttk.Button(top, text="导出 CSV", command=self.export_csv).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="粘贴导入 BOM", command=self.open_paste_bom_dialog).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="AI 提示词", command=self.copy_ai_prompt).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="刷新", command=self.do_search).pack(side=tk.RIGHT, padx=4)

        tip = ttk.Label(
            self,
            text="数据来源：元件库自动聚合。双击复制封装名，右键更多操作。"
        )
        tip.pack(fill=tk.X, padx=10, pady=(0, 4))

        # ===== 表格 =====
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        columns = [
            {"key": "display",  "text": "简介",     "width": 200},
            {"key": "name",     "text": "封装名",   "width": 250},
            {"key": "lcsc_ids", "text": "C 编号",   "width": 130},
            {"key": "specs",    "text": "规格",     "width": 200},
            {"key": "category", "text": "分类",     "width": 70},
            {"key": "pins",     "text": "引脚",     "width": 50},
            {"key": "note",     "text": "该封装元件", "width": 200},
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
        self.context_menu.add_command(label="在主界面筛选该封装的元件", command=self.filter_in_main)

        # ===== 底部按钮 =====
        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X, padx=10, pady=(4, 10))
        ttk.Button(bottom, text="复制封装名", command=self.copy_name).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="复制 C 编号", command=self.copy_lcsc).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="应用到选中元件", command=self.apply_to_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="在主界面查看", command=self.filter_in_main).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="← 返回主界面", command=self.parent.show_main_view).pack(side=tk.RIGHT, padx=4)

        self.results = []
        self.do_search()

    # ==================== 搜索（从元件库聚合） ====================
    def do_search(self):
        query = self.query_var.get()
        self.parent.last_footprint_query = query

        try:
            self.results = component_service.list_footprints_from_components(query)
        except Exception as e:
            log_error(e)
            messagebox.showerror("错误", f"读取封装失败：{e}")
            self.results = []

        rows = []
        for fp in self.results:
            rows.append({
                "display":  fp.get("display", ""),
                "name":     fp.get("name", ""),
                "lcsc_ids": fp.get("lcsc_ids", ""),
                "specs":    fp.get("specs", ""),
                "category": fp.get("category", ""),
                "pins":     fp.get("pins", ""),
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

    # ==================== 回调 ====================
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
        lcsc = fp.get("lcsc_ids", "")
        if isinstance(lcsc, list):
            lcsc = [t.strip() for t in lcsc if t.strip()]
            text = ",".join(lcsc)
        else:
            text = (lcsc or "").strip()
        if not text:
            messagebox.showwarning("提示", "该封装下没有元件有 C 编号")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("已复制", f"已复制 C 编号：\n{text}")

    # ==================== 主界面联动 ====================
    def filter_in_main(self):
        """在主界面搜索框填入封装名，跳回主界面"""
        fp = self._selected_fp()
        if not fp:
            messagebox.showwarning("提示", "请先选中一行")
            return
        self.parent.search_var.set(fp["name"])
        self.parent.project_var.set("[全部]")
        self.parent.notify_data_changed()
        self.parent.show_main_view()

    def apply_to_selected(self):
        """把选中封装的名称，更新到主界面当前选中的元件"""
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
            self.parent.notify_data_changed()
            messagebox.showinfo("成功", f"已将 {comp.model} 的封装更新为：\n{fp['name']}")
        except Exception as e:
            log_error(e)
            messagebox.showerror("失败", f"更新封装时出错：{e}")

    # ==================== 导出 CSV ====================
    def export_csv(self):
        if not self.results:
            messagebox.showwarning("提示", "当前无数据")
            return
        path = filedialog.asksaveasfilename(
            title="导出封装聚合视图",
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")],
            initialfile="footprints.csv",
        )
        if not path:
            return
        try:
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["简介", "封装名", "C 编号", "规格",
                                 "分类", "引脚", "该封装元件"])
                for fp in self.results:
                    writer.writerow([
                        fp.get("display", ""),
                        fp.get("name", ""),
                        fp.get("lcsc_ids", ""),
                        fp.get("specs", "").replace("\n", " | "),
                        fp.get("category", ""),
                        fp.get("pins", ""),
                        fp.get("note", ""),
                    ])
            messagebox.showinfo("成功", f"已导出 {len(self.results)} 条到：\n{path}")
        except Exception as e:
            log_error(e)
            messagebox.showerror("导出失败", str(e))

    # ==================== 粘贴导入 BOM ====================
    def open_paste_bom_dialog(self):
        from ui.main_window import PasteBomDialog
        dlg = PasteBomDialog(self.parent)
        self.parent.wait_window(dlg)
        if dlg.result:
            self.parent.notify_data_changed()

    # ==================== AI 提示词 ====================
    def copy_ai_prompt(self):
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
                    "直接粘到 AI 对话框即可。"
                )
            else:
                messagebox.showinfo(
                    "已复制",
                    "AI 提示词已复制到剪贴板。\n\n"
                    "把它发给 AI，让 AI 按格式输出元件清单，\n"
                    "然后把清单粘回「添加元件」或「粘贴导入」即可。"
                )
        except Exception as e:
            log_error(e)
            messagebox.showerror("复制失败", str(e))