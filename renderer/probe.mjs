// 探查 mindustry-schematic-parser 的 Schematic API
import fs from "node:fs";
import path from "node:path";
import { Schematic } from "mindustry-schematic-parser";

const dir = "/www/blueprints-src/blueprints";
const slug = fs.readdirSync(dir).find((d) => fs.existsSync(path.join(dir, d, "blueprint.txt")));
const text = fs.readFileSync(path.join(dir, slug, "blueprint.txt"), "utf8").trim();
const sch = Schematic.decode(text);

const ownProps = Object.keys(sch);
const protoProps = Object.getOwnPropertyNames(Object.getPrototypeOf(sch));
console.log("slug:", slug);
console.log("static:", Object.getOwnPropertyNames(Schematic).slice(0, 40));
console.log("own:", ownProps.slice(0, 60));
console.log("proto:", protoProps.slice(0, 60));

for (const key of ["requirements", "powerBalance", "tiles", "width", "height", "name", "description", "labels", "tags"]) {
  const v = sch[key];
  console.log(`prop ${key}:`, typeof v, Array.isArray(v) ? `array(${v.length})` : typeof v === "object" && v ? Object.keys(v).slice(0, 8) : String(v).slice(0, 80));
}

const t0 = sch.tiles?.[0];
if (t0) {
  console.log("tile0 keys:", Object.keys(t0));
  console.log("tile0 block:", typeof t0.block, t0.block && Object.keys(t0.block).slice(0, 12));
  console.log("tile0 block name:", t0.block?.name, "req:", typeof t0.block?.requirements);
}

const opts = Schematic.render?.length; // 看看 render 签名
console.log("render arity:", opts, typeof Schematic.prototype?.render);
