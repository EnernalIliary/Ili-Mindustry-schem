"""Import Mindustry schematics from the game folder into this repo: preview + meta + push.

    python tools/import_schematics.py --src "E:\\...\\Mindustry\\saves\\schematics"

For every .msch it writes blueprints/<slug>/{blueprint.txt,preview.png,meta.json},
rebuilds index.json, commits, and pushes. Re-running is incremental: a blueprint
whose content hash did not change is left alone.

Push goes through `git push` first; if that fails (github.com blocked) and a token
is available it falls back to the GitHub REST API (api.github.com is reachable when
github.com is not). Token lookup: --token, $GITHUB_TOKEN / $GH_TOKEN, or .github-token.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_index  # noqa: E402
import category_tags  # noqa: E402
import msch_min  # noqa: E402
import preview as preview_mod  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BLUEPRINT_DIR = ROOT / "blueprints"
SIZES_PATH = Path(__file__).resolve().parent / "data" / "block_sizes.json"

# content tags -------------------------------------------------------------
# 标签一律用游戏内的建筑分类（炮塔/生产/运输/流体/电力/防御/制造/单位/功能），
# 由 blueprint 里实际放置的方块决定，见 tools/category_tags.py。


def content_tags(sch: dict) -> list[str]:
    tags, _ = category_tags.blueprint_tags(sch)
    return tags

SLUG_KEEP = set("abcdefghijklmnopqrstuvwxyz0123456789")


def slugify(name: str, source_key: str) -> str:
    """Readable ASCII part + stable hash of the *source file*, so two files that
    happen to share a display name never overwrite each other."""
    ascii_part = "".join(c if c in SLUG_KEEP else "-" for c in name.lower())
    while "--" in ascii_part:
        ascii_part = ascii_part.replace("--", "-")
    ascii_part = ascii_part.strip("-")[:40]
    digest = hashlib.sha1(source_key.encode("utf-8")).hexdigest()[:6]
    if len(ascii_part) < 3:
        ascii_part = "bp"
    return f"{ascii_part}-{digest}"


def load_sizes() -> dict[str, int]:
    if SIZES_PATH.is_file():
        try:
            return {str(k): int(v) for k, v in json.loads(SIZES_PATH.read_text(encoding="utf-8")).items()}
        except (ValueError, TypeError):
            pass
    return {}


def read_schematic(path: Path) -> tuple[str, dict]:
    """Game files are binary .msch; the repo stores the base64 text form.

    A few schematics carry byte[] configs that are not zlib-compressed logic
    (older mods, other tools). Those blocks still render; only the logic text is
    dropped, instead of losing the whole blueprint.
    """
    data = path.read_bytes()
    if data[:4] == msch_min.MAGIC:
        text = base64.b64encode(data).decode("ascii")
        try:
            return text, msch_min.parse_bytes(data)
        except msch_min.MschError as exc:
            if "logic payload" not in str(exc):
                raise
            return text, _lenient_parse(lambda: msch_min.parse_bytes(data))
    text = data.decode("utf-8-sig", "replace").strip()
    try:
        return text, msch_min.parse_base64(text)
    except msch_min.MschError as exc:
        if "logic payload" not in str(exc):
            raise
        return text, _lenient_parse(lambda: msch_min.parse_base64(text))


def _lenient_parse(parse) -> dict:
    """Re-parse with logic decoding disabled (byte[] configs that are not zlib)."""
    original = msch_min.decode_logic
    msch_min.decode_logic = lambda blob: {"version": 0, "lines": [], "links": []}
    try:
        return parse()
    finally:
        msch_min.decode_logic = original


def clean_name(stem: str) -> str:
    name = " ".join(stem.replace("_", " ").split()).strip(" .-")
    return name or stem


def import_one(path: Path, author: str, sizes: dict[str, int], force: bool,
               dry_run: bool = False) -> tuple[str, str]:
    """Returns (slug, status) where status is created / updated / unchanged / error."""
    text, sch = read_schematic(path)
    if not sch["tiles"] or sch["width"] <= 0 or sch["height"] <= 0:
        return "", "error: no blocks"

    name = str(sch["tags"].get("name") or "").strip() or clean_name(path.stem)
    description = str(sch["tags"].get("description") or "").strip()
    slug = slugify(name, path.stem)
    folder = BLUEPRINT_DIR / slug
    target = folder / "blueprint.txt"

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if target.is_file() and not force:
        if hashlib.sha256(target.read_text(encoding="utf-8-sig").strip().encode("utf-8")).hexdigest() == digest:
            return slug, "unchanged"
        status = "updated"
    else:
        status = "created"

    if dry_run:
        preview_mod.render(sch, sizes)  # proves the render path works, writes nothing
        return slug, status
    folder.mkdir(parents=True, exist_ok=True)
    target.write_text(text + "\n", encoding="utf-8")
    (folder / "preview.png").write_bytes(preview_mod.render(sch, sizes))

    stamp = datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()
    if not description:
        bits = [f"{sch['width']}×{sch['height']}", f"{len(sch['tiles'])} 个方块"]
        if sch["logic"]:
            bits.append(f"逻辑 {sum(len(e['lines']) for e in sch['logic'])} 行")
        description = "，".join(bits) + "。从游戏内蓝图导入。"

    meta = {
        "name": name,
        "author": author,
        "description": description,
        "tags": content_tags(sch),
        "created": stamp,
        "updated": stamp,
    }
    (folder / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return slug, status


# --------------------------------------------------------------------------
# publishing
# --------------------------------------------------------------------------

def git(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=check)


def repo_slug() -> str:
    url = git("remote", "get-url", "origin").stdout.strip()
    if url.endswith(".git"):
        url = url[:-4]
    for marker in ("github.com:", "github.com/"):
        if marker in url:
            return url.split(marker, 1)[1].strip("/")
    return ""


def find_token(explicit: str | None) -> str:
    if explicit:
        return explicit.strip()
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(key, "").strip():
            return os.environ[key].strip()
    for candidate in (ROOT / ".github-token", Path.home() / ".github-token"):
        if candidate.is_file():
            text = candidate.read_text(encoding="utf-8").strip()
            if text:
                return text
    return ""


def api(slug: str, token: str, method: str, path: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(f"https://api.github.com/repos/{slug}{path}", data=body, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if body:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_commit(slug: str, token: str, message: str) -> str:
    """Create one commit containing every working-tree change, via the REST API."""
    status = git("status", "--porcelain").stdout
    added: dict[str, str | None] = {}
    for line in status.splitlines():
        if not line.strip():
            continue
        code, _, path = line[:2], line[2], line[3:].strip().strip('"')
        if code.strip() == "D":
            added[path] = None
            continue
        full = ROOT / path
        if full.is_file():
            added[path] = base64.b64encode(full.read_bytes()).decode("ascii")
    if not added:
        return ""

    ref = api(slug, token, "GET", "/git/ref/heads/main")
    head = ref["object"]["sha"]
    base_tree = api(slug, token, "GET", f"/git/commits/{head}")["tree"]["sha"]

    tree = []
    for path, encoded in added.items():
        if encoded is None:
            tree.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
            continue
        blob = api(slug, token, "POST", "/git/blobs", {"content": encoded, "encoding": "base64"})
        tree.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    new_tree = api(slug, token, "POST", "/git/trees", {"base_tree": base_tree, "tree": tree})
    commit = api(slug, token, "POST", "/git/commits",
                 {"message": message, "tree": new_tree["sha"], "parents": [head]})
    api(slug, token, "PATCH", "/git/refs/heads/main", {"sha": commit["sha"], "force": False})
    return commit["sha"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", required=True, help="folder holding .msch files")
    parser.add_argument("--author", default="Iliary", help="author written into meta.json")
    parser.add_argument("--limit", type=int, default=0, help="only the first N files (debugging)")
    parser.add_argument("--dry-run", action="store_true", help="parse and render, write nothing")
    parser.add_argument("--no-push", action="store_true", help="commit locally, skip push")
    parser.add_argument("--force", action="store_true", help="rewrite files even if unchanged")
    parser.add_argument("--token", default=None, help="GitHub token for the API push fallback")
    args = parser.parse_args()

    src = Path(args.src)
    if not src.is_dir():
        print(f"error: {src} is not a folder", file=sys.stderr)
        return 2
    files = sorted(p for p in src.iterdir() if p.suffix.lower() == ".msch" and p.is_file())
    if args.limit:
        files = files[:args.limit]
    if not files:
        print("error: no .msch files found", file=sys.stderr)
        return 2

    sizes = load_sizes()
    counts = {"created": 0, "updated": 0, "unchanged": 0, "error": 0}
    problems: list[str] = []
    for path in files:
        try:
            slug, status = import_one(path, args.author, sizes, args.force, args.dry_run)
        except (msch_min.MschError, OSError, ValueError) as exc:
            counts["error"] += 1
            problems.append(f"{path.name}: {exc}")
            continue
        counts[status.split(":")[0]] = counts.get(status.split(":")[0], 0) + 1
        if status.startswith("error"):
            problems.append(f"{path.name}: {status}")
    print(f"scanned {len(files)}: " + ", ".join(f"{k} {v}" for k, v in counts.items() if v))
    for line in problems[:10]:
        print(f"  ! {line}")
    if args.dry_run:
        print("dry run: nothing written")
        return 0

    saved_argv = sys.argv
    sys.argv = ["build_index.py"]
    try:
        build_index.main()  # regenerates index.json from blueprints/
    finally:
        sys.argv = saved_argv
    changed = git("status", "--porcelain").stdout.strip()
    if not changed:
        print("nothing to commit")
        return 0

    git("add", "-A")
    message = f"import: 从游戏导入 {counts['created'] + counts['updated']} 张蓝图（{date.today().isoformat()}）"
    commit = git("-c", "user.name=Iliary", "-c", "user.email=iliary@outlook.com", "commit", "-m", message)
    if commit.returncode != 0:
        print(f"error: git commit failed\n{commit.stderr}", file=sys.stderr)
        return 1
    print(f"committed: {git('log', '--oneline', '-1').stdout.strip()}")

    if args.no_push:
        print("--no-push: stopping before push")
        return 0

    push = git("push", "origin", "HEAD:main")
    if push.returncode == 0:
        print("pushed via git")
        return 0

    print(f"git push failed: {push.stderr.strip().splitlines()[-1] if push.stderr.strip() else '?'}")
    token = find_token(args.token)
    slug = repo_slug()
    if not token or not slug:
        print("no token and/or repo slug: run again with --token, or push by hand later", file=sys.stderr)
        return 3
    try:
        sha = api_commit(slug, token, message)
    except urllib.error.HTTPError as exc:
        print(f"error: api push failed: {exc.code} {exc.read()[:200]!r}", file=sys.stderr)
        return 1
    print(f"pushed via api: {sha[:7]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
