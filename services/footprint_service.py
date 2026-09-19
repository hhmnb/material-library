# -*- coding: utf-8 -*-
"""封装库数据服务（数据库 CRUD + 搜索）"""
import csv
from typing import List, Optional, Dict, Any

from database.schema import get_connection
from utils.footprint_library import search_in_list


def _fetch_columns(cursor, table) -> list:
    cursor.execute(f"PRAGMA table_info({table})")
    return [c[1] for c in cursor.fetchall()]


def _row_to_dict(row, columns) -> dict:
    d = dict(zip(columns, row))
    if d.get("tags"):
        d["tags"] = [t.strip() for t in d["tags"].split(",") if t.strip()]
    else:
        d["tags"] = []
    return d


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

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO footprints (name, display, category, pins, tags, note, is_builtin)
        VALUES (?,?,?,?,?,?,0)
    """, (
        name,
        data.get("display", ""),
        data.get("category", ""),
        int(data.get("pins") or 0),
        tags,
        data.get("note", ""),
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


def import_from_csv(filepath: str) -> Dict[str, Any]:
    """CSV 列：name, display, category, pins, tags, note"""
    success, skipped = 0, 0
    failures = []
    with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 2):
            try:
                name = (row.get("name") or "").strip()
                if not name:
                    skipped += 1
                    continue
                data = {
                    "display": row.get("display", ""),
                    "category": row.get("category", ""),
                    "pins": int(row.get("pins") or 0),
                    "tags": row.get("tags", ""),
                    "note": row.get("note", ""),
                }
                existing = get_by_name(name)
                if existing:
                    update(existing["id"], **data)
                else:
                    data["name"] = name
                    add(data)
                success += 1
            except Exception as e:
                failures.append(f"第{i}行: {e}")
    return {"success": success, "skipped": skipped, "failures": failures}


def export_to_csv(filepath: str) -> int:
    all_fps = list_all()
    with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "display", "category", "pins", "tags", "note"])
        for fp in all_fps:
            tags = fp.get("tags", [])
            if isinstance(tags, list):
                tags = ",".join(tags)
            writer.writerow([
                fp["name"], fp.get("display", ""), fp.get("category", ""),
                fp.get("pins", 0), tags, fp.get("note", "")
            ])
    return len(all_fps)