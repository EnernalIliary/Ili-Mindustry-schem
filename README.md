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

服务器每 10 分钟 `git pull`，把 `site/` 和 `blueprints/*` 组装进
`/www/wwwroot/Iliary.life/blueprints/`，nginx 直接当静态文件发出去。
访客不访问 GitHub，所以国内网络也不受影响。
