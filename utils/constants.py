"""
全局常量配置
所有可变参数集中在这里，修改时只需要改这一个文件。
"""

import os

# ================= 数据库 =================
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_DIR = os.path.join(_BASE_DIR, "data")
DATABASE_FILENAME = "components.db"
DATABASE_PATH = os.path.join(DATABASE_DIR, DATABASE_FILENAME)

# ================= 元件状态 =================
STATUS_UNVERIFIED = "未验证"
STATUS_VERIFIED = "已验证"
STATUS_DEPRECATED = "已淘汰"

ALL_STATUSES = [
    STATUS_UNVERIFIED,
    STATUS_VERIFIED,
    STATUS_DEPRECATED,
]

# ================= 复习间隔（天） =================
REVIEW_INTERVALS = [3, 7, 15, 30, 90]
DEFAULT_FIRST_INTERVAL = 3
DEFAULT_REVIEW_RESULT_REMEMBER = "记得"
DEFAULT_REVIEW_RESULT_FORGET = "忘记"

# ================= 字段名常量 =================
FIELD_ID = "id"
FIELD_PURPOSE = "purpose"
FIELD_GENERIC_DESC = "generic_desc"
FIELD_MODEL = "model"
FIELD_PACKAGE = "package"
FIELD_PIN_COUNT = "pin_count"
FIELD_KEY_PARAMS = "key_params"
FIELD_PIN_NOTES = "pin_notes"
FIELD_LCSC_ID = "lcsc_id"
FIELD_BUY_LINK = "buy_link"
FIELD_CURRENT_PRICE = "current_price"
FIELD_SUPPLIER = "supplier"
FIELD_STATUS = "status"
FIELD_CREATED_AT = "created_at"
FIELD_UPDATED_AT = "updated_at"

# ================= AI 提示词模板 =================
AI_PROMPT_TEMPLATE = """
请分析以下元件清单，并给出优化建议：

{component_data}

请完成：
1. 价格合理性评估
2. 替代料推荐
3. 供应商评估
4. 库存优化建议

输出格式：
| 元件 | 当前价格 | 合理价区间 | 建议 |
"""

# ================= GUI 配置 =================
APP_TITLE = "元件库管理系统"
APP_VERSION = "v0.1"
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 500

# ================= 显示字段 =================
TABLE_COLUMNS = [
    FIELD_PURPOSE,
    FIELD_MODEL,
    FIELD_PACKAGE,
    FIELD_LCSC_ID,
    FIELD_CURRENT_PRICE,
    FIELD_STATUS,
]

# ================= 多主题定义 =================
THEMES = {
    "柔和深灰蓝": {
        "bg_main": "#1e1e2a",
        "bg_table": "#262635",
        "bg_heading": "#2a2a3a",
        "bg_button": "#2e2e3e",
        "bg_button_hover": "#3a3a4e",
        "bg_input": "#262635",
        "bg_select": "#3a4a6b",
        "fg_text": "#e0e0ea",
        "fg_white": "#ffffff",
        "border": "#3a3a4e",
    },
    "纯黑": {
        "bg_main": "#0d0d0d",
        "bg_table": "#141414",
        "bg_heading": "#1a1a1a",
        "bg_button": "#1f1f1f",
        "bg_button_hover": "#2a2a2a",
        "bg_input": "#141414",
        "bg_select": "#2b3a5a",
        "fg_text": "#e8e8e8",
        "fg_white": "#ffffff",
        "border": "#333333",
    },
    "浅色": {
        "bg_main": "#f0f0f0",
        "bg_table": "#ffffff",
        "bg_heading": "#e0e0e0",
        "bg_button": "#d0d0d0",
        "bg_button_hover": "#c0c0c0",
        "bg_input": "#ffffff",
        "bg_select": "#a0c0e0",
        "fg_text": "#000000",
        "fg_white": "#000000",
        "border": "#b0b0b0",
    },
}

# 默认主题
DEFAULT_THEME = "柔和深灰蓝"
THEME = THEMES[DEFAULT_THEME]