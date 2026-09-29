'use strict';

// ================================================================ map core
// The part of the map every product shares. build_map.py inlines this file first and
// the product after it (src_app.js — the 2022 analysis map, src_volunteer.js — the
// election-day volunteers' map), into the same <script>, so the two see one scope.
//
// The product provides, before its start-up calls into anything here:
//   state        { mode, q, selected, labels, tableLevel, tableSort, ... }
//   visible()    the sites the active filters keep
//   colorOf(s)   a marker's fill in the current colour mode
//   tipHtml(s), cardHtml(s)   the hover tooltip, and the card a tap opens on a phone
//   renderStats(), renderLegend(), renderList(), renderDetail(s), renderAbout()
//   syncFilterSummary()
//   SITE_COLS, KALPI_COLS, kalpiRows, MOBILE_KEYS   the table view
//   markerStyle(s, selected)   optional: extra Leaflet path options for a marker
//   labelText(s), labelTitle(shown, total)   optional: what the map's labels say (the
//                site's name by default) and the label button's tooltip
//   LABEL_SIDES  optional: the sides of its marker a label may take, in order of
//                preference (below only by default)
//   LABEL_CLEAR_MARKERS  optional: true keeps labels off other sites' markers as well
// and ends its start-up with startShell().

// ---------------------------------------------------------------- helpers
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const nf = new Intl.NumberFormat('he-IL');
const num = n => nf.format(Math.round(n));
const pct = (n, d = 1) => (n == null ? '—' : n.toFixed(d).replace(/\.0$/, '') + '%');
const share = (v, t) => (t ? (100 * v) / t : 0);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const cssVar = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

// The city is data, not a literal: every string that names it is built from
// DATA.city.name so the same front end serves any city in config.CITIES.
// Both prefixes are single letters glued to a noun, which is how Hebrew forms
// "in <city>" and "from <city>" for the names in play (בחיפה, מחיפה, בבית שמש).
const CITY = DATA.city.name;
const IN_CITY = 'ב' + CITY;
const FROM_CITY = 'מ' + CITY;

// marker radius ~ sqrt(eligible voters) so the marker AREA is proportional to the
// size of the electorate the station serves — colour then shows how much of that
// electorate actually turned out. Scaled down when zoomed out so dense areas do
// not fuse into one blob.
const zoomScale = () => { const z = map.getZoom(); return z <= 12 ? 0.62 : z <= 13 ? 0.78 : z <= 14 ? 0.92 : z <= 16 ? 1 : 1.15; };
const baseRadius = (v, k = 0.235) => Math.max(3.2, Math.min(14, 1.2 + Math.sqrt(Math.max(0, v)) * k));
// Size is the electorate in EVERY mode, potential included — the mode changes the
// colour and nothing else. Sizing potential mode by the potential spent both channels
// on the same variable: a big marker was dark because it was big, and the map carried
// one number instead of two. With area on בעלי זכות and colour on the potential,
// "big and dark" says a large electorate with a lot of it still on the table, and
// "small and dark" — a modest electorate that barely voted — becomes visible too.
const radiusOf = s => baseRadius(s.eligible) * zoomScale();

const partyName = k => DATA.party_names[k] || k;
// one address arrives mangled from the official PDF; everything else is used verbatim
const ADDRESS_FIX = { 'פרץ י .ל20,.': 'י.ל. פרץ 20' };
const addressOf = s => ADDRESS_FIX[s.address] || s.address;
const signed = (n, d = 1) => (n > 0 ? '+' : '') + n.toFixed(d).replace(/\.0$/, '') + '%';

const sites = DATA.sites;
const kalpiNumKey = s => (s.kalpiot ? s.kalpiot[0].kalpi : s.kalpi).split('.').map(Number).reduce((a, b) => a * 1000 + b, 0);

// ---------------------------------------------------------------- map
const map = L.map('map', { zoomControl: false, preferCanvas: false, attributionControl: true })
  .setView(DATA.city.center, DATA.city.zoom);
L.control.zoom({ position: 'topleft' }).addTo(map);
L.control.scale({ imperial: false, position: 'bottomleft', maxWidth: 120 }).addTo(map);

const TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · נתונים: ועדת הבחירות המרכזית';
let tileLayer = null;
function setTiles() {
  const dark = document.documentElement.getAttribute('data-theme') === 'dark' ||
    (!document.documentElement.getAttribute('data-theme') && matchMedia('(prefers-color-scheme: dark)').matches);
  if (!tileLayer) {
    tileLayer = L.tileLayer(TILE_URL, { attribution: ATTR, maxZoom: 19, crossOrigin: true }).addTo(map);
    tileLayer.setZIndex(0);
  }
  // the basemap is muted in CSS so the data markers stay the loudest thing on screen
  document.getElementById('map').classList.toggle('tiles-dark', dark);
}

const markerLayer = L.layerGroup().addTo(map);
const markers = new Map();

// Pointer devices get the hover tooltip; touch layouts get the tappable card.
// Rebound on layout change so a resize does not leave the wrong one attached.
function bindMarkerUI(m, s) {
  m.unbindTooltip(); m.unbindPopup();
  if (isNarrow()) {
    m.bindPopup(() => cardHtml(s), {
      className: 'mcard-popup', maxWidth: 260, minWidth: 200,
      autoPanPadding: [12, 12], closeButton: true,
    });
  } else {
    m.bindTooltip(tipHtml(s), { className: 'tip', direction: 'top', offset: [0, -6], sticky: false });
  }
}

function buildMarkers() {
  markerLayer.clearLayers(); markers.clear();
  for (const s of [...sites].sort((a, b) => b.eligible - a.eligible)) {   // small markers last = on top
    if (s.lat == null) continue;
    const m = L.circleMarker([s.lat, s.lon], {
      radius: radiusOf(s), color: cssVar('--ring'), weight: 1.5, opacity: 1,
      fillColor: colorOf(s), fillOpacity: 0.85, className: 'site-marker',
    });
    bindMarkerUI(m, s);
    // on a narrow layout the bound popup handles the tap; anywhere else a click
    // opens the full panel, which is already beside the map
    m.on('click', () => { if (!isNarrow()) selectSite(s.id, false); });
    m.on('keypress', () => selectSite(s.id, false));
    markers.set(s.id, m);
  }
  restyleMarkers();
}

// the card is plain HTML inside a Leaflet popup, so its button is delegated
map.getContainer().addEventListener('click', e => {
  const b = e.target.closest('.mcard-more');
  if (!b) return;
  map.closePopup();
  selectSite(+b.dataset.id, false);
});

function restyleMarkers() {
  const vis = new Set(visible().map(s => s.id));
  for (const s of sites) {
    const m = markers.get(s.id); if (!m) continue;
    const on = vis.has(s.id);
    if (on && !markerLayer.hasLayer(m)) markerLayer.addLayer(m);
    if (!on && markerLayer.hasLayer(m)) markerLayer.removeLayer(m);
    if (!on) continue;
    const sel = state.selected === s.id;
    m.setStyle({
      fillColor: colorOf(s), fillOpacity: sel ? 1 : 0.88,
      color: sel ? cssVar('--text-primary') : cssVar('--ring'), weight: sel ? 3 : 2,
      ...(typeof markerStyle === 'function' ? markerStyle(s, sel) : null),
    });
    m.setRadius(radiusOf(s) * (sel ? 1.25 : 1));
    if (sel) m.bringToFront();
  }
  updateLabels();
}

let labelLayer = L.layerGroup();
const labelOf = s => (typeof labelText === 'function' ? labelText(s) : s.name);
const labelSides = () => (typeof LABEL_SIDES !== 'undefined' ? LABEL_SIDES : ['bottom']);
// A label's box on one side of its marker (container px, padded 3px left and right and
// 1px above and below), and the tooltip offset that puts it there. The box is where the
// label really renders: 4px clear of the marker, since Leaflet adds a 6px margin on the
// tooltip's side to the offset. Below is the original placement; the other sides let
// a label that collides below still find room before it is dropped.
const LABEL_AT = {
  bottom: (p, r, w, h) => [{ l: p.x - w / 2 - 3, r: p.x + w / 2 + 3, t: p.y + r + 3, bo: p.y + r + h + 5 }, [0, r - 2]],
  top: (p, r, w, h) => [{ l: p.x - w / 2 - 3, r: p.x + w / 2 + 3, t: p.y - r - h - 5, bo: p.y - r - 3 }, [0, 2 - r]],
  right: (p, r, w, h) => [{ l: p.x + r + 1, r: p.x + r + w + 7, t: p.y - h / 2 - 1, bo: p.y + h / 2 + 1 }, [r - 2, 0]],
  left: (p, r, w, h) => [{ l: p.x - r - w - 7, r: p.x - r - 1, t: p.y - h / 2 - 1, bo: p.y + h / 2 + 1 }, [2 - r, 0]],
};
// Site labels are placed greedily, largest site first, and a label is dropped when
// every side it may take would overlap one already placed — so dense areas stay readable.
// With LABEL_CLEAR_MARKERS a side must also keep off every other site's marker, so a
// label can't be read as that site's.
function updateLabels() {
  labelLayer.clearLayers();
  if (!state.labels) { if (map.hasLayer(labelLayer)) map.removeLayer(labelLayer); return; }
  if (!map.hasLayer(labelLayer)) labelLayer.addTo(map);
  const bounds = map.getBounds().pad(0.02);
  const cand = visible().filter(s => s.lat != null && bounds.contains([s.lat, s.lon]))
    .sort((a, b) => b.eligible - a.eligible)
    .map(s => ({ s, p: map.latLngToContainerPoint([s.lat, s.lon]), r: radiusOf(s) }));
  const CH = 7.0, LH = 17;               // approx char width / line height at 11.5px
  const placed = [];
  const overlaps = (a, b) => !(a.r < b.l || a.l > b.r || a.bo < b.t || a.t > b.bo);
  // whether a box reaches into a marker's circle, its 1px ring included
  const covers = (b, m) => Math.hypot(Math.max(b.l - m.p.x, 0, m.p.x - b.r),
    Math.max(b.t - m.p.y, 0, m.p.y - b.bo)) < m.r + 1;
  const clearMarkers = typeof LABEL_CLEAR_MARKERS !== 'undefined' && LABEL_CLEAR_MARKERS;
  for (const c of cand) {
    if (placed.length >= 70) break;
    const { s, p, r } = c;
    const w = Math.min(labelOf(s).length * CH, 190);
    const free = box => !placed.some(q => overlaps(box, q))
      && !(clearMarkers && cand.some(m => m !== c && covers(box, m)));
    const side = labelSides().find(d => free(LABEL_AT[d](p, r, w, LH)[0]));
    if (!side) continue;
    const [box, offset] = LABEL_AT[side](p, r, w, LH);
    placed.push(box);
    L.marker([s.lat, s.lon], {
      icon: L.divIcon({ className: 'lbl-anchor', html: '', iconSize: [0, 0] }),
      interactive: false, keyboard: false })
      .bindTooltip(esc(labelOf(s)), { permanent: true, direction: side, className: 'lbl', offset })
      .addTo(labelLayer).openTooltip();
  }
  $('#btnLabels').title = typeof labelTitle === 'function' ? labelTitle(placed.length, cand.length)
    : `${placed.length} מתוך ${cand.length} שמות מוצגים — התקרבו כדי לראות עוד`;
}
map.on('zoomend', restyleMarkers);
map.on('moveend zoomend', () => { if (state.labels) updateLabels(); });

function sizeLegend() {
  return `<div class="size-legend">${[700, 1600, 3500].map(v => {
    const r = baseRadius(v);
    return `<div class="b"><i style="width:${2 * r}px;height:${2 * r}px"></i><span>${num(v)}</span></div>`;
  }).join('')}<div class="b" style="align-self:center"><span>בעלי זכות בחירה<br>(שטח הסמן)</span></div></div>`;
}

function selectSite(id, fly) {
  state.selected = id;
  // on a phone the detail lives in the list pane, so a marker tap must switch to it
  if (id != null && isNarrow()) setView('list');
  if (id == null) { $('#detail').classList.add('hidden'); }
  else {
    const s = sites.find(x => x.id === id);
    renderDetail(s);
    if (s.lat != null) {
      if (fly) map.flyTo([s.lat, s.lon], Math.max(map.getZoom(), 16), { duration: 0.6 });
      if (!isNarrow()) markers.get(id)?.openTooltip();
    }
  }
  restyleMarkers(); renderList();
}

// ---------------------------------------------------------------- table view
const isNarrow = () => matchMedia('(max-width:1000px)').matches;

function renderTable() {
  const site = state.tableLevel === 'site';
  const allCols = site ? SITE_COLS : KALPI_COLS;
  let cols = allCols;
  if (isNarrow()) {
    // one key list for both levels, or one per level when the two need different ones
    const keys = Array.isArray(MOBILE_KEYS) ? MOBILE_KEYS : MOBILE_KEYS[state.tableLevel];
    const sub = cols.filter(c => keys.includes(c[0]));
    if (sub.length) cols = sub;
  }
  const visIds = new Set(visible().map(s => s.id));
  let rows = site ? visible() : kalpiRows.filter(k => visIds.has(k.siteId));
  const col = allCols.find(c => c[0] === state.tableSort.key) || cols[0];
  rows = [...rows].sort((a, b) => {
    const x = col[3](a), y = col[3](b);
    return (typeof x === 'string' ? x.localeCompare(y, 'he') : x - y) * state.tableSort.dir;
  });
  $('#tvCount').textContent = `${num(rows.length)} שורות (לפי הסינון הפעיל)`;
  $('#tvBody').innerHTML = `<table class="full"><thead><tr>${cols.map(c =>
    `<th data-key="${c[0]}" ${state.tableSort.key === c[0] ? `aria-sort="${state.tableSort.dir > 0 ? 'ascending' : 'descending'}"` : ''}>${c[1]}${state.tableSort.key === c[0] ? (state.tableSort.dir > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(r => `<tr>${cols.map(c => `<td>${c[2](r)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  $$('#tvBody th').forEach(th => th.addEventListener('click', () => {
    const k = th.dataset.key;
    state.tableSort = { key: k, dir: state.tableSort.key === k ? -state.tableSort.dir : 1 };
    renderTable();
  }));
}

// ---------------------------------------------------------------- wiring
function renderAll() { map.closePopup(); renderLegend(); renderList(); restyleMarkers(); syncFilterSummary(); if (!$('#tableview').classList.contains('hidden')) renderTable(); }

$('#q').addEventListener('input', e => { state.q = e.target.value; renderAll(); });
$('#btnReset').addEventListener('click', () => { selectSite(null); fitAll(); });
$('#btnLabels').addEventListener('click', e => {
  state.labels = !state.labels;
  e.currentTarget.setAttribute('aria-pressed', String(state.labels));
  e.currentTarget.classList.toggle('primary', state.labels);
  updateLabels();
});
$('#btnAbout').addEventListener('click', () => { renderAbout(); $('#about').classList.remove('hidden'); $('#btnCloseAbout').focus(); });
$('#btnCloseAbout').addEventListener('click', () => { $('#about').classList.add('hidden'); $('#btnAbout').focus(); });
$('#about').addEventListener('click', e => { if (e.target.id === 'about') $('#about').classList.add('hidden'); });
$('#btnTable').addEventListener('click', () => { $('#tableview').classList.remove('hidden'); renderTable(); });
$('#btnCloseTable').addEventListener('click', () => $('#tableview').classList.add('hidden'));
$('#tvSeg').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  state.tableLevel = b.dataset.level;
  state.tableSort = { key: 'kalpi', dir: 1 };
  $$('#tvSeg button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
  renderTable();
});
$('#btnTheme').addEventListener('click', () => {
  const cur = document.documentElement.getAttribute('data-theme') ||
    (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  const next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  $('#btnTheme').textContent = next === 'dark' ? 'מצב בהיר' : 'מצב כהה';
  setTiles(); renderAll();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    if (!$('#about').classList.contains('hidden')) $('#about').classList.add('hidden');
    else if (!$('#tableview').classList.contains('hidden')) $('#tableview').classList.add('hidden');
    else if (state.selected != null) selectSite(null);
  }
});

// ---------------------------------------------------------------- mobile shell
// Below 1000px the map and the list are separate tabs. They used to be stacked
// inside a 100vh box that could not scroll, which left the filters and the whole
// list off-screen and unreachable on any phone.
function setView(v) {
  document.body.dataset.view = v;
  map.closePopup();          // it would otherwise linger, hidden, behind the other tab
  $$('#viewTabs button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.view === v)));
  // the map was display:none, so Leaflet has to re-measure before it draws
  if (v === 'map') setTimeout(() => { map.invalidateSize(); updateLabels(); }, 0);
}
$('#viewTabs').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  setView(b.dataset.view);
});
$('#btnMenu').addEventListener('click', e => {
  const open = $('#hdrActions').classList.toggle('open');
  e.currentTarget.setAttribute('aria-expanded', String(open));
});
$('#hdrActions').addEventListener('click', () => {
  $('#hdrActions').classList.remove('open');
  $('#btnMenu').setAttribute('aria-expanded', 'false');
});
document.addEventListener('click', e => {
  if (!e.target.closest('#hdrActions') && !e.target.closest('#btnMenu')) {
    $('#hdrActions').classList.remove('open');
    $('#btnMenu').setAttribute('aria-expanded', 'false');
  }
});
$('#btnStatsMore').addEventListener('click', e => {
  const open = $('#stats').classList.toggle('expanded');
  e.currentTarget.textContent = open ? 'פחות' : 'עוד';
  e.currentTarget.setAttribute('aria-expanded', String(open));
});

function fitAll() {
  const pts = sites.filter(s => s.lat != null).map(s => [s.lat, s.lon]);
  if (pts.length) map.fitBounds(L.latLngBounds(pts), { padding: [40, 40] });
}

// The last step of every product's start-up: the view, the phone's folded filters,
// the breakpoint listener, the theme button's label, and the ready flag the tests wait on.
function startShell() {
  setView('map');
  // on a phone the filters start folded so the list gets the screen; on a desktop
  // the <details> is always open and its summary is hidden by CSS
  if (isNarrow()) $('#filters').open = false;
  // the table's column set and the filter fold depend on width, so follow resizes
  matchMedia('(max-width:1000px)').addEventListener('change', () => {
    if (!$('#tableview').classList.contains('hidden')) renderTable();
    $('#filters').open = !isNarrow();
    map.closePopup();
    for (const s of sites) { const m = markers.get(s.id); if (m) bindMarkerUI(m, s); }
    map.invalidateSize();
  });
  $('#btnTheme').textContent = matchMedia('(prefers-color-scheme: dark)').matches ? 'מצב בהיר' : 'מצב כהה';
  window.__READY__ = true;
}
