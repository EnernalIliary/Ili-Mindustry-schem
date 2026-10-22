#!/usr/bin/env python3
"""Build data/block_categories.json: block id -> in-game tag (Mindustry v7 database tags).

Mindustry declares every vanilla block in Blocks.java like

    copperWall = new Wall("copper-wall"){{
        requirements(Category.defense, with(Items.copper, 6));
        ...
    }};

so the category of a block is the first `Category.<name>` inside its initializer.
Those categories are exactly the in-game database tags (炮塔/生产/运输/流体/电力/
防御/制造/单位/功能/逻辑), whose zh_CN names come from bundle_zh_CN.properties
(`database-tag.*`). Mod blocks are not in Blocks.java and stay untagged.

    python tools/make_categories.py                       # download Blocks.java
    python tools/make_categories.py --file Blocks.java    # use a local copy
    python tools/make_categories.py --check               # coverage report only
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / "data"
OUT_PATH = DATA / "block_categories.json"
LABELS_PATH = DATA / "category_labels.json"
BUNDLE_PATH = DATA / "bundle_zh_cn.properties"

DEFAULT_URL = "https://cdn.jsdelivr.net/gh/Anuken/Mindustry@master/core/src/mindustry/content/Blocks.java"
BUNDLE_URL = "https://cdn.jsdelivr.net/gh/Anuken/Mindustry@master/core/assets/bundles/bundle_zh_CN.properties"

NEW_RE = re.compile(r"(\w+)\s*=\s*new\s+(?:[\w.]+\.)?(\w+)(?:<[^>]*>)?\(\s*\"([a-z0-9-]+)\"\s*\)")
CATEGORY_RE = re.compile(r"Category\.(\w+)")
TAG_KEY_RE = re.compile(r"^database-tag\.(\w+)\s*=\s*(.+)$", re.M)

# Categories that exist in Blocks.java but are not database tags.
EXTRA_LABELS = {"core": "核心", "misc": "杂项"}


def download(url: str, cache: Path) -> str:
    if cache.is_file():
        return cache.read_text(encoding="utf-8", errors="replace")
    req = urllib.request.Request(url, headers={"User-Agent": "blueprints-site/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        text = resp.read().decode("utf-8", "replace")
    cache.write_text(text, encoding="utf-8")
    return text


def parse_blocks(text: str) -> dict[str, str]:
    lines = text.splitlines()
    result: dict[str, str] = {}
    for i, line in enumerate(lines):
        for m in NEW_RE.finditer(line):
            _field, _cls, block_id = m.groups()
            found = CATEGORY_RE.search(line)
            if not found:
                depth = line.count("{") - line.count("}")
                j = i + 1
                while j < len(lines) and depth > 0:
                    found = CATEGORY_RE.search(lines[j])
                    if found:
                        break
                    depth += lines[j].count("{") - lines[j].count("}")
                    j += 1
            if found:
                result.setdefault(block_id, found.group(1))
    return result


def parse_labels(bundle: str) -> dict[str, str]:
    labels = dict(EXTRA_LABELS)
    for name, value in TAG_KEY_RE.findall(bundle):
        labels[name] = value.strip()
    return labels


def coverage(blocks: dict[str, str]) -> None:
    index = ROOT / "index.json"
    if not index.is_file():
        return
    data = json.loads(index.read_text(encoding="utf-8"))
    used: dict[str, int] = {}
    for bp in data.get("blueprints", []):
        for item in bp.get("blocks", []):
            used[item["block"]] = used.get(item["block"], 0) + item["count"]
    known = [b for b in used if b in blocks]
    unknown = sorted((b for b in used if b not in blocks), key=lambda b: -used[b])
    total = sum(used.values())
    covered = sum(used[b] for b in known)
    print(f"coverage: {len(known)}/{len(used)} distinct blocks, "
          f"{covered}/{total} placed blocks ({covered * 100 // max(total, 1)}%)")
    if unknown:
        print("unmapped (top 20): " + ", ".join(f"{b}×{used[b]}" for b in unknown[:20]))
    counts: dict[str, int] = {}
    for item_block, n in used.items():
        cat = blocks.get(item_block)
        if cat:
            counts[cat] = counts.get(cat, 0) + n
    print("by category: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", help="local Blocks.java instead of downloading")
    parser.add_argument("--bundle", help="local bundle_zh_CN.properties instead of downloading")
    parser.add_argument("--check", action="store_true", help="report coverage, write nothing")
    args = parser.parse_args()

    text = Path(args.file).read_text(encoding="utf-8", errors="replace") if args.file \
        else download(DEFAULT_URL, DATA / "Blocks.java.txt")
    bundle = Path(args.bundle).read_text(encoding="utf-8", errors="replace") if args.bundle \
        else download(BUNDLE_URL, BUNDLE_PATH)

    blocks = parse_blocks(text)
    labels = parse_labels(bundle)
    print(f"parsed {len(blocks)} blocks, {len(labels)} labels: "
          + ", ".join(f"{k}={v}" for k, v in labels.items()))
    coverage(blocks)
    if args.check:
        return 0

    DATA.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(dict(sorted(blocks.items())), ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    LABELS_PATH.write_text(json.dumps(dict(sorted(labels.items())), ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(ROOT)} and {LABELS_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
