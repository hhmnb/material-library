# -*- coding: utf-8 -*-
"""
封装库的搜索/打分工具。
不预置任何数据，数据全部来自数据库 footprints 表。
"""

BUILTIN_FOOTPRINTS = []


def _normalize(s) -> str:
    if s is None:
        return ""
    return str(s).lower().replace(" ", "").replace("-", "").replace("_", "").replace(".", "")


def _score(fp: dict, keywords: list) -> int:
    """给一个封装打分，命中越多分越高"""
    name_n = _normalize(fp.get("name", ""))
    display_n = _normalize(fp.get("display", ""))
    category_n = _normalize(fp.get("category", ""))

    tags = fp.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    tags_n = [_normalize(t) for t in tags]

    # 关联 C 编号（如 C384887,C7519）
    lcsc_ids = fp.get("lcsc_ids", "")
    if isinstance(lcsc_ids, list):
        lcsc_list = lcsc_ids
    else:
        lcsc_list = [t.strip() for t in str(lcsc_ids).split(",") if t.strip()]
    lcsc_n = [_normalize(x) for x in lcsc_list]

    note_n = _normalize(fp.get("note", ""))

    score = 0
    for kw in keywords:
        kw_n = _normalize(kw)
        if not kw_n:
            continue

        # C 编号完全命中：最高优先
        if kw_n in lcsc_n:
            score += 200
            continue

        # 完整 tag 命中
        if kw_n in tags_n:
            score += 100
            continue

        # name / display 完全等于
        if kw_n == name_n or kw_n == display_n:
            score += 100
            continue

        # tag 子串
        for t in tags_n:
            if kw_n in t:
                score += 40
                break

        # C 编号子串
        for x in lcsc_n:
            if kw_n in x:
                score += 50
                break

        if kw_n in name_n:
            score += 30
        if kw_n in display_n:
            score += 30
        if kw_n in category_n:
            score += 20
        if kw_n in note_n:
            score += 10

    return score


def search_in_list(footprints: list, query: str, limit: int = 200) -> list:
    """
    在给定的封装列表里搜索（列表可以来自数据库）。
    - 空格分隔多关键词，所有关键词累加打分
    - 空查询返回全部
    """
    query = (query or "").strip()
    if not query:
        return footprints[:limit]

    keywords = query.split()
    scored = []
    for fp in footprints:
        s = _score(fp, keywords)
        if s > 0:
            scored.append((s, fp))

    scored.sort(key=lambda x: (
        -x[0],
        x[1].get("display", "") or x[1].get("name", "")
    ))
    return [fp for _, fp in scored[:limit]]