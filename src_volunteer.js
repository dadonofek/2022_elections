// ================================================================ the volunteers' map
// For the election-day volunteers of one city: every polling station of the coming
// election, one marker per building, labelled with its station numbers and coloured by
// CLUSTER (אשכול) or by the observers' risk level — so volunteers who want to be
// together can find a cluster, see which of its stations sit close to each other, and
// register for them by number.
//
// A cluster is one of the list's per-place sheets ("בית שמש 1", "בית שמש 2", ...), which
// the list colours by the volunteer community that staffs it. In the data and the code it
// is still `area`; on screen it is always "אשכול", the word the coordinators use.
//
// NOTHING on this map leans to a party. No colour anywhere stands for a party or a
// bloc, and there is no potential. Where the building was a polling site in 2022, its
// turnout and three largest lists are shown as plain text in its card — background a
// volunteer asks about, not something the map paints. The shared map shell is
// src_core.js, inlined before this file; see the contract at its top.

// ---------------------------------------------------------------- risk, area
// The list's colours, most severe first. The words are the list's own; the severity
// reading beside them is how the list orders them.
const RISK_ORDER = ['red', 'orange', 'yellow', 'white', 'gray'];
const RISK_RANK = Object.fromEntries(RISK_ORDER.map((r, i) => [r, i]));
const RISK_LABEL = { red: 'אדום', orange: 'כתום', yellow: 'צהוב', white: 'לבן', gray: 'אפור' };
const RISK_PLURAL = { red: 'אדומות', orange: 'כתומות', yellow: 'צהובות', white: 'לבנות', gray: 'אפורות' };
const RISK_LEVEL = { red: 'גבוהה', orange: 'בינונית', yellow: 'נמוכה', white: 'ללא סיכון מיוחד', gray: 'ללא סיווג' };
// the levels this city has, plus '' when some building carries none the list knows
const RISKS = [...RISK_ORDER.filter(r => DATA.city.risk_kalpi[r]),
               ...(DATA.sites.some(s => !RISK_LABEL[s.risk]) ? [''] : [])];
const riskLabel = r => RISK_LABEL[r] || 'ללא סיווג';
const riskColor = r => cssVar(RISK_LABEL[r] ? `--risk-${r}` : '--area-none');
// HTML marks reference the token itself, so a theme switch repaints them for free;
// only the Leaflet paths need the resolved colour (colorOf)
const riskVar = r => `var(--risk-${RISK_LABEL[r] ? r : 'gray'})`;

const AREAS = DATA.city.areas;                                        // in name order
const AREA_IDX = Object.fromEntries(AREAS.map((a, i) => [a.key, i]));
const HAS_UNASSIGNED = sites.some(s => !s.area);
const AREA_KEYS = [...AREAS.map(a => a.key), ...(HAS_UNASSIGNED ? [''] : [])];
// three validated area hues; a fourth area, or a station on no area's list, is neutral
const areaToken = k => (AREA_IDX[k] ?? 9) < 3 ? `--area-${AREA_IDX[k]}` : '--area-none';
const areaColor = k => cssVar(areaToken(k));
const areaVar = k => `var(${areaToken(k)})`;
const areaLabel = k => k || 'ללא אשכול';
const areaDesc = k => (AREAS.find(a => a.key === k) || {}).desc || '';

const dot = (color, inline) => `<span class="dot${inline ? ' i' : ''}" style="background:${color}"></span>`;
const nSites = n => (n === 1 ? 'אתר אחד' : `${num(n)} אתרים`);
const nKalpi = n => (n === 1 ? 'קלפי אחת' : `${num(n)} קלפיות`);
const kalpiList = s => s.kalpiot.map(k => k.kalpi).join(', ');
const kalpiWord = s => (s.n_kalpi === 1 ? 'קלפי' : 'קלפיות');
// A building's station numbers, short enough to sit beside its marker: sub-stations of
// one number collapse into a range ("112.1–112.7"), the rest are listed ("121 · 125").
function compactKalpi(s) {
  const groups = new Map();
  for (const k of s.kalpiot) {
    const [whole, part] = k.kalpi.split('.');
    if (!groups.has(whole)) groups.set(whole, []);
    if (part != null) groups.get(whole).push(+part);
  }
  return [...groups].map(([whole, parts]) => {
    if (!parts.length) return whole;
    parts.sort((a, b) => a - b);
    const run = parts.every((x, i) => i === 0 || x === parts[i - 1] + 1);
    return parts.length > 2 && run ? `${whole}.${parts[0]}–${whole}.${parts[parts.length - 1]}`
      : parts.map(x => `${whole}.${x}`).join(' · ');
  }).join(' · ');
}
// the map's labels are the station numbers — the thing a volunteer registers by
const labelText = compactKalpi;
const labelTitle = (shown, total) => (shown < total
  ? `מספרי הקלפיות של ${shown} מתוך ${total} האתרים שבתצוגה — התקרבו כדי לראות עוד`
  : 'מספרי הקלפיות של כל האתרים שבתצוגה');
// a label that collides below its marker tries the other sides before it is dropped, and
// never sits on another building's marker — numbers there would read as that building's
const LABEL_SIDES = ['bottom', 'top', 'right', 'left'];
const LABEL_CLEAR_MARKERS = true;
// a building whose stations are not all one colour says so wherever its colour is named
const riskMix = s => Object.keys(s.risk_counts).length > 1
  ? RISK_ORDER.filter(r => s.risk_counts[r]).map(r => `${s.risk_counts[r]} ${riskLabel(r)}`).join(', ') : '';
const topLists = (h, n = 3) => h.top.slice(0, n).map(([p, , pc]) => `${partyName(p)} ${pct(pc)}`).join(' · ');
const h22Short = s => (s.h22 ? `הצבעה ב-2022: ${pct(s.h22.turnout)}` : 'אתר חדש');

// Navigation goes by the ADDRESS, not by the marker: a street-level marker can sit a
// few hundred metres from the building, and the address is what the volunteer's own
// map app resolves best.
const navQuery = s => `${addressOf(s)}, ${CITY}`;
const gmapsUrl = s => `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${s.name}, ${navQuery(s)}`)}`;
const wazeUrl = s => `https://waze.com/ul?q=${encodeURIComponent(navQuery(s))}&navigate=yes`;

const colorOf = s => (state.mode === 'area' ? areaColor(s.area) : riskColor(s.risk));
const modeDot = s => (state.mode === 'area' ? areaVar(s.area) : riskVar(s.risk));

// '2026-09-15' -> '15.9.2026', the way the lists themselves write dates
const LIST_DATE = (([y, m, d]) => (d ? `${+d}.${+m}.${y}` : ''))((DATA.city.list_date || '').split('-'));

// ---------------------------------------------------------------- state
const state = {
  // clusters first: the map is for choosing where to register, and together
  mode: 'area',
  q: '',
  areas: new Set(AREA_KEYS),
  risks: new Set(RISKS),
  // each cluster's buildings in station-number order, under the cluster's header
  sort: 'area',
  selected: null,
  labels: true,
  tableLevel: 'site',
  tableSort: { key: 'kalpi', dir: 1 },
};
const kalpiRows = sites.flatMap(s => s.kalpiot.map(k => ({ ...k, site: s.name, address: s.address, area: s.area, siteId: s.id })));

function visible() {
  const q = state.q.trim();
  return sites.filter(s => {
    if (!state.areas.has(s.area)) return false;
    if (!state.risks.has(s.risk)) return false;
    if (q) {
      // the streets are where each station's VOTERS live — so a volunteer can find
      // the station of their own street, or a friend's
      const hay = [s.name, s.address, s.area, s.h22?.name || '',
                   ...s.kalpiot.map(k => `${k.kalpi} ${k.barzel} ${k.streets}`)].join(' ');
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}
const SORTS = {
  risk: (a, b) => (RISK_RANK[a.risk] ?? 9) - (RISK_RANK[b.risk] ?? 9) || kalpiNumKey(a) - kalpiNumKey(b),
  kalpi: (a, b) => kalpiNumKey(a) - kalpiNumKey(b),
  area: (a, b) => areaLabel(a.area).localeCompare(areaLabel(b.area), 'he', { numeric: true }) || kalpiNumKey(a) - kalpiNumKey(b),
  eligible: (a, b) => b.eligible - a.eligible,
  name: (a, b) => a.name.localeCompare(b.name, 'he'),
};

// ---------------------------------------------------------------- map
function tipHtml(s) {
  const mix = riskMix(s);
  return `<b>${esc(s.name)}</b>
    <div class="r"><span>${esc(addressOf(s))}</span></div>
    <div class="r"><span>${kalpiWord(s)} ${esc(kalpiList(s))}</span><span>${num(s.eligible)} בעלי זכות</span></div>
    <div class="lead">${dot(areaVar(s.area))}<span>${esc(areaLabel(s.area))}</span>
      ${dot(riskVar(s.risk))}<span>${riskLabel(s.risk)}${mix ? ` (${mix})` : ''}</span></div>
    <div class="r"><span>${s.h22 ? `2022: הצבעה ${pct(s.h22.turnout)}` : 'אתר חדש — לא פעל ב-2022'}</span></div>`;
}

// the card a marker tap opens on a phone: what the building is, how risky, whose
function cardHtml(s) {
  const mix = riskMix(s);
  return `<div class="mcard">
    <b>${esc(s.name)}</b>
    <div class="ad">${esc(addressOf(s))}</div>
    <div class="row"><span>אשכול</span><span class="v">${dot(areaVar(s.area))}${esc(areaLabel(s.area))}</span></div>
    <div class="row"><span>${kalpiWord(s)}</span><span class="v wrap">${esc(compactKalpi(s))}</span></div>
    <div class="row"><span>רמת סיכון</span><span class="v">${dot(riskVar(s.risk))}${riskLabel(s.risk)}</span></div>
    ${mix ? `<div class="row"><span></span><span class="v muted" style="font-weight:400">${mix}</span></div>` : ''}
    <div class="row"><span>בעלי זכות בחירה</span><span class="v">${num(s.eligible)}</span></div>
    <div class="row"><span>הצבעה ב-2022</span><span class="v">${s.h22 ? pct(s.h22.turnout) : 'אתר חדש'}</span></div>
    <button class="btn primary mcard-more" data-id="${s.id}">כל הפרטים על האתר</button>
  </div>`;
}

// ---------------------------------------------------------------- header stats
function renderStats() {
  const c = DATA.city;
  // the first three ride along on a phone — the city and its first two clusters; the
  // rest wait behind "עוד"
  const tiles = [
    ['קלפיות', num(c.n_kalpi)],
    ...AREAS.map(a => [`קלפיות ב${a.key}`, num(a.n_kalpi)]),
    ['אתרי הצבעה', num(c.n_sites)],
    ...RISKS.map(r => [`קלפיות ${RISK_PLURAL[r]}`, num(c.risk_kalpi[r])]),
    ['בעלי זכות בחירה', num(c.eligible)],
  ];
  $('#stats').innerHTML = tiles.map(([k, v]) => `<div class="stat"><div class="v">${v}</div><div class="k">${esc(k)}</div></div>`).join('');
}

// ---------------------------------------------------------------- legend
function renderLegend() {
  const el = $('#legend');
  const vis = visible();
  // the risk level's reading fits beside its word; a cluster's part of the city goes under
  // it, and a cluster counts STATIONS — what volunteers register for
  const row = (color, label, note, n, count, under) =>
    `<div class="legend-row"${n ? '' : ' style="opacity:.45"'}><span class="sw" style="background:${color}"></span>
       <span>${esc(label)}${note ? (under ? `<br><span class="muted sub">${esc(note)}</span>`
                                          : ` <span class="muted">· ${esc(note)}</span>`) : ''}</span>
       <span class="n nowrap">${count}</span></div>`;
  if (state.mode === 'area') {
    el.innerHTML = `<h3>אשכול</h3>` +
      AREA_KEYS.map(k => {
        const n = vis.filter(s => s.area === k).reduce((a, s) => a + s.n_kalpi, 0);
        return row(areaVar(k), areaLabel(k), areaDesc(k), n, n ? nKalpi(n) : '0 קלפיות', true);
      }).join('') +
      `<p class="legend-note">ליד האתרים — מספרי הקלפיות; התקרבו כדי לראות את כולם</p>` + sizeLegend();
  } else {
    el.innerHTML = `<h3>רמת סיכון</h3>` +
      RISKS.map(r => { const n = vis.filter(s => s.risk === r).length;
                       return row(riskVar(r), riskLabel(r), RISK_LEVEL[r], n, nSites(n)); }).join('') +
      `<p class="legend-note">אתר עם כמה קלפיות — לפי הקלפי ברמה הגבוהה בו</p>` + sizeLegend();
  }
}

// ---------------------------------------------------------------- list
function renderList() {
  const vis = visible().sort(SORTS[state.sort]);
  $('#count').textContent = `${vis.length} מתוך ${sites.length} אתרים`;
  const el = $('#list');
  if (!vis.length) { el.innerHTML = `<div class="empty">אין אתרים התואמים לסינון.</div>`; return; }
  const row = s => `
    <button class="site" data-id="${s.id}" aria-current="${state.selected === s.id}">
      <div class="t"><span class="dot" style="background:${modeDot(s)}"></span>
        <span class="nm">${esc(s.name)}</span>
        <span class="pill" style="margin-inline-start:auto">${nKalpi(s.n_kalpi)}</span></div>
      <div class="ad">${esc(addressOf(s))} · ${kalpiWord(s)} ${esc(kalpiList(s))}</div>
      <div class="m"><span>${esc(areaLabel(s.area))}</span><span>${riskLabel(s.risk)}</span>
        <span>${h22Short(s)}</span></div>
    </button>`;
  // sorted by cluster, the list is a sign-up sheet: each cluster under its own header,
  // its buildings in station-number order
  if (state.sort !== 'area') { el.innerHTML = vis.map(row).join(''); }
  else {
    el.innerHTML = AREA_KEYS.map(k => {
      const g = vis.filter(s => s.area === k);
      if (!g.length) return '';
      const n = g.reduce((a, s) => a + s.n_kalpi, 0);
      return `<div class="grp">${dot(areaVar(k))}<b>${esc(areaLabel(k))}</b>
          <span class="muted">${areaDesc(k) ? `${esc(areaDesc(k))} · ` : ''}${nKalpi(n)} ב${g.length === 1 ? 'אתר אחד' : `-${num(g.length)} אתרים`}</span></div>` +
        g.map(row).join('');
    }).join('');
  }
  $$('.site', el).forEach(b => b.addEventListener('click', () => selectSite(+b.dataset.id, true)));
}

// ---------------------------------------------------------------- detail
const GEO_NOTE = {
  venue: s => `מיקום המבנה לפי OpenStreetMap${s.osm_venue ? ' (' + esc(s.osm_venue) + ')' : ''}`,
  house: () => 'מיקום ברמת מספר בית',
  street: s => 'מיקום ברמת רחוב — הסמן על הרחוב, לא על המבנה' +
    (s.geo_source === 'same-street' ? ' (לפי כתובת אחרת באותו רחוב)'
      : s.geo_source === 'overture' ? ' (אמצע הרחוב, לפי מפת הרחובות של OpenStreetMap)' : ''),
  place: () => 'מיקום מקורב',
};

function h22Section(s) {
  const h = s.h22, c = DATA.city.h22;
  if (!h) {
    return `<p class="legend-note" style="margin:0">אתר חדש: בבחירות 2022 לא פעלה קלפי בבניין הזה,
      ולכן אין לו נתונים קודמים.</p>`;
  }
  const where = h.match === 'address' ? ` — אז בשם "${esc(h.name)}"`
    : h.match === 'name' ? ` — אז בכתובת "${esc(h.address)}"` : '';
  return `<div class="kpis" style="margin-top:0">
      <div class="kpi"><div class="v">${pct(h.turnout)}</div><div class="k">אחוז הצבעה באתר</div></div>
      <div class="kpi"><div class="v">${pct(c.turnout)}</div><div class="k">${esc(IN_CITY)} כולה</div></div>
      <div class="kpi"><div class="v">${pct(c.national_turnout)}</div><div class="k">בכל הארץ</div></div>
    </div>
    <p class="h22-top"><span class="muted">הרשימות הגדולות באתר:</span> ${esc(topLists(h))}</p>
    <p class="legend-note">ב-2022 ${h.kalpiot.length === 1 ? 'פעלה' : 'פעלו'} כאן ${nKalpi(h.kalpiot.length)} (${esc(h.kalpiot.join(', '))}) עם
      ${num(h.eligible)} בעלי זכות${where}. מספרי הקלפיות וגבולותיהן השתנו מאז, ולכן אלה נתוני
      הבניין — לא של הקלפיות החדשות.</p>`;
}

function renderDetail(s) {
  const d = $('#detail');
  const geoNote = (GEO_NOTE[s.geo_precision] || GEO_NOTE.place)(s);
  const mix = riskMix(s);
  d.innerHTML = `
    <div class="detail-head">
      <div class="row">
        <div style="min-width:0">
          <h3>${esc(s.name)}</h3>
          <div class="ad">${esc(addressOf(s))}, ${esc(CITY)} · ${kalpiWord(s)} ${esc(kalpiList(s))}</div>
        </div>
        <button class="btn" id="closeDetail" style="margin-inline-start:auto">חזרה</button>
      </div>
      <div class="kpis">
        <div class="kpi"><div class="v">${dot(areaVar(s.area), true)}${esc(areaLabel(s.area))}</div>
          <div class="k">אשכול${areaDesc(s.area) ? ` · ${esc(areaDesc(s.area))}` : ''}</div></div>
        <div class="kpi"><div class="v">${dot(riskVar(s.risk), true)}${riskLabel(s.risk)}</div>
          <div class="k">${mix ? esc(mix) : 'רמת סיכון'}</div></div>
        <div class="kpi"><div class="v">${num(s.eligible)}</div><div class="k">בעלי זכות בחירה</div></div>
      </div>
      <div class="navlinks">
        <a class="btn" href="${gmapsUrl(s)}" target="_blank" rel="noopener">ניווט בגוגל מפות</a>
        <a class="btn" href="${wazeUrl(s)}" target="_blank" rel="noopener">ניווט ב-Waze</a>
      </div>
      <span class="warn">📍 ${geoNote}${s.jittered ? ' · הוזז מעט כדי להפריד סמנים חופפים' : ''}</span>
    </div>
    <div class="scroll">
      <div class="sec"><h4>הקלפיות באתר (${s.n_kalpi})</h4>
        <table class="kt"><thead><tr><th>קלפי</th><th>רמת סיכון</th><th>בעלי זכות</th><th>רחובות המצביעים</th></tr></thead>
        <tbody>${s.kalpiot.map(k => `<tr>
          <td>${esc(k.kalpi)}</td>
          <td style="white-space:nowrap">${dot(riskVar(k.risk), true)}${riskLabel(k.risk)}${k.risk_national
            ? `<div class="muted" style="font-size:11px">ברשימה הארצית: ${riskLabel(k.risk_national)}</div>` : ''}</td>
          <td>${num(k.eligible)}</td>
          <td class="streets">${esc(k.streets) || '—'}</td>
        </tr>`).join('')}</tbody></table>
      </div>
      <div class="sec"><h4>הבניין בבחירות 2022 (הכנסת ה-25)</h4>${h22Section(s)}</div>
    </div>`;
  d.classList.remove('hidden');
  $('#closeDetail').addEventListener('click', () => selectSite(null));
}

// ---------------------------------------------------------------- about
function renderAbout() {
  const c = DATA.city, h = c.h22;
  const byPrec = {};
  sites.forEach(s => { byPrec[s.geo_precision] = (byPrec[s.geo_precision] || 0) + 1; });
  const PREC = { venue: 'מבנה מזוהה ב-OpenStreetMap', house: 'מספר בית מדויק',
                 street: 'רחוב (ללא מספר בית)', place: 'נקודה מקורבת' };
  const fallback = sites.filter(s => s.geo_source === 'overture' || s.geo_source === 'same-street').length;
  const date = LIST_DATE || 'תאריך לא ידוע';
  $('#aboutBody').innerHTML = `
    <h3>מה מוצג כאן</h3>
    <p>כל סמן הוא <b>אתר הצבעה</b> אחד ${esc(IN_CITY)} — בניין שבו יפעלו קלפי אחת או יותר
       ב${esc(c.election || 'בחירות הקרובות')}, לפי רשימת הקלפיות המעודכנת ל-${esc(date)}.
       ב-${num(c.n_sites)} האתרים יפעלו ${num(c.n_kalpi)} קלפיות; הפירוט לפי קלפי נפתח בלחיצה
       על אתר, וגם בטבלה.</p>
    <p>ליד כל סמן מופיעים <b>מספרי הקלפיות</b> שבו. <b>שטח</b> הסמן פרופורציוני למספר <b>בעלי זכות
       הבחירה</b> באתר, ו<b>צבעו</b> מציין את האשכול או את רמת הסיכון — לפי הבחירה בלוח הצביעה.</p>
    <p><b>המפה אינה מזוהה עם אף מפלגה.</b> אף צבע בה אינו מייצג מפלגה או מחנה פוליטי, ואין בה
       חישוב שמכוון לצד כלשהו.</p>
    <h3>רמת הסיכון</h3>
    <p>הצבע של כל קלפי לקוח מסיווג הקלפיות שברשימה — אדום, כתום או צהוב — שנקבע לפי סימנים
       מבחירות קודמות, כמו אחוזי הצבעה חריגים. ${esc(IN_CITY)}:
       ${RISKS.map(r => `${num(c.risk_kalpi[r])} קלפיות ${RISK_PLURAL[r]}`).join(', ')}.
       אתר שיש בו כמה קלפיות צבוע לפי הקלפי ברמת הסיכון הגבוהה ביותר בו, וכל הקלפיות שלו
       מפורטות בכרטיס שלו.</p>
    ${c.risk_differs.length ? `<p class="muted">ב-${c.risk_differs.length} קלפיות
       (${esc(c.risk_differs.join(', '))}) הצבע ברשימת האשכול שונה מהצבע ברשימה הארצית. המפה
       משתמשת ברשימת האשכול, שהיא רשימת העבודה, והצבע הארצי מופיע לצידו בכרטיס האתר.</p>` : ''}
    <h3>האשכולות</h3>
    <p>האשכולות הם החלוקה של רשימת הקלפיות לגיליונות — כל אשכול גיליון משלו, בצבע משלו —
       וכל קלפי שייכת לאשכול אחד. מתנדבים שרוצים להיות יחד נרשמים לאותו אשכול ובוחרים בו
       קלפיות סמוכות; מספרי הקלפיות מופיעים על המפה ליד כל אתר, וברשימה — אשכול אחר אשכול.</p>
    <ul>${AREAS.map(a => `<li><b>${esc(a.key)}</b>${a.desc ? ` — ${esc(a.desc)}` : ''}:
      ${nKalpi(a.n_kalpi)} ב${a.n_sites === 1 ? 'אתר אחד' : `-${num(a.n_sites)} אתרים`}</li>`).join('')}
      ${HAS_UNASSIGNED ? `<li><b>ללא אשכול</b>: ${nKalpi(c.unassigned.n_kalpi)} שאינן ברשימה של אף אשכול</li>` : ''}</ul>
    ${c.empty_areas.length ? `<p class="muted">${c.empty_areas.map(a => `"${esc(a.key)}"${a.desc ? ` (${esc(a.desc)})` : ''}`).join(', ')}
       ${c.empty_areas.length === 1 ? 'מופיע' : 'מופיעים'} ברשימה, אך עדיין לא שויכו ${c.empty_areas.length === 1 ? 'אליו' : 'אליהם'} קלפיות.</p>` : ''}
    <h3>נתוני 2022 — רקע בלבד</h3>
    <p>לכל אתר שפעל גם בבחירות לכנסת ה-25 (נובמבר 2022) מוצגים, כטקסט בלבד, אחוז ההצבעה ושלוש
       הרשימות הגדולות באותו בניין. ${num(h.sites_matched)} מתוך ${num(c.n_sites)} האתרים זוהו
       כאותו בניין — לפי הכתובת, או לפי שם המקום בכתובת סמוכה — ו-${num(c.n_sites - h.sites_matched)}
       הם אתרים חדשים.</p>
    <p class="muted">מספרי הקלפיות וגבולותיהן השתנו מאז (ב-2022 פעלו ${esc(IN_CITY)} ${num(h.n_kalpi)} קלפיות
       ב-${num(h.n_sites)} אתרים), ולכן אלה נתוני הבניין ולא של הקלפיות החדשות. אחוז ההצבעה
       ${esc(IN_CITY)} ב-2022 היה ${pct(h.turnout)}, ובכל הארץ ${pct(h.national_turnout)}.</p>
    <h3>מקורות</h3>
    <ul>
      <li>הקלפיות, האשכולות ורמת הסיכון — רשימת הקלפיות המעודכנת ל-${esc(date)}.</li>
      <li>נתוני 2022 — הקובץ הרשמי של ועדת הבחירות המרכזית (<code>expb.csv</code>, כנסת ה-25)
          וקובץ מקומות הקלפי שלה.</li>
      <li>קואורדינטות — OpenStreetMap: גאוקודינג של הכתובות (Nominatim), מבנים שזוהו בשמם (Overpass),
          ולכתובות החדשות — רשת הרחובות של OpenStreetMap, דרך Overture Maps.</li>
    </ul>
    <h3>דיוק המיקום</h3>
    <ul>${Object.entries(byPrec).sort((a, b) => b[1] - a[1])
      .map(([k, v]) => `<li>${PREC[k] || k}: <b>${v}</b> אתרים</li>`).join('')}</ul>
    <p class="muted">סמן שמוקם לפי הרחוב עשוי לסטות בעשרות עד מאות מטרים מהבניין עצמו${fallback
       ? `; ${num(fallback)} כתובות חדשות מוקמו ברמת הרחוב בלבד — באמצע הרחוב, או לפי כתובת אחרת
       באותו רחוב` : ''}. הכתובת המלאה מופיעה בכרטיס של כל אתר, עם קישור לניווט לפיה.</p>
    <h3>מגבלות</h3>
    <ul>
      <li>הרשימה עשויה להשתנות עד יום הבחירות; המפה משקפת את הרשימה מ-${esc(date)}.</li>
      <li>מיקום הסמן הוא של אתר ההצבעה, לא של מקום מגוריהם של המצביעים.</li>
    </ul>`;
}

// ---------------------------------------------------------------- table view
const riskCell = r => `${dot(riskVar(r), true)}${riskLabel(r)}`;
const SITE_COLS = [
  ['kalpi', 'קלפיות', s => esc(kalpiList(s)), s => kalpiNumKey(s)],
  ['name', 'אתר הצבעה', s => esc(s.name), s => s.name],
  ['address', 'כתובת', s => esc(addressOf(s)), s => addressOf(s)],
  ['area', 'אשכול', s => esc(areaLabel(s.area)), s => areaLabel(s.area)],
  ['risk', 'רמת סיכון', s => riskCell(s.risk), s => RISK_RANK[s.risk] ?? 9],
  ['n_kalpi', 'מס׳ קלפיות', s => s.n_kalpi, s => s.n_kalpi],
  ['eligible', 'בעלי זכות', s => num(s.eligible), s => s.eligible],
  ['t22', 'הצבעה ב-2022', s => (s.h22 ? pct(s.h22.turnout) : 'אתר חדש'), s => (s.h22 ? s.h22.turnout : -1)],
  ['top22', 'הרשימות הגדולות ב-2022', s => (s.h22 ? esc(topLists(s.h22)) : '—'), s => (s.h22 ? topLists(s.h22) : '')],
  ['lat', 'קו רוחב', s => s.lat?.toFixed(5) ?? '—', s => s.lat ?? 0],
  ['lon', 'קו אורך', s => s.lon?.toFixed(5) ?? '—', s => s.lon ?? 0],
];
const KALPI_COLS = [
  ['kalpi', 'קלפי', k => esc(k.kalpi), k => kalpiNumKey(k)],
  ['barzel', 'מספר ברזל', k => k.barzel, k => k.barzel],
  ['name', 'אתר הצבעה', k => esc(k.site), k => k.site],
  ['address', 'כתובת', k => esc(addressOf(k)), k => addressOf(k)],
  ['area', 'אשכול', k => esc(areaLabel(k.area)), k => areaLabel(k.area)],
  ['risk', 'רמת סיכון', k => riskCell(k.risk), k => RISK_RANK[k.risk] ?? 9],
  ['eligible', 'בעלי זכות', k => num(k.eligible), k => k.eligible],
  ['streets', 'רחובות המצביעים', k => esc(k.streets), k => k.streets],
];
// six columns is the phone's ceiling, and the two levels need different six
const MOBILE_KEYS = {
  site: ['name', 'risk', 'area', 'n_kalpi', 'eligible', 't22'],
  kalpi: ['kalpi', 'name', 'risk', 'area', 'eligible'],
};

// ---------------------------------------------------------------- wiring
// the panel's segmented control and the phone's map-bar select are one state
function setMode(m) {
  state.mode = m;
  $$('#modeSeg button').forEach(x => x.setAttribute('aria-pressed', String(x.dataset.mode === m)));
  $('#mapMode').value = m;
  renderAll();
}
$('#modeSeg').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  setMode(b.dataset.mode);
});
$('#mapMode').addEventListener('change', e => setMode(e.target.value));
$('#sort').addEventListener('change', e => { state.sort = e.target.value; renderList(); });

function chips(el, items, set) {
  el.innerHTML = items.map(([key, label, color]) =>
    `<label class="chip" data-key="${esc(key)}" data-on="1"><input type="checkbox" checked>
       <span class="dot" style="background:${color}"></span>${esc(label)}</label>`).join('');
  $$('.chip', el).forEach(c => c.addEventListener('change', e => {
    const k = c.dataset.key, on = e.target.checked;
    on ? set.add(k) : set.delete(k);
    c.dataset.on = on ? '1' : '0';
    renderAll();
  }));
}
chips($('#areaChips'), AREA_KEYS.map(k => [k, areaLabel(k), areaVar(k)]), state.areas);
chips($('#riskChips'), RISKS.map(r => [r, riskLabel(r), riskVar(r)]), state.risks);

const MODE_LABEL = { risk: 'רמת סיכון', area: 'אשכול' };
// The row below already prints the count, so the folded summary says what is ACTIVE:
// the colour mode, plus a note when a filter is hiding sites.
function syncFilterSummary() {
  const n = visible().length;
  const filtered = n < sites.length;
  $('#filtSummary').textContent = MODE_LABEL[state.mode] + (filtered ? ` · מסונן (${n})` : '');
}

setTiles();
renderStats();
buildMarkers();
renderLegend();
renderList();
fitAll();
syncFilterSummary();
startShell();
