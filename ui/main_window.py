import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser
import os
import csv
import json
import io
from services import component_service
from models.component import Component
from utils.constants import THEMES, DEFAULT_THEME
from utils.error_handler import safe_call, log_error


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("精料库 - 元件库管理系统")
        self.geometry("1100x500")
        self.minsize(800, 400)

        self.current_theme = DEFAULT_THEME
        self.style = ttk.Style(self)
        self.style.theme_use('clam')

        self.current_components = []

        # 页面状态
        self.last_footprint_query = ""     # 记住上次封装搜索词
        self.footprint_view = None         # 封装速查页面（懒加载）

        # ===== 主界面容器 =====
        self.main_view = ttk.Frame(self)
        self.main_view.pack(fill=tk.BOTH, expand=True)

        # ===== 搜索区域 =====
        search_frame = ttk.Frame(self.main_view)
        search_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Label(search_frame, text="搜索：").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(search_frame, text="查询", command=self.refresh_table).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="显示全部", command=self.show_all).pack(side=tk.LEFT, padx=5)

        # 主题切换下拉框
        ttk.Label(search_frame, text="主题：").pack(side=tk.LEFT, padx=(20, 5))
        self.theme_var = tk.StringVar(value=self.current_theme)
        theme_combo = ttk.Combobox(search_frame, textvariable=self.theme_var,
                                   values=list(THEMES.keys()), state="readonly", width=12)
        theme_combo.pack(side=tk.LEFT, padx=5)
        theme_combo.bind("<<ComboboxSelected>>", self.on_theme_change)

        # ===== 表格区域 =====
        table_frame = ttk.Frame(self.main_view)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("purpose", "model", "package", "lcsc_id", "current_price", "buy_link", "status")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")

        self.tree.heading("purpose", text="用途")
        self.tree.heading("model", text="型号")
        self.tree.heading("package", text="封装")
        self.tree.heading("lcsc_id", text="立创编号")
        self.tree.heading("current_price", text="价格")
        self.tree.heading("buy_link", text="购买链接")
        self.tree.heading("status", text="状态")

        self.tree.column("purpose", width=100)
        self.tree.column("model", width=120)
        self.tree.column("package", width=80)
        self.tree.column("lcsc_id", width=100)
        self.tree.column("current_price", width=60)
        self.tree.column("buy_link", width=250)
        self.tree.column("status", width=60)

        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # 创建右键菜单
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="修改购买链接", command=self.edit_buy_link)
        self.context_menu.add_command(label="修改价格", command=self.edit_price)
        self.tree.bind("<Button-3>", self.show_context_menu)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ===== 按钮区域 =====
        button_frame = ttk.Frame(self.main_view)
        button_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

        ttk.Button(button_frame, text="添加元件", command=self.add_component).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="编辑选中", command=self.edit_component).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="删除选中", command=self.delete_component).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="封装速查", command=self.open_footprint_search).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="参数匹配", command=self.open_match_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="批量更新价格", command=self.open_batch_price_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="导出数据", command=self.export_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="价格校准", command=self.show_price_outdated).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="刷新", command=self.refresh_table).pack(side=tk.LEFT, padx=5)

        self.apply_theme(self.current_theme)

    # ==================== 页面切换 ====================
    def show_main_view(self):
        """切回主界面"""
        if self.footprint_view is not None:
            self.footprint_view.pack_forget()
        self.main_view.pack(fill=tk.BOTH, expand=True)

    def show_footprint_view(self):
        """切到封装速查页面"""
        self.main_view.pack_forget()
        if self.footprint_view is None:
            from ui.footprint_search_dialog import FootprintSearchView
            self.footprint_view = FootprintSearchView(self)
        self.footprint_view.pack(fill=tk.BOTH, expand=True)

    def get_selected_component(self):
        """取主界面当前选中的元件对象，给封装速查用"""
        sel = self.tree.selection()
        if not sel:
            return None
        values = self.tree.item(sel[0], "values")
        if len(values) < 4:
            return None
        lcsc_id = values[3]
        model = values[1]
        if lcsc_id:
            comp = component_service.get_component_by_lcsc_id(lcsc_id)
            if comp:
                return comp
        if model:
            return component_service.get_component_by_model(model)
        return None

    # ==================== 右键菜单 ====================
    def show_context_menu(self, event):
        """右键时自动选中鼠标所在行，并弹出菜单"""
        row_id = self.tree.identify_row(event.y)
        if row_id:
            self.tree.selection_set(row_id)
        selected = self.tree.selection()
        if not selected:
            return
        self.context_menu.post(event.x_root, event.y_root)

    def edit_buy_link(self):
        """快速修改选中元件的购买链接"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选中一行")
            return
        values = self.tree.item(selected[0], "values")
        if len(values) > 5:
            lcsc_id = values[3]
            comp = component_service.get_component_by_lcsc_id(lcsc_id)
            if not comp:
                messagebox.showerror("错误", "未找到该元件")
                return
            dialog = SimpleInputDialog(
                self,
                title="修改购买链接",
                prompt=f"元件：{comp.model}\n请输入新的购买链接：",
                initial_value=comp.buy_link
            )
            self.wait_window(dialog)
            new_link = dialog.result
            if new_link is not None:
                try:
                    component_service.update_component(comp.id, buy_link=new_link.strip())
                    self.refresh_table()
                    messagebox.showinfo("成功", "购买链接已更新")
                except Exception as e:
                    log_error(e)
                    messagebox.showerror("更新失败", f"更新购买链接时出错：{e}")
        else:
            messagebox.showwarning("提示", "数据不完整")

    def edit_price(self):
        """快速修改选中元件的价格"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选中一行")
            return
        values = self.tree.item(selected[0], "values")
        if len(values) > 3:
            lcsc_id = values[3]
            comp = component_service.get_component_by_lcsc_id(lcsc_id)
            if not comp:
                messagebox.showerror("错误", "未找到该元件")
                return
            dialog = SimpleInputDialog(
                self,
                title="修改价格",
                prompt=f"元件：{comp.model}\n请输入新的价格：",
                initial_value=str(comp.current_price) if comp.current_price else ""
            )
            self.wait_window(dialog)
            new_price_str = dialog.result
            if new_price_str is not None:
                try:
                    price = float(new_price_str.strip())
                    if price < 0:
                        raise ValueError
                    component_service.update_component(comp.id, current_price=price)
                    self.refresh_table()
                    messagebox.showinfo("成功", "价格已更新")
                except ValueError:
                    messagebox.showerror("错误", "请输入有效的正数价格")
                except Exception as e:
                    log_error(e)
                    messagebox.showerror("更新失败", f"更新价格时出错：{e}")
        else:
            messagebox.showwarning("提示", "数据不完整")

    # ==================== 弹窗入口 ====================
    def open_match_dialog(self):
        MatchDialog(self)

    def open_footprint_search(self):
        self.show_footprint_view()

    def open_batch_price_dialog(self):
        BatchPriceDialog(self)

    def on_tree_double_click(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0], "values")
        if len(values) > 5:
            link = values[5]
            if link and link.strip():
                webbrowser.open(link)

    def apply_theme(self, theme_name):
        theme = THEMES[theme_name]
        self.current_theme = theme_name
        self.configure(bg=theme["bg_main"])
        self.style.configure('TLabel', background=theme["bg_main"], foreground=theme["fg_text"])
        self.style.configure('TFrame', background=theme["bg_main"])
        self.style.configure('TButton', background=theme["bg_button"], foreground=theme["fg_text"],
                             bordercolor=theme["border"])
        self.style.map('TButton',
                       background=[('active', theme["bg_button_hover"]), ('pressed', theme["bg_main"])],
                       foreground=[('active', theme["fg_white"])])
        self.style.configure('Treeview',
                             background=theme["bg_table"],
                             foreground=theme["fg_text"],
                             fieldbackground=theme["bg_table"],
                             bordercolor=theme["border"],
                             lightcolor=theme["bg_table"],
                             darkcolor=theme["bg_table"])
        self.style.configure('Treeview.Heading',
                             background=theme["bg_heading"],
                             foreground=theme["fg_text"],
                             relief='flat')
        self.style.map('Treeview',
                       background=[('selected', theme["bg_select"])],
                       foreground=[('selected', theme["fg_white"])])
        self.style.configure('TEntry',
                             fieldbackground=theme["bg_input"],
                             foreground=theme["fg_text"],
                             insertcolor=theme["fg_text"])
        self.refresh_table()

    def on_theme_change(self, event=None):
        selected_theme = self.theme_var.get()
        if selected_theme in THEMES:
            self.apply_theme(selected_theme)
            # 如果封装页已经建过，重建以应用新主题
            if self.footprint_view is not None:
                was_visible = self.footprint_view.winfo_ismapped()
                self.footprint_view.destroy()
                self.footprint_view = None
                if was_visible:
                    self.show_footprint_view()

    # ==================== 数据操作 ====================
    def refresh_table(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        keyword = self.search_var.get().strip()
        if keyword:
            components = component_service.search_components_multi(keyword)
        else:
            components = component_service.list_all_components()
        self.current_components = components
        for comp in components:
            self.tree.insert("", tk.END, values=(
                comp.purpose,
                comp.model,
                comp.package,
                comp.lcsc_id,
                comp.current_price,
                comp.buy_link,
                comp.status
            ))

    def display_components(self, components):
        self.current_components = components
        for i in self.tree.get_children():
            self.tree.delete(i)
        for comp in components:
            self.tree.insert("", tk.END, values=(
                comp.purpose,
                comp.model,
                comp.package,
                comp.lcsc_id,
                comp.current_price,
                comp.buy_link,
                comp.status
            ))

    def show_all(self):
        self.search_var.set("")
        self.refresh_table()

    def add_component(self):
        TextInputDialog(self, None)

    def edit_component(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选中一行")
            return
        values = self.tree.item(selected[0], "values")
        if len(values) > 3:
            lcsc_id = values[3]
            comp = component_service.get_component_by_lcsc_id(lcsc_id)
            if comp:
                TextInputDialog(self, comp)
            else:
                messagebox.showerror("错误", "未找到该元件")
        else:
            messagebox.showwarning("提示", "数据不完整")

    def delete_component(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选中一行")
            return
        values = self.tree.item(selected[0], "values")
        if len(values) > 3:
            lcsc_id = values[3]
            comp = component_service.get_component_by_lcsc_id(lcsc_id)
            if comp:
                if messagebox.askyesno("确认", f"确定要删除 {comp.model} 吗？"):
                    component_service.delete_component(comp.id)
                    self.refresh_table()
            else:
                messagebox.showerror("错误", "未找到该元件")
        else:
            messagebox.showwarning("提示", "数据不完整")

    # ==================== 导出数据（复制到剪贴板） ====================
    def export_data(self):
        choice = messagebox.askyesnocancel("导出数据", "选择复制格式：\n是 = CSV\n否 = JSON\n取消 = 返回")
        if choice is None:
            return
        try:
            components = component_service.list_all_components()
            if not components:
                messagebox.showwarning("提示", "没有可导出的数据")
                return

            if choice:
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["用途", "型号", "封装", "立创编号", "价格", "购买链接", "状态"])
                for comp in components:
                    writer.writerow([comp.purpose, comp.model, comp.package, comp.lcsc_id,
                                     comp.current_price, comp.buy_link, comp.status])
                text = output.getvalue()
            else:
                data = [comp.to_dict() for comp in components]
                text = json.dumps(data, ensure_ascii=False, indent=2)

            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("成功", f"已复制 {len(components)} 个元件数据到剪贴板")
        except Exception as e:
            log_error(e)
            messagebox.showerror("导出失败", f"导出过程中发生错误：{e}")

    # ==================== 价格校准 ====================
    def show_price_outdated(self):
        try:
            outdated = component_service.get_components_price_outdated(days=15)
            self.display_components(outdated)
            messagebox.showinfo("价格校准", f"找到 {len(outdated)} 个超过15天未更新价格的元件。")
        except Exception as e:
            log_error(e)
            messagebox.showerror("查询失败", f"查询价格过期元件时出错：{e}")


# ==================== 自定义中文输入对话框 ====================
class SimpleInputDialog(tk.Toplevel):
    """带有中文按钮的简单输入对话框，取代 simpledialog"""

    def __init__(self, parent, title="", prompt="", initial_value=""):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.result = None

        theme = THEMES[parent.current_theme]
        self.configure(bg=theme["bg_main"])
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TLabel', background=theme["bg_main"], foreground=theme["fg_text"])
        style.configure('TButton', background=theme["bg_button"], foreground=theme["fg_text"],
                        bordercolor=theme["border"])
        style.map('TButton',
                  background=[('active', theme["bg_button_hover"]), ('pressed', theme["bg_main"])],
                  foreground=[('active', theme["fg_white"])])
        style.configure('TEntry',
                        fieldbackground=theme["bg_input"],
                        foreground=theme["fg_text"],
                        insertcolor=theme["fg_text"])

        if prompt:
            ttk.Label(self, text=prompt, justify=tk.LEFT).pack(padx=10, pady=(10, 5))

        self.entry_var = tk.StringVar(value=initial_value)
        entry = ttk.Entry(self, textvariable=self.entry_var, width=40)
        entry.pack(padx=10, pady=5)
        entry.focus_set()

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="确定", command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self._on_cancel).pack(side=tk.LEFT, padx=5)

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

        self.transient(parent)
        self.grab_set()

    def _on_ok(self):
        self.result = self.entry_var.get()
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()


# ==================== 添加/编辑元件对话框 ====================
class TextInputDialog(tk.Toplevel):
    def __init__(self, parent, component: Component = None):
        super().__init__(parent)
        self.parent = parent
        self.component = component
        self.theme_name = parent.current_theme
        self.title("编辑元件" if component else "添加元件")
        self.geometry("600x600")
        self.resizable(False, False)

        theme = THEMES[self.theme_name]
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

        self.info_text = """元件输入格式（每行一项，用中文冒号分隔）：
用途: 例如 USB Hub 主控
通用描述: 例如 USB Hub IC
型号: 例如 SL2.1A
封装: 例如 SOP-16
引脚数: 例如 16
关键参数: 例如 VDD5=5V，12MHz晶振
特殊注意: 例如 VDD33/VDD18只接电容
立创编号: 例如 C192893
购买链接: 例如 https://...
价格: 例如 1.2
供应商: 例如 立创商城
状态: 未验证 / 已验证 / 已淘汰
（可留空，但用途、通用描述、型号建议填写）

【批量添加】多个元件请用空行分隔，每段格式同上。"""

        ttk.Label(self, text=self.info_text, justify=tk.LEFT).pack(padx=10, pady=(10, 5))

        self.text = tk.Text(self, height=12, bg=theme["bg_input"], fg=theme["fg_text"],
                            insertbackground=theme["fg_text"])
        self.text.pack(fill=tk.BOTH, padx=10, pady=(0, 5))

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        inner_btn_frame = ttk.Frame(btn_frame)
        inner_btn_frame.pack(anchor='center')

        save_text = "保存修改" if component else "添加元件"
        ttk.Button(inner_btn_frame, text=save_text, command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(inner_btn_frame, text="导出规则", command=self.export_rule).pack(side=tk.LEFT, padx=5)
        ttk.Button(inner_btn_frame, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=5)

        if component:
            data = component.to_dict()
            lines = []
            field_names = {
                "purpose": "用途", "generic_desc": "通用描述", "model": "型号",
                "package": "封装", "pin_count": "引脚数", "key_params": "关键参数",
                "pin_notes": "特殊注意", "lcsc_id": "立创编号", "buy_link": "购买链接",
                "current_price": "价格", "supplier": "供应商", "status": "状态"
            }
            for field, label in field_names.items():
                value = data.get(field, "")
                if value:
                    lines.append(f"{label}: {value}")
                else:
                    lines.append(f"{label}: ")
            self.text.insert("1.0", "\n".join(lines))

    def validate_text_format(self, raw_text):
        errors = []
        for i, line in enumerate(raw_text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            if ":" not in line and "：" not in line:
                errors.append(f"第 {i} 行缺少冒号: {line}")
        return errors

    def export_rule(self):
        self.clipboard_clear()
        self.clipboard_append(self.info_text)
        messagebox.showinfo("提示", "输入规则已复制到剪贴板，可粘贴给AI生成符合格式的文本")

    def _parse_and_validate_block(self, block: str) -> dict:
        errors = self.validate_text_format(block)
        if errors:
            raise ValueError("格式错误：\n" + "\n".join(errors))

        data = {}
        field_map = {
            "用途": "purpose", "通用描述": "generic_desc", "型号": "model",
            "封装": "package", "引脚数": "pin_count", "关键参数": "key_params",
            "特殊注意": "pin_notes", "立创编号": "lcsc_id", "购买链接": "buy_link",
            "价格": "current_price", "供应商": "supplier", "状态": "status"
        }
        for line in block.splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" in line or "：" in line:
                if ":" in line:
                    key, value = line.split(":", 1)
                else:
                    key, value = line.split("：", 1)
                key = key.strip()
                value = value.strip()
                if key in field_map:
                    data[field_map[key]] = value

        try:
            if data.get("pin_count"):
                data["pin_count"] = int(data["pin_count"])
            else:
                data["pin_count"] = 0
            if data.get("current_price"):
                data["current_price"] = float(data["current_price"])
            else:
                data["current_price"] = 0.0
        except ValueError:
            raise ValueError("引脚数必须是整数，价格必须是数字")

        if not data.get("purpose") or not data.get("model"):
            raise ValueError("用途和型号不能为空")

        return data

    def _check_duplicate(self, data: dict):
        existing = None
        lcsc_id = data.get("lcsc_id", "").strip()
        model = data.get("model", "").strip()
        if lcsc_id:
            existing = component_service.get_component_by_lcsc_id(lcsc_id)
        if existing is None and model:
            existing = component_service.get_component_by_model(model)
        if existing:
            raise ValueError(f"重复：元件已存在 {existing.model} (立创编号: {existing.lcsc_id})")

    def _save_single_block(self, block: str):
        data = self._parse_and_validate_block(block)

        if self.component is None:
            self._check_duplicate(data)
            comp = Component(**data)
            component_service.add_component(comp)
        else:
            component_service.update_component(self.component.id, **data)

    def save(self):
        raw_text = self.text.get("1.0", tk.END).strip()
        blocks = [b.strip() for b in raw_text.split('\n\n') if b.strip()]

        if self.component is not None and len(blocks) > 1:
            messagebox.showerror("错误", "编辑模式下只允许一个元件")
            return

        if len(blocks) > 1:
            success_count = 0
            failures = []
            for i, block in enumerate(blocks, 1):
                try:
                    self._save_single_block(block)
                    success_count += 1
                except Exception as e:
                    failures.append(f"第 {i} 个元件失败: {e}")
            self.parent.refresh_table()
            if failures:
                messagebox.showwarning("批量添加结果",
                                       f"成功 {success_count} 个，失败 {len(failures)} 个\n\n" + "\n".join(failures))
            else:
                messagebox.showinfo("批量添加结果", f"成功添加 {success_count} 个元件")
            self.destroy()
            return

        try:
            self._save_single_block(raw_text)
            self.parent.refresh_table()
            self.destroy()
        except Exception as e:
            messagebox.showerror("保存失败", str(e))


# ==================== 参数匹配对话框 ====================
class MatchDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("参数匹配")
        self.geometry("600x550")
        self.resizable(False, False)

        theme = THEMES[self.parent.current_theme]
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

        self.rule_text = """参数匹配输入规则：
支持批量输入多个硬件描述，每行一个硬件。
每行的格式可以是以下任意一种：
1. 立创编号：直接输入，如 C192893
2. 精确型号：直接输入型号，如 SL2.1A
3. 通用描述：直接输入，如 0.1uF 0603
4. 多关键词组合：用空格分隔多个关键词，如 SOP-16 12MHz
系统会按照优先级自动识别并匹配：先精确匹配立创编号，再匹配型号，然后通用描述，最后模糊匹配关键词。
示例输入：
C192893
SL2.1A
0.1uF 0603
SOP-16 12MHz
"""

        ttk.Label(self, text=self.rule_text, justify=tk.LEFT).pack(padx=10, pady=10)
        self.text = tk.Text(self, height=8, bg=theme["bg_input"], fg=theme["fg_text"],
                            insertbackground=theme["fg_text"])
        self.text.pack(fill=tk.BOTH, padx=10, pady=5)

        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        inner_btn_frame = ttk.Frame(button_frame)
        inner_btn_frame.pack(anchor='center')
        ttk.Button(inner_btn_frame, text="执行匹配", command=self.execute_match).pack(side=tk.LEFT, padx=5)
        ttk.Button(inner_btn_frame, text="导出结果", command=self.export_results).pack(side=tk.LEFT, padx=5)
        ttk.Button(inner_btn_frame, text="导出规则", command=self.export_rule).pack(side=tk.LEFT, padx=5)
        ttk.Button(inner_btn_frame, text="关闭", command=self.destroy).pack(side=tk.LEFT, padx=5)

        self.matched_components = []

    def execute_match(self):
        text = self.text.get("1.0", tk.END).strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        self.matched_components = []
        for line in lines:
            comp = None
            if line.upper().startswith("C") and line[1:].isdigit():
                comp = component_service.get_component_by_lcsc_id(line)
            if comp is None:
                comp = component_service.get_component_by_model(line)
            if comp is None:
                comp = component_service.get_component_by_generic_desc(line)
            if comp is None:
                candidates = component_service.search_components_multi(line)
                if candidates:
                    comp = candidates[0]
            if comp:
                self.matched_components.append(comp)
        self.parent.display_components(self.matched_components)
        messagebox.showinfo("提示", f"匹配到 {len(self.matched_components)} 个元件")

    def export_results(self):
        if not self.matched_components:
            messagebox.showwarning("提示", "没有可导出的结果")
            return
        try:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["用途", "型号", "封装", "立创编号", "价格", "购买链接", "状态"])
            for comp in self.matched_components:
                writer.writerow([comp.purpose, comp.model, comp.package, comp.lcsc_id,
                                 comp.current_price, comp.buy_link, comp.status])
            text = output.getvalue()
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("成功", f"已复制 {len(self.matched_components)} 个匹配结果到剪贴板")
        except Exception as e:
            log_error(e)
            messagebox.showerror("导出失败", f"导出匹配结果时出错：{e}")

    def export_rule(self):
        self.clipboard_clear()
        self.clipboard_append(self.rule_text)
        messagebox.showinfo("提示", "输入规则已复制到剪贴板，可粘贴给AI生成符合格式的文本")


# ==================== 批量更新价格对话框 ====================
class BatchPriceDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("批量更新价格")
        self.geometry("600x550")
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

        rule_text = """批量更新价格输入规则：
每行一个元件，格式为：元件标识 价格
元件标识可以是：
- 立创编号（如 C192893）
- 精确型号（如 SL2.1A）
- 通用描述（如 0.1uF 0603）
- 多关键词组合（如 SOP-16 12MHz）
价格用空格、Tab 或逗号与标识分隔。
示例：
C192893 1.5
SL2.1A 2.3
0.1uF 0603 0.8
"""
        ttk.Label(self, text=rule_text, justify=tk.LEFT).pack(padx=10, pady=(10, 5))

        limit_frame = ttk.Frame(self)
        limit_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        ttk.Label(limit_frame, text="最大处理行数（留空不限制）:").pack(side=tk.LEFT)
        self.limit_var = tk.StringVar()
        ttk.Entry(limit_frame, textvariable=self.limit_var, width=10).pack(side=tk.LEFT, padx=5)

        self.text = tk.Text(self, height=10, bg=theme["bg_input"], fg=theme["fg_text"],
                            insertbackground=theme["fg_text"])
        self.text.pack(fill=tk.BOTH, padx=10, pady=5)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="执行更新", command=self.execute).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="关闭", command=self.destroy).pack(side=tk.LEFT, padx=5)

    def execute(self):
        raw_text = self.text.get("1.0", tk.END).strip()
        if not raw_text:
            messagebox.showwarning("提示", "请输入内容")
            return

        limit_str = self.limit_var.get().strip()
        limit = None
        if limit_str:
            try:
                limit = int(limit_str)
                if limit <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("错误", "最大行数必须是正整数")
                return

        try:
            result = component_service.batch_update_prices_from_text(raw_text, limit)
            success = result["success"]
            failures = result["failures"]
            message = f"成功更新 {success} 个元件的价格。"
            if failures:
                message += f"\n失败 {len(failures)} 行：\n" + "\n".join(failures)
            messagebox.showinfo("更新结果", message)
            self.parent.refresh_table()
        except Exception as e:
            log_error(e)
            messagebox.showerror("更新失败", f"批量更新价格时出错：{e}")