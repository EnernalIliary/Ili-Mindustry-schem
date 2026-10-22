# Mindustry 蓝图库

`https://iliary.life/blueprints/` 的数据源。**只改这个仓库，站点 10 分钟内自动更新。**

```
blueprints/
  <slug>/                 # 小写字母、数字、连字符，比如 copper-line
    meta.json             # 名称、作者、描述、标签
    blueprint.txt          # 游戏里复制出来的那串字符，原样贴进去
    preview.png            # 可选，截图；没有就显示占位块
index.json                 # 自动生成，不要手改
site/                      # 页面本体（index.html / app.js / style.css）
tools/                     # 校验与生成脚本
```

## 加一张蓝图

1. 游戏里框选 → 复制蓝图（那串 `bXNjaAF4n...`）。
2. 新建 `blueprints/<slug>/`，放两个文件：

   `blueprint.txt`
   ```
   bXNjaAF4nGNgZmBmYGBgZmDgBgABAgEAAAA...（原样粘贴，一行就行）
   ```

   `meta.json`
   ```json
   {
     "name": "铜铅混采阵列",
     "author": "Iliary",
     "description": "一句话说清它干什么、怎么用。",
     "tags": ["生产", "钻头"],
     "game_version": "146",
     "created": "2026-10-22",
     "updated": "2026-10-22"
   }
   ```

3. 想放预览图就再加 `preview.png`（≤ 4 MiB，建议 800×600 以内）。
4. commit & push。Actions 会校验蓝图能否解析、字段是否齐全，然后重写 `index.json`。

如果校验失败，Action 会红叉并打印原因（`meta.json` 缺字段、蓝图解析不了、文件夹名不合规），页面不会更新。

## 一键导入游戏里的蓝图（推荐）

游戏存档里的 `.msch` 直接批量搬进来，自动生成配色预览图、标签、尺寸，然后 commit + push：

双击 `import-schematics.cmd`，或者：

```bash
python tools/import_schematics.py --src "E:\Program Files (x86)\Steam\steamapps\common\Mindustry\saves\schematics"
```

| 参数 | 作用 |
| --- | --- |
| `--src <目录>` | `.msch` 所在目录（必填；`.cmd` 里没给参数时用上面那个默认路径） |
| `--no-push` | 只在本地生成并提交，不推送（想先看一眼时用） |
| `--dry-run` | 只解析和渲染，什么都不写 |
| `--force` | 内容没变也重写（改了预览算法之后用） |
| `--author` | 写进 `meta.json` 的作者，默认 `Iliary` |
| `--token` | `git push` 不通时走 GitHub API 兜底用的 token（也可用 `$GITHUB_TOKEN` 或仓库根的 `.github-token`） |

- **增量**：按蓝图内容哈希判断，没改过的文件不会重写，也不会重复提交。
- **slug**：`名字-ascii部分-内容哈希`，名字取文件名（去掉 `.msch`），所以同名不同内容的蓝图不会互相覆盖。
- **预览图**：按方块实际占地画色块图 + 网格，不是游戏截图（`.msch` 里没有贴图信息）；≥1 MiB 的蓝图不做预览，卡片显示占位。
- 单张蓝图文本特别大（仓库里最大一张 21 MiB，像素画类）会拖慢 git 仓库和首次打开；介意的话删掉对应目录再 push。

## 本地自检

```bash
python3 tools/build_index.py --check   # 只校验，不写文件
python3 tools/build_index.py           # 校验并重写 index.json
python3 tools/msch_min.py              # 编解码器自测
```

需要 Python 3.9+，无第三方依赖。

## 提交规矩（重要）

- **不要手动提交 `index.json`**：它是生成物，push 之后 GitHub Action 会校验并重写它、自己提交。
- push 之前先 `git pull --rebase`，否则会跟 Action 的自动提交打架。
- 平时你只改 `blueprints/<slug>/` 里的文件就够了。

## meta.json 字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `name` | ✅ | 显示名 |
| `author` | ✅ | 作者 |
| `description` | ✅ | 一两句话，卡片上会截断成两行 |
| `tags` | — | 字符串数组；页面顶部自动生成标签筛选 |
| `game_version` | — | 例如 `146`（BE 就写 `146-BE`） |
| `created` / `updated` | — | `YYYY-MM-DD`；`created` 决定列表排序（新的在前） |

宽度、高度、方块数、逻辑行数都由蓝图本身算出来，不用手填。

## 站点怎么拿数据

页面本身是静态的（`site/` 部署到 `/www/wwwroot/msch.iliary.life/`），**清单和蓝图由访客浏览器直连仓库取**，按顺序尝试三条源，用第一条成功的：

1. `https://raw.githubusercontent.com/EnernalIliary/Ili-Mindustry-schem/main/`（内容最新）
2. `https://cdn.jsdelivr.net/gh/EnernalIliary/Ili-Mindustry-schem@main/`（国内更通，但分支缓存最长 12 小时）
3. 本站镜像（服务器每 10 分钟 `git pull` 一份，前两条都不通时的兜底）

页脚会显示这次实际用的是哪条（`数据源：GitHub 直连 / jsDelivr / 本站镜像`）。
服务器只负责托管页面、以及在 GitHub 通的时候做镜像；就算服务器拉不动 GitHub，访客仍能直接从仓库看到最新内容。

## 预览图与材料清单

预览不是游戏导出的——Mindustry 只在显存里现画蓝图缩略图，磁盘上没有对应文件。这里用
[mindustry-schematic-parser](https://github.com/JeanJPNM/mindustry-schematic-parser) 的 node-canvas
渲染真实贴图，顺手算材料清单和电力收支：

```bash
cd renderer
npm install        # 国内可先 npm config set registry https://registry.npmmirror.com
node render.mjs ../blueprints ../_out --png --extra ../tools/data/blueprint_extra.json \
  --max-tiles 20000 --max-bytes 400000
```

- 产物直接覆盖 `blueprints/<slug>/preview.png`；`--extra` 写出的 `tools/data/blueprint_extra.json`
  提供材料清单与电力收支，`tools/build_index.py` 会自动合并进 `index.json`。
- **1.8 G 内存的机器必须限内存**：`systemd-run --scope -p MemoryMax=700M -p MemorySwapMax=0 node render.mjs ...`。
  像素画类蓝图（`linux-on-mlogv32` 21 MB、`badapple` 3.4 MB）不加限制会把整机跑到 OOM。
- `--max-tiles` / `--max-bytes` 会跳过超大蓝图；含模组方块（`landing-pad`、`logic-display` 等）的蓝图解析会报
  `block ... could not be found in the registry`。这两种都保留纯色方块图，不影响站点。当前 674 张里 573 张是真实渲染。
- 新增或改动了蓝图后，重跑一次渲染再 `git push`。
