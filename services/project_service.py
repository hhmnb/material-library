# -*- coding: utf-8 -*-
"""
项目服务层：管理项目及项目-元件关联。
与元件表 components 完全独立，互不污染。
"""
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from database.schema import get_connection


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _dedup_key(row: dict) -> str:
    """
    主页展示时的去重键，只认立创编号。
    - 有 lcsc_id → 按 lcsc_id 合并（保留最新一条）
    - 没有 lcsc_id → 用 id 兜底（不合并，各显示各的）
    """
    lcsc = (row.get("lcsc_id") or "").strip()
    if lcsc:
        return f"lcsc:{lcsc}"
    return f"id:{row.get('id')}"


# ==================== 智能搜索解析 ====================

# 类型词映射：用户输入 → purpose 里的关键词
_PURPOSE_WORDS = {
    "电容": "电容",
    "电阻": "电阻",
    "电感": "电感",
    "芯片": "芯片",
    "ic": "芯片",
    "连接器": "连接器",
    "接插件": "连接器",
    "端子": "连接器",
    "tvs": "TVS",
    "esd": "TVS",
    "静电": "TVS",
    "二极管": "二极管",
    "led": "LED",
    "usb": "USB",
    "typec": "USB",
    "type-c": "USB",
    "type-c": "USB",
    "晶振": "晶振",
    "晶体": "晶振",
    "保险丝": "保险丝",
    "熔断": "保险丝",
    "开关": "开关",
    "按键": "开关",
    "无线": "无线",
    "蓝牙": "无线",
    "wifi": "无线",
    "mos": "芯片",
    "mosfet": "芯片",
    "ldo": "芯片",
    "运放": "芯片",
    "电源": "芯片",
    "mcu": "芯片",
    "单片机": "芯片",
}


def _parse_search_terms(keyword_text: str) -> dict:
    """
    把搜索文本解析成多个维度。返回：
        {
            "purpose": [...],   # 用途关键词（电阻/电容/TVS...）
            "core":    [...],   # 核心值（100nF / 5.1K / 10uH / 12MHz）
            "voltage": [...],   # 电压（5V / 3.3V）
            "current": [...],   # 电流（1A / 500mA）
            "power":   [...],   # 功率（1W / 0.25W / 250mW）
            "other":   [...],   # 其它关键词（C编号 / 型号 / 供应商...）
        }
    """
    result = {
        "purpose": [],
        "core": [],
        "voltage": [],
        "current": [],
        "power": [],
        "other": [],
    }
    tokens = [t for t in keyword_text.strip().split() if t]
    if not tokens:
        return result

    for tok in tokens:
        low = tok.lower()
        is_num_start = bool(re.match(r'^\d', tok))

        # ---- 1. 类型词（优先）----
        matched_type = None
        for k, v in _PURPOSE_WORDS.items():
            if k in low:
                matched_type = v
                break
        if matched_type:
            result["purpose"].append(matched_type)
            continue

        # ---- 2. 数值型：只对以数字开头的 token 做电气参数判断 ----
        if is_num_start:
            # 2.1 电压：5V / 3.3V / 50VDC / 5V0
            if re.fullmatch(r'\d+(?:\.\d+)?[vV](?:[dD][cC])?', tok):
                v_clean = re.sub(r'[dD][cC]$', '', tok)
                result["voltage"].append(v_clean)
                continue
            m = re.fullmatch(r'(\d+)[vV](\d)', tok)
            if m:
                result["voltage"].append(f"{m.group(1)}.{m.group(2)}V")
                continue

            # 2.2 电流：1A / 500mA / 100uA
            if re.fullmatch(r'\d+(?:\.\d+)?(?:m|μ|u|M)?[aA]', tok):
                result["current"].append(tok)
                continue

            # 2.3 功率：1W / 0.25W / 250mW
            if re.fullmatch(r'\d+(?:\.\d+)?(?:m|M)?[wW]', tok):
                result["power"].append(tok)
                continue

            # 2.4 容值：100nF / 10uF / 4.7pF / 100NF
            if re.search(r'[fF]$', tok):
                result["core"].append(tok)
                continue

            # 2.5 频率：12MHz / 32.768kHz
            if re.search(r'[hH][zZ]$', tok):
                result["core"].append(tok)
                continue

            # 2.6 感值：10uH / 4.7nH（Hz 已在上面排除）
            if re.search(r'[hH]$', tok):
                result["core"].append(tok)
                continue

            # 2.7 阻值：5.1K / 5.1k / 100R / 4.7M / 10kΩ / 5.1KΩ
            if re.search(r'[kKmMrRΩ]$', tok):
                result["core"].append(tok)
                continue

            # 2.8 纯数字 + k/K/M → 也当阻值（如 5.1K）
            if re.fullmatch(r'\d+(?:\.\d+)?[kKmM]', tok):
                result["core"].append(tok)
                continue

            # 2.9 立创编号 C12345
            if re.fullmatch(r'[cC]\d+', tok):
                result["other"].append(tok)
                continue

        # ---- 3. 其它：走普通模糊搜索 ----
        result["other"].append(tok)

    return result


def _append_where(parsed: dict, where_parts: list, params: list, prefix: str = ""):
    """
    把 parsed 拼成 SQL 条件 + 参数。
    prefix: '' 或 'c.'（项目视图里表别名是 c）
    """
    if not parsed:
        return
    p = prefix

    # 1. 用途：任一命中
    if parsed["purpose"]:
        sub = "(" + " OR ".join([f"{p}purpose LIKE ?"] * len(parsed["purpose"])) + ")"
        where_parts.append(sub)
        for v in parsed["purpose"]:
            params.append(f"%{v}%")

    # 2. 核心值：在 generic_desc / model / key_params 里任一命中
    for c in parsed["core"]:
        where_parts.append(
            f"({p}generic_desc LIKE ? OR {p}model LIKE ? OR {p}key_params LIKE ?)"
        )
        like = f"%{c}%"
        params.extend([like, like, like])

    # 3. 电压
    for v in parsed["voltage"]:
        where_parts.append(f"{p}voltage LIKE ?")
        params.append(f"%{v}%")

    # 4. 电流
    for c in parsed["current"]:
        where_parts.append(f"{p}current LIKE ?")
        params.append(f"%{c}%")

    # 5. 功率
    for w in parsed["power"]:
        where_parts.append(f"{p}power LIKE ?")
        params.append(f"%{w}%")

    # 6. 其它：全字段模糊
    for kw in parsed["other"]:
        where_parts.append(
            f"({p}purpose LIKE ? OR {p}generic_desc LIKE ? OR {p}model LIKE ? "
            f"OR {p}package LIKE ? OR {p}lcsc_id LIKE ? OR {p}key_params LIKE ? "
            f"OR {p}pin_notes LIKE ? OR {p}supplier LIKE ? "
            f"OR {p}voltage LIKE ? OR {p}current LIKE ? OR {p}power LIKE ?)"
        )
        like = f"%{kw}%"
        params.extend([like] * 11)


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
    在项目内搜索元件（支持智能解析关键词）。
    - project_id=None：返回所有元件（"全部"视图），按 lcsc_id 去重
    - project_id 有值：返回该项目下的元件（原样，不去重）

    搜索示例：
        "电阻 5.1K 1W"  → 用途=电阻 AND 核心值=5.1K AND 功率=1W
        "tvs 5V"        → 用途=TVS AND 电压=5V
        "100nF"         → 核心值=100nF
        "C122969"       → 立创编号模糊匹配
    """
    conn = get_connection()
    cursor = conn.cursor()

    parsed = _parse_search_terms(keyword) if keyword else None

    if project_id is None:
        base_sql = """
        SELECT id, purpose, generic_desc, model, package, pin_count, key_params,
               pin_notes, voltage, current, power, lcsc_id, buy_link,
               current_price, supplier, status, created_at, updated_at,
               price_updated_at
        FROM components
        """
        where_parts = []
        params = []
        _append_where(parsed, where_parts, params, prefix="")

        sql = base_sql
        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)
        sql += " ORDER BY id DESC"
        cursor.execute(sql, params)
    else:
        base_sql = """
        SELECT pi.id AS item_id, pi.quantity, pi.note AS item_note, pi.added_at,
               c.id, c.purpose, c.generic_desc, c.model, c.package, c.pin_count,
               c.key_params, c.pin_notes, c.voltage, c.current, c.power,
               c.lcsc_id, c.buy_link, c.current_price, c.supplier, c.status,
               c.created_at, c.updated_at, c.price_updated_at
        FROM project_items pi
        JOIN components c ON c.id = pi.component_id
        """
        where_parts = ["pi.project_id = ?"]
        params = [project_id]
        _append_where(parsed, where_parts, params, prefix="c.")

        sql = base_sql + " WHERE " + " AND ".join(where_parts)
        sql += " ORDER BY c.id DESC"
        cursor.execute(sql, params)

    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    result = [dict(zip(columns, row)) for row in rows]

    # 全部视图：按 lcsc_id 去重
    if project_id is None:
        seen = set()
        deduped = []
        for r in result:
            key = _dedup_key(r)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(r)
        return deduped

    return result


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