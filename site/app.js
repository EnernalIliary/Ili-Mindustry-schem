/* 蓝图库前端：只读 index.json + 按需取 blueprint.txt，无第三方依赖。 */
(() => {
  "use strict";

  const el = (id) => document.getElementById(id);
  const state = { data: null, tag: null, query: "", base: "", source: "" };

  // 数据优先由访客浏览器直连仓库取（服务器到 GitHub 不稳），失败再逐级退到 CDN、最后用本站镜像。
  const REPO_PAGE = "https://github.com/EnernalIliary/Ili-Mindustry-schem";
  const SOURCES = [
    { label: "GitHub 直连", base: "https://raw.githubusercontent.com/EnernalIliary/Ili-Mindustry-schem/main/" },
    { label: "jsDelivr", base: "https://cdn.jsdelivr.net/gh/EnernalIliary/Ili-Mindustry-schem@main/" },
    { label: "本站镜像", base: "" },
  ];

  const $grid = el("grid");
  const $tags = el("tags");
  const $search = el("search");
  const $meta = el("meta");
  const $empty = el("empty");
  const $stamp = el("stamp");
  const $modal = el("modal");

  const fmtDate = (iso) => {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  };

  function card(bp) {
    const node = document.createElement("article");
    node.className = "card";
    node.tabIndex = 0;
    node.setAttribute("role", "button");
    node.setAttribute("aria-label", `查看 ${bp.name}`);

    const thumb = document.createElement("div");
    thumb.className = "thumb";
    if (bp.preview) {
      const img = document.createElement("img");
      img.loading = "lazy";
      img.alt = `${bp.name} 预览`;
      img.src = bp.preview;
      // 镜像里还没同步到这张图时，退回仓库原图
      img.onerror = () => {
        const remote = (bp.source_preview && state.base) ? state.base + bp.source_preview : null;
        if (remote && img.src !== remote) img.src = remote;
        else img.onerror = null;
      };
      thumb.append(img);
    } else {
      const ph = document.createElement("div");
      ph.className = "ph";
      ph.textContent = "暂无预览图";
      thumb.append(ph);
    }
    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = `${bp.width}×${bp.height}`;
    thumb.append(badge);

    const body = document.createElement("div");
    body.className = "card-body";

    const h2 = document.createElement("h2");
    h2.textContent = bp.name;

    const desc = document.createElement("p");
    desc.className = "desc";
    desc.textContent = bp.description;

    const row = document.createElement("div");
    row.className = "row";
    row.append(pill(`${bp.tiles} 方块`));
    if (bp.logic_blocks) row.append(pill(`${bp.logic_blocks} 逻辑`));
    for (const tag of bp.tags.slice(0, 2)) row.append(pill(tag));

    body.append(h2, desc, row);
    node.append(thumb, body);

    const open = () => showDetail(bp);
    node.addEventListener("click", open);
    node.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        open();
      }
    });
    return node;
  }

  function pill(text) {
    const span = document.createElement("span");
    span.className = "pill";
    span.textContent = text;
    return span;
  }

  function renderTags() {
    $tags.replaceChildren();
    const all = document.createElement("button");
    all.className = "chip";
    all.textContent = "全部";
    all.dataset.tag = "";
    all.setAttribute("aria-pressed", String(state.tag === null));
    all.addEventListener("click", () => setTag(null));
    $tags.append(all);

    for (const t of state.data.tags) {
      const chip = document.createElement("button");
      chip.className = "chip";
      chip.dataset.tag = t.name;
      chip.setAttribute("aria-pressed", String(state.tag === t.name));
      chip.append(document.createTextNode(t.name));
      const n = document.createElement("span");
      n.className = "n";
      n.textContent = String(t.count);
      chip.append(n);
      chip.addEventListener("click", () => setTag(state.tag === t.name ? null : t.name));
      $tags.append(chip);
    }
  }

  function setTag(tag) {
    state.tag = tag;
    for (const chip of $tags.querySelectorAll(".chip")) {
      chip.setAttribute("aria-pressed", String((chip.dataset.tag || null) === tag));
    }
    renderGrid();
  }

  function matches(bp) {
    if (state.tag && !bp.tags.includes(state.tag)) return false;
    const q = state.query.trim().toLowerCase();
    if (!q) return true;
    return [bp.name, bp.description, bp.author, bp.game_version, ...bp.tags]
      .join(" ").toLowerCase().includes(q);
  }

  function renderGrid() {
    const list = state.data.blueprints.filter(matches);
    $grid.replaceChildren(...list.map(card));
    $empty.hidden = list.length > 0;
    $meta.textContent = state.tag
      ? `${list.length} / ${state.data.count} 张蓝图 · 标签「${state.tag}」`
      : `${list.length} / ${state.data.count} 张蓝图`;
  }

  async function showDetail(bp) {
    const repo = state.data.repo || REPO_PAGE;

    el("m-title").textContent = bp.name;
    el("m-desc").textContent = bp.description;

    const stats = el("m-stats");
    stats.replaceChildren();
    const facts = [
      ["尺寸", `${bp.width}×${bp.height}`],
      ["方块", String(bp.tiles)],
      ["逻辑块", String(bp.logic_blocks)],
      ["逻辑行", String(bp.logic_lines)],
      ["作者", bp.author],
      ["版本", bp.game_version || "—"],
      ["更新", fmtDate(bp.updated) || "—"],
      ["校验", bp.sha256.slice(0, 8)],
    ];
    for (const [k, v] of facts) {
      const box = document.createElement("div");
      const dt = document.createElement("dt");
      dt.textContent = k;
      const dd = document.createElement("dd");
      dd.textContent = v;
      box.append(dt, dd);
      stats.append(box);
    }

    const tagBox = el("m-tags");
    tagBox.replaceChildren(...bp.tags.map(pill));

    const preview = el("m-preview");
    preview.replaceChildren();
    if (bp.preview) {
      const img = document.createElement("img");
      img.src = bp.preview;
      img.alt = `${bp.name} 预览`;
      preview.append(img);
    } else {
      const ph = document.createElement("div");
      ph.className = "ph";
      ph.textContent = "还没有预览图。在蓝图文件夹里放一张 preview.png 就会出现。";
      preview.append(ph);
    }

    const source = el("m-source");
    if (repo) {
      source.hidden = false;
      source.href = `${repo}/tree/main/blueprints/${bp.slug}`;
    } else {
      source.hidden = true;
    }

    const hint = el("m-hint");
    hint.textContent = "";
    hint.className = "hint";

    const copyBtn = el("m-copy");
    copyBtn.onclick = async () => {
      copyBtn.disabled = true;
      hint.textContent = "读取中…";
      hint.className = "hint";
      try {
        const text = await fetchBlueprint(bp);
        await copyText(text);
        hint.textContent = "已复制。回游戏里按 Ctrl+V 就能粘出这张蓝图。";
        hint.className = "hint ok";
        copyBtn.textContent = "已复制 ✓";
        setTimeout(() => { copyBtn.textContent = "复制蓝图"; }, 2000);
      } catch (err) {
        hint.textContent = `复制失败：${err.message}。可以直接下载文件导入。`;
        hint.className = "hint err";
      } finally {
        copyBtn.disabled = false;
      }
    };

    const dl = el("m-download");
    dl.href = bp.file;
    dl.setAttribute("download", `${bp.slug}.txt`);

    $modal.hidden = false;
    document.body.style.overflow = "hidden";
    el("close").focus();
  }

  function closeModal() {
    $modal.hidden = true;
    document.body.style.overflow = "";
  }

  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.append(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    if (!ok) throw new Error("浏览器拒绝了复制");
  }

  function bindEvents() {
    $search.addEventListener("input", (e) => {
      state.query = e.target.value;
      renderGrid();
    });
    el("close").addEventListener("click", closeModal);
    $modal.addEventListener("click", (e) => {
      if (e.target === $modal) closeModal();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !$modal.hidden) closeModal();
    });
  }

  async function fetchText(url, ms = 8000) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), ms);
    try {
      const res = await fetch(url, { cache: "no-cache", signal: ctrl.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.text();
    } finally {
      clearTimeout(timer);
    }
  }

  function fetchBlueprint(bp) {
    // index.json 里的 file 是站点镜像路径（data/…），source 是仓库内路径（blueprints/…）
    const remotePath = bp.source || (bp.file.startsWith("data/") ? `blueprints/${bp.file.slice(5)}` : bp.file);
    const attempts = state.base ? [[state.base, remotePath], ["", bp.file]] : [["", bp.file]];
    let lastErr = null;
    return (async () => {
      for (const [base, path] of attempts) {
        try {
          return (await fetchText(base + path)).trim();
        } catch (err) {
          lastErr = err;
        }
      }
      throw lastErr || new Error("取不到文件");
    })();
  }

  async function boot() {
    bindEvents();
    let lastErr = null;
    for (const src of SOURCES) {
      try {
        state.data = JSON.parse(await fetchText(src.base + "index.json"));
        state.base = src.base;
        state.source = src.label;
        break;
      } catch (err) {
        lastErr = err;
      }
    }
    if (!state.data) {
      $meta.textContent = `读取 index.json 失败：${(lastErr && lastErr.message) || "网络不可用"}`;
      return;
    }
    if (state.data.generated_at) {
      const d = new Date(state.data.generated_at);
      $stamp.textContent = `清单更新于 ${d.toLocaleString("zh-CN", { hour12: false })} · 数据源：${state.source}`;
    } else {
      $stamp.textContent = `数据源：${state.source}`;
    }
    renderTags();
    renderGrid();
  }

  boot();
})();
