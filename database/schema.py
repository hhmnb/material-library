"""
数据库表结构定义
"""

import sqlite3
import os

from utils import constants


def get_connection():
    """获取数据库连接"""
    os.makedirs(constants.DATABASE_DIR, exist_ok=True)
    conn = sqlite3.connect(constants.DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """初始化数据库，创建所有表"""
    conn = get_connection()
    cursor = conn.cursor()

    # ============ 元件主表 ============
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS components (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purpose TEXT NOT NULL,
        generic_desc TEXT NOT NULL,
        model TEXT NOT NULL,
        package TEXT,
        pin_count INTEGER,
        key_params TEXT,
        pin_notes TEXT,
        voltage TEXT,
        current TEXT,
        power TEXT,
        lcsc_id TEXT,
        buy_link TEXT,
        current_price REAL,
        supplier TEXT,
        status TEXT DEFAULT '未验证',
        created_at TEXT DEFAULT (datetime('now', 'localtime')),
        updated_at TEXT DEFAULT (datetime('now', 'localtime')),
        price_updated_at TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """)

    # ============ 老库迁移 ============
    cursor.execute("PRAGMA table_info(components)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'price_updated_at' not in columns:
        cursor.execute("ALTER TABLE components ADD COLUMN price_updated_at TEXT")
        cursor.execute("UPDATE components SET price_updated_at = created_at WHERE price_updated_at IS NULL")
        print("✅ components 表已添加 price_updated_at 列")

    # 电气参数三剑客
    for col_name, col_type in (
        ("voltage", "TEXT"),
        ("current", "TEXT"),
        ("power", "TEXT"),
    ):
        if col_name not in columns:
            cursor.execute(f"ALTER TABLE components ADD COLUMN {col_name} {col_type}")
            print(f"✅ components 表已添加 {col_name} 列")

    # ============ 复习日志表 ============
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS review_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        component_id INTEGER NOT NULL,
        reviewed_at TEXT,
        result TEXT,
        next_review_at TEXT,
        FOREIGN KEY (component_id) REFERENCES components(id)
    )
    """)

    # ============ 价格历史表 ============
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        component_id INTEGER NOT NULL,
        price REAL,
        supplier TEXT,
        recorded_at TEXT DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (component_id) REFERENCES components(id)
    )
    """)

    # ============ 供应商表 ============
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        rating INTEGER DEFAULT 0,
        notes TEXT
    )
    """)

    # ============ 封装库表 ============
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS footprints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        display TEXT,
        category TEXT,
        pins INTEGER DEFAULT 0,
        tags TEXT,
        note TEXT,
        lcsc_ids TEXT,
        is_builtin INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now', 'localtime')),
        updated_at TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """)

    # 老库迁移：footprints 加 lcsc_ids 列
    cursor.execute("PRAGMA table_info(footprints)")
    fp_columns = [col[1] for col in cursor.fetchall()]
    if 'lcsc_ids' not in fp_columns:
        cursor.execute("ALTER TABLE footprints ADD COLUMN lcsc_ids TEXT")
        print("✅ footprints 表已添加 lcsc_ids 列")

    # ============ 项目表（与元件表完全独立）============
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now', 'localtime')),
        updated_at TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """)

    # ============ 项目-元件关联表（多对多）============
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS project_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        component_id INTEGER NOT NULL,
        quantity INTEGER DEFAULT 1,
        note TEXT DEFAULT '',
        added_at TEXT DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
        FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE,
        UNIQUE (project_id, component_id)
    )
    """)

    # 常用查询走索引
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_project_items_project
    ON project_items(project_id)
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_project_items_component
    ON project_items(component_id)
    """)

    # 首次启动导入内置封装（BUILTIN_FOOTPRINTS 为空则跳过）
    cursor.execute("SELECT COUNT(*) FROM footprints")
    if cursor.fetchone()[0] == 0:
        try:
            from utils.footprint_library import BUILTIN_FOOTPRINTS
            if BUILTIN_FOOTPRINTS:
                for fp in BUILTIN_FOOTPRINTS:
                    tags = fp.get("tags", [])
                    if isinstance(tags, list):
                        tags = ",".join(tags)
                    lcsc_ids = fp.get("lcsc_ids", "")
                    if isinstance(lcsc_ids, list):
                        lcsc_ids = ",".join(lcsc_ids)
                    cursor.execute("""
                        INSERT OR IGNORE INTO footprints
                        (name, display, category, pins, tags, note, lcsc_ids, is_builtin)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    """, (
                        fp["name"],
                        fp.get("display", ""),
                        fp.get("category", ""),
                        fp.get("pins", 0),
                        tags,
                        fp.get("note", ""),
                        lcsc_ids,
                    ))
                print(f"✅ 已导入 {len(BUILTIN_FOOTPRINTS)} 条内置封装")
            else:
                print("ℹ 未预置内置封装，请通过界面或 CSV 导入")
        except Exception as e:
            print(f"⚠ 导入内置封装失败: {e}")

    conn.commit()
    conn.close()
    print("✅ 数据库初始化完成")


if __name__ == "__main__":
    init_db()