# -*- coding: utf-8 -*-
"""封装库数据服务（数据库 CRUD + 搜索 + CSV 校验/导入/导出）"""
import csv
import os
from typing import List, Optional, Dict, Any

from database.schema import get_connection
from utils.footprint_library import search_in_list


# ==================== CSV 校验规则 ====================
MAX_ROWS = 10000
REQUIRED_COLUMNS = {"name"}
MAX_LEN = {
    "name": 100,
    "display": 200,
    "category": 50,
    "pins": 10,
    "tags": 500,
    "note": 500,
    "lcsc_ids": 500,
}


def _fetch_columns(cursor, table) -> list:
    cursor.execute(f"PRAGMA table_info({table})")
    return [c[1] for c in cursor.fetchall()]


def _row_to_dict(row, columns) -> dict:
    d = dict(zip(columns, row))
    # tags 拆成列表
    if d.get("tags"):
        d["tags"] = [t.strip() for t in d["tags"].split(",") if t.strip()]
    else:
        d["tags"] = []
    # lcsc_ids 拆成列表
    if d.get("lcsc_ids"):
        d["lcsc_ids"] = [t.strip() for t in d["lcsc_ids"].split(",") if t.strip()]
    else:
        d["lcsc_ids"] = []
    return d


# ==================== 基本 CRUD ====================

def list_all() -> List[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cols = _fetch_columns(cur, "footprints")
    cur.execute("SELECT * FROM footprints ORDER BY category, name")
    rows = cur.fetchall()
    conn.close()
    return [_row_to_dict(r, cols) for r in rows]


def search(query: str, limit: int = 200) -> List[dict]:
    return search_in_list(list_all(), query, limit)


def get_by_id(fp_id: int) -> Optional[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cols = _fetch_columns(cur, "footprints")
    cur.execute("SELECT * FROM footprints WHERE id=?", (fp_id,))
    row = cur.fetchone()
    conn.close()
    return _row_to_dict(row, cols) if row else None


def get_by_name(name: str) -> Optional[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cols = _fetch_columns(cur, "footprints")
    cur.execute("SELECT * FROM footprints WHERE name=?", (name,))
    row = cur.fetchone()
    conn.close()
    return _row_to_dict(row, cols) if row else None


def add(data: dict) -> int:
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("封装名不能为空")
    if get_by_name(name):
        raise ValueError(f"封装名已存在：{name}")

    tags = data.get("tags", [])
    if isinstance(tags, list):
        tags = ",".join(t.strip() for t in tags if t.strip())

    lcsc_ids = data.get("lcsc_ids", [])
    if isinstance(lcsc_ids, list):
        lcsc_ids = ",".join(t.strip() for t in lcsc_ids if t.strip())

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO footprints (name, display, category, pins, tags, note, lcsc_ids, is_builtin)
        VALUES (?,?,?,?,?,?,?,0)
    """, (
        name,
        data.get("display", ""),
        data.get("category", ""),
        int(data.get("pins") or 0),
        tags,
        data.get("note", ""),
        lcsc_ids,
    ))
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return new_id


def update(fp_id: int, **kwargs) -> None:
    if not kwargs:
        return
    if "tags" in kwargs and isinstance(kwargs["tags"], list):
        kwargs["tags"] = ",".join(t.strip() for t in kwargs["tags"] if t.strip())
    if "lcsc_ids" in kwargs and isinstance(kwargs["lcsc_ids"], list):
        kwargs["lcsc_ids"] = ",".join(t.strip() for t in kwargs["lcsc_ids"] if t.strip())

    sets = []
    values = []
    for k, v in kwargs.items():
        sets.append(f"{k}=?")
        values.append(v)
    sets.append("updated_at=datetime('now', 'localtime')")
    values.append(fp_id)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"UPDATE footprints SET {', '.join(sets)} WHERE id=?", values)
    conn.commit()
    conn.close()


def delete(fp_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM footprints WHERE id=?", (fp_id,))
    conn.commit()
    conn.close()


# ==================== CSV 校验 ====================

def _validate_row(row: dict, line_no: int):
    name = (row.get("name") or "").strip()
    if not name:
        return None, f"第 {line_no} 行：name（封装名）不能为空", None
    if len(name) > MAX_LEN["name"]:
        return None, f"第 {line_no} 行：name 超过 {MAX_LEN['name']} 字符", None
    if "\n" in name or "\r" in name:
        return None, f"第 {line_no} 行：name 不能包含换行", None

    display = (row.get("display") or "").strip()
    category = (row.get("category") or "").strip()
    tags = (row.get("tags") or "").strip()
    note = (row.get("note") or "").strip()
    lcsc_ids = (row.get("lcsc_ids") or "").strip()

    pins_raw = (row.get("pins") or "").strip()
    if pins_raw == "":
        pins = 0
    else:
        try:
            pins = int(pins_raw)
            if pins < 0:
                return None, f"第 {line_no} 行：pins 不能为负数（当前 {pins}）", None
        except ValueError:
            return None, f"第 {line_no} 行：pins 必须是整数（当前 '{pins_raw}'）", None

    for k, v in [("display", display), ("category", category),
                 ("tags", tags), ("note", note), ("lcsc_ids", lcsc_ids)]:
        if len(v) > MAX_LEN[k]:
            return None, f"第 {line_no} 行：{k} 超过 {MAX_LEN[k]} 字符", None

    warning = None
    if not display:
        warning = f"第 {line_no} 行：display（简介）为空，建议填写"
    elif not category:
        warning = f"第 {line_no} 行：category（分类）为空，建议填写"

    return {
        "name": name,
        "display": display,
        "category": category,
        "pins": pins,
        "tags": tags,
        "note": note,
        "lcsc_ids": lcsc_ids,
    }, None, warning


def validate_csv(filepath: str) -> Dict[str, Any]:
    report = {
        "ok": False,
        "file_error": None,
        "missing_columns": [],
        "total": 0,
        "valid": 0,
        "errors": [],
        "warnings": [],
        "rows": [],
    }

    if not os.path.exists(filepath):
        report["file_error"] = f"文件不存在：{filepath}"
        return report

    try:
        with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                report["file_error"] = "CSV 文件为空或没有表头"
                return report

            fields = {f.strip().lower() for f in reader.fieldnames if f}
            missing = REQUIRED_COLUMNS - fields
            if missing:
                report["missing_columns"] = sorted(missing)
                report["file_error"] = f"缺少必需列：{', '.join(sorted(missing))}"
                return report

            for i, row in enumerate(reader, start=2):
                if report["total"] >= MAX_ROWS:
                    report["errors"].append(f"文件超过 {MAX_ROWS} 行，已停止扫描")
                    break
                report["total"] += 1
                data, err, warn = _validate_row(row, i)
                if err:
                    report["errors"].append(err)
                else:
                    report["valid"] += 1
                    if warn:
                        report["warnings"].append(warn)
                    if len(report["rows"]) < 20:
                        report["rows"].append(data)

    except UnicodeDecodeError:
        report["file_error"] = "编码错误：文件不是 UTF-8，请另存为 UTF-8"
        return report
    except Exception as e:
        report["file_error"] = f"读取文件失败：{e}"
        return report

    report["ok"] = (report["valid"] > 0 and not report["errors"])
    return report


def import_from_csv(filepath: str, strict: bool = True) -> Dict[str, Any]:
    report = validate_csv(filepath)

    if report["file_error"]:
        return {
            "success": 0, "updated": 0,
            "failures": [report["file_error"]],
            "aborted": True,
            "reason": report["file_error"],
        }

    if strict and report["errors"]:
        return {
            "success": 0, "updated": 0,
            "failures": report["errors"][:50],
            "aborted": True,
            "reason": "严格模式：文件有错误，未导入任何数据",
        }

    success = 0
    updated = 0
    failures = []

    with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            data, err, _ = _validate_row(row, i)
            if err:
                failures.append(err)
                continue
            try:
                existing = get_by_name(data["name"])
                if existing:
                    upd = {k: v for k, v in data.items() if k != "name"}
                    update(existing["id"], **upd)
                    updated += 1
                else:
                    add(data)
                    success += 1
            except Exception as e:
                failures.append(f"第 {i} 行导入失败：{e}")

    return {
        "success": success,
        "updated": updated,
        "failures": failures,
        "aborted": False,
        "warnings": report["warnings"],
    }


def export_to_csv(filepath: str) -> int:
    all_fps = list_all()
    with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "display", "category", "pins", "tags", "note", "lcsc_ids"])
        for fp in all_fps:
            tags = fp.get("tags", [])
            if isinstance(tags, list):
                tags = ",".join(tags)
            lcsc_ids = fp.get("lcsc_ids", [])
            if isinstance(lcsc_ids, list):
                lcsc_ids = ",".join(lcsc_ids)
            writer.writerow([
                fp["name"],
                fp.get("display", ""),
                fp.get("category", ""),
                fp.get("pins", 0),
                tags,
                fp.get("note", ""),
                lcsc_ids,
            ])
    return len(all_fps)