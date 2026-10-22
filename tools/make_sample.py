#!/usr/bin/env python3
"""Generate a small demo blueprint, used to smoke-test the pipeline.

    python3 tools/make_sample.py

Writes blueprints/example-copper-line/blueprint.txt. Delete that folder once
you have real blueprints.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import msch_min  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "blueprints" / "example-copper-line"

LOGIC = [
    'print "copper in core: "',
    "sensor total = core1 @copper",
    "print total",
    "printflush message1",
]

TILES = [
    {"block": "conveyor", "x": 1, "y": 1, "rot": 0},
    {"block": "conveyor", "x": 2, "y": 1, "rot": 0},
    {"block": "conveyor", "x": 3, "y": 1, "rot": 0},
    {"block": "router", "x": 4, "y": 1, "rot": 0},
    {"block": "conveyor", "x": 4, "y": 2, "rot": 1},
    {"block": "conveyor", "x": 0, "y": 1, "rot": 0},
    {"block": "mechanical-drill", "x": 0, "y": 1, "rot": 0},
    {"block": "logic-processor", "x": 2, "y": 0, "rot": 0,
     "config": msch_min.encode_logic(LOGIC, [("core1", 0, 3), ("message1", 3, 0)])},
    {"block": "message", "x": 3, "y": 0, "rot": 0},
    {"block": "core-shard", "x": 5, "y": 1, "rot": 0},
]

TAGS = {
    "name": "铜矿示例产线",
    "description": "示例蓝图：钻头 -> 传送带 -> 路由器，附带一个把核心铜量打印到信息板的小处理器。",
}


def main() -> int:
    text = msch_min.build_base64(6, 4, TAGS, TILES)
    TARGET.mkdir(parents=True, exist_ok=True)
    (TARGET / "blueprint.txt").write_text(text + "\n", encoding="utf-8")
    print(f"wrote {(TARGET / 'blueprint.txt').relative_to(ROOT)} ({len(text)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
