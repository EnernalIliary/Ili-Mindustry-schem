"""Render a Mindustry schematic to a PNG preview, no third-party deps.

Mindustry ships sprites, not colours we can read from a .msch, so the preview is
a *schematic map*: every block is drawn as its footprint, coloured by kind
(logistics / turret / power / logic / unit ...), with a deterministic hue for
anything the table below does not know. Readable at a glance, honest about
being a diagram rather than a screenshot.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

# (substring matchers, rgb) -- first match wins, order matters.
PALETTE: list[tuple[tuple[str, ...], tuple[int, int, int]]] = [
    (("core-",), (232, 196, 106)),                     # cores
    (("wall", "door", "gate", "shield", "mender", "overdrive", "force-projector"), (128, 132, 142)),
    (("conveyor", "junction", "router", "sorter", "duct", "unloader", "mass-driver"), (150, 158, 168)),
    (("conduit", "tank", "pump", "valve", "liquid", "impulse-pump", "rotary-pump"), (86, 150, 214)),
    (("drill", "bore", "cultivator", "excavator", "water-extractor"), (206, 142, 74)),
    (("smelter", "kiln", "press", "mixer", "compressor", "incinerator", "separator",
      "disassembler", "pulverizer", "centrifuge", "melter", "cryofluid", "coal-centrifuge"), (198, 118, 60)),
    (("solar", "battery", "reactor", "generator", "combustion", "thermal", "differential",
      "power-node", "power-source", "beam-node", "beam-tower", "beam-link", "diode"), (226, 190, 70)),
    (("duo", "scatter", "scorch", "hail", "wave", "lancer", "arc", "cyclone", "fuse", "ripple",
      "meltdown", "salvo", "segment", "tsunami", "foreshadow", "spectre", "swarmer", "parallax",
      "breach", "diffuse", "sublimate", "titan", "disperse", "afflict", "lustre", "scathe",
      "smite", "malign", "radar"), (212, 92, 92)),
    (("reconstructor", "factory", "assembler", "ship", "mech", "tank", "refabricator"), (150, 120, 200)),
    (("logic-", "processor", "memory-", "switch", "message", "display", "effect", "canvas"), (110, 200, 150)),
    (("container", "vault", "storage"), (168, 150, 112)),
    (("sand", "water", "stone", "floor", "ore-", "boulder"), (70, 76, 86)),
    (("enemy", "spawn", "guardian", "boss"), (180, 70, 120)),
]


def color_for(block: str, sizes: dict[str, int]) -> tuple[int, int, int]:
    name = block.lower()
    for matchers, rgb in PALETTE:
        if any(m in name for m in matchers):
            return rgb
    # deterministic fallback: spread hues over the name hash
    h = int(hashlib.sha1(name.encode("utf-8")).hexdigest()[:6], 16)
    hue = (h % 360) / 360.0
    return _hsl(hue, 0.45, 0.55)


def _hsl(h: float, s: float, l: float) -> tuple[int, int, int]:
    def f(n: float) -> float:
        k = (n + h * 12) % 12
        a = s * min(l, 1 - l)
        return l - a * max(-1, min(k - 3, 9 - k, 1))

    return tuple(int(round(255 * f(n))) for n in (0, 8, 4))  # type: ignore[return-value]


def _shade(rgb: tuple[int, int, int], k: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(c * k))) for c in rgb)  # type: ignore[return-value]


class Canvas:
    """Tiny RGB canvas that writes PNG by hand."""

    def __init__(self, width: int, height: int, fill: tuple[int, int, int] = (22, 24, 28)) -> None:
        self.w, self.h = width, height
        self.px = bytearray(bytes(fill) * (width * height))

    def rect(self, x0: int, y0: int, x1: int, y1: int, rgb: tuple[int, int, int]) -> None:
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(self.w, x1), min(self.h, y1)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(rgb) * (x1 - x0)
        for y in range(y0, y1):
            start = (y * self.w + x0) * 3
            self.px[start:start + len(row)] = row

    def png(self) -> bytes:
        raw = bytearray()
        stride = self.w * 3
        for y in range(self.h):
            raw.append(0)  # filter: none
            raw += self.px[y * stride:(y + 1) * stride]

        def chunk(tag: bytes, data: bytes) -> bytes:
            return (struct.pack(">I", len(data)) + tag + data
                    + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

        return (b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
                + chunk(b"IEND", b""))


def render(sch: dict, sizes: dict[str, int], max_side: int = 512, pad: int = 6) -> bytes:
    """Render a parsed schematic (see msch_min.parse_base64) to PNG bytes."""
    w, h = int(sch.get("width") or 0), int(sch.get("height") or 0)
    if w <= 0 or h <= 0:
        raise ValueError("schematic has no size")
    cell = max(2, min(28, (max_side - 2 * pad) // max(w, h)))
    cv = Canvas(w * cell + 2 * pad, h * cell + 2 * pad)

    # faint grid so sparse builds still read as a grid
    if cell >= 8:
        grid = (32, 35, 40)
        for x in range(w + 1):
            cv.rect(pad + x * cell, pad, pad + x * cell + 1, pad + h * cell, grid)
        for y in range(h + 1):
            cv.rect(pad, pad + y * cell, pad + w * cell, pad + y * cell + 1, grid)

    for tile in sch.get("tiles", []):
        block = tile["block"]
        size = int(sizes.get(block, 1) or 1)
        rgb = color_for(block, sizes)
        x0 = pad + tile["x"] * cell
        y0 = pad + tile["y"] * cell
        x1 = pad + min(w, tile["x"] + size) * cell
        y1 = pad + min(h, tile["y"] + size) * cell
        cv.rect(x0, y0, x1, y1, rgb)
        if cell >= 6:
            cv.rect(x0, y0, x1, y0 + 1, _shade(rgb, 1.35))
            cv.rect(x0, y1 - 1, x1, y1, _shade(rgb, 0.55))
            cv.rect(x0, y0, x0 + 1, y1, _shade(rgb, 1.2))
            cv.rect(x1 - 1, y0, x1, y1, _shade(rgb, 0.55))

    # logic blocks get a marker so "has logic" is visible without opening the card
    for entry in sch.get("logic", []):
        if cell >= 6:
            x0 = pad + entry["x"] * cell + cell // 2
            y0 = pad + entry["y"] * cell + cell // 2
            cv.rect(x0 - 1, y0 - 1, x0 + 2, y0 + 2, (245, 245, 245))

    return cv.png()
