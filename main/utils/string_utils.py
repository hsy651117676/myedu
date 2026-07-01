"""字符串处理工具"""


def safe_str(value, default=""):
    """安全转字符串"""
    if value is None:
        return default
    return str(value)


def truncate(value, max_len=50, suffix="..."):
    """截断字符串"""
    s = safe_str(value)
    if len(s) <= max_len:
        return s
    return s[:max_len] + suffix


def wrap_text(text, max_width=50, indent_width=18):
    if not text:
        return ""

    lines = text.strip().split("\n")
    result = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if len(line) <= max_width:
            result.append(line)
            continue

        result.append(line[:max_width])
        remaining = line[max_width:]

        indent = " " * indent_width
        while remaining:
            result.append(indent + remaining[:max_width])
            remaining = remaining[max_width:]

    return "\n".join(result)
