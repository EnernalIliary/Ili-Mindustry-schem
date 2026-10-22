"""Minimal Mindustry schematic (.msch) codec.

Only what a static gallery needs: read a blueprint copied from the game,
report its size / blocks / logic, and (for tests) write one back out.

Format (from Mindustry build 159.1, Schematics.read / write):

    'msch' | version(1 byte) | zlib(
        width:int16, height:int16,
        tagCount:uint8, tagCount*(UTF key, UTF value),
        dictLen:uint8,  dictLen*UTF block name,
        total:int32, total*{ blockIndex:int8, packedPos:int32,
                             config:TypeIO object, rotation:int8 }
    )

TypeIO object tags start at 0 (null) and are listed in TAGS below.
"""

from __future__ import annotations

import base64
import struct
import zlib

MAGIC = b"msch"
TAG_NAMES = [
    "null", "int", "long", "float", "string", "content", "int[]", "point",
    "point[]", "technode", "bool", "double", "building", "laccess", "byte[]",
    "unitcommand", "bool[]", "unit", "vec2[]", "vec2", "team", "ints",
    "object[]", "unitcommandbox",
]
CONTENT_TYPES = [
    "item", "block", "mech", "bullet", "liquid", "status", "unit", "weather",
    "effect", "sector", "loadout", "typeid", "error", "planet", "ammo", "team",
]


class MschError(Exception):
    """Raised when bytes are not a valid schematic."""


class Reader:
    """Big-endian cursor, mirroring arc's Reads."""

    __slots__ = ("data", "pos")

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def take(self, n: int) -> bytes:
        end = self.pos + n
        if end > len(self.data):
            raise MschError(f"truncated: wanted {n} bytes at {self.pos}, {len(self.data)} total")
        out = self.data[self.pos:end]
        self.pos = end
        return out

    def i8(self) -> int:
        return struct.unpack(">b", self.take(1))[0]

    def u8(self) -> int:
        return self.take(1)[0]

    def i16(self) -> int:
        return struct.unpack(">h", self.take(2))[0]

    def u16(self) -> int:
        return struct.unpack(">H", self.take(2))[0]

    def i32(self) -> int:
        return struct.unpack(">i", self.take(4))[0]

    def i64(self) -> int:
        return struct.unpack(">q", self.take(8))[0]

    def f32(self) -> float:
        return struct.unpack(">f", self.take(4))[0]

    def f64(self) -> float:
        return struct.unpack(">d", self.take(8))[0]

    def utf(self) -> str:
        return self.take(self.u16()).decode("utf-8", "replace")


def _read_object(r: Reader, depth: int = 0):
    """Consume one TypeIO object. Returns a compact python value.

    The only one the gallery cares about is byte[] (a logic block's payload);
    everything else is consumed so the cursor stays aligned.
    """
    if depth > 32:
        raise MschError("config nested too deeply")
    tag = r.i8()
    if tag == 0:
        return None
    if tag == 1:
        return r.i32()
    if tag == 2:
        return r.i64()
    if tag == 3:
        return r.f32()
    if tag == 4:
        return r.utf() if r.u8() else None
    if tag == 5:
        ctype, cid = r.u8(), r.i16()
        name = CONTENT_TYPES[ctype] if ctype < len(CONTENT_TYPES) else str(ctype)
        return {"type": name, "id": cid}
    if tag == 6:
        n = r.i16()
        _size(n)
        return [r.i32() for _ in range(n)]
    if tag == 7:
        return (r.i32(), r.i32())
    if tag == 8:
        n = r.u8()
        _size(n)
        return [_unpack(r.i32()) for _ in range(n)]
    if tag == 9:
        return {"node": (r.u8(), r.i16())}
    if tag == 10:
        return r.u8() != 0
    if tag == 11:
        return r.f64()
    if tag == 12:
        return {"building": r.i32()}
    if tag == 13:
        return {"laccess": r.i16()}
    if tag == 14:
        n = r.i32()
        _size(n, 20_000_000)
        return r.take(n)
    if tag == 15:
        r.u8()
        return None
    if tag == 16:
        n = r.i32()
        _size(n)
        return [r.u8() != 0 for _ in range(n)]
    if tag == 17:
        return {"unit": r.i32()}
    if tag == 18:
        n = r.i16()
        _size(n)
        return [(r.f32(), r.f32()) for _ in range(n)]
    if tag == 19:
        return (r.f32(), r.f32())
    if tag == 20:
        return {"team": r.u8()}
    if tag == 21:
        n = r.u16()
        _size(n)
        return [r.i32() for _ in range(n)]
    if tag == 22:
        n = r.i32()
        _size(n)
        return [_read_object(r, depth + 1) for _ in range(n)]
    if tag == 23:
        return {"cmd": r.u16()}
    raise MschError(f"unknown TypeIO tag {tag} at {r.pos - 1}")


def _size(n: int, limit: int = 1_000_000) -> None:
    if n < 0 or n > limit:
        raise MschError(f"implausible length {n}")


def _unpack(packed: int) -> tuple[int, int]:
    x = (packed >> 16) & 0xFFFF
    y = packed & 0xFFFF
    return (x - 0x10000 if x >= 0x8000 else x), (y - 0x10000 if y >= 0x8000 else y)


def _pack(x: int, y: int) -> int:
    return ((x & 0xFFFF) << 16) | (y & 0xFFFF)


def decode_logic(blob: bytes) -> dict:
    """Unpack a logic block's byte[] config into {version, lines, links}."""
    try:
        raw = zlib.decompress(blob)
    except zlib.error as exc:
        raise MschError(f"logic payload is not zlib: {exc}") from exc
    r = Reader(raw)
    version = r.u8()
    n = r.i32()
    _size(n, 100_000_000)
    code = r.take(n).decode("utf-8", "replace")
    links = []
    total = r.i32()
    _size(total, 100_000)
    if version == 0:
        for _ in range(total):
            r.i32()
    else:
        for _ in range(total):
            name = r.utf()
            links.append((name, r.i16(), r.i16()))
    lines = [ln for ln in code.split("\n") if ln.strip()]
    return {"version": version, "lines": lines, "links": links}


def parse_bytes(data: bytes) -> dict:
    """Parse raw .msch bytes into a plain dict."""
    if len(data) < 5 or data[:4] != MAGIC:
        raise MschError("not a schematic (bad magic)")
    version = data[4]
    if version > 1:
        raise MschError(f"unsupported schematic version {version}")
    try:
        raw = zlib.decompress(data[5:])
    except zlib.error as exc:
        raise MschError(f"body is not zlib: {exc}") from exc

    r = Reader(raw)
    width, height = r.i16(), r.i16()
    tags: dict[str, str] = {}
    for _ in range(r.u8()):
        key = r.utf()
        tags[key] = r.utf()

    names = [r.utf() for _ in range(r.u8())]
    total = r.i32()
    _size(total)

    tiles = []
    logic = []
    for _ in range(total):
        idx = r.i8()
        if not 0 <= idx < len(names):
            raise MschError(f"block index {idx} out of range ({len(names)} names)")
        block = names[idx]
        x, y = _unpack(r.i32())
        config = _read_object(r)
        rotation = r.i8()
        tiles.append({"block": block, "x": x, "y": y, "rot": rotation})
        if isinstance(config, bytes):
            info = decode_logic(config)
            logic.append({"x": x, "y": y, "block": block, **info})

    return {
        "version": version,
        "width": width,
        "height": height,
        "tags": tags,
        "tiles": tiles,
        "logic": logic,
    }


def parse_base64(text: str) -> dict:
    """Parse the text you copy out of the game's blueprint clipboard."""
    cleaned = "".join(text.split())
    try:
        data = base64.b64decode(cleaned, validate=False)
    except Exception as exc:  # noqa: BLE001 - surface a single clear error
        raise MschError(f"not valid base64: {exc}") from exc
    return parse_bytes(data)


# --------------------------------------------------------------------------
# writer -- used by tools/make_sample.py and the round-trip test
# --------------------------------------------------------------------------

def encode_logic(lines: list[str], links: list[tuple[str, int, int]] | None = None) -> bytes:
    code = "\n".join(lines)
    out = bytearray([1])
    payload = code.encode("utf-8")
    out += struct.pack(">i", len(payload)) + payload
    links = links or []
    out += struct.pack(">i", len(links))
    for name, x, y in links:
        nb = name.encode("utf-8")
        out += struct.pack(">H", len(nb)) + nb + struct.pack(">hh", x, y)
    return zlib.compress(bytes(out), 9)


def _write_object(out: bytearray, obj) -> None:
    if obj is None:
        out.append(0)
    elif isinstance(obj, bool):
        out += bytes([10, 1 if obj else 0])
    elif isinstance(obj, int):
        out.append(1)
        out += struct.pack(">i", obj)
    elif isinstance(obj, float):
        out.append(3)
        out += struct.pack(">f", obj)
    elif isinstance(obj, str):
        sb = obj.encode("utf-8")
        out += bytes([4, 1]) + struct.pack(">H", len(sb)) + sb
    elif isinstance(obj, (bytes, bytearray)):
        out.append(14)
        out += struct.pack(">i", len(obj)) + bytes(obj)
    else:
        raise MschError(f"cannot serialise {type(obj).__name__}")


def build_bytes(width: int, height: int, tags: dict[str, str], tiles: list[dict]) -> bytes:
    """Build .msch bytes. Each tile: {block, x, y, rot, config}."""
    body = bytearray()
    body += struct.pack(">hh", width, height)
    body.append(len(tags))
    for key, value in tags.items():
        for text in (key, value):
            sb = text.encode("utf-8")
            body += struct.pack(">H", len(sb)) + sb

    names: list[str] = []
    for tile in tiles:
        if tile["block"] not in names:
            names.append(tile["block"])
    body.append(len(names))
    for name in names:
        nb = name.encode("utf-8")
        body += struct.pack(">H", len(nb)) + nb

    body += struct.pack(">i", len(tiles))
    for tile in tiles:
        body.append(names.index(tile["block"]))
        body += struct.pack(">i", _pack(tile["x"], tile["y"]))
        _write_object(body, tile.get("config"))
        body.append(tile.get("rot", 0) & 0xFF)

    return MAGIC + b"\x01" + zlib.compress(bytes(body), 9)


def build_base64(width: int, height: int, tags: dict[str, str], tiles: list[dict]) -> str:
    return base64.b64encode(build_bytes(width, height, tags, tiles)).decode("ascii")


if __name__ == "__main__":  # quick self-check
    sample = build_base64(
        4, 3, {"name": "self-check", "description": "round trip"},
        [
            {"block": "conveyor", "x": 0, "y": 0, "rot": 0},
            {"block": "conveyor", "x": 1, "y": 0, "rot": 0},
            {"block": "logic-processor", "x": 2, "y": 0, "rot": 0,
             "config": encode_logic(["print 1"], [("switch1", 3, 0)])},
        ],
    )
    parsed = parse_base64(sample)
    assert parsed["width"] == 4 and parsed["height"] == 3
    assert parsed["tags"]["name"] == "self-check"
    assert len(parsed["tiles"]) == 3
    assert len(parsed["logic"]) == 1
    assert parsed["logic"][0]["lines"] == ["print 1"]
    assert parsed["logic"][0]["links"][0][0] == "switch1"
    print("ok", len(sample), "chars")
