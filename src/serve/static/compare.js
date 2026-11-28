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
const INCOME_LABEL_TO_CODE = {
  "high income":         "HIC",
  "upper middle income": "UMIC",
  "upper-middle income": "UMIC",
  "lower middle income": "LMIC",
  "lower-middle income": "LMIC",
  "low income":          "LIC",
};
function incomeFromRow(row, country) {
  // Prefer the CSV-provided income_group (authoritative World Bank classification).
  // Fall back to the hardcoded country → tier map only when the column is absent.
  const raw = (row && row.income_group ? String(row.income_group) : "").trim().toLowerCase();
  if (raw && INCOME_LABEL_TO_CODE[raw]) return INCOME_LABEL_TO_CODE[raw];
  return country ? (INCOME_MAP[country] || null) : null;
}
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
// Pricing classification — sourced from the AI Coding Agent Cost Codebook
// (operator-maintained xlsx; keyed by `category_default` column, i.e. the
// path most developers actually pay for, not the cheapest-possible path).
// Categories: C0 = $0 forever via local/open models; C1 = vendor free tier, capped,
// no expiry; C1-P = free for public/OSS repos only; C2 = student/verified-OSS free;
// C3 = metered (pay only API tokens, no sub); C4 = paid subscription required;
// C5 = enterprise/sales-only/discontinued; X = framework/registry, excluded;
// Unknown = unverified. Binary rule (per codebook Key sheet):
// FREE_CATS = {C0, C1, C1-P, C2}; PAID_CATS = {C3, C4, C5}; X/Unknown → ambiguous.
const FREE_CATS = new Set(["C0", "C1", "C1-P", "C2"]);
const PAID_CATS = new Set(["C3", "C4", "C5"]);
const AGENT_CATEGORY = {
  "abacus ai agent": { cat: "C4", conf: "H" },
  "abacus ai agent / coding agent": { cat: "C4", conf: "H" },
  "abacus ai coding agent": { cat: "C4", conf: "H" },
  "abacus.ai cli": { cat: "C4", conf: "H" },
  "aider": { cat: "C3", conf: "M" },
  "alibaba lingma": { cat: "C1", conf: "H" },
  "amazon q cli": { cat: "C1", conf: "H" },
  "amazon q ide": { cat: "C1", conf: "H" },
  "amp": { cat: "C1", conf: "M" },
  "archon": { cat: "C4", conf: "M" },
  "atlassian rovo cli": { cat: "C4", conf: "H" },
  "augment code": { cat: "C4", conf: "H" },
  "azure sre agent": { cat: "X", conf: "H" },
  "baidu comate": { cat: "C1", conf: "M" },
  "bmad-method": { cat: "X", conf: "M" },
  "builder.io fusion": { cat: "C1", conf: "H" },
  "cascade": { cat: "C4", conf: "H" },
  "charlie": { cat: "C4", conf: "L" },
  "claude code": { cat: "C4", conf: "H" },
  "cline": { cat: "C3", conf: "M" },
  "codebuddy": { cat: "C1", conf: "H" },
  "codebuff": { cat: "C1", conf: "H" },
  "codegen": { cat: "C5", conf: "H" },
  "coderabbit": { cat: "C1", conf: "H" },
  "codex": { cat: "C1", conf: "M" },
  "command code": { cat: "C4", conf: "M" },
  "copilot": { cat: "C1", conf: "H" },
  "copilotswe": { cat: "C1", conf: "H" },
  "crush": { cat: "C3", conf: "L" },
  "cubic": { cat: "C1", conf: "H" },
  "cursor": { cat: "C1", conf: "H" },
  "deepagent": { cat: "C4", conf: "H" },
  "deepseek harness": { cat: "C3", conf: "M" },
  "deepsource": { cat: "C1", conf: "H" },
  "devin / devin desktop": { cat: "C4", conf: "H" },
  "docker agent": { cat: "C3", conf: "H" },
  "factory": { cat: "C4", conf: "M" },
  "factory droid": { cat: "C4", conf: "M" },
  "fly": { cat: "C4", conf: "M" },
  "freebuff (codebuff lineage)": { cat: "C1", conf: "H" },
  "gajae-code": { cat: "C4", conf: "M" },
  "gemini": { cat: "C1", conf: "H" },
  "gemini cli": { cat: "C1", conf: "H" },
  "gemini code assist": { cat: "C1", conf: "H" },
  "gitai / graft": { cat: "X", conf: "L" },
  "github agentic workflows": { cat: "C1-P", conf: "M" },
  "gitlab duo agent platform": { cat: "C4", conf: "H" },
  "google antigravity / gemini code assist": { cat: "C1", conf: "H" },
  "goose": { cat: "C3", conf: "M" },
  "greptile": { cat: "C1", conf: "H" },
  "grok build": { cat: "C4", conf: "M" },
  "gru": { cat: "Unknown", conf: "L" },
  "herder": { cat: "C4", conf: "L" },
  "hermes agent": { cat: "C3", conf: "H" },
  "jcode": { cat: "C3", conf: "M" },
  "jules": { cat: "C1", conf: "H" },
  "junie": { cat: "C2", conf: "M" },
  "kilo code": { cat: "C1", conf: "M" },
  "kimi code": { cat: "C4", conf: "M" },
  "kimi code cli": { cat: "C4", conf: "M" },
  "kiro": { cat: "C1", conf: "H" },
  "kody ai": { cat: "C3", conf: "M" },
  "langchain open swe": { cat: "C3", conf: "M" },
  "langgraph": { cat: "X", conf: "M" },
  "letta code": { cat: "C3", conf: "H" },
  "lingma": { cat: "C1", conf: "H" },
  "lovable": { cat: "C1", conf: "H" },
  "manicode": { cat: "C1", conf: "H" },
  "microsoft amplifier": { cat: "C3", conf: "M" },
  "mistral vibe": { cat: "C4", conf: "H" },
  "odysseus": { cat: "X", conf: "L" },
  "oh my pi": { cat: "C3", conf: "M" },
  "oh-my-claudecode": { cat: "C4", conf: "H" },
  "ona": { cat: "C4", conf: "M" },
  "openclaw": { cat: "C3", conf: "H" },
  "opencode": { cat: "C1", conf: "H" },
  "opencodereview": { cat: "C3", conf: "M" },
  "openhands": { cat: "C3", conf: "M" },
  "openspec": { cat: "X", conf: "M" },
  "orca": { cat: "C4", conf: "M" },
  "paperclip": { cat: "C4", conf: "M" },
  "phoenix": { cat: "C4", conf: "M" },
  "phoenix.new (fly.io)": { cat: "C4", conf: "M" },
  "pi": { cat: "C3", conf: "H" },
  "plandex": { cat: "C3", conf: "M" },
  "pr-agent": { cat: "C3", conf: "M" },
  "prime agent": { cat: "C3", conf: "H" },
  "qoder (alibaba)": { cat: "C1", conf: "H" },
  "qodo": { cat: "C4", conf: "H" },
  "qwen coder": { cat: "C3", conf: "H" },
  "replit agent": { cat: "C1", conf: "H" },
  "roo code": { cat: "C3", conf: "M" },
  "roomote": { cat: "C4", conf: "M" },
  "rovo dev": { cat: "C4", conf: "H" },
  "ruler": { cat: "X", conf: "M" },
  "rulesync": { cat: "X", conf: "M" },
  "sentry seer": { cat: "C4", conf: "H" },
  "serena": { cat: "X", conf: "M" },
  "shelley": { cat: "C4", conf: "M" },
  "sketch": { cat: "C4", conf: "M" },
  "snarktank/ralph": { cat: "X", conf: "M" },
  "sourcery": { cat: "C1-P", conf: "H" },
  "speckit": { cat: "X", conf: "M" },
  "t3 code": { cat: "C4", conf: "H" },
  "taskmaster": { cat: "X", conf: "M" },
  "tessl": { cat: "X", conf: "M" },
  "trae": { cat: "C1", conf: "M" },
  "verdent": { cat: "C4", conf: "H" },
  "warp": { cat: "C1", conf: "M" },
  "windsurf": { cat: "C4", conf: "H" },
  "xiaomi mimo code": { cat: "C4", conf: "H" },
  "zoo code": { cat: "C3", conf: "M" },
};
// Sample-size floor: income-group cells with fewer than this many repos
// are rendered as "insufficient data" instead of a rate.
const MIN_INCOME_SAMPLE = 30;

// ── State ──────────────────────────────────────────────────────────────────────
const stacks  = [];   // [{label, filename, rows, enriched}]
const charts  = {};   // keyed by canvas id

// ── Persistence (IndexedDB) ────────────────────────────────────────────────────
const IDB_NAME = "e2e_compare";
const IDB_STORE = "stacks";
const IDB_KEY = "current";
function idbOpen() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(IDB_NAME, 1);
    req.onupgradeneeded = () => { req.result.createObjectStore(IDB_STORE); };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
async function idbPut(value) {
  try {
    const db = await idbOpen();
    await new Promise((res, rej) => {
      const tx = db.transaction(IDB_STORE, "readwrite");
      tx.objectStore(IDB_STORE).put(value, IDB_KEY);
      tx.oncomplete = res; tx.onerror = () => rej(tx.error);
    });
    db.close();
  } catch (e) { console.warn("idb put failed", e); }
}
async function idbGet() {
  try {
    const db = await idbOpen();
    const value = await new Promise((res, rej) => {
      const tx = db.transaction(IDB_STORE, "readonly");
      const r = tx.objectStore(IDB_STORE).get(IDB_KEY);
      r.onsuccess = () => res(r.result);
      r.onerror = () => rej(r.error);
    });
    db.close();
    return value;
  } catch (e) { console.warn("idb get failed", e); return null; }
}
function persistStacks() {
  const payload = stacks.map(s => ({ filename: s.filename, label: s.label, rows: s.rows }));
  idbPut(payload);
}
async function hydrateStacks() {
  const payload = await idbGet();
  if (Array.isArray(payload)) {
    for (const s of payload) {
      if (!s || !Array.isArray(s.rows) || !s.rows.length) continue;
      stacks.push({ filename: s.filename, label: s.label, rows: s.rows, enriched: s.rows.map(enrichRow) });
    }
  }
  // Consume a one-shot "pending" upload (from Open in Cross-Stack)
  const pending = await idbGetKey("pending");
  if (pending && pending.csvText) {
    const rows = await new Promise((res) => {
      Papa.parse(pending.csvText, { header: true, skipEmptyLines: true, complete: r => res(r.data) });
    });
    if (rows && rows.length) {
      const label = pending.label || inferLabel(rows, pending.filename || "pending.csv");
      stacks.push({
        filename: pending.filename || "pending.csv",
        label,
        rows,
        enriched: rows.map(enrichRow),
      });
      await idbDelKey("pending");
      persistStacks();
    }
  }
  return stacks.length > 0;
}

async function idbGetKey(key) {
  try {
    const db = await idbOpen();
    const value = await new Promise((res, rej) => {
      const tx = db.transaction(IDB_STORE, "readonly");
      const r = tx.objectStore(IDB_STORE).get(key);
      r.onsuccess = () => res(r.result);
      r.onerror = () => rej(r.error);
    });
    db.close();
    return value;
  } catch (e) { console.warn("idb getKey failed", e); return null; }
}
async function idbDelKey(key) {
  try {
    const db = await idbOpen();
    await new Promise((res, rej) => {
      const tx = db.transaction(IDB_STORE, "readwrite");
      tx.objectStore(IDB_STORE).delete(key);
      tx.oncomplete = res; tx.onerror = () => rej(tx.error);
    });
    db.close();
  } catch (e) { console.warn("idb delKey failed", e); }
}
let   filters = {
  selectedStacks: null,   // null = all; Set of labels when filtered
  perStackSub:   {},      // { stackLabel: { framework: Set<string>, ecosystem: Set<string> } }
  dateFrom: null,
  dateTo:   null,
  minCountry: 10,
  eco:      {},           // col → [allowed vals]
  adoptionLevels: null,   // null = all; Set of levels when filtered
  primaryAgents:  null,   // null = all; Set of agents when filtered
  archived:  "any",       // "any" | "only" | "exclude"
  active90:  "any",       // "any" | "only" | "exclude"
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
  const lbl = (row.commit_adoption || row.adoption_label || "").trim().toLowerCase();
  if (lbl) return lbl;
  const lvl = (row.adoption_level || "").trim().toLowerCase();
  if (!lvl || lvl === "none") return "none";
  return "agentic";
}
function parseAgents(row) {
  const raw = (row.agents_found || row.agents || "").trim();
  if (!raw) return [];
  return raw.split("|").map(a => a.trim()).filter(Boolean);
}
function parsePipeList(val) {
  if (!val) return [];
  return String(val).split("|").map(s => s.trim()).filter(Boolean);
}
function toInt(v, fb) { const n = parseInt(v, 10); return isNaN(n) ? (fb == null ? null : fb) : n; }
function toFloat(v) { const n = parseFloat(v); return isNaN(n) ? null : n; }
const ADOPTION_DEPTH_ORDER   = ["none","experimental","limited","consistent","pervasive"];
const ADOPTION_DEPTH_COLORS  = { none:"#E0E0E0", experimental:"#FFE082", limited:"#FFB74D", consistent:"#64B5F6", pervasive:"#1565C0" };
const RECENCY_ORDER = ["≤7d","8–30d","31–90d","91–180d","180d+"];
function recencyBucket(days) {
  if (days == null || isNaN(days) || days < 0) return null;
  if (days <= 7)   return "≤7d";
  if (days <= 30)  return "8–30d";
  if (days <= 90)  return "31–90d";
  if (days <= 180) return "91–180d";
  return "180d+";
}
const COUNTRY_ALIASES = {
  "korea, rep.": "South Korea",
  "korea, dem. people's rep.": "North Korea",
  "turkiye": "Turkey",
  "türkiye": "Turkey",
  "viet nam": "Vietnam",
  "russian federation": "Russia",
  "iran, islamic rep.": "Iran",
  "egypt, arab rep.": "Egypt",
  "hong kong sar, china": "Hong Kong",
  "macao sar, china": "Macao",
  "czechia": "Czech Republic",
  "slovak republic": "Slovakia",
  "venezuela, rb": "Venezuela",
  "yemen, rep.": "Yemen",
  "syrian arab republic": "Syria",
  "lao pdr": "Laos",
  "myanmar": "Myanmar",
  "congo, dem. rep.": "DR Congo",
  "congo, rep.": "Congo",
  "cote d'ivoire": "Ivory Coast",
  "côte d'ivoire": "Ivory Coast",
  "gambia, the": "Gambia",
  "bahamas, the": "Bahamas",
  "west bank and gaza": "Palestine",
  "russia": "Russia",
  "south korea": "South Korea",
  "taiwan, province of china": "Taiwan",
  "tw": "Taiwan",
  "va": "Vatican",
  "holy see (vatican city state)": "Vatican",
  "brunei darussalam": "Brunei",
  "kyrgyz republic": "Kyrgyzstan",
  "cabo verde": "Cape Verde",
  "eswatini": "Swaziland",
  "north macedonia": "Macedonia",
  "timor-leste": "East Timor",
  "micronesia, fed. sts.": "Micronesia",
  "st. lucia": "Saint Lucia",
  "st. vincent and the grenadines": "Saint Vincent",
  "st. kitts and nevis": "Saint Kitts and Nevis",
};
function getCountry(row) {
  const raw = (row.country || row.inferred_country || "").trim();
  if (!raw || raw === "not_specified" || raw === "unknown") return null;
  const alias = COUNTRY_ALIASES[raw.toLowerCase()];
  return alias || raw;
}
function getMonth(row) {
  const d = (row.created_at || row.repo_created_at || row.first_signal_at || "").trim().slice(0, 7);
  return d.length === 7 ? d : null;
}
function getAIDensity(row) {
  const v = parseFloat(row.commit_ratio != null ? row.commit_ratio : (row.ai_density != null ? row.ai_density : ""));
  return isNaN(v) ? null : Math.min(1, Math.max(0, v));
}
function classifyPricing(name) {
  const entry = AGENT_CATEGORY[name.trim().toLowerCase()];
  if (!entry) return "ambiguous";
  if (FREE_CATS.has(entry.cat)) return "free";
  if (PAID_CATS.has(entry.cat)) return "paid";
  return "ambiguous";
}

// Unified geo-confidence vocabulary across stacks.
// The Go pipeline emits coarse confidence ("high"/"medium"/"low"/"none");
// the JS/TS pipeline emits resolution-method tags ("name"/"region"/"weak"
// plus the rarer "exact-iso"/"gazetteer-city"/"geocoder"/"unmatched").
// Fold both into: strong / medium / weak / unresolved.
function geoTier(raw) {
  const v = (raw || "").trim().toLowerCase();
  if (!v || v === "none" || v === "unmatched" || v === "unknown") return "unresolved";
  if (v === "high" || v === "name" || v === "exact-iso" || v === "gazetteer-city" || v === "geocoder") return "strong";
  if (v === "medium" || v === "region") return "medium";
  if (v === "low" || v === "weak") return "weak";
  return "weak";
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
  const lvl = (row.adoption_level || "").trim().toLowerCase();
  const aiPresent = String(row.agentic_present || "").trim().toLowerCase() === "true";
  // Headline "adoption" = any AI signal detected (agentic_present / has_signal).
  // The commit-ratio-based `commit_adoption` is retained in `_commit_adoption`
  // as an intensity axis (captured per-level in `_level`).
  const adopted = aiPresent;
  return Object.assign({}, row, {
    _lbl:          adopted ? "agentic" : "none",
    _adopted:      adopted,
    _lbl_orig:     adopted ? "agentic" : "none",
    _adopted_orig: adopted,
    _commit_adoption: lbl,
    _ai_present:   aiPresent,
    _agents_md_marker: String(row.agents_md_marker || "").trim().toLowerCase() === "true",
    _agents_md_only:   String(row.agents_md_only   || "").trim().toLowerCase() === "true",
    _country: country,
    _geo_confidence: (row.geo_confidence || "").trim().toLowerCase(),
    _geo_tier:       geoTier(row.geo_confidence),
    _region:  country ? (REGION_MAP[country] || null)   : null,
    _income:  incomeFromRow(row, country),
    _is_mena: country ? MENA_COUNTRIES.has(country)     : false,
    _month:   getMonth(row),
    _density: getAIDensity(row),
    _agents:  parseAgents(row),
    _level:   ADOPTION_DEPTH_ORDER.includes(lvl) ? lvl : (lbl === "agentic" ? "limited" : "none"),
    _current: parsePipeList(row.current_agents),
    _configured: parsePipeList(row.configured_agents),
    _primary_agent: (row.primary_agent || "").trim(),
    _agent_count:   toInt(row.agent_count, 0),
    _channels_count: toInt(row.channels_count, 0),
    _channels_fired: parsePipeList(row.channels_fired),
    _first_signal_days_ago: toInt(row.first_signal_days_ago, null),
    _history_coverage: toFloat(row.history_coverage),
    _semantics: parsePipeList(row.evidence_semantics),
    _frameworks:  parsePipeList(row.frameworks).flatMap(x => x.split(";").map(s => s.trim()).filter(Boolean)),
    _categories:  parsePipeList(row.categories).flatMap(x => x.split(";").map(s => s.trim()).filter(Boolean)),
    _typescript:  (row.typescript || "").trim().toLowerCase(),
    _language:    ((row.typescript || "").trim().toLowerCase() === "yes" ? "TypeScript"
                 : (row.typescript || "").trim().toLowerCase() === "no"  ? "JavaScript" : ""),
    _monorepo:    (row.monorepo || "").trim(),
    _package_json_count: toInt(row.package_json_count, null),
    _has_agents_md: String(row.has_agents_md || "").toLowerCase() === "true",
    _is_archived:   String(row.is_archived   || "").toLowerCase() === "true",
    _is_active_90d: String(row.is_active_last_90d || "").toLowerCase() === "true",
    _repo_age_days:          toInt(row.repo_age_days, null),
    _age_at_adoption_days:   toInt(row.age_at_adoption_days, null),
    _days_since_push:        toInt(row.days_since_push, null),
    _first_signal_at:        (row.first_signal_at || "").trim(),
    _oldest_commit_at:       (row.oldest_scanned_commit_at || row.repo_created_at || "").trim(),
    _authored_by_agent:      row.authored_commits_by_agent || "",
    _size_kb:                toFloat(row.size_kb),
    _commits:                toFloat(row.commits),
    _ecosystem_type:         (row.ecosystem_type || "").trim().toLowerCase(),
    _primary_language_detected: (row.primary_language_detected || "").trim(),
    _size_stratum:           (row.size_stratum || "").trim().toLowerCase(),
  });
}

// ── Filtered rows ──────────────────────────────────────────────────────────────
function getFilteredRows(onlyStacks) {
  const rows = [];
  // The "Adoption depth" sidebar filter redefines which repos count as adopted
  // for this render pass (so rate-of-adoption charts show the rate of the picked
  // depth across each bucket). It does NOT exclude rows — excluding non-matching
  // rows would make every rate chart show 100% because numerator and denominator
  // shrink together.
  const depthLevels = filters.adoptionLevels && filters.adoptionLevels.size
    ? filters.adoptionLevels : null;
  for (const s of stacks) {
    if (filters.selectedStacks && !filters.selectedStacks.has(s.label)) continue;
    if (onlyStacks && !onlyStacks.includes(s.label)) continue;
    const sub = filters.perStackSub[s.label] || {};
    const fwFilter   = sub.framework  && sub.framework.size  ? sub.framework  : null;
    const catFilter  = sub.category   && sub.category.size   ? sub.category   : null;
    const langFilter = sub.language   && sub.language.size   ? sub.language   : null;
    const ecoFilter  = sub.ecosystem  && sub.ecosystem.size  ? sub.ecosystem  : null;
    if (!s.enriched) s.enriched = s.rows.map(enrichRow);
    for (const er of s.enriched) {
      er._stack = s.label;
      if (filters.dateFrom && er._month && er._month < filters.dateFrom) continue;
      if (filters.dateTo   && er._month && er._month > filters.dateTo)   continue;
      // Per-stack sub-filters (framework/category/language/ecosystem — JS/TS only, real data)
      if (fwFilter) {
        if (!er._frameworks.length) continue;
        if (!er._frameworks.some(f => fwFilter.has(f))) continue;
      }
      if (catFilter) {
        if (!er._categories.length) continue;
        if (!er._categories.some(c => catFilter.has(c))) continue;
      }
      if (langFilter) {
        if (!er._language || !langFilter.has(er._language)) continue;
      }
      if (ecoFilter) {
        if (!er._ecosystem_type || !ecoFilter.has(er._ecosystem_type)) continue;
      }
      // Top-level enrichment filters
      if (filters.primaryAgents && filters.primaryAgents.size &&
          !filters.primaryAgents.has(er._primary_agent)) continue;
      if (filters.archived === "only"    && !er._is_archived) continue;
      if (filters.archived === "exclude" &&  er._is_archived) continue;
      if (filters.active90 === "only"    && !er._is_active_90d) continue;
      if (filters.active90 === "exclude" &&  er._is_active_90d) continue;
      // Generic eco column filters
      let pass = true;
      for (const [col, vals] of Object.entries(filters.eco)) {
        if (!vals || vals.length === 0) continue;
        const v = er[col];
        if (v != null && v !== "" && !vals.includes(String(v))) { pass = false; break; }
      }
      if (!pass) continue;
      // Reset or redefine adoption semantics per the depth filter. These fields
      // are mutated per render pass; always reset so a prior render's state
      // doesn't leak into this one.
      if (depthLevels) {
        er._adopted = depthLevels.has(er._level);
        er._lbl = er._adopted ? "agentic" : "none";
      } else {
        er._adopted = er._adopted_orig;
        er._lbl = er._lbl_orig;
      }
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
  const el = document.getElementById(id);
  if (!el) return null;
  // Clear any prior empty-state note and restore visibility.
  if (el.parentNode) {
    const note = el.parentNode.querySelector(`.compare-empty-note[data-for="${id}"]`);
    if (note) note.remove();
  }
  el.style.display = "";
  const existing = charts[id];
  if (existing && existing.config && existing.config.type === type) {
    existing.data = data;
    existing.options = options;
    existing.update("none");
    return existing;
  }
  if (existing) { existing.destroy(); delete charts[id]; }
  const c = new Chart(el.getContext("2d"), { type, data, options });
  charts[id] = c;
  return c;
}

// ── PNG download per chart ─────────────────────────────────────────────────────
function downloadCanvasPNG(canvas, name) {
  if (!canvas) return;
  try {
    const tmp = document.createElement("canvas");
    tmp.width = canvas.width; tmp.height = canvas.height;
    const ctx = tmp.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, tmp.width, tmp.height);
    ctx.drawImage(canvas, 0, 0);
    const url = tmp.toDataURL("image/png");
    const a = document.createElement("a");
    a.href = url;
    const safe = String(name || canvas.id || "chart").replace(/[^a-zA-Z0-9._-]+/g, "_").slice(0, 80);
    a.download = `${safe}.png`;
    document.body.appendChild(a); a.click(); a.remove();
  } catch (e) { console.warn("PNG download failed", e); }
}
function attachDownloadButtons() {
  document.querySelectorAll("canvas[id]").forEach(canvas => {
    if (canvas.dataset.downloadWired === "1") return;
    const card = canvas.closest(".compare-chart-card");
    if (!card) return;
    // Prefer the heading that directly precedes this canvas's wrap (sub-card h4 case).
    let heading = null;
    const wrap = canvas.closest(".compare-chart-wrap");
    if (wrap) {
      let prev = wrap.previousElementSibling;
      while (prev && !/^H[1-6]$/.test(prev.tagName)) prev = prev.previousElementSibling;
      if (prev && card.contains(prev)) heading = prev;
    }
    if (!heading) heading = card.querySelector("h3, h4");
    if (!heading) return;
    if (heading.querySelector(".compare-dl-btn")) {
      canvas.dataset.downloadWired = "1";
      return;
    }
    const btn = document.createElement("button");
    btn.className = "compare-dl-btn";
    btn.type = "button";
    btn.title = "Download PNG";
    btn.setAttribute("aria-label", "Download PNG");
    btn.innerHTML = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 3v10m0 0l-3.5-3.5M10 13l3.5-3.5M4 15.5v1A1.5 1.5 0 0 0 5.5 18h9a1.5 1.5 0 0 0 1.5-1.5v-1"/></svg>';
    const titleHint = heading.textContent.trim();
    btn.addEventListener("click", ev => {
      ev.preventDefault(); ev.stopPropagation();
      downloadCanvasPNG(canvas, titleHint);
    });
    heading.appendChild(btn);
    canvas.dataset.downloadWired = "1";
  });
}

// ── Per-chart "normalize to %" toggle ──────────────────────────────────────────
const normalizeMode = {};
function isNormalized(id) { return !!normalizeMode[id]; }
function markNormalizable(id) {
  const el = document.getElementById(id);
  if (el) el.dataset.normalizable = "1";
}
function attachNormalizeButtons() {
  document.querySelectorAll('canvas[data-normalizable="1"]').forEach(canvas => {
    const card = canvas.closest(".compare-chart-card");
    if (!card) return;
    let heading = null;
    const wrap = canvas.closest(".compare-chart-wrap");
    if (wrap) {
      let prev = wrap.previousElementSibling;
      while (prev && !/^H[1-6]$/.test(prev.tagName)) prev = prev.previousElementSibling;
      if (prev && card.contains(prev)) heading = prev;
    }
    if (!heading) heading = card.querySelector("h3, h4");
    if (!heading) return;
    const active = isNormalized(canvas.id);
    let btn = heading.querySelector(".compare-norm-btn");
    if (btn) {
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
      btn.title = active ? "Show raw counts" : "Normalize to % of stack";
      return;
    }
    btn = document.createElement("button");
    btn.className = "compare-norm-btn" + (active ? " active" : "");
    btn.type = "button";
    btn.title = active ? "Show raw counts" : "Normalize to % of stack";
    btn.setAttribute("aria-label", "Toggle normalize to percent");
    btn.setAttribute("aria-pressed", active ? "true" : "false");
    btn.textContent = "%";
    btn.addEventListener("click", ev => {
      ev.preventDefault(); ev.stopPropagation();
      normalizeMode[canvas.id] = !normalizeMode[canvas.id];
      renderActiveTab();
    });
    heading.appendChild(btn);
  });
}

// ── Per-chart "info" popover ──────────────────────────────────────────────────
// Describes what the chart shows, the stacks compared, and one or two findings.
// Entry lookup: exact canvas id first; else the longest matching prefix.
const CHART_INFO = {
  // ── Overview ────────────────────────────────────────────────────────────
  "chart-adoption-bars": {
    title: "Adoption Rate by Stack",
    desc: "Share of repos classified as agentic (any named-agent evidence) in each stack. Error bars show Wilson 95% confidence intervals.",
  },
  "chart-adoption-split": {
    title: "Agentic / Non-agentic Split",
    desc: "For each stack, how the repos split between agentic and not. Useful to eyeball the raw composition — not just the rate.",
  },
  "chart-adoption-depth": {
    title: "Adoption Depth",
    desc: "Breakdown of agentic repos by AI-authored commit ratio: Limited (<5%), Consistent (5–20%), Pervasive (≥20%).",
  },
  "chart-channel-breadth": {
    title: "Detection Signal Breadth",
    desc: "For each stack, how many of the channels (file, author, commit_trailer, pr_metadata, branch, label, bot, issue) fired at least once.",
  },
  // ── Agents ─────────────────────────────────────────────────────────────
  "compare-agent-lifecycle-stacks": {
    title: "Agent Lifecycle Funnel",
    desc: "How repos in this stack move through the AI pipeline: configured → first signal → agentic → deep adoption. Big drop-offs point to silent adopters or dormant configs.",
  },
  "chart-agent-concentration": {
    title: "Multi-Agent Concentration",
    desc: "Share of agentic repos using exactly 1, 2, 3+ distinct agents. Flat distribution = stacks blending tools; spike at 1 = single-agent loyalty.",
  },
  "compare-primary-agent-stacks": {
    title: "Primary Agent Market Share",
    desc: "The single top-scoring agent per repo, aggregated across the stack. One slice per agent family.",
  },
  "compare-agents-top-stacks": {
    title: "Top Agents",
    desc: "Top-N agent families by repo count in this stack. Multiple agents per repo can contribute.",
  },
  "compare-tool-loyalty-stacks": {
    title: "Tool Loyalty",
    desc: "Among agentic repos in this stack, how many use exactly one agent (loyal) vs mix multiple (polyglot).",
  },
  "chart-agent-diversity": {
    title: "Agent Diversity",
    desc: "Shannon-style diversity of agents across stacks. Higher = healthier ecosystem; lower = winner-take-all.",
  },
  "chart-commit-depth": {
    title: "AI Commit Density",
    desc: "Histogram of AI-authored commit ratio (0–100%) per stack. The right tail is where AI is doing real work.",
  },
  "compare-commit-density-hist-stacks": {
    title: "AI Density Distribution",
    desc: "Per-stack histogram of the AI-authored commit ratio. Mass near 0% = config-only; mass near 1 = saturated.",
  },
  "compare-density-by-agent-stacks": {
    title: "AI Density by Agent",
    desc: "For this stack, how deep each agent gets into commits. Compares agents by median/quartile AI ratio.",
  },
  // ── Geography ──────────────────────────────────────────────────────────
  "compare-country-resolution-stacks": {
    title: "Country Resolution per Stack",
    desc: "For the selected stack, how many repos had their owner location parsed and at what confidence vs. how many were unresolved. Use it as a data-quality lens before interpreting other geo charts. Vocabulary differs per stack (Go: high/medium/low · JS/TS: name/region/weak).",
  },
  "chart-world-regions": {
    title: "Adoption by World Region",
    desc: "Rate of agentic repos per world region, aggregated across all stacks.",
  },
  "compare-countries-stacks": {
    title: "Top Countries",
    desc: "Top countries by agentic-repo count in this stack. Owner-country is captured at search time and carried through detection.",
  },
  "chart-income-group": {
    title: "Adoption × Income Group",
    desc: "Rate of agentic repos bucketed by World-Bank income group of the owner's country.",
  },
  "compare-pricing-income-stacks": {
    title: "Pricing × Income",
    desc: "Within this stack, adoption rate per income group plus the share of agentic repos that use any free-path tool vs any paid-path tool. Classification comes from the AI Coding Agent Cost Codebook (default-path column): free = C0/C1/C1-P/C2 (OSS, vendor free tier, OSS-only free, student free); paid = C3/C4/C5 (metered API tokens, paid subscription, enterprise-only). Frameworks (X) and unverified tools are excluded from the free/paid lines.",
  },
  "compare-mena-countries-stacks": {
    title: "MENA Countries — Detail",
    desc: "Country-level adoption rate inside MENA for this stack.",
  },
  "compare-country-heatmap": {
    title: "Country × Repo-Creation Month — Sparklines",
    desc: "One sparkline per top country for this stack: 3-month rolling adoption rate over time. Header shows the latest rolling rate; footer shows total repos and overall adoption rate.",
  },
  "compare-country-bump-stacks": {
    title: "Country Adoption Trend — compare two picks",
    desc: "Pick a Stack · Country in each slot to compare their 3-month rolling adoption trends side by side. Dropdown lists top countries per stack.",
  },
  "chart-country-cumulative": {
    title: "Cumulative Agentic Repos per Country",
    desc: "Running total of agentic repos by country, across all stacks.",
  },
  "compare-country-agent-matrix": {
    title: "Country × Primary Agent",
    desc: "For each top country in this stack, the primary-agent mix as a 100%-stacked bar. Countries sorted by leader share (most dominated → most fragmented). The grey 'Other' slice absorbs agents outside the top 8.",
  },
  // ── Time Series ────────────────────────────────────────────────────────
  "chart-time-series": {
    title: "Adoption Rate Over Time",
    desc: "Monthly adoption rate per stack — the share of repos first observed in each month that are agentic. Months with <5 repos are dropped.",
  },
  "chart-agent-emergence": {
    title: "Agent Emergence Timeline",
    desc: "Cumulative repos per agent family over time. Shows which agent built its footprint first and who's compounding fastest.",
  },
  "compare-recency-depth-stacks": {
    title: "Recency × Adoption Depth per Stack",
    desc: "Repos bucketed by how long ago their first AI signal fired, split by adoption depth. Each slot shows one stack so you can compare whether deep adoption takes time or shows up fast. Toggle % to normalise each recency bucket to 100%.",
  },
  "compare-stacked-area-stacks": {
    title: "Monthly New Repos by Adoption Label",
    desc: "For this stack, how many new repos each month, coloured by adoption depth. Toggle % to see the share of depth within each month.",
  },
  "chart-adoption-timing": {
    title: "Signal Recency per Stack",
    desc: "Among agentic repos in each stack, how recently the first AI signal fired. Short-bucket mass = active adoption; long-bucket mass = older adoption stabilising.",
  },
  "compare-days-hist-stacks": {
    title: "Days Since First AI Signal",
    desc: "Smoothed density of days-since-first-signal for agentic repos in this stack (clipped at 365d). Peaks mark adoption waves.",
  },
  "chart-monthly-new-adopters": {
    title: "Monthly New Adopters",
    desc: "New agentic repos per month, stacked by stack. Toggle % to see each stack's share of the monthly flow.",
  },
  "chart-cumulative-adopters": {
    title: "Cumulative Agentic Repos per Stack",
    desc: "Running total of agentic repos by stack. Steeper curve = faster accumulation. Toggle % to compare growth shape (each stack normalised to its own final).",
  },
  "chart-retrofit-greenfield": {
    title: "Greenfield vs Retrofit",
    desc: "Gap from the repo's oldest known commit (or creation date when scanned-commit history is unavailable) to the first AI signal. Short gap = AI landed near the project's birth (greenfield); long gap = retrofit onto an older repo.",
  },
  "chart-adoption-momentum": {
    title: "Adoption Momentum",
    desc: "For each stack, the share of agentic repos whose first AI signal fell inside each lookback window. Steeper rise = older, more mature adoption; flatter = recent push.",
  },
  "chart-authored-depth": {
    title: "AI-Authored Commit Depth per Stack",
    desc: "Among agentic repos in each stack, 100%-stacked share by AI-commit depth tier. Config-only = present but zero AI commits; Full = ≥80% AI-authored.",
  },
  "chart-top-countries-timeline": {
    title: "Top Adopted Countries Over Time",
    desc: "Running total of agentic repos per country, top-N by final count. Toggle % to compare growth shape across countries of different sizes.",
  },
  "chart-top-countries-monthly": {
    title: "Top Countries — Monthly New Agentic Repos",
    desc: "Monthly inflow of agentic repos per country. Peaks mark acceleration events. Toggle % to see each country's share of the monthly top-N flow.",
  },
  // ── Size ───────────────────────────────────────────────────────────────
  "chart-size-tertile": {
    title: "Adoption Rate by Stars Tertile",
    desc: "Repos split into Small / Medium / Large by star count within each stack. Rising bars left-to-right = larger repos adopt more.",
  },
  "chart-size-commits-tertile": {
    title: "Adoption Rate by Commits Tertile",
    desc: "Repos split into Small / Medium / Large by total commits within each stack.",
  },
  "chart-size-stars": {
    title: "Median Stars by Adoption Category",
    desc: "Median star count for No AI vs Agentic repos in each stack.",
  },
  "chart-size-commits": {
    title: "Median Commits by Adoption Category",
    desc: "Median total commits for No AI vs Agentic repos in each stack.",
  },
  // ── Depth & Ecosystems ─────────────────────────────────────────────────
  "chart-semantics-coverage": {
    title: "Evidence Semantics Coverage",
    desc: "Which categories of evidence fired per stack: configuration, activity, authorship, historical lineage, generated code.",
  },
  "chart-history-coverage": {
    title: "History Scan Quality",
    desc: "Repos binned by history_coverage — the fraction of the repo that was in scan scope. Higher = more trustworthy signal.",
  },
  "compare-ecosystem-stacks": {
    title: "Adoption Rate by Framework",
    desc: "Framework hints (pipe-delimited) with ≥5 repos per entry. A repo can appear under multiple frameworks.",
  },
  "chart-agent-market-share": {
    title: "Agent Market Share Over Time",
    desc: "For agentic repos in each month, the share that uses each top-7 agent. Months with <5 agentic repos are dropped.",
  },
  "compare-cooccurrence-table": {
    title: "Tool Co-occurrence Heatmap",
    desc: "% of repos with the row agent that also have the column agent. Diagonal is 100% by definition.",
  },
  "chart-jsts-ecosystem": {
    title: "Adoption Rate by Package Manager",
    desc: "JS/TS repos grouped by lockfile detected during seed: npm, pnpm, yarn, bun, deno, vanilla (no manifest), npm_no_lock (manifest without lockfile).",
  },
  "chart-jsts-language": {
    title: "Adoption Rate by Primary Language",
    desc: "JS/TS repos split by the primary language detected from seed metadata (TypeScript vs JavaScript).",
  },
  "chart-jsts-size-stratum": {
    title: "Adoption Rate by Seed Size Stratum",
    desc: "Repos were split into small/medium/large strata by the seed phase using star + commit thresholds.",
  },
  "compare-jsts-lang-eco-heatmap": {
    title: "Language × Package Manager Heatmap",
    desc: "Adoption rate (%) per {language, ecosystem} cell. Cells with n<30 are dashed out.",
  },
};

function infoEntryFor(canvasId) {
  if (CHART_INFO[canvasId]) return CHART_INFO[canvasId];
  // Prefix match for slot ids like "compare-stacked-area-stacks-a"
  let best = null;
  Object.keys(CHART_INFO).forEach(k => {
    if (canvasId.startsWith(k + "-") && (!best || k.length > best.length)) best = k;
  });
  return best ? CHART_INFO[best] : null;
}

function slotLabelForBodyId(bodyId) {
  // bodyId like "compare-foo-a" — walk up to find the compare-slot card, then its <select>.
  const el = document.getElementById(bodyId);
  if (!el) return null;
  const card = el.closest(".compare-slot");
  if (!card) return null;
  const sel = card.querySelector(".compare-slot-select");
  return sel ? sel.value : null;
}

function computeChartFindings(canvasId) {
  const c = charts[canvasId];
  if (!c) return [];
  const ds = c.data && c.data.datasets || [];
  const labels = (c.data && c.data.labels) || [];
  if (!ds.length) return [];
  const findings = [];
  const fmt = v => Math.abs(v) >= 1 ? v.toLocaleString(undefined, { maximumFractionDigits: 1 }) : v.toFixed(2);

  if (ds.length === 1) {
    const d = ds[0];
    const vals = (d._raw || d.data).map(v => (v == null || isNaN(v)) ? null : +v);
    const nonNull = vals.map((v, i) => [v, i]).filter(([v]) => v != null);
    if (nonNull.length) {
      const maxP = nonNull.reduce((a, b) => b[0] > a[0] ? b : a);
      const total = nonNull.reduce((s, [v]) => s + v, 0);
      findings.push(`Peak: ${fmt(maxP[0])} at ${labels[maxP[1]] || "—"}`);
      if (total && total !== maxP[0]) findings.push(`Total across bins: ${fmt(total)}`);
    }
  } else {
    // Multi-series: show leader + runner-up by total
    const totals = ds.map(d => {
      const vals = (d._raw || d.data).map(v => (v == null || isNaN(v)) ? 0 : +v);
      return vals.reduce((s, v) => s + v, 0);
    });
    const ranked = ds.map((d, i) => ({ label: d.label || `Series ${i + 1}`, total: totals[i] }))
      .sort((a, b) => b.total - a.total);
    if (ranked[0]) findings.push(`Leader: ${ranked[0].label} (${fmt(ranked[0].total)})`);
    if (ranked[1]) findings.push(`Runner-up: ${ranked[1].label} (${fmt(ranked[1].total)})`);
  }
  return findings;
}

function stacksForChart(canvasId) {
  // Slot chart? Return the slot's selected stack.
  const slot = slotLabelForBodyId(canvasId);
  if (slot) return [slot];
  // Otherwise derive from dataset labels (combined chart).
  const c = charts[canvasId];
  if (!c) return [];
  const labels = (c.data && c.data.datasets || []).map(d => d.label).filter(Boolean);
  return [...new Set(labels)];
}

let _activeInfoPop = null;
function closeInfoPop() {
  if (_activeInfoPop) {
    _activeInfoPop.remove();
    _activeInfoPop = null;
    document.removeEventListener("mousedown", _infoDocClick, true);
    document.removeEventListener("keydown", _infoDocKey, true);
  }
}
function _infoDocClick(ev) {
  if (!_activeInfoPop) return;
  if (_activeInfoPop.contains(ev.target)) return;
  if (ev.target.classList && ev.target.classList.contains("compare-info-btn")) return;
  closeInfoPop();
}
function _infoDocKey(ev) { if (ev.key === "Escape") closeInfoPop(); }

function openInfoPop(canvasId, anchorBtn) {
  closeInfoPop();
  const entry = infoEntryFor(canvasId);
  if (!entry) return;
  const stacks = stacksForChart(canvasId);
  const findings = computeChartFindings(canvasId);
  const pop = document.createElement("div");
  pop.className = "compare-info-pop";
  pop.setAttribute("role", "dialog");
  const stackHTML = stacks.length
    ? `<p>${stacks.map(s => `<span class="compare-info-stack">${escapeHtml(s)}</span>`).join("")}</p>`
    : "";
  const findingsHTML = findings.length
    ? `<ul>${findings.map(f => `<li>${escapeHtml(f)}</li>`).join("")}</ul>`
    : "";
  pop.innerHTML = `
    <div class="compare-info-pop-header">
      <h5>${escapeHtml(entry.title)}</h5>
      <button class="compare-info-pop-close" type="button" aria-label="Close">&times;</button>
    </div>
    <p>${escapeHtml(entry.desc)}</p>
    ${stackHTML}
    ${findingsHTML}
    <div class="compare-info-pop-hint">Tip: use the <strong>%</strong> toggle to flip between raw counts and shares.</div>
  `;
  document.body.appendChild(pop);
  // Position: below the button, right-aligned to it.
  const r = anchorBtn.getBoundingClientRect();
  const scrollY = window.scrollY || document.documentElement.scrollTop;
  const scrollX = window.scrollX || document.documentElement.scrollLeft;
  const popW = pop.offsetWidth;
  let left = r.right + scrollX - popW;
  if (left < scrollX + 8) left = scrollX + 8;
  const maxLeft = scrollX + document.documentElement.clientWidth - popW - 8;
  if (left > maxLeft) left = maxLeft;
  let top = r.bottom + scrollY + 6;
  // Flip above if off-screen vertically.
  const viewportBottom = scrollY + window.innerHeight;
  if (top + pop.offsetHeight > viewportBottom - 8) {
    top = r.top + scrollY - pop.offsetHeight - 6;
  }
  pop.style.left = left + "px";
  pop.style.top = top + "px";
  _activeInfoPop = pop;
  pop.querySelector(".compare-info-pop-close").addEventListener("click", closeInfoPop);
  setTimeout(() => {
    document.addEventListener("mousedown", _infoDocClick, true);
    document.addEventListener("keydown", _infoDocKey, true);
  }, 0);
}

function escapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function attachInfoButtons() {
  document.querySelectorAll("canvas[id], .compare-slot-html[id], #compare-cooccurrence-table, #compare-country-heatmap, #compare-country-agent-matrix").forEach(el => {
    const canvasId = el.id;
    if (!canvasId) return;
    if (!infoEntryFor(canvasId)) return;
    const card = el.closest(".compare-chart-card");
    if (!card) return;
    let heading = null;
    const wrap = el.closest(".compare-chart-wrap");
    if (wrap) {
      let prev = wrap.previousElementSibling;
      while (prev && !/^H[1-6]$/.test(prev.tagName)) prev = prev.previousElementSibling;
      if (prev && card.contains(prev)) heading = prev;
    }
    if (!heading) heading = card.querySelector("h3, h4");
    if (!heading) return;
    if (heading.querySelector(".compare-info-btn")) return;
    const btn = document.createElement("button");
    btn.className = "compare-info-btn";
    btn.type = "button";
    btn.title = "What is this chart?";
    btn.setAttribute("aria-label", "Show chart info");
    btn.textContent = "i";
    btn.dataset.canvasId = canvasId;
    btn.addEventListener("click", ev => {
      ev.preventDefault(); ev.stopPropagation();
      if (_activeInfoPop && _activeInfoPop.dataset.for === canvasId) { closeInfoPop(); return; }
      openInfoPop(canvasId, btn);
      if (_activeInfoPop) _activeInfoPop.dataset.for = canvasId;
    });
    heading.appendChild(btn);
  });
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
const slotState = {};  // keyed by containerId → { a: label, b: label }
function buildCompareSlots(containerId, stackLabels, buildFn, opts) {
  opts = opts || {};
  const useHtml = opts.html === true;
  const tall = opts.tall === true;
  const container = document.getElementById(containerId);
  if (!container) return;
  destroyPrefix(containerId + "-");
  container.innerHTML = "";
  if (!stackLabels.length) return;
  const state = slotState[containerId] || {};
  if (!stackLabels.includes(state.a)) state.a = stackLabels[0];
  if (!stackLabels.includes(state.b)) state.b = stackLabels.length >= 2 ? stackLabels[1] : stackLabels[0];
  slotState[containerId] = state;
  const slots = document.createElement("div");
  slots.className = "compare-slots";
  container.appendChild(slots);
  const slotKeys = stackLabels.length >= 2 ? ["a", "b"] : ["a"];
  slotKeys.forEach(key => {
    const card = document.createElement("div");
    card.className = "compare-chart-card compare-slot" + (tall ? " compare-slot-tall" : "");
    const header = document.createElement("div");
    header.className = "compare-slot-header";
    const h4 = document.createElement("h4"); h4.textContent = opts.label || "Stack";
    const sel = document.createElement("select");
    sel.className = "compare-slot-select";
    stackLabels.forEach(l => {
      const o = document.createElement("option");
      o.value = l; o.textContent = l;
      if (l === state[key]) o.selected = true;
      sel.appendChild(o);
    });
    header.appendChild(h4); header.appendChild(sel);
    card.appendChild(header);
    const bodyId = containerId + "-" + key;
    let body;
    if (useHtml) {
      body = document.createElement("div");
      body.className = "compare-slot-html";
      body.id = bodyId;
    } else {
      body = document.createElement("div");
      body.className = "compare-chart-wrap";
      const canvas = document.createElement("canvas");
      canvas.id = bodyId;
      body.appendChild(canvas);
    }
    card.appendChild(body);
    slots.appendChild(card);
    const render = () => {
      destroyChart(bodyId);
      if (useHtml) document.getElementById(bodyId).innerHTML = "";
      buildFn(bodyId, state[key]);
    };
    sel.addEventListener("change", () => { state[key] = sel.value; render(); });
    render();
  });
}

function buildPerStackHtmlGrid(containerId, stackLabels, buildFn) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = "";
  if (!stackLabels.length) return;
  const grid = document.createElement("div");
  grid.className = "compare-per-stack-grid";
  container.appendChild(grid);
  stackLabels.forEach(label => {
    const card = document.createElement("div");
    card.className = "compare-chart-card";
    const h4 = document.createElement("h4"); h4.textContent = label; card.appendChild(h4);
    const inner = document.createElement("div");
    inner.id = containerId + "-" + label.replace(/[^a-zA-Z0-9]/g, "_");
    card.appendChild(inner);
    grid.appendChild(card);
    buildFn(inner.id, label);
  });
}

function buildPerStackGrid(containerId, stackLabels, buildFn) {
  const container = document.getElementById(containerId);
  if (!container) return;
  destroyPrefix(containerId + "-");
  container.innerHTML = "";
  if (!stackLabels.length) return;
  const grid = document.createElement("div");
  grid.className = "compare-per-stack-grid";
  container.appendChild(grid);
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
  // `adopted` = headline AI-signal rate (agentic_present / has_signal, ~70%)
  // `commitAg` = narrower commit-ratio-based rate (commit_adoption, ~43%)
  const summary = stackLabels.map(lbl => {
    const rows = all.filter(r => (r._stack || r.stack) === lbl);
    const n    = rows.length;
    const commitAg   = rows.filter(r => r._commit_adoption === "agentic" || r._commit_adoption === "ai_assisted").length;
    const pervasive  = rows.filter(r => r._level === "pervasive").length;
    const consistent = rows.filter(r => r._level === "consistent").length;
    const limited    = rows.filter(r => r._level === "limited").length;
    const adopted = rows.filter(r => r._adopted).length;
    const ci   = wilsonCI(adopted, n);
    return { lbl, n, ag: commitAg, pervasive, consistent, limited, adopted, ci };
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

  // Stacked split bar — adoption depth mix per stack
  mkChart("chart-adoption-split", "bar", {
    labels: summary.map(s => s.lbl),
    datasets: [
      { label: "Pervasive",  data: summary.map(s => s.n > 0 ? s.pervasive  / s.n * 100 : 0), backgroundColor: ADOPTION_DEPTH_COLORS.pervasive  + "cc", borderRadius: 2 },
      { label: "Consistent", data: summary.map(s => s.n > 0 ? s.consistent / s.n * 100 : 0), backgroundColor: ADOPTION_DEPTH_COLORS.consistent + "cc", borderRadius: 2 },
      { label: "Limited",    data: summary.map(s => s.n > 0 ? s.limited    / s.n * 100 : 0), backgroundColor: ADOPTION_DEPTH_COLORS.limited    + "cc", borderRadius: 2 },
      { label: "No AI",      data: summary.map(s => s.n > 0 ? (s.n - s.adopted) / s.n * 100 : 0), backgroundColor: ADOPTION_DEPTH_COLORS.none       + "cc", borderRadius: 2 },
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
      <td>${s.pervasive.toLocaleString()}</td>
      <td><strong>${pct(s.ci.mid)}</strong></td>
      <td>${pct(s.ci.lo)}</td>
      <td>${pct(s.ci.hi)}</td>
    </tr>`).join("");
  }

  renderKpiGrid(all);
  renderAdoptionDepthChart(all, stackLabels);
  renderChannelBreadthChart(all);
  renderAgentsMdExclusionChart(all, stackLabels);
}

function renderAgentsMdExclusionChart(all, stackLabels) {
  const th = getTheme();
  const canvas = document.getElementById("chart-agents-md-exclusion");
  const tableHost = document.getElementById("chart-agents-md-exclusion-table");
  if (!canvas) return;
  // Only render if at least one stack has the agents_md_only column populated.
  const haveSignal = all.some(r => r._agents_md_only || r._agents_md_marker);
  if (!haveSignal) {
    destroyChart("chart-agents-md-exclusion");
    if (tableHost) tableHost.innerHTML = `<p class="muted" style="margin:0">Load a CSV that includes the <code>agents_md_only</code> column to see this chart.</p>`;
    return;
  }
  const rows = stackLabels.map(lbl => {
    const sub = all.filter(r => (r._stack || r.stack) === lbl);
    const n     = sub.length;
    const named = sub.filter(r => r._ai_present).length;
    const onlyMd = sub.filter(r => r._agents_md_only).length;
    return {
      lbl, n, named, onlyMd,
      namedPct:    n ? named  / n * 100 : 0,
      onlyMdPct:   n ? onlyMd / n * 100 : 0,
      includedPct: n ? (named + onlyMd) / n * 100 : 0,
    };
  });
  mkChart("chart-agents-md-exclusion", "bar", {
    labels: rows.map(r => r.lbl),
    datasets: [
      {
        label: "Named-agent rate (current agentic_present)",
        data: rows.map(r => r.namedPct),
        backgroundColor: rows.map(r => stackColorForLabel(r.lbl) + "cc"),
        borderColor:     rows.map(r => stackColorForLabel(r.lbl)),
        borderWidth: 1,
        borderRadius: 2,
      },
      {
        label: "AGENTS.md-only addition (excluded)",
        data: rows.map(r => r.onlyMdPct),
        backgroundColor: rows.map(r => stackColorForLabel(r.lbl) + "55"),
        borderColor:     rows.map(r => stackColorForLabel(r.lbl)),
        borderWidth: 1,
        borderRadius: 2,
      },
    ],
  }, commonOpts({
    indexAxis: "y",
    plugins: {
      legend: { position: "bottom", labels: { color: th.text } },
      tooltip: {
        callbacks: {
          label: ctx => {
            const r = rows[ctx.dataIndex];
            if (ctx.datasetIndex === 0) return `Named agents: ${r.named.toLocaleString()} / ${r.n.toLocaleString()}  (${pct(r.namedPct/100)})`;
            return `AGENTS.md-only: +${r.onlyMd.toLocaleString()}  (${pct(r.onlyMdPct/100)}) → included total ${pct(r.includedPct/100)}`;
          }
        }
      }
    },
    scales: {
      x: { stacked: true, min: 0, max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } },
      y: { stacked: true, ticks: { color: th.text }, grid: { color: th.grid } },
    },
  }));
  if (tableHost) {
    tableHost.innerHTML = `
      <table class="data-table" style="width:100%;font-size:.85rem">
        <thead><tr>
          <th>Stack</th><th>Repos</th>
          <th>Named-agent (current)</th>
          <th>AGENTS.md-only excluded</th>
          <th>Included total</th>
        </tr></thead>
        <tbody>
          ${rows.map(r => `<tr>
            <td><span class="compare-stack-dot" style="background:${stackColorForLabel(r.lbl)}"></span>${r.lbl}</td>
            <td>${r.n.toLocaleString()}</td>
            <td>${r.named.toLocaleString()} (${pct(r.namedPct/100)})</td>
            <td>+${r.onlyMd.toLocaleString()} (${pct(r.onlyMdPct/100)})</td>
            <td><strong>${(r.named + r.onlyMd).toLocaleString()} (${pct(r.includedPct/100)})</strong></td>
          </tr>`).join("")}
        </tbody>
      </table>`;
  }
}

// ── Overview extras ───────────────────────────────────────────────────────────
function renderKpiGrid(all) {
  const host = document.getElementById("compare-kpi-grid");
  if (!host) return;
  const n = all.length;
  if (!n) { host.innerHTML = ""; return; }
  const aiPresent = all.filter(r => r._ai_present).length;
  const commitAgentic = all.filter(r => r._commit_adoption === "agentic" || r._commit_adoption === "ai_assisted").length;
  const multiAgent = all.filter(r => r._agent_count > 1).length;
  const authored = all.filter(r => toFloat(r.commit_ratio) > 0).length;
  const withCountry = all.filter(r => r._country).length;
  const avgChannels = all.reduce((s, r) => s + (r._channels_count || 0), 0) / n;
  const distinctPrimary = new Set(all.filter(r => r._primary_agent).map(r => r._primary_agent)).size;
  const depthActive = !!(filters.adoptionLevels && filters.adoptionLevels.size);
  const depthFlag = depthActive
    ? ` <span class="muted" title="This KPI uses the commit_adoption column, which is not re-labeled by the sidebar Adoption-depth filter. The AI-signal present KPI above is.">⚠ ignores depth filter</span>`
    : "";
  const kpis = [
    { label: "Repos",             value: n.toLocaleString(),              sub: "in dataset" },
    { label: "AI-signal present", value: pct(aiPresent / n),              sub: `${aiPresent.toLocaleString()} repos (agentic_present)` },
    { label: "Commit-level agentic", value: pct(commitAgentic / n),       sub: `${commitAgentic.toLocaleString()} repos (commit_adoption)${depthFlag}` },
    { label: "Multi-agent",       value: pct(multiAgent / n),             sub: `${multiAgent.toLocaleString()} repos ≥2 agents` },
    { label: "Authored commits",  value: pct(authored / n),               sub: `${authored.toLocaleString()} repos with commit_ratio>0` },
    { label: "Country-tagged",    value: pct(withCountry / n),            sub: `${withCountry.toLocaleString()} repos` },
    { label: "Avg channels fired", value: avgChannels.toFixed(1),         sub: "out of 8" },
    { label: "Agent families",    value: String(distinctPrimary),         sub: "distinct primaries" },
  ];
  host.innerHTML = kpis.map(k => `
    <div class="compare-kpi">
      <p class="compare-kpi-label">${k.label}</p>
      <div class="compare-kpi-value">${k.value}</div>
      <div class="compare-kpi-sub">${k.sub}</div>
    </div>`).join("");
}

function renderAdoptionDepthChart(all, stackLabels) {
  const th = getTheme();
  const have = all.some(r => ADOPTION_DEPTH_ORDER.includes(r._level));
  if (!have) { destroyChart("chart-adoption-depth"); return; }
  const datasets = ADOPTION_DEPTH_ORDER.map(lvl => ({
    label: lvl,
    data: stackLabels.map(lbl => {
      const rows = all.filter(r => (r._stack || r.stack) === lbl);
      return rows.length ? rows.filter(r => r._level === lvl).length / rows.length * 100 : 0;
    }),
    backgroundColor: ADOPTION_DEPTH_COLORS[lvl] + "cc",
    borderRadius: 2,
  }));
  mkChart("chart-adoption-depth", "bar", { labels: stackLabels, datasets }, commonOpts({
    scales: {
      x: { stacked: true, ticks: { color: th.text }, grid: { color: th.grid } },
      y: { stacked: true, max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } },
    },
  }));
}

const CHANNEL_ORDER = ["file","author","branch","bot","commit_trailer","pr_metadata","issue","label"];
function renderChannelBreadthChart(all) {
  const th = getTheme();
  const id = "chart-channel-breadth";
  if (!all.length) { destroyChart(id); return; }
  const norm = isNormalized(id);
  const stackLabels = [...new Set(all.map(r => r._stack || r.stack))];
  const useFired = all.some(r => r._channels_fired && r._channels_fired.length);
  const stackRaw = {}, stackTotal = {};
  stackLabels.forEach(lbl => {
    const srows = all.filter(r => (r._stack || r.stack) === lbl);
    stackTotal[lbl] = srows.length || 1;
    stackRaw[lbl] = CHANNEL_ORDER.map(ch => {
      if (useFired) return srows.filter(r => r._channels_fired.includes(ch)).length;
      const key = "has_" + ch + "_evidence";
      return srows.filter(r => String(r[key] || "").toLowerCase() === "true").length;
    });
  });
  const datasets = stackLabels.map(lbl => ({
    label: lbl,
    data: norm ? stackRaw[lbl].map(v => v / stackTotal[lbl] * 100) : stackRaw[lbl],
    backgroundColor: stackColorForLabel(lbl) + "cc",
    borderColor: stackColorForLabel(lbl),
    borderWidth: 1, borderRadius: 2,
  }));
  mkChart(id, "bar", { labels: CHANNEL_ORDER, datasets }, commonOpts({
    plugins: {
      tooltip: {
        callbacks: {
          label: ctx => {
            const lbl = ctx.dataset.label;
            const raw = stackRaw[lbl][ctx.dataIndex];
            const p = raw / stackTotal[lbl];
            return `${lbl}: ${raw.toLocaleString()} repos (${pct(p)})`;
          }
        }
      }
    },
    scales: {
      x: { ticks: { color: th.text }, grid: { color: th.grid }, title: { display: true, text: "Channel", color: th.text } },
      y: norm
        ? { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid }, title: { display: true, text: "% of stack firing channel", color: th.text } }
        : { ticks: { color: th.text }, grid: { color: th.grid }, title: { display: true, text: "Repos firing channel", color: th.text } },
    },
  }));
  markNormalizable(id);
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 2: AGENTS
// ══════════════════════════════════════════════════════════════════════════════
function renderAgents() {
  const all = getFilteredRows();
  const stackLabels = [...new Set(all.map(r => r._stack || r.stack))];
  const th = getTheme();
  const topN = filters.topAgents;

  renderAgentLifecycleChart(all, stackLabels);
  renderAgentConcentrationChart(all);
  renderPrimaryAgentChart(all, stackLabels);

  // Top agents per stack (per-stack grid)
  buildCompareSlots("compare-agents-top-stacks", stackLabels, (id, lbl) => {
    const rows = all.filter(r => (r._stack || r.stack) === lbl);
    const counts = {};
    rows.forEach(r => r._agents.forEach(a => { counts[a] = (counts[a] || 0) + 1; }));
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, topN).reverse();
    if (!sorted.length) return;
    const norm = isNormalized(id);
    const total = rows.length || 1;
    const raw = sorted.map(([, c]) => c);
    mkChart(id, "bar", {
      labels: sorted.map(([a]) => a),
      datasets: [{ label: "Repos", data: norm ? raw.map(v => v / total * 100) : raw,
        backgroundColor: stackColorForLabel(lbl) + "cc", borderColor: stackColorForLabel(lbl), borderWidth: 1, borderRadius: 3 }],
    }, commonOpts({ indexAxis: "y",
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => `${raw[ctx.dataIndex].toLocaleString()} repos (${pct(raw[ctx.dataIndex] / total)})` } },
      },
      scales: {
        x: norm
          ? { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid }, title: { display: true, text: "% of stack", color: th.text } }
          : { ticks: { color: th.text }, grid: { color: th.grid } },
        y: { ticks: { color: th.text }, grid: { display: false } },
      },
    }));
    markNormalizable(id);
  });

  renderToolLoyaltyChart(all, stackLabels);
  renderAgentDiversityChart(all, stackLabels);

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
  buildCompareSlots("compare-commit-density-hist-stacks", stackLabels, (id, lbl) => {
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
  buildCompareSlots("compare-density-by-agent-stacks", stackLabels, (id, lbl) => {
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

// ── Agent-tab extras ──────────────────────────────────────────────────────────
function renderAgentLifecycleChart(all, stackLabels) {
  const th = getTheme();
  const topN = filters.topAgents || 8;
  buildCompareSlots("compare-agent-lifecycle-stacks", stackLabels, (id, lbl) => {
    const rows = all.filter(r => (r._stack || r.stack) === lbl);
    const total = rows.length || 1;
    const everCounts = {}, currentCounts = {}, configuredCounts = {};
    rows.forEach(r => {
      r._agents.forEach(a => { everCounts[a] = (everCounts[a] || 0) + 1; });
      r._current.forEach(a => { currentCounts[a] = (currentCounts[a] || 0) + 1; });
      r._configured.forEach(a => { configuredCounts[a] = (configuredCounts[a] || 0) + 1; });
    });
    const topAgents = Object.entries(everCounts)
      .filter(([a]) => a && a !== "Generic" && a !== "Rejected/noise")
      .sort((a, b) => b[1] - a[1]).slice(0, topN).map(([a]) => a);
    if (!topAgents.length) return;
    const norm = isNormalized(id);
    const everRaw = topAgents.map(a => everCounts[a] || 0);
    const currRaw = topAgents.map(a => currentCounts[a] || 0);
    const cfgRaw  = topAgents.map(a => configuredCounts[a] || 0);
    const toPct = arr => arr.map(v => v / total * 100);
    const rawByLabel = { "Ever observed": everRaw, "Currently active": currRaw, "Currently configured": cfgRaw };
    mkChart(id, "bar", {
      labels: topAgents,
      datasets: [
        { label: "Ever observed",        data: norm ? toPct(everRaw) : everRaw, backgroundColor: "#90A4AEcc", borderRadius: 3 },
        { label: "Currently active",     data: norm ? toPct(currRaw) : currRaw, backgroundColor: "#42A5F5cc", borderRadius: 3 },
        { label: "Currently configured", data: norm ? toPct(cfgRaw)  : cfgRaw,  backgroundColor: "#1565C0cc", borderRadius: 3 },
      ],
    }, commonOpts({
      indexAxis: "y",
      plugins: {
        tooltip: { callbacks: { label: ctx => {
          const raw = rawByLabel[ctx.dataset.label][ctx.dataIndex];
          return `${ctx.dataset.label}: ${raw.toLocaleString()} repos (${pct(raw / total)})`;
        } } }
      },
      scales: {
        x: norm
          ? { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid }, title: { display: true, text: "% of stack", color: th.text } }
          : { ticks: { color: th.text }, grid: { color: th.grid }, title: { display: true, text: "Repos", color: th.text } },
        y: { ticks: { color: th.text }, grid: { display: false } },
      },
    }));
    markNormalizable(id);
  }, { tall: true });
}

function renderAgentConcentrationChart(all) {
  const th = getTheme();
  const id = "chart-agent-concentration";
  const rows = all.filter(r => r._agent_count != null);
  if (!rows.length) { destroyChart(id); return; }
  const norm = isNormalized(id);
  const buckets = ["0","1","2","3","4+"];
  const stackLabels = [...new Set(rows.map(r => r._stack || r.stack))];
  const stackRaw = {}, stackTotal = {};
  stackLabels.forEach(lbl => {
    const srows = rows.filter(r => (r._stack || r.stack) === lbl);
    stackTotal[lbl] = srows.length || 1;
    stackRaw[lbl] = buckets.map(b => b === "4+"
      ? srows.filter(r => r._agent_count >= 4).length
      : srows.filter(r => r._agent_count === parseInt(b, 10)).length);
  });
  const datasets = stackLabels.map(lbl => ({
    label: lbl,
    data: norm ? stackRaw[lbl].map(v => v / stackTotal[lbl] * 100) : stackRaw[lbl],
    backgroundColor: stackColorForLabel(lbl) + "cc",
    borderRadius: 3,
  }));
  mkChart(id, "bar", { labels: buckets, datasets }, commonOpts({
    plugins: {
      tooltip: {
        callbacks: {
          label: ctx => {
            const lbl = ctx.dataset.label;
            const raw = stackRaw[lbl][ctx.dataIndex];
            return `${lbl}: ${raw.toLocaleString()} repos (${pct(raw / stackTotal[lbl])})`;
          }
        }
      }
    },
    scales: {
      x: { stacked: !norm, ticks: { color: th.text }, grid: { color: th.grid }, title: { display: true, text: "Agent families per repo", color: th.text } },
      y: norm
        ? { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid }, title: { display: true, text: "% of stack", color: th.text } }
        : { stacked: true, ticks: { color: th.text }, grid: { color: th.grid } },
    },
  }));
  markNormalizable(id);
}

function renderToolLoyaltyChart(all, stackLabels) {
  // Per-stack doughnut: % of agentic repos sticking with ONE agent family
  // vs those using 2, 3, or 4+ families.
  const th = getTheme();
  const SEG_LABELS = ["Loyal (1 tool)","Dabbling (2)","Mixed (3)","Polyglot (4+)"];
  const SEG_COLORS = ["#2a9d8f","#e9c46a","#f4a261","#e76f51"];
  buildCompareSlots("compare-tool-loyalty-stacks", stackLabels, (id, lbl) => {
    const agentic = all.filter(r => (r._stack || r.stack) === lbl && r._lbl === "agentic");
    if (!agentic.length) return;
    const n = agentic.length;
    const data = [
      agentic.filter(r => r._agents.length === 1).length,
      agentic.filter(r => r._agents.length === 2).length,
      agentic.filter(r => r._agents.length === 3).length,
      agentic.filter(r => r._agents.length >= 4).length,
    ];
    mkChart(id, "doughnut", {
      labels: SEG_LABELS,
      datasets: [{ data, backgroundColor: SEG_COLORS, borderWidth: 1 }],
    }, {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { color: th.text, font: { size: 10 }, boxWidth: 10 } },
        tooltip: { callbacks: { label: ctx => `${ctx.label}: ${ctx.raw.toLocaleString()} (${pct(ctx.raw / n)})` } },
        title: { display: true, text: `Loyal: ${pct(data[0]/n)} · n=${n.toLocaleString()}`, color: th.text, font: { size: 11 } },
      },
      cutout: "55%",
    });
  });
}

function renderAgentDiversityChart(all, stackLabels) {
  // Radar: each stack plotted on 4 diversity axes (0-100 scaled)
  //  • Shannon entropy (bits), normalised by log2(unique agents) × 100
  //  • Mean agents per agentic repo (0-4+ → 0-100)
  //  • % of agentic repos with ≥3 agents
  //  • % of agents families observed (coverage: unique agents / all agents seen globally)
  const th = getTheme();
  const host = document.getElementById("chart-agent-diversity");
  if (!host) return;
  const agenticAll = all.filter(r => r._lbl === "agentic");
  const globalAgents = new Set(); agenticAll.forEach(r => r._agents.forEach(a => globalAgents.add(a)));
  const globalTotal = globalAgents.size || 1;
  const perStack = stackLabels.map(lbl => {
    const rows = agenticAll.filter(r => (r._stack || r.stack) === lbl);
    const n = rows.length || 1;
    const freq = {};
    rows.forEach(r => r._agents.forEach(a => { freq[a] = (freq[a] || 0) + 1; }));
    const total = Object.values(freq).reduce((s, v) => s + v, 0) || 1;
    const k = Object.keys(freq).length || 1;
    let ent = 0; Object.values(freq).forEach(v => { const p = v / total; if (p > 0) ent -= p * Math.log2(p); });
    const entMax = Math.log2(k) || 1;
    const entNorm = (ent / entMax) * 100;
    const mean = rows.reduce((s, r) => s + (r._agents.length || 0), 0) / n;
    const meanScaled = Math.min(1, mean / 4) * 100;  // cap at 4 agents/repo
    const polyPct = rows.filter(r => r._agents.length >= 3).length / n * 100;
    const coverage = k / globalTotal * 100;
    return { lbl, entNorm, meanScaled, polyPct, coverage, mean: mean.toFixed(2), k };
  });
  const AXES = ["Entropy", "Avg agents/repo", "% with ≥3 agents", "Family coverage"];
  mkChart("chart-agent-diversity", "radar", {
    labels: AXES,
    datasets: perStack.map((s, i) => ({
      label: s.lbl,
      data: [s.entNorm, s.meanScaled, s.polyPct, s.coverage],
      backgroundColor: stackColorForLabel(s.lbl) + "33",
      borderColor: stackColorForLabel(s.lbl),
      borderWidth: 2,
      pointBackgroundColor: stackColorForLabel(s.lbl),
      pointRadius: 3,
    })),
  }, {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: th.text, font: { size: 11 } } },
      tooltip: {
        callbacks: {
          label: ctx => {
            const s = perStack[ctx.datasetIndex];
            if (!s) return "";
            const axis = AXES[ctx.dataIndex];
            if (axis === "Entropy")           return `Entropy: ${(s.entNorm/100 * Math.log2(s.k)).toFixed(2)} bits (${s.entNorm.toFixed(0)}% of max)`;
            if (axis === "Avg agents/repo")   return `Mean: ${s.mean} agents/repo`;
            if (axis === "% with ≥3 agents")  return `${s.polyPct.toFixed(1)}% have ≥3 families`;
            if (axis === "Family coverage")   return `${s.coverage.toFixed(0)}% of global families seen (${s.k}/${globalAgents.size})`;
            return "";
          }
        }
      }
    },
    scales: {
      r: {
        min: 0, max: 100,
        angleLines: { color: th.grid },
        grid: { color: th.grid },
        pointLabels: { color: th.text, font: { size: 11 } },
        ticks: { color: th.muted, backdropColor: "transparent", stepSize: 25, callback: v => v + "%" },
      },
    },
  });
}

function renderPrimaryAgentChart(all, stackLabels) {
  const th = getTheme();
  buildCompareSlots("compare-primary-agent-stacks", stackLabels, (id, lbl) => {
    const rows = all.filter(r => (r._stack || r.stack) === lbl && r._primary_agent);
    if (!rows.length) return;
    const counts = {};
    rows.forEach(r => { counts[r._primary_agent] = (counts[r._primary_agent] || 0) + 1; });
    const top = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 10);
    const n = rows.length;
    const norm = isNormalized(id);
    const raw = top.map(([, c]) => c);
    mkChart(id, "bar", {
      labels: top.map(([a]) => a),
      datasets: [{
        label: "Repos",
        data: norm ? raw.map(v => v / n * 100) : raw,
        backgroundColor: top.map((_, i) => PALETTE[i % PALETTE.length] + "cc"),
        borderRadius: 3,
      }],
    }, commonOpts({
      indexAxis: "y",
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => `${ctx.label}: ${raw[ctx.dataIndex].toLocaleString()} (${pct(raw[ctx.dataIndex] / n)})` } },
      },
      scales: {
        x: norm
          ? { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid }, title: { display: true, text: "% of stack", color: th.text } }
          : { ticks: { color: th.text }, grid: { color: th.grid } },
        y: { ticks: { color: th.text }, grid: { display: false } },
      },
    }));
    markNormalizable(id);
  });
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 3: GEOGRAPHY
// ══════════════════════════════════════════════════════════════════════════════

// Unified tier order: strongest → weakest → unresolved (last)
const GEO_CONF_ORDER = ["strong", "medium", "weak", "unresolved"];
const GEO_CONF_COLORS = {
  "strong":     "#1565C0",
  "medium":     "#42A5F5",
  "weak":       "#FFB74D",
  "unresolved": "#9E9E9E",
};
const GEO_CONF_LABELS = {
  "strong":     "strong (direct name / ISO / city match)",
  "medium":     "medium (regional hint)",
  "weak":       "weak (fuzzy / last-resort match)",
  "unresolved": "unresolved (no location)",
};

function renderCountryResolutionChart(all, stackLabels) {
  const th = getTheme();
  buildCompareSlots("compare-country-resolution-stacks", stackLabels, (id, lbl) => {
    const rows = all.filter(r => (r._stack || r.stack) === lbl);
    if (!rows.length) return;
    const buckets = {};
    rows.forEach(r => {
      const key = r._country ? r._geo_tier : "unresolved";
      buckets[key] = (buckets[key] || 0) + 1;
    });
    const total = rows.length;
    const ordered = GEO_CONF_ORDER.filter(k => buckets[k]);
    const labels = ordered.map(k => GEO_CONF_LABELS[k] || k);
    const counts = ordered.map(k => buckets[k]);
    const pcts = counts.map(c => c / total * 100);
    const colors = ordered.map(k => (GEO_CONF_COLORS[k] || "#78909C") + "cc");
    const resolvedN = rows.filter(r => r._country).length;
    const unresolvedN = total - resolvedN;
    mkChart(id, "bar", {
      labels,
      datasets: [{
        label: lbl,
        data: counts,
        _pct: pcts,
        backgroundColor: colors,
        borderColor: colors.map(c => c.slice(0, 7)),
        borderWidth: 1, borderRadius: 3,
      }],
    }, commonOpts({
      indexAxis: "y",
      plugins: {
        legend: { display: false },
        title: {
          display: true,
          color: th.text,
          font: { size: 12, weight: "normal" },
          text: `Total ${total.toLocaleString()} · Resolved ${resolvedN.toLocaleString()} (${(resolvedN/total*100).toFixed(1)}%) · Unresolved ${unresolvedN.toLocaleString()} (${(unresolvedN/total*100).toFixed(1)}%)`,
        },
        tooltip: { callbacks: {
          label: ctx => `${ctx.raw.toLocaleString()} repos (${pcts[ctx.dataIndex].toFixed(1)}%)`,
        } },
      },
      scales: {
        x: { ticks: { color: th.text }, grid: { color: th.grid }, title: { display: true, text: "Repos", color: th.text } },
        y: { ticks: { color: th.text }, grid: { display: false } },
      },
    }));
  });
}

function renderCountryTransparencyChart(all) {
  const th = getTheme();
  const canvasId = "chart-country-transparency";
  const geo = all.filter(r => r._country);
  if (!geo.length) { destroyChart(canvasId); return; }

  // Per-country tier split (strong / medium / weak). Ignore `unresolved`:
  // those rows have no country, so they're already excluded by `_country` above.
  const MIN_N = 30;
  const TOP_N = 25;
  const byCountry = new Map();
  for (const r of geo) {
    const c = r._country;
    let row = byCountry.get(c);
    if (!row) { row = { country: c, strong: 0, medium: 0, weak: 0, n: 0 }; byCountry.set(c, row); }
    const tier = r._geo_tier || "weak";
    if (tier === "strong" || tier === "medium" || tier === "weak") row[tier] += 1;
    row.n += 1;
  }
  const countries = [...byCountry.values()]
    .filter(c => c.n >= MIN_N)
    .map(c => ({
      ...c,
      strongPct: c.n ? c.strong / c.n * 100 : 0,
      mediumPct: c.n ? c.medium / c.n * 100 : 0,
      weakPct:   c.n ? c.weak   / c.n * 100 : 0,
    }))
    .sort((a, b) => b.strongPct - a.strongPct)
    .slice(0, TOP_N);

  if (!countries.length) { destroyChart(canvasId); return; }

  mkChart(canvasId, "bar", {
    labels: countries.map(c => c.country),
    datasets: [
      {
        label: "Strong (openly declared)",
        data: countries.map(c => c.strongPct),
        backgroundColor: GEO_CONF_COLORS.strong + "cc",
        borderColor:     GEO_CONF_COLORS.strong,
        borderWidth: 1,
      },
      {
        label: "Medium (region only)",
        data: countries.map(c => c.mediumPct),
        backgroundColor: GEO_CONF_COLORS.medium + "cc",
        borderColor:     GEO_CONF_COLORS.medium,
        borderWidth: 1,
      },
      {
        label: "Weak (inferred — no profile location)",
        data: countries.map(c => c.weakPct),
        backgroundColor: GEO_CONF_COLORS.weak + "cc",
        borderColor:     GEO_CONF_COLORS.weak,
        borderWidth: 1,
      },
    ],
  }, commonOpts({
    indexAxis: "y",
    plugins: {
      legend: { position: "bottom", labels: { color: th.text, font: { size: 11 }, boxWidth: 10 } },
      tooltip: {
        callbacks: {
          label: ctx => {
            const c = countries[ctx.dataIndex];
            const dsKey = ctx.datasetIndex === 0 ? "strong" : ctx.datasetIndex === 1 ? "medium" : "weak";
            const n = c[dsKey];
            const pctV = c[dsKey + "Pct"];
            return `${ctx.dataset.label.split(" (")[0]}: ${n.toLocaleString()} / ${c.n.toLocaleString()}  (${pctV.toFixed(1)}%)`;
          },
          title: items => {
            const c = countries[items[0].dataIndex];
            return `${c.country} · ${c.n.toLocaleString()} resolved owners`;
          },
        },
      },
    },
    scales: {
      x: { stacked: true, min: 0, max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid }, title: { display: true, text: "Share of resolved owners", color: th.text } },
      y: { stacked: true, ticks: { color: th.text }, grid: { display: false } },
    },
  }));
}

function renderGeography() {
  const all = getFilteredRows();
  const stackLabels = [...new Set(all.map(r => r._stack || r.stack))];
  const th = getTheme();
  const geo = all.filter(r => r._country);

  // Country resolution (data-quality panel) — how many owner locations parsed, at what confidence
  renderCountryResolutionChart(all, stackLabels);

  // Country location transparency — per country, share of owners resolved via strong evidence
  renderCountryTransparencyChart(all);

  // World regions — horizontal grouped bars, ranked by combined adoption rate
  const candidateRegions = REGION_ORDER.filter(r => geo.some(row => row._region === r));
  const perRegion = candidateRegions.map(reg => {
    const perStack = stackLabels.map(lbl => {
      const g = geo.filter(r => (r._stack || r.stack) === lbl && r._region === reg);
      return { lbl, n: g.length, rate: g.length ? g.filter(r => r._adopted).length / g.length * 100 : null };
    });
    const totalN = perStack.reduce((s, p) => s + p.n, 0);
    const totalK = perStack.reduce((s, p) => s + (p.n ? (p.rate / 100) * p.n : 0), 0);
    return { reg, perStack, combined: totalN ? totalK / totalN * 100 : 0, totalN };
  }).sort((a, b) => b.combined - a.combined);
  if (perRegion.length) {
    const sortedRegions = perRegion.map(r => r.reg);
    const regionDatasets = stackLabels.map(lbl => ({
      label: lbl,
      data: perRegion.map(r => {
        const ps = r.perStack.find(p => p.lbl === lbl);
        return ps && ps.n ? ps.rate : null;
      }),
      _n: perRegion.map(r => (r.perStack.find(p => p.lbl === lbl) || { n: 0 }).n),
      backgroundColor: stackColorForLabel(lbl) + "cc",
      borderColor: stackColorForLabel(lbl), borderWidth: 1, borderRadius: 3,
    }));
    mkChart("chart-world-regions", "bar", { labels: sortedRegions, datasets: regionDatasets },
      commonOpts({
        indexAxis: "y",
        plugins: {
          legend: { position: "bottom", labels: { color: th.text, font: { size: 11 }, boxWidth: 10 } },
          tooltip: { callbacks: { label: ctx => {
            const n = ctx.dataset._n[ctx.dataIndex] || 0;
            const v = ctx.parsed.x;
            return v == null ? `${ctx.dataset.label}: n=0` : `${ctx.dataset.label}: ${v.toFixed(1)}%  (n=${n.toLocaleString()})`;
          } } },
        },
        scales: {
          x: { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid }, title: { display: true, text: "Adoption rate", color: th.text } },
          y: { ticks: { color: th.text }, grid: { display: false } },
        },
      }));
  }

  // Top/bottom countries per stack
  buildCompareSlots("compare-countries-stacks", stackLabels, (id, lbl) => {
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

  // Income group — bar suppressed when bucket sample < MIN_INCOME_SAMPLE
  const incomeDatasets = stackLabels.map(lbl => {
    const rows = geo.filter(r => (r._stack || r.stack) === lbl && r._income);
    const ns = INCOME_ORDER.map(ig => rows.filter(r => r._income === ig).length);
    const data = INCOME_ORDER.map((ig, i) => {
      if (ns[i] < MIN_INCOME_SAMPLE) return null;
      const g = rows.filter(r => r._income === ig);
      return g.length ? g.filter(r => r._adopted).length / g.length * 100 : null;
    });
    return {
      label: lbl,
      data,
      _n: ns,
      backgroundColor: stackColorForLabel(lbl) + "cc",
      borderColor: stackColorForLabel(lbl), borderWidth: 1, borderRadius: 3,
    };
  });
  if (geo.some(r => r._income)) {
    mkChart("chart-income-group", "bar", { labels: INCOME_ORDER.map(k => INCOME_LABELS[k]), datasets: incomeDatasets },
      commonOpts({
        plugins: {
          legend: { labels: { color: th.text, font: { size: 11 } } },
          tooltip: { callbacks: { label: ctx => {
            const n = ctx.dataset._n[ctx.dataIndex] || 0;
            const v = ctx.parsed.y;
            if (v == null) {
              if (n === 0) return `${ctx.dataset.label}: no repos in this bucket`;
              return `${ctx.dataset.label}: hidden — n=${n} below floor of ${MIN_INCOME_SAMPLE}`;
            }
            return `${ctx.dataset.label}: ${v.toFixed(1)}%  (n=${n.toLocaleString()})`;
          } } },
        },
        scales: { x: { ticks: { color: th.text }, grid: { color: th.grid } }, y: { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } } },
      }));
  }

  // Pricing by income per stack — with sample-size floor
  buildCompareSlots("compare-pricing-income-stacks", stackLabels, (id, lbl) => {
    const rows = geo.filter(r => (r._stack || r.stack) === lbl && r._income);
    if (!rows.length) return;
    const labels = INCOME_ORDER.map(k => INCOME_LABELS[k]);
    const totalNs    = INCOME_ORDER.map(ig => rows.filter(r => r._income === ig).length);
    const agenticNs  = INCOME_ORDER.map(ig => rows.filter(r => r._income === ig && r._lbl === "agentic").length);
    const adoptRates = INCOME_ORDER.map((ig, i) => {
      if (totalNs[i] < MIN_INCOME_SAMPLE) return null;
      const g = rows.filter(r => r._income === ig);
      return g.length ? g.filter(r => r._adopted).length / g.length * 100 : null;
    });
    const paidPcts = INCOME_ORDER.map((ig, i) => {
      if (agenticNs[i] < MIN_INCOME_SAMPLE) return null;
      const ag = rows.filter(r => r._income === ig && r._lbl === "agentic");
      return ag.filter(r => r._agents.some(a => classifyPricing(a) === "paid")).length / ag.length * 100;
    });
    const freePcts = INCOME_ORDER.map((ig, i) => {
      if (agenticNs[i] < MIN_INCOME_SAMPLE) return null;
      const ag = rows.filter(r => r._income === ig && r._lbl === "agentic");
      return ag.filter(r => r._agents.some(a => classifyPricing(a) === "free")).length / ag.length * 100;
    });
    mkChart(id, "bar", {
      labels,
      datasets: [
        { label: "Adoption Rate", data: adoptRates, _n: totalNs, backgroundColor: "#1565C0cc", borderRadius: 3, order: 2 },
        { label: "Paid Tools %",  data: paidPcts,   _n: agenticNs, type: "line", borderColor: "#E53935", backgroundColor: "transparent", pointRadius: 4, borderWidth: 2, order: 1, spanGaps: false },
        { label: "Free Tools %",  data: freePcts,   _n: agenticNs, type: "line", borderColor: "#43A047", backgroundColor: "transparent", pointRadius: 4, borderWidth: 2, order: 1, spanGaps: false },
      ],
    }, commonOpts({
      plugins: {
        legend: { labels: { color: th.text, font: { size: 11 } } },
        tooltip: { mode: "index", intersect: false, callbacks: { label: ctx => {
          const n = ctx.dataset._n[ctx.dataIndex] || 0;
          const v = ctx.parsed.y;
          if (v == null) {
            if (n === 0) return `${ctx.dataset.label}: no repos in this bucket`;
            if (ctx.dataset.label === "Adoption Rate") return `${ctx.dataset.label}: hidden — n=${n} below floor of ${MIN_INCOME_SAMPLE}`;
            return `${ctx.dataset.label}: insufficient agentic sample (n=${n}, floor ${MIN_INCOME_SAMPLE})`;
          }
          return `${ctx.dataset.label}: ${v.toFixed(1)}%  (n=${n.toLocaleString()})`;
        } } },
      },
      scales: {
        x: { ticks: { color: th.text }, grid: { color: th.grid } },
        y: { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } },
      },
    }));
  });

  // MENA countries — per stack
  buildCompareSlots("compare-mena-countries-stacks", stackLabels, (id, lbl) => {
    const menaRows = geo.filter(r => (r._stack || r.stack) === lbl && r._is_mena);
    if (!menaRows.length) return;
    const menaCounts = {};
    menaRows.forEach(r => {
      if (!menaCounts[r._country]) menaCounts[r._country] = { n: 0, adopted: 0 };
      menaCounts[r._country].n++;
      if (r._adopted) menaCounts[r._country].adopted++;
    });
    const menaStats = Object.entries(menaCounts)
      .filter(([, v]) => v.n >= filters.menaMin)
      .map(([c, v]) => ({ c, rate: v.adopted / v.n * 100, n: v.n }))
      .sort((a, b) => a.rate - b.rate);
    if (!menaStats.length) return;
    mkChart(id, "bar", {
      labels: menaStats.map(s => s.c),
      datasets: [{ label: "Adoption Rate", data: menaStats.map(s => s.rate),
        backgroundColor: stackColorForLabel(lbl) + "cc", borderColor: stackColorForLabel(lbl), borderWidth: 1, borderRadius: 3 }],
    }, commonOpts({ indexAxis: "y",
      plugins: { legend: { display: false },
        tooltip: { callbacks: { label: ctx => `Rate: ${ctx.raw.toFixed(1)}% · n=${menaStats[ctx.dataIndex].n}` } } },
      scales: { x: { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } }, y: { ticks: { color: th.text }, grid: { display: false } } } }));
  });

  // Country × Month cohort — per stack, rendered as sparkline small-multiples
  buildCompareSlots("compare-country-heatmap", stackLabels, (id, lbl) => {
    renderCountryMonthSparks(id, geo, lbl);
  }, { html: true, tall: true });

  // Country Adoption Rate Trend — per-country compare slots (pick stack + country)
  renderCountryTrendSlots(geo, stackLabels);

  // Cumulative (combined across all stacks — one chart)
  const geoWithDate = geo.filter(r => r._month);
  if (geoWithDate.length) {
    const topN = filters.cumulN;
    const agentic = geoWithDate.filter(r => r._lbl === "agentic");
    const ctryFreq = {};
    agentic.forEach(r => { ctryFreq[r._country] = (ctryFreq[r._country] || 0) + 1; });
    const topCtries = Object.entries(ctryFreq)
      .filter(([, n]) => n >= filters.minCountry)
      .sort((a, b) => b[1] - a[1]).slice(0, topN).map(([c]) => c);
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

  // Country × primary agent matrix — per stack
  renderCountryAgentMatrix(geo, stackLabels);
}

function renderCountryTrendSlots(geo, stackLabels) {
  const th = getTheme();
  // Build "Stack · Country" combo labels, limited to top N by repo count per stack.
  const perStackTop = {};
  stackLabels.forEach(lbl => {
    const srows = geo.filter(r => (r._stack || r.stack) === lbl && r._month);
    const freq = {};
    srows.forEach(r => { freq[r._country] = (freq[r._country] || 0) + 1; });
    perStackTop[lbl] = Object.entries(freq)
      .filter(([, n]) => n >= filters.minCountry)
      .sort((a, b) => b[1] - a[1])
      .slice(0, filters.bumpN).map(([c]) => c);
  });
  const combos = [];
  stackLabels.forEach(lbl => perStackTop[lbl].forEach(c => combos.push(`${lbl} · ${c}`)));
  if (!combos.length) return;

  buildCompareSlots("compare-country-bump-stacks", combos, (id, combo) => {
    const sep = combo.indexOf(" · ");
    const lbl = combo.slice(0, sep);
    const country = combo.slice(sep + 3);
    const srows = geo.filter(r => (r._stack || r.stack) === lbl && r._country === country && r._month);
    if (!srows.length) { destroyChart(id); return; }
    const months = [...new Set(geo.filter(r => (r._stack || r.stack) === lbl && r._month).map(r => r._month))].sort();
    const cells = months.map(m => {
      const g = srows.filter(r => r._month === m);
      return { n: g.length, k: g.filter(r => r._adopted).length };
    });
    const WINDOW = 3;
    const rolled = cells.map((_, i) => {
      let n = 0, k = 0;
      for (let j = Math.max(0, i - (WINDOW - 1)); j <= i; j++) { n += cells[j].n; k += cells[j].k; }
      return n >= 5 ? { rate: k / n * 100, n } : { rate: null, n };
    });
    const color = stackColorForLabel(lbl);
    mkChart(id, "line", {
      labels: months,
      datasets: [{
        label: country,
        data: rolled.map(r => r.rate),
        _n: rolled.map(r => r.n),
        borderColor: color,
        backgroundColor: color + "33",
        pointRadius: 2,
        pointHoverRadius: 5,
        borderWidth: 2.5,
        tension: 0.4,
        fill: true,
        spanGaps: true,
      }],
    }, commonOpts({
      interaction: { mode: "nearest", axis: "x", intersect: false },
      plugins: {
        legend: { display: false },
        title: { display: true, color: th.text, font: { size: 12, weight: "normal" },
          text: `${lbl} · ${country} — total repos: ${srows.length.toLocaleString()}, agentic: ${srows.filter(r => r._adopted).length.toLocaleString()}` },
        tooltip: { callbacks: { label: ctx => {
          const n = ctx.dataset._n[ctx.dataIndex];
          const v = ctx.parsed.y;
          return v == null ? "insufficient data" : `${v.toFixed(1)}%  (n=${n})`;
        } } },
      },
      scales: {
        x: { ticks: { color: th.text, maxTicksLimit: 12 }, grid: { color: th.grid }, title: { display: true, text: "Repo creation month", color: th.text } },
        y: { min: 0, max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid }, title: { display: true, text: "Adoption rate (3-mo rolling)", color: th.text } },
      },
    }));
  }, { tall: true, label: "Stack · Country" });
}

function renderCountryMonthSparks(slotId, geo, lbl) {
  const host = document.getElementById(slotId);
  if (!host) return;
  const th = getTheme();
  const rows = geo.filter(r => (r._stack || r.stack) === lbl && r._month);
  if (!rows.length) { host.innerHTML = '<p class="muted">No month data for this stack.</p>'; return; }
  const topN = filters.heatmapN;
  const ctryFreq = {};
  rows.forEach(r => { ctryFreq[r._country] = (ctryFreq[r._country] || 0) + 1; });
  const topCtries = Object.entries(ctryFreq).sort((a, b) => b[1] - a[1]).slice(0, topN).map(([c]) => c);
  const months = [...new Set(rows.map(r => r._month))].sort();
  if (!topCtries.length || !months.length) { host.innerHTML = '<p class="muted">Not enough data.</p>'; return; }

  // Per country: monthly {n, k}; then 3-month rolling adoption rate
  const WINDOW = 3;
  const grid = document.createElement("div");
  grid.className = "compare-spark-grid";
  topCtries.forEach((country, idx) => {
    const cells = months.map(m => {
      const g = rows.filter(r => r._country === country && r._month === m);
      return { n: g.length, k: g.filter(r => r._adopted).length };
    });
    const series = cells.map((_, i) => {
      let n = 0, k = 0;
      for (let j = Math.max(0, i - (WINDOW - 1)); j <= i; j++) { n += cells[j].n; k += cells[j].k; }
      return n >= 5 ? k / n * 100 : null;
    });
    const latest = [...series].reverse().find(v => v != null);
    const latestLabel = latest == null ? "—" : latest.toFixed(0) + "%";
    const overallN = cells.reduce((s, c) => s + c.n, 0);
    const overallK = cells.reduce((s, c) => s + c.k, 0);
    const overallRate = overallN ? overallK / overallN * 100 : null;

    const card = document.createElement("div");
    card.className = "compare-spark-card";
    const canvasId = `${slotId}-spark-${idx}`;
    card.innerHTML = `
      <div class="compare-spark-header">
        <span class="compare-spark-country">${country}</span>
        <span class="compare-spark-latest" style="color:${stackColorForLabel(lbl)}">${latestLabel}</span>
      </div>
      <div class="compare-spark-canvas-wrap"><canvas id="${canvasId}"></canvas></div>
      <div class="compare-spark-sub">
        <span>n=${overallN.toLocaleString()}</span>
        <span>overall ${overallRate == null ? "—" : overallRate.toFixed(0) + "%"}</span>
      </div>
    `;
    grid.appendChild(card);

    // Chart.js sparkline
    requestAnimationFrame(() => {
      mkChart(canvasId, "line", {
        labels: months,
        datasets: [{
          label: country,
          data: series,
          _n: cells.map(c => c.n),
          borderColor: stackColorForLabel(lbl),
          backgroundColor: stackColorForLabel(lbl) + "22",
          pointRadius: 0,
          borderWidth: 2,
          tension: 0.35,
          fill: true,
          spanGaps: true,
        }],
      }, commonOpts({
        plugins: {
          legend: { display: false },
          tooltip: { mode: "index", intersect: false, callbacks: {
            label: ctx => {
              const n = ctx.dataset._n[ctx.dataIndex] || 0;
              const v = ctx.parsed.y;
              return v == null ? `${months[ctx.dataIndex]} · insufficient` : `${months[ctx.dataIndex]} · ${v.toFixed(0)}% (n=${n})`;
            },
            title: () => "",
          } },
        },
        scales: {
          x: { display: false },
          y: { display: false, min: 0, max: 100 },
        },
      }));
    });
  });
  host.innerHTML = "";
  host.appendChild(grid);
}

function renderCountryAgentMatrix(geo, stackLabels) {
  const th = getTheme();
  buildCompareSlots("compare-country-agent-matrix", stackLabels, (id, lbl) => {
    const rows = geo.filter(r => (r._stack || r.stack) === lbl && r._primary_agent);
    if (!rows.length) { destroyChart(id); return; }
    const ctryCounts = {};
    rows.forEach(r => { ctryCounts[r._country] = (ctryCounts[r._country] || 0) + 1; });
    const topCtries = Object.entries(ctryCounts)
      .filter(([, n]) => n >= Math.max(3, filters.minCountry))
      .sort((a, b) => b[1] - a[1]).slice(0, 12).map(([c]) => c);
    if (!topCtries.length) { destroyChart(id); return; }
    const agentCounts = {};
    rows.forEach(r => { if (topCtries.includes(r._country)) agentCounts[r._primary_agent] = (agentCounts[r._primary_agent] || 0) + 1; });
    const topAgents = Object.entries(agentCounts).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([a]) => a);
    // Per country: count per agent, plus "Other" bucket for any agent outside top set.
    const perCtry = {};
    topCtries.forEach(c => {
      const bucket = {};
      topAgents.forEach(a => bucket[a] = 0);
      bucket._other = 0;
      perCtry[c] = { bucket, n: 0 };
    });
    rows.forEach(r => {
      if (!perCtry[r._country]) return;
      const b = perCtry[r._country];
      b.n++;
      if (topAgents.includes(r._primary_agent)) b.bucket[r._primary_agent]++;
      else b.bucket._other++;
    });
    // Rank countries by their leader share (so dominant leaders bubble to the top).
    topCtries.sort((a, b) => {
      const aLead = Math.max(...topAgents.map(ag => perCtry[a].bucket[ag])) / perCtry[a].n;
      const bLead = Math.max(...topAgents.map(ag => perCtry[b].bucket[ag])) / perCtry[b].n;
      return bLead - aLead;
    });
    const series = [...topAgents, "_other"];
    const seriesLabels = [...topAgents, "Other"];
    const datasets = series.map((ag, i) => ({
      label: seriesLabels[i],
      data: topCtries.map(c => {
        const b = perCtry[c];
        return b.n ? b.bucket[ag] / b.n * 100 : 0;
      }),
      _raw: topCtries.map(c => perCtry[c].bucket[ag]),
      _n: topCtries.map(c => perCtry[c].n),
      backgroundColor: (ag === "_other" ? "#9E9E9E" : PALETTE[i % PALETTE.length]) + "cc",
      borderWidth: 0, borderRadius: 2,
    }));
    mkChart(id, "bar", { labels: topCtries, datasets }, commonOpts({
      indexAxis: "y",
      plugins: {
        legend: { position: "bottom", labels: { color: th.text, font: { size: 11 }, boxWidth: 10 } },
        tooltip: { mode: "index", intersect: false, callbacks: {
          label: ctx => {
            const raw = ctx.dataset._raw[ctx.dataIndex] || 0;
            const n = ctx.dataset._n[ctx.dataIndex] || 0;
            const pct = ctx.parsed.x;
            return `${ctx.dataset.label}: ${raw.toLocaleString()} / ${n.toLocaleString()} (${pct.toFixed(1)}%)`;
          },
        } },
      },
      scales: {
        x: { stacked: true, max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid }, title: { display: true, text: "Share of country's primary-agent mix", color: th.text } },
        y: { stacked: true, ticks: { color: th.text }, grid: { display: false } },
      },
    }));
  }, { tall: true });
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

  // Stacked area per stack (true filled area chart)
  buildCompareSlots("compare-stacked-area-stacks", stackLabels, (id, lbl) => {
    const rows = dated.filter(r => (r._stack || r.stack) === lbl);
    if (!rows.length) return;
    const ms = [...new Set(rows.map(r => r._month))].sort();
    const SEGS = [
      { k: "pervasive",  l: "Pervasive",  v: m => rows.filter(r => r._month === m && r._level === "pervasive").length },
      { k: "consistent", l: "Consistent", v: m => rows.filter(r => r._month === m && r._level === "consistent").length },
      { k: "limited",    l: "Limited",    v: m => rows.filter(r => r._month === m && r._level === "limited").length },
      { k: "none",       l: "No AI",      v: m => rows.filter(r => r._month === m && r._lbl === "none").length },
    ];
    const rawPerMonth = SEGS.map(s => ms.map(m => s.v(m)));
    const totals = ms.map((_, i) => rawPerMonth.reduce((acc, row) => acc + row[i], 0));
    const norm = isNormalized(id);
    const datasets = SEGS.map((s, i) => ({
      label: s.l,
      data: rawPerMonth[i].map((v, j) => norm ? (totals[j] ? v / totals[j] * 100 : 0) : v),
      _raw: rawPerMonth[i],
      borderColor: ADOPTION_DEPTH_COLORS[s.k],
      backgroundColor: ADOPTION_DEPTH_COLORS[s.k] + "aa",
      pointRadius: 0, borderWidth: 1.2, tension: 0.35, fill: true,
    }));
    mkChart(id, "line", { labels: ms, datasets }, commonOpts({
      plugins: {
        legend: { position: "bottom", labels: { color: th.text, font: { size: 11 }, boxWidth: 10 } },
        tooltip: { mode: "index", intersect: false, callbacks: {
          label: ctx => {
            const raw = ctx.dataset._raw ? ctx.dataset._raw[ctx.dataIndex] : ctx.parsed.y;
            const total = totals[ctx.dataIndex] || 0;
            const pct = total ? (raw / total * 100) : 0;
            return `${ctx.dataset.label}: ${raw.toLocaleString()} (${pct.toFixed(1)}%)`;
          },
        } },
      },
      scales: {
        x: { stacked: false, ticks: { color: th.text, maxTicksLimit: 10 }, grid: { color: th.grid } },
        y: { stacked: true, ticks: { color: th.text, callback: v => norm ? v + "%" : v }, grid: { color: th.grid }, max: norm ? 100 : undefined },
      },
    }));
    markNormalizable(id);
  }, { tall: true });

  // First signal recency per stack (replaces created-at based timing, which is identical to first_signal_at in this dataset)
  const recencyRows = all.filter(r => r._lbl === "agentic" && r._first_signal_days_ago != null);
  if (recencyRows.length) {
    const BUCKET_COLORS = { "≤7d":"#1565C0cc","8–30d":"#42A5F5cc","31–90d":"#66BB6Acc","91–180d":"#FFB74Dcc","180d+":"#9E9E9Ecc" };
    mkChart("chart-adoption-timing", "bar", {
      labels: stackLabels,
      datasets: RECENCY_ORDER.map(b => ({
        label: b,
        data: stackLabels.map(lbl => {
          const g = recencyRows.filter(r => (r._stack || r.stack) === lbl);
          return g.length ? g.filter(r => recencyBucket(r._first_signal_days_ago) === b).length / g.length * 100 : 0;
        }),
        backgroundColor: BUCKET_COLORS[b], borderRadius: 2,
      })),
    }, commonOpts({ scales: { x: { stacked: true, ticks: { color: th.text }, grid: { color: th.grid } }, y: { stacked: true, max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } } } }));
  } else {
    destroyChart("chart-adoption-timing");
  }

  // Days-since-first-signal density per stack (clipped to 365d)
  buildCompareSlots("compare-days-hist-stacks", stackLabels, (id, lbl) => {
    const rows = all.filter(r => (r._stack || r.stack) === lbl && r._lbl === "agentic" && r._first_signal_days_ago != null);
    if (!rows.length) return;
    const vals = rows.map(r => Math.min(365, r._first_signal_days_ago)).filter(v => !isNaN(v) && v >= 0);
    if (!vals.length) return;
    const bins = 36; const binSize = 365 / bins;
    const counts = new Array(bins).fill(0);
    vals.forEach(v => { const bi = Math.min(bins - 1, Math.floor(v / binSize)); counts[bi]++; });
    const total = vals.length;
    const norm = isNormalized(id);
    const labels = Array.from({ length: bins }, (_, i) => Math.round(i * binSize) + "d");
    const color = stackColorForLabel(lbl);
    const data = norm ? counts.map(c => c / total * 100) : counts;
    mkChart(id, "line", {
      labels,
      datasets: [{
        label: lbl,
        data,
        _raw: counts,
        borderColor: color,
        backgroundColor: color + "33",
        pointRadius: 0, borderWidth: 2, tension: 0.4, fill: true,
      }],
    }, commonOpts({
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => {
          const raw = counts[ctx.dataIndex] || 0;
          const pct = total ? (raw / total * 100) : 0;
          return `${raw.toLocaleString()} repos (${pct.toFixed(1)}%)`;
        } } },
      },
      scales: {
        x: { ticks: { color: th.text, maxTicksLimit: 10 }, grid: { color: th.grid } },
        y: { ticks: { color: th.text, callback: v => norm ? v + "%" : v }, grid: { color: th.grid }, beginAtZero: true },
      },
    }));
    markNormalizable(id);
  });

  renderAgentEmergenceChart(all);
  renderRecencyDepthChart(all, stackLabels);
  renderMonthlyNewAdoptersChart(all, stackLabels);
  renderCumulativeAdoptersChart(all, stackLabels);
  renderRetrofitVsGreenfieldChart(all, stackLabels);
  renderAdoptionMomentumChart(all, stackLabels);
  renderAuthoredDepthChart(all, stackLabels);
  renderTopCountriesTimelineChart(all);
  renderTopCountriesMonthlyChart(all);
}

// ── Top countries over time ────────────────────────────────────────────────────
function renderTopCountriesTimelineChart(all) {
  const id = "chart-top-countries-timeline";
  const th = getTheme();
  const rows = all.filter(r => r._lbl === "agentic" && r._month && r._country);
  if (!rows.length) { destroyChart(id); return; }
  const topN = filters.topCountries || 10;
  const totals = {};
  rows.forEach(r => { totals[r._country] = (totals[r._country] || 0) + 1; });
  const top = Object.entries(totals)
    .filter(([, n]) => n >= filters.minCountry)
    .sort((a, b) => b[1] - a[1]).slice(0, topN).map(([c]) => c);
  if (!top.length) { destroyChart(id); return; }
  const months = [...new Set(rows.map(r => r._month))].sort();
  const rawPer = top.map(country => {
    let cum = 0;
    return months.map(m => { cum += rows.filter(r => r._country === country && r._month === m).length; return cum; });
  });
  const finals = rawPer.map(d => d[d.length - 1] || 1);
  const norm = isNormalized(id);
  const datasets = top.map((country, i) => ({
    label: country,
    data: rawPer[i].map(v => norm ? (v / finals[i] * 100) : v),
    _raw: rawPer[i],
    borderColor: PALETTE[i % PALETTE.length],
    backgroundColor: PALETTE[i % PALETTE.length] + "22",
    pointRadius: 0, borderWidth: 2, tension: 0.35, fill: false,
  }));
  mkChart(id, "line", { labels: months, datasets }, commonOpts({
    plugins: {
      legend: { labels: { color: th.text, font: { size: 11 } }, position: "right" },
      tooltip: { mode: "index", intersect: false, callbacks: { label: ctx => {
        const raw = ctx.dataset._raw[ctx.dataIndex] || 0;
        const final = finals[ctx.datasetIndex] || 0;
        const pct = final ? (raw / final * 100) : 0;
        return `${ctx.dataset.label}: ${raw.toLocaleString()} (${pct.toFixed(1)}% of country total)`;
      } } },
    },
    scales: {
      x: { ticks: { color: th.text, maxTicksLimit: 12 }, grid: { color: th.grid } },
      y: { max: norm ? 100 : undefined, ticks: { color: th.text, callback: v => norm ? v + "%" : v }, grid: { color: th.grid }, title: { display: true, text: norm ? "% of country's final cumulative" : "Cumulative agentic repos", color: th.text } },
    },
  }));
  markNormalizable(id);
}

function renderTopCountriesMonthlyChart(all) {
  const id = "chart-top-countries-monthly";
  const th = getTheme();
  const rows = all.filter(r => r._lbl === "agentic" && r._month && r._country);
  if (!rows.length) { destroyChart(id); return; }
  const topN = filters.topCountries || 10;
  const totals = {};
  rows.forEach(r => { totals[r._country] = (totals[r._country] || 0) + 1; });
  const top = Object.entries(totals)
    .filter(([, n]) => n >= filters.minCountry)
    .sort((a, b) => b[1] - a[1]).slice(0, topN).map(([c]) => c);
  if (!top.length) { destroyChart(id); return; }
  const months = [...new Set(rows.map(r => r._month))].sort();
  const rawPer = top.map(country => months.map(m => rows.filter(r => r._country === country && r._month === m).length));
  const monthTotals = months.map((_, i) => rawPer.reduce((a, row) => a + row[i], 0));
  const norm = isNormalized(id);
  const datasets = top.map((country, i) => ({
    label: country,
    data: rawPer[i].map((v, j) => norm ? (monthTotals[j] ? v / monthTotals[j] * 100 : 0) : v),
    _raw: rawPer[i],
    backgroundColor: PALETTE[i % PALETTE.length] + "cc",
    borderColor: PALETTE[i % PALETTE.length], borderWidth: 1, borderRadius: 2,
  }));
  mkChart(id, "bar", { labels: months, datasets }, commonOpts({
    plugins: {
      legend: { labels: { color: th.text, font: { size: 11 } }, position: "right" },
      tooltip: { mode: "index", intersect: false, callbacks: { label: ctx => {
        const raw = ctx.dataset._raw[ctx.dataIndex] || 0;
        const total = monthTotals[ctx.dataIndex] || 0;
        const pct = total ? (raw / total * 100) : 0;
        return `${ctx.dataset.label}: ${raw.toLocaleString()} (${pct.toFixed(1)}%)`;
      } } },
    },
    scales: {
      x: { stacked: true, ticks: { color: th.text, maxTicksLimit: 12 }, grid: { color: th.grid } },
      y: { stacked: true, max: norm ? 100 : undefined, ticks: { color: th.text, callback: v => norm ? v + "%" : v }, grid: { color: th.grid }, title: { display: true, text: norm ? "Share of monthly top-N flow" : "New agentic repos", color: th.text } },
    },
  }));
  markNormalizable(id);
}

// ── Time-series extras ─────────────────────────────────────────────────────────
function renderMonthlyNewAdoptersChart(all, stackLabels) {
  const id = "chart-monthly-new-adopters";
  const th = getTheme();
  const rows = all.filter(r => r._lbl === "agentic" && r._month);
  if (!rows.length) { destroyChart(id); return; }
  const months = [...new Set(rows.map(r => r._month))].sort();
  const rawPerStack = stackLabels.map(lbl =>
    months.map(m => rows.filter(r => (r._stack || r.stack) === lbl && r._month === m).length));
  const totals = months.map((_, i) => rawPerStack.reduce((a, row) => a + row[i], 0));
  const norm = isNormalized(id);
  const datasets = stackLabels.map((lbl, i) => ({
    label: lbl,
    data: rawPerStack[i].map((v, j) => norm ? (totals[j] ? v / totals[j] * 100 : 0) : v),
    _raw: rawPerStack[i],
    backgroundColor: stackColorForLabel(lbl) + "cc",
    borderColor: stackColorForLabel(lbl), borderWidth: 1, borderRadius: 2,
  }));
  mkChart(id, "bar", { labels: months, datasets }, commonOpts({
    plugins: {
      legend: { labels: { color: th.text, font: { size: 11 } } },
      tooltip: { mode: "index", intersect: false, callbacks: { label: ctx => {
        const raw = ctx.dataset._raw[ctx.dataIndex] || 0;
        const total = totals[ctx.dataIndex] || 0;
        const pct = total ? (raw / total * 100) : 0;
        return `${ctx.dataset.label}: ${raw.toLocaleString()} (${pct.toFixed(1)}%)`;
      } } },
    },
    scales: {
      x: { stacked: true, ticks: { color: th.text, maxTicksLimit: 12 }, grid: { color: th.grid } },
      y: { stacked: true, max: norm ? 100 : undefined, ticks: { color: th.text, callback: v => norm ? v + "%" : v }, grid: { color: th.grid }, title: { display: true, text: norm ? "Share of monthly flow" : "New agentic repos", color: th.text } },
    },
  }));
  markNormalizable(id);
}

function renderCumulativeAdoptersChart(all, stackLabels) {
  const id = "chart-cumulative-adopters";
  const th = getTheme();
  const rows = all.filter(r => r._lbl === "agentic" && r._month);
  if (!rows.length) { destroyChart(id); return; }
  const months = [...new Set(rows.map(r => r._month))].sort();
  const rawPerStack = stackLabels.map(lbl => {
    let cum = 0;
    return months.map(m => { cum += rows.filter(r => (r._stack || r.stack) === lbl && r._month === m).length; return cum; });
  });
  const finals = rawPerStack.map(d => d[d.length - 1] || 0);
  const norm = isNormalized(id);
  const datasets = stackLabels.map((lbl, i) => {
    const color = stackColorForLabel(lbl);
    const final = finals[i] || 1;
    return {
      label: lbl,
      data: rawPerStack[i].map(v => norm ? (v / final * 100) : v),
      _raw: rawPerStack[i],
      borderColor: color,
      backgroundColor: color + "33",
      pointRadius: 0, borderWidth: 2.2, tension: 0.35, fill: !norm,
    };
  });
  mkChart(id, "line", { labels: months, datasets }, commonOpts({
    plugins: {
      legend: { labels: { color: th.text, font: { size: 11 } } },
      tooltip: { mode: "index", intersect: false, callbacks: { label: ctx => {
        const raw = ctx.dataset._raw[ctx.dataIndex] || 0;
        const final = finals[ctx.datasetIndex] || 0;
        const pct = final ? (raw / final * 100) : 0;
        return `${ctx.dataset.label}: ${raw.toLocaleString()} (${pct.toFixed(1)}% of stack total)`;
      } } },
    },
    scales: {
      x: { ticks: { color: th.text, maxTicksLimit: 12 }, grid: { color: th.grid } },
      y: { max: norm ? 100 : undefined, ticks: { color: th.text, callback: v => norm ? v + "%" : v }, grid: { color: th.grid }, title: { display: true, text: norm ? "% of stack's final cumulative" : "Cumulative agentic repos", color: th.text } },
    },
  }));
  markNormalizable(id);
}

function parseIsoDays(a, b) {
  if (!a || !b) return null;
  const da = Date.parse(a), db = Date.parse(b);
  if (isNaN(da) || isNaN(db)) return null;
  return Math.max(0, Math.round((db - da) / 86400000));
}

const RETROFIT_BUCKETS = ["Greenfield (≤7d)","Fast (7–30d)","Normal (1–3mo)","Slow (3–12mo)","Retrofit (1y+)"];
function retrofitBucket(days) {
  if (days == null || isNaN(days) || days < 0) return null;
  if (days <=   7) return "Greenfield (≤7d)";
  if (days <=  30) return "Fast (7–30d)";
  if (days <=  90) return "Normal (1–3mo)";
  if (days <= 365) return "Slow (3–12mo)";
  return "Retrofit (1y+)";
}

function renderRetrofitVsGreenfieldChart(all, stackLabels) {
  // "Greenfield vs Retrofit" = time from oldest scanned commit to first AI signal.
  // Short gap = AI landed near project birth (greenfield); long gap = added much later.
  const th = getTheme();
  const rows = all
    .filter(r => r._lbl === "agentic" && r._first_signal_at && r._oldest_commit_at)
    .map(r => Object.assign({}, r, { _gap_days: parseIsoDays(r._oldest_commit_at, r._first_signal_at) }))
    .filter(r => r._gap_days != null);
  if (!rows.length) { destroyChart("chart-retrofit-greenfield"); return; }
  const BUCKET_COLORS = ["#2a9d8f","#8ecae6","#e9c46a","#f4a261","#6c757d"];
  const datasets = RETROFIT_BUCKETS.map((b, i) => ({
    label: b,
    data: stackLabels.map(lbl => {
      const srows = rows.filter(r => (r._stack || r.stack) === lbl);
      return srows.length ? srows.filter(r => retrofitBucket(r._gap_days) === b).length / srows.length * 100 : 0;
    }),
    backgroundColor: BUCKET_COLORS[i] + "cc",
    borderRadius: 2,
  }));
  mkChart("chart-retrofit-greenfield", "bar", { labels: stackLabels, datasets }, commonOpts({
    scales: {
      x: { stacked: true, ticks: { color: th.text }, grid: { color: th.grid } },
      y: { stacked: true, max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid },
           title: { display: true, text: "Share of agentic repos", color: th.text } },
    },
  }));
}

function renderAdoptionMomentumChart(all, stackLabels) {
  // What % of agentic repos had their first signal inside each lookback window?
  const th = getTheme();
  const rows = all.filter(r => r._lbl === "agentic" && r._first_signal_days_ago != null);
  if (!rows.length) { destroyChart("chart-adoption-momentum"); return; }
  const WINDOWS = [
    { label: "≤30d",  days: 30 },
    { label: "≤90d",  days: 90 },
    { label: "≤180d", days: 180 },
    { label: "≤365d", days: 365 },
  ];
  const datasets = stackLabels.map(lbl => {
    const srows = rows.filter(r => (r._stack || r.stack) === lbl);
    const n = srows.length || 1;
    return {
      label: lbl,
      data: WINDOWS.map(w => srows.filter(r => r._first_signal_days_ago <= w.days).length / n * 100),
      backgroundColor: stackColorForLabel(lbl) + "cc",
      borderColor: stackColorForLabel(lbl), borderWidth: 1, borderRadius: 3,
    };
  });
  mkChart("chart-adoption-momentum", "bar", { labels: WINDOWS.map(w => w.label), datasets }, commonOpts({
    scales: {
      x: { ticks: { color: th.text }, grid: { color: th.grid },
           title: { display: true, text: "Lookback window (first AI signal within)", color: th.text } },
      y: { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid },
           title: { display: true, text: "% of agentic repos", color: th.text } },
    },
  }));
}

function renderAuthoredDepthChart(all, stackLabels) {
  // Distribution of AI-authored commit depth per stack. Uses commit_ratio tiers.
  // Shows how many repos are "flirting" vs "saturated".
  const th = getTheme();
  const rows = all.filter(r => r._lbl === "agentic" && r._density != null);
  if (!rows.length) { destroyChart("chart-authored-depth"); return; }
  const SEG_COLORS = { "Config-only (0%)":"#E0E0E0","Low (<10%)":"#FFE082","Medium (10–40%)":"#FFB74D","High (40–80%)":"#64B5F6","Full (≥80%)":"#1565C0" };
  const datasets = DENSITY_BUCKET_ORDER.map(b => ({
    label: b,
    data: stackLabels.map(lbl => {
      const srows = rows.filter(r => (r._stack || r.stack) === lbl);
      return srows.length ? srows.filter(r => densityBucket(r._density) === b).length / srows.length * 100 : 0;
    }),
    backgroundColor: SEG_COLORS[b] + "cc",
    borderRadius: 2,
  }));
  mkChart("chart-authored-depth", "bar", { labels: stackLabels, datasets }, commonOpts({
    scales: {
      x: { stacked: true, ticks: { color: th.text }, grid: { color: th.grid } },
      y: { stacked: true, max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid },
           title: { display: true, text: "Agentic repos by AI-commit depth", color: th.text } },
    },
  }));
}

function renderAgentEmergenceChart(all) {
  const id = "chart-agent-emergence";
  const th = getTheme();
  const rows = all.filter(r => r._lbl === "agentic" && r._month && r._primary_agent);
  if (!rows.length) { destroyChart(id); return; }
  const months = [...new Set(rows.map(r => r._month))].sort();
  const counts = {};
  rows.forEach(r => { counts[r._primary_agent] = (counts[r._primary_agent] || 0) + 1; });
  const topAgents = Object.entries(counts)
    .filter(([a]) => a && a !== "Generic")
    .sort((a, b) => b[1] - a[1]).slice(0, 6).map(([a]) => a);
  const rawPerAgent = topAgents.map(agent => {
    let cum = 0;
    return months.map(m => { cum += rows.filter(r => r._primary_agent === agent && r._month === m).length; return cum; });
  });
  const finals = rawPerAgent.map(d => d[d.length - 1] || 1);
  const norm = isNormalized(id);
  const datasets = topAgents.map((agent, i) => ({
    label: agent,
    data: rawPerAgent[i].map(v => norm ? (v / finals[i] * 100) : v),
    _raw: rawPerAgent[i],
    borderColor: PALETTE[i % PALETTE.length],
    backgroundColor: PALETTE[i % PALETTE.length] + "22",
    pointRadius: 0, borderWidth: 2.2, tension: 0.35, fill: false,
  }));
  mkChart(id, "line", { labels: months, datasets }, commonOpts({
    plugins: {
      legend: { labels: { color: th.text, font: { size: 11 } }, position: "right" },
      tooltip: { mode: "index", intersect: false, callbacks: { label: ctx => {
        const raw = ctx.dataset._raw[ctx.dataIndex] || 0;
        const final = finals[ctx.datasetIndex] || 0;
        const pct = final ? (raw / final * 100) : 0;
        return `${ctx.dataset.label}: ${raw.toLocaleString()} (${pct.toFixed(1)}% of agent total)`;
      } } },
    },
    scales: {
      x: { ticks: { color: th.text, maxTicksLimit: 12 }, grid: { color: th.grid } },
      y: { max: norm ? 100 : undefined, ticks: { color: th.text, callback: v => norm ? v + "%" : v }, grid: { color: th.grid }, title: { display: true, text: norm ? "% of agent's final footprint" : "Cumulative repos", color: th.text } },
    },
  }));
  markNormalizable(id);
}

function renderRecencyDepthChart(all, stackLabels) {
  const th = getTheme();
  const DEPTHS = ADOPTION_DEPTH_ORDER.filter(l => l !== "none");
  buildCompareSlots("compare-recency-depth-stacks", stackLabels, (id, lbl) => {
    const rows = all.filter(r => (r._stack || r.stack) === lbl && r._first_signal_days_ago != null);
    if (!rows.length) return;
    const rawPerDepth = DEPTHS.map(lvl =>
      RECENCY_ORDER.map(b => rows.filter(r => recencyBucket(r._first_signal_days_ago) === b && r._level === lvl).length)
    );
    const totals = RECENCY_ORDER.map((_, i) => rawPerDepth.reduce((acc, row) => acc + row[i], 0));
    const norm = isNormalized(id);
    const datasets = DEPTHS.map((lvl, i) => ({
      label: lvl,
      data: rawPerDepth[i].map((v, j) => norm ? (totals[j] ? v / totals[j] * 100 : 0) : v),
      _raw: rawPerDepth[i],
      backgroundColor: ADOPTION_DEPTH_COLORS[lvl] + "cc",
      borderRadius: 2,
    }));
    mkChart(id, "bar", { labels: RECENCY_ORDER, datasets }, commonOpts({
      plugins: {
        legend: { position: "bottom", labels: { color: th.text, font: { size: 11 }, boxWidth: 10 } },
        tooltip: { mode: "index", intersect: false, callbacks: {
          label: ctx => {
            const raw = ctx.dataset._raw ? ctx.dataset._raw[ctx.dataIndex] : ctx.parsed.y;
            const total = totals[ctx.dataIndex] || 0;
            const pct = total ? (raw / total * 100) : 0;
            return `${ctx.dataset.label}: ${raw.toLocaleString()} (${pct.toFixed(1)}%)`;
          },
        } },
      },
      scales: {
        x: { stacked: true, ticks: { color: th.text }, grid: { color: th.grid }, title: { display: true, text: "Days since first signal", color: th.text } },
        y: { stacked: true, max: norm ? 100 : undefined, ticks: { color: th.text, callback: v => norm ? v + "%" : v }, grid: { color: th.grid }, title: { display: true, text: norm ? "% of bucket" : "Repos", color: th.text } },
      },
    }));
    markNormalizable(id);
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
    const CAT_LABELS = ["No AI","Agentic"];
    const CAT_KEYS   = ["none","agentic"];
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
  const withCommits = all.filter(r => r._commits != null);
  if (withCommits.length) {
    const CAT_LABELS = ["No AI","Agentic"];
    const CAT_KEYS   = ["none","agentic"];
    const commitsDatasets = stackLabels.map(lbl => {
      const rows = withCommits.filter(r => (r._stack || r.stack) === lbl);
      return {
        label: lbl,
        data: CAT_KEYS.map(cat => {
          const g = rows.filter(r => r._lbl === cat).map(r => r._commits).filter(v => !isNaN(v)).sort((a, b) => a - b);
          return g.length ? g[Math.floor(g.length / 2)] : 0;
        }),
        backgroundColor: stackColorForLabel(lbl) + "cc", borderColor: stackColorForLabel(lbl), borderWidth: 1, borderRadius: 3,
      };
    });
    mkChart("chart-size-commits", "bar", { labels: CAT_LABELS, datasets: commitsDatasets },
      commonOpts({ scales: { x: { ticks: { color: th.text }, grid: { color: th.grid } }, y: { ticks: { color: th.text }, grid: { color: th.grid } } } }));
  } else {
    destroyChart("chart-size-commits");
  }

  // Commits tertile adoption rate (Small / Medium / Large by commit count)
  renderTertileAdoptionChart(
    "chart-size-commits-tertile",
    all.filter(r => r._commits != null).map(r => Object.assign({}, r, { _sizeVal: r._commits })),
    stackLabels,
    "commits",
  );

}

// ── Helpers: tertile adoption chart + empty-state ──────────────────────────────
function renderTertileAdoptionChart(canvasId, rowsWithSize, stackLabels, label) {
  const th = getTheme();
  if (!rowsWithSize.length) {
    showEmptyCanvas(canvasId, `No ${label} data in uploaded CSVs.`);
    return;
  }
  const TERTILE_LABELS = ["Small","Medium","Large"];
  const datasets = stackLabels.map(lbl => {
    const rows = rowsWithSize.filter(r => (r._stack || r.stack) === lbl).sort((a, b) => a._sizeVal - b._sizeVal);
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
  if (!datasets.length) { showEmptyCanvas(canvasId, `Not enough ${label} data per stack (need ≥3 repos).`); return; }
  mkChart(canvasId, "bar", { labels: TERTILE_LABELS, datasets },
    commonOpts({ scales: {
      x: { ticks: { color: th.text }, grid: { color: th.grid }, title: { display: true, text: label, color: th.text } },
      y: { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } },
    } }));
}

function showEmptyCanvas(canvasId, msg) {
  destroyChart(canvasId);
  const el = document.getElementById(canvasId);
  if (!el || !el.parentNode) return;
  // If we've already replaced it with a note, update text.
  const existing = el.parentNode.querySelector(`.compare-empty-note[data-for="${canvasId}"]`);
  if (existing) { existing.textContent = msg; return; }
  const note = document.createElement("div");
  note.className = "compare-empty-note";
  note.dataset.for = canvasId;
  note.textContent = msg;
  // Keep the canvas in DOM but hidden so download wiring can skip it.
  el.style.display = "none";
  el.parentNode.insertBefore(note, el);
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 6: DEPTH & ECOSYSTEMS
// ══════════════════════════════════════════════════════════════════════════════
function renderDepth() {
  const all = getFilteredRows();
  const stackLabels = [...new Set(all.map(r => r._stack || r.stack))];
  const th = getTheme();

  renderSemanticsCoverageChart(all, stackLabels);
  renderHistoryCoverageChart(all, stackLabels);

  // Framework adoption rate per stack (real data from package.json scans; JS/TS only).
  const haveFrameworks = all.some(r => r._frameworks && r._frameworks.length);
  if (haveFrameworks) {
    buildCompareSlots("compare-ecosystem-stacks", stackLabels, (id, lbl) => {
      const rows = all.filter(r => (r._stack || r.stack) === lbl && r._frameworks && r._frameworks.length);
      if (!rows.length) return;
      const fwMap = {};
      rows.forEach(r => r._frameworks.forEach(f => {
        if (!fwMap[f]) fwMap[f] = { n: 0, adopted: 0 };
        fwMap[f].n++;
        if (r._adopted) fwMap[f].adopted++;
      }));
      const stats = Object.entries(fwMap)
        .filter(([, v]) => v.n >= 5)
        .map(([f, v]) => ({ f, n: v.n, rate: v.adopted / v.n * 100 }))
        .sort((a, b) => a.rate - b.rate)
        .slice(-18);
      if (!stats.length) return;
      const color = stackColorForLabel(lbl);
      mkChart(id, "bar", {
        labels: stats.map(s => `${s.f} (n=${s.n})`),
        datasets: [{ label: "Adoption Rate", data: stats.map(s => s.rate),
          backgroundColor: stats.map(s => color + "cc"),
          borderColor: color, borderWidth: 1, borderRadius: 4 }],
      }, commonOpts({ indexAxis: "y", plugins: { legend: { display: false },
          tooltip: { callbacks: { label: ctx => {
            const s = stats[ctx.dataIndex]; return `${s.rate.toFixed(1)}%  (${Math.round(s.rate * s.n / 100)}/${s.n})`;
          } } } },
        scales: { x: { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid }, title: { display: true, text: "Adoption rate", color: th.text } }, y: { ticks: { color: th.text, font: { size: 10 } }, grid: { display: false } } } }));
    }, { tall: true });
  } else {
    const host = document.getElementById("compare-ecosystem-stacks");
    if (host) host.innerHTML = '<p class="muted">No framework data in the uploaded CSVs. Framework columns are populated for JS/TS only (from package.json scans). Upload a JS/TS integrated CSV with the <code>frameworks</code> column to see this chart.</p>';
  }

  // Agent market share over time (already percent-based)
  const dated = all.filter(r => r._lbl === "agentic" && r._month);
  if (dated.length) {
    const globalCounts = {};
    dated.forEach(r => r._agents.forEach(a => { globalCounts[a] = (globalCounts[a] || 0) + 1; }));
    const topN = 7;
    const topAgents = Object.entries(globalCounts).sort((a, b) => b[1] - a[1]).slice(0, topN).map(([a]) => a);
    const months = [...new Set(dated.map(r => r._month))].sort();
    const perMonthG = months.map(m => dated.filter(r => r._month === m));
    const msDatasets = topAgents.map((agent, i) => ({
      label: agent,
      data: perMonthG.map(g => g.length < 5 ? null : g.filter(r => r._agents.includes(agent)).length / g.length * 100),
      _counts: perMonthG.map(g => g.filter(r => r._agents.includes(agent)).length),
      _denoms: perMonthG.map(g => g.length),
      borderColor: PALETTE[i % PALETTE.length],
      backgroundColor: PALETTE[i % PALETTE.length] + "14",
      pointRadius: 0, borderWidth: 2.2, tension: 0.4, spanGaps: true, fill: false,
    }));
    mkChart("chart-agent-market-share", "line", { labels: months, datasets: msDatasets }, commonOpts({
      plugins: {
        legend: { labels: { color: th.text, font: { size: 11 } }, position: "right" },
        tooltip: { mode: "index", intersect: false, callbacks: { label: ctx => {
          const c = ctx.dataset._counts[ctx.dataIndex];
          const d = ctx.dataset._denoms[ctx.dataIndex];
          if (ctx.parsed.y == null) return `${ctx.dataset.label}: — (n<5)`;
          return `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}% (${c}/${d})`;
        } } },
      },
      scales: {
        x: { ticks: { color: th.text, maxTicksLimit: 12 }, grid: { color: th.grid } },
        y: { ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid }, title: { display: true, text: "Share of agentic repos that month", color: th.text } },
      },
    }));
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

  // JS/TS-only composition section (seed-phase lockfile / language / stratum).
  renderJstsComposition(all);
}

// ══════════════════════════════════════════════════════════════════════════════
// JS/TS STACK COMPOSITION (seed-phase ecosystem / language / size stratum)
// ══════════════════════════════════════════════════════════════════════════════
function renderJstsComposition(all) {
  const host = document.getElementById("compare-jsts-composition");
  if (!host) return;
  const stacksWithJstsCols = new Set(
    all.filter(r => r._ecosystem_type || r._primary_language_detected || r._size_stratum)
       .map(r => r._stack || r.stack)
       .filter(Boolean)
  );
  const rows = all.filter(r => stacksWithJstsCols.has(r._stack || r.stack));
  const hasData = rows.length > 0;
  host.hidden = !hasData;
  if (!hasData) return;

  renderJstsBar(rows, "chart-jsts-ecosystem", r => r._ecosystem_type,
    ["npm","pnpm","npm_no_lock","vanilla","yarn","deno","bun","unknown"]);
  renderJstsBar(rows, "chart-jsts-language", r => r._primary_language_detected,
    ["TypeScript","JavaScript"]);
  renderJstsBar(rows, "chart-jsts-size-stratum", r => r._size_stratum,
    ["small","medium","large"]);
  renderJstsLangEcoHeatmap(rows);
}

function renderJstsBar(rows, canvasId, keyFn, order) {
  const th = getTheme();
  const map = {};
  rows.forEach(r => {
    const k = keyFn(r);
    if (!k) return;
    if (!map[k]) map[k] = { n: 0, adopted: 0 };
    map[k].n++;
    if (r._adopted) map[k].adopted++;
  });
  let stats = Object.entries(map).map(([k, v]) => ({ k, n: v.n, adopted: v.adopted, rate: v.n ? v.adopted / v.n * 100 : 0 }));
  if (order && order.length) {
    const pos = Object.fromEntries(order.map((o, i) => [o.toLowerCase(), i]));
    stats = stats.filter(s => pos[s.k.toLowerCase()] != null)
                 .concat(stats.filter(s => pos[s.k.toLowerCase()] == null))
                 .sort((a, b) => {
                   const pa = pos[a.k.toLowerCase()]; const pb = pos[b.k.toLowerCase()];
                   if (pa != null && pb != null) return pa - pb;
                   if (pa != null) return -1; if (pb != null) return 1;
                   return b.n - a.n;
                 });
  } else {
    stats.sort((a, b) => b.n - a.n);
  }
  if (!stats.length) { destroyChart(canvasId); return; }
  const color = stackColorForLabel("JS/TS") || PALETTE[1];
  mkChart(canvasId, "bar", {
    labels: stats.map(s => `${s.k} (n=${s.n.toLocaleString()})`),
    datasets: [{ label: "Adoption Rate", data: stats.map(s => s.rate),
      backgroundColor: stats.map(s => s.n < 30 ? color + "66" : color + "cc"),
      borderColor: color, borderWidth: 1, borderRadius: 4 }],
  }, commonOpts({
    indexAxis: "y",
    plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => {
      const s = stats[ctx.dataIndex];
      const flag = s.n < 30 ? "  ⚠ small sample" : "";
      return `${s.rate.toFixed(1)}%  (${s.adopted.toLocaleString()}/${s.n.toLocaleString()})${flag}`;
    } } } },
    scales: {
      x: { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid },
           title: { display: true, text: "Adoption rate", color: th.text } },
      y: { ticks: { color: th.text, font: { size: 11 } }, grid: { display: false } },
    },
  }));
}

function renderJstsLangEcoHeatmap(rows) {
  const langs = ["TypeScript","JavaScript"];
  const ecos  = ["npm","pnpm","npm_no_lock","vanilla","yarn","deno","bun"];
  const cell = {};
  langs.forEach(l => { cell[l] = {}; ecos.forEach(e => { cell[l][e] = { n: 0, adopted: 0 }; }); });
  rows.forEach(r => {
    const l = r._primary_language_detected;
    const e = r._ecosystem_type;
    if (!langs.includes(l) || !ecos.includes(e)) return;
    cell[l][e].n++;
    if (r._adopted) cell[l][e].adopted++;
  });
  buildHeatmapTable("compare-jsts-lang-eco-heatmap", langs, ecos, (l, e) => {
    const c = cell[l][e];
    if (!c || !c.n) return { val: null, label: "—" };
    if (c.n < 30) return { val: null, label: `<span class="muted">${(c.adopted/c.n*100).toFixed(0)}%<br><small>n=${c.n}</small></span>` };
    const val = c.adopted / c.n * 100;
    return { val, label: `${val.toFixed(1)}%<br><small>n=${c.n.toLocaleString()}</small>` };
  }, "Language ↓ / Ecosystem →", "");
}

function renderSemanticsCoverageChart(all, stackLabels) {
  const th = getTheme();
  const rows = all.filter(r => r._semantics && r._semantics.length);
  if (!rows.length) { destroyChart("chart-semantics-coverage"); return; }
  const semKeys = ["configuration","activity","authorship","historical_lineage","generated_code"];
  const semLabels = ["Configuration","Activity","Authorship","Historical","Generated"];
  const datasets = stackLabels.map(lbl => {
    const srows = rows.filter(r => (r._stack || r.stack) === lbl);
    return {
      label: lbl,
      data: semKeys.map(k => srows.length ? srows.filter(r => r._semantics.includes(k)).length / srows.length * 100 : 0),
      backgroundColor: stackColorForLabel(lbl) + "cc",
      borderRadius: 3,
    };
  });
  mkChart("chart-semantics-coverage", "bar", { labels: semLabels, datasets }, commonOpts({
    scales: {
      x: { ticks: { color: th.text }, grid: { color: th.grid } },
      y: { max: 100, ticks: { color: th.text, callback: v => v + "%" }, grid: { color: th.grid } },
    },
  }));
}

function renderHistoryCoverageChart(all, stackLabels) {
  const th = getTheme();
  const rows = all.filter(r => r._history_coverage != null);
  if (!rows.length) { destroyChart("chart-history-coverage"); return; }
  const buckets = ["0–20%","20–40%","40–60%","60–80%","80–100%"];
  function bin(v) {
    if (v == null) return null;
    if (v < 0.2) return "0–20%";
    if (v < 0.4) return "20–40%";
    if (v < 0.6) return "40–60%";
    if (v < 0.8) return "60–80%";
    return "80–100%";
  }
  const datasets = stackLabels.map(lbl => {
    const srows = rows.filter(r => (r._stack || r.stack) === lbl);
    return {
      label: lbl,
      data: buckets.map(b => srows.filter(r => bin(r._history_coverage) === b).length),
      backgroundColor: stackColorForLabel(lbl) + "cc",
      borderRadius: 2,
    };
  });
  mkChart("chart-history-coverage", "bar", { labels: buckets, datasets }, commonOpts({
    scales: {
      x: { stacked: true, ticks: { color: th.text }, grid: { color: th.grid } },
      y: { stacked: true, ticks: { color: th.text }, grid: { color: th.grid } },
    },
  }));
}

// ══════════════════════════════════════════════════════════════════════════════
// SIDEBAR BUILDER
// ══════════════════════════════════════════════════════════════════════════════
function buildSidebar() {
  const sidebar = document.getElementById("compare-sidebar");
  if (!sidebar) return;
  const allStacks = stacks.map(s => s.label);

  // Pre-compute per-stack facets from REAL JS/TS columns (Go/Rust leave these empty,
  // so their "narrow by" details element won't render).
  const stackFacets = {};
  stacks.forEach(s => {
    const fwCount = new Map(); const cat = new Set();
    const lang = new Set(); const eco = new Set();
    s.rows.forEach(r => {
      const fwList = (r.frameworks || "").trim();
      if (fwList) {
        fwList.split("|").flatMap(x => x.split(";")).map(x => x.trim()).filter(Boolean)
          .forEach(f => fwCount.set(f, (fwCount.get(f) || 0) + 1));
      }
      const catList = (r.categories || "").trim();
      if (catList) {
        catList.split("|").flatMap(x => x.split(";")).map(x => x.trim()).filter(Boolean)
          .forEach(c => cat.add(c));
      }
      const ts = (r.typescript || "").trim().toLowerCase();
      if (ts === "yes") lang.add("TypeScript");
      else if (ts === "no") lang.add("JavaScript");
      const e = (r.ecosystem_type || "").trim().toLowerCase();
      if (e) eco.add(e);
    });
    const topFw = [...fwCount.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10);
    stackFacets[s.label] = {
      frameworks: topFw,                           // [[name, count], ...] top 10
      categories: [...cat].sort(),
      languages:  [...lang].sort(),
      ecosystems: [...eco].sort(),
    };
  });

  // Discover top-level enum facets.
  const allEnrichedSample = stacks.flatMap(s => s.rows.slice(0, 4000).map(r => enrichRow(r)));
  const levelSet = new Set(allEnrichedSample.map(r => r._level).filter(Boolean));
  const primaryAgentCounts = {};
  allEnrichedSample.forEach(r => { if (r._primary_agent) primaryAgentCounts[r._primary_agent] = (primaryAgentCounts[r._primary_agent] || 0) + 1; });
  const topPrimaryAgents = Object.entries(primaryAgentCounts).sort((a,b) => b[1]-a[1]).slice(0, 12).map(([a]) => a);
  const hasArchivedData = allEnrichedSample.some(r => r._is_archived);
  const hasActiveData   = allEnrichedSample.some(r => r._is_active_90d);

  let html = "";

  // ── Stacks (with nested framework + ecosystem) ──────────────────────────
  html += `<div class="compare-filter-group"><h4>Stacks</h4>`;
  allStacks.forEach(lbl => {
    const checked = !filters.selectedStacks || filters.selectedStacks.has(lbl);
    const col = stackColorForLabel(lbl);
    const facets = stackFacets[lbl] || { frameworks: [], categories: [], languages: [], ecosystems: [] };
    const sub = filters.perStackSub[lbl] || {};
    html += `<label class="compare-filter-row"><input type="checkbox" class="sf-stack" value="${escHtml(lbl)}"${checked ? " checked" : ""}><span class="compare-stack-dot" style="background:${col}"></span>${escHtml(lbl)}</label>`;
    const hasAny = facets.categories.length || facets.frameworks.length || facets.languages.length || facets.ecosystems.length;
    if (hasAny) {
      html += `<details class="compare-nested-group"><summary>↳ narrow by framework/category/language/ecosystem</summary>`;
      if (facets.languages.length) {
        html += `<div class="compare-nested-label">Language</div>`;
        facets.languages.forEach(l => {
          const isSel = sub.language && sub.language.has(l);
          html += `<label class="compare-filter-row compare-nested-row"><input type="checkbox" class="sf-substack" data-stack="${escHtml(lbl)}" data-kind="language" value="${escHtml(l)}"${isSel ? " checked" : ""}> ${escHtml(l)}</label>`;
        });
      }
      if (facets.ecosystems.length) {
        html += `<div class="compare-nested-label">Ecosystem</div>`;
        facets.ecosystems.forEach(e => {
          const isSel = sub.ecosystem && sub.ecosystem.has(e);
          html += `<label class="compare-filter-row compare-nested-row"><input type="checkbox" class="sf-substack" data-stack="${escHtml(lbl)}" data-kind="ecosystem" value="${escHtml(e)}"${isSel ? " checked" : ""}> ${escHtml(e)}</label>`;
        });
      }
      if (facets.categories.length) {
        html += `<div class="compare-nested-label">Category</div>`;
        facets.categories.forEach(c => {
          const isSel = sub.category && sub.category.has(c);
          html += `<label class="compare-filter-row compare-nested-row"><input type="checkbox" class="sf-substack" data-stack="${escHtml(lbl)}" data-kind="category" value="${escHtml(c)}"${isSel ? " checked" : ""}> ${escHtml(c)}</label>`;
        });
      }
      if (facets.frameworks.length) {
        html += `<div class="compare-nested-label">Framework <span class="muted">(top 10)</span></div>`;
        facets.frameworks.forEach(([f, n]) => {
          const isSel = sub.framework && sub.framework.has(f);
          html += `<label class="compare-filter-row compare-nested-row"><input type="checkbox" class="sf-substack" data-stack="${escHtml(lbl)}" data-kind="framework" value="${escHtml(f)}"${isSel ? " checked" : ""}> ${escHtml(f)} <span class="muted">(${n.toLocaleString()})</span></label>`;
        });
      }
      html += "</details>";
    }
  });
  html += "</div>";

  // ── Date range ─────────────────────────────────────────────────────────
  const months = [...new Set(stacks.flatMap(s => s.rows.map(r => getMonth(r)).filter(Boolean)))].sort();
  if (months.length >= 2) {
    html += `<div class="compare-filter-group"><h4>Date range</h4>
      <label class="compare-filter-row">From<select id="sf-date-from" class="field-input sf-date">`;
    months.forEach(m => { html += `<option value="${m}"${m === (filters.dateFrom || months[0]) ? " selected" : ""}>${m}</option>`; });
    html += `</select></label><label class="compare-filter-row">To<select id="sf-date-to" class="field-input sf-date">`;
    months.forEach(m => { html += `<option value="${m}"${m === (filters.dateTo || months[months.length - 1]) ? " selected" : ""}>${m}</option>`; });
    html += `</select></label></div>`;
  }

  // ── Adoption depth ─────────────────────────────────────────────────────
  if (levelSet.size > 1) {
    html += `<div class="compare-filter-group"><h4>Adoption depth</h4>`;
    ADOPTION_DEPTH_ORDER.forEach(lvl => {
      if (!levelSet.has(lvl)) return;
      const isSel = filters.adoptionLevels && filters.adoptionLevels.has(lvl);
      html += `<label class="compare-filter-row"><input type="checkbox" class="sf-level" value="${lvl}"${isSel ? " checked" : ""}>${lvl}</label>`;
    });
    html += `<p class="muted compare-filter-hint">Leave empty to include all levels.</p></div>`;
  }

  // ── Repo state (archived / active) ─────────────────────────────────────
  if (hasArchivedData || hasActiveData) {
    html += `<div class="compare-filter-group"><h4>Repo state</h4>`;
    if (hasArchivedData) {
      html += `<label class="compare-filter-row">Archived<select id="sf-archived" class="field-input">
        <option value="any"${filters.archived === "any" ? " selected" : ""}>Any</option>
        <option value="exclude"${filters.archived === "exclude" ? " selected" : ""}>Exclude</option>
        <option value="only"${filters.archived === "only" ? " selected" : ""}>Only</option>
      </select></label>`;
    }
    if (hasActiveData) {
      html += `<label class="compare-filter-row">Active &lt;90d<select id="sf-active90" class="field-input">
        <option value="any"${filters.active90 === "any" ? " selected" : ""}>Any</option>
        <option value="only"${filters.active90 === "only" ? " selected" : ""}>Only</option>
        <option value="exclude"${filters.active90 === "exclude" ? " selected" : ""}>Exclude</option>
      </select></label>`;
    }
    html += `</div>`;
  }

  // ── Primary agent family ───────────────────────────────────────────────
  if (topPrimaryAgents.length > 1) {
    html += `<div class="compare-filter-group"><h4>Primary agent family</h4><details class="compare-eco-group"><summary>${filters.primaryAgents && filters.primaryAgents.size ? filters.primaryAgents.size + " selected" : "any"}</summary>`;
    topPrimaryAgents.forEach(a => {
      const isSel = filters.primaryAgents && filters.primaryAgents.has(a);
      html += `<label class="compare-filter-row"><input type="checkbox" class="sf-primary" value="${escHtml(a)}"${isSel ? " checked" : ""}> ${escHtml(a)}</label>`;
    });
    html += `</details></div>`;
  }

  // ── Min repos per country ──────────────────────────────────────────────
  html += `<div class="compare-filter-group"><h4>Min repos per country <span id="sf-mincountry-val">${filters.minCountry}</span></h4>
    <input type="range" id="sf-mincountry" min="1" max="50" value="${filters.minCountry}" class="compare-range">
  </div>`;

  // ── Chart sliders ──────────────────────────────────────────────────────
  html += `<div class="compare-filter-group"><h4>Chart controls</h4>
    <label class="compare-filter-row">Top agents <input type="range" id="sf-top-agents" min="3" max="15" value="${filters.topAgents}" class="compare-range"> <span id="sf-top-agents-val">${filters.topAgents}</span></label>
    <label class="compare-filter-row">Top countries <input type="range" id="sf-top-countries" min="5" max="20" value="${filters.topCountries}" class="compare-range"> <span id="sf-top-countries-val">${filters.topCountries}</span></label>
    <label class="compare-filter-row">Heatmap rows <input type="range" id="sf-heatmap-n" min="5" max="25" value="${filters.heatmapN}" class="compare-range"> <span id="sf-heatmap-n-val">${filters.heatmapN}</span></label>
    <label class="compare-filter-row">Bump rows <input type="range" id="sf-bump-n" min="4" max="20" value="${filters.bumpN}" class="compare-range"> <span id="sf-bump-n-val">${filters.bumpN}</span></label>
    <label class="compare-filter-row">Cumul. countries <input type="range" id="sf-cumul-n" min="3" max="20" value="${filters.cumulN}" class="compare-range"> <span id="sf-cumul-n-val">${filters.cumulN}</span></label>
    <label class="compare-filter-row">MENA min repos <input type="range" id="sf-mena-min" min="1" max="30" value="${filters.menaMin}" class="compare-range"> <span id="sf-mena-min-val">${filters.menaMin}</span></label>
  </div>`;

  sidebar.innerHTML = html;

  // ── Event wiring ────────────────────────────────────────────────────────
  sidebar.querySelectorAll(".sf-stack").forEach(cb => cb.addEventListener("change", () => {
    const checked = [...sidebar.querySelectorAll(".sf-stack:checked")].map(c => c.value);
    filters.selectedStacks = checked.length === allStacks.length ? null : new Set(checked);
    scheduleRender();
  }));
  sidebar.querySelectorAll(".sf-substack").forEach(cb => cb.addEventListener("change", () => {
    const stack = cb.dataset.stack, kind = cb.dataset.kind;
    const sub = filters.perStackSub[stack] = filters.perStackSub[stack] || {};
    sub[kind] = sub[kind] || new Set();
    if (cb.checked) sub[kind].add(cb.value); else sub[kind].delete(cb.value);
    if (sub[kind].size === 0) delete sub[kind];
    scheduleRender();
  }));
  sidebar.querySelectorAll(".sf-date").forEach(sel => sel.addEventListener("change", () => {
    const from = document.getElementById("sf-date-from"); const to = document.getElementById("sf-date-to");
    filters.dateFrom = from ? from.value : null;
    filters.dateTo   = to   ? to.value   : null;
    scheduleRender();
  }));
  sidebar.querySelectorAll(".sf-level").forEach(cb => cb.addEventListener("change", () => {
    const checked = [...sidebar.querySelectorAll(".sf-level:checked")].map(c => c.value);
    filters.adoptionLevels = checked.length ? new Set(checked) : null;
    scheduleRender();
  }));
  sidebar.querySelectorAll(".sf-primary").forEach(cb => cb.addEventListener("change", () => {
    const checked = [...sidebar.querySelectorAll(".sf-primary:checked")].map(c => c.value);
    filters.primaryAgents = checked.length ? new Set(checked) : null;
    scheduleRender();
  }));
  const archEl = document.getElementById("sf-archived");
  if (archEl) archEl.addEventListener("change", () => { filters.archived = archEl.value; scheduleRender(); });
  const actEl = document.getElementById("sf-active90");
  if (actEl) actEl.addEventListener("change", () => { filters.active90 = actEl.value; scheduleRender(); });
  const mcSlider = document.getElementById("sf-mincountry");
  if (mcSlider) mcSlider.addEventListener("input", () => {
    filters.minCountry = parseInt(mcSlider.value); document.getElementById("sf-mincountry-val").textContent = filters.minCountry; scheduleRender();
  });
  [["sf-top-agents","topAgents"],["sf-top-countries","topCountries"],["sf-heatmap-n","heatmapN"],["sf-bump-n","bumpN"],["sf-cumul-n","cumulN"],["sf-mena-min","menaMin"]].forEach(([id, key]) => {
    const el = document.getElementById(id); if (!el) return;
    el.addEventListener("input", () => { filters[key] = parseInt(el.value); document.getElementById(id + "-val").textContent = filters[key]; scheduleRender(); });
  });
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
  // Attach per-chart PNG download + normalize + info toggles (idempotent).
  requestAnimationFrame(() => { attachDownloadButtons(); attachNormalizeButtons(); attachInfoButtons(); closeInfoPop(); });
}
let _renderTimer = null;
function scheduleRender() {
  if (_renderTimer) clearTimeout(_renderTimer);
  _renderTimer = setTimeout(() => { _renderTimer = null; renderActiveTab(); }, 200);
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
  const agentic = s.rows.filter(r => String(r.agentic_present || "").trim().toLowerCase() === "true").length;
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
    const enriched = rows.map(enrichRow);
    stacks.push({ filename: file.name, label, rows, enriched });
  }
  refreshStackTable();
  persistStacks();
}
function removeStack(idx) { stacks.splice(idx, 1); refreshStackTable(); persistStacks(); }
function clearAllStacks() {
  if (!stacks.length) return;
  if (!confirm("Remove all uploaded datasets?")) return;
  stacks.splice(0, stacks.length);
  Object.keys(charts).forEach(k => { try { charts[k].destroy(); } catch (_) {} delete charts[k]; });
  document.getElementById("compare-dashboard").hidden = true;
  document.getElementById("compare-empty").hidden = false;
  refreshStackTable();
  persistStacks();
}

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
      const n = rows.length; const ad = rows.filter(r => r._adopted).length;
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
  persistStacks();
});
document.getElementById("compare-clear-all")?.addEventListener("click", clearAllStacks);

hydrateStacks().then(ok => { if (ok) refreshStackTable(); });

// ── Sidebar collapse/pin ─────────────────────────────────────────────────────
(function() {
  const sidebar = document.getElementById("compare-sidebar");
  const edge = document.getElementById("compare-sidebar-edge");
  if (!sidebar || !edge) return;
  const PIN_KEY = "compare_sidebar_pinned";
  let closeTimer = null;
  const open  = () => { if (closeTimer) { clearTimeout(closeTimer); closeTimer = null; } sidebar.classList.add("is-open"); };
  const close = () => { closeTimer = setTimeout(() => sidebar.classList.remove("is-open"), 180); };
  edge.addEventListener("mouseenter", open);
  edge.addEventListener("mouseleave", close);
  sidebar.addEventListener("mouseenter", open);
  sidebar.addEventListener("mouseleave", close);
  edge.addEventListener("click", () => {
    const pinned = sidebar.classList.toggle("is-pinned");
    try { localStorage.setItem(PIN_KEY, pinned ? "1" : "0"); } catch (_) {}
    edge.setAttribute("aria-pressed", pinned ? "true" : "false");
  });
  try { if (localStorage.getItem(PIN_KEY) === "1") sidebar.classList.add("is-pinned"); } catch (_) {}
})();

document.getElementById("btn-export-html")?.addEventListener("click", exportHTML);
document.getElementById("btn-export-pdf")?.addEventListener("click",  exportPDF);
document.getElementById("theme-toggle")?.addEventListener("click",    () => setTimeout(renderActiveTab, 80));

})();
