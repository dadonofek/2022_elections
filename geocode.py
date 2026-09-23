import json, os, time, urllib.parse, urllib.request, re, sys, config

CACHE = config.data('geocache.json')
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
UA = config.UA
BBOX = config.BBOX  # (W, S, E, N)
CITY = config.CITY_HE

class Unreachable(Exception):
    """Nominatim could not be reached at all — not the same answer as "no match"."""

def nominatim(params):
    url = 'https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            time.sleep(2 + 2*attempt)
    # Three failures in a row is the network, not the address. Caching a miss here
    # would stop every later run from ever asking again, so raise instead.
    raise Unreachable(url)

def in_city(lat, lon):
    return config.in_bbox(lat, lon)

def geocode(addr):
    # a provisional entry (geocode_overture.py's street-level fallback) is kept only
    # until Nominatim can be asked; a real answer replaces it
    if addr in cache and not (cache[addr] or {}).get('provisional'): return cache[addr]
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
    if (cache.get(addr) or {}).get('provisional'): return cache[addr]   # keep the fallback
    cache[addr] = None; return None

addrs = sorted({s['address'] for s in json.load(open(config.data('raw.json')))['stations'] if s['address']})
unreached = []
for i, a in enumerate(addrs, 1):
    try:
        r = geocode(a)
    except Unreachable:
        # offline: stop asking, and leave every address not yet answered uncached
        unreached = [x for x in addrs[i - 1:] if x not in cache or (cache[x] or {}).get('provisional')]
        break
    stage = r.get('query_stage') if r else None
    msg = 'MISS' if not r else '%.5f,%.5f stage%s' % (r['lat'], r['lon'], stage if isinstance(stage, int) else ' ' + str(stage))
    print('%d/%d  %s -> %s' % (i, len(addrs), a, msg), flush=True)
    if i % 10 == 0: json.dump(cache, open(CACHE,'w'), ensure_ascii=False, indent=1)
json.dump(cache, open(CACHE,'w'), ensure_ascii=False, indent=1)
print('MISSES:', sum(1 for a in addrs if not cache.get(a)))
if unreached:
    print(f'Nominatim could not be reached; {len(unreached)} addresses were not asked and stay '
          'uncached (or provisional) for the next run:', ', '.join(unreached))
