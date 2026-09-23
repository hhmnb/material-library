# -*- coding: utf-8 -*-
"""
元件服务层：提供元件的增删改查和匹配功能。
"""
import re
import json
import csv
import io
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from database.schema import get_connection
from models.component import Component


# ==================== AI 生成提示词（一键复制给 AI 用）====================

AI_PROMPT_TEMPLATE = """精料库 · 数据生成规范（AI 提示词）
================================================================
本段整段发给 AI，让 AI 按下面的规范生成可批量导入"精料库"的数据。

【任务 1 · 生成元件（文本格式，粘到"添加元件"框批量导入）】
规则：
  1. 每行一个字段，用中文冒号（：）或英文冒号（:）分隔
  2. 多个元件之间用【一个空行】分隔
  3. 字段值可以为空，但保留标签更便于后续补填
  4. 字段清单（顺序可任意）：
     用途 | 通用描述 | 型号 | 封装 | 引脚数 | 电压 | 电流 | 功率 |
     关键参数 | 特殊注意 | 立创编号 | 购买链接 | 价格 | 供应商 | 状态
  5. 状态字段只能是：未验证 / 已验证 / 已淘汰
  6. 引脚数是整数；价格是数字（不带单位）

【任务 2 · 生成封装库（CSV 格式，保存为 .csv 后用"智能导入"）】
第一行必须是下面这个表头（英文，逗号分隔）：
name,display,category,pins,tags,note,lcsc_ids
说明：
  name       封装名（唯一，必填），如 LED0603-RD
  display    简介，如 "0603 LED · 状态指示"
  category   分类，如 LED / USB / 阻容 / 半导体
  pins       引脚数（整数）
  tags       标签，多个用英文逗号隔开
  note       备注
  lcsc_ids   关联的立创编号，多个用英文逗号隔开

================================================================
【元件输出示例】
用途: LDO 稳压
通用描述: 3.3V LDO
型号: AMS1117-3.3
封装: SOT-223
引脚数: 3
电压: 5V
电流: 800mA
功率: 1W
关键参数: 输出3.3V，最大1A
特殊注意: 输入输出各接10uF
立创编号: C6186
购买链接: https://item.szlcsc.com/6186.html
价格: 0.35
供应商: 立创商城
状态: 已验证

用途: 退耦/滤波
通用描述: 100nF/50V 0603
型号: 0603B104K500NT
封装: C0603
引脚数: 2
电压: 50V
电流: 
功率: 
关键参数: X7R 材质
特殊注意: 
立创编号: C14663
购买链接: 
价格: 0.01
供应商: 立创商城
状态: 已验证

用途: TVS/ESD 保护
通用描述: SRV05-4
型号: SRV05-4
封装: SOT-23-6
引脚数: 6
电压: 5V
电流: 1A
功率: 0.5W
关键参数: 结电容 1pF
特殊注意: 靠近接口放置
立创编号: C384887
购买链接: 
价格: 0.85
供应商: 立创商城
状态: 已验证

================================================================
【封装库 CSV 输出示例】
name,display,category,pins,tags,note,lcsc_ids
LED0603-RD,0603 LED · 状态指示,LED,2,0603;LED,状态灯,C125095
C0603,0603 电容 · 退耦滤波,阻容,2,0603,最常用,C14663
R0603,0603 电阻 · 上拉/下拉/限流,阻容,2,0603,通用,C122969
SOT-23-6,TVS/ESD 保护专用,半导体,6,SOT-23-6,SRV05-4 用,C384887
================================================================
"""


def _now_str() -> str:
    """获取当前时间字符串，格式：YYYY-MM-DD HH:MM:SS"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ==================== 文档读取 & 提示词拼接 ====================

def _read_text_file(filepath: str) -> str:
    """读取文本文件，自动检测编码（UTF-8 / UTF-16 / GBK）"""
    with open(filepath, 'rb') as f:
        raw = f.read()

    if raw.startswith(b'\xff\xfe'):
        encoding = 'utf-16-le'
    elif raw.startswith(b'\xfe\xff'):
        encoding = 'utf-16-be'
    elif raw.startswith(b'\xef\xbb\xbf'):
        encoding = 'utf-8-sig'
    else:
        try:
            raw.decode('utf-8')
            encoding = 'utf-8'
        except UnicodeDecodeError:
            encoding = 'gbk'

    return raw.decode(encoding, errors='replace')


def build_ai_prompt_with_file(filepath: str = None) -> str:
    """
    返回一份可以直接复制给 AI 的完整文本。
    - 不传 filepath：只返回提示词
    - 传了 filepath：提示词 + 文档内容拼接在一起
    """
    prompt = AI_PROMPT_TEMPLATE
    if not filepath:
        return prompt

    content = _read_text_file(filepath).strip()
    return (
        prompt
        + "\n\n"
        + "=" * 60
        + "\n【以下是需要处理的原始信息】\n"
        + "=" * 60
        + "\n"
        + content
        + "\n"
        + "=" * 60
        + "\n"
    )


# ==================== 信息完整度评分 ====================

_COMPLETENESS_WEIGHTS = {
    "purpose":       1,
    "generic_desc":  1,
    "model":         2,
    "package":       2,
    "pin_count":     1,
    "key_params":    3,
    "pin_notes":     1,
    "voltage":       3,
    "current":       3,
    "power":         3,
    "lcsc_id":       3,
    "buy_link":      2,
    "current_price": 2,
    "supplier":      1,
    "status":        2,
}


def _completeness_score(data: dict) -> int:
    """计算一条元件信息的完整度得分"""
    score = 0
    for field, weight in _COMPLETENESS_WEIGHTS.items():
        val = data.get(field)
        if val is None:
            continue
        if isinstance(val, (int, float)):
            if val > 0:
                score += weight
        elif isinstance(val, str):
            v = val.strip()
            if v and v != "未验证":
                score += weight
    return score


# ==================== CRUD ====================

def add_component(component: Component) -> int:
    """添加新元件，返回新元件的 id"""
    conn = get_connection()
    cursor = conn.cursor()
    now = _now_str()
    cursor.execute("""
        INSERT INTO components (
            purpose, generic_desc, model, package, pin_count,
            key_params, pin_notes, voltage, current, power,
            lcsc_id, buy_link, current_price, supplier, status, price_updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        component.purpose,
        component.generic_desc,
        component.model,
        component.package,
        component.pin_count,
        component.key_params,
        component.pin_notes,
        component.voltage,
        component.current,
        component.power,
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
    """更新元件信息（白名单字段）"""
    allowed_fields = [
        "purpose", "generic_desc", "model", "package", "pin_count",
        "key_params", "pin_notes", "voltage", "current", "power",
        "lcsc_id", "buy_link",
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
    """根据多个字段组合查询元件"""
    conn = get_connection()
    cursor = conn.cursor()

    where_parts = []
    values = []

    for field in ("purpose", "model", "package", "lcsc_id", "key_params",
                  "voltage", "current", "power", "supplier"):
        if filters.get(field):
            where_parts.append(f"{field} LIKE ?")
            values.append(f"%{filters[field]}%")

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
    """按空格拆关键词，全部命中才返回"""
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
            "OR lcsc_id LIKE ? OR key_params LIKE ? OR pin_notes LIKE ? OR supplier LIKE ? "
            "OR voltage LIKE ? OR current LIKE ? OR power LIKE ?)"
        )
        values.extend([like, like, like, like, like, like, like, like, like, like, like])

    sql = "SELECT * FROM components WHERE " + " AND ".join(where_parts) + " ORDER BY id DESC"
    cursor.execute(sql, values)
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    return [Component.from_dict(dict(zip(columns, row))) for row in rows]


def get_component_by_model(model: str) -> Optional[Component]:
    """根据型号精确查询元件"""
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
    """根据通用描述精确查询元件"""
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
    """批量更新价格"""
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
    """按 编号 → 型号 → 通用描述 → 模糊 顺序匹配"""
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
    """从文本批量更新价格"""
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
    """导出所有元件到 CSV"""
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
    """导出所有元件到 JSON"""
    components = list_all_components()
    data = [comp.to_dict() for comp in components]
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_components_price_outdated(days: int = 15) -> List[Component]:
    """查询价格超期未更新的元件"""
    conn = get_connection()
    cursor = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("SELECT * FROM components WHERE price_updated_at < ?", (cutoff,))
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    return [Component.from_dict(dict(zip(columns, row))) for row in rows]


# ==================== BOM 导入（编号/型号去重 + 完整度覆盖）====================

def import_bom_from_csv(filepath: str) -> Dict[str, Any]:
    """
    从 CSV 文件导入 BOM，自动检测编码。
    去重与覆盖策略：
        1) 立创编号完全相同 / 型号完全相同：
              - 新数据完整度 > 已有 → 用新数据补全（只补非空字段）
              - 否则 → 跳过
        2) 都没有 → 新增
    """
    from utils.spec_parser import parse_specs

    success = 0
    updated = 0
    skipped = 0
    failures = []
    total = 0

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
        return {"success": 0, "updated": 0, "skipped": 0,
                "failures": ["无法识别文件编码，请转换为 UTF-8"], "total": 0}

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return {"success": 0, "updated": 0, "skipped": 0,
                "failures": ["CSV 文件为空或缺少表头"], "total": 0}

    def pick(row, *candidates):
        for name in candidates:
            if name in row and row[name] is not None:
                val = str(row[name]).strip()
                if val:
                    return val
        return ""

    # 加载全库索引
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM components")
    existing_rows = cursor.fetchall()
    existing_cols = [desc[0] for desc in cursor.description]
    conn.close()

    by_lcsc = {}
    by_model = {}
    for row in existing_rows:
        d = dict(zip(existing_cols, row))
        if d.get("lcsc_id"):
            by_lcsc.setdefault(d["lcsc_id"].strip(), d)
        if d.get("model"):
            by_model.setdefault(d["model"].strip(), d)

    for row in reader:
        total += 1
        comment = pick(row, 'Comment', '注释', '描述', 'Description')
        footprint = pick(row, 'Footprint', '封装')
        mfr_part = pick(row, 'Manufacturer Part', '制造商型号', '型号')
        supplier_part = pick(row, 'Supplier Part', '供应商编号', '立创编号')
        manufacturer = pick(row, 'Manufacturer', '制造商', '供应商')
        col_v = pick(row, 'Voltage', '电压')
        col_i = pick(row, 'Current', '电流')
        col_p = pick(row, 'Power', '功率')

        if not comment and not mfr_part:
            failures.append(f"第 {total} 行缺少有效型号信息")
            continue

        model = mfr_part if mfr_part else comment
        generic_desc = comment if comment else model
        lcsc_id = supplier_part if supplier_part else ""

        parsed = parse_specs(comment)
        voltage = col_v or parsed["voltage"]
        current = col_i or parsed["current"]
        power   = col_p or parsed["power"]

        new_data = {
            "purpose":       "BOM导入",
            "generic_desc":  generic_desc,
            "model":         model,
            "package":       footprint,
            "pin_count":     0,
            "key_params":    comment,
            "pin_notes":     "",
            "voltage":       voltage,
            "current":       current,
            "power":         power,
            "lcsc_id":       lcsc_id,
            "buy_link":      "",
            "current_price": 0.0,
            "supplier":      manufacturer,
            "status":        "未验证",
        }

        existing = None
        match_reason = ""
        if lcsc_id and lcsc_id in by_lcsc:
            existing = by_lcsc[lcsc_id]
            match_reason = f"立创编号 {lcsc_id}"
        elif model and model in by_model:
            existing = by_model[model]
            match_reason = f"型号 {model}"

        if existing:
            old_score = _completeness_score(existing)
            new_score = _completeness_score(new_data)

            if new_score > old_score:
                update_fields = {}
                for k, v in new_data.items():
                    if k in ("created_at", "updated_at", "price_updated_at", "id"):
                        continue
                    if isinstance(v, str):
                        if v.strip():
                            update_fields[k] = v
                    elif isinstance(v, (int, float)):
                        if v > 0:
                            update_fields[k] = v

                if model:
                    update_fields["model"] = model
                if lcsc_id:
                    update_fields["lcsc_id"] = lcsc_id

                try:
                    update_component(existing["id"], **update_fields)
                    updated += 1
                    failures.append(
                        f"第 {total} 行 因信息更完整已更新"
                        f"（{match_reason}，得分 {old_score}→{new_score}）"
                    )
                except Exception as e:
                    failures.append(f"第 {total} 行更新失败: {e}")
                continue
            else:
                skipped += 1
                failures.append(
                    f"第 {total} 行 重复且不更完整，已跳过"
                    f"（{match_reason}，得分 {old_score}→{new_score}）"
                )
                continue

        comp = Component(**new_data)
        add_component(comp)
        success += 1

        new_dict = dict(new_data)
        new_dict["id"] = -1
        if lcsc_id:
            by_lcsc.setdefault(lcsc_id, new_dict)
        if model:
            by_model.setdefault(model, new_dict)

    return {
        "success": success,
        "updated": updated,
        "skipped": skipped,
        "failures": failures,
        "total": total,
    }


# ==================== 智能导入（自动识别封装库 / BOM）====================

def smart_import_csv(filepath: str) -> Dict[str, Any]:
    """
    智能导入：自动根据 CSV 表头判断类型并导入。
    返回：
        {
            "kind": "footprint" | "component",
            "result": {...}
        }
    """
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

    text = raw_data.decode(encoding, errors='replace')
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV 文件为空或缺少表头")

    names = {f.strip().lower() for f in reader.fieldnames if f}

    bom_markers = {"comment", "manufacturer part", "supplier part",
                   "designator", "quantity", "注释", "制造商型号", "供应商编号"}
    fp_markers = {"name", "display", "category", "pins", "lcsc_ids",
                  "builtin", "is_builtin", "封装名", "分类", "引脚"}

    bom_score = len(bom_markers & names)
    fp_score = len(fp_markers & names)

    if fp_score > bom_score:
        from services import footprint_service
        report = footprint_service.validate_csv(filepath)
        if report.get("file_error"):
            return {"kind": "footprint", "aborted": True,
                    "reason": report["file_error"]}
        if report.get("errors"):
            return {"kind": "footprint", "aborted": True,
                    "reason": f"校验未通过，{len(report['errors'])} 条错误",
                    "report": report}
        result = footprint_service.import_from_csv(filepath, strict=True)
        return {"kind": "footprint", "result": result}
    else:
        result = import_bom_from_csv(filepath)
        return {"kind": "component", "result": result}


# ==================== 封装速查关联 ====================

def get_specs_by_lcsc_ids(lcsc_ids) -> str:
    """根据一组 C 编号，把它们对应元件的电压/电流/功率拼成多行字符串"""
    if not lcsc_ids:
        return ""
    if isinstance(lcsc_ids, str):
        lcsc_ids = [t.strip() for t in lcsc_ids.split(",") if t.strip()]
    lcsc_ids = [str(x).strip() for x in lcsc_ids if x and str(x).strip()]
    if not lcsc_ids:
        return ""

    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ",".join(["?"] * len(lcsc_ids))
    cursor.execute(
        f"SELECT lcsc_id, voltage, current, power "
        f"FROM components WHERE lcsc_id IN ({placeholders})",
        lcsc_ids,
    )
    rows = cursor.fetchall()
    conn.close()

    lines = []
    for lcsc, v, i, p in rows:
        parts = []
        if v:
            parts.append(f"V:{v}")
        if i:
            parts.append(f"I:{i}")
        if p:
            parts.append(f"P:{p}")
        if parts:
            lines.append(f"{lcsc}: " + " ".join(parts))
    return "\n".join(lines)


# ==================== 回填规格 ====================

def backfill_specs_from_desc(only_empty: bool = True) -> Dict[str, Any]:
    """从 generic_desc / key_params 里重新解析 V / I / P 并回填"""
    from utils.spec_parser import parse_specs

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM components")
    rows = cursor.fetchall()
    columns = [d[0] for d in cursor.description]
    conn.close()

    scanned = 0
    updated = 0
    skipped = 0

    for row in rows:
        data = dict(zip(columns, row))
        scanned += 1

        has_spec = any(data.get(k) for k in ("voltage", "current", "power"))
        if only_empty and has_spec:
            skipped += 1
            continue

        src = data.get("generic_desc") or data.get("key_params") or ""
        parsed = parse_specs(src)
        if not any(parsed[k] for k in ("voltage", "current", "power")):
            skipped += 1
            continue

        update_component(
            data["id"],
            voltage=parsed["voltage"] or data.get("voltage") or "",
            current=parsed["current"] or data.get("current") or "",
            power=parsed["power"] or data.get("power") or "",
        )
        updated += 1

    return {"scanned": scanned, "updated": updated, "skipped": skipped}