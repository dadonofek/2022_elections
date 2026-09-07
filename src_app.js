'use strict';
// ---------------------------------------------------------------- helpers
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const nf = new Intl.NumberFormat('he-IL');
const num = n => nf.format(Math.round(n));
const pct = (n, d = 1) => (n == null ? '—' : n.toFixed(d).replace(/\.0$/, '') + '%');
const share = (v, t) => (t ? (100 * v) / t : 0);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const cssVar = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

const BLOC_LABEL = {
  coalition: 'קואליציית 2022',
  opposition: 'אופוזיציה רחבה',
  other: 'רשימות אחרות',
};
const BLOC_VAR = { coalition: '--bloc-coalition', opposition: '--bloc-opposition', other: '--bloc-other' };
const blocColor = b => cssVar(BLOC_VAR[b] || '--text-muted');

// turnout ramp: one hue, light -> dark, 6 bins
const TURNOUT_BINS = [40, 48, 55, 62, 70];      // upper edges of bins 0..4
const TURNOUT_VARS = ['--seq-0', '--seq-1', '--seq-2', '--seq-3', '--seq-4', '--seq-5'];
const turnoutBin = t => TURNOUT_BINS.findIndex(e => t < e) === -1 ? 5 : TURNOUT_BINS.findIndex(e => t < e);
const turnoutColor = t => cssVar(TURNOUT_VARS[turnoutBin(t)]);

// margin (coalition - opposition, pct points): diverging, gray midpoint
const MARGIN_BINS = [-30, -15, -3, 3, 15, 30];
const MARGIN_VARS = ['--div-opp-3', '--div-opp-2', '--div-opp-1', '--div-mid', '--div-coal-1', '--div-coal-2', '--div-coal-3'];
const marginIdx = m => { let i = 0; while (i < MARGIN_BINS.length && m >= MARGIN_BINS[i]) i++; return i; };
const marginColor = m => cssVar(MARGIN_VARS[marginIdx(m)]);

// turnout delta. The baseline is the NATIONAL average, not the city's own mean:
// against the city mean half the sites sit above it by construction and nothing
// reads as low, which is exactly the thing this map exists to show. Against the
// national 70.63%, 123 of the 140 sites are below — so the scale is sequential
// (a deficit ramp), not diverging, with one neutral step for the 17 at or above.
const NAT = DATA.city.national_turnout;
const deltaNat = s => s.turnout - NAT;
const deltaCity = s => s.turnout - DATA.city.turnout;
const DELTA_BINS = [-40, -30, -20, -10, 0];    // lower edges, deepest deficit first
const DELTA_VARS = ['--dlt-4', '--dlt-3', '--dlt-2', '--dlt-1', '--dlt-0', '--dlt-none'];
const deltaIdx = d => { let i = 0; while (i < DELTA_BINS.length && d >= DELTA_BINS[i]) i++; return i; };
const deltaColor = s => cssVar(DELTA_VARS[deltaIdx(deltaNat(s))]);

// potential: eligible x (1 - turnout) x the bloc's share of the votes actually
// cast here — i.e. the non-voters at this site, attributed by how their voting
// neighbours voted. Hue says WHICH bloc, lightness says HOW MANY votes.
const POT_LABEL = {
  none: 'קולות שלא הגיעו', coalition: 'פוטנציאל קואליציה',
  opposition: 'פוטנציאל אופוזיציה', other: 'פוטנציאל רשימות אחרות',
};
const POT_SHORT = {
  none: 'כל מי שלא הצביע', coalition: 'קואליציית 2022',
  opposition: 'אופוזיציה רחבה', other: 'רשימות אחרות',
};
const POT_VARS = {
  none: ['--dlt-0', '--dlt-1', '--dlt-2', '--dlt-3', '--dlt-4'],
  coalition: ['--pot-coal-0', '--pot-coal-1', '--pot-coal-2', '--pot-coal-3', '--pot-coal-4'],
  opposition: ['--pot-opp-0', '--pot-opp-1', '--pot-opp-2', '--pot-opp-3', '--pot-opp-4'],
  other: ['--pot-oth-0', '--pot-oth-1', '--pot-oth-2', '--pot-oth-3', '--pot-oth-4'],
};
// fixed bins, never quantiles of the filtered set — a colour must not change
// meaning when the user filters. 'other' gets its own scale (site max 97, not 1532).
const POT_BINS = {
  none: [400, 800, 1200, 1600], coalition: [100, 250, 450, 700],
  opposition: [100, 250, 450, 700], other: [10, 25, 45, 70],
};
const potValue = s => (state.potTarget === 'none' ? s.non_voters : s.pot[state.potTarget]);
const potColor = s => {
  const b = POT_BINS[state.potTarget]; const v = potValue(s);
  let i = 0; while (i < b.length && v >= b[i]) i++;
  return cssVar(POT_VARS[state.potTarget][i]);
};

const colorOf = s => state.mode === 'lead' ? blocColor(s.lead)
  : state.mode === 'turnout' ? turnoutColor(s.turnout)
  : state.mode === 'delta' ? deltaColor(s)
  : state.mode === 'potential' ? potColor(s)
  : marginColor(s.margin);

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

// ---------------------------------------------------------------- state
const state = {
  mode: 'potential',
  potTarget: 'none',
  q: '',
  turnoutMin: 0,
  turnoutMax: 100,
  blocs: new Set(['coalition', 'opposition', 'other']),
  sort: 'pot_desc',
  selected: null,
  labels: false,
  tableLevel: 'site',
  tableSort: { key: 'kalpi', dir: 1 },
};
const sites = DATA.sites;
const kalpiRows = sites.flatMap(s => s.kalpiot.map(k => ({ ...k, site: s.name, address: s.address, siteId: s.id })));
const kalpiNumKey = s => (s.kalpiot ? s.kalpiot[0].kalpi : s.kalpi).split('.').map(Number).reduce((a, b) => a * 1000 + b, 0);

function visible() {
  const q = state.q.trim();
  return sites.filter(s => {
    if (!state.blocs.has(s.lead)) return false;
    if (s.turnout < state.turnoutMin || s.turnout > state.turnoutMax) return false;
    if (q) {
      const hay = s.name + ' ' + s.address + ' ' + addressOf(s) + ' ' + s.kalpiot.map(k => k.kalpi + ' ' + k.barzel).join(' ');
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}
const SORTS = {
  pot_desc: (a, b) => potValue(b) - potValue(a),
  delta_asc: (a, b) => deltaNat(a) - deltaNat(b),
  kalpi: (a, b) => kalpiNumKey(a) - kalpiNumKey(b),
  turnout_desc: (a, b) => b.turnout - a.turnout,
  turnout_asc: (a, b) => a.turnout - b.turnout,
  voters_desc: (a, b) => b.voters - a.voters,
  coal_desc: (a, b) => share(b.coalition, b.valid) - share(a.coalition, a.valid),
  opp_desc: (a, b) => share(b.opposition, b.valid) - share(a.opposition, a.valid),
};

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

function tipHtml(s) {
  return `<b>${esc(s.name)}</b>
    <div class="r"><span>${esc(addressOf(s))}</span></div>
    <div class="r"><span>הצבעה ${pct(s.turnout)}</span><span>${signed(deltaNat(s))} מהארצי</span><span>${s.n_kalpi} קלפיות</span></div>
    <div class="r"><span>${POT_LABEL[state.potTarget]}: ${num(potValue(s))}</span><span>מתוך ${num(s.eligible)} בעלי זכות</span></div>
    <div class="lead"><span class="dot" style="background:${blocColor(s.lead)}"></span>
      <span>מוביל: ${BLOC_LABEL[s.lead]} · ${pct(share(s[s.lead], s.valid))}</span></div>`;
}

// The compact card a marker tap opens on a phone. There is no hover on touch, so
// a tap used to go straight to the full site panel — which meant leaving the map
// for another tab just to see what a circle was. The card answers that in place and
// keeps the trip to the full data an explicit choice.
function cardHtml(s) {
  return `<div class="mcard">
    <b>${esc(s.name)}</b>
    <div class="ad">${esc(addressOf(s))} · ${s.n_kalpi} קלפיות</div>
    <div class="row"><span>${POT_LABEL[state.potTarget]}</span><span class="v">${num(potValue(s))}</span></div>
    <div class="row"><span>אחוז הצבעה</span><span class="v">${pct(s.turnout)}
      <span class="muted" style="font-weight:400">${signed(deltaNat(s))} מהארצי</span></span></div>
    <div class="row"><span>גוש מוביל</span><span class="v">
      <span class="dot" style="background:${blocColor(s.lead)}"></span>${BLOC_LABEL[s.lead]}</span></div>
    <button class="btn primary mcard-more" data-id="${s.id}">כל הנתונים באתר</button>
  </div>`;
}

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
    });
    m.setRadius(radiusOf(s) * (sel ? 1.25 : 1));
    if (sel) m.bringToFront();
  }
  updateLabels();
}

let labelLayer = L.layerGroup();
// Site labels are placed greedily, largest site first, and a label is dropped when
// its box would overlap one already placed — so dense areas stay readable.
function updateLabels() {
  labelLayer.clearLayers();
  if (!state.labels) { if (map.hasLayer(labelLayer)) map.removeLayer(labelLayer); return; }
  if (!map.hasLayer(labelLayer)) labelLayer.addTo(map);
  const bounds = map.getBounds().pad(0.02);
  const cand = visible().filter(s => s.lat != null && bounds.contains([s.lat, s.lon]))
    .sort((a, b) => b.eligible - a.eligible);
  const CH = 7.0, LH = 15;               // approx char width / line height at 11.5px
  const placed = [];
  const overlaps = (a, b) => !(a.r < b.l || a.l > b.r || a.bo < b.t || a.t > b.bo);
  for (const s of cand) {
    if (placed.length >= 70) break;
    const p = map.latLngToContainerPoint([s.lat, s.lon]);
    const w = Math.min(s.name.length * CH, 190);
    const y = p.y + radiusOf(s) + 1;
    const box = { l: p.x - w / 2 - 3, r: p.x + w / 2 + 3, t: y - 2, bo: y + LH + 2 };
    if (placed.some(q => overlaps(box, q))) continue;
    placed.push(box);
    L.marker([s.lat, s.lon], {
      icon: L.divIcon({ className: 'lbl-anchor', html: '', iconSize: [0, 0] }),
      interactive: false, keyboard: false })
      .bindTooltip(esc(s.name), { permanent: true, direction: 'bottom', className: 'lbl',
                                  offset: [0, radiusOf(s) - 2] })
      .addTo(labelLayer).openTooltip();
  }
  $('#btnLabels').title = `${placed.length} מתוך ${cand.length} שמות מוצגים — התקרבו כדי לראות עוד`;
}
map.on('zoomend', restyleMarkers);
map.on('moveend zoomend', () => { if (state.labels) updateLabels(); });

// ---------------------------------------------------------------- header stats
function renderStats() {
  const c = DATA.city;
  // first three ride along on mobile; the rest wait behind "עוד"
  const tiles = [
    ['קולות שלא הגיעו', num(c.non_voters)],
    ['אחוז הצבעה', pct(c.turnout)],
    ['פער מהארצי', signed(c.turnout - c.national_turnout)],
    ['אתרי הצבעה', num(c.n_sites)],
    ['קלפיות', num(c.n_kalpi)],
    ['בעלי זכות בחירה', num(c.eligible)],
    ['קולות כשרים', num(c.valid)],
  ];
  $('#stats').innerHTML = tiles.map(([k, v]) => `<div class="stat"><div class="v">${v}</div><div class="k">${k}</div></div>`).join('');
}

// ---------------------------------------------------------------- legend
function renderLegend() {
  const el = $('#legend');
  const vis = visible();
  if (state.mode === 'lead') {
    const counts = { coalition: 0, opposition: 0, other: 0 };
    vis.forEach(s => counts[s.lead]++);
    el.innerHTML = `<h3>הגוש המוביל באתר</h3>` + ['coalition', 'opposition', 'other'].map(b =>
      `<div class="legend-row"${counts[b] ? '' : ' style="opacity:.45"'}><span class="sw" style="background:${blocColor(b)}"></span><span>${BLOC_LABEL[b]}</span><span class="n">${counts[b]} אתרים</span></div>`).join('') + sizeLegend();
  } else if (state.mode === 'turnout') {
    el.innerHTML = `<h3>אחוז הצבעה באתר</h3>
      <div class="ramp">${TURNOUT_VARS.map(v => `<span style="background:${cssVar(v)}"></span>`).join('')}</div>
      <div class="ramp-labels"><span>עד ${TURNOUT_BINS[0]}%</span><span>${TURNOUT_BINS[2]}%</span><span>${TURNOUT_BINS[TURNOUT_BINS.length - 1]}%+</span></div>
      <p class="legend-note">סמן גדול ובהיר = ציבור בוחרים גדול שרבים בו לא הצביעו</p>` + sizeLegend();
  } else if (state.mode === 'delta') {
    // ramp is written darkest-first so the RIGHT-hand swatch under RTL is the
    // deepest deficit, and the labels are written in that same order
    const n = vis.filter(x => deltaNat(x) >= 0).length;
    el.innerHTML = `<h3>פער מאחוז ההצבעה הארצי</h3>
      <div class="ramp">${DELTA_VARS.map(v => `<span style="background:${cssVar(v)}"></span>`).join('')}</div>
      <div class="ramp-labels"><span>40-% ומטה</span><span>20-%</span><span>הארצי ומעלה</span></div>
      <p class="legend-note">הבסיס הוא אחוז ההצבעה הארצי בבחירות אלה (${pct(NAT)}), לא ממוצע העיר
         (${pct(DATA.city.turnout)}). ${n} מתוך ${vis.length} אתרים בתצוגה מגיעים לממוצע הארצי.</p>` + sizeLegend();
  } else if (state.mode === 'potential') {
    const b = POT_BINS[state.potTarget], vars = POT_VARS[state.potTarget];
    el.innerHTML = `<h3>${POT_LABEL[state.potTarget]}</h3>
      <div class="ramp">${vars.map(v => `<span style="background:${cssVar(v)}"></span>`).join('')}</div>
      <div class="ramp-labels"><span>עד ${num(b[0])}</span><span>${num(b[1])}</span><span>${num(b[b.length - 1])}+</span></div>
      <p class="legend-note">סמן גדול וכהה = ציבור בוחרים גדול שהרבה ממנו לא הגיע לקלפי
         (שטח = בעלי זכות, צבע = הפוטנציאל).</p>` + sizeLegend();
  } else {
    el.innerHTML = `<h3>פער בין הגושים (2022)</h3>
      <div class="ramp">${MARGIN_VARS.map(v => `<span style="background:${cssVar(v)}"></span>`).join('')}</div>
      <div class="ramp-labels"><span>אופוזיציה 30+</span><span>שוויון</span><span>קואליציה 30+</span></div>` + sizeLegend();
  }
}
function sizeLegend() {
  return `<div class="size-legend">${[700, 1600, 3500].map(v => {
    const r = baseRadius(v);
    return `<div class="b"><i style="width:${2 * r}px;height:${2 * r}px"></i><span>${num(v)}</span></div>`;
  }).join('')}<div class="b" style="align-self:center"><span>בעלי זכות בחירה<br>(שטח הסמן)</span></div></div>`;
}

// ---------------------------------------------------------------- list
function renderList() {
  const vis = visible().sort(SORTS[state.sort]);
  $('#count').textContent = `${vis.length} מתוך ${sites.length} אתרים`;
  const el = $('#list');
  if (!vis.length) { el.innerHTML = `<div class="empty">אין אתרים התואמים לסינון.</div>`; return; }
  el.innerHTML = vis.map(s => `
    <button class="site" data-id="${s.id}" aria-current="${state.selected === s.id}">
      <div class="t"><span class="dot" style="background:${colorOf(s)}"></span>
        <span class="nm">${esc(s.name)}</span>
        <span class="pill" style="margin-inline-start:auto">${s.n_kalpi} קלפיות</span></div>
      <div class="ad">${esc(addressOf(s))}</div>
      <div class="m"><span><b>${num(potValue(s))}</b> ${POT_LABEL[state.potTarget]}</span>
        <span>הצבעה ${pct(s.turnout)}</span><span>${signed(deltaNat(s))} מהארצי</span></div>
    </button>`).join('');
  $$('.site', el).forEach(b => b.addEventListener('click', () => selectSite(+b.dataset.id, true)));
}

// ---------------------------------------------------------------- detail
function blocStack(o) {
  const parts = [['coalition', o.coalition], ['opposition', o.opposition], ['other', o.other]];
  const t = o.valid || 1;
  return `<div class="stack">${parts.map(([k, v]) =>
    `<span style="width:${(100 * v / t).toFixed(2)}%;background:${blocColor(k)}" title="${BLOC_LABEL[k]}"></span>`).join('')}</div>
    <div class="stack-key">${parts.map(([k, v]) =>
      `<span class="i"><span class="dot" style="background:${blocColor(k)}"></span><span class="lbl">${BLOC_LABEL[k]}</span><span class="pc">${pct(share(v, t))}</span><span class="abs">${num(v)}</span></span>`).join('')}</div>`;
}

function renderDetail(s) {
  const d = $('#detail');
  const maxParty = Math.max(...s.top_parties.map(p => p[1]), 1);
  const geoNote = s.geo_precision === 'venue' ? `מיקום המבנה לפי OpenStreetMap${s.osm_venue ? ' (' + esc(s.osm_venue) + ')' : ''}`
    : s.geo_precision === 'house' ? 'מיקום ברמת מספר בית'
    : s.geo_precision === 'street' ? 'מיקום ברמת רחוב — הסמן על מרכז הרחוב, לא על המבנה'
    : 'מיקום מקורב';
  d.innerHTML = `
    <div class="detail-head">
      <div class="row">
        <div style="min-width:0">
          <h3>${esc(s.name)}</h3>
          <div class="ad">${esc(addressOf(s))}, חיפה · קלפיות ${s.kalpiot.map(k => esc(k.kalpi)).join(', ')}</div>
        </div>
        <button class="btn" id="closeDetail" style="margin-inline-start:auto">חזרה</button>
      </div>
      <div class="kpis">
        <div class="kpi"><div class="v">${pct(s.turnout)}</div><div class="k">אחוז הצבעה</div></div>
        <div class="kpi"><div class="v">${num(s.voters)}</div><div class="k">מצביעים</div></div>
        <div class="kpi"><div class="v">${num(s.eligible)}</div><div class="k">בעלי זכות</div></div>
        <div class="kpi"><div class="v">${num(s.non_voters)}</div><div class="k">לא הצביעו</div></div>
        <div class="kpi"><div class="v">${signed(deltaNat(s))}</div><div class="k">מהארצי ${pct(NAT)}</div></div>
        <div class="kpi"><div class="v">${signed(deltaCity(s))}</div><div class="k">מחיפה ${pct(DATA.city.turnout)}</div></div>
      </div>
      <div class="sec" style="padding:10px 0 0; border:0">
        <h4>פוטנציאל לפי גוש — הערכה</h4>
        <div class="bars">${['coalition', 'opposition', 'other'].map(b => `
          <div class="bar"><span>${BLOC_LABEL[b]}</span>
            <span class="track"><span class="fill" style="width:${(100 * s.pot[b] / Math.max(...Object.values(s.pot), 1)).toFixed(1)}%;background:${blocColor(b)}"></span></span>
            <span class="val">${num(s.pot[b])} קולות</span></div>`).join('')}</div>
        <p class="legend-note">${num(s.non_voters)} בעלי זכות לא הצביעו כאן. החלוקה לגושים מניחה
           שהם היו מצביעים כמו מי שכן הצביע באתר — הערכה, לא תחזית.</p>
      </div>
      <span class="warn">📍 ${geoNote}${s.jittered ? ' · הוזז מעט כדי להפריד סמנים חופפים' : ''}</span>
    </div>
    <div class="scroll">
      <div class="sec"><h4>חלוקה לגושים</h4>${blocStack(s)}</div>
      <div class="sec"><h4>המפלגות הגדולות באתר</h4>
        <div class="bars">${s.top_parties.map(([k, v]) => `
          <div class="bar"><span>${esc(partyName(k))}</span>
            <span class="track"><span class="fill" style="width:${(100 * v / maxParty).toFixed(1)}%;background:${cssVar('--accent')}"></span></span>
            <span class="val">${num(v)} · ${pct(share(v, s.valid))}</span></div>`).join('')}</div>
      </div>
      <details class="sec"><summary>פירוט לפי קלפי (${s.n_kalpi})</summary>
        <table class="kt"><thead><tr><th>קלפי</th><th>ברזל</th><th>בעלי זכות</th><th>מצביעים</th><th>הצבעה</th><th>גוש מוביל</th></tr></thead>
        <tbody>${s.kalpiot.map(k => `<tr>
          <td>${esc(k.kalpi)}</td><td class="muted">${k.barzel}</td><td>${num(k.eligible)}</td>
          <td>${num(k.voters)}</td><td>${pct(k.turnout)}</td>
          <td><span class="dot" style="background:${blocColor(k.lead)};display:inline-block;vertical-align:middle"></span> ${BLOC_LABEL[k.lead]}</td>
        </tr>`).join('')}</tbody></table>
      </details>
      <div class="sec"><h4>כל הקולות באתר</h4>
        <table class="kt"><tbody>${Object.entries(s.parties).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1])
          .map(([k, v]) => `<tr><td>${esc(partyName(k))} <span class="muted">(${esc(k)})</span></td><td style="text-align:end">${num(v)}</td><td style="text-align:end" class="muted">${pct(share(v, s.valid))}</td></tr>`).join('')}
          <tr><td><b>קולות פסולים</b></td><td style="text-align:end">${num(s.invalid)}</td><td></td></tr>
        </tbody></table>
      </div>
    </div>`;
  d.classList.remove('hidden');
  $('#closeDetail').addEventListener('click', () => selectSite(null));
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

// ---------------------------------------------------------------- about
function renderAbout() {
  const c = DATA.city;
  const byPrec = {}, byConf = {};
  sites.forEach(s => {
    byPrec[s.geo_precision] = (byPrec[s.geo_precision] || 0) + 1;
    byConf[s.confidence] = (byConf[s.confidence] || 0) + 1;
  });
  const PREC = { venue: 'מבנה מזוהה ב-OpenStreetMap', house: 'מספר בית מדויק',
                 street: 'מרכז הרחוב (ללא מספר בית)', place: 'נקודה מקורבת ברחוב' };
  const names = b => DATA.blocs[b].map(k => `${partyName(k)} (${k})`).join(', ');
  $('#aboutBody').innerHTML = `
    <h3>מה מוצג כאן</h3>
    <p>כל סמן הוא <b>אתר הצבעה</b> אחד בחיפה בבחירות לכנסת ה-25 (1 בנובמבר 2022).
       ב-${num(c.n_sites)} האתרים פעלו ${num(c.n_kalpi)} קלפיות; אתר שבו כמה קלפיות מוצג כסמן אחד,
       והפירוט לפי קלפי נפתח בלחיצה עליו וכן בטבלה.</p>
    <p><b>שטח</b> הסמן פרופורציוני למספר <b>בעלי זכות הבחירה</b> באתר (לא למספר המצביעים
       בפועל), ו<b>צבעו</b> נקבע לפי מצב הצביעה הנבחר. כך, במצב "אחוז הצבעה", סמן גדול
       ובהיר הוא אתר עם ציבור בוחרים גדול שרבים בו לא הגיעו לקלפי.</p>
    <h3>פוטנציאל — איך הוא מחושב ומה הוא לא</h3>
    <p>לכל אתר: <b>בעלי זכות בחירה × (1 פחות אחוז ההצבעה) × שיעור הגוש בקולות שנספרו באתר</b>.
       החלק הראשון הוא בדיוק מספר בעלי הזכות ש<b>לא</b> הצביעו שם; הכפלתו בשיעור הגוש עונה על
       השאלה "כמה קולות היה הגוש הזה מרוויח אילו מי שלא הצביע כאן היה מצביע כמו שכניו שכן הצביעו".
       בכל העיר מדובר ב-${num(c.non_voters)} בעלי זכות שלא הצביעו — כ-80% ממספר המצביעים בפועל
       (${num(c.voters)}).</p>
    <p class="muted"><b>זו הערכה, לא תחזית.</b> היא מניחה שמי שלא הצביע היה מצביע כמו מי שכן הצביע
       באותו אתר — הנחה שאין דרך לאמת אותה מהנתונים. בנוסף, מרשם בעלי זכות הבחירה (בזב) בערים גדולות
       כולל גם מי שרשומים בעיר אך אינם גרים בה בפועל, ולכן חלק מ"מי שלא הצביע" אינו בר-השגה כלל.
       המספר הוא <b>חסם עליון</b> על הקולות שניתן היה להוסיף, לא הצפי להם.</p>
    <h3>פער מהארצי — למה זה הבסיס</h3>
    <p>אחוז ההצבעה בחיפה, ${pct(c.turnout)}, נראה נמוך — אבל מול <b>ממוצע העיר עצמה</b> מחצית האתרים
       גבוהים ממנו מעצם ההגדרה, וכל צבע מתכנס לאפס. לכן הבסיס במפה הוא <b>אחוז ההצבעה הארצי</b>
       באותן בחירות, ${pct(c.national_turnout)}: מולו ${sites.filter(x => x.turnout < c.national_turnout).length}
       מתוך ${sites.length} האתרים בחיפה נמצאים מתחת לממוצע, והפער הוא הסיפור.
       הפער מממוצע העיר מוצג גם הוא, בכרטיס של כל אתר ובטבלה.</p>
    <h3>מקורות</h3>
    <ul>
      <li>תוצאות, בעלי זכות בחירה ומצביעים לכל קלפי — הקובץ הרשמי של ועדת הבחירות המרכזית
          (<code>expb.csv</code>, כנסת ה-25). כל ${num(c.n_kalpi)} השורות הושוו לקובץ המקורי ונמצאו זהות.</li>
      <li>שיוך כתובת לכל קלפי — קובץ ההתאמות <code>haifa_polling_station_matching.xlsx</code>
          המבוסס בעיקר על הודעת הבחירות הרשמית של עיריית חיפה ועל שם אתר הקלפי.</li>
      <li>קואורדינטות — גאוקודינג של ${Object.values(byPrec).reduce((a, b) => a + b, 0)} האתרים מול
          OpenStreetMap (Nominatim), ובמקרים שבהם זוהה המבנה בשמו — מיקום המבנה עצמו (Overpass).</li>
    </ul>
    <h3>דיוק המיקום</h3>
    <ul>${Object.entries(byPrec).sort((a, b) => b[1] - a[1])
      .map(([k, v]) => `<li>${PREC[k] || k}: <b>${v}</b> אתרים</li>`).join('')}</ul>
    <p class="muted">אתר שמוקם לפי מרכז הרחוב עשוי לסטות בעשרות עד מאות מטרים מהמבנה עצמו.
       רמת הדיוק של כל אתר מוצגת בכרטיס שלו. אתרים שקיבלו בדיוק את אותה נקודה הוזזו במטרים ספורים
       כדי שהסמנים לא יסתירו זה את זה.</p>
    <h3>הגדרת הגושים</h3>
    <ul>
      <li><b>קואליציית 2022</b>: ${names('coalition')}</li>
      <li><b>אופוזיציה רחבה</b>: ${names('zionist_opp')}; ${names('arab')}</li>
      <li><b>רשימות אחרות</b>: כל שאר הרשימות שקיבלו קולות בעיר.</li>
    </ul>
    <p>השיעורים מחושבים מתוך הקולות הכשרים. "פער בין הגושים" הוא שיעור קואליציית 2022 פחות שיעור האופוזיציה הרחבה.</p>
    <h3>מגבלות</h3>
    <ul>
      <li>הנתונים הם של קלפיות חיפה בלבד; מעטפות כפולות וקלפיות חיצוניות אינן נכללות,
          ולכן אחוז ההצבעה כאן (${pct(c.turnout)}) הוא של הקלפיות בעיר ולא של תושבי העיר כולם.</li>
      <li>ההתאמה בין קלפי לכתובת נשענת על מסמכי עירייה משנים סמוכות; רמת הביטחון לכל אתר:
          ${Object.entries(byConf).map(([k, v]) => `${k} — ${v}`).join(' · ')}.</li>
      <li>מיקום הסמן הוא של אתר ההצבעה, לא של מקום מגוריהם של המצביעים.</li>
    </ul>`;
}

// ---------------------------------------------------------------- table view
const SITE_COLS = [
  ['kalpi', 'קלפיות', s => s.kalpiot.map(k => k.kalpi).join(', '), s => kalpiNumKey(s)],
  ['name', 'אתר הצבעה', s => esc(s.name), s => s.name],
  ['address', 'כתובת', s => esc(addressOf(s)), s => addressOf(s)],
  ['n_kalpi', 'מס׳ קלפיות', s => s.n_kalpi, s => s.n_kalpi],
  ['eligible', 'בעלי זכות', s => num(s.eligible), s => s.eligible],
  ['voters', 'מצביעים', s => num(s.voters), s => s.voters],
  ['turnout', 'אחוז הצבעה', s => pct(s.turnout), s => s.turnout],
  ['dnat', 'פער מהארצי', s => signed(deltaNat(s)), s => deltaNat(s)],
  ['dcity', 'פער מחיפה', s => signed(deltaCity(s)), s => deltaCity(s)],
  ['nonv', 'לא הצביעו', s => num(s.non_voters), s => s.non_voters],
  ['potc', 'פוטנציאל קואליציה', s => num(s.pot.coalition), s => s.pot.coalition],
  ['poto', 'פוטנציאל אופוזיציה', s => num(s.pot.opposition), s => s.pot.opposition],
  ['valid', 'כשרים', s => num(s.valid), s => s.valid],
  ['invalid', 'פסולים', s => num(s.invalid), s => s.invalid],
  ['coal', 'קואליציית 2022', s => pct(share(s.coalition, s.valid)), s => share(s.coalition, s.valid)],
  ['opp', 'אופוזיציה רחבה', s => pct(share(s.opposition, s.valid)), s => share(s.opposition, s.valid)],
  ['oth', 'רשימות אחרות', s => pct(share(s.other, s.valid)), s => share(s.other, s.valid)],
  ['lead', 'גוש מוביל', s => `<span class="dot" style="background:${blocColor(s.lead)};display:inline-block"></span> ${BLOC_LABEL[s.lead]}`, s => s.lead],
  ['lat', 'קו רוחב', s => s.lat?.toFixed(5) ?? '—', s => s.lat ?? 0],
  ['lon', 'קו אורך', s => s.lon?.toFixed(5) ?? '—', s => s.lon ?? 0],
];
const KALPI_COLS = [
  ['kalpi', 'קלפי', k => esc(k.kalpi), k => k.kalpi.split('.').map(Number).reduce((a, b) => a * 1000 + b, 0)],
  ['barzel', 'מספר ברזל', k => k.barzel, k => k.barzel],
  ['name', 'אתר הצבעה', k => esc(k.site), k => k.site],
  ['address', 'כתובת', k => esc(addressOf(k)), k => addressOf(k)],
  ['eligible', 'בעלי זכות', k => num(k.eligible), k => k.eligible],
  ['voters', 'מצביעים', k => num(k.voters), k => k.voters],
  ['turnout', 'אחוז הצבעה', k => pct(k.turnout), k => k.turnout],
  ['dnat', 'פער מהארצי', k => signed(k.turnout - NAT), k => k.turnout - NAT],
  ['nonv', 'לא הצביעו', k => num(k.non_voters), k => k.non_voters],
  ['valid', 'כשרים', k => num(k.valid), k => k.valid],
  ['invalid', 'פסולים', k => num(k.invalid), k => k.invalid],
  ['coal', 'קואליציית 2022', k => pct(share(k.coalition, k.valid)), k => share(k.coalition, k.valid)],
  ['opp', 'אופוזיציה רחבה', k => pct(share(k.opposition, k.valid)), k => share(k.opposition, k.valid)],
  ['lead', 'גוש מוביל', k => `<span class="dot" style="background:${blocColor(k.lead)};display:inline-block"></span> ${BLOC_LABEL[k.lead]}`, k => k.lead],
];
// A 15-column nowrap table is unreadable on a phone; keep the columns that carry
// the story and let the full set come back on a wider screen.
const MOBILE_KEYS = ['name', 'turnout', 'dnat', 'nonv', 'potc', 'poto'];
const isNarrow = () => matchMedia('(max-width:1000px)').matches;

function renderTable() {
  const site = state.tableLevel === 'site';
  let cols = site ? SITE_COLS : KALPI_COLS;
  if (isNarrow()) {
    const sub = cols.filter(c => MOBILE_KEYS.includes(c[0]));
    if (sub.length) cols = sub;
  }
  const visIds = new Set(visible().map(s => s.id));
  let rows = site ? visible() : kalpiRows.filter(k => visIds.has(k.siteId));
  const allCols = site ? SITE_COLS : KALPI_COLS;
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

// The colour mode has two controls bound to the same state: the segmented control in
// the filter panel, and a compact pair of selects on the map bar that only the narrow
// layout shows. Below 1000px the panel lives on the OTHER tab, so choosing a mode cost
// three taps and you never saw the map you were painting. Every change goes through
// these setters so the two controls can never disagree.
function setMode(m) {
  state.mode = m;
  $$('#modeSeg button').forEach(x => x.setAttribute('aria-pressed', String(x.dataset.mode === m)));
  $('#mapMode').value = m;
  syncPotField();
  renderAll();
}
function setPotTarget(t) {
  state.potTarget = t;
  $('#potTarget').value = t;
  $('#mapPotTarget').value = t;
  renderAll();
}
$('#modeSeg').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  setMode(b.dataset.mode);
});
$('#mapMode').addEventListener('change', e => setMode(e.target.value));
// the bloc target only means anything in potential mode, but it also decides what
// the list sorts by, so in the panel it stays reachable whenever that sort is active.
// On the map bar it follows the mode alone — the sort control is not on that tab.
function syncPotField() {
  const on = state.mode === 'potential' || state.sort === 'pot_desc';
  $('#potTargetField').classList.toggle('hidden', !on);
  $('#mapPotTarget').classList.toggle('hidden', state.mode !== 'potential');
}
$('#potTarget').addEventListener('change', e => setPotTarget(e.target.value));
$('#mapPotTarget').addEventListener('change', e => setPotTarget(e.target.value));
$('#q').addEventListener('input', e => { state.q = e.target.value; renderAll(); });
function syncTurnoutRange(changed) {
  let lo = +$('#turnoutMin').value, hi = +$('#turnoutMax').value;
  if (lo > hi) {                    // push the other handle so they never cross
    if (changed === 'min') hi = lo, $('#turnoutMax').value = hi;
    else lo = hi, $('#turnoutMin').value = lo;
  }
  state.turnoutMin = lo; state.turnoutMax = hi;
  $('#turnoutVal').textContent = `${lo}%–${hi}%`;
  renderAll();
}
$('#turnoutMin').addEventListener('input', () => syncTurnoutRange('min'));
$('#turnoutMax').addEventListener('input', () => syncTurnoutRange('max'));
$('#sort').addEventListener('change', e => { state.sort = e.target.value; syncPotField(); renderList(); });
$('#blocChips').innerHTML = ['coalition', 'opposition', 'other'].map(b =>
  `<label class="chip" data-bloc="${b}" data-on="1"><input type="checkbox" checked>
     <span class="dot" style="background:${blocColor(b)}"></span>${BLOC_LABEL[b]}</label>`).join('');
$$('#blocChips .chip').forEach(c => c.addEventListener('change', e => {
  const b = c.dataset.bloc, on = e.target.checked;
  on ? state.blocs.add(b) : state.blocs.delete(b);
  c.dataset.on = on ? '1' : '0';
  renderAll();
}));
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
const MODE_LABEL = {
  potential: 'פוטנציאל', turnout: 'אחוז הצבעה', delta: 'פער מהארצי',
  lead: 'גוש מוביל', margin: 'פער בין הגושים',
};
// The row below already prints the count, so the folded summary says what is ACTIVE:
// the colour mode, plus a note when a filter is hiding sites.
function syncFilterSummary() {
  const n = visible().length;
  const filtered = n < sites.length;
  $('#filtSummary').textContent = MODE_LABEL[state.mode] + (filtered ? ` · מסונן (${n})` : '');
}

function fitAll() {
  const pts = sites.filter(s => s.lat != null).map(s => [s.lat, s.lon]);
  if (pts.length) map.fitBounds(L.latLngBounds(pts), { padding: [40, 40] });
}

setTiles();
renderStats();
buildMarkers();
renderLegend();
renderList();
fitAll();
syncPotField();
syncFilterSummary();
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
