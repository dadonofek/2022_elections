"""Snap polling sites to the real building where OSM knows the named venue.

Nominatim resolves most Haifa addresses only to a street centroid. Most polling
sites are named schools / community centres, so we pull every named school,
kindergarten, community centre and college in the Haifa bbox from Overpass and
match them to site names. A match is accepted only when it also sits close to
the address the site was geocoded to, which guards against same-name venues.
"""
import json, re, math, urllib.request, urllib.parse, time, config

BBOX = config.overpass_bbox_str()   # "S,W,N,E"
Q = f"""
[out:json][timeout:120];
(
  nwr["amenity"~"^(school|kindergarten|college|university|community_centre|library)$"]["name"]({BBOX});
  nwr["building"="school"]["name"]({BBOX});
  nwr["leisure"="sports_centre"]["name"]({BBOX});
  nwr["amenity"="place_of_worship"]["name"]({BBOX});
);
out center tags;
"""

def overpass():
    for url in ('https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter'):
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode({'data': Q}).encode(),
                                         headers={'User-Agent': config.UA})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode())['elements']
        except Exception as e:
            print('overpass failed', url, e)
            time.sleep(3)
    return []

import os
if os.path.exists('data/osm_venues.json'):
    els = json.load(open('data/osm_venues.json'))          # cached Overpass response
    print('osm venues (cached):', len(els))
else:
    els = overpass()
    print('osm venues:', len(els))
    if els: json.dump(els, open('data/osm_venues.json', 'w'), ensure_ascii=False)

# ---------------- name normalisation ----------------
ABBR = [
  (r'בי"?ס', 'בית ספר'), (r'ביה"?ס', 'בית ספר'), (r'בית ספר יסודי', 'בית ספר'),
  (r'ממ"?ד', ''), (r'מקיף', ''), (r'תיכון', ''), (r'עירוני', ''),
  (r'אולם ספורט', ''), (r'מועדון גמלאים', ''), (r'מתנ"?ס', 'מרכז קהילתי'),
  (r'ע"?ש', ''), (r'ע\'\'ש', ''),
]
STOP = {'בית','ספר','מרכז','קהילתי','ה','של','בית-ספר','אולם','מועדון','גן','ילדים','חטיבת','ביניים'}
def norm(s):
    s = str(s or '')
    s = s.replace('"', '').replace("'", '').replace('־', ' ').replace('-', ' ')
    for a, b in ABBR: s = re.sub(a.replace('"',''), b, s)
    s = re.sub(r'[^\wא-ת ]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()
def tokens(s):
    return {t for t in norm(s).split() if len(t) > 1 and t not in STOP}

def dist_m(a, b):
    dy = (a[0] - b[0]) * 111320
    dx = (a[1] - b[1]) * 111320 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)

venues = []
for e in els:
    c = e.get('center') or ({'lat': e.get('lat'), 'lon': e.get('lon')} if e.get('lat') else None)
    if not c: continue
    t = e.get('tags', {})
    for key in ('name', 'name:he', 'alt_name', 'official_name'):
        if t.get(key):
            venues.append({'name': t[key], 'tok': tokens(t[key]), 'lat': c['lat'], 'lon': c['lon'],
                           'amenity': t.get('amenity') or t.get('leisure') or t.get('building')})

raw = json.load(open('data/raw.json'))
cache = json.load(open('data/geocache.json'))
sites = {}
for s in raw['stations']:
    sites.setdefault((s['site'], s['address']), None)

# token document frequency: tokens shared by many venues (neighbourhood names such
# as "קרית"/"חיים") carry no identity, so a match resting only on them is rejected.
from collections import Counter
df = Counter()
for nm in {v['name'] for v in venues}:          # count distinct names, not duplicate OSM objects
    for t in tokens(nm): df[t] += 1
def distinctive(toks):
    return {t for t in toks if df[t] <= 3}

snaps = {}
report = []
rejected = []
for (name, addr) in sites:
    g = cache.get(addr)
    if not g: continue
    base = (g['lat'], g['lon'])
    st = tokens(name)
    if len(st) < 1: continue
    best = None
    for v in venues:
        if not v['tok']: continue
        inter = st & v['tok']
        if not inter: continue
        j = len(inter) / len(st | v['tok'])
        cov = len(inter) / len(st)
        d = dist_m(base, (v['lat'], v['lon']))
        if d > 500: continue                      # must be near the stated address
        if cov < 0.6 or j < 0.34: continue        # names must really correspond
        if not distinctive(inter):                # matched only on generic/place words
            rejected.append((round(d), name, v['name'])); continue
        score = cov + j - d / 4000
        if not best or score > best[0]: best = (score, v, d, cov, j)
    if best:
        _, v, d, cov, j = best
        snaps[f'{name}||{addr}'] = {'lat': v['lat'], 'lon': v['lon'], 'osm_name': v['name'],
                                    'dist_m': round(d), 'cov': round(cov, 2), 'jacc': round(j, 2)}
        report.append((round(d), name, v['name']))

json.dump(snaps, open('data/osm_snaps.json', 'w'), ensure_ascii=False, indent=1)
report.sort(reverse=True)
print('snapped sites:', len(snaps), 'of', len(sites))
print('rejected as name-only-generic:', len(set(r[1] for r in rejected)))
for r in sorted(set(rejected), reverse=True)[:6]: print('   reject', r)
print('\nfarthest 12 snaps (sanity check):')
for d, a, b in report[:12]: print(f'  {d:4d}m  {a}  ->  {b}')
