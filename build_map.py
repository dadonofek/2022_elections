"""Stage 7 — inline the data, Leaflet and the app into one self-contained HTML file."""
import json, pathlib, config

def rt(p): return pathlib.Path(p).read_text(encoding='utf-8')

data_json = rt(config.data('map_data.json'))
city = json.loads(data_json)['city']

# City tokens are substituted on the TEMPLATE, before the data and the app are
# inlined — a blind replace afterwards could rewrite text inside the JSON.
tpl = rt('src_map.html')
for token, value in (('__CITY_HE__', city['name']),
                     ('__N_KALPI__', str(city['n_kalpi'])),
                     ('__N_SITES__', str(city['n_sites']))):
    tpl = tpl.replace(token, value)

out = (tpl
  .replace('/*__LEAFLET_JS__*/', rt('vendor/leaflet.js'))
  .replace('/*__DATA__*/', data_json)
  .replace('/*__APP_JS__*/', rt('src_app.js')))
css = rt('vendor/leaflet.css')
out = out.replace('<style>', '<style>\n/* ---- Leaflet 1.9.4 ---- */\n' + css + '\n/* ---- app ---- */\n', 1)
pathlib.Path(config.OUT_HTML).write_text(out, encoding='utf-8')
print('built', config.OUT_HTML, round(len(out)/1024), 'KB')
