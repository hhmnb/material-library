# -*- coding: utf-8 -*-
"""项目管理弹窗"""
import tkinter as tk
import os
from tkinter import ttk, messagebox, filedialog

from services import project_service
from services import component_service
from utils.constants import THEMES
from utils.error_handler import log_error


class ProjectManagerDialog(tk.Toplevel):
    """项目管理：列出所有项目，可增/改/删"""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("项目管理")
        self.geometry("760x480")
        self.resizable(False, False)

        theme = THEMES[parent.current_theme]
        self.theme = theme
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
                        fieldbackground=theme["bg_table"],
                        bordercolor=theme["border"])
        style.configure('Treeview.Heading',
                        background=theme["bg_heading"],
                        foreground=theme["fg_text"],
                        relief='flat')
        style.map('Treeview',
                  background=[('selected', theme["bg_select"])],
                  foreground=[('selected', theme["fg_white"])])

        # 顶部输入区
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(top, text="项目名：").pack(side=tk.LEFT)
        self.name_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.name_var, width=18).pack(side=tk.LEFT, padx=5)

        ttk.Label(top, text="描述：").pack(side=tk.LEFT, padx=(10, 0))
        self.desc_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.desc_var, width=32).pack(side=tk.LEFT, padx=5)

        ttk.Button(top, text="新增", command=self.add_project).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="清空输入", command=self.clear_input).pack(side=tk.LEFT, padx=5)

        # 表格
        tbl_frame = ttk.Frame(self)
        tbl_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        cols = ("name", "desc", "count", "created")
        self.tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", selectmode="browse")
        for key, text, w in [
            ("name", "项目名", 150),
            ("desc", "描述", 260),
            ("count", "元件数", 80),
            ("created", "创建时间", 160),
        ]:
            self.tree.heading(key, text=text)
            self.tree.column(key, width=w, anchor=tk.W)
        vsb = ttk.Scrollbar(tbl_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", lambda e: self.edit_project())

        # 底部按钮
        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X, padx=10, pady=(4, 10))
        ttk.Button(bottom, text="编辑选中", command=self.edit_project).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="删除选中", command=self.delete_project).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="刷新", command=self.reload).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="关闭", command=self.destroy).pack(side=tk.RIGHT, padx=4)

        self.projects = []
        self.reload()

        self.transient(parent)
        self.grab_set()

    def clear_input(self):
        self.name_var.set("")
        self.desc_var.set("")

    def reload(self):
        try:
            self.projects = project_service.list_all_projects()
        except Exception as e:
            log_error(e)
            messagebox.showerror("错误", f"读取项目失败：{e}")
            self.projects = []
        for i in self.tree.get_children():
            self.tree.delete(i)
        for p in self.projects:
            self.tree.insert("", tk.END, values=(
                p["name"],
                p.get("description", ""),
                p.get("item_count", 0),
                p.get("created_at", ""),
            ))

    def _selected_project(self):
        sel = self.tree.selection()
        if not sel:
            return None
        idx = self.tree.index(sel[0])
        if 0 <= idx < len(self.projects):
            return self.projects[idx]
        return None

    def add_project(self):
        name = self.name_var.get().strip()
        desc = self.desc_var.get().strip()
        if not name:
            messagebox.showwarning("提示", "请输入项目名")
            return
        try:
            project_service.create_project(name, desc)
            self.clear_input()
            self.reload()
        except Exception as e:
            log_error(e)
            messagebox.showerror("失败", str(e))

    def edit_project(self):
        p = self._selected_project()
        if not p:
            messagebox.showwarning("提示", "请先选中一行")
            return
        dlg = EditProjectDialog(self, p)
        self.wait_window(dlg)
        if dlg.result:
            self.reload()

    def delete_project(self):
        p = self._selected_project()
        if not p:
            messagebox.showwarning("提示", "请先选中一行")
            return
        count = p.get("item_count", 0)
        if not messagebox.askyesno(
            "确认删除",
            f"确定删除项目「{p['name']}」？\n\n"
            f"该项目下有 {count} 个元件关联，删除项目不会删除元件本身，\n"
            f"只会移除这些元件与本项目的关联。"
        ):
            return
        try:
            project_service.delete_project(p["id"])
            self.reload()
        except Exception as e:
            log_error(e)
            messagebox.showerror("失败", f"删除失败：{e}")


class EditProjectDialog(tk.Toplevel):
    """编辑项目名 / 描述"""

    def __init__(self, parent, project):
        super().__init__(parent)
        self.parent = parent
        self.project = project
        self.result = False

        theme = parent.theme
        self.configure(bg=theme["bg_main"])
        self.title("编辑项目")
        self.geometry("440x220")
        self.resizable(False, False)

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

        f = ttk.Frame(self)
        f.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        ttk.Label(f, text="项目名：").grid(row=0, column=0, sticky="w", pady=6)
        self.name_var = tk.StringVar(value=project["name"])
        ttk.Entry(f, textvariable=self.name_var, width=30).grid(row=0, column=1, pady=6)

        ttk.Label(f, text="描述：").grid(row=1, column=0, sticky="w", pady=6)
        self.desc_var = tk.StringVar(value=project.get("description", ""))
        ttk.Entry(f, textvariable=self.desc_var, width=30).grid(row=1, column=1, pady=6)

        btn = ttk.Frame(self)
        btn.pack(pady=10)
        ttk.Button(btn, text="保存", command=self.save).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=6)

        self.transient(parent)
        self.grab_set()

    def save(self):
        name = self.name_var.get().strip()
        desc = self.desc_var.get().strip()
        if not name:
            messagebox.showwarning("提示", "项目名不能为空")
            return
        try:
            if name != self.project["name"]:
                existing = project_service.get_project_by_name(name)
                if existing and existing["id"] != self.project["id"]:
                    raise ValueError(f"项目名已被占用：{name}")
            project_service.update_project(
                self.project["id"], name=name, description=desc
            )
            self.result = True
            self.destroy()
        except Exception as e:
            log_error(e)
            messagebox.showerror("保存失败", str(e))


class AddToProjectDialog(tk.Toplevel):
    """把某个元件加入项目（可现场新建项目）"""

    def __init__(self, parent, component):
        super().__init__(parent)
        self.parent = parent
        self.component = component
        self.result = False

        theme = THEMES[parent.current_theme]
        self.configure(bg=theme["bg_main"])
        self.title("加入项目")
        self.geometry("440x280")
        self.resizable(False, False)

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
        style.configure('TCombobox',
                        fieldbackground=theme["bg_input"],
                        foreground=theme["fg_text"])

        f = ttk.Frame(self)
        f.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        ttk.Label(f, text=f"元件：{component.model}").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )

        ttk.Label(f, text="项目：").grid(row=1, column=0, sticky="w", pady=6)
        self.project_var = tk.StringVar()
        projects = project_service.list_all_projects()
        self.project_combo = ttk.Combobox(
            f, textvariable=self.project_var,
            values=[p["name"] for p in projects],
            width=28
        )
        self.project_combo.grid(row=1, column=1, pady=6)
        self.project_combo.focus_set()

        ttk.Label(f, text="用量：").grid(row=2, column=0, sticky="w", pady=6)
        self.qty_var = tk.StringVar(value="1")
        ttk.Entry(f, textvariable=self.qty_var, width=28).grid(row=2, column=1, pady=6)

        ttk.Label(f, text="备注：").grid(row=3, column=0, sticky="w", pady=6)
        self.note_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.note_var, width=28).grid(row=3, column=1, pady=6)

        ttk.Label(
            f, text="提示：输入不存在的项目名会自动创建新项目",
            foreground=theme["fg_text"]
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(4, 0))

        btn = ttk.Frame(self)
        btn.pack(pady=10)
        ttk.Button(btn, text="加入", command=self.save).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=6)

        self.transient(parent)
        self.grab_set()

    def save(self):
        name = self.project_var.get().strip()
        if not name:
            messagebox.showwarning("提示", "请选择或输入项目名")
            return
        try:
            qty = int(self.qty_var.get().strip() or "1")
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "用量必须是正整数")
            return

        try:
            proj = project_service.get_project_by_name(name)
            if not proj:
                pid = project_service.create_project(name, "")
            else:
                pid = proj["id"]
            project_service.add_component_to_project(
                pid, self.component.id, qty, self.note_var.get().strip()
            )
            self.result = True
            self.destroy()
        except Exception as e:
            log_error(e)
            messagebox.showerror("加入失败", str(e))


class RemoveFromProjectDialog(tk.Toplevel):
    """从当前项目中移除指定元件"""

    def __init__(self, parent, project, component):
        super().__init__(parent)
        self.parent = parent
        self.project = project
        self.component = component
        self.result = False

        theme = THEMES[parent.current_theme]
        self.configure(bg=theme["bg_main"])
        self.title("从项目移除")
        self.geometry("440x180")
        self.resizable(False, False)

        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TLabel', background=theme["bg_main"], foreground=theme["fg_text"])
        style.configure('TFrame', background=theme["bg_main"])
        style.configure('TButton', background=theme["bg_button"], foreground=theme["fg_text"],
                        bordercolor=theme["border"])
        style.map('TButton',
                  background=[('active', theme["bg_button_hover"]), ('pressed', theme["bg_main"])],
                  foreground=[('active', theme["fg_white"])])

        f = ttk.Frame(self)
        f.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        ttk.Label(
            f,
            text=f"从项目「{project['name']}」中移除元件：\n\n{component.model}",
            justify=tk.LEFT
        ).pack(anchor="w", pady=(0, 10))

        ttk.Label(
            f,
            text="（元件本身不会被删除，只是解除与本项目的关联）",
            foreground=theme["fg_text"]
        ).pack(anchor="w", pady=(0, 10))

        btn = ttk.Frame(self)
        btn.pack(pady=10)
        ttk.Button(btn, text="确认移除", command=self.do_remove).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=6)

        self.transient(parent)
        self.grab_set()

    def do_remove(self):
        try:
            project_service.remove_component_from_project(
                self.project["id"], self.component.id
            )
            self.result = True
            self.destroy()
        except Exception as e:
            log_error(e)
            messagebox.showerror("失败", f"移除失败：{e}")


# ==================== 批量加入项目（文本导入模式）====================

BATCH_ADD_RULE = """批量加入项目 · 输入规则
----------------------------------------
每行一个元件，可选用量写在后面：
    C192893              → 用量默认 1
    SL2.1A   2           → 用量 2
    0.1uF 0603 x3        → 用量 3
    SOP-16 12MHz *2      → 用量 2
    100nF 4个            → 用量 4

匹配顺序：立创编号 → 精确型号 → 通用描述 → 多关键词模糊
以 # 开头的行是注释，自动忽略。
空行自动忽略。

示例：
# --- 拓展坞 ---
C192893
SL2.1A   2
0.1uF 0603 x3
SOP-16 12MHz
"""


class BatchAddToProjectDialog(tk.Toplevel):
    """
    批量把元件加入项目（文本导入模式）。
    用户粘贴或导入一份文本清单，每行一个元件标识 [+ 可选用量]。
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.result = False

        theme = THEMES[parent.current_theme]
        self.theme = theme
        self.configure(bg=theme["bg_main"])
        self.title("批量加入项目")
        self.geometry("740x660")
        self.resizable(True, True)

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
        style.configure('TCombobox',
                        fieldbackground=theme["bg_input"],
                        foreground=theme["fg_text"])

        # ---------- 顶部：目标项目 + 快捷按钮 ----------
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=15, pady=(15, 4))
        ttk.Label(top, text="目标项目：").pack(side=tk.LEFT)
        self.project_var = tk.StringVar()
        try:
            projects = project_service.list_all_projects()
        except Exception:
            projects = []
        self.project_combo = ttk.Combobox(
            top, textvariable=self.project_var,
            values=[p["name"] for p in projects],
            width=24
        )
        self.project_combo.pack(side=tk.LEFT, padx=5)
        self.project_combo.focus_set()

        ttk.Button(top, text="📂 从文件导入", command=self.import_from_file).pack(side=tk.LEFT, padx=(10, 3))
        ttk.Button(top, text="📋 从剪贴板填充", command=self.fill_from_clipboard).pack(side=tk.LEFT, padx=3)
        ttk.Button(top, text="🤖 AI 提示词", command=self.copy_ai_prompt).pack(side=tk.LEFT, padx=3)

        ttk.Label(
            self,
            text="提示：项目名可直接输入新名字，会自动创建。下方粘贴或导入清单。",
            foreground=theme["fg_text"]
        ).pack(anchor="w", padx=15, pady=(0, 6))

        # ---------- 中部：规则说明 ----------
        rule_frame = ttk.Frame(self)
        rule_frame.pack(fill=tk.X, padx=15, pady=(0, 4))
        ttk.Label(rule_frame, text="输入格式：", font=("TkDefaultFont", 9, "bold")).pack(anchor="w")
        rule_lbl = tk.Label(
            rule_frame,
            text=BATCH_ADD_RULE,
            bg=theme["bg_input"],
            fg=theme["fg_text"],
            justify=tk.LEFT,
            anchor="nw",
            padx=8, pady=6,
        )
        rule_lbl.pack(fill=tk.X, pady=(2, 0))

        # ---------- 中部：文本框 ----------
        text_frame = ttk.Frame(self)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(6, 4))

        self.text = tk.Text(
            text_frame,
            height=14,
            bg=theme["bg_input"], fg=theme["fg_text"],
            insertbackground=theme["fg_text"],
            wrap="none",
        )
        vsb = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text.yview)
        self.text.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ---------- 底部：默认备注 + 按钮 ----------
        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X, padx=15, pady=(4, 15))

        row1 = ttk.Frame(bottom)
        row1.pack(fill=tk.X, pady=3)
        ttk.Label(row1, text="默认备注：").pack(side=tk.LEFT)
        self.note_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.note_var, width=32).pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="（可选，会写入每条关联）").pack(side=tk.LEFT)

        row2 = ttk.Frame(bottom)
        row2.pack(fill=tk.X, pady=(8, 0))

        self.status_var = tk.StringVar(value="")
        ttk.Label(row2, textvariable=self.status_var).pack(side=tk.LEFT)

        ttk.Button(row2, text="取消", command=self.destroy).pack(side=tk.RIGHT, padx=4)
        ttk.Button(row2, text="加入", command=self.save).pack(side=tk.RIGHT, padx=4)

        self.transient(parent)
        self.grab_set()

    # ---------------- 文本获取 ----------------
    def fill_from_clipboard(self):
        try:
            raw = self.clipboard_get()
        except Exception:
            messagebox.showwarning("提示", "剪贴板是空的")
            return
        if not raw or not raw.strip():
            messagebox.showwarning("提示", "剪贴板是空的")
            return
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", raw)

    def import_from_file(self):
        path = filedialog.askopenfilename(
            title="选择文本文件",
            filetypes=[
                ("文本文件", "*.txt *.md *.log *.csv *.json"),
                ("所有文件", "*.*"),
            ],
        )
        if not path:
            return
        try:
            with open(path, 'rb') as f:
                raw = f.read()
            if raw.startswith(b'\xff\xfe'):
                enc = 'utf-16-le'
            elif raw.startswith(b'\xfe\xff'):
                enc = 'utf-16-be'
            elif raw.startswith(b'\xef\xbb\xbf'):
                enc = 'utf-8-sig'
            else:
                try:
                    raw.decode('utf-8')
                    enc = 'utf-8'
                except UnicodeDecodeError:
                    enc = 'gbk'
            content = raw.decode(enc, errors='replace')
            self.text.delete("1.0", tk.END)
            self.text.insert("1.0", content)
        except Exception as e:
            log_error(e)
            messagebox.showerror("读取失败", str(e))

    # ---------------- AI 提示词（可选附加本地文档） ----------------
    def copy_ai_prompt(self):
        """
        三选一：
          是   → 选本地文档 → 提示词 + 文档内容 一起复制
          否   → 只复制提示词
          取消 → 什么都不做
        """
        prompt = (
            "请帮我整理出一份元件清单，用于导入到元件库项目。\n\n"
            "输出格式要求（每行一个元件，纯文本，不要用 markdown 代码块）：\n"
            "  1. 每行写一个元件标识（可以是立创编号 / 精确型号 / 通用描述）\n"
            "  2. 用量写在标识后面，用空格 + 数字，如：\n"
            "         C192893 2\n"
            "         SL2.1A 1\n"
            "         0.1uF 0603 4\n"
            "  3. 以 # 开头的行是注释，会被忽略\n"
            "  4. 不要写额外的说明文字，只输出清单\n\n"
            "下面是我的需求：\n"
            "【在此粘贴你要的元件，或描述你的电路】\n"
        )

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

        # 组装最终文本
        if filepath:
            try:
                with open(filepath, 'rb') as f:
                    raw = f.read()
                if raw.startswith(b'\xff\xfe'):
                    enc = 'utf-16-le'
                elif raw.startswith(b'\xfe\xff'):
                    enc = 'utf-16-be'
                elif raw.startswith(b'\xef\xbb\xbf'):
                    enc = 'utf-8-sig'
                else:
                    try:
                        raw.decode('utf-8')
                        enc = 'utf-8'
                    except UnicodeDecodeError:
                        enc = 'gbk'
                content = raw.decode(enc, errors='replace').strip()
            except Exception as e:
                log_error(e)
                messagebox.showerror("读取失败", f"读取文档时出错：\n{e}")
                return

            final_text = (
                prompt
                + "\n"
                + "=" * 60
                + "\n【以下是需要处理的原始信息】\n"
                + "=" * 60
                + "\n"
                + content
                + "\n"
                + "=" * 60
                + "\n"
            )
        else:
            final_text = prompt

        try:
            self.clipboard_clear()
            self.clipboard_append(final_text)

            if filepath:
                fname = os.path.basename(filepath)
                messagebox.showinfo(
                    "已复制",
                    "提示词 + 文档内容已复制到剪贴板。\n\n"
                    f"文档：{fname}\n"
                    f"总长度：{len(final_text)} 字符\n\n"
                    "直接粘到 AI 对话框即可。"
                )
            else:
                messagebox.showinfo(
                    "已复制",
                    "AI 提示词已复制到剪贴板。\n\n"
                    "把它发给 AI，让 AI 按格式输出元件清单，\n"
                    "然后把清单粘回本窗口的文本框即可。"
                )
        except Exception as e:
            log_error(e)
            messagebox.showerror("复制失败", str(e))

    # ---------------- 解析 ----------------
    @staticmethod
    def _parse_lines(raw_text):
        """
        逐行解析，返回 [(identifier, quantity), ...]
        - 忽略空行 / # 注释
        - 支持数量写法：末尾数字、"x3"、"*3"、"3个"
        """
        import re as _re
        items = []
        for raw_line in raw_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue

            qty = 1
            ident = line

            # x3 / *3 / ×3
            m = _re.search(r'[x*×]\s*(\d+)\s*$', ident)
            if not m:
                # 3个
                m = _re.search(r'(\d+)\s*个\s*$', ident)
            if m:
                try:
                    qty = max(1, int(m.group(1)))
                except ValueError:
                    qty = 1
                ident = ident[:m.start()].strip()
            else:
                # 末尾裸数字（空格 / 逗号分隔）
                m2 = _re.search(r'(?:[\s,，]+)(\d+)\s*$', ident)
                if m2:
                    try:
                        qty = max(1, int(m2.group(1)))
                    except ValueError:
                        qty = 1
                    ident = ident[:m2.start()].strip()

            if not ident:
                continue
            items.append((ident, qty))
        return items

    # ---------------- 执行 ----------------
    def save(self):
        name = self.project_var.get().strip()
        if not name:
            messagebox.showwarning("提示", "请选择或输入项目名")
            return

        raw_text = self.text.get("1.0", tk.END).strip()
        if not raw_text:
            messagebox.showwarning("提示", "请粘贴或导入元件清单")
            return

        items = self._parse_lines(raw_text)
        if not items:
            messagebox.showwarning("提示", "没有解析到任何有效元件")
            return

        note = self.note_var.get().strip()

        try:
            proj = project_service.get_project_by_name(name)
            if not proj:
                pid = project_service.create_project(name, "")
            else:
                pid = proj["id"]

            success = 0
            failures = []
            total_lines = len(items)

            for ident, qty in items:
                comp = component_service.find_component_by_identifier(ident)
                if comp is None:
                    failures.append(f"未匹配到：{ident}")
                    continue
                try:
                    project_service.add_component_to_project(pid, comp.id, qty, note)
                    success += 1
                except Exception as e:
                    failures.append(f"{ident}: {e}")

            msg = f"项目「{name}」：\n\n成功加入 {success} / {total_lines} 个元件"
            if failures:
                msg += f"\n\n失败 {len(failures)} 条（前 20 条）：\n"
                msg += "\n".join(failures[:20])
                if len(failures) > 20:
                    msg += f"\n... 还有 {len(failures) - 20} 条"

            messagebox.showinfo("批量加入完成", msg)
            self.result = True
            self.destroy()
        except Exception as e:
            log_error(e)
            messagebox.showerror("失败", str(e))