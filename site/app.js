/* 蓝图库前端：数据由访客浏览器直连仓库取，GitHub 不通时退到 jsDelivr、再退到本站镜像 */
(() => {
  "use strict";

  // 三个数据源按顺序回退；base 为空 = 本站镜像
  const SOURCES = [
    { label: "GitHub 直连", base: "https://raw.githubusercontent.com/EnernalIliary/Ili-Mindustry-schem/main/" },
    { label: "jsDelivr", base: "https://cdn.jsdelivr.net/gh/EnernalIliary/Ili-Mindustry-schem@main/" },
    { label: "本站镜像", base: "" },
  ];
  const REPO_PAGE = "https://github.com/EnernalIliary/Ili-Mindustry-schem";

  // 材料英文 id → 中文名（游戏内叫法，缺的回落成 id）
  const ITEM_ZH = {
    copper: "铜", lead: "铅", metaglass: "玻璃", graphite: "石墨", sand: "沙",
    coal: "煤", titanium: "钛", thorium: "钍", scrap: "废料", silicon: "硅",
    plastanium: "塑钢", "phase-fabric": "相织布", "surge-alloy": "浪涌合金",
    "spore-pod": "孢子荚", "blast-compound": "爆炸混合物", pyratite: "硫磺炸药",
    beryllium: "铍", tungsten: "钨", oxide: "氧化铍", carbide: "碳化物",
    "fissile-matter": "裂变物质", "dormant-cyst": "休眠孢囊",
  };
  const $ = (id) => document.getElementById(id);
  const els = {
    header: $("header"),
    search: $("search"),
    tags: $("tags"),
    factory: $("factory-range"),
    logic: $("logic-range"),
    meta: $("meta"),
    grid: $("grid"),
    empty: $("empty"),
    stamp: $("stamp"),
    statCount: $("stat-count"),
    statTags: $("stat-tags"),
    statLogic: $("stat-logic"),
    modal: $("modal"),
    mPreview: $("m-preview"),
    mTitle: $("m-title"),
    mDesc: $("m-desc"),
    mStats: $("m-stats"),
    mTags: $("m-tags"),
    mReq: $("m-req"),
    mCopy: $("m-copy"),
    mDownload: $("m-download"),
    mSource: $("m-source"),
    mHint: $("m-hint"),
    close: $("close"),
    theme: $("theme-toggle"),
    repoLink: $("repo-link"),
  };

  const state = {
    data: null,
    base: "",
    source: "",
    query: "",
    cat: null,
    factory: "",
    logic: "",
    lastFocus: null,
  };

  /* ---------- 工具 ---------- */

  const pad = (n) => String(n).padStart(2, "0");

  function fmtDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function fmtNum(n) {
    return new Intl.NumberFormat("zh-CN").format(n);
  }

  function debounce(fn, ms) {
    let t = 0;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  }

  function ripple(node, ev) {
    if (!node) return;
    const box = node.getBoundingClientRect();
    const size = Math.max(box.width, box.height);
    const dot = document.createElement("span");
    dot.className = "ripple";
    dot.style.width = dot.style.height = `${size}px`;
    dot.style.left = `${ev.clientX - box.left - size / 2}px`;
    dot.style.top = `${ev.clientY - box.top - size / 2}px`;
    node.appendChild(dot);
    dot.addEventListener("animationend", () => dot.remove(), { once: true });
  }

  async function fetchText(url, ms = 8000) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), ms);
    try {
      const res = await fetch(url, { signal: ctrl.signal, cache: "no-cache" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.text();
    } finally {
      clearTimeout(timer);
    }
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, (ch) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]
    ));
  }

  // 数字标签：1..9 是生效工厂台数，10~19 / 20~29 是区间，极多是更多。
  function fmtFactory(value) {
    if (!value) return "";
    return value.replace("~", "–");
  }

  /* ---------- 筛选 ---------- */

  function inLogicRange(lines) {
    const range = state.logic;
    if (!range) return true;
    if (range === "0") return lines === 0;
    if (range.endsWith("+")) return lines >= parseInt(range, 10);
    const [lo, hi] = range.split("-").map((v) => parseInt(v, 10));
    return lines >= lo && lines <= hi;
  }

  function matches(bp) {
    const labels = bp.labels || [];
    if (state.cat && !labels.includes(state.cat)) return false;
    if (state.factory && (bp.factory || "") !== state.factory) return false;
    if (!inLogicRange(bp.logic_lines || 0)) return false;
    const q = state.query.trim().toLowerCase();
    if (!q) return true;
    const hay = [bp.name, bp.description, labels.join(" "), bp.slug].join(" ").toLowerCase();
    return q.split(/\s+/).every((word) => hay.includes(word));
  }

  /* ---------- 卡片 ---------- */

  function previewSrc(bp) {
    return state.base && bp.source_preview ? state.base + bp.source_preview : bp.preview;
  }

  function cardHtml(bp, i) {
    const thumb = bp.has_preview
      ? `<img src="${previewSrc(bp)}" alt="${escapeHtml(bp.name)} 预览" loading="lazy" decoding="async"
              data-fallback="${bp.preview || ""}">`
      : `<span class="ph">无预览</span>`;
    const pills = (bp.labels || []).slice(0, 3).map((t) => `<span class="pill cat">${escapeHtml(t)}</span>`).join("");
    const fac = bp.factory
      ? `<span class="pill fac">工厂 ${escapeHtml(fmtFactory(bp.factory))}</span>`
      : "";
    const logic = bp.logic_lines > 0
      ? `<span class="pill logic">逻辑 ${fmtNum(bp.logic_lines)} 行</span>`
      : "";

    return `
      <button class="card" type="button" style="--delay:${Math.min(i * 26, 520)}ms" data-slug="${bp.slug}">
        <span class="thumb">
          ${thumb}
          <span class="badge">${bp.width}×${bp.height}</span>
        </span>
        <span class="card-body">
          <h2>${escapeHtml(bp.name)}</h2>
          <p class="desc">${escapeHtml(bp.description || "")}</p>
          <span class="row">${pills}${fac}${logic}</span>
        </span>
      </button>`;
  }

  /* ---------- 渲染 ---------- */

  function render() {
    const data = state.data;
    if (!data) return;
    const list = data.blueprints.filter(matches);
    const limit = 400;

    els.grid.innerHTML = list.slice(0, limit).map(cardHtml).join("");
    els.empty.hidden = list.length > 0;

    const bits = [`显示 ${fmtNum(Math.min(list.length, limit))} / ${fmtNum(data.count)} 张`];
    bits.push(state.cat ? `分类：${state.cat}` : "分类：全部");
    if (state.factory) bits.push(`生效工厂：${fmtFactory(state.factory)}`);
    if (state.logic && els.logic.selectedOptions[0]) {
      bits.push(`逻辑：${els.logic.selectedOptions[0].textContent.trim()}`);
    }
    if (state.query.trim()) bits.push(`搜索「${state.query.trim()}」`);
    if (list.length > limit) bits.push(`列表只铺前 ${limit} 张，缩小范围更快`);
    els.meta.textContent = bits.join(" · ");

    observeCards();
    watchImages();
  }

  function renderTags() {
    // 游戏内自己打的标签（蓝图文件里的 labels）。
    // 顺序来自游戏里那张「000标签排序」蓝图，构建 index.json 时就排好了。
    const all = state.data.labels || [];
    const chip = (label, count, active, value) => `
      <button class="chip" type="button" aria-pressed="${active}" data-cat="${escapeHtml(value || "")}">
        ${escapeHtml(label)}<span class="n">${fmtNum(count)}</span>
      </button>`;

    els.tags.innerHTML =
      chip("全部", state.data.count, state.cat === null, "") +
      all.map((c) => chip(c.name, c.count, state.cat === c.name, c.name)).join("");
    els.statTags.textContent = fmtNum(all.length);
  }

  function renderFactories() {
    const items = state.data.factories || [];
    for (const item of items) {
      const opt = document.createElement("option");
      opt.value = item.name;
      opt.textContent = `${fmtFactory(item.name)} · ${fmtNum(item.count)} 张`;
      els.factory.appendChild(opt);
    }
  }

  function renderStats() {
    const data = state.data;
    els.statCount.textContent = fmtNum(data.count);
    els.statLogic.textContent = fmtNum((data.logic && data.logic.with_logic) || 0);
    els.stamp.textContent = `清单更新于 ${fmtDate(data.generated_at)} · 数据源：${state.source}`;
    if (data.repo) els.repoLink.href = data.repo;
  }

  function observeCards() {
    if (!("IntersectionObserver" in window)) {
      els.grid.querySelectorAll(".card").forEach((c) => c.classList.add("in"));
      return;
    }
    const io = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("in");
          io.unobserve(entry.target);
        }
      }
    }, { rootMargin: "140px" });
    els.grid.querySelectorAll(".card").forEach((card) => {
      if (!card.querySelector("img")) card.classList.add("in");
      else io.observe(card);
    });
  }

  function watchImages() {
    els.grid.querySelectorAll("img[data-fallback]").forEach((img) => {
      img.addEventListener("load", () => {
        img.classList.add("loaded");
        const card = img.closest(".card");
        if (card) card.classList.add("in");
      }, { once: true });
      img.addEventListener("error", () => {
        const fb = img.dataset.fallback;
        if (fb && !img.dataset.retried) {
          img.dataset.retried = "1";
          img.src = fb;
        } else {
          const ph = document.createElement("span");
          ph.className = "ph";
          ph.textContent = "无预览";
          img.replaceWith(ph);
        }
      });
    });
  }

  /* ---------- 弹窗 ---------- */

  function statRow(dt, dd) {
    return `<div><dt>${dt}</dt><dd>${dd}</dd></div>`;
  }

  function openModal(bp) {
    state.lastFocus = document.activeElement;
    els.mTitle.textContent = bp.name;
    els.mDesc.textContent = bp.description || "";

    els.mPreview.innerHTML = bp.has_preview
      ? `<img src="${previewSrc(bp)}" alt="${escapeHtml(bp.name)} 预览">`
      : `<div class="ph">这张蓝图没有预览图</div>`;

    const power = typeof bp.power_balance === "number" ? bp.power_balance : null;
    els.mStats.innerHTML = [
      statRow("尺寸", `${bp.width} × ${bp.height}`),
      statRow("方块", fmtNum(bp.tiles)),
      statRow("逻辑", bp.logic_lines > 0 ? `${fmtNum(bp.logic_lines)} 行 / ${fmtNum(bp.logic_blocks)} 块` : "无"),
      statRow("生效工厂", bp.factory ? fmtFactory(bp.factory) : "—"),
      statRow("电力", power === null ? "—" : `${power > 0 ? "+" : ""}${fmtNum(power)}`),
      statRow("导入于", bp.created || "—"),
    ].join("");

    const labels = bp.labels || [];
    els.mTags.innerHTML = labels.map((t) => `<span class="chip">${escapeHtml(t)}</span>`).join("");

    const req = (bp.requirements || []).filter((r) => r && r.item);
    if (req.length) {
      const total = req.reduce((sum, r) => sum + (r.amount || 0), 0);
      els.mReq.hidden = false;
      els.mReq.querySelector("ul").innerHTML = req
        .map((r) => `<li><span class="item">${escapeHtml(ITEM_ZH[r.item] || r.item)}</span>
          <span class="amt">${fmtNum(r.amount)}</span></li>`)
        .join("");
      els.mReq.querySelector("h3").textContent = `材料清单 · 共 ${fmtNum(total)}`;
    } else {
      els.mReq.hidden = true;
    }

    els.mSource.href = `${REPO_PAGE}/blob/main/blueprints/${bp.slug}/blueprint.txt`;
    els.mHint.textContent = "";
    els.mHint.className = "hint";
    els.mCopy.disabled = false;
    els.mCopy.textContent = "复制蓝图";

    els.modal.hidden = false;
    els.modal.dataset.slug = bp.slug;
    requestAnimationFrame(() => els.modal.classList.add("open"));
    document.body.style.overflow = "hidden";
    els.close.focus({ preventScroll: true });
  }

  function closeModal() {
    if (els.modal.hidden) return;
    els.modal.classList.remove("open");
    document.body.style.overflow = "";
    const done = () => {
      els.modal.hidden = true;
      els.modal.removeEventListener("transitionend", done);
    };
    els.modal.addEventListener("transitionend", done);
    setTimeout(done, 360);
    if (state.lastFocus && state.lastFocus.focus) {
      state.lastFocus.focus({ preventScroll: true });
    }
  }

  function currentBp() {
    const slug = els.modal.dataset.slug;
    return (state.data ? state.data.blueprints : []).find((bp) => bp.slug === slug);
  }

  async function blueprintText(bp) {
    if (state.base) {
      try {
        return await fetchText(state.base + (bp.source || bp.file), 12000);
      } catch (err) {
        /* 远程取不到就退回本站镜像 */
      }
    }
    return await fetchText(bp.file, 12000);
  }

  async function copyBlueprint() {
    const bp = currentBp();
    if (!bp) return;
    els.mCopy.disabled = true;
    els.mCopy.textContent = "读取中…";
    els.mHint.textContent = "";
    els.mHint.className = "hint";
    try {
      const text = (await blueprintText(bp)).trim();
      await navigator.clipboard.writeText(text);
      els.mHint.textContent = `已复制 ${fmtNum(text.length)} 个字符，回游戏里按 Ctrl+V 粘贴。`;
      els.mHint.className = "hint ok";
      els.mCopy.textContent = "已复制";
    } catch (err) {
      els.mHint.textContent = "复制失败，可以用「下载文本」再手动打开。";
      els.mHint.className = "hint err";
      els.mCopy.textContent = "复制蓝图";
    } finally {
      els.mCopy.disabled = false;
    }
  }

  async function downloadBlueprint(ev) {
    const bp = currentBp();
    if (!bp) return;
    ev.preventDefault();
    try {
      const text = (await blueprintText(bp)).trim();
      const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${bp.slug}.txt`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 4000);
    } catch (err) {
      els.mHint.textContent = "取文件失败，网络可能不太稳。";
      els.mHint.className = "hint err";
    }
  }

  /* ---------- 主题 / 滚动 ---------- */

  function initTheme() {
    const saved = localStorage.getItem("bp-theme");
    if (saved !== "light" && saved !== "dark") {
      document.documentElement.dataset.theme =
        matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    els.theme.addEventListener("click", () => {
      const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      localStorage.setItem("bp-theme", next);
    });
  }

  function initScroll() {
    const onScroll = () => els.header.classList.toggle("scrolled", window.scrollY > 8);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  function revealOnScroll() {
    const nodes = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window)) {
      nodes.forEach((n) => n.classList.add("in"));
      return;
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("in");
          io.unobserve(entry.target);
        }
      });
    }, { rootMargin: "-40px" });
    nodes.forEach((n) => io.observe(n));
  }

  /* ---------- 启动 ---------- */

  function skeletons(n = 6) {
    els.grid.innerHTML = Array.from({ length: n }, () => `<div class="skeleton"></div>`).join("");
  }

  async function boot() {
    skeletons();
    let lastErr = null;
    for (const source of SOURCES) {
      try {
        const text = await fetchText(source.base + "index.json", 8000);
        state.data = JSON.parse(text);
        state.base = source.base;
        state.source = source.label;
        break;
      } catch (err) {
        lastErr = err;
      }
    }

    if (!state.data) {
      els.grid.innerHTML = `<p class="empty">清单加载失败：三个数据源都没取到。${lastErr ? `（${escapeHtml(lastErr.message)}）` : ""}</p>`;
      els.stamp.textContent = "数据源全部不可达，稍后刷新重试。";
      return;
    }

    renderStats();
    renderFactories();
    renderTags();
    render();
  }

  /* ---------- 事件 ---------- */

  function bind() {
    els.search.addEventListener("input", debounce((ev) => {
      state.query = ev.target.value;
      render();
    }, 130));

    els.tags.addEventListener("click", (ev) => {
      const chip = ev.target.closest(".chip");
      if (!chip) return;
      const value = chip.dataset.cat;
      state.cat = value ? value : null;
      renderTags();
      render();
    });

    els.logic.addEventListener("change", () => {
      state.logic = els.logic.value;
      render();
    });

    els.factory.addEventListener("change", () => {
      state.factory = els.factory.value;
      render();
    });

    els.grid.addEventListener("click", (ev) => {
      const card = ev.target.closest(".card");
      if (!card) return;
      const bp = (state.data ? state.data.blueprints : []).find((item) => item.slug === card.dataset.slug);
      if (bp) openModal(bp);
    });

    els.close.addEventListener("click", closeModal);
    els.modal.addEventListener("click", (ev) => {
      if (ev.target === els.modal) closeModal();
    });
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && !els.modal.hidden) closeModal();
    });

    els.mCopy.addEventListener("click", copyBlueprint);
    els.mDownload.addEventListener("click", downloadBlueprint);

    document.addEventListener("click", (ev) => {
      const node = ev.target.closest(".btn, .chip, .icon-btn");
      if (node) ripple(node, ev);
    });
  }

  initTheme();
  initScroll();
  revealOnScroll();
  bind();
  boot();
})();
