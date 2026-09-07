import json, pathlib, config

def rt(p): return pathlib.Path(p).read_text(encoding='utf-8')

tpl = rt('src_map.html')
out = (tpl
  .replace('/*__LEAFLET_JS__*/', rt('vendor/leaflet.js'))
  .replace('/*__DATA__*/', rt('data/map_data.json'))
  .replace('/*__APP_JS__*/', rt('src_app.js')))
css = rt('vendor/leaflet.css')
out = out.replace('<style>', '<style>\n/* ---- Leaflet 1.9.4 ---- */\n' + css + '\n/* ---- app ---- */\n', 1)
pathlib.Path(config.OUT_HTML).write_text(out, encoding='utf-8')
print('built', config.OUT_HTML, round(len(out)/1024), 'KB')
