"""Mindustry 的「标签」：游戏内给蓝图打的 labels。

蓝图文件 `tags` 里有一项 `labels`，值是 JSON 数组文本，元素带颜色标记，
例如 `["[#6335f8][white]ILI","[gray]抽水"]`。这里把它解析成纯文本标签。
"""

from __future__ import annotations

import json
import re

_COLOR_TOKEN = re.compile(r"\[([^\]]{1,32})\]")

# Mindustry 的颜色名（Colors 里的 put 名 + 常用别名）。其余 `[...]` 视为正文。
_COLOR_NAMES = {
    "white", "black", "gray", "grey", "lightgray", "lightgrey", "darkgray", "darkgrey",
    "red", "green", "blue", "yellow", "orange", "purple", "pink", "cyan", "magenta",
    "sky", "olive", "slate", "gold", "highlight", "accent", "scarlet", "crimson",
    "coral", "acid", "teal", "forest", "navy", "royal", "brown", "darkest", "clear",
    "light", "dark", "value", "unlaunched", "stat", "negstat", "control", "logic",
}


def strip_colors(text: str) -> str:
    """去掉 Mindustry 颜色标记与图标字形，保留文字。"""
    def repl(match: re.Match[str]) -> str:
        token = match.group(1)
        if token.startswith("#") or token.lower() in _COLOR_NAMES:
            return ""
        return match.group(0)

    text = _COLOR_TOKEN.sub(repl, text)
    # 游戏里标签前面常带一个图标字形（Unicode 私用区 U+E000..U+F8FF），页面上显示成方块，去掉。
    text = "".join(ch for ch in text if not ("\ue000" <= ch <= "\uf8ff"))
    return text.strip()


# 数字标签不是分类，是「生效工厂总数」：1..9 是确切台数，10~19 / 20~29 是区间，极多是更多。
FACTORY_RE = re.compile(r"^([1-9]|10~19|20~29|极多)$")

# 页面上按这个顺序排列（1→9，再区间，最后极多）。
FACTORY_ORDER = [str(i) for i in range(1, 10)] + ["10~19", "20~29", "极多"]


def split_factory(labels: list[str]) -> tuple[str, list[str]]:
    """把数字标签挑出来当作「生效工厂总数」，返回 (factory, 其余标签)。

    蓝图只会带一个数字标签；万一有多个，取第一个，其余丢弃。
    """
    factory = ""
    rest: list[str] = []
    for label in labels:
        if FACTORY_RE.match(label):
            if not factory:
                factory = label
            continue
        rest.append(label)
    return factory, rest


def parse_labels(raw: str) -> list[str]:
    """把蓝图 tags['labels'] 解析成标签列表（去重、保序、去空）。"""
    raw = (raw or "").strip()
    if not raw:
        return []

    items: list[str] = []
    try:
        value = json.loads(raw)
        if isinstance(value, str):
            items = [value]
        elif isinstance(value, list):
            items = [str(x) for x in value]
    except (json.JSONDecodeError, TypeError):
        # 老版本或被截断的写法：`["a","b"]` / `a,b`
        text = raw
        if text.startswith("[\"") and text.endswith("\"]"):
            text = text[2:-2]
        text = text.replace('","', ",").replace('\\"', '"')
        items = [part.strip(' "[]') for part in text.split(",")]

    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        label = strip_colors(item)
        if not label or label in seen:
            continue
        seen.add(label)
        out.append(label)
    return out
