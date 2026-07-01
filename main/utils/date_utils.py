"""日期计算工具"""

import datetime
import re


def calc_age(birth_str):
    """从日期字符串计算年龄，支持 198601 / 1986-01 / 1986年01月"""
    if not birth_str:
        return None

    birth_str = str(birth_str).strip()

    m = re.match(r"^(\d{4})(\d{2})$", birth_str)
    if m:
        return _calc(int(m.group(1)), int(m.group(2)))

    m = re.match(r"^(\d{4})-(\d{2})", birth_str)
    if m:
        return _calc(int(m.group(1)), int(m.group(2)))

    m = re.match(r"^(\d{4})年(\d{2})月", birth_str)
    if m:
        return _calc(int(m.group(1)), int(m.group(2)))

    m = re.match(r"^(\d{4})$", birth_str)
    if m:
        return datetime.date.today().year - int(m.group(1))

    return None


def _calc(year, month):
    today = datetime.date.today()
    age = today.year - year
    if today.month < month:
        age -= 1
    return age


def fmt_date(date_str, fmt="ym"):
    """格式化日期，198601 → 1986.01"""
    if not date_str:
        return ""

    date_str = str(date_str).strip()
    m = re.match(r"^(\d{4})(\d{2})(\d{2})?$", date_str)
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3) or "01"
        if fmt == "ym":
            return f"{y}.{mo}"
        elif fmt == "y-m":
            return f"{y}-{mo}"
        elif fmt == "ymd":
            return f"{y}.{mo}.{d}"

    return date_str


def birth_with_age(birth_str):
    """198601 → 1986.01（38岁）"""
    fmt = fmt_date(birth_str, "ym")
    age = calc_age(birth_str)
    if age is not None:
        return f"{fmt}\n（{age}岁）"
    return fmt
