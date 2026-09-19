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
                   CREATE TABLE IF NOT EXISTS components
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       purpose
                       TEXT
                       NOT
                       NULL,
                       generic_desc
                       TEXT
                       NOT
                       NULL,
                       model
                       TEXT
                       NOT
                       NULL,
                       package
                       TEXT,
                       pin_count
                       INTEGER,
                       key_params
                       TEXT,
                       pin_notes
                       TEXT,
                       lcsc_id
                       TEXT,
                       buy_link
                       TEXT,
                       current_price
                       REAL,
                       supplier
                       TEXT,
                       status
                       TEXT
                       DEFAULT
                       '未验证',
                       created_at
                       TEXT
                       DEFAULT (
                       datetime
                   (
                       'now',
                       'localtime'
                   )),
                       updated_at TEXT DEFAULT
                   (
                       datetime
                   (
                       'now',
                       'localtime'
                   )),
                       price_updated_at TEXT DEFAULT
                   (
                       datetime
                   (
                       'now',
                       'localtime'
                   ))
                       )
                   """)

    # 兼容旧库：补 price_updated_at
    cursor.execute("PRAGMA table_info(components)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'price_updated_at' not in columns:
        cursor.execute("ALTER TABLE components ADD COLUMN price_updated_at TEXT")
        cursor.execute("UPDATE components SET price_updated_at = created_at WHERE price_updated_at IS NULL")

    # ============ 复习日志表 ============
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS review_log
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       component_id
                       INTEGER
                       NOT
                       NULL,
                       reviewed_at
                       TEXT,
                       result
                       TEXT,
                       next_review_at
                       TEXT,
                       FOREIGN
                       KEY
                   (
                       component_id
                   ) REFERENCES components
                   (
                       id
                   )
                       )
                   """)

    # ============ 价格历史表 ============
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS price_history
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       component_id
                       INTEGER
                       NOT
                       NULL,
                       price
                       REAL,
                       supplier
                       TEXT,
                       recorded_at
                       TEXT
                       DEFAULT (
                       datetime
                   (
                       'now',
                       'localtime'
                   )),
                       FOREIGN KEY
                   (
                       component_id
                   ) REFERENCES components
                   (
                       id
                   )
                       )
                   """)

    # ============ 供应商表 ============
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS suppliers
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       name
                       TEXT
                       UNIQUE,
                       rating
                       INTEGER
                       DEFAULT
                       0,
                       notes
                       TEXT
                   )
                   """)

    # ============ 封装库表 ============
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS footprints
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       name
                       TEXT
                       NOT
                       NULL
                       UNIQUE,
                       display
                       TEXT,
                       category
                       TEXT,
                       pins
                       INTEGER
                       DEFAULT
                       0,
                       tags
                       TEXT,
                       note
                       TEXT,
                       is_builtin
                       INTEGER
                       DEFAULT
                       0,
                       created_at
                       TEXT
                       DEFAULT (
                       datetime
                   (
                       'now',
                       'localtime'
                   )),
                       updated_at TEXT DEFAULT
                   (
                       datetime
                   (
                       'now',
                       'localtime'
                   ))
                       )
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
                    cursor.execute("""
                                   INSERT
                                   OR IGNORE INTO footprints
                            (name, display, category, pins, tags, note, is_builtin)
                            VALUES (?, ?, ?, ?, ?, ?, 1)
                                   """, (
                                       fp["name"],
                                       fp.get("display", ""),
                                       fp.get("category", ""),
                                       fp.get("pins", 0),
                                       tags,
                                       fp.get("note", ""),
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