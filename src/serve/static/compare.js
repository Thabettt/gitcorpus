/* compare.js — Cross Stack Comparison Dashboard
 * Full client-side implementation of all charts from shared_viz_tool/app.py
 * Requires: Chart.js 4, PapaParse 5
 */
(function () {
"use strict";

// ── Constants ──────────────────────────────────────────────────────────────────
const STACK_COLORS = {
  "TypeScript/JavaScript": "#F0A500",
  "Python":                "#3776AB",
  "Java":                  "#ED8B00",
  "Rust":                  "#CE422B",
  "C#":                    "#178600",
  "C++":                   "#00599C",
};
const PALETTE = [
  "#1d3557","#457b9d","#2a9d8f","#e9c46a","#f4a261",
  "#e76f51","#8ecae6","#6a994e","#bc4749","#a8dadc",
  "#264653","#d4a373","#588157","#c77dff","#f72585",
];
const INCOME_MAP = {
  "United States":"HIC","United Kingdom":"HIC","Germany":"HIC","France":"HIC",
  "Japan":"HIC","South Korea":"HIC","Australia":"HIC","Canada":"HIC",
  "Israel":"HIC","United Arab Emirates":"HIC","UAE":"HIC","Sweden":"HIC",
  "Switzerland":"HIC","Netherlands":"HIC","Denmark":"HIC","Singapore":"HIC",
  "Taiwan":"HIC","Belgium":"HIC","Norway":"HIC","Austria":"HIC",
  "Finland":"HIC","New Zealand":"HIC","Ireland":"HIC","Hong Kong":"HIC",
  "Italy":"HIC","Spain":"HIC","Portugal":"HIC","Czech Republic":"HIC",
  "Saudi Arabia":"HIC","Greece":"HIC","Cyprus":"HIC","Estonia":"HIC",
  "Latvia":"HIC","Lithuania":"HIC","Slovakia":"HIC","Slovenia":"HIC",
  "Luxembourg":"HIC",
  "China":"UMIC","Brazil":"UMIC","Turkey":"UMIC","Russia":"UMIC",
  "Mexico":"UMIC","Argentina":"UMIC","Thailand":"UMIC","Malaysia":"UMIC",
  "Colombia":"UMIC","Ukraine":"UMIC","South Africa":"UMIC","Poland":"UMIC",
  "Romania":"UMIC","Bulgaria":"UMIC","Serbia":"UMIC","Chile":"UMIC",
  "Egypt":"UMIC","Georgia":"UMIC","Kazakhstan":"UMIC","Uzbekistan":"UMIC",
  "Algeria":"UMIC","Tunisia":"UMIC","Hungary":"UMIC","Peru":"UMIC",
  "Venezuela":"UMIC","Ecuador":"UMIC","Azerbaijan":"UMIC",
  "Bosnia and Herzegovina":"UMIC","Albania":"UMIC","Jordan":"UMIC",
  "Armenia":"UMIC","Croatia":"UMIC",
  "India":"LMIC","Vietnam":"LMIC","Philippines":"LMIC","Indonesia":"LMIC",
  "Bangladesh":"LMIC","Pakistan":"LMIC","Nigeria":"LMIC","Ghana":"LMIC",
  "Kenya":"LMIC","Morocco":"LMIC","Sri Lanka":"LMIC","Nepal":"LMIC",
  "Ethiopia":"LMIC","Iran":"LMIC","Bolivia":"LMIC","Honduras":"LMIC",
  "Nicaragua":"LMIC","Senegal":"LMIC","Tanzania":"LMIC","Cameroon":"LMIC",
  "Palestine":"LMIC",
  "Rwanda":"LIC","Uganda":"LIC","Mali":"LIC","Niger":"LIC",
  "Mozambique":"LIC","Madagascar":"LIC",
};
const INCOME_ORDER  = ["HIC","UMIC","LMIC","LIC"];
const INCOME_LABELS = {"HIC":"High Income","UMIC":"Upper-Middle","LMIC":"Lower-Middle","LIC":"Low Income"};
const MENA_COUNTRIES = new Set([
  "Algeria","Bahrain","Egypt","Iran","Iraq","Israel","Jordan",
  "Kuwait","Lebanon","Libya","Morocco","Oman","Palestine",
  "Qatar","Saudi Arabia","Syria","Tunisia","Turkey",
  "United Arab Emirates","UAE","Yemen",
]);
const REGION_MAP = {
  "United States":"North America","Canada":"North America",
  "Mexico":"Latin America","Brazil":"Latin America","Argentina":"Latin America",
  "Colombia":"Latin America","Chile":"Latin America","Peru":"Latin America",
  "Venezuela":"Latin America","Ecuador":"Latin America",
  "Honduras":"Latin America","Nicaragua":"Latin America","Bolivia":"Latin America",
  "United Kingdom":"Western Europe","Germany":"Western Europe","France":"Western Europe",
  "Netherlands":"Western Europe","Spain":"Western Europe","Italy":"Western Europe",
  "Sweden":"Western Europe","Switzerland":"Western Europe","Belgium":"Western Europe",
  "Austria":"Western Europe","Denmark":"Western Europe","Finland":"Western Europe",
  "Norway":"Western Europe","Portugal":"Western Europe","Ireland":"Western Europe",
  "Luxembourg":"Western Europe",
  "Russia":"Eastern Europe","Poland":"Eastern Europe","Ukraine":"Eastern Europe",
  "Romania":"Eastern Europe","Czech Republic":"Eastern Europe","Hungary":"Eastern Europe",
  "Bulgaria":"Eastern Europe","Serbia":"Eastern Europe","Croatia":"Eastern Europe",
  "Slovakia":"Eastern Europe","Slovenia":"Eastern Europe","Estonia":"Eastern Europe",
  "Latvia":"Eastern Europe","Lithuania":"Eastern Europe",
  "Bosnia and Herzegovina":"Eastern Europe","Albania":"Eastern Europe",
  "Georgia":"Eastern Europe","Armenia":"Eastern Europe","Azerbaijan":"Eastern Europe",
  "Kazakhstan":"Eastern Europe","Uzbekistan":"Eastern Europe",
  "Egypt":"MENA","Israel":"MENA","Saudi Arabia":"MENA","Turkey":"MENA",
  "UAE":"MENA","United Arab Emirates":"MENA","Jordan":"MENA","Morocco":"MENA",
  "Tunisia":"MENA","Algeria":"MENA","Iran":"MENA","Iraq":"MENA",
  "Palestine":"MENA","Lebanon":"MENA","Qatar":"MENA","Kuwait":"MENA",
  "Bahrain":"MENA","Oman":"MENA","Libya":"MENA","Yemen":"MENA","Syria":"MENA",
  "Nigeria":"Sub-Saharan Africa","Kenya":"Sub-Saharan Africa","Ghana":"Sub-Saharan Africa",
  "South Africa":"Sub-Saharan Africa","Ethiopia":"Sub-Saharan Africa",
  "Tanzania":"Sub-Saharan Africa","Senegal":"Sub-Saharan Africa",
  "Cameroon":"Sub-Saharan Africa","Rwanda":"Sub-Saharan Africa","Uganda":"Sub-Saharan Africa",
  "Mali":"Sub-Saharan Africa","Niger":"Sub-Saharan Africa",
  "Mozambique":"Sub-Saharan Africa","Madagascar":"Sub-Saharan Africa",
  "India":"South Asia","Pakistan":"South Asia","Bangladesh":"South Asia",
  "Sri Lanka":"South Asia","Nepal":"South Asia",
  "China":"East Asia","Japan":"East Asia","South Korea":"East Asia",
  "Taiwan":"East Asia","Hong Kong":"East Asia",
  "Vietnam":"Southeast Asia","Indonesia":"Southeast Asia","Philippines":"Southeast Asia",
  "Malaysia":"Southeast Asia","Thailand":"Southeast Asia","Singapore":"Southeast Asia",
  "Australia":"Oceania","New Zealand":"Oceania",
};
const REGION_ORDER = [
  "North America","Western Europe","East Asia","South Asia",
  "Eastern Europe","Latin America","MENA","Southeast Asia","Sub-Saharan Africa","Oceania",
];
const PAID_TOOLS = new Set([
  "claude code","claude code / generic","junie","devin","roo code",
  "codegen","factory","greptile","ellipsis","amp","openai codex",
]);
const FREE_TOOLS = new Set([
  "github copilot","cursor","windsurf","codeium","aider","continue",
  "gemini cli","opencode","openhands","swe-agent","amazon q","kiro",
  "coderabbit","sweep","jules","replit","deepsource","pr-agent","sourcery",
]);

// ── State ──────────────────────────────────────────────────────────────────────
const stacks  = [];   // [{label, filename, rows}]
const charts  = {};   // keyed by canvas id
let   filters = {
  selectedStacks: null,  // null = all; Set of labels when filtered
  dateFrom: null,
  dateTo:   null,
  scope:    "all",       // "all" | "agentic"
  minCountry: 10,
  eco:      {},          // col → [allowed vals]
  topAgents:    8,
  topCountries: 10,
  heatmapN:     15,
  bumpN:        12,
  cumulN:       10,
  menaMin:      5,
  topDensity:   12,
};

// ── Helpers ────────────────────────────────────────────────────────────────────
function wilsonCI(k, n) {
  if (n === 0) return { lo: 0, mid: 0, hi: 0 };
  const z = 1.96, p = k / n;
  const d = 1 + z * z / n;
  const c = (p + z * z / (2 * n)) / d;
  const s = (z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d;
  return { lo: Math.max(0, c - s), mid: c, hi: Math.min(1, c + s) };
}
function pct(v, dec) { return (v * 100).toFixed(dec === undefined ? 1 : dec) + "%"; }

function stackColor(label, fallbackIdx) {
  return STACK_COLORS[label] || PALETTE[(fallbackIdx || 0) % PALETTE.length];
}
function stackColorForLabel(label) {
  if (STACK_COLORS[label]) return STACK_COLORS[label];
  const idx = stacks.findIndex(s => s.label === label);
  return PALETTE[(idx < 0 ? 0 : idx) % PALETTE.length];
}

function getAdoptionLabel(row) {
  const lbl = (row.adoption_label || "").trim().toLowerCase();
  if (lbl) return lbl;
  const lvl = (row.adoption_level || "").trim().toLowerCase();
  if (!lvl || lvl === "none") return "none";
  return "agentic";
}
function isAdopted(label) {
  if (filters.scope === "agentic") return label === "agentic";
  return label === "agentic" || label === "ai_assisted";
}
function parseAgents(row) {
  const raw = (row.agents_found || row.agents || "").trim();
  if (!raw) return [];
  return raw.split("|").map(a => a.trim()).filter(Boolean);
}
function getCountry(row) {
  const c = (row.country || row.inferred_country || "").trim();
  return c && c !== "not_specified" && c !== "unknown" ? c : null;
}
function getMonth(row) {
  const d = (row.created_at || row.first_signal_at || "").trim().slice(0, 7);
  return d.length === 7 ? d : null;
}
function getAIDensity(row) {
  const v = parseFloat(row.commit_ratio != null ? row.commit_ratio : (row.ai_density != null ? row.ai_density : ""));
  return isNaN(v) ? null : Math.min(1, Math.max(0, v));
}
function classifyPricing(name) {
  const n = name.trim().toLowerCase();
  if (PAID_TOOLS.has(n)) return "paid";
  if (FREE_TOOLS.has(n)) return "free";
  return "ambiguous";
}
function densityBucket(d) {
  if (d === 0)      return "Config-only (0%)";
  if (d < 0.10)    return "Low (<10%)";
  if (d < 0.40)    return "Medium (10–40%)";
  if (d < 0.80)    return "High (40–80%)";
  return "Full (≥80%)";
}
const DENSITY_BUCKET_ORDER = ["Config-only (0%)","Low (<10%)","Medium (10–40%)","High (40–80%)","Full (≥80%)"];

function enrichRow(row) {
  const lbl = getAdoptionLabel(row);
  const country = getCountry(row);
  return Object.assign({}, row, {
    _lbl:     lbl,
    _adopted: isAdopted(lbl),
    _country: country,
    _region:  country ? (REGION_MAP[country] || null)   : null,
    _income:  country ? (INCOME_MAP[country] || null)   : null,
    _is_mena: country ? MENA_COUNTRIES.has(country)     : false,
    _month:   getMonth(row),
    _density: getAIDensity(row),
    _agents:  parseAgents(row),
  });
}

// ── Filtered rows ──────────────────────────────────────────────────────────────
function getFilteredRows(onlyStacks) {
  const rows = [];
  for (const s of stacks) {
    if (filters.selectedStacks && !filters.selectedStacks.has(s.label)) continue;
    if (onlyStacks && !onlyStacks.includes(s.label)) continue;
    for (const r of s.rows) {
      const er = enrichRow(r);
      if (filters.dateFrom && er._month && er._month < filters.dateFrom) continue;
      if (filters.dateTo   && er._month && er._month > filters.dateTo)   continue;
      let pass = true;
      for (const [col, vals] of Object.entries(filters.eco)) {
        if (!vals || vals.length === 0) continue;
        const v = er[col];
        if (v != null && v !== "" && !vals.includes(String(v))) { pass = false; break; }
      }
      if (!pass) continue;
      rows.push(er);
    }
  }
  return rows;
}

function getStackRows(stackLabel) {
  return getFilteredRows([stackLabel]);
}

// ── Chart infrastructure ───────────────────────────────────────────────────────
function getTheme() {
  const s = getComputedStyle(document.documentElement);
  return {
    text:   s.getPropertyValue("--gc-text").trim()   || "#201d16",
    grid:   s.getPropertyValue("--gc-border").trim() || "#e2dbc6",
    muted:  s.getPropertyValue("--gc-muted").trim()  || "#6d6554",
    surface:s.getPropertyValue("--gc-surface").trim()|| "#fffdf8",
  };
}
function destroyChart(id) {
  if (charts[id]) { charts[id].destroy(); delete charts[id]; }
}
function destroyPrefix(prefix) {
  Object.keys(charts).filter(k => k.startsWith(prefix)).forEach(k => { charts[k].destroy(); delete charts[k]; });
}
function mkChart(id, type, data, options) {
  destroyChart(id);
  const el = document.getElementById(id);
  if (!el) return null;
  const c = new Chart(el.getContext("2d"), { type, data, options });
  charts[id] = c;
  return c;
}

function commonOpts(overrides) {
  const th = getTheme();
  return Object.assign({
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 300 },
    plugins: {
      legend: { labels: { color: th.text, font: { size: 11 } } },
      tooltip: { mode: "index", intersect: false },
    },
    scales: {
      x: { ticks: { color: th.text }, grid: { color: th.grid } },
      y: { ticks: { color: th.text }, grid: { color: th.grid } },
    },
  }, overrides || {});
}

// Error-bar plugin (draws whiskers on bar charts where ds.errorBars is set)
const errorBarPlugin = {
  id: "errorBar",
  afterDatasetsDraw(chart) {
    const { ctx } = chart;
    chart.data.datasets.forEach((ds, di) => {
      if (!ds.errorBars) return;
      const meta = chart.getDatasetMeta(di);
      meta.data.forEach((bar, i) => {
        const ci = ds.errorBars[i];
        if (!ci) return;
        const isHoriz = chart.options.indexAxis === "y";
        ctx.save();
        ctx.strokeStyle = "#333";
        ctx.lineWidth = 1.5;
        if (isHoriz) {
          const y = bar.y, xLo = chart.scales.x.getPixelForValue(ci.lo * 100), xHi = chart.scales.x.getPixelForValue(ci.hi * 100);
          ctx.beginPath(); ctx.moveTo(xLo, y); ctx.lineTo(xHi, y); ctx.stroke();
          ctx.beginPath(); ctx.moveTo(xLo, y - 5); ctx.lineTo(xLo, y + 5); ctx.stroke();
          ctx.beginPath(); ctx.moveTo(xHi, y - 5); ctx.lineTo(xHi, y + 5); ctx.stroke();
        } else {
          const x = bar.x, yLo = chart.scales.y.getPixelForValue(ci.lo * 100), yHi = chart.scales.y.getPixelForValue(ci.hi * 100);
          ctx.beginPath(); ctx.moveTo(x, yLo); ctx.lineTo(x, yHi); ctx.stroke();
          ctx.beginPath(); ctx.moveTo(x - 5, yLo); ctx.lineTo(x + 5, yLo); ctx.stroke();
          ctx.beginPath(); ctx.moveTo(x - 5, yHi); ctx.lineTo(x + 5, yHi); ctx.stroke();
        }
        ctx.restore();
      });
    });
  },
};
Chart.register(errorBarPlugin);

// ── Per-stack grid helper ──────────────────────────────────────────────────────
function buildPerStackGrid(containerId, stackLabels, buildFn) {
  const container = document.getElementById(containerId);
  if (!container) return;
  // Destroy charts whose IDs start with containerId
  destroyPrefix(containerId + "-");
  container.innerHTML = "";
  if (!stackLabels.length) return;
  const grid = document.createElement("div");
  grid.className = "compare-per-stack-grid";
  stackLabels.forEach(label => {
    const card = document.createElement("div");
    card.className = "compare-chart-card";
    const h4 = document.createElement("h4"); h4.textContent = label; card.appendChild(h4);
    const wrap = document.createElement("div"); wrap.className = "compare-chart-wrap"; card.appendChild(wrap);
    const canvas = document.createElement("canvas");
    const id = containerId + "-" + label.replace(/[^a-zA-Z0-9]/g, "_");
    canvas.id = id; wrap.appendChild(canvas); grid.appendChild(card);
    buildFn(id, label);
  });
  container.appendChild(grid);
}

// ── HTML heatmap helper ────────────────────────────────────────────────────────
function colorCell(val, max) {
  if (val == null || isNaN(val)) return "background:#ccc;color:#666";
  const v = Math.min(1, val / (max || 100));
  const r = Math.round(255 * Math.min(1, 2 * (1 - v)));
  const g = Math.round(200 * Math.min(1, 2 * v));
  const b = 50;
  return `background:rgb(${r},${g},${b});color:${v > 0.5 ? "#fff" : "#111"}`;
}
function buildHeatmapTable(containerId, rows, cols, cellFn, rowLabel, colLabel) {
  const wrap = document.getElementById(containerId);
  if (!wrap) return;
  let html = `<div class="compare-heatmap-scroll"><table class="compare-heatmap-table"><thead><tr><th>${rowLabel || ""}</th>`;
  cols.forEach(c => { html += `<th>${c}</th>`; });
  html += "</tr></thead><tbody>";
  rows.forEach(row => {
    html += `<tr><td><strong>${row}</strong></td>`;
    cols.forEach(col => {
      const { val, label } = cellFn(row, col);
      html += `<td style="${colorCell(val, 100)}">${label}</td>`;
    });
    html += "</tr>";
  });
  html += "</tbody></table></div>";
  wrap.innerHTML = html;
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 1: OVERVIEW
// ══════════════════════════════════════════════════════════════════════════════
function renderOverview() {
  const all = getFilteredRows();
  const stackLabels = [...new Set(all.map(r => r._stack || r.stack))];
  const th = getTheme();

  // Compute per-stack summary
  const summary = stackLabels.map(lbl => {
    const rows = all.filter(r => (r._stack || r.stack) === lbl);
    const n    = rows.length;
    const ag   = rows.filter(r => r._lbl === "agentic").length;
    const ai   = rows.filter(r => r._lbl === "ai_assisted").length;
    const adopted = rows.filter(r => r._adopted).length;
    const ci   = wilsonCI(adopted, n);
    return { lbl, n, ag, ai, adopted, ci };
  });

  // Adoption bars
  mkChart("chart-adoption-bars", "bar", {
    labels: summary.map(s => s.lbl),
    datasets: [{
      label: "Adoption Rate",
      data: summary.map(s => s.ci.mid * 100),
      backgroundColor: summary.map(s => stackColorForLabel(s.lbl) + "cc"),
      borderColor:     summary.map(s => stackColorForLabel(s.lbl)),
      borderWidth: 2, borderRadius: 4,
      errorBars: summary.map(s => ({ lo: s.ci.lo, hi: s.ci.hi })),
    }],
  }, commonOpts({
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: ctx => {
            const s = summary[ctx.dataIndex];
            return [`Rate: ${pct(s.ci.mid)}`, `95% CI: [${pct(s.ci.lo)}, ${pct(s.ci.hi)}]`, `Adopted: ${s.adopted} / ${s.n}`];
          }
        }
      }
    },
    scales: {
      x: { ticks: { color: th.text }, grid: { color: th.grid } },
      y: { min: 0, max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } },
    },
  }));

  // Stacked split bar
  mkChart("chart-adoption-split", "bar", {
    labels: summary.map(s => s.lbl),
    datasets: [
      { label: "Agentic",      data: summary.map(s => s.n > 0 ? s.ag   / s.n * 100 : 0), backgroundColor: "#2196F3cc", borderRadius: 2 },
      { label: "AI-Assisted",  data: summary.map(s => s.n > 0 ? s.ai   / s.n * 100 : 0), backgroundColor: "#81D4FAcc", borderRadius: 2 },
      { label: "No AI",        data: summary.map(s => s.n > 0 ? (s.n - s.ag - s.ai) / s.n * 100 : 0), backgroundColor: "#E0E0E0cc", borderRadius: 2 },
    ],
  }, commonOpts({
    scales: {
      x: { stacked: true, ticks: { color: th.text }, grid: { color: th.grid } },
      y: { stacked: true, min: 0, max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } },
    },
  }));

  // Summary table
  const tbody = document.getElementById("compare-summary-tbody");
  if (tbody) {
    tbody.innerHTML = summary.map((s, i) => `<tr>
      <td><span class="compare-stack-dot" style="background:${stackColorForLabel(s.lbl)}"></span>${s.lbl}</td>
      <td>${s.n.toLocaleString()}</td>
      <td>${s.adopted.toLocaleString()}</td>
      <td>${s.ag.toLocaleString()}</td>
      <td>${s.ai.toLocaleString()}</td>
      <td><strong>${pct(s.ci.mid)}</strong></td>
      <td>${pct(s.ci.lo)}</td>
      <td>${pct(s.ci.hi)}</td>
    </tr>`).join("");
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 2: AGENTS
// ══════════════════════════════════════════════════════════════════════════════
function renderAgents() {
  const all = getFilteredRows();
  const stackLabels = [...new Set(all.map(r => r._stack || r.stack))];
  const th = getTheme();
  const topN = filters.topAgents;

  // Top agents per stack (per-stack grid)
  buildPerStackGrid("compare-agents-top-stacks", stackLabels, (id, lbl) => {
    const rows = all.filter(r => (r._stack || r.stack) === lbl);
    const counts = {};
    rows.forEach(r => r._agents.forEach(a => { counts[a] = (counts[a] || 0) + 1; }));
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, topN).reverse();
    if (!sorted.length) return;
    mkChart(id, "bar", {
      labels: sorted.map(([a]) => a),
      datasets: [{ label: "Repos", data: sorted.map(([,c]) => c),
        backgroundColor: stackColorForLabel(lbl) + "cc", borderColor: stackColorForLabel(lbl), borderWidth: 1, borderRadius: 3 }],
    }, commonOpts({ indexAxis: "y", plugins: { legend: { display: false } },
      scales: { x: { ticks: { color: th.text }, grid: { color: th.grid } }, y: { ticks: { color: th.text }, grid: { display: false } } } }));
  });

  // Tool loyalty
  const loyaltyData = stackLabels.map(lbl => {
    const rows = all.filter(r => (r._stack || r.stack) === lbl && r._lbl === "agentic");
    if (!rows.length) return { lbl, single: 0, multi: 0 };
    const n = rows.length;
    const single = rows.filter(r => r._agents.length === 1).length;
    const multi  = rows.filter(r => r._agents.length  > 1).length;
    return { lbl, single: single / n * 100, multi: multi / n * 100 };
  });
  mkChart("chart-tool-loyalty", "bar", {
    labels: loyaltyData.map(d => d.lbl),
    datasets: [
      { label: "Single-tool", data: loyaltyData.map(d => d.single), backgroundColor: "#4C72B0cc", borderRadius: 3 },
      { label: "Multi-tool",  data: loyaltyData.map(d => d.multi),  backgroundColor: "#DD8452cc", borderRadius: 3 },
    ],
  }, commonOpts({ scales: { x: { stacked: true, ticks: { color: th.text }, grid: { color: th.grid } }, y: { stacked: true, max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } } } }));

  // Agent diversity
  mkChart("chart-agent-diversity", "bar", {
    labels: loyaltyData.map(d => d.lbl),
    datasets: [
      { label: "Single-agent", data: loyaltyData.map(d => d.single), backgroundColor: "#4C72B0cc", borderRadius: 3 },
      { label: "Multi-agent",  data: loyaltyData.map(d => d.multi),  backgroundColor: "#DD8452cc", borderRadius: 3 },
    ],
  }, commonOpts({ scales: { x: { stacked: true, ticks: { color: th.text }, grid: { color: th.grid } }, y: { stacked: true, max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } } } }));

  // Commit density buckets
  const agentic = all.filter(r => r._lbl === "agentic" && r._density != null);
  const bucketData = stackLabels.map((lbl, si) => {
    const rows = agentic.filter(r => (r._stack || r.stack) === lbl);
    if (!rows.length) return null;
    const n = rows.length;
    return {
      label: lbl,
      data: DENSITY_BUCKET_ORDER.map(b => rows.filter(r => densityBucket(r._density) === b).length / n * 100),
      backgroundColor: stackColorForLabel(lbl) + "cc",
      borderColor: stackColorForLabel(lbl), borderWidth: 1, borderRadius: 3,
    };
  }).filter(Boolean);
  if (bucketData.length) {
    mkChart("chart-commit-depth", "bar", { labels: DENSITY_BUCKET_ORDER, datasets: bucketData },
      commonOpts({ scales: { x: { ticks: { color: th.text }, grid: { color: th.grid } }, y: { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } } } }));
  } else {
    destroyChart("chart-commit-depth");
    const el = document.getElementById("chart-commit-depth");
    if (el && el.parentNode) { const p = document.createElement("p"); p.className = "muted"; p.textContent = "No commit_ratio data in uploaded CSVs."; el.parentNode.replaceChild(p, el); }
  }

  // Density histogram per stack
  buildPerStackGrid("compare-commit-density-hist-stacks", stackLabels, (id, lbl) => {
    const rows = agentic.filter(r => (r._stack || r.stack) === lbl);
    if (!rows.length) return;
    const bins = 20; const binWidth = 1 / bins;
    const counts = new Array(bins).fill(0);
    rows.forEach(r => { const bi = Math.min(bins - 1, Math.floor(r._density / binWidth)); counts[bi]++; });
    const labels = Array.from({ length: bins }, (_, i) => pct(i * binWidth, 0));
    mkChart(id, "bar", {
      labels,
      datasets: [{ label: "Repos", data: counts, backgroundColor: stackColorForLabel(lbl) + "cc", borderColor: stackColorForLabel(lbl), borderWidth: 1, borderRadius: 2 }],
    }, commonOpts({ plugins: { legend: { display: false } },
      scales: { x: { ticks: { color: th.text, maxTicksLimit: 10 }, grid: { color: th.grid } }, y: { ticks: { color: th.text }, grid: { color: th.grid } } } }));
  });

  // Density by agent per stack
  buildPerStackGrid("compare-density-by-agent-stacks", stackLabels, (id, lbl) => {
    const rows = agentic.filter(r => (r._stack || r.stack) === lbl);
    if (!rows.length) return;
    const counts = {};
    rows.forEach(r => r._agents.forEach(a => { counts[a] = (counts[a] || 0) + 1; }));
    const topAgents = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, filters.topDensity).map(([a]) => a);
    const stats = topAgents.map(agent => {
      const densities = rows.filter(r => r._agents.includes(agent)).map(r => r._density).sort((a, b) => a - b);
      if (densities.length < 3) return null;
      const med = densities[Math.floor(densities.length / 2)];
      const q1  = densities[Math.floor(densities.length / 4)];
      const q3  = densities[Math.floor(3 * densities.length / 4)];
      return { agent, med, q1, q3, n: densities.length };
    }).filter(Boolean).sort((a, b) => a.med - b.med);
    if (!stats.length) return;
    mkChart(id, "bar", {
      labels: stats.map(s => s.agent),
      datasets: [{ label: "Median AI Density", data: stats.map(s => s.med * 100),
        backgroundColor: stackColorForLabel(lbl) + "cc", borderColor: stackColorForLabel(lbl), borderWidth: 1, borderRadius: 3,
        errorBars: stats.map(s => ({ lo: s.q1, hi: s.q3 })) }],
    }, commonOpts({ indexAxis: "y",
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => { const s = stats[ctx.dataIndex]; return [`Median: ${pct(s.med)}`, `IQR: ${pct(s.q1)} – ${pct(s.q3)}`, `n: ${s.n}`]; } } } },
      scales: { x: { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } }, y: { ticks: { color: th.text }, grid: { display: false } } } }));
  });
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 3: GEOGRAPHY
// ══════════════════════════════════════════════════════════════════════════════
function renderGeography() {
  const all = getFilteredRows();
  const stackLabels = [...new Set(all.map(r => r._stack || r.stack))];
  const th = getTheme();
  const geo = all.filter(r => r._country);

  // World regions
  const regions = REGION_ORDER.filter(r => geo.some(row => row._region === r));
  const regionDatasets = stackLabels.map(lbl => {
    const rows = geo.filter(r => (r._stack || r.stack) === lbl);
    return {
      label: lbl,
      data: regions.map(reg => {
        const g = rows.filter(r => r._region === reg);
        return g.length ? g.filter(r => r._adopted).length / g.length * 100 : 0;
      }),
      backgroundColor: stackColorForLabel(lbl) + "cc",
      borderColor: stackColorForLabel(lbl), borderWidth: 1, borderRadius: 3,
    };
  });
  if (regions.length) {
    mkChart("chart-world-regions", "bar", { labels: regions, datasets: regionDatasets },
      commonOpts({ scales: { x: { ticks: { color: th.text, maxTicksLimit: 15 }, grid: { color: th.grid } }, y: { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } } } }));
  }

  // Top/bottom countries per stack
  buildPerStackGrid("compare-countries-stacks", stackLabels, (id, lbl) => {
    const rows = geo.filter(r => (r._stack || r.stack) === lbl);
    const countryCounts = {};
    rows.forEach(r => {
      if (!countryCounts[r._country]) countryCounts[r._country] = { n: 0, adopted: 0 };
      countryCounts[r._country].n++;
      if (r._adopted) countryCounts[r._country].adopted++;
    });
    const stats = Object.entries(countryCounts)
      .filter(([, v]) => v.n >= filters.minCountry)
      .map(([c, v]) => ({ c, rate: v.adopted / v.n * 100 }))
      .sort((a, b) => b.rate - a.rate);
    if (!stats.length) return;
    const topN = stats.slice(0, filters.topCountries).reverse();
    mkChart(id, "bar", {
      labels: topN.map(s => s.c),
      datasets: [{ label: "Adoption Rate", data: topN.map(s => s.rate),
        backgroundColor: stackColorForLabel(lbl) + "cc", borderColor: stackColorForLabel(lbl), borderWidth: 1, borderRadius: 3 }],
    }, commonOpts({ indexAxis: "y",
      plugins: { legend: { display: false } },
      scales: { x: { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } }, y: { ticks: { color: th.text }, grid: { display: false } } } }));
  });

  // Income group
  const incomeDatasets = stackLabels.map(lbl => {
    const rows = geo.filter(r => (r._stack || r.stack) === lbl && r._income);
    return {
      label: lbl,
      data: INCOME_ORDER.map(ig => {
        const g = rows.filter(r => r._income === ig);
        return g.length ? g.filter(r => r._adopted).length / g.length * 100 : 0;
      }),
      backgroundColor: stackColorForLabel(lbl) + "cc",
      borderColor: stackColorForLabel(lbl), borderWidth: 1, borderRadius: 3,
    };
  });
  if (geo.some(r => r._income)) {
    mkChart("chart-income-group", "bar", { labels: INCOME_ORDER.map(k => INCOME_LABELS[k]), datasets: incomeDatasets },
      commonOpts({ scales: { x: { ticks: { color: th.text }, grid: { color: th.grid } }, y: { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } } } }));
  }

  // Pricing by income per stack
  buildPerStackGrid("compare-pricing-income-stacks", stackLabels, (id, lbl) => {
    const rows = geo.filter(r => (r._stack || r.stack) === lbl && r._income);
    if (!rows.length) return;
    const labels = INCOME_ORDER.map(k => INCOME_LABELS[k]);
    const adoptRates = INCOME_ORDER.map(ig => {
      const g = rows.filter(r => r._income === ig);
      return g.length ? g.filter(r => r._adopted).length / g.length * 100 : 0;
    });
    const paidPcts = INCOME_ORDER.map(ig => {
      const ag = rows.filter(r => r._income === ig && r._lbl === "agentic");
      if (!ag.length) return 0;
      return ag.filter(r => r._agents.some(a => classifyPricing(a) === "paid")).length / ag.length * 100;
    });
    const freePcts = INCOME_ORDER.map(ig => {
      const ag = rows.filter(r => r._income === ig && r._lbl === "agentic");
      if (!ag.length) return 0;
      return ag.filter(r => r._agents.some(a => classifyPricing(a) === "free")).length / ag.length * 100;
    });
    mkChart(id, "bar", {
      labels,
      datasets: [
        { label: "Adoption Rate", data: adoptRates, backgroundColor: "#1565C0cc", borderRadius: 3, order: 2 },
        { label: "Paid Tools %", data: paidPcts, type: "line", borderColor: "#E53935", backgroundColor: "transparent", pointRadius: 4, borderWidth: 2, order: 1 },
        { label: "Free Tools %", data: freePcts, type: "line", borderColor: "#43A047", backgroundColor: "transparent", pointRadius: 4, borderWidth: 2, order: 1 },
      ],
    }, commonOpts({ scales: { x: { ticks: { color: th.text }, grid: { color: th.grid } }, y: { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } } } }));
  });

  // MENA vs rest
  const menaData = stackLabels.map(lbl => {
    const rows = geo.filter(r => (r._stack || r.stack) === lbl);
    const mena    = rows.filter(r => r._is_mena);
    const nonMena = rows.filter(r => !r._is_mena);
    return {
      lbl,
      mena:    mena.length    ? mena.filter(r => r._adopted).length    / mena.length    * 100 : 0,
      nonMena: nonMena.length ? nonMena.filter(r => r._adopted).length / nonMena.length * 100 : 0,
    };
  });
  mkChart("chart-mena-vs-rest", "bar", {
    labels: menaData.map(d => d.lbl),
    datasets: [
      { label: "MENA",     data: menaData.map(d => d.mena),    backgroundColor: "#FF7043cc", borderRadius: 3 },
      { label: "Non-MENA", data: menaData.map(d => d.nonMena), backgroundColor: "#42A5F5cc", borderRadius: 3 },
    ],
  }, commonOpts({ scales: { x: { ticks: { color: th.text }, grid: { color: th.grid } }, y: { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } } } }));

  // MENA countries
  const menaRows = geo.filter(r => r._is_mena);
  const menaCounts = {};
  menaRows.forEach(r => {
    if (!menaCounts[r._country]) menaCounts[r._country] = { n: 0, adopted: 0 };
    menaCounts[r._country].n++;
    if (r._adopted) menaCounts[r._country].adopted++;
  });
  const menaStats = Object.entries(menaCounts)
    .filter(([, v]) => v.n >= filters.menaMin)
    .map(([c, v]) => ({ c, rate: v.adopted / v.n * 100 }))
    .sort((a, b) => a.rate - b.rate);
  if (menaStats.length) {
    mkChart("chart-mena-countries", "bar", {
      labels: menaStats.map(s => s.c),
      datasets: [{ label: "Adoption Rate", data: menaStats.map(s => s.rate),
        backgroundColor: "#FF7043cc", borderColor: "#FF7043", borderWidth: 1, borderRadius: 3 }],
    }, commonOpts({ indexAxis: "y", plugins: { legend: { display: false } },
      scales: { x: { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } }, y: { ticks: { color: th.text }, grid: { display: false } } } }));
  }

  // Country heatmap (requires created_at)
  const geoWithDate = geo.filter(r => r._month);
  if (geoWithDate.length) {
    const topN = filters.heatmapN;
    const ctryFreq = {};
    geoWithDate.forEach(r => { ctryFreq[r._country] = (ctryFreq[r._country] || 0) + 1; });
    const topCtries = Object.entries(ctryFreq).sort((a, b) => b[1] - a[1]).slice(0, topN).map(([c]) => c);
    const months = [...new Set(geoWithDate.map(r => r._month))].sort();
    buildHeatmapTable("compare-country-heatmap", topCtries, months, (c, m) => {
      const cell = geoWithDate.filter(r => r._country === c && r._month === m);
      if (cell.length < 5) return { val: null, label: "—" };
      const rate = cell.filter(r => r._adopted).length / cell.length * 100;
      return { val: rate, label: rate.toFixed(0) + "%" };
    }, "Country", "Month");
  }

  // Bump chart
  if (geoWithDate.length) {
    const topN = filters.bumpN;
    const ctryFreq = {};
    geoWithDate.forEach(r => { ctryFreq[r._country] = (ctryFreq[r._country] || 0) + 1; });
    const topCtries = Object.entries(ctryFreq).sort((a, b) => b[1] - a[1]).slice(0, topN).map(([c]) => c);
    const months = [...new Set(geoWithDate.map(r => r._month))].sort();
    const rankData = {};
    topCtries.forEach(c => { rankData[c] = []; });
    months.forEach(m => {
      const mRows = geoWithDate.filter(r => r._month === m);
      const rates = {};
      topCtries.forEach(c => {
        const g = mRows.filter(r => r._country === c);
        if (g.length >= 3) rates[c] = g.filter(r => r._adopted).length / g.length;
        else rates[c] = null;
      });
      const ranked = topCtries.filter(c => rates[c] != null).sort((a, b) => rates[b] - rates[a]);
      topCtries.forEach(c => { rankData[c].push(ranked.includes(c) ? ranked.indexOf(c) + 1 : null); });
    });
    const bumpDatasets = topCtries.map((c, i) => ({
      label: c,
      data: rankData[c],
      borderColor: PALETTE[i % PALETTE.length],
      backgroundColor: "transparent",
      pointRadius: 3, borderWidth: 2, tension: 0.3, spanGaps: false,
    }));
    mkChart("chart-country-bump", "line", { labels: months, datasets: bumpDatasets },
      commonOpts({
        plugins: { tooltip: { mode: "index" } },
        scales: {
          x: { ticks: { color: th.text, maxTicksLimit: 12 }, grid: { color: th.grid } },
          y: { reverse: true, min: 1, ticks: { color: th.text, stepSize: 1 }, grid: { color: th.grid } },
        },
      }));
  }

  // Cumulative
  if (geoWithDate.length) {
    const topN = filters.cumulN;
    const agentic = geoWithDate.filter(r => r._lbl === "agentic");
    const ctryFreq = {};
    agentic.forEach(r => { ctryFreq[r._country] = (ctryFreq[r._country] || 0) + 1; });
    const topCtries = Object.entries(ctryFreq).sort((a, b) => b[1] - a[1]).slice(0, topN).map(([c]) => c);
    const months = [...new Set(agentic.map(r => r._month))].sort();
    const cumDatasets = topCtries.map((c, i) => {
      let cum = 0;
      return {
        label: c,
        data: months.map(m => { cum += agentic.filter(r => r._country === c && r._month === m).length; return cum; }),
        borderColor: PALETTE[i % PALETTE.length],
        backgroundColor: "transparent",
        pointRadius: 2, borderWidth: 2, tension: 0.3,
      };
    });
    mkChart("chart-country-cumulative", "line", { labels: months, datasets: cumDatasets },
      commonOpts({ scales: { x: { ticks: { color: th.text, maxTicksLimit: 12 }, grid: { color: th.grid } }, y: { ticks: { color: th.text }, grid: { color: th.grid } } } }));
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 4: TIME SERIES
// ══════════════════════════════════════════════════════════════════════════════
function renderTimeSeries() {
  const all = getFilteredRows();
  const stackLabels = [...new Set(all.map(r => r._stack || r.stack))];
  const th = getTheme();
  const dated = all.filter(r => r._month);
  if (!dated.length) return;

  // Adoption rate by month (line)
  const months = [...new Set(dated.map(r => r._month))].sort();
  const tsDatasets = stackLabels.map(lbl => {
    return {
      label: lbl,
      data: months.map(m => {
        const g = dated.filter(r => (r._stack || r.stack) === lbl && r._month === m);
        if (g.length < 5) return null;
        return g.filter(r => r._adopted).length / g.length * 100;
      }),
      borderColor: stackColorForLabel(lbl),
      backgroundColor: stackColorForLabel(lbl) + "33",
      pointRadius: 3, borderWidth: 2, tension: 0.3, spanGaps: true,
    };
  });
  mkChart("chart-time-series", "line", { labels: months, datasets: tsDatasets },
    commonOpts({ scales: { x: { ticks: { color: th.text, maxTicksLimit: 12 }, grid: { color: th.grid } }, y: { ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } } } }));

  // Stacked area per stack (stacked bar in Chart.js)
  buildPerStackGrid("compare-stacked-area-stacks", stackLabels, (id, lbl) => {
    const rows = dated.filter(r => (r._stack || r.stack) === lbl);
    const ms = [...new Set(rows.map(r => r._month))].sort();
    mkChart(id, "bar", {
      labels: ms,
      datasets: [
        { label: "Agentic",     data: ms.map(m => rows.filter(r => r._month === m && r._lbl === "agentic").length),     backgroundColor: "#2196F3cc", borderRadius: 1 },
        { label: "AI-Assisted", data: ms.map(m => rows.filter(r => r._month === m && r._lbl === "ai_assisted").length), backgroundColor: "#81D4FAcc", borderRadius: 1 },
        { label: "No AI",       data: ms.map(m => rows.filter(r => r._month === m && r._lbl === "none").length),        backgroundColor: "#E0E0E0cc", borderRadius: 1 },
      ],
    }, commonOpts({ scales: { x: { stacked: true, ticks: { color: th.text, maxTicksLimit: 12 }, grid: { color: th.grid } }, y: { stacked: true, ticks: { color: th.text }, grid: { color: th.grid } } } }));
  });

  // Adoption timing stacked bar (uses commit_ratio as a proxy if adoption_timing not present)
  // This chart requires a "timing_category" column — if absent, derive from days between created_at and first_signal_at
  const timingRows = all.filter(r => r.timing_category || (r.created_at && r.first_signal_at));
  if (timingRows.length) {
    function getTimingCat(r) {
      if (r.timing_category) return r.timing_category;
      const days = (new Date(r.first_signal_at) - new Date(r.created_at)) / 86400000;
      if (days <= 7)  return "immediate";
      if (days <= 30) return "early";
      if (days > 30)  return "late";
      return "unknown";
    }
    const CAT_ORDER = ["immediate","early","late","unknown"];
    const CAT_COLORS = { immediate: "#2196F3cc", early: "#66BB6Acc", late: "#FF7043cc", unknown: "#9E9E9Ecc" };
    const CAT_LABELS = { immediate: "Immediate (≤7d)", early: "Early (8–30d)", late: "Late (>30d)", unknown: "Unknown" };
    const agentic = timingRows.filter(r => r._lbl === "agentic");
    if (agentic.length) {
      mkChart("chart-adoption-timing", "bar", {
        labels: stackLabels,
        datasets: CAT_ORDER.map(cat => ({
          label: CAT_LABELS[cat],
          data: stackLabels.map(lbl => {
            const g = agentic.filter(r => (r._stack || r.stack) === lbl);
            return g.length ? g.filter(r => getTimingCat(r) === cat).length / g.length * 100 : 0;
          }),
          backgroundColor: CAT_COLORS[cat], borderRadius: 2,
        })),
      }, commonOpts({ scales: { x: { stacked: true, ticks: { color: th.text }, grid: { color: th.grid } }, y: { stacked: true, max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } } } }));
    }
  }

  // Days to adoption histogram per stack
  buildPerStackGrid("compare-days-hist-stacks", stackLabels, (id, lbl) => {
    const rows = all.filter(r => (r._stack || r.stack) === lbl && r.days_to_adoption != null);
    if (!rows.length) return;
    const vals = rows.map(r => Math.min(365, parseFloat(r.days_to_adoption))).filter(v => !isNaN(v) && v >= 0);
    if (!vals.length) return;
    const bins = 36; const binSize = 365 / bins;
    const counts = new Array(bins).fill(0);
    vals.forEach(v => { const bi = Math.min(bins - 1, Math.floor(v / binSize)); counts[bi]++; });
    const labels = Array.from({ length: bins }, (_, i) => Math.round(i * binSize) + "d");
    mkChart(id, "bar", {
      labels,
      datasets: [{ label: "Repos", data: counts, backgroundColor: stackColorForLabel(lbl) + "cc", borderRadius: 2 }],
    }, commonOpts({ plugins: { legend: { display: false } }, scales: { x: { ticks: { color: th.text, maxTicksLimit: 10 }, grid: { color: th.grid } }, y: { ticks: { color: th.text }, grid: { color: th.grid } } } }));
  });
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 5: SIZE
// ══════════════════════════════════════════════════════════════════════════════
function renderSize() {
  const all = getFilteredRows();
  const stackLabels = [...new Set(all.map(r => r._stack || r.stack))];
  const th = getTheme();

  // Stars by tertile
  const withStars = all.filter(r => r.stars != null && r.stars !== "");
  if (withStars.length) {
    const TERTILE_LABELS = ["Small","Medium","Large"];
    const tertileDatasets = stackLabels.map(lbl => {
      const rows = withStars.filter(r => (r._stack || r.stack) === lbl).map(r => ({ ...r, _stars: parseFloat(r.stars) })).filter(r => !isNaN(r._stars)).sort((a, b) => a._stars - b._stars);
      if (rows.length < 3) return null;
      const t = Math.floor(rows.length / 3);
      const groups = [rows.slice(0, t), rows.slice(t, 2 * t), rows.slice(2 * t)];
      return {
        label: lbl,
        data: groups.map(g => g.filter(r => r._adopted).length / (g.length || 1) * 100),
        backgroundColor: stackColorForLabel(lbl) + "cc",
        borderColor: stackColorForLabel(lbl), borderWidth: 1, borderRadius: 3,
      };
    }).filter(Boolean);
    if (tertileDatasets.length) {
      mkChart("chart-size-tertile", "bar", { labels: TERTILE_LABELS, datasets: tertileDatasets },
        commonOpts({ scales: { x: { ticks: { color: th.text }, grid: { color: th.grid } }, y: { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } } } }));
    }

    // Median stars by adoption category
    const CAT_LABELS = ["No AI","AI-Assisted","Agentic"];
    const CAT_KEYS   = ["none","ai_assisted","agentic"];
    const starsDatasets = stackLabels.map(lbl => {
      const rows = withStars.filter(r => (r._stack || r.stack) === lbl);
      return {
        label: lbl,
        data: CAT_KEYS.map(cat => {
          const g = rows.filter(r => r._lbl === cat).map(r => parseFloat(r.stars)).filter(v => !isNaN(v)).sort((a, b) => a - b);
          return g.length ? g[Math.floor(g.length / 2)] : 0;
        }),
        backgroundColor: stackColorForLabel(lbl) + "cc", borderColor: stackColorForLabel(lbl), borderWidth: 1, borderRadius: 3,
      };
    });
    mkChart("chart-size-stars", "bar", { labels: CAT_LABELS, datasets: starsDatasets },
      commonOpts({ scales: { x: { ticks: { color: th.text }, grid: { color: th.grid } }, y: { ticks: { color: th.text }, grid: { color: th.grid } } } }));
  }

  // Median commits by adoption category (if column exists)
  const withCommits = all.filter(r => r.commits != null && r.commits !== "");
  if (withCommits.length) {
    const CAT_LABELS = ["No AI","AI-Assisted","Agentic"];
    const CAT_KEYS   = ["none","ai_assisted","agentic"];
    const commitsDatasets = stackLabels.map(lbl => {
      const rows = withCommits.filter(r => (r._stack || r.stack) === lbl);
      return {
        label: lbl,
        data: CAT_KEYS.map(cat => {
          const g = rows.filter(r => r._lbl === cat).map(r => parseFloat(r.commits)).filter(v => !isNaN(v)).sort((a, b) => a - b);
          return g.length ? g[Math.floor(g.length / 2)] : 0;
        }),
        backgroundColor: stackColorForLabel(lbl) + "cc", borderColor: stackColorForLabel(lbl), borderWidth: 1, borderRadius: 3,
      };
    });
    mkChart("chart-size-commits", "bar", { labels: CAT_LABELS, datasets: commitsDatasets },
      commonOpts({ scales: { x: { ticks: { color: th.text }, grid: { color: th.grid } }, y: { ticks: { color: th.text }, grid: { color: th.grid } } } }));
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 6: DEPTH & ECOSYSTEMS
// ══════════════════════════════════════════════════════════════════════════════
function renderDepth() {
  const all = getFilteredRows();
  const stackLabels = [...new Set(all.map(r => r._stack || r.stack))];
  const th = getTheme();

  // Ecosystem breakdown per stack
  const ecoCol = ["ecosystem_type","primary_language","corpus_source"].find(c => all.some(r => r[c]));
  if (ecoCol) {
    buildPerStackGrid("compare-ecosystem-stacks", stackLabels, (id, lbl) => {
      const rows = all.filter(r => (r._stack || r.stack) === lbl && r[ecoCol]);
      if (!rows.length) return;
      const ecoMap = {};
      rows.forEach(r => {
        const eco = String(r[ecoCol]);
        if (!ecoMap[eco]) ecoMap[eco] = { n: 0, adopted: 0 };
        ecoMap[eco].n++;
        if (r._adopted) ecoMap[eco].adopted++;
      });
      const stats = Object.entries(ecoMap).map(([e, v]) => ({ e, rate: v.adopted / v.n * 100 })).sort((a, b) => a.rate - b.rate);
      mkChart(id, "bar", {
        labels: stats.map(s => s.e),
        datasets: [{ label: "Adoption Rate", data: stats.map(s => s.rate),
          backgroundColor: stackColorForLabel(lbl) + "cc", borderColor: stackColorForLabel(lbl), borderWidth: 1, borderRadius: 3 }],
      }, commonOpts({ indexAxis: "y", plugins: { legend: { display: false } },
        scales: { x: { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } }, y: { ticks: { color: th.text }, grid: { display: false } } } }));
    });
  }

  // Agent market share over time
  const dated = all.filter(r => r._lbl === "agentic" && r._month);
  if (dated.length) {
    const globalCounts = {};
    dated.forEach(r => r._agents.forEach(a => { globalCounts[a] = (globalCounts[a] || 0) + 1; }));
    const topN = 7;
    const topAgents = Object.entries(globalCounts).sort((a, b) => b[1] - a[1]).slice(0, topN).map(([a]) => a);
    const months = [...new Set(dated.map(r => r._month))].sort();
    const msDatasets = topAgents.map((agent, i) => ({
      label: agent,
      data: months.map(m => {
        const g = dated.filter(r => r._month === m);
        if (g.length < 5) return null;
        return g.filter(r => r._agents.includes(agent)).length / g.length * 100;
      }),
      borderColor: PALETTE[i % PALETTE.length],
      backgroundColor: "transparent",
      pointRadius: 3, borderWidth: 2, tension: 0.3, spanGaps: true,
    }));
    mkChart("chart-agent-market-share", "line", { labels: months, datasets: msDatasets },
      commonOpts({ scales: { x: { ticks: { color: th.text, maxTicksLimit: 12 }, grid: { color: th.grid } }, y: { ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } } } }));
  }

  // Tool co-occurrence heatmap
  const agentic = all.filter(r => r._lbl === "agentic");
  if (agentic.length) {
    const globalCounts = {};
    agentic.forEach(r => r._agents.forEach(a => { globalCounts[a] = (globalCounts[a] || 0) + 1; }));
    const topAgents = Object.entries(globalCounts).sort((a, b) => b[1] - a[1]).slice(0, 10).map(([a]) => a);
    // Matrix: pct of repos with row-agent that also have col-agent
    const matrix = {};
    topAgents.forEach(a => { matrix[a] = {}; topAgents.forEach(b => { matrix[a][b] = 0; }); });
    agentic.forEach(r => {
      const present = new Set(r._agents);
      topAgents.filter(a => present.has(a)).forEach(a => {
        topAgents.forEach(b => { if (present.has(b)) matrix[a][b]++; });
      });
    });
    buildHeatmapTable("compare-cooccurrence-table", topAgents, topAgents, (rowA, colB) => {
      const denom = matrix[rowA][rowA];
      if (!denom) return { val: null, label: "—" };
      const val = matrix[rowA][colB] / denom * 100;
      return { val, label: val.toFixed(0) + "%" };
    }, "Agent ↓ / Agent →", "");
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// SIDEBAR BUILDER
// ══════════════════════════════════════════════════════════════════════════════
function buildSidebar() {
  const sidebar = document.getElementById("compare-sidebar");
  if (!sidebar) return;
  const all = getFilteredRows.call ? (() => { const rows = []; stacks.forEach(s => s.rows.forEach(r => rows.push(Object.assign({}, r, { _stack: s.label })))); return rows; })() : [];
  const allStacks = stacks.map(s => s.label);

  let html = "";

  // Stack filter
  html += `<div class="compare-filter-group"><h4>Stacks</h4>`;
  allStacks.forEach(lbl => {
    const checked = !filters.selectedStacks || filters.selectedStacks.has(lbl);
    const col = stackColorForLabel(lbl);
    html += `<label class="compare-filter-row"><input type="checkbox" class="sf-stack" value="${escHtml(lbl)}"${checked ? " checked" : ""}><span class="compare-stack-dot" style="background:${col}"></span>${escHtml(lbl)}</label>`;
  });
  html += "</div>";

  // Date range
  const months = [...new Set(stacks.flatMap(s => s.rows.map(r => getMonth(r)).filter(Boolean)))].sort();
  if (months.length >= 2) {
    html += `<div class="compare-filter-group"><h4>Date range</h4>
      <label class="compare-filter-row">From<select id="sf-date-from" class="field-input sf-date">`;
    months.forEach(m => { html += `<option value="${m}"${m === (filters.dateFrom || months[0]) ? " selected" : ""}>${m}</option>`; });
    html += `</select></label><label class="compare-filter-row">To<select id="sf-date-to" class="field-input sf-date">`;
    months.forEach(m => { html += `<option value="${m}"${m === (filters.dateTo || months[months.length - 1]) ? " selected" : ""}>${m}</option>`; });
    html += `</select></label></div>`;
  }

  // Adoption scope
  html += `<div class="compare-filter-group"><h4>Adoption scope</h4>
    <label class="compare-filter-row"><input type="radio" name="sf-scope" value="all"${filters.scope === "all" ? " checked" : ""}> All adopted (agentic + AI-assisted)</label>
    <label class="compare-filter-row"><input type="radio" name="sf-scope" value="agentic"${filters.scope === "agentic" ? " checked" : ""}> Agentic only</label>
  </div>`;

  // Min repos per country
  html += `<div class="compare-filter-group"><h4>Min repos per country <span id="sf-mincountry-val">${filters.minCountry}</span></h4>
    <input type="range" id="sf-mincountry" min="1" max="50" value="${filters.minCountry}" class="compare-range">
  </div>`;

  // Chart sliders
  html += `<div class="compare-filter-group"><h4>Chart controls</h4>
    <label class="compare-filter-row">Top agents <input type="range" id="sf-top-agents" min="3" max="15" value="${filters.topAgents}" class="compare-range"> <span id="sf-top-agents-val">${filters.topAgents}</span></label>
    <label class="compare-filter-row">Top countries <input type="range" id="sf-top-countries" min="5" max="20" value="${filters.topCountries}" class="compare-range"> <span id="sf-top-countries-val">${filters.topCountries}</span></label>
    <label class="compare-filter-row">Heatmap rows <input type="range" id="sf-heatmap-n" min="5" max="25" value="${filters.heatmapN}" class="compare-range"> <span id="sf-heatmap-n-val">${filters.heatmapN}</span></label>
    <label class="compare-filter-row">Bump rows <input type="range" id="sf-bump-n" min="4" max="20" value="${filters.bumpN}" class="compare-range"> <span id="sf-bump-n-val">${filters.bumpN}</span></label>
    <label class="compare-filter-row">Cumul. countries <input type="range" id="sf-cumul-n" min="3" max="20" value="${filters.cumulN}" class="compare-range"> <span id="sf-cumul-n-val">${filters.cumulN}</span></label>
    <label class="compare-filter-row">MENA min repos <input type="range" id="sf-mena-min" min="1" max="30" value="${filters.menaMin}" class="compare-range"> <span id="sf-mena-min-val">${filters.menaMin}</span></label>
  </div>`;

  // Ecosystem filters (dynamic)
  const ecoAllRows = stacks.flatMap(s => s.rows.map(r => Object.assign({}, r)));
  const detectedCols = ["ecosystem_type","primary_language","corpus_source","size_stratum","topics"].filter(col => ecoAllRows.some(r => r[col]));
  if (detectedCols.length) {
    html += `<div class="compare-filter-group"><h4>Ecosystem filters</h4>`;
    detectedCols.forEach(col => {
      const vals = [...new Set(ecoAllRows.map(r => r[col]).filter(v => v != null && v !== ""))].sort();
      if (vals.length < 2 || vals.length > 50) return;
      const selVals = filters.eco[col] || vals;
      html += `<details class="compare-eco-group"><summary>${col.replace(/_/g, " ")}</summary>`;
      vals.forEach(v => {
        const checked = selVals.includes(String(v));
        html += `<label class="compare-filter-row"><input type="checkbox" class="sf-eco" data-col="${escHtml(col)}" value="${escHtml(String(v))}"${checked ? " checked" : ""}> ${escHtml(String(v))}</label>`;
      });
      html += "</details>";
    });
    html += "</div>";
  }

  sidebar.innerHTML = html;

  // Wire events
  sidebar.querySelectorAll(".sf-stack").forEach(cb => cb.addEventListener("change", () => {
    const checked = [...sidebar.querySelectorAll(".sf-stack:checked")].map(c => c.value);
    filters.selectedStacks = checked.length === allStacks.length ? null : new Set(checked);
    renderActiveTab();
  }));
  sidebar.querySelectorAll(".sf-date").forEach(sel => sel.addEventListener("change", () => {
    const from = document.getElementById("sf-date-from"); const to = document.getElementById("sf-date-to");
    filters.dateFrom = from ? from.value : null;
    filters.dateTo   = to   ? to.value   : null;
    renderActiveTab();
  }));
  sidebar.querySelectorAll("input[name='sf-scope']").forEach(r => r.addEventListener("change", () => {
    filters.scope = r.value; if (r.checked) renderActiveTab();
  }));
  const mcSlider = document.getElementById("sf-mincountry");
  if (mcSlider) mcSlider.addEventListener("input", () => {
    filters.minCountry = parseInt(mcSlider.value); document.getElementById("sf-mincountry-val").textContent = filters.minCountry; renderActiveTab();
  });
  [["sf-top-agents","topAgents"],["sf-top-countries","topCountries"],["sf-heatmap-n","heatmapN"],["sf-bump-n","bumpN"],["sf-cumul-n","cumulN"],["sf-mena-min","menaMin"]].forEach(([id, key]) => {
    const el = document.getElementById(id); if (!el) return;
    el.addEventListener("input", () => { filters[key] = parseInt(el.value); document.getElementById(id + "-val").textContent = filters[key]; renderActiveTab(); });
  });
  sidebar.querySelectorAll(".sf-eco").forEach(cb => cb.addEventListener("change", () => {
    const col = cb.dataset.col;
    const checked = [...sidebar.querySelectorAll(`.sf-eco[data-col="${col}"]:checked`)].map(c => c.value);
    filters.eco[col] = checked; renderActiveTab();
  }));
}

function escHtml(s) { return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }

// ── Active tab tracking ────────────────────────────────────────────────────────
let activeTab = "overview";
function renderActiveTab() {
  if (activeTab === "overview")   renderOverview();
  else if (activeTab === "agents")     renderAgents();
  else if (activeTab === "geography")  renderGeography();
  else if (activeTab === "time")       renderTimeSeries();
  else if (activeTab === "size")       renderSize();
  else if (activeTab === "depth")      renderDepth();
}

function renderAll() {
  document.getElementById("compare-dashboard").hidden = false;
  document.getElementById("compare-empty").hidden = true;
  buildSidebar();
  renderActiveTab();
}

// ══════════════════════════════════════════════════════════════════════════════
// STACK TABLE
// ══════════════════════════════════════════════════════════════════════════════
function buildStackRow(idx) {
  const s = stacks[idx];
  const total = s.rows.length;
  const agentic = s.rows.filter(r => { const lbl = getAdoptionLabel(r); return lbl === "agentic" || lbl === "ai_assisted"; }).length;
  const ci = wilsonCI(agentic, total);
  const tr = document.createElement("tr");
  tr.dataset.idx = idx;
  tr.innerHTML = `
    <td><span class="compare-stack-dot" style="background:${stackColorForLabel(s.label)}"></span>${escHtml(s.filename)}</td>
    <td><input class="field-input compare-label-input" type="text" value="${escHtml(s.label)}" data-idx="${idx}" aria-label="Stack label"></td>
    <td>${total.toLocaleString()}</td>
    <td>${agentic.toLocaleString()}</td>
    <td>${pct(ci.mid)}</td>
    <td><button class="button ghost compare-remove" data-idx="${idx}" aria-label="Remove ${escHtml(s.label)}">✕</button></td>`;
  return tr;
}

function refreshStackTable() {
  const tbody = document.getElementById("compare-stacks-tbody");
  if (!tbody) return;
  tbody.innerHTML = "";
  stacks.forEach((_, i) => tbody.appendChild(buildStackRow(i)));
  document.getElementById("compare-stacks").hidden = stacks.length === 0;
  if (stacks.length) renderAll();
}

// ── File parsing ───────────────────────────────────────────────────────────────
function parseCSV(file) {
  return new Promise((resolve, reject) => {
    Papa.parse(file, { header: true, skipEmptyLines: true, complete: r => resolve(r.data), error: reject });
  });
}
function inferLabel(rows, filename) {
  const counts = {};
  rows.forEach(r => { const s = (r.stack || "").trim(); if (s) counts[s] = (counts[s] || 0) + 1; });
  const best = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
  return best ? best[0] : filename.replace(/\.csv$/i, "");
}

async function addFiles(files) {
  for (const file of files) {
    const rows = await parseCSV(file);
    if (!rows.length) continue;
    const label = inferLabel(rows, file.name);
    stacks.push({ filename: file.name, label, rows });
  }
  refreshStackTable();
}
function removeStack(idx) { stacks.splice(idx, 1); refreshStackTable(); }

// ══════════════════════════════════════════════════════════════════════════════
// EXPORT
// ══════════════════════════════════════════════════════════════════════════════
function captureCharts() {
  const panels = [...document.querySelectorAll(".compare-tab-panel")];
  const wasHidden = panels.map(p => p.hidden);
  panels.forEach(p => { p.hidden = false; });
  Object.values(charts).forEach(c => { try { c.resize(); } catch (_) {} });
  const images = {};
  Object.entries(charts).forEach(([id, ch]) => {
    const el = document.getElementById(id);
    if (el) try { images[id] = el.toDataURL("image/png"); } catch (_) {}
  });
  panels.forEach((p, i) => { p.hidden = wasHidden[i]; });
  return images;
}

function summaryTableHTML() {
  const all = getFilteredRows();
  const labels = [...new Set(all.map(r => r._stack || r.stack))];
  return `<table class="export-table"><thead><tr><th>Stack</th><th>Repos</th><th>Adopted</th><th>Rate</th><th>95% CI Low</th><th>95% CI High</th></tr></thead><tbody>` +
    labels.map(lbl => {
      const rows = all.filter(r => (r._stack || r.stack) === lbl);
      const n = rows.length; const ad = rows.filter(r => { const l = getAdoptionLabel(r); return l === "agentic" || l === "ai_assisted"; }).length;
      const ci = wilsonCI(ad, n);
      return `<tr><td>${lbl}</td><td>${n}</td><td>${ad}</td><td>${pct(ci.mid)}</td><td>${pct(ci.lo)}</td><td>${pct(ci.hi)}</td></tr>`;
    }).join("") + "</tbody></table>";
}

function buildExportHTML(images, forPrint) {
  const now = new Date().toLocaleString();
  const img = (id, alt) => images[id] ? `<img src="${images[id]}" alt="${alt}" style="width:100%;height:auto;display:block;">` : `<p style="color:#888;font-style:italic">No data for ${alt}</p>`;
  const allIds = Object.keys(images);
  let cards = allIds.map(id => `<div style="border:1px solid #ccc;border-radius:6px;padding:1rem;margin-bottom:1.5rem;background:#fff;page-break-inside:avoid"><h3 style="margin:0 0 .5rem;font-size:.95rem">${id.replace(/chart-|compare-|_/g," ")}</h3>${img(id, id)}</div>`).join("");
  return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Cross Stack Comparison</title>
<style>*{box-sizing:border-box}body{font-family:system-ui,sans-serif;margin:0;padding:2rem;background:#f7f4ec;color:#201d16;font-size:14px}h1{color:#1d3557;margin:0}h2{color:#1d3557;border-bottom:1px solid #ccc;padding-bottom:.4rem}.export-table{width:100%;border-collapse:collapse;margin:1rem 0;font-size:.85rem}.export-table th{background:#1d3557;color:#fff;padding:.5rem}.export-table td{padding:.4rem .6rem;border-bottom:1px solid #ccc}.header{display:flex;justify-content:space-between;margin-bottom:2rem;padding-bottom:1rem;border-bottom:2px solid #1d3557}${forPrint ? "@page{size:A3 landscape;margin:15mm}@media print{body{padding:0;background:#fff}}" : ""}</style></head><body>
<div class="header"><div><h1>Cross Stack Comparison</h1><p style="margin:.25rem 0 0;color:#666">Stacks: ${stacks.map(s => s.label).join(", ")}</p></div><div style="color:#666;font-size:.85rem">${now}</div></div>
<h2>Summary</h2>${summaryTableHTML()}
<h2>Charts</h2>${cards}
<div style="margin-top:3rem;padding-top:1rem;border-top:1px solid #ccc;color:#888;font-size:.8rem;display:flex;justify-content:space-between"><span>gitcorpus · Cross Stack Comparison</span><span>${now}</span></div>
</body></html>`;
}

function exportHTML() {
  const images = captureCharts();
  const blob = new Blob([buildExportHTML(images, false)], { type: "text/html;charset=utf-8" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
  a.download = `cross-stack-${new Date().toISOString().slice(0,10)}.html`; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}
function exportPDF() {
  const images = captureCharts();
  const win = window.open("", "_blank");
  if (!win) { alert("Allow pop-ups to export PDF, then try again."); return; }
  win.document.write(buildExportHTML(images, true));
  win.document.close();
  win.addEventListener("load", () => setTimeout(() => { win.focus(); win.print(); }, 400));
}

// ══════════════════════════════════════════════════════════════════════════════
// EVENT WIRING
// ══════════════════════════════════════════════════════════════════════════════
document.querySelectorAll(".compare-tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".compare-tab").forEach(b => { b.classList.remove("active"); b.setAttribute("aria-selected","false"); });
    document.querySelectorAll(".compare-tab-panel").forEach(p => { p.hidden = true; });
    btn.classList.add("active"); btn.setAttribute("aria-selected","true");
    activeTab = btn.dataset.tab;
    document.getElementById("tab-" + activeTab).hidden = false;
    renderActiveTab();
  });
});

const dropzone = document.getElementById("compare-dropzone");
const fileInput = document.getElementById("compare-file-input");
if (dropzone) {
  dropzone.addEventListener("click",   e => { if (e.target.tagName !== "LABEL") fileInput.click(); });
  dropzone.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") fileInput.click(); });
  dropzone.addEventListener("dragover",  e => { e.preventDefault(); dropzone.classList.add("drag-over"); });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag-over"));
  dropzone.addEventListener("drop", e => { e.preventDefault(); dropzone.classList.remove("drag-over"); addFiles([...e.dataTransfer.files].filter(f => f.name.endsWith(".csv"))); });
}
if (fileInput) { fileInput.addEventListener("change", () => { addFiles([...fileInput.files]); fileInput.value = ""; }); }

document.getElementById("compare-stacks-tbody")?.addEventListener("click", e => {
  const btn = e.target.closest(".compare-remove"); if (btn) removeStack(parseInt(btn.dataset.idx, 10));
});
document.getElementById("compare-stacks-tbody")?.addEventListener("change", e => {
  const inp = e.target.closest(".compare-label-input"); if (!inp) return;
  stacks[parseInt(inp.dataset.idx, 10)].label = inp.value.trim() || stacks[parseInt(inp.dataset.idx, 10)].filename;
  renderAll();
});

document.getElementById("btn-export-html")?.addEventListener("click", exportHTML);
document.getElementById("btn-export-pdf")?.addEventListener("click",  exportPDF);
document.getElementById("theme-toggle")?.addEventListener("click",    () => setTimeout(renderActiveTab, 80));

})();
