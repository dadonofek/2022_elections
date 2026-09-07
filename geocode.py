import json, os, time, urllib.parse, urllib.request, re, sys, config

CACHE = config.data('geocache.json')
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
UA = config.UA
BBOX = config.BBOX  # (W, S, E, N)
CITY = config.CITY_HE

def nominatim(params):
    url = 'https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            time.sleep(2 + 2*attempt)
    return []

def in_city(lat, lon):
    return config.in_bbox(lat, lon)

def geocode(addr):
    if addr in cache: return cache[addr]
    m = re.match(r'^(.*?)\s+(\d+[א-ת]?)$', addr.strip())
    street, num = (m.group(1), m.group(2)) if m else (addr.strip(), None)
    tries = []
    if num:
        tries.append({'street': f'{num} {street}', 'city': CITY, 'country': 'ישראל'})
        tries.append({'q': f'{street} {num}, {CITY}, ישראל'})
    tries.append({'q': f'{street}, {CITY}, ישראל'})
    tries.append({'street': street, 'city': CITY, 'country': 'ישראל'})
    for i, t in enumerate(tries):
        p = dict(t, format='json', limit=5, addressdetails=1,
                 viewbox=config.viewbox_str(), bounded=1)
        res = nominatim(p); time.sleep(1.1)
        for r in res:
            lat, lon = float(r['lat']), float(r['lon'])
            if in_city(lat, lon):
                out = {'lat': lat, 'lon': lon, 'display': r['display_name'],
                       'osm_type': r.get('type'), 'addresstype': r.get('addresstype'),
                       'precision': 'house' if (num and r.get('addresstype') in ('house_number','building','place')) else ('street' if i < len(tries)-0 else 'other'),
                       'query_stage': i}
                cache[addr] = out; return out
    cache[addr] = None; return None

addrs = sorted({s['address'] for s in json.load(open(config.data('raw.json')))['stations'] if s['address']})
for i, a in enumerate(addrs, 1):
    r = geocode(a)
    msg = 'MISS' if not r else '%.5f,%.5f stage%d' % (r['lat'], r['lon'], r['query_stage'])
    print('%d/%d  %s -> %s' % (i, len(addrs), a, msg), flush=True)
    if i % 10 == 0: json.dump(cache, open(CACHE,'w'), ensure_ascii=False, indent=1)
json.dump(cache, open(CACHE,'w'), ensure_ascii=False, indent=1)
print('MISSES:', sum(1 for a in addrs if not cache.get(a)))
