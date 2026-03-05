// --- Paths must match repo (spaces URL-encoded) ---
const PATHS = {
  geo: "/Data/Raw%20data/GST%20East%20Delhi%20Divisions.geojson",
  mandoli: "/Data/Cleaned%20data/Chapter%20data/chapter_mandoli.csv",
  gandhi: "/Data/Cleaned%20data/Chapter%20data/chapter_gandhinagar.csv",
  delhiEast: "/Data/Cleaned%20data/Chapter%20data/chapter_delhieast.csv",
};

let state = {
  chapter: null,
  metric: "z2", // z1, z2, z3
  geojson: null,
  layer: null,
  labelLayer: null,
  dataIndex: {}, // dataIndex[DIVISION][CHAPTER_STR] = { z1, z2, z3 }
  chapters: [],
  chapterLabel: {},
  schema: null,
  featureLayers: [],
  chapterRangeText: "",
  lb: { div: "MANDOLI", open: false },
};

function normKey(s) {
  return String(s || "")
    .replace(/\uFEFF/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

function pickKey(keys, mustIncludeWords) {
  const nk = keys.map((k) => ({ raw: k, n: normKey(k) }));
  for (const cand of nk) {
    if (mustIncludeWords.every((w) => cand.n.includes(w))) return cand.raw;
  }
  return null;
}

function detectSchema(rows) {
  const first = rows[0] || {};
  const keys = Object.keys(first);

  const chapterKey = pickKey(keys, ["chapter"]) || "Chapter";
  const hsnChapterKey = pickKey(keys, ["hsn", "chapter"]) || "HSN Chapter";
  const z1Key = pickKey(keys, ["gstns", "z1"]) || "No. of GSTNs_z1";
  const z2Key = pickKey(keys, ["taxable", "z2"]) || pickKey(keys, ["taxable", "24_25"]) || "Taxable value 24_25_z2";
  const z3Key = pickKey(keys, ["yoy", "z3"]) || pickKey(keys, ["yoy", "growth"]) || "YoY growth_z3";

  return { chapterKey, hsnChapterKey, z1Key, z2Key, z3Key };
}

function canonDivisionName(s) {
  const x = String(s || "")
    .trim()
    .toUpperCase()
    .replace(/\s+/g, " ");

  if (x === "GANDHI NAGAR") return "GANDHINAGAR";
  if (x === "GANDHINAGAR") return "GANDHINAGAR";
  if (x === "DELHI EAST") return "DELHIEAST";
  return x.replace(/\s+/g, "");
}

function parseChapter(raw) {
  if (raw === null || raw === undefined) return null;
  const s = String(raw).trim();
  if (!s) return null;
  const digits = s.replace(/\D/g, "");
  if (!digits) return null;
  return String(parseInt(digits, 10));
}

function parseNumber(x) {
  if (x === null || x === undefined) return null;
  const s = String(x).trim();
  if (!s || s === "-") return null;
  const n = Number(s.replace(/,/g, ""));
  return Number.isFinite(n) ? n : null;
}

function formatINR(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function formatPct(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return (Number(n) * 100).toFixed(1) + "%";
}

function formatInt(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Math.round(Number(n)).toLocaleString("en-IN");
}

function metricLabel(metric) {
  if (metric === "z3") return "YoY Growth";
  if (metric === "z1") return "No. of GSTNs";
  return "Supply Value";
}

function metricFormatted(metric, v) {
  if (metric === "z3") return formatPct(v);
  if (metric === "z1") return formatInt(v);
  return formatINR(v);
}

function chapterSelectEl() {
  return document.getElementById("chapterSelect");
}

function syncChapterSelect() {
  const sel = chapterSelectEl();
  if (sel) sel.value = state.chapter || "";
}

function loadCSV(url) {
  return new Promise((resolve, reject) => {
    Papa.parse(url, {
      download: true,
      header: true,
      skipEmptyLines: true,
      complete: (res) => resolve(res.data || []),
      error: reject,
    });
  });
}

function buildIndex(rows, divisionName) {
  const { chapterKey, hsnChapterKey, z1Key, z2Key, z3Key } = state.schema;
  const division = canonDivisionName(divisionName);

  for (const r of rows) {
    const chapter = parseChapter(r[chapterKey]);
    if (!chapter) continue;
    const hsnChapter = String(r[hsnChapterKey] || "").trim();

    const z1 = parseNumber(r[z1Key]);
    const z2 = parseNumber(r[z2Key]);
    const z3 = parseNumber(r[z3Key]);

    if (!state.dataIndex[division]) state.dataIndex[division] = {};
    state.dataIndex[division][chapter] = { z1, z2, z3 };
    state.chapters.push(chapter);
    const fallback = `Chapter ${chapter}`;
    if (!state.chapterLabel[chapter]) {
      state.chapterLabel[chapter] = hsnChapter || fallback;
    } else if (
      hsnChapter &&
      state.chapterLabel[chapter].trim().toLowerCase() === fallback.toLowerCase()
    ) {
      state.chapterLabel[chapter] = hsnChapter;
    }
  }
}

function buildChapterDropdown() {
  const sel = chapterSelectEl();
  sel.innerHTML = "";

  if (!state.chapters.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "No Chapter found";
    sel.appendChild(opt);
    return;
  }

  for (const chapter of state.chapters) {
    const opt = document.createElement("option");
    opt.value = chapter;
    opt.textContent = state.chapterLabel[chapter] || `Chapter ${chapter}`;
    sel.appendChild(opt);
  }

  sel.value = state.chapter;
  sel.addEventListener("change", () => {
    state.chapter = sel.value;
    render();
  });

  document.getElementById("subnote").textContent =
    `Hover a division to see values for the selected chapter. Available chapter range: ${state.chapterRangeText}.`;
}

function getDivisionName(feature) {
  const p = feature.properties || {};
  return canonDivisionName(p.Division_Map || "");
}

function divisionValue(division, chapter, metric) {
  const row = state.dataIndex[division]?.[chapter];
  if (!row) return null;
  const v = row[metric];
  return v === undefined ? null : v;
}

function percentile(sortedVals, p) {
  if (!sortedVals.length) return null;
  if (sortedVals.length === 1) return sortedVals[0];
  const idx = (sortedVals.length - 1) * p;
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  if (lo === hi) return sortedVals[lo];
  const w = idx - lo;
  return sortedVals[lo] * (1 - w) + sortedVals[hi] * w;
}

function signedLog(v) {
  return Math.sign(v) * Math.log1p(Math.abs(v));
}

function tooltipHTML(division) {
  const v = divisionValue(division, state.chapter, state.metric);
  const label = metricLabel(state.metric);
  const val = metricFormatted(state.metric, v);
  const chapterText = state.chapter ? state.chapter : "—";

  return `
    <div style="font-weight:700; margin-bottom:2px;">${division}</div>
    <div style="font-size:12px; color:#475569;">
      Chapter: <b>${chapterText}</b> • ${label}: <b>${val}</b>
    </div>
  `;
}

function getLeaders(division, metric, topN) {
  const rows = Object.entries(state.dataIndex[division] || {})
    .map(([chapter, vals]) => ({ chapter, value: vals?.[metric] }))
    .filter((r) => Number.isFinite(Number(r.value)))
    .sort((a, b) => Number(b.value) - Number(a.value))
    .slice(0, topN);
  return rows;
}

function leaderboardValue(metric, value) {
  if (metric === "z3") return formatPct(value);
  if (metric === "z1") return formatInt(value);
  return formatINR(value);
}

function leaderboardRowsHTML(rows, metric) {
  if (!rows.length) {
    return `<div class="lb-row"><span class="lb-rank">-</span><span class="lb-ch">No data</span><span class="lb-val">—</span></div>`;
  }
  return rows
    .map(
      (r, i) => {
        const label = state.chapterLabel[r.chapter] || `Chapter ${r.chapter}`;
        return `<button class="lb-row" data-ch="${r.chapter}">
          <span class="lb-rank">${i + 1}</span>
          <span class="lb-ch">${label}</span>
          <span class="lb-val">${leaderboardValue(metric, r.value)}</span>
        </button>`;
      }
    )
    .join("");
}

function bindLeaderboardRowClicks() {
  document.querySelectorAll(".lb-row[data-ch]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.chapter = String(btn.dataset.ch || "");
      syncChapterSelect();
      render();
    });
  });
}

function renderLeaderboard() {
  const division = state.lb.div;
  const valueLeaders = getLeaders(division, "z2", 5);
  const growthLeaders = getLeaders(division, "z3", 5);

  const valueEl = document.getElementById("lbValue");
  const growthEl = document.getElementById("lbGrowth");
  if (!valueEl || !growthEl) return;

  valueEl.innerHTML = leaderboardRowsHTML(valueLeaders, "z2");
  growthEl.innerHTML = leaderboardRowsHTML(growthLeaders, "z3");
  bindLeaderboardRowClicks();
}

function bindLeaderboardUI() {
  const tabs = document.querySelectorAll(".lb-tab");
  tabs.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabs.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.lb.div = String(btn.dataset.div || "MANDOLI");
      renderLeaderboard();
    });
  });

  const openBtn = document.getElementById("lbOpen");
  const closeBtn = document.getElementById("lbClose");
  const backdrop = document.getElementById("lbBackdrop");
  const modal = document.getElementById("lbModal");
  const card = document.getElementById("lbCard");

  const setOpen = (open) => {
    state.lb.open = open;
    if (!backdrop || !modal) return;
    if (openBtn) openBtn.classList.toggle("active", open);
    document.body.style.overflow = open ? "hidden" : "";
    backdrop.hidden = !open;
    modal.hidden = !open;
    modal.setAttribute("aria-hidden", open ? "false" : "true");
    if (open) {
      renderLeaderboard();
    }
  };

  if (openBtn) {
    openBtn.addEventListener("click", () => {
      setOpen(!state.lb.open);
    });
  }

  if (closeBtn) {
    closeBtn.addEventListener("click", () => setOpen(false));
  }

  if (backdrop) {
    backdrop.addEventListener("click", () => setOpen(false));
  }

  if (modal) {
    modal.addEventListener("click", () => setOpen(false));
  }

  if (card) {
    card.addEventListener("click", (e) => e.stopPropagation());
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && state.lb.open) {
      setOpen(false);
    }
  });

  // Keep closed by default
  if (backdrop && modal) {
    backdrop.hidden = true;
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
  }
}

function initMap() {
  const map = L.map("map", { zoomControl: true }).setView([28.63, 77.28], 11);
  state.map = map;

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "",
  }).addTo(map);

  state.labelLayer = L.layerGroup().addTo(map);
  state.featureLayers = [];

  state.layer = L.geoJSON(state.geojson, {
    style: featureStyle,
    onEachFeature: (feature, layer) => {
      const division = getDivisionName(feature);
      layer.bindTooltip(tooltipHTML(division), { sticky: true, direction: "top", opacity: 0.95 });
      layer.__divisionName = division;
      state.featureLayers.push(layer);

      if (division === "MANDOLI" || division === "GANDHINAGAR") {
        const center = layer.getBounds().getCenter();
        const icon = L.divIcon({
          className: "",
          html: `<div class="div-label">${division}</div>`,
          iconSize: [0, 0],
        });
        L.marker(center, { icon, interactive: false }).addTo(state.labelLayer);
      }
    },
  }).addTo(map);
}

function colorForMetric(v, metric) {
  if (v === null || v === undefined || Number.isNaN(v)) return "#e2e8f0";
  const clamp01 = (x) => Math.max(0, Math.min(1, x));

  if (metric === "z2") {
    // Compare Mandoli vs Gandhinagar for selected chapter, but compress saturation
    // when values are close to avoid extreme visual contrast.
    const vals = ["MANDOLI", "GANDHINAGAR"]
      .map((d) => divisionValue(d, state.chapter, "z2"))
      .filter((x) => x !== null && x !== undefined && Number.isFinite(Number(x)))
      .map(Number);

    if (!vals.length) return "#e2e8f0";

    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const ratio = min > 0 ? max / min : Number.POSITIVE_INFINITY;
    const rawT = max === min ? 0.5 : (Number(v) - min) / (max - min);
    const t0 = clamp01(rawT);

    let t;
    if (ratio <= 1.5) {
      t = 0.45 + 0.40 * t0; // 0.45..0.85
    } else if (ratio <= 3) {
      t = 0.25 + 0.65 * t0; // 0.25..0.90
    } else {
      t = 0.10 + 0.85 * t0; // 0.10..0.95
    }

    return chroma.scale(["#f1f5f9", "#1e3a8a"]).mode("lab")(clamp01(t)).hex();
  }

  if (metric === "z1") {
    const vals = ["MANDOLI", "GANDHINAGAR"]
      .map((d) => divisionValue(d, state.chapter, "z1"))
      .filter((x) => x !== null && x !== undefined);

    if (!vals.length) return "#e2e8f0";

    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const t = max === min ? 0.7 : (v - min) / (max - min);
    return chroma.scale(["#f1f5f9", "#1e3a8a"]).mode("lab")(t).hex();
  }

  // z3 sign-aware coloring
  const vals = ["MANDOLI", "GANDHINAGAR", "DELHIEAST"]
    .map((d) => divisionValue(d, state.chapter, "z3"))
    .filter((x) => x !== null && x !== undefined && Number.isFinite(Number(x)))
    .map(Number);

  if (!vals.length) return "#e2e8f0";

  const allPos = vals.every((x) => x >= 0);
  const allNeg = vals.every((x) => x <= 0);
  const y = signedLog(Number(v));
  const yVals = vals.map((x) => signedLog(x));

  if (allPos) {
    const minY = Math.min(...yVals);
    const maxY = Math.max(...yVals);
    const t = maxY === minY ? 0.7 : (y - minY) / (maxY - minY);
    return chroma.scale(["#f8fafc", "#0f766e"]).mode("lab")(clamp01(t)).hex();
  }

  if (allNeg) {
    const minY = Math.min(...yVals); // most negative
    const maxY = Math.max(...yVals); // closest to 0
    const t = maxY === minY ? 0.7 : (y - minY) / (maxY - minY);
    return chroma.scale(["#9f1239", "#f8fafc"]).mode("lab")(clamp01(t)).hex();
  }

  const maxAbs = Math.max(...yVals.map((x) => Math.abs(x)));
  if (!Number.isFinite(maxAbs) || maxAbs === 0) {
    return chroma.scale(["#9f1239", "#f8fafc", "#0f766e"]).mode("lab")(0.5).hex();
  }

  const t = clamp01((y + maxAbs) / (2 * maxAbs));

  return chroma.scale(["#9f1239", "#f8fafc", "#0f766e"]).mode("lab")(t).hex();
}

function featureStyle(feature) {
  const division = getDivisionName(feature);
  const isTarget = division === "MANDOLI" || division === "GANDHINAGAR";
  const v = isTarget ? divisionValue(division, state.chapter, state.metric) : null;

  const fill = isTarget ? colorForMetric(v, state.metric) : "#f8fafc";

  return {
    color: "#0b1220",
    weight: isTarget ? 2.6 : 2.0,
    opacity: isTarget ? 0.95 : 0.65,
    fillColor: fill,
    fillOpacity: isTarget ? 0.7 : 0.18,
  };
}

function render() {
  if (!state.chapter) return;

  state.layer.setStyle(featureStyle);

  for (const lyr of state.featureLayers) {
    const div = lyr.__divisionName || "—";
    if (lyr.getTooltip()) lyr.setTooltipContent(tooltipHTML(div));
  }

  const m = state.dataIndex["MANDOLI"]?.[state.chapter] || {};
  const g = state.dataIndex["GANDHINAGAR"]?.[state.chapter] || {};

  document.getElementById("kpiMandoli").innerHTML =
    `<div style="font-weight:800; font-size:14px;">Mandoli</div>
     <div>GSTNs: <b>${formatInt(m.z1)}</b></div>
     <div>Value: <b>${formatINR(m.z2)}</b></div>
     <div>YoY: <b>${formatPct(m.z3)}</b></div>`;

  document.getElementById("kpiGandhi").innerHTML =
    `<div style="font-weight:800; font-size:14px;">Gandhinagar</div>
     <div>GSTNs: <b>${formatInt(g.z1)}</b></div>
     <div>Value: <b>${formatINR(g.z2)}</b></div>
     <div>YoY: <b>${formatPct(g.z3)}</b></div>`;

  renderLeaderboard();
}

function bindUI() {
  document.querySelectorAll(".chip[data-metric]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".chip[data-metric]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.metric = btn.dataset.metric;
      render();
    });
  });
}

async function init() {
  const [geoRes, mandoliRows, gandhiRows, delhiEastRows] = await Promise.all([
    fetch(PATHS.geo).then((r) => r.json()),
    loadCSV(PATHS.mandoli),
    loadCSV(PATHS.gandhi),
    loadCSV(PATHS.delhiEast),
  ]);

  state.geojson = geoRes;

  state.schema = detectSchema(mandoliRows.length ? mandoliRows : gandhiRows);

  buildIndex(mandoliRows, "MANDOLI");
  buildIndex(gandhiRows, "GANDHINAGAR");
  buildIndex(delhiEastRows, "DELHI EAST");

  const uniq = Array.from(new Set(state.chapters));
  uniq.sort((a, b) => Number(b) - Number(a));
  state.chapters = uniq;

  const chapterNums = state.chapters.map((c) => Number(c)).filter((n) => Number.isFinite(n));
  const minCh = chapterNums.length ? Math.min(...chapterNums) : "—";
  const maxCh = chapterNums.length ? Math.max(...chapterNums) : "—";
  state.chapterRangeText = `${minCh} to ${maxCh}`;
  state.chapter = state.chapters[0] || null;

  buildChapterDropdown();
  initMap();
  bindUI();
  bindLeaderboardUI();
  render();
}

init().catch((err) => console.error(err));
