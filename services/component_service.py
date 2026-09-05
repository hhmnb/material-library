"""
元件服务层：提供元件的增删改查和匹配功能。
"""
import re
import json
import csv
import io
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from database.schema import get_connection
from models.component import Component


def _now_str() -> str:
    """获取当前时间字符串，格式：YYYY-MM-DD HH:MM:SS"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def add_component(component: Component) -> int:
    """添加新元件，返回新元件的 id"""
    conn = get_connection()
    cursor = conn.cursor()
    now = _now_str()
    cursor.execute("""
        INSERT INTO components (
            purpose, generic_desc, model, package, pin_count,
            key_params, pin_notes, lcsc_id, buy_link,
            current_price, supplier, status, price_updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        component.purpose,
        component.generic_desc,
        component.model,
        component.package,
        component.pin_count,
        component.key_params,
        component.pin_notes,
        component.lcsc_id,
        component.buy_link,
        component.current_price,
        component.supplier,
        component.status,
        now,
    ))
    conn.commit()
    component_id = cursor.lastrowid
    conn.close()
    return component_id


def get_component_by_id(component_id: int) -> Optional[Component]:
    """根据 id 查询元件，找不到返回 None"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM components WHERE id = ?", (component_id,))
    row = cursor.fetchone()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    if row:
        return Component.from_dict(dict(zip(columns, row)))
    return None


def get_component_by_lcsc_id(lcsc_id: str) -> Optional[Component]:
    """根据立创编号精确查询元件，找不到返回 None"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM components WHERE lcsc_id = ?", (lcsc_id,))
    row = cursor.fetchone()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    if row:
        return Component.from_dict(dict(zip(columns, row)))
    return None


def search_components(keyword: str) -> List[Component]:
    """按关键字模糊搜索（用途、型号、封装、立创编号）"""
    conn = get_connection()
    cursor = conn.cursor()
    like = f"%{keyword}%"
    cursor.execute("""
        SELECT * FROM components
        WHERE purpose LIKE ? OR model LIKE ? OR package LIKE ? OR lcsc_id LIKE ?
    """, (like, like, like, like))
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    return [Component.from_dict(dict(zip(columns, row))) for row in rows]


def list_all_components() -> List[Component]:
    """列出所有元件，按 id 倒序"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM components ORDER BY id DESC")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    return [Component.from_dict(dict(zip(columns, row))) for row in rows]


def update_component(component_id: int, **kwargs) -> None:
    """
    更新元件信息
    只允许更新白名单内的字段，避免 SQL 注入和误操作
    如果更新了 current_price，则同时更新 price_updated_at
    """
    allowed_fields = [
        "purpose", "generic_desc", "model", "package", "pin_count",
        "key_params", "pin_notes", "lcsc_id", "buy_link",
        "current_price", "supplier", "status"
    ]
    updates = []
    values = []
    for key, value in kwargs.items():
        if key in allowed_fields:
            updates.append(f"{key} = ?")
            values.append(value)
            if key == "current_price":
                updates.append("price_updated_at = ?")
                values.append(_now_str())

    if not updates:
        return
    values.append(component_id)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE components SET {', '.join(updates)} WHERE id = ?", values)
    conn.commit()
    conn.close()


def delete_component(component_id: int) -> None:
    """删除指定 id 的元件"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM components WHERE id = ?", (component_id,))
    conn.commit()
    conn.close()


def search_components_advanced(filters: dict) -> List[Component]:
    """
    根据多个字段组合查询元件，filters 中只包含非空条件。
    可用的键：purpose, model, package, lcsc_id, key_params, supplier, status
    """
    conn = get_connection()
    cursor = conn.cursor()

    where_parts = []
    values = []

    if filters.get("purpose"):
        where_parts.append("purpose LIKE ?")
        values.append(f"%{filters['purpose']}%")

    if filters.get("model"):
        where_parts.append("model LIKE ?")
        values.append(f"%{filters['model']}%")

    if filters.get("package"):
        where_parts.append("package LIKE ?")
        values.append(f"%{filters['package']}%")

    if filters.get("lcsc_id"):
        where_parts.append("lcsc_id LIKE ?")
        values.append(f"%{filters['lcsc_id']}%")

    if filters.get("key_params"):
        where_parts.append("key_params LIKE ?")
        values.append(f"%{filters['key_params']}%")

    if filters.get("supplier"):
        where_parts.append("supplier LIKE ?")
        values.append(f"%{filters['supplier']}%")

    if filters.get("status"):
        where_parts.append("status = ?")
        values.append(filters["status"])

    sql = "SELECT * FROM components"
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    sql += " ORDER BY id DESC"

    cursor.execute(sql, values)
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    return [Component.from_dict(dict(zip(columns, row))) for row in rows]


def search_components_multi(keyword_text: str) -> List[Component]:
    """
    按空格拆分为多个关键词，所有关键词都必须匹配才返回。
    每个关键词会在多个字段中模糊匹配。
    """
    keywords = [k.strip() for k in keyword_text.strip().split() if k.strip()]
    if not keywords:
        return []

    conn = get_connection()
    cursor = conn.cursor()

    where_parts = []
    values = []
    for kw in keywords:
        like = f"%{kw}%"
        where_parts.append(
            "(purpose LIKE ? OR generic_desc LIKE ? OR model LIKE ? OR package LIKE ? "
            "OR lcsc_id LIKE ? OR key_params LIKE ? OR pin_notes LIKE ? OR supplier LIKE ?)"
        )
        values.extend([like, like, like, like, like, like, like, like])

    sql = "SELECT * FROM components WHERE " + " AND ".join(where_parts) + " ORDER BY id DESC"
    cursor.execute(sql, values)
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    return [Component.from_dict(dict(zip(columns, row))) for row in rows]


def get_component_by_model(model: str) -> Optional[Component]:
    """根据型号精确查询元件，找不到返回 None"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM components WHERE model = ?", (model,))
    row = cursor.fetchone()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    if row:
        return Component.from_dict(dict(zip(columns, row)))
    return None


def get_component_by_generic_desc(generic_desc: str) -> Optional[Component]:
    """根据通用描述精确查询元件，找不到返回 None"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM components WHERE generic_desc = ?", (generic_desc,))
    row = cursor.fetchone()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    if row:
        return Component.from_dict(dict(zip(columns, row)))
    return None


def batch_update_price(component_ids: list, new_price: float) -> None:
    """批量更新指定元件列表的价格，并同步更新价格更新时间"""
    now = _now_str()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executemany(
        "UPDATE components SET current_price = ?, price_updated_at = ? WHERE id = ?",
        [(new_price, now, cid) for cid in component_ids]
    )
    conn.commit()
    conn.close()


def find_component_by_identifier(identifier: str) -> Optional[Component]:
    """根据输入标识匹配元件，按优先级查找"""
    comp = get_component_by_lcsc_id(identifier)
    if comp:
        return comp

    comp = get_component_by_model(identifier)
    if comp:
        return comp

    comp = get_component_by_generic_desc(identifier)
    if comp:
        return comp

    candidates = search_components_multi(identifier)
    if candidates:
        return candidates[0]

    return None


def batch_update_prices_from_text(text: str, limit: int = None) -> Dict[str, Any]:
    """
    从文本批量更新价格。
    每行格式：元件标识 价格（用空格、Tab 或逗号分隔）
    limit 参数可限制最大处理行数，None 表示不限制。
    返回 {success, failures}
    """
    success = 0
    failures = []
    lines = text.strip().splitlines()
    if limit is not None and limit > 0:
        lines = lines[:limit]

    for line_no, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue

        parts = re.split(r'[\s,]+', line)
        if len(parts) < 2:
            failures.append(f"第 {line_no} 行格式错误: {line}")
            continue

        price_str = parts[-1]
        identifier = ' '.join(parts[:-1])

        try:
            new_price = float(price_str)
            if new_price < 0:
                raise ValueError
        except ValueError:
            failures.append(f"第 {line_no} 行价格无效: {price_str}")
            continue

        comp = find_component_by_identifier(identifier)
        if comp:
            try:
                update_component(comp.id, current_price=new_price)
                success += 1
            except Exception as e:
                failures.append(f"第 {line_no} 行更新失败: {identifier} ({e})")
        else:
            failures.append(f"第 {line_no} 行未匹配到元件: {identifier}")

    return {"success": success, "failures": failures}


def export_all_to_csv(filepath: str) -> None:
    """导出所有元件到 CSV 文件，使用 utf-8-sig 编码避免乱码"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM components ORDER BY id")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()

    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)


def export_all_to_json(filepath: str) -> None:
    """导出所有元件到 JSON 文件"""
    components = list_all_components()
    data = [comp.to_dict() for comp in components]
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_components_price_outdated(days: int = 15) -> List[Component]:
    """查询价格超过指定天数未更新的元件"""
    conn = get_connection()
    cursor = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("SELECT * FROM components WHERE price_updated_at < ?", (cutoff,))
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    return [Component.from_dict(dict(zip(columns, row))) for row in rows]


def import_bom_from_csv(filepath: str) -> Dict[str, Any]:
    """
    从 CSV 文件导入 BOM，自动检测编码（UTF-8、UTF-16 LE/BE、GBK）。
    返回 {success, failures, total}
    """
    success = 0
    failures = []
    total = 0

    # 读取原始字节，检测 BOM
    with open(filepath, 'rb') as f:
        raw_data = f.read()

    if raw_data.startswith(b'\xff\xfe'):
        encoding = 'utf-16-le'
    elif raw_data.startswith(b'\xfe\xff'):
        encoding = 'utf-16-be'
    elif raw_data.startswith(b'\xef\xbb\xbf'):
        encoding = 'utf-8-sig'
    else:
        try:
            raw_data.decode('utf-8')
            encoding = 'utf-8'
        except UnicodeDecodeError:
            encoding = 'gbk'

    try:
        text = raw_data.decode(encoding)
    except UnicodeDecodeError:
        return {"success": 0, "failures": ["无法识别文件编码，请转换为 UTF-8"], "total": 0}

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return {"success": 0, "failures": ["CSV 文件为空或缺少表头"], "total": 0}

    for row in reader:
        total += 1
        comment = row.get('Comment', '').strip()
        footprint = row.get('Footprint', '').strip()
        mfr_part = row.get('Manufacturer Part', '').strip()
        supplier_part = row.get('Supplier Part', '').strip()
        manufacturer = row.get('Manufacturer', '').strip()

        if not comment and not mfr_part:
            failures.append(f"第 {total} 行缺少有效型号信息")
            continue

        model = mfr_part if mfr_part else comment
        generic_desc = comment if comment else model
        lcsc_id = supplier_part if supplier_part else ""

        existing = None
        if lcsc_id:
            existing = get_component_by_lcsc_id(lcsc_id)
        if existing is None and model:
            existing = get_component_by_model(model)
        if existing:
            failures.append(f"第 {total} 行重复跳过: {model}")
            continue

        comp = Component(
            purpose="BOM导入",
            generic_desc=generic_desc,
            model=model,
            package=footprint,
            pin_count=0,
            key_params="",
            pin_notes="",
            lcsc_id=lcsc_id,
            buy_link="",
            current_price=0.0,
            supplier=manufacturer,
            status="未验证",
        )
        add_component(comp)
        success += 1

    return {"success": success, "failures": failures, "total": total}