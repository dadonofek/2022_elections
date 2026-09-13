"""Nationwide stage 2 — geocode every (locality, address) pair in data/national/raw.json.

RUN THIS ON A MACHINE WITH NORMAL INTERNET ACCESS, NOT IN THIS SANDBOX.
This session's network policy blocks Nominatim (and every other geocoder tested:
data.gov.il, govmap, Geoapify, odata.org.il — all 403/EGRESS_BLOCKED), so this script
cannot be run here. It needs only the Python standard library plus openpyxl for
national_extract.py's output — no API key.

    python3 national_extract.py     # writes data/national/raw.json (no network)
    python3 geocode_national.py     # this script — needs internet, ~70 minutes

It is the same approach as geocode.py, run over every locality instead of one:
Nominatim, rate-limited to 1 req/s per usage policy, queried per (locality, address)
pair. There are 3,762 unique pairs, so a cold run is roughly 3,762 x 1.1s ~= 70
minutes. It is resumable — the cache is written to data/national/geocache.json every
10 addresses, and a re-run skips anything already cached, so it is safe to Ctrl-C
and restart.

The one thing this script cannot borrow from geocode.py: there is no per-city bbox
to bound results to, or to sanity-check a hit against. Two things stand in for it:

  1. Every query is bounded to a generous ISRAEL_BBOX (rejects a result geocoded to
     the wrong country entirely).
  2. Every hit is checked against the locality name Nominatim itself returns
     (address.city / town / village / municipality / suburb / county), normalized
     for the spelling variants the CEC and OSM disagree on (קרית/קריית, punctuation,
     hyphens). A hit is 'verified: true' only if that check passes; otherwise it is
     still saved (so it does not need re-fetching) but flagged 'verified: false' for
     manual review — do not treat an unverified hit as a real coordinate.

When this finishes, send data/national/geocache.json back — it is the only new
artifact this step produces; the pipeline continues from there (build_data /
build_map for the national tab) once it exists. The printed summary at the end
(hits / misses / unverified, precision counts) is worth pasting back too.
"""
import json, os, re, time, unicodedata, urllib.parse, urllib.request

RAW    = 'data/national/raw.json'
CACHE  = 'data/national/geocache.json'
UA     = 'il-elections-2022-national-map/1.0 (research)'
ISRAEL_BBOX = (34.20, 29.40, 35.95, 33.45)   # (W, S, E, N) — generous, incl. Eilat & the Golan

cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}

def key(locality_name, address):
    return f'{locality_name}|||{address}'

def in_bbox(lat, lon):
    w, s, e, n = ISRAEL_BBOX
    return s <= lat <= n and w <= lon <= e

def viewbox_str():
    return ','.join(map(str, ISRAEL_BBOX))

def nominatim(params):
    url = 'https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception:
            time.sleep(2 + 2 * attempt)
    return []

# --------------------------------------------------------- locality-name matching
SPELL_PAIRS = [('קריית', 'קרית'), ('־', '-'), ('"', ''), ('״', ''), ("'", '')]

def normalize_locality(name):
    name = unicodedata.normalize('NFKC', name or '')
    for a, b in SPELL_PAIRS:
        name = name.replace(a, b)
    name = re.sub(r'\(.*?\)', '', name)          # "כנרת (קבוצה)" -> "כנרת "
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def locality_matches(locality_name, addressdetails):
    want = normalize_locality(locality_name)
    for field in ('city', 'town', 'village', 'municipality', 'suburb', 'county', 'city_district'):
        got = normalize_locality(addressdetails.get(field, ''))
        if got and (got in want or want in got):
            return True
    return False

# ---------------------------------------------------------------------- geocoding
def geocode_one(locality_name, address):
    m = re.match(r'^(.*?)\s+(\d+[א-ת]?)$', address.strip())
    street, num = (m.group(1), m.group(2)) if m else (address.strip(), None)
    tries = []
    if num:
        tries.append({'street': f'{num} {street}', 'city': locality_name, 'country': 'ישראל'})
        tries.append({'q': f'{street} {num}, {locality_name}, ישראל'})
    tries.append({'q': f'{street}, {locality_name}, ישראל'})
    tries.append({'street': street, 'city': locality_name, 'country': 'ישראל'})
    for i, t in enumerate(tries):
        p = dict(t, format='json', limit=5, addressdetails=1, viewbox=viewbox_str(), bounded=1)
        res = nominatim(p); time.sleep(1.1)
        for r in res:
            lat, lon = float(r['lat']), float(r['lon'])
            if not in_bbox(lat, lon):
                continue
            ad = r.get('address', {})
            verified = locality_matches(locality_name, ad)
            precision = ('house' if (num and r.get('addresstype') in ('house_number', 'building', 'place'))
                         else 'street')
            return {'lat': lat, 'lon': lon, 'display': r['display_name'],
                    'osm_type': r.get('type'), 'addresstype': r.get('addresstype'),
                    'precision': precision, 'verified': verified, 'query_stage': i}
    return None

raw = json.load(open(RAW))
pairs = sorted({(s['locality_name'], s['address']) for s in raw['sites']})
todo = [(ln, a) for ln, a in pairs if key(ln, a) not in cache]
print(f'{len(pairs)} unique (locality, address) pairs, {len(todo)} not yet cached')

for i, (locality_name, address) in enumerate(todo, 1):
    r = geocode_one(locality_name, address)
    cache[key(locality_name, address)] = r
    if not r:
        msg = 'MISS'
    else:
        msg = '%.5f,%.5f %s%s' % (r['lat'], r['lon'], r['precision'],
                                    '' if r['verified'] else ' UNVERIFIED')
    print(f'{i}/{len(todo)}  {locality_name} | {address} -> {msg}', flush=True)
    if i % 10 == 0:
        json.dump(cache, open(CACHE, 'w'), ensure_ascii=False, indent=1)
json.dump(cache, open(CACHE, 'w'), ensure_ascii=False, indent=1)

hits = [v for v in cache.values() if v]
print()
print('total cached:', len(cache))
print('hits:', len(hits), '| misses:', sum(1 for v in cache.values() if not v))
print('verified:', sum(1 for v in hits if v['verified']),
      '| unverified (needs manual review):', sum(1 for v in hits if not v['verified']))
prec = {}
for v in hits: prec[v['precision']] = prec.get(v['precision'], 0) + 1
print('precision:', prec)
print('-> data/national/geocache.json')
