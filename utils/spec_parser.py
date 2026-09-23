# -*- coding: utf-8 -*-
"""
从嘉立创 / 立创商城 BOM 的 Comment 字段里解析出电气规格。
支持：
    - 电压：5V / 3.3V / 5V0 / 3V3 / 50VDC / V=5 / V:5 / 2.7-5.5V / 5伏
    - 电流：1A / 500mA / 100uA / I=2A / Iout=500mA
    - 功率：1W / 0.25W / 250mW / 1/4W / 1/2W / P=0.5W

用法：
    from utils.spec_parser import parse_specs
    parsed = parse_specs("100nF/50V 0603")
    # {'voltage': '50V', 'current': '', 'power': '', 'key_params': '100nF/50V 0603'}
"""
import re


def _normalize(text: str) -> str:
    """基础归一化：全角转半角、去首尾空格"""
    if not text:
        return ""
    text = text.replace("，", ",").replace("；", ";").replace("：", ":")
    text = text.replace("～", "~").replace("到", "~")
    return text.strip()


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
    # 1) 3V3 / 5V0 / 1V8 这种把小数点写在字母中间的写法
    m = re.search(r'(?<![A-Za-z0-9])(\d+)[Vv](\d)(?![0-9])', text)
    if m:
        result["voltage"] = f"{m.group(1)}.{m.group(2)}V"
    else:
        # 2) 范围：2.7-5.5V 或 2.7~5.5V
        m = re.search(r'(\d+(?:\.\d+)?)\s*[Vv]?\s*[-~]\s*(\d+(?:\.\d+)?)\s*[Vv](?![A-Za-z0-9])', text)
        if m:
            result["voltage"] = f"{m.group(1)}-{m.group(2)}V"
        else:
            # 3) 普通写法：5V / 3.3V / 50VDC
            m = re.search(r'(\d+(?:\.\d+)?)\s*[Vv](?:DC|dc)?(?![A-Za-z0-9])', text)
            if m:
                result["voltage"] = f"{m.group(1)}V"
            else:
                # 4) V=5 / V:5 / Voltage=5
                m = re.search(r'[Vv](?:oltage)?\s*[:=]\s*(\d+(?:\.\d+)?)', text)
                if m:
                    result["voltage"] = f"{m.group(1)}V"
                else:
                    # 5) 中文：5伏
                    m = re.search(r'(\d+(?:\.\d+)?)\s*伏', text)
                    if m:
                        result["voltage"] = f"{m.group(1)}V"

    # ---------- 电流 ----------
    # 1) mA
    m = re.search(r'(\d+(?:\.\d+)?)\s*m[Aa](?![A-Za-z0-9])', text)
    if m:
        result["current"] = f"{m.group(1)}mA"
    else:
        # 2) uA / μA
        m = re.search(r'(\d+(?:\.\d+)?)\s*[uμ][Aa](?![A-Za-z0-9])', text)
        if m:
            result["current"] = f"{m.group(1)}uA"
        else:
            # 3) 单独 A：注意前后不能跟字母数字，避免吃掉 AMS1117 之类
            m = re.search(r'(?<![A-Za-z])(\d+(?:\.\d+)?)\s*[Aa](?![A-Za-z0-9])', text)
            if m:
                result["current"] = f"{m.group(1)}A"
            else:
                # 4) I=2A / Iout=500mA / Imax=3A
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
    # 1) 分数写法：1/4W / 1/2W / 1/8W
    m = re.search(r'1\s*/\s*(\d+)\s*[Ww](?![A-Za-z0-9])', text)
    if m:
        denom = int(m.group(1))
        if denom > 0:
            result["power"] = f"{1.0/denom:.4g}W"
    else:
        # 2) mW
        m = re.search(r'(\d+(?:\.\d+)?)\s*m[Ww](?![A-Za-z0-9])', text)
        if m:
            result["power"] = f"{m.group(1)}mW"
        else:
            # 3) 普通 W：1W / 0.25W
            m = re.search(r'(\d+(?:\.\d+)?)\s*[Ww](?![A-Za-z0-9])', text)
            if m:
                result["power"] = f"{m.group(1)}W"
            else:
                # 4) P=0.5W / Power=500mW
                m = re.search(r'[Pp](?:ower)?\s*[:=]\s*(\d+(?:\.\d+)?)\s*([mM]?)[Ww]', text)
                if m:
                    unit = m.group(2).lower()
                    if unit == 'm':
                        result["power"] = f"{m.group(1)}mW"
                    else:
                        result["power"] = f"{m.group(1)}W"

    return result


# 调试用
if __name__ == "__main__":
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
        print(f"{s:25s} → V={p['voltage']:10s} I={p['current']:8s} P={p['power']}")