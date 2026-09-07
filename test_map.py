"""Render the map headlessly and check for errors, layout overflow and legibility."""
import sys, json, pathlib, config
from playwright.sync_api import sync_playwright

URL = 'file://' + str(pathlib.Path(config.OUT_HTML).resolve())
SHOTS = pathlib.Path('build'); SHOTS.mkdir(exist_ok=True)

def run(theme, actions=(), name='light', width=1600, height=1000):
    errs, fails = [], []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': width, 'height': height},
                            color_scheme=theme, device_scale_factor=2)
        pg = ctx.new_page()
        pg.on('console', lambda m: errs.append(f'{m.type}: {m.text}') if m.type == 'error' else None)
        pg.on('pageerror', lambda e: errs.append(f'pageerror: {e}'))
        pg.on('requestfailed', lambda r: fails.append(r.url))
        pg.goto(URL, wait_until='load')
        pg.wait_for_function('window.__READY__ === true', timeout=15000)
        pg.wait_for_timeout(3500)  # tiles
        for fn in actions: fn(pg)
        pg.wait_for_timeout(900)
        pg.screenshot(path=str(SHOTS / f'{name}.png'), full_page=False)
        checks = pg.evaluate('''() => {
          const r = {};
          r.markers = document.querySelectorAll('path.site-marker').length;
          r.listItems = document.querySelectorAll('.site').length;
          r.count = document.querySelector('#count')?.textContent;
          r.tiles = document.querySelectorAll('.leaflet-tile-loaded').length;
          r.hOverflow = document.documentElement.scrollWidth - document.documentElement.clientWidth;
          r.vOverflow = document.body.scrollHeight - window.innerHeight;
          const bad = [];
          document.querySelectorAll('.stat,.legendbox,.mapbar,.kpi,.chip,.seg button').forEach(e=>{
            if (e.scrollWidth > e.clientWidth + 2) bad.push(e.className + ' :: ' + e.textContent.trim().slice(0,30));
          });
          r.clipped = bad;
          // overlays must stay inside the map; the detail panel inside the sidebar
          const inside = (a, b, pad = 2) =>
            a.left >= b.left - pad && a.right <= b.right + pad &&
            a.top >= b.top - pad && a.bottom <= b.bottom + pad;
          const mapR = document.querySelector('.mapwrap').getBoundingClientRect();
          const sideR = document.querySelector('.sidebar').getBoundingClientRect();
          r.escaped = [];
          for (const sel of ['.legendbox', '.mapbar']) {
            const e = document.querySelector(sel);
            if (e && e.offsetParent && !inside(e.getBoundingClientRect(), mapR)) r.escaped.push(sel);
          }
          const det = document.querySelector('.detail');
          if (det && !det.classList.contains('hidden') && !inside(det.getBoundingClientRect(), sideR)) r.escaped.push('.detail');
          // whatever is painted over the map centre must belong to an open overlay
          const tv = document.querySelector('.tableview');
          if (!tv.classList.contains('hidden')) {
            const el = document.elementFromPoint(mapR.left + mapR.width / 2, mapR.top + mapR.height / 2);
            r.coveredByTable = !!(el && el.closest('.tableview'));
          }
          const lb = document.querySelector('.legendbox').getBoundingClientRect();
          const attr = document.querySelector('.leaflet-control-attribution')?.getBoundingClientRect();
          r.legendOverlapsAttribution = !!(attr && lb.right > attr.left && lb.bottom > attr.top && lb.left < attr.right && lb.top < attr.bottom);
          return r;
        }''')
        ctx.close(); b.close()
    return checks, errs, fails

scen = sys.argv[1] if len(sys.argv) > 1 else 'all'
def click(sel):
    return lambda pg: pg.click(sel)
def do(js):
    return lambda pg: pg.evaluate(js)

scenarios = {
  'light':   ('light', ()),
  'dark':    ('dark', ()),
  'turnout': ('light', (click('#modeSeg button[data-mode="turnout"]'),)),
  'margin':  ('light', (click('#modeSeg button[data-mode="margin"]'),)),
  'detail':  ('light', (do("document.querySelectorAll('.site')[3].click()"),)),
  'labels':  ('light', (click('#btnLabels'), do("map.setZoom(15)"))),
  'table':   ('light', (click('#btnTable'),)),
  'filter':  ('light', (do("document.querySelector('#turnoutMin').value=60;document.querySelector('#turnoutMin').dispatchEvent(new Event('input'))"),)),
  'search':  ('light', (do("const q=document.querySelector('#q');q.value='הרצל';q.dispatchEvent(new Event('input'))"),)),
  'narrow':  ('light', (), 900, 1100),
}
if __name__ == "__main__":
    names = list(scenarios) if scen == 'all' else [scen]
    bad = 0
    for n in names:
        theme, acts, *dims = scenarios[n]
        w, h = (dims + [1600, 1000])[:2] if dims else (1600, 1000)
        c, errs, fails = run(theme, acts, n, w, h)
        tilefails = [u for u in fails if 'basemaps' in u]
        problems = []
        if errs: problems.append(f'JS ERRORS: {errs[:3]}')
        if c['hOverflow'] > 0: problems.append(f"horizontal overflow {c['hOverflow']}px")
        if c['clipped']: problems.append(f"clipped: {c['clipped'][:3]}")
        if c['legendOverlapsAttribution']: problems.append('legend overlaps attribution')
        if c.get('escaped'): problems.append(f"overlay escaped its container: {c['escaped']}")
        if c.get('coveredByTable') is False: problems.append('table view does not cover the map')
        if n not in ('table',) and c['markers'] == 0: problems.append('no markers rendered')
        if c['tiles'] == 0: problems.append('no tiles loaded')
        bad += len(problems)
        print(f"[{'FAIL' if problems else ' ok '}] {n:8s} markers={c['markers']:3d} list={c['listItems']:3d} tiles={c['tiles']:3d} {c['count'] or ''}")
        for p_ in problems: print('        -', p_)
    print('\nproblems:', bad)
