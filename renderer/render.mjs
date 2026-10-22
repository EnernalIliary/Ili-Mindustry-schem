// 用 mindustry-schematic-parser 渲染蓝图预览，并产出材料清单/电力收支。
// 用法: node render.mjs <inDir> <outDir> [--png] [--extra out.json]
import fs from "node:fs";
import path from "node:path";
import { Schematic } from "mindustry-schematic-parser";

const args = process.argv.slice(2);
const [inDir, outDir] = args;
const wantPng = args.includes("--png");
const extraIdx = args.indexOf("--extra");
const extraOut = extraIdx >= 0 ? args[extraIdx + 1] : null;
const limitIdx = args.indexOf("--limit");
const limit = limitIdx >= 0 ? parseInt(args[limitIdx + 1], 10) : 0;
// 超过阈值就跳过（像素画类蓝图会把内存吃光，1.8G 的机器上必须挡掉）
const maxTilesIdx = args.indexOf("--max-tiles");
const MAX_TILES = maxTilesIdx >= 0 ? parseInt(args[maxTilesIdx + 1], 10) : 20000;
const maxBytesIdx = args.indexOf("--max-bytes");
const MAX_BYTES = maxBytesIdx >= 0 ? parseInt(args[maxBytesIdx + 1], 10) : 400000;

const all = fs
  .readdirSync(inDir, { withFileTypes: true })
  .filter((d) => d.isDirectory())
  .map((d) => d.name)
  .sort();
const slugs = limit > 0 ? all.slice(0, limit) : all;

const extra = {};
let ok = 0;
const failed = [];
const skipped = [];

for (const slug of slugs) {
  const file = path.join(inDir, slug, "blueprint.txt");
  if (!fs.existsSync(file)) continue;
  try {
    const size = fs.statSync(file).size;
    if (size > MAX_BYTES) {
      skipped.push([slug, `file ${Math.round(size / 1024)}KiB > ${Math.round(MAX_BYTES / 1024)}KiB`]);
      continue;
    }
    const b64 = fs.readFileSync(file, "utf8").trim();
    const sch = Schematic.decode(b64);

    // requirements 是 getter，返回 { 物品id: 数量 }
    const reqMap = sch.requirements || {};
    const req = Object.entries(reqMap).map(([item, amount]) => ({ item, amount }));
    const power = sch.powerBalance;
    extra[slug] = {
      requirements: req,
      power_balance: typeof power === "number" && Number.isFinite(power) ? Math.round(power * 100) / 100 : null,
    };

    const tiles = (sch.width || 0) * (sch.height || 0);
    if (wantPng && tiles > MAX_TILES) {
      skipped.push([slug, `${sch.width}x${sch.height}=${tiles} tiles`]);
      ok += 1;
      continue;
    }

    if (wantPng) {
      const canvas = await sch.render({ background: false });
      const buf = canvas.toBuffer("image/png");
      fs.mkdirSync(path.join(outDir, slug), { recursive: true });
      fs.writeFileSync(path.join(outDir, slug, "preview.png"), buf);
    }
    ok += 1;
  } catch (err) {
    failed.push([slug, String(err && err.message ? err.message : err).slice(0, 160)]);
  }
  if (ok % 50 === 0) {
    const mb = Math.round(process.memoryUsage().rss / 1048576);
    process.stderr.write(`progress ${ok}/${slugs.length} rss=${mb}MB\n`);
  }
}

if (extraOut) fs.writeFileSync(extraOut, JSON.stringify(extra, null, 2) + "\n");

console.log(JSON.stringify({
  total: slugs.length,
  ok,
  failed: failed.length,
  skipped: skipped.length,
  sample_failed: failed.slice(0, 5),
  sample_skipped: skipped.slice(0, 8),
}));
