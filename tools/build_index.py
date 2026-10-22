#!/usr/bin/env python3
"""Scan blueprints/ and emit index.json for the gallery page.

Run from anywhere:

    python3 tools/build_index.py            # write index.json
    python3 tools/build_index.py --check    # validate only, write nothing

Exit code 1 means the repo is not publishable (bad blueprint, missing field).
The site never parses blueprints at runtime -- it reads index.json only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import category_tags  # noqa: E402
import msch_min  # noqa: E402
import schem_labels  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BLUEPRINT_DIR = ROOT / "blueprints"
INDEX_PATH = ROOT / "index.json"
EXTRA_PATH = ROOT / "tools" / "data" / "blueprint_extra.json"

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
REQUIRED_FIELDS = ("name", "author", "description")
MAX_PREVIEW_BYTES = 4 * 1024 * 1024


class Problem(Exception):
    """A blueprint that cannot be published."""


def load_meta(folder: Path) -> dict:
    path = folder / "meta.json"
    if not path.is_file():
        raise Problem("missing meta.json")
    try:
        meta = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise Problem(f"meta.json is not valid JSON: {exc}") from exc
    if not isinstance(meta, dict):
        raise Problem("meta.json must be a JSON object")
    missing = [k for k in REQUIRED_FIELDS if not str(meta.get(k, "")).strip()]
    if missing:
        raise Problem(f"meta.json missing {', '.join(missing)}")
    tags = meta.get("tags", [])
    if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
        raise Problem("meta.json tags must be a list of strings")
    for key in ("created", "updated"):
        value = meta.get(key)
        if value is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value)):
            raise Problem(f"meta.json {key} must be YYYY-MM-DD")
    return meta


def load_blueprint(folder: Path) -> tuple[str, dict]:
    path = folder / "blueprint.txt"
    if not path.is_file():
        raise Problem("missing blueprint.txt")
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        raise Problem("blueprint.txt is empty")
    try:
        sch = msch_min.parse_base64(text)
    except msch_min.MschError as exc:
        if "logic payload" not in str(exc):
            raise Problem(f"blueprint.txt does not decode: {exc}") from exc
        sch = msch_min.parse_base64_lenient(text)
    if sch["width"] <= 0 or sch["height"] <= 0:
        raise Problem(f"blueprint has invalid size {sch['width']}x{sch['height']}")
    if not sch["tiles"]:
        raise Problem("blueprint has no blocks")
    return text, sch


def repo_url() -> str:
    """Public URL of the repo, used by the page's "view source" link."""
    explicit = os.environ.get("BLUEPRINT_REPO_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    slug = os.environ.get("GITHUB_REPOSITORY", "").strip()
    return f"https://github.com/{slug}" if "/" in slug else ""


def load_extra() -> dict:
    """渲染器顺带产出的材料清单与电力收支（可选，按 slug 索引）。"""
    if not EXTRA_PATH.is_file():
        return {}
    try:
        data = json.loads(EXTRA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def block_summary(sch: dict) -> list[dict]:
    counts: dict[str, int] = {}
    for tile in sch["tiles"]:
        counts[tile["block"]] = counts.get(tile["block"], 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"block": name, "count": n} for name, n in ordered[:8]]


def collect(folder: Path, extra: dict | None = None) -> dict:
    slug = folder.name
    if not SLUG_RE.match(slug):
        raise Problem("folder name must be lowercase letters, digits and dashes")

    meta = load_meta(folder)
    text, sch = load_blueprint(folder)

    preview = folder / "preview.png"
    has_preview = preview.is_file()
    if has_preview and preview.stat().st_size > MAX_PREVIEW_BYTES:
        raise Problem(f"preview.png is {preview.stat().st_size // 1024} KiB, limit is 4 MiB")

    logic = sch["logic"]
    name = str(meta["name"]).strip()
    description = str(meta["description"]).strip()
    tags, category = category_tags.blueprint_tags(sch)
    _, labels = category_tags._tables()
    if not tags:
        # 全是模组方块、游戏内分类表里查不到的蓝图，归到「其他」，页面上不至于没有标签。
        tags, category = ["其他"], "other"

    # 游戏内自己打的标签（蓝图文件 tags['labels']），这才是「按游戏来」的那套。
    game_labels = schem_labels.parse_labels((sch.get("tags") or {}).get("labels", ""))
    # 数字标签（1..9 / 10~19 / 20~29 / 极多）其实指「生效工厂总数」，单独拆出来当筛选项。
    factory, game_labels = schem_labels.split_factory(game_labels)
    info = (extra or {}).get(slug) or {}

    return {
        "slug": slug,
        "name": name,
        "author": str(meta["author"]).strip(),
        "description": description,
        "labels": game_labels,
        "factory": factory,
        "tags": tags,
        "category": category,
        "category_label": labels.get(category, ""),
        "requirements": info.get("requirements") or [],
        "power_balance": info.get("power_balance"),
        "game_version": str(meta.get("game_version", "")).strip(),
        "width": sch["width"],
        "height": sch["height"],
        "tiles": len(sch["tiles"]),
        "logic_blocks": len(logic),
        "logic_lines": sum(len(entry["lines"]) for entry in logic),
        "blocks": block_summary(sch),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        "chars": len(text),
        "has_preview": has_preview,
        "created": str(meta.get("created") or ""),
        "updated": str(meta.get("updated") or meta.get("created") or ""),
        "file": f"data/{slug}/blueprint.txt",
        "preview": f"data/{slug}/preview.png" if has_preview else None,
        # 仓库内的原始路径：浏览器直连 GitHub 取文件时用这套（站点镜像路径是 data/…）。
        "source": f"{BLUEPRINT_DIR.name}/{slug}/blueprint.txt",
        "source_preview": f"{BLUEPRINT_DIR.name}/{slug}/preview.png" if has_preview else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate only, do not write")
    args = parser.parse_args()

    if not BLUEPRINT_DIR.is_dir():
        print(f"error: {BLUEPRINT_DIR} does not exist", file=sys.stderr)
        return 1

    entries: list[dict] = []
    problems: list[str] = []
    extra = load_extra()

    for folder in sorted(BLUEPRINT_DIR.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        try:
            entries.append(collect(folder, extra))
        except Problem as exc:
            problems.append(f"{folder.name}: {exc}")
        except msch_min.MschError as exc:
            problems.append(f"{folder.name}: {exc}")

    seen = {}
    for entry in entries:
        if entry["slug"] in seen:
            problems.append(f"duplicate slug {entry['slug']}")
        seen[entry["slug"]] = entry

    if problems:
        print(f"{len(problems)} problem(s) found:", file=sys.stderr)
        for line in problems:
            print(f"  - {line}", file=sys.stderr)
        return 1

    # 游戏里有一张 1×1 的「000标签排序」蓝图，它的 labels 就是标签显示顺序的母版：
    # 只拿它定顺序，本身不进列表。
    order_entry = next(
        (e for e in entries if e["name"].startswith("000") and e["tiles"] <= 4), None
    )
    label_order = list(order_entry["labels"]) if order_entry else []
    if order_entry:
        entries = [e for e in entries if e is not order_entry]

    entries.sort(key=lambda e: (e["created"] or "", e["name"]), reverse=True)

    category_counts: dict[str, int] = {}
    label_counts: dict[str, int] = {}
    factory_counts: dict[str, int] = {}
    for entry in entries:
        for label in entry["tags"]:
            category_counts[label] = category_counts.get(label, 0) + 1
        for label in entry["labels"]:
            label_counts[label] = label_counts.get(label, 0) + 1
        if entry["factory"]:
            factory_counts[entry["factory"]] = factory_counts.get(entry["factory"], 0) + 1

    tags = category_counts  # kept under both names: the page reads "categories"
    _, labels = category_tags._tables()
    key_by_label = {v: k for k, v in labels.items()}
    # 生效工厂总数：按 1..9 → 区间 → 极多 的固定顺序输出，页面下拉照这个顺序排。
    factory_entries = [
        {"name": name, "count": factory_counts[name]}
        for name in schem_labels.FACTORY_ORDER
        if name in factory_counts
    ]

    # 标签按「000标签排序」那张蓝图的顺序排，母版里没有的排最后（按出现次数）。
    rank = {name: i for i, name in enumerate(label_order)}
    label_entries = [
        {"name": name, "count": count}
        for name, count in sorted(
            label_counts.items(), key=lambda kv: (rank.get(kv[0], len(rank)), -kv[1], kv[0])
        )
    ]

    index = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo": repo_url(),
        "count": len(entries),
        "label_order": label_order,
        "labels": label_entries,
        "factories": factory_entries,
        "tags": [{"name": k, "count": v} for k, v in sorted(tags.items(), key=lambda kv: (-kv[1], kv[0]))],
        "categories": [
            {"key": key_by_label.get(name, name), "name": name, "count": count}
            for name, count in sorted(category_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "logic": {
            "max_lines": max((e["logic_lines"] for e in entries), default=0),
            "with_logic": sum(1 for e in entries if e["logic_lines"] > 0),
        },
        "blueprints": entries,
    }
    payload = json.dumps(index, ensure_ascii=False, indent=2) + "\n"

    if args.check:
        print(f"ok: {len(entries)} blueprint(s) valid, nothing written")
        return 0

    INDEX_PATH.write_text(payload, encoding="utf-8")
    print(f"wrote {INDEX_PATH.relative_to(ROOT)}: {len(entries)} blueprint(s), {len(tags)} tag(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
