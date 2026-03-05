// --- Paths must match repo (spaces URL-encoded) ---
const PATHS = {
  geo: "/Data/Raw%20data/GST%20East%20Delhi%20Divisions.geojson",
  mandoli: "/Data/Cleaned%20data/Mandoli.csv",
  gandhi: "/Data/Cleaned%20data/Gandhinagar.csv",
  delhiEast: "/Data/Cleaned%20data/Delhi%20East.csv",
};

let state = {
  hsn: null,                // string key (prevents weird numeric truncation)
  metric: "z2",             // z2 or z3
  geojson: null,
  layer: null,
  labelLayer: null,
  dataIndex: {},            // dataIndex[DIVISION][HSN_STR] = { z2, z3 }
  hsns: [],                 // list of HSN_STR
  schema: null,             // detected column keys
  featureLayers: [],        // leaflet layers for tooltip updates
};

function normKey(s){
  return String(s || "")
    .toLowerCase()
    .replace(/\uFEFF/g, "")   // BOM
    .replace(/\s+/g, " ")
    .trim();
}

function pickKey(keys, mustIncludeWords){
  const nk = keys.map(k => ({ raw: k, n: normKey(k) }));
  for (const cand of nk){
    const ok = mustIncludeWords.every(w => cand.n.includes(w));
    if (ok) return cand.raw;
  }
  return null;
}

function detectSchema(rows){
  const first = rows[0] || {};
  const keys = Object.keys(first);

  const divisionKey = pickKey(keys, ["division"]) || "Division";
  const hsnKey = pickKey(keys, ["hsn","code"]) || "HSN Code";
  const z2Key = pickKey(keys, ["taxable","z2"]) || pickKey(keys, ["taxable","24_25"]) || "Taxable value 24_25_z2";
  const z3Key = pickKey(keys, ["yoy","z3"]) || pickKey(keys, ["yoy","growth"]) || "YoY growth_z3";

  return { divisionKey, hsnKey, z2Key, z3Key };
}

function canonDivisionName(s){
  // Make CSV division names and GeoJSON Division_Map match consistently.
  const x = String(s || "")
    .trim()
    .toUpperCase()
    .replace(/\s+/g, " ");

  // normalize common variation
  if (x === "GANDHI NAGAR") return "GANDHINAGAR";
  if (x === "GANDHI  NAGAR") return "GANDHINAGAR";
  if (x === "GANDHINAGAR") return "GANDHINAGAR";
  return x;
}

function parseHSN(raw){
  if (raw === null || raw === undefined) return null;
  let s = String(raw).trim();

  if (!s) return null;

  // Handle things like "7404.0"
  s = s.replace(/\.0+$/,"");

  // Handle scientific notation like "6.203E3"
  if (/e\+?/i.test(s)){
    const n = Number(s);
    if (Number.isFinite(n)) s = String(Math.round(n));
  }

  // Keep only digits
  const digits = s.replace(/\D/g,"");
  return digits ? digits : null;
}

function parseNumber(x){
  if (x === null || x === undefined) return null;
  const s = String(x).trim();
  if (!s) return null;
  const n = Number(s.replace(/,/g, ""));
  return Number.isFinite(n) ? n : null;
}

function formatINR(n){
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function formatPct(n){
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return (Number(n) * 100).toFixed(1) + "%";
}

function metricLabel(metric){
  return metric === "z3" ? "YoY Growth" : "Supply Value";
}

function metricFormatted(metric, v){
  if (metric === "z3") return formatPct(v);
  return formatINR(v);
}

function loadCSV(url){
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

async function init(){
  const [geoRes, mandoliRows, gandhiRows] = await Promise.all([
    fetch(PATHS.geo).then(r => r.json()),
    loadCSV(PATHS.mandoli),
    loadCSV(PATHS.gandhi),
  ]);

  state.geojson = geoRes;

  // detect schema once (Mandoli + Gandhi have identical columns)
  state.schema = detectSchema(mandoliRows.length ? mandoliRows : gandhiRows);

  buildIndex(mandoliRows);
  buildIndex(gandhiRows);

  // Unique, sort (numeric sort without losing string keys)
  const uniq = Array.from(new Set(state.hsns));
  uniq.sort((a,b) => (Number(a) - Number(b)));
  state.hsns = uniq;

  state.hsn = state.hsns[0] || null;

  buildHSNDropdown();
  initMap();
  bindUI();
  render();
}

function buildIndex(rows){
  const { divisionKey, hsnKey, z2Key, z3Key } = state.schema;

  for (const r of rows){
    const divRaw = r[divisionKey];
    const division = canonDivisionName(divRaw);

    const hsn = parseHSN(r[hsnKey]);
    if (!division || !hsn) continue;

    const z2 = parseNumber(r[z2Key]);
    const z3 = parseNumber(r[z3Key]);

    if (!state.dataIndex[division]) state.dataIndex[division] = {};
    state.dataIndex[division][hsn] = { z2, z3 };

    state.hsns.push(hsn);
  }
}

function buildHSNDropdown(){
  const sel = document.getElementById("hsnSelect");
  sel.innerHTML = "";

  if (!state.hsns.length){
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "No HSN found";
    sel.appendChild(opt);
    return;
  }

  for (const hsn of state.hsns){
    const opt = document.createElement("option");
    opt.value = hsn;
    opt.textContent = `HSN Code: ${hsn}`;
    sel.appendChild(opt);
  }

  sel.value = state.hsn;

  sel.addEventListener("change", () => {
    state.hsn = sel.value;
    render();
  });

  // Small helper note
  document.getElementById("subnote").textContent =
    "Hover a division to see values for the selected HSN.";
}

function getDivisionName(feature){
  const p = feature.properties || {};
  return canonDivisionName(p.Division_Map || "");
}

function divisionValue(division, hsn, metric){
  const row = state.dataIndex[division]?.[hsn];
  if (!row) return null;
  const v = row[metric];
  return (v === undefined ? null : v);
}

function tooltipHTML(division){
  const v = divisionValue(division, state.hsn, state.metric);
  const label = metricLabel(state.metric);
  const val = metricFormatted(state.metric, v);
  const hsnText = state.hsn ? state.hsn : "—";

  return `
    <div style="font-weight:700; margin-bottom:2px;">${division}</div>
    <div style="font-size:12px; color:#475569;">
      HSN: <b>${hsnText}</b> • ${label}: <b>${val}</b>
    </div>
  `;
}

function initMap(){
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

      // Hover tooltip with values
      layer.bindTooltip(tooltipHTML(division), { sticky: true, direction: "top", opacity: 0.95 });

      // Keep reference so we can update tooltip content when HSN/metric changes
      layer.__divisionName = division;
      state.featureLayers.push(layer);

      // Permanent division labels (overlay)
      const center = layer.getBounds().getCenter();
      const icon = L.divIcon({
        className: "",
        html: `<div class="div-label">${division}</div>`,
        iconSize: [0,0],
      });
      L.marker(center, { icon, interactive: false }).addTo(state.labelLayer);
    }
  }).addTo(map);
}

function colorForMetric(v, metric){
  if (v === null || v === undefined || Number.isNaN(v)) return "#e2e8f0";

  if (metric === "z2"){
    // Scale only across Mandoli + Gandhinagar for current HSN (keeps colors meaningful)
    const vals = ["MANDOLI","GANDHINAGAR"]
      .map(d => divisionValue(d, state.hsn, "z2"))
      .filter(x => x !== null && x !== undefined);

    if (!vals.length) return "#e2e8f0";

    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const t = (max === min) ? 0.7 : (v - min) / (max - min);

    return chroma.scale(["#f1f5f9", "#1e3a8a"]).mode("lab")(t).hex();
  }

  // z3 diverging around 0
  const clamp = Math.max(-0.5, Math.min(0.5, v));
  const t = (clamp + 0.5) / 1.0;

  return chroma.scale(["#9f1239", "#f8fafc", "#0f766e"]).mode("lab")(t).hex();
}

function featureStyle(feature){
  const division = getDivisionName(feature);

  const isTarget = (division === "MANDOLI" || division === "GANDHINAGAR");
  const v = isTarget ? divisionValue(division, state.hsn, state.metric) : null;

  const fill = isTarget ? colorForMetric(v, state.metric) : "#f8fafc";

  return {
    color: "#0b1220",     // more vivid boundary
    weight: isTarget ? 2.6 : 2.0,
    opacity: isTarget ? 0.95 : 0.65,
    fillColor: fill,
    fillOpacity: isTarget ? 0.70 : 0.18,
  };
}

function render(){
  if (!state.hsn) return;

  // Update polygon styles
  state.layer.setStyle(featureStyle);

  // Update hover tooltip content (since metric/HSN changed)
  for (const lyr of state.featureLayers){
    const div = lyr.__divisionName || "—";
    if (lyr.getTooltip()){
      lyr.setTooltipContent(tooltipHTML(div));
    }
  }

  // KPI cards
  const m = state.dataIndex["MANDOLI"]?.[state.hsn] || {};
  const g = state.dataIndex["GANDHINAGAR"]?.[state.hsn] || {};

  document.getElementById("kpiMandoli").innerHTML =
    `<div style="font-weight:800; font-size:14px;">Mandoli</div>
     <div>Value: <b>${formatINR(m.z2)}</b></div>
     <div>YoY: <b>${formatPct(m.z3)}</b></div>`;

  document.getElementById("kpiGandhi").innerHTML =
    `<div style="font-weight:800; font-size:14px;">Gandhinagar</div>
     <div>Value: <b>${formatINR(g.z2)}</b></div>
     <div>YoY: <b>${formatPct(g.z3)}</b></div>`;
}

function bindUI(){
  document.querySelectorAll(".chip").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".chip").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.metric = btn.dataset.metric;
      render();
    });
  });
}

init().catch(err => console.error(err));
