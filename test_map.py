"""Render the map headlessly and check for errors, layout overflow and legibility.

Scenario list covers every interactive feature; the phone scenarios assert that
controls are actually REACHABLE, not merely present in the DOM. The old suite
checked `listItems == 140`, which counts DOM nodes — it passed while the list
rendered at zero height, off the bottom of every phone screen.
"""
import sys, os, json, pathlib, config
from playwright.sync_api import sync_playwright

# Normally Playwright finds its own browser. Set PLAYWRIGHT_CHROMIUM_PATH when the
# available Chromium build does not match the installed Playwright (e.g. a
# preinstalled browser in a container), to point the launcher at it directly.
_EXE = os.environ.get('PLAYWRIGHT_CHROMIUM_PATH')
_LAUNCH = {'executable_path': _EXE} if _EXE else {}

URL = 'file://' + str(pathlib.Path(config.OUT_HTML).resolve())
SHOTS = pathlib.Path('build'); SHOTS.mkdir(exist_ok=True)

CHECKS_JS = '''() => {
  const r = {};
  const q = s => document.querySelector(s);
  const box = s => { const e = q(s); return e ? e.getBoundingClientRect() : null; };
  const shown = e => !!(e && e.offsetParent !== null);

  r.markers = document.querySelectorAll('path.site-marker').length;
  r.listItems = document.querySelectorAll('.site').length;
  r.count = q('#count')?.textContent;
  r.tiles = document.querySelectorAll('.leaflet-tile-loaded').length;
  r.hOverflow = document.documentElement.scrollWidth - document.documentElement.clientWidth;
  r.mode = document.querySelector('#modeSeg button[aria-pressed="true"]')?.dataset.mode;
  r.mapMode = q('#mapMode')?.value;          // the map-bar copy must agree with the segment
  r.mapPotShown = shown(q('#mapPotTarget'));
  r.sort = q('#sort')?.value;
  r.potTarget = q('#potTarget')?.value;
  r.view = document.body.dataset.view;
  r.legendTitle = q('#legend h3')?.textContent || '';
  // Ramp swatches and their labels must run in the same direction. The first DOM
  // swatch paints on the RIGHT under RTL, and every ramp is authored lightest/
  // lowest first, so the first label must be the low end ("עד ...").
  const rampLabels = [...document.querySelectorAll('#legend .ramp-labels span')].map(e => e.textContent.trim());
  r.rampFirstLabel = rampLabels[0] || '';
  const sw0 = q('#legend .ramp span');
  r.rampSwatch0 = sw0 ? getComputedStyle(sw0).backgroundColor : '';
  // marker AREA carries the electorate in every mode; only the colour follows the mode
  const szs = [...document.querySelectorAll('#legend .size-legend .b span')].map(e => e.textContent.trim());
  r.sizeFirst = szs[0] || '';
  r.sizeIsEligible = /בעלי זכות/.test(szs[szs.length - 1] || '');
  r.radiusModeIndependent = (() => {
    const s0 = sites[0], keep = state.mode, r0 = radiusOf(s0);
    const same = ['potential', 'turnout', 'lead', 'delta', 'margin']
      .every(m => { state.mode = m; return Math.abs(radiusOf(s0) - r0) < 1e-9; });
    state.mode = keep;
    return same;
  })();
  r.statTiles = [...document.querySelectorAll('.stat')].filter(shown).length;
  r.tableCols = document.querySelectorAll('#tvBody thead th').length;
  r.tableRows = document.querySelectorAll('#tvBody tbody tr').length;
  r.menuOpen = q('#hdrActions')?.classList.contains('open');
  r.popupOpen = !!q('.leaflet-popup');
  r.cardMoreBtn = !!q('.mcard-more');
  r.detailOpen = !!(q('.detail') && !q('.detail').classList.contains('hidden'));
  r.tooltipBound = !!q('.leaflet-tooltip.tip');
  r.cardTitleClearsClose = (() => {
    const el = q('.mcard b'), c = q('.leaflet-popup-close-button');
    if (!el || !c) return null;
    const rng = document.createRange(); rng.selectNodeContents(el);
    const t = rng.getBoundingClientRect(), cb = c.getBoundingClientRect();
    return !(t.right > cb.left && t.left < cb.right && t.bottom > cb.top && t.top < cb.bottom);
  })();

  const bad = [];
  document.querySelectorAll('.stat,.legendbox,.mapbar,.kpi,.chip,.seg button,.viewtabs button').forEach(e => {
    if (shown(e) && e.scrollWidth > e.clientWidth + 2) bad.push(e.className + ' :: ' + e.textContent.trim().slice(0, 30));
  });
  r.clipped = bad;

  const inside = (a, b, pad = 2) =>
    a.left >= b.left - pad && a.right <= b.right + pad && a.top >= b.top - pad && a.bottom <= b.bottom + pad;
  const mapR = box('.mapwrap'), sideR = box('.sidebar');
  const mapShown = shown(q('.mapwrap'));
  r.escaped = [];
  if (mapShown) for (const sel of ['.legendbox', '.mapbar']) {
    const e = q(sel);
    if (shown(e) && !inside(e.getBoundingClientRect(), mapR)) r.escaped.push(sel);
  }
  const det = q('.detail');
  if (det && !det.classList.contains('hidden') && !inside(det.getBoundingClientRect(), sideR)) r.escaped.push('.detail');

  const tv = q('.tableview');
  if (!tv.classList.contains('hidden') && mapShown) {
    const el = document.elementFromPoint(mapR.left + mapR.width / 2, mapR.top + mapR.height / 2);
    r.coveredByTable = !!(el && el.closest('.tableview'));
  }
  if (mapShown) {
    const lb = box('.legendbox'), attr = box('.leaflet-control-attribution');
    r.legendOverlapsAttribution = !!(attr && lb.right > attr.left && lb.bottom > attr.top && lb.left < attr.right && lb.top < attr.bottom);
  } else r.legendOverlapsAttribution = false;

  // --- RTL: under direction:rtl the sidebar must sit to the RIGHT of the map ---
  r.sidebarRightOfMap = mapShown && sideR ? sideR.left >= mapR.right - 2 : null;

  // --- reachability: a control is usable only if it is on screen with real size ---
  const usable = sel => { const b = box(sel); const e = q(sel);
    return !!(b && shown(e) && b.height > 0 && b.width > 0 && b.top >= 0 && b.bottom <= innerHeight + 1); };
  r.listH = q('#list')?.clientHeight ?? 0;
  r.listOnScreen = (() => { const b = box('#list'); return !!(b && b.height > 0 && b.top < innerHeight); })();
  r.searchUsable = usable('#q');
  r.sortUsable = usable('#sort');
  r.modeSegUsable = usable('#modeSeg');
  r.mapModeUsable = usable('#mapMode');
  r.mapH = mapShown ? Math.round(mapR.height) : 0;
  r.headerH = Math.round(box('header').height);
  r.filtersOpen = q('#filters')?.open;
  return r;
}'''


def run(theme, actions=(), name='light', width=1600, height=1000, mobile=False):
    errs, fails = [], []
    with sync_playwright() as p:
        b = p.chromium.launch(**_LAUNCH)
        ctx = b.new_context(viewport={'width': width, 'height': height},
                            color_scheme=theme, device_scale_factor=2,
                            is_mobile=mobile, has_touch=mobile)
        pg = ctx.new_page()
        pg.on('console', lambda m: errs.append(f'{m.type}: {m.text}') if m.type == 'error' else None)
        pg.on('pageerror', lambda e: errs.append(f'pageerror: {e}'))
        pg.on('requestfailed', lambda r: fails.append(r.url))
        pg.goto(URL, wait_until='load')
        pg.wait_for_function('window.__READY__ === true', timeout=20000)
        pg.wait_for_timeout(3000)  # tiles
        for fn in actions: fn(pg)
        pg.wait_for_timeout(900)
        pg.screenshot(path=str(SHOTS / f'{name}.png'), full_page=False)
        checks = pg.evaluate(CHECKS_JS)
        ctx.close(); b.close()
    return checks, errs, fails


def click(sel):   return lambda pg: pg.click(sel)
def do(js):       return lambda pg: pg.evaluate(js)
def mode(m):      return click(f'#modeSeg button[data-mode="{m}"]')
def pot(t):       return do(f"const s=document.querySelector('#potTarget');s.value='{t}';s.dispatchEvent(new Event('change'))")
def view(v):      return click(f'#viewTabs button[data-view="{v}"]')
def mapMode(m):   return do(f"const s=document.querySelector('#mapMode');s.value='{m}';s.dispatchEvent(new Event('change'))")
def tapMarker():  return lambda pg: pg.locator('path.site-marker').nth(60).click(force=True)
def tapCardMore(): return click('.mcard-more')

PHONE = dict(width=390, height=844, mobile=True)

# name -> (theme, actions, dims, expectations)
scenarios = {
  # the map-bar mode control is for the stacked layout only; beside the panel it is noise
  'light':      ('light', (), {}, {'sidebarRightOfMap': True, 'mode': 'potential', 'sort': 'pot_desc',
                                   'mapModeUsable': False, 'sizeFirst': '700', 'sizeIsEligible': True}),
  'dark':       ('dark', (), {}, {}),
  'turnout':    ('light', (mode('turnout'),), {}, {'rampFirstLabel': 'עד 40%'}),
  'margin':     ('light', (mode('margin'),), {}, {}),
  'lead':       ('light', (mode('lead'),), {}, {}),
  'delta':      ('light', (mode('delta'),), {}, {'mode': 'delta'}),
  # potential sizes by the electorate like every other mode — colour carries the metric
  'potential':  ('light', (mode('potential'),), {}, {'mode': 'potential', 'rampFirstLabel': 'עד 400',
                                                     'sizeFirst': '700', 'sizeIsEligible': True}),
  'pot_coal':   ('light', (mode('potential'), pot('coalition')), {}, {'potTarget': 'coalition', 'rampFirstLabel': 'עד 100'}),
  'pot_opp':    ('light', (mode('potential'), pot('opposition')), {}, {'potTarget': 'opposition'}),
  'pot_other':  ('light', (mode('potential'), pot('other')), {}, {'potTarget': 'other',
                                                                  'sizeFirst': '700', 'sizeIsEligible': True}),
  'delta_dark': ('dark', (mode('delta'),), {}, {}),
  'pot_dark':   ('dark', (mode('potential'), pot('opposition')), {}, {}),
  'detail':     ('light', (do("document.querySelectorAll('.site')[3].click()"),), {}, {}),
  'labels':     ('light', (click('#btnLabels'), do("map.setZoom(15)")), {}, {}),
  'table':      ('light', (click('#btnTable'),), {}, {'coveredByTable': True}),
  'sort_delta': ('light', (do("const s=document.querySelector('#sort');s.value='delta_asc';s.dispatchEvent(new Event('change'))"),), {}, {'sort': 'delta_asc'}),
  'filter':     ('light', (do("for(const [id,v] of [['#turnoutMin',55],['#turnoutMax',70]]){const e=document.querySelector(id);e.value=v;e.dispatchEvent(new Event('input'))}"),), {}, {}),
  'search':     ('light', (do("const q=document.querySelector('#q');q.value='הרצל';q.dispatchEvent(new Event('input'))"),), {}, {}),
  'narrow':     ('light', (), dict(width=900, height=1100), {}),

  # ---- phone scenarios: every one asserts REACHABILITY, not DOM presence ----
  # on a phone the segmented control is on the other tab, so the map carries its own
  'phone_map':   ('light', (), PHONE, {'view': 'map', 'modeSegUsable': False,
                                       'mapModeUsable': True, 'mapMode': 'potential', 'mapPotShown': True}),
  # changing the mode from the map must not leave the map, and must move both controls
  'phone_mapmode': ('light', (mapMode('turnout'),), PHONE,
                  {'view': 'map', 'mode': 'turnout', 'mapMode': 'turnout', 'mapPotShown': False,
                   'legendTitle': 'אחוז הצבעה באתר', 'mapModeUsable': True}),
  # ...and the panel's own control still drives the map-bar copy
  'phone_mapmode_sync': ('light', (view('list'), click('#filters > summary'), mode('lead'), view('map')), PHONE,
                  {'view': 'map', 'mapMode': 'lead', 'mapPotShown': False}),
  'phone_list':  ('light', (view('list'),), PHONE,
                  {'view': 'list', 'listOnScreen': True, 'sortUsable': True}),
  'phone_filt':  ('light', (view('list'), click('#filters > summary')), PHONE,
                  {'searchUsable': True, 'filtersOpen': True}),
  'phone_menu':  ('light', (click('#btnMenu'),), PHONE, {'menuOpen': True}),
  'phone_stats': ('light', (click('#btnStatsMore'),), PHONE, {'statTiles': 7}),
  'phone_table': ('light', (click('#btnMenu'), click('#btnTable')), PHONE, {'tableCols': 6}),
  'phone_detail':('light', (view('map'), do("document.querySelectorAll('.site')[2].click()")), PHONE,
                  {'view': 'list'}),
  # tapping a circle must NOT leave the map — it opens a card in place
  'phone_tap':   ('light', (tapMarker(),), PHONE,
                  {'view': 'map', 'popupOpen': True, 'cardMoreBtn': True, 'detailOpen': False,
                   'cardTitleClearsClose': True}),
  # ...and the full panel is reached only by the explicit button on that card
  'phone_card_more': ('light', (tapMarker(), tapCardMore()), PHONE,
                  {'view': 'list', 'detailOpen': True, 'popupOpen': False}),
  # a pointer layout keeps the hover tooltip and the direct click-to-panel
  'desktop_tap': ('light', (tapMarker(),), {},
                  {'detailOpen': True, 'popupOpen': False}),
  'phone_dark':  ('dark', (view('list'),), PHONE, {'listOnScreen': True}),
}

if __name__ == "__main__":
    scen = sys.argv[1] if len(sys.argv) > 1 else 'all'
    names = list(scenarios) if scen == 'all' else [scen]
    bad = 0
    for n in names:
        theme, acts, dims, expect = scenarios[n]
        c, errs, fails = run(theme, acts, n, **dims)
        problems = []
        # Basemap tiles need the network. When they cannot be reached at all, that is
        # the environment, not the page — report it once and skip the tile assertions
        # so the suite still runs offline.
        offline = any('tile.openstreetmap.org' in u for u in fails)
        errs = [e for e in errs if 'Failed to load resource' not in e]
        if errs: problems.append(f'JS ERRORS: {errs[:3]}')
        if c['hOverflow'] > 0: problems.append(f"horizontal overflow {c['hOverflow']}px")
        if c['clipped']: problems.append(f"clipped: {c['clipped'][:3]}")
        if c['legendOverlapsAttribution']: problems.append('legend overlaps attribution')
        if c.get('escaped'): problems.append(f"overlay escaped its container: {c['escaped']}")
        if c.get('coveredByTable') is False: problems.append('table view does not cover the map')
        if c.get('radiusModeIndependent') is False:
            problems.append('marker radius changes with the colour mode')
        if 'table' not in n and c['markers'] == 0 and c['view'] != 'list':
            problems.append('no markers rendered')
        if c['tiles'] == 0 and c['view'] != 'list' and not offline:
            problems.append('no tiles loaded')
        # the list must be genuinely on screen wherever it is the active pane
        if c['view'] == 'list' and not c['listOnScreen']:
            problems.append(f"site list not on screen (height {c['listH']})")
        for k, want in expect.items():
            if c.get(k) != want:
                problems.append(f'{k}: expected {want!r}, got {c.get(k)!r}')
        bad += len(problems)
        print(f"[{'FAIL' if problems else ' ok '}] {n:13s}{'*' if offline else ' '} markers={c['markers']:3d} list={c['listItems']:3d} "
              f"listH={c['listH']:4d} mapH={c['mapH']:4d} hdr={c['headerH']:3d} {c['count'] or ''}")
        for p_ in problems: print('        -', p_)
    print('\nproblems:', bad)
    print('* = basemap tiles unreachable (offline); tile checks skipped for that row')
