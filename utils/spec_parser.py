# -*- coding: utf-8 -*-
"""
从嘉立创 / 立创商城 BOM 的 Comment 和 Footprint 字段里解析出电气规格、引脚数、用途等。
支持：
    - 电压：5V / 3.3V / 5V0 / 3V3 / 50VDC / V=5 / V:5 / 2.7-5.5V / 5伏
    - 电流：1A / 500mA / 100uA / I=2A / Iout=500mA
    - 功率：1W / 0.25W / 250mW / 1/4W / 1/2W / P=0.5W
    - 引脚数：从封装名解析（SOT-23-6 → 6、MSOP-10 → 10、C0603 → 2）
    - 用途：从封装名推断（C0603 → 电容、R0603 → 电阻、SOP-16 → 芯片）

用法：
    from utils.spec_parser import (
        parse_specs, extract_pin_count, infer_purpose,
        simplify_footprint, build_key_params,
    )
    parse_specs("100nF/50V 0603")
    # {'voltage': '50V', 'current': '', 'power': '', 'key_params': '100nF/50V 0603'}
    extract_pin_count("SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BR")   # 6
    infer_purpose("C0603", "100nF")                          # "电容"
    simplify_footprint("SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BR")  # "SOT-23-6"
    build_key_params("100nF", "C0603", "100nF")              # "100nF · C0603"
"""
import re


def _normalize(text: str) -> str:
    """基础归一化：全角转半角、去首尾空格"""
    if not text:
        return ""
    text = text.replace("，", ",").replace("；", ";").replace("：", ":")
    text = text.replace("～", "~").replace("到", "~")
    return text.strip()


# ==================== 电气规格解析 ====================

def parse_specs(text: str) -> dict:
    """
    解析一段 Comment 文本，返回：
        {
            "voltage":    "5V" / "2.7-5.5V" / "",
            "current":    "500mA" / "3A" / "",
            "power":      "0.25W" / "250mW" / "",
            "key_params": "原始 Comment 文本（保留全部信息）",
        }
    """
    text = _normalize(text)
    result = {"voltage": "", "current": "", "power": "", "key_params": text}
    if not text:
        return result

    # ---------- 电压 ----------
    m = re.search(r'(?<![A-Za-z0-9])(\d+)[Vv](\d)(?![0-9])', text)
    if m:
        result["voltage"] = f"{m.group(1)}.{m.group(2)}V"
    else:
        m = re.search(r'(\d+(?:\.\d+)?)\s*[Vv]?\s*[-~]\s*(\d+(?:\.\d+)?)\s*[Vv](?![A-Za-z0-9])', text)
        if m:
            result["voltage"] = f"{m.group(1)}-{m.group(2)}V"
        else:
            m = re.search(r'(\d+(?:\.\d+)?)\s*[Vv](?:DC|dc)?(?![A-Za-z0-9])', text)
            if m:
                result["voltage"] = f"{m.group(1)}V"
            else:
                m = re.search(r'[Vv](?:oltage)?\s*[:=]\s*(\d+(?:\.\d+)?)', text)
                if m:
                    result["voltage"] = f"{m.group(1)}V"
                else:
                    m = re.search(r'(\d+(?:\.\d+)?)\s*伏', text)
                    if m:
                        result["voltage"] = f"{m.group(1)}V"

    # ---------- 电流 ----------
    m = re.search(r'(\d+(?:\.\d+)?)\s*m[Aa](?![A-Za-z0-9])', text)
    if m:
        result["current"] = f"{m.group(1)}mA"
    else:
        m = re.search(r'(\d+(?:\.\d+)?)\s*[uμ][Aa](?![A-Za-z0-9])', text)
        if m:
            result["current"] = f"{m.group(1)}uA"
        else:
            m = re.search(r'(?<![A-Za-z])(\d+(?:\.\d+)?)\s*[Aa](?![A-Za-z0-9])', text)
            if m:
                result["current"] = f"{m.group(1)}A"
            else:
                m = re.search(r'[Ii](?:out|max|rms)?\s*[:=]\s*(\d+(?:\.\d+)?)\s*([uμmM]?)[Aa]', text)
                if m:
                    unit = m.group(2).lower()
                    if unit == 'm':
                        result["current"] = f"{m.group(1)}mA"
                    elif unit in ('u', 'μ'):
                        result["current"] = f"{m.group(1)}uA"
                    else:
                        result["current"] = f"{m.group(1)}A"

    # ---------- 功率 ----------
    m = re.search(r'1\s*/\s*(\d+)\s*[Ww](?![A-Za-z0-9])', text)
    if m:
        denom = int(m.group(1))
        if denom > 0:
            result["power"] = f"{1.0/denom:.4g}W"
    else:
        m = re.search(r'(\d+(?:\.\d+)?)\s*m[Ww](?![A-Za-z0-9])', text)
        if m:
            result["power"] = f"{m.group(1)}mW"
        else:
            m = re.search(r'(\d+(?:\.\d+)?)\s*[Ww](?![A-Za-z0-9])', text)
            if m:
                result["power"] = f"{m.group(1)}W"
            else:
                m = re.search(r'[Pp](?:ower)?\s*[:=]\s*(\d+(?:\.\d+)?)\s*([mM]?)[Ww]', text)
                if m:
                    unit = m.group(2).lower()
                    if unit == 'm':
                        result["power"] = f"{m.group(1)}mW"
                    else:
                        result["power"] = f"{m.group(1)}W"

    return result


# ==================== 引脚数解析 ====================

def extract_pin_count(footprint: str) -> int:
    """
    从封装名解析引脚数，无法确定返回 0。
    支持的写法：
        RES-SMD_4P-... / SW-SMD_4P-...      → 4
        CONN-TH_...-2P                       → 2
        USB-C-SMD_TYPE-C-16PIN-...           → 16
        SOT-23-6_L2.9-W1.6-...               → 6
        SOT-23-3_L2.9-W1.3-...               → 3
        MSOP-10_L3.0-W3.0-...                → 10
        DFN-8_L3.0-W3.0-...                  → 8
        ESSOP-10_L4.9-W3.9-...               → 10
        C0603 / R0603 / R2512 / F2920        → 2
        LED0603-RD                           → 2
        SOD-323_... / DO-214AA_...           → 2
        IND-SMD_L3.0-W3.0                    → 2
    """
    if not footprint:
        return 0
    up = footprint.strip().upper()

    # 1) 显式 "4P" / "5P"（下划线或连字符包围，或作为尾部）
    m = re.search(r'[_\-](\d+)\s*P(?:[_\-]|$)', up)
    if m:
        return int(m.group(1))

    # 2) 显式 "16PIN"
    m = re.search(r'[_\-](\d+)\s*PIN', up)
    if m:
        return int(m.group(1))

    # 3) SOT-23-6 / MSOP-10-... 这种标准封装：前缀-数字-数字
    m = re.match(r'^(?:SOT|MSOP|DFN|QFN|SOP|ESSOP|TSSOP|SSOP|QFP|LQFP|DIP|HDIP|TO)-[0-9A-Z]+-(\d+)(?:[_\-]|$)', up)
    if m:
        return int(m.group(1))

    # 4) MSOP-10_... / DFN-8_... / ESSOP-10_... 这种：前缀-数字
    m = re.match(r'^(?:SOT|MSOP|DFN|QFN|SOP|ESSOP|TSSOP|SSOP)-(\d+)(?:[_\-]|$)', up)
    if m:
        return int(m.group(1))

    # 5) TYPE-C-16PIN
    m = re.search(r'TYPE-?C-(\d+)PIN', up)
    if m:
        return int(m.group(1))

    # 6) 已知的两脚封装
    if re.match(r'^(?:C|R|L|FB|D)\d{3,4}$', up):     # C0603 / R0603 / R2512
        return 2
    if re.match(r'^F\d{3,4}$', up):                   # F2920
        return 2
    if re.match(r'^(?:SOD|DO)-', up):                 # SOD-323 / DO-214AA
        return 2
    if re.match(r'^LED\d{3,4}', up):                  # LED0603
        return 2
    if re.match(r'^IND-', up):                        # IND-SMD
        return 2

    return 0


# ==================== 封装名简化 ====================

def simplify_footprint(footprint: str) -> str:
    """
    从封装名提取主体部分（去掉后续的尺寸信息）：
        SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BR → SOT-23-6
        USB-C-SMD_TYPE-C-16PIN-XUBF-0336-0816 → USB-C-SMD
        MSOP-10_L3.0-W3.0-P0.50-LS5.0-BL → MSOP-10
    """
    if not footprint:
        return ""
    fp = footprint.strip()
    if '_' in fp:
        return fp.split('_', 1)[0]
    return fp


# ==================== 用途推断 ====================

def infer_purpose(footprint: str, comment: str = "") -> str:
    """
    从封装名 / Comment 推断元件的粗略类型（作为 purpose 字段的默认值）。
    推断不出返回 "BOM导入"。
    """
    fp = (footprint or "").upper()
    cm = (comment or "").upper()
    raw_c = comment or ""

    # 贴片阻容：C0603 / C0805 / R0603 / R2512 / L0603 / FB0603
    if re.match(r'^C\d{3,4}$', fp):
        return "电容"
    if re.match(r'^R\d{3,4}$', fp):
        return "电阻"
    if re.match(r'^(?:L|FB)\d{3,4}$', fp):
        return "电感"

    # 从 Comment 推断（阻容值语义）
    if raw_c:
        # 电容：数字 + (p|n|u|μ|m)F，如 100nF / 10uF / 4.7pF
        if re.search(r'\d+(?:\.\d+)?\s*(?:[pnμum]?)[Ff](?![A-Za-z])', raw_c):
            return "电容"
        # 电感：数字 + (n|u|μ|m)H，如 10uH / 4.7nH
        if re.search(r'\d+(?:\.\d+)?\s*[nuμm]?[Hh](?![zZ])', raw_c):
            return "电感"
        # 电阻：数字 + Ω/K/M/R，如 1kΩ / 10K
        if re.search(r'\d+(?:\.\d+)?\s*(?:[KMkm]?)\s*(?:Ω|[Rr])(?![A-Za-z])', raw_c):
            return "电阻"
        if re.match(r'^\d+(?:\.\d+)?\s*[KMkm]$', raw_c.strip()):
            return "电阻"

    # 二极管 / TVS
    if fp.startswith('SOD-') or fp.startswith('DO-'):
        return "二极管"
    if fp.startswith('LED'):
        return "LED"
    if 'TVS' in cm or 'ESD' in cm:
        return "TVS/ESD"

    # 电感封装
    if fp.startswith('IND-'):
        return "电感"

    # 保险丝
    if re.match(r'^F\d{3,4}$', fp) or 'FUSE' in cm:
        return "保险丝"

    # 晶振
    if 'CRYSTAL' in fp or 'XTAL' in fp:
        return "晶振"

    # USB
    if 'USB' in fp:
        return "USB 接口"

    # 开关
    if fp.startswith('SW-') or fp.startswith('SW_') or 'SWITCH' in cm:
        return "开关"

    # 连接器
    if fp.startswith('CONN-') or fp.startswith('CONN_') or 'CONNECTOR' in cm:
        return "连接器"

    # 无线模块
    if 'WIFIM' in fp or 'WIFI' in fp or 'ESP32' in fp:
        return "无线模块"

    # 芯片
    if re.match(r'^(?:SOT|DFN|QFN|SOP|MSOP|ESSOP|TSSOP|SSOP|QFP|LQFP|DIP|TO)-', fp):
        return "芯片"

    return "BOM导入"


# ==================== key_params 组合 ====================

def build_key_params(comment: str, footprint: str, value: str = "") -> str:
    """
    组合 key_params：Comment 为主，补封装主体
        build_key_params("100nF", "C0603", "100nF")  → "100nF · C0603"
        build_key_params("SRV05-4", "SOT-23-6_xxx")  → "SRV05-4 · SOT-23-6"
    """
    parts = []
    c = (comment or "").strip()
    v = (value or "").strip()
    fp_short = simplify_footprint(footprint or "")

    # 主描述：优先 Comment，其次 Value
    if c:
        parts.append(c)
    elif v:
        parts.append(v)

    # 如果 Comment 为空但 Value 有值，把 Value 也补上（避免丢信息）
    if c and v and v.lower() != c.lower():
        # 一般 Value 和 Comment 相同，不重复加
        pass

    # 补封装主体（去重）
    if fp_short and fp_short.lower() != c.lower() and fp_short not in parts:
        parts.append(fp_short)

    return " · ".join(parts)


# ==================== 调试 ====================
if __name__ == "__main__":
    print("== parse_specs 测试 ==")
    samples = [
        "100nF/50V 0603",
        "10K 1% 0603",
        "5V0 500mA LDO",
        "3V3 800mA",
        "1/4W 10R 0603",
        "250mW 100R",
        "SRV05-4",
        "2.7-5.5V 3A",
        "AMS1117-3.3",
        "1uF/25V",
        "V=5V I=1A P=0.5W",
    ]
    for s in samples:
        p = parse_specs(s)
        print(f"  {s:25s} → V={p['voltage']:10s} I={p['current']:8s} P={p['power']}")

    print("\n== extract_pin_count 测试 ==")
    fps = [
        "C0603", "R0603", "R2512", "F2920",
        "SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BR",
        "SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR",
        "MSOP-10_L3.0-W3.0-P0.50-LS5.0-BL",
        "DFN-8_L3.0-W3.0-P0.65-BL",
        "DFN-10_L3.0-W3.0-P0.50-TL-EP_L7983PU33R",
        "ESSOP-10_L4.9-W3.9-P1.0-LS6.0-TL-EP",
        "USB-C-SMD_TYPE-C-16PIN-XUBF-0336-0816",
        "SOD-323_L1.7-W1.3-LS2.7-RD",
        "DO-214AA_L4.4-W3.6-LS5.3-RD",
        "IND-SMD_L3.0-W3.0",
        "LED0603-RD",
        "RES-SMD_4P-L3.2-W6.4_LVK25XXXX",
        "SW-SMD_4P-L6.0-W6.0-P4.50-LS9.0_H5.0",
        "CONN-TH_LAIL-PZ2.54-4P-L",
        "CONN-TH_P5.08_KF128-5.08-2P",
        "WIFIM-SMD_ESP32-C3-MINI-1",
    ]
    for fp in fps:
        print(f"  {fp[:50]:50s} → {extract_pin_count(fp)}")

    print("\n== infer_purpose 测试 ==")
    pairs = [
        ("C0603", "100nF"),
        ("R0603", "10K"),
        ("R2512", "1kΩ"),
        ("SOT-23-6_L2.9-W1.6", "SRV05-4"),
        ("SOT-23-3_L2.9-W1.3", "MMBT3904T2"),
        ("MSOP-10_L3.0-W3.0", "INA226AIDGSR"),
        ("SOD-323_L1.7-W1.3", "1N5819WS S4"),
        ("DO-214AA_L4.4-W3.6", "SMBJ24A"),
        ("USB-C-SMD_TYPE-C-16PIN", "TYPE C 16PIN"),
        ("F2920", "2920L500/33GR"),
        ("IND-SMD_L3.0-W3.0", "10uH"),
        ("LED0603-RD", "LTST-C190KSKT"),
        ("WIFIM-SMD_ESP32-C3-MINI-1", "2.4GHz"),
        ("CONN-TH_LAIL-PZ2.54-4P-L", "LAIL-PZ2.54-4P-L"),
        ("SW-SMD_4P-L6.0-W6.0", "KH-6X6X5H-STM"),
        ("", "1uF"),
    ]
    for fp, cm in pairs:
        print(f"  {(fp or '')[:35]:35s} | {cm[:25]:25s} → {infer_purpose(fp, cm)}")

    print("\n== build_key_params 测试 ==")
    for c, fp, v in [
        ("100nF", "C0603", "100nF"),
        ("47uF", "C1210", "47uF"),
        ("SRV05-4", "SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BR", ""),
        ("", "C0603", "1uF"),
        ("AON7407", "DFN-8_L3.0-W3.0-P0.65-BL", "AON7407"),
    ]:
        print(f"  comment={c!r:15s} fp={fp[:35]:35s} value={v!r:10s}")
        print(f"    → {build_key_params(c, fp, v)}")