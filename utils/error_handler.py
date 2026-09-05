"""
错误处理辅助模块
提供统一异常捕获、日志记录和用户提示。
"""
import logging
import traceback
from tkinter import messagebox

# 配置日志：错误写入 error.log 文件
logging.basicConfig(
    filename='error.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def safe_call(func, *args, **kwargs):
    """
    在 UI 事件中安全调用函数，捕获异常并弹窗提示。
    用法：safe_call(self.some_method, arg1, arg2)
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logging.error(f"错误: {e}\n{traceback.format_exc()}")
        messagebox.showerror("错误", f"操作失败：{e}")
        return None

def log_error(e):
    """记录异常到日志（供需要单独记录的场景使用）"""
    logging.error(f"异常: {e}\n{traceback.format_exc()}")