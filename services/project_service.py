# -*- coding: utf-8 -*-
"""
项目服务层：管理项目及项目-元件关联。
与元件表 components 完全独立，互不污染。
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from database.schema import get_connection


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ==================== 项目 CRUD ====================

def create_project(name: str, description: str = "") -> int:
    """创建项目，返回新项目 id；重名抛 ValueError"""
    name = (name or "").strip()
    if not name:
        raise ValueError("项目名不能为空")
    existing = get_project_by_name(name)
    if existing:
        raise ValueError(f"项目已存在：{name}")
    conn = get_connection()
    cursor = conn.cursor()
    now = _now_str()
    cursor.execute("""
        INSERT INTO projects (name, description, created_at, updated_at)
        VALUES (?, ?, ?, ?)
    """, (name, description.strip(), now, now))
    conn.commit()
    project_id = cursor.lastrowid
    conn.close()
    return project_id


def get_project_by_id(project_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    if row:
        return dict(zip(columns, row))
    return None


def get_project_by_name(name: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE name = ?", (name.strip(),))
    row = cursor.fetchone()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    if row:
        return dict(zip(columns, row))
    return None


def list_all_projects() -> List[Dict[str, Any]]:
    """列出所有项目，带元件数量统计"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.name, p.description,
               p.created_at, p.updated_at,
               COALESCE(COUNT(pi.id), 0) AS item_count
        FROM projects p
        LEFT JOIN project_items pi ON pi.project_id = p.id
        GROUP BY p.id
        ORDER BY p.name ASC
    """)
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    return [dict(zip(columns, row)) for row in rows]


def update_project(project_id: int, **kwargs) -> None:
    allowed = ["name", "description"]
    updates = []
    values = []
    for k, v in kwargs.items():
        if k in allowed:
            updates.append(f"{k} = ?")
            values.append(v)
    if not updates:
        return
    updates.append("updated_at = ?")
    values.append(_now_str())
    values.append(project_id)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE projects SET {', '.join(updates)} WHERE id = ?", values)
    conn.commit()
    conn.close()


def delete_project(project_id: int) -> None:
    """删除项目，级联清掉关联（components 表不受影响）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()


# ==================== 项目-元件关联 ====================

def add_component_to_project(project_id: int, component_id: int,
                             quantity: int = 1, note: str = "") -> None:
    """把元件加入项目；已存在则覆盖用量/备注"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO project_items (project_id, component_id, quantity, note)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(project_id, component_id)
        DO UPDATE SET quantity = excluded.quantity, note = excluded.note
    """, (project_id, component_id, quantity, note))
    conn.commit()
    conn.close()


def remove_component_from_project(project_id: int, component_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM project_items WHERE project_id = ? AND component_id = ?",
        (project_id, component_id)
    )
    conn.commit()
    conn.close()


def update_project_item(project_id: int, component_id: int, **kwargs) -> None:
    allowed = ["quantity", "note"]
    updates = []
    values = []
    for k, v in kwargs.items():
        if k in allowed:
            updates.append(f"{k} = ?")
            values.append(v)
    if not updates:
        return
    values.extend([project_id, component_id])
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE project_items SET {', '.join(updates)} "
        f"WHERE project_id = ? AND component_id = ?",
        values
    )
    conn.commit()
    conn.close()


def list_project_items(project_id: int) -> List[Dict[str, Any]]:
    """列出项目下所有元件，带用量/备注"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT pi.id AS item_id, pi.quantity, pi.note AS item_note, pi.added_at,
               c.*
        FROM project_items pi
        JOIN components c ON c.id = pi.component_id
        WHERE pi.project_id = ?
        ORDER BY c.id DESC
    """, (project_id,))
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    return [dict(zip(columns, row)) for row in rows]


def search_components_in_project(project_id: Optional[int],
                                 keyword: str = "") -> List[Dict[str, Any]]:
    """
    在项目内搜索元件。
    project_id=None 时返回所有元件（相当于"全部"）。
    返回统一结构的 dict 列表。
    """
    conn = get_connection()
    cursor = conn.cursor()

    if project_id is None:
        sql = """
        SELECT id, purpose, generic_desc, model, package, pin_count, key_params,
               pin_notes, voltage, current, power, lcsc_id, buy_link,
               current_price, supplier, status, created_at, updated_at,
               price_updated_at
        FROM components
        """
        params = []
        if keyword:
            keywords = [k.strip() for k in keyword.split() if k.strip()]
            where_parts = []
            for kw in keywords:
                like = f"%{kw}%"
                where_parts.append(
                    "(purpose LIKE ? OR generic_desc LIKE ? OR model LIKE ? OR package LIKE ? "
                    "OR lcsc_id LIKE ? OR key_params LIKE ? OR pin_notes LIKE ? OR supplier LIKE ? "
                    "OR voltage LIKE ? OR current LIKE ? OR power LIKE ?)"
                )
                params.extend([like] * 11)
            if where_parts:
                sql += " WHERE " + " AND ".join(where_parts)
        sql += " ORDER BY id DESC"
        cursor.execute(sql, params)
    else:
        sql = """
        SELECT pi.id AS item_id, pi.quantity, pi.note AS item_note, pi.added_at,
               c.id, c.purpose, c.generic_desc, c.model, c.package, c.pin_count,
               c.key_params, c.pin_notes, c.voltage, c.current, c.power,
               c.lcsc_id, c.buy_link, c.current_price, c.supplier, c.status,
               c.created_at, c.updated_at, c.price_updated_at
        FROM project_items pi
        JOIN components c ON c.id = pi.component_id
        WHERE pi.project_id = ?
        """
        params = [project_id]
        if keyword:
            keywords = [k.strip() for k in keyword.split() if k.strip()]
            for kw in keywords:
                like = f"%{kw}%"
                sql += (
                    " AND (c.purpose LIKE ? OR c.generic_desc LIKE ? OR c.model LIKE ? "
                    "OR c.package LIKE ? OR c.lcsc_id LIKE ? OR c.key_params LIKE ? "
                    "OR c.pin_notes LIKE ? OR c.supplier LIKE ? "
                    "OR c.voltage LIKE ? OR c.current LIKE ? OR c.power LIKE ?)"
                )
                params.extend([like] * 11)
        sql += " ORDER BY c.id DESC"
        cursor.execute(sql, params)

    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    return [dict(zip(columns, row)) for row in rows]


def list_projects_of_component(component_id: int) -> List[Dict[str, Any]]:
    """反查：某个元件属于哪些项目"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.name, pi.quantity, pi.note
        FROM project_items pi
        JOIN projects p ON p.id = pi.project_id
        WHERE pi.component_id = ?
        ORDER BY p.name
    """, (component_id,))
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    return [dict(zip(columns, row)) for row in rows]