const PATHS = {
  geo: "/data/GST East Delhi Divisions.geojson",
  mandoli: "/data/Mandoli.csv",
  gandhi: "/data/Gandhinagar.csv",
  delhiEast: "/data/Delhi East.csv",
};

let state = {
  hsn: null,
  metric: "z2",
  regionFocus: "MANDOLI",
  geojson: null,
  layer: null,
  dataIndex: {},
  hsns: [],
};

function parseNumber(x){
  if (x === null || x === undefined) return null;
  const n = Number(String(x).replace(/,/g,''));
  return Number.isFinite(n) ? n : null;
}

function formatINR(n){
  if (n === null) return "—";
  return n.toLocaleString("en-IN",{maximumFractionDigits:0});
}

function formatPct(n){
  if (n === null) return "—";
  return (n*100).toFixed(1)+"%";
}

function loadCSV(url){
  return new Promise((resolve,reject)=>{
    Papa.parse(url,{
      download:true,
      header:true,
      skipEmptyLines:true,
      complete:(res)=>resolve(res.data),
      error:reject
    });
  });
}

async function init(){

  const [geoRes,mandoliRows,gandhiRows] = await Promise.all([
    fetch(PATHS.geo).then(r=>r.json()),
    loadCSV(PATHS.mandoli),
    loadCSV(PATHS.gandhi)
  ]);

  state.geojson = geoRes;

  buildIndex(mandoliRows);
  buildIndex(gandhiRows);

  state.hsns = [...new Set(state.hsns)].sort((a,b)=>a-b);
  state.hsn = state.hsns[0];

  buildHSNDropdown();
  initMap();
  render();
  bindUI();
}

function buildIndex(rows){

  for(const r of rows){

    const division = String(r["Division"]||"").trim().toUpperCase();
    const hsn = parseNumber(r["HSN Code"]);

    if(!division || !hsn) continue;

    const z2 = parseNumber(r["Taxable value 24_25_z2"]);
    const z3 = parseNumber(r["YoY growth_z3"]);

    if(!state.dataIndex[division]) state.dataIndex[division] = {};
    state.dataIndex[division][hsn] = {z2,z3};

    state.hsns.push(hsn);
  }
}

function buildHSNDropdown(){

  const sel = document.getElementById("hsnSelect");

  for(const hsn of state.hsns){

    const opt = document.createElement("option");
    opt.value = hsn;
    opt.textContent = "HSN Code: "+hsn;

    sel.appendChild(opt);
  }

  sel.value = state.hsn;

  sel.addEventListener("change",()=>{
    state.hsn = Number(sel.value);
    render();
  });
}

function getDivisionName(feature){

  const p = feature.properties || {};
  return (p.Division_Map || "").toUpperCase();
}

function initMap(){

  const map = L.map("map",{zoomControl:false}).setView([28.63,77.28],11);
  state.map = map;

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{}).addTo(map);

  state.layer = L.geoJSON(state.geojson,{
    style:featureStyle,
    onEachFeature:(feature,layer)=>{
      const name = getDivisionName(feature);
      layer.bindTooltip(name,{sticky:true});
    }
  }).addTo(map);
}

function colorForMetric(v,metric){

  if(metric==="z2"){

    const vals = ["MANDOLI","GANDHINAGAR"]
      .map(d=>state.dataIndex[d]?.[state.hsn]?.z2)
      .filter(x=>x!=null);

    const min = Math.min(...vals);
    const max = Math.max(...vals);

    const t = (max===min)?0.7:(v-min)/(max-min);

    return chroma.scale(["#f1f5f9","#1e3a8a"])(t).hex();
  }

  const clamp = Math.max(-0.5,Math.min(0.5,v));
  const t = (clamp+0.5)/1;

  return chroma.scale(["#9f1239","#f8fafc","#0f766e"])(t).hex();
}

function featureStyle(feature){

  const division = getDivisionName(feature);

  const v = state.dataIndex[division]?.[state.hsn]?.[state.metric] ?? null;

  const isTarget = division==="MANDOLI" || division==="GANDHINAGAR";

  let fill = isTarget ? "#e2e8f0" : "#f8fafc";

  if(isTarget && v!=null) fill = colorForMetric(v,state.metric);

  return {
    color:"#334155",
    weight: division===state.regionFocus ? 2.2 : 1,
    fillColor:fill,
    fillOpacity: isTarget ? 0.75 : 0.25
  };
}

function render(){

  state.layer.setStyle(featureStyle);

  const m = state.dataIndex["MANDOLI"]?.[state.hsn] || {};
  const g = state.dataIndex["GANDHINAGAR"]?.[state.hsn] || {};

  document.getElementById("kpiMandoli").innerHTML =
    `<b>Mandoli</b><br>
     Value: ${formatINR(m.z2)}<br>
     YoY: ${formatPct(m.z3)}`;

  document.getElementById("kpiGandhi").innerHTML =
    `<b>Gandhinagar</b><br>
     Value: ${formatINR(g.z2)}<br>
     YoY: ${formatPct(g.z3)}`;
}

function bindUI(){

  document.querySelectorAll(".chip").forEach(btn=>{

    btn.addEventListener("click",()=>{

      document.querySelectorAll(".chip").forEach(b=>b.classList.remove("active"));

      btn.classList.add("active");

      state.metric = btn.dataset.metric;

      render();
    });
  });

  document.querySelectorAll(".tab").forEach(btn=>{

    btn.addEventListener("click",()=>{

      document.querySelectorAll(".tab").forEach(b=>b.classList.remove("active"));

      btn.classList.add("active");

      state.regionFocus = btn.dataset.region;

      render();
    });
  });
}

init();
