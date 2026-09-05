from database.schema import init_db
from ui.main_window import MainWindow

if __name__ == "__main__":
    # 启动时自动创建表（如果不存在）
    init_db()
    app = MainWindow()
    app.mainloop()