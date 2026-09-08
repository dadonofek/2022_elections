"""Second pass for addresses the plain query missed: expand abbreviations,
flip surname-first street names, try spelling variants, then street-only."""
import json, re, time, urllib.parse, urllib.request, config

CACHE = config.data('geocache.json')
cache = json.load(open(CACHE))
UA = config.UA
BBOX = config.BBOX
CITY = config.CITY_HE

def nominatim(params):
    url = 'https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    for a in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception:
            time.sleep(2 + 2 * a)
    return []

HONORIFICS = ['ד"ר', 'דר\'', 'הרב', 'פרופ\'', 'פרופ']
SPELL = {
    'הגבורים': 'הגיבורים', 'הקבוצים': 'הקיבוצים',
    'קריית': 'קרית', 'הציונות': 'הציונות',
    'איידלשטיין': 'אדלשטיין',
}

def variants(street):
    out = []
    def add(s):
        s = re.sub(r'\s+', ' ', s).strip()
        if s and s not in out: out.append(s)
    add(street)
    s = street
    if s.startswith('שד '): add('שדרות ' + s[3:]); s2 = 'שדרות ' + s[3:]
    for h in HONORIFICS:
        if h in s: add(s.replace(h, ''))
    base = s
    for h in HONORIFICS: base = base.replace(h, '')
    base = re.sub(r'\s+', ' ', base).strip()
    # The CEC file sometimes preserves abbreviations/punctuation that OSM omits,
    # e.g. "סמ ויצ\"ו" versus the OSM street name "ויצו".
    plain = base.replace('"', '').replace('״', '')
    add(plain)
    if plain.startswith('סמ '):
        add(plain[3:])
        add('סמטת ' + plain[3:])
    toks = base.split()
    if len(toks) == 2: add(toks[1] + ' ' + toks[0])          # surname-first -> given-first
    for a, b in SPELL.items():
        if a in base: add(base.replace(a, b))
    if base.startswith('שד '): 
        add('שדרות ' + base[3:])
        rest = base[3:]
        add(rest)
    return out

def try_queries(street, num):
    qs = []
    for v in variants(street):
        if num:
            qs.append({'street': f'{num} {v}', 'city': CITY, 'country': 'ישראל'})
            qs.append({'q': f'{v} {num}, {CITY}, ישראל'})
    for v in variants(street):
        qs.append({'q': f'{v}, {CITY}, ישראל'})
        qs.append({'street': v, 'city': CITY, 'country': 'ישראל'})
    return qs

fixed = 0
misses = [a for a, v in cache.items() if not v]
for addr in misses:
    m = re.match(r'^(.*?)\s+(\d+[א-ת]?)$', addr.strip())
    street, num = (m.group(1), m.group(2)) if m else (addr.strip(), None)
    got = None
    for i, q in enumerate(try_queries(street, num)):
        p = dict(q, format='json', limit=5, addressdetails=1,
                 viewbox=config.viewbox_str(), bounded=1)
        res = nominatim(p); time.sleep(1.1)
        for r in res:
            lat, lon = float(r['lat']), float(r['lon'])
            if config.in_bbox(lat, lon):
                got = {'lat': lat, 'lon': lon, 'display': r['display_name'],
                       'osm_type': r.get('type'), 'addresstype': r.get('addresstype'),
                       'query_stage': 10 + i, 'query_used': str(q)}
                break
        if got: break
    cache[addr] = got
    fixed += bool(got)
    print(('OK   ' if got else 'MISS ') + addr + (' -> %.5f,%.5f' % (got['lat'], got['lon']) if got else ''), flush=True)
    json.dump(cache, open(CACHE, 'w'), ensure_ascii=False, indent=1)
print('fixed', fixed, 'of', len(misses))
