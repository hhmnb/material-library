# -*- coding: utf-8 -*-
"""
封装库的搜索/打分工具。
不预置任何数据，数据全部来自数据库 footprints 表。
"""

# 内置种子数据：留空。如果你想以后批量灌数据，把内容填进来即可。
BUILTIN_FOOTPRINTS = []


# ==================== 匹配打分 ====================

def _normalize(s: str) -> str:
    """统一小写 + 去空格 + 去常见分隔符，方便匹配"""
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

    note_n = _normalize(fp.get("note", ""))

    score = 0
    for kw in keywords:
        kw_n = _normalize(kw)
        if not kw_n:
            continue

        # 完整 tag 命中：最高优先级
        if kw_n in tags_n:
            score += 100
            continue

        # name / display 完全等于：最高
        if kw_n == name_n or kw_n == display_n:
            score += 100
            continue

        # tags 子串
        for t in tags_n:
            if kw_n in t:
                score += 40
                break

        # name / display 子串
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