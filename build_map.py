"""Stage 7 — inline the data, Leaflet and the app into one self-contained HTML file.

The map's profile (config.PROFILES; carried in map_data.json) picks two things:
  * which blocks of src_map.html survive — a block is the lines between a
    `<!--@<profile>-->` marker and the next marker, `<!--@end-->` closing it;
  * the product script inlined after the shared core, src_core.js.
"""
import json, pathlib, re, config

PRODUCT_JS = {'analysis': 'src_app.js', 'volunteer': 'src_volunteer.js'}
MARKER = re.compile(r'\s*<!--@(\w+)-->\s*')


def rt(p): return pathlib.Path(p).read_text(encoding='utf-8')


def select_profile(tpl, profile):
    """Keep the shared lines and the active profile's blocks; drop the marker lines."""
    out, keep = [], True
    for line in tpl.split('\n'):
        m = MARKER.fullmatch(line)
        if m:
            tag = m.group(1)
            if tag != 'end' and tag not in config.PROFILES:
                raise SystemExit(f'src_map.html: unknown profile block <!--@{tag}-->')
            keep = tag in ('end', profile)
            continue
        if keep:
            out.append(line)
    return '\n'.join(out)


def list_date(iso):
    """'2026-09-15' -> '15.9.2026', the way the lists themselves write it."""
    if not iso: return 'תאריך לא ידוע'
    y, m, d = iso.split('-')
    return f'{int(d)}.{int(m)}.{y}'


data_json = rt(config.data('map_data.json'))
data = json.loads(data_json)
city, profile = data['city'], data.get('profile', 'analysis')

# City tokens are substituted on the TEMPLATE, before the data and the app are
# inlined — a blind replace afterwards could rewrite text inside the JSON.
tpl = select_profile(rt('src_map.html'), profile)
for token, value in (('__CITY_HE__', city['name']),
                     ('__N_KALPI__', str(city['n_kalpi'])),
                     ('__N_SITES__', str(city['n_sites'])),
                     ('__ELECTION_HE__', city.get('election') or ''),
                     ('__LIST_DATE__', list_date(city.get('list_date')))):
    tpl = tpl.replace(token, value)

app = rt('src_core.js') + '\n' + rt(PRODUCT_JS[profile])
out = (tpl
  .replace('/*__LEAFLET_JS__*/', rt('vendor/leaflet.js'))
  .replace('/*__DATA__*/', data_json)
  .replace('/*__APP_JS__*/', app))
css = rt('vendor/leaflet.css')
out = out.replace('<style>', '<style>\n/* ---- Leaflet 1.9.4 ---- */\n' + css + '\n/* ---- app ---- */\n', 1)
pathlib.Path(config.OUT_HTML).write_text(out, encoding='utf-8')
print('built', config.OUT_HTML, f'({profile})', round(len(out)/1024), 'KB')
