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

AI_PROMPT_TEMPLATE = """【机器解析契约 · 严禁自由发挥】

你正在生成一份由程序直接解析的数据文件。任何格式偏差都会导致解析失败。
请严格遵守以下规则，只输出规定格式。

============================================================
一、输出格式

1. 纯文本。禁止 markdown、代码块、```、# 标题。
2. 禁止前言、后记、说明。不要写"好的"、"以下是结果"。
3. 每个元件由若干行组成，每行格式：
       字段名: 值
4. 元件与元件之间用一个【空行】分隔。
5. 字段名一字不差，顺序固定如下（共 15 个）：
       用途
       通用描述
       型号
       封装
       引脚数
       电压
       电流
       功率
       关键参数
       特殊注意
       立创编号
       购买链接
       价格
       供应商
       状态
6. 值为空时，写"字段名: "（冒号后一个空格），不要省略整行。

============================================================
二、最重要的一条规则 · 参数补全（务必执行）

输入（BOM/描述）里通常缺少 电压、电流、功率。
你有责任根据【型号】补全这三个参数，用你已有的电子元器件知识：
    · AMS1117-3.3       → 电压: 5V（输入上限）  电流: 800mA  功率: 1W
    · CC0603KRX7R9BB104 → 电压: 50V             电流:       功率: 
    · SRV05-4           → 电压: 5V（反向工作）  电流: 1A     功率: 0.5W
    · SMBJ24A           → 电压: 24V（反向工作） 电流:       功率: 600W（峰值）
    · INA226AIDGSR      → 电压: 36V             电流:       功率: 
    · 100nF 0603 电容   → 电压: 50V（常见耐压） 电流:       功率: 
    · 47uF 1210 电容    → 电压: 25V（常见耐压） 电流:       功率: 
    · 1kΩ 0603 电阻     → 电压:              电流:        功率: 0.1W
    · 4.7kΩ 0603 电阻   → 电压:              电流:        功率: 0.1W
    · TVS/ESD 器件      → 用工作电压+峰值电流+峰值功率

补全规则：
  1. 优先用你在 BOM 里能看到的明确信息
  2. BOM 里没有的，用型号自身的规格补上
  3. 阻容类：
       电容 → 电压填常见耐压（0603 默认 50V，0805/1206 默认 25V）
       电阻 → 功率填常见值（0603 默认 0.1W，0805 默认 0.125W，1206 默认 0.25W，2512 默认 1W）
  4. 芯片类：查不到的参数（如 INA226 电流）可以留空，能查到的必须填
  5. 只在你【完全不确定】的时候才留空；不要因为"BOM 里没写"就留空
  6. 数字单位要带（50V / 800mA / 0.5W）

============================================================
三、正确输出示例

用途: 电容
通用描述: 100nF
型号: CC0603KRX7R9BB104
封装: C0603
引脚数: 2
电压: 50V
电流: 
功率: 
关键参数: 100nF · C0603
特殊注意: 
立创编号: C14663
购买链接: 
价格: 
供应商: YAGEO(国巨)
状态: 未验证

用途: LDO 稳压
通用描述: 3.3V LDO
型号: AMS1117-3.3
封装: SOT-223
引脚数: 3
电压: 5V
电流: 800mA
功率: 1W
关键参数: 输出3.3V
特殊注意: 输入输出各接 10uF
立创编号: C6186
购买链接: 
价格: 0.35
供应商: 立创商城
状态: 未验证

用途: TVS/ESD
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
价格: 
供应商: Leiditech(雷卯电子)
状态: 未验证

============================================================
四、字段填写规则

用途      一句话功能或类型，如 "电容" / "电阻" / "芯片" / "LDO 稳压" / "TVS/ESD" / "连接器"
通用描述  原始描述文字（BOM 的 Comment 列）
型号      精确型号，如 CC0603KRX7R9BB104 / AMS1117-3.3
封装      完整封装名，如 C0603 / SOT-223
引脚数    整数，从封装名推断：
              SOT-23-6 → 6；SOT-23-3 → 3
              MSOP-10 / DFN-10 / ESSOP-10 / DFN-8 → 10 / 10 / 10 / 8
              SOP-16 / TSSOP-16 → 16
              USB-C-16PIN → 16
              RES-SMD_4P / SW-SMD_4P → 4
              C0603 / R0603 / R2512 / F2920 / SOD-323 / DO-214AA / LED0603 / IND-SMD → 2
              CONN-TH_xxx-2P → 2
              不确定 → 0
电压      ★ 见第二节，必须尽量补全
电流      ★ 见第二节，必须尽量补全
功率      ★ 见第二节，必须尽量补全
关键参数  格式 "Comment · 封装主体"，如 100nF · C0603
特殊注意  使用注意，没有留空
立创编号  C 开头，没有留空
购买链接  完整 URL，没有留空
价格      数字，没有留空
供应商    品牌名，如 "YAGEO(国巨)" / "TI(德州仪器)"
状态      只能是 未验证 / 已验证 / 已淘汰

============================================================
五、输入是嘉立创 BOM 表格时

表头：
    No. | Quantity | Comment | Designator | Footprint | Value |
    Manufacturer Part | Manufacturer | Supplier Part | Supplier

字段映射：
    Comment             → 通用描述
    Manufacturer Part   → 型号
    Footprint           → 封装（完整保留）
    Manufacturer        → 供应商
    Supplier Part       → 立创编号
    Value               → 与 Comment 不同时拼到"关键参数"
    Voltage/Current/Power（若有列） → 直接填到对应字段
    Quantity            → 忽略
    Designator          → 忽略
    No.                 → 忽略
    Supplier            → 忽略

去重：按"型号"去重，型号相同只输出一次。
跳过第一行表头。

============================================================
六、用途推断

    C0603 / C0805 / C1206 / C1210 → 电容
    R0603 / R2512 → 电阻
    L0603 / IND-SMD → 电感
    LED 开头 → LED
    SOD- / DO- → 二极管
    SOT-23-6 且 Comment 含 TVS/ESD → TVS/ESD
    F 开头 → 保险丝
    USB → USB 接口
    CONN- → 连接器
    SW- → 开关
    WIFIM / ESP32 → 无线模块
    其他 SOP / DFN / MSOP / QFN / SOT-23-3 → 芯片
    判断不出 → "BOM导入"

============================================================
七、现在，请处理下面的原始信息

再次强调：**电压 / 电流 / 功率 必须根据型号补全**，不要因为 BOM 里没写就留空。
按上述规则输出。不要任何前言、后记、markdown。
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


# ==================== BOM 导入（核心解析逻辑）====================

def _parse_bom_text(text: str) -> Dict[str, Any]:
    """
    内部函数：解析已经解码的 BOM 文本并导入。
    - import_bom_from_csv 负责读文件 + 编码检测，然后调它
    - import_bom_from_text 直接从剪贴板文本调它
    """
    from utils.spec_parser import (
        parse_specs, extract_pin_count, infer_purpose,
        build_key_params,
    )

    success = 0
    updated = 0
    skipped = 0
    failures = []
    total = 0

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return {"success": 0, "updated": 0, "skipped": 0,
                "failures": ["内容为空或缺少表头"], "total": 0}

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
        value_col = pick(row, 'Value', '值')
        col_v = pick(row, 'Voltage', '电压')
        col_i = pick(row, 'Current', '电流')
        col_p = pick(row, 'Power', '功率')

        if not comment and not mfr_part:
            failures.append(f"第 {total} 行缺少有效型号信息")
            continue

        model = mfr_part if mfr_part else comment
        generic_desc = comment if comment else (value_col or model)
        lcsc_id = supplier_part if supplier_part else ""

        parsed = parse_specs(comment)
        voltage = col_v or parsed["voltage"]
        current = col_i or parsed["current"]
        power   = col_p or parsed["power"]

        pin_count = extract_pin_count(footprint)
        purpose = infer_purpose(footprint, comment) or "BOM导入"
        key_params = build_key_params(comment, footprint, value_col)

        new_data = {
            "purpose":       purpose,
            "generic_desc":  generic_desc,
            "model":         model,
            "package":       footprint,
            "pin_count":     pin_count,
            "key_params":    key_params,
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


def import_bom_from_csv(filepath: str) -> Dict[str, Any]:
    """
    从 CSV 文件导入 BOM，自动检测编码。
    去重与覆盖策略：
        1) 立创编号完全相同 / 型号完全相同：
              - 新数据完整度 > 已有 → 用新数据补全（只补非空字段）
              - 否则 → 跳过
        2) 都没有 → 新增
    引脚数、用途、关键参数自动从 Footprint / Comment 推断。
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

    try:
        text = raw_data.decode(encoding)
    except UnicodeDecodeError:
        return {"success": 0, "updated": 0, "skipped": 0,
                "failures": ["无法识别文件编码，请转换为 UTF-8"], "total": 0}

    return _parse_bom_text(text)


def import_bom_from_text(text: str) -> Dict[str, Any]:
    """
    从文本直接导入 BOM（用于从剪贴板粘贴）。
    输入是已经解码好的字符串，支持 Tab 或逗号分隔。
    """
    if not text or not text.strip():
        return {"success": 0, "updated": 0, "skipped": 0,
                "failures": ["内容为空"], "total": 0}
    return _parse_bom_text(text)


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

# ==================== 从元件库聚合封装视图 ====================

def list_footprints_from_components(keyword: str = "") -> List[Dict[str, Any]]:
    """
    从 components 表按 package 字段聚合出"封装视图"。
    每个封装汇总该封装下所有元件的信息。
    """
    from utils.spec_parser import extract_pin_count, infer_purpose
    from collections import defaultdict

    conn = get_connection()
    cursor = conn.cursor()

    if keyword:
        like = f"%{keyword}%"
        cursor.execute("""
            SELECT package, purpose, lcsc_id, voltage, current, power,
                   model, generic_desc, supplier
            FROM components
            WHERE package LIKE ?
            ORDER BY package, id
        """, (like,))
    else:
        cursor.execute("""
            SELECT package, purpose, lcsc_id, voltage, current, power,
                   model, generic_desc, supplier
            FROM components
            WHERE package IS NOT NULL AND package != ''
            ORDER BY package, id
        """)

    rows = cursor.fetchall()
    conn.close()

    groups = defaultdict(list)
    for (pkg, purpose, lcsc_id, v, i, p, model, desc, supplier) in rows:
        if not pkg:
            continue
        groups[pkg].append({
            "purpose": purpose or "",
            "lcsc_id": lcsc_id or "",
            "voltage": v or "",
            "current": i or "",
            "power": p or "",
            "model": model or "",
            "generic_desc": desc or "",
            "supplier": supplier or "",
        })

    results = []
    for pkg, items in groups.items():
        # 合并 C 编号（去重）
        lcsc_set = []
        for it in items:
            cid = it["lcsc_id"].strip()
            if cid and cid not in lcsc_set:
                lcsc_set.append(cid)
        lcsc_str = ",".join(lcsc_set)

        # 合并规格（每个 C 编号一行）
        spec_lines = []
        for it in items:
            parts = []
            if it["voltage"]:
                parts.append(f"V:{it['voltage']}")
            if it["current"]:
                parts.append(f"I:{it['current']}")
            if it["power"]:
                parts.append(f"P:{it['power']}")
            if parts and it["lcsc_id"]:
                line = f"{it['lcsc_id']}: " + " ".join(parts)
                if line not in spec_lines:
                    spec_lines.append(line)
        specs = "\n".join(spec_lines)

        # 用途聚合
        purposes = []
        for it in items:
            pu = it["purpose"].strip()
            if pu and pu not in purposes:
                purposes.append(pu)
        if len(purposes) <= 3:
            purpose_str = " / ".join(purposes)
        else:
            purpose_str = " / ".join(purposes[:3]) + f" 等 {len(purposes)} 类"

        # 分类：从封装名推断
        category = infer_purpose(pkg, "")
        if category == "BOM导入":
            category = ""

        # 引脚数
        pins = extract_pin_count(pkg)

        # 供应商聚合
        suppliers = []
        for it in items:
            s = it["supplier"].strip()
            if s and s not in suppliers:
                suppliers.append(s)
        if len(suppliers) <= 2:
            supplier_str = " / ".join(suppliers)
        else:
            supplier_str = " / ".join(suppliers[:2]) + " 等"

        results.append({
            "display": purpose_str,
            "name": pkg,
            "lcsc_ids": lcsc_str,
            "specs": specs,
            "category": category,
            "pins": pins,
            "builtin": "元件库",
            "note": f"{len(items)} 个元件 · {supplier_str}",
            "is_builtin": False,
            "_count": len(items),
        })

    # 按元件数量降序
    results.sort(key=lambda x: -x["_count"])
    return results