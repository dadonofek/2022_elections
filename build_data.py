"""Join every polling station to geocoded coordinates and aggregate to map sites."""
import json, re, unicodedata, config

BLOCS = config.BLOCS
PARTY_NAMES = config.PARTY_NAMES

raw = json.load(open('data/raw.json'))
geo = json.load(open('data/geocache.json'))
snaps = json.load(open('data/osm_snaps.json'))   # sites matched to a named OSM venue
stations, site_rows = raw['stations'], raw['sites']

def precision(g):
    if not g: return 'none'
    if g.get('snapped'): return 'venue'
    at = (g.get('addresstype') or '') + '|' + (g.get('osm_type') or '')
    if 'house_number' in at or 'building' in at: return 'house'
    if 'road' in at or 'residential' in at or 'tertiary' in at or 'secondary' in at or 'primary' in at or 'unclassified' in at or 'living_street' in at or 'pedestrian' in at:
        return 'street'
    return 'place'

def bloc_totals(parties):
    t = {k: sum(parties.get(p, 0) for p in ps) for k, ps in BLOCS.items()}
    t['opposition'] = t['zionist_opp'] + t['arab']
    return t

# --- station level -------------------------------------------------------
for s in stations:
    g = geo.get(s['address'])
    sn = snaps.get(f"{s['site']}||{s['address']}")
    if sn:
        g = dict(g or {}, lat=sn['lat'], lon=sn['lon'], snapped=True,
                 display=sn['osm_name'] + ' · ' + (g or {}).get('display', ''),
                 osm_venue=sn['osm_name'])
    s['lat'], s['lon'] = (g['lat'], g['lon']) if g else (None, None)
    s['geo_precision'] = precision(g)
    s['geo_display'] = g['display'] if g else None
    s['turnout'] = round(100 * s['voters'] / s['eligible'], 2) if s['eligible'] else 0
    b = bloc_totals(s['parties'])
    s.update(b)
    s['other'] = s['valid'] - b['coalition'] - b['opposition']
    top = max((('coalition', b['coalition']), ('opposition', b['opposition']), ('other', s['other'])), key=lambda x: x[1])
    s['lead'] = top[0] if s['valid'] else 'none'

# --- site level (group by site name + address) ---------------------------
sites = {}
for s in stations:
    key = (s['site'], s['address'])
    st = sites.setdefault(key, {
        'name': s['site'], 'address': s['address'], 'lat': s['lat'], 'lon': s['lon'],
        'geo_precision': s['geo_precision'], 'geo_display': s['geo_display'],
        'osm_venue': (geo.get(s['address']) or {}).get('osm_venue') or (snaps.get(f"{s['site']}||{s['address']}") or {}).get('osm_name'),
        'confidence': s['confidence'], 'kalpiot': [], 'parties': {},
        'eligible': 0, 'voters': 0, 'valid': 0, 'invalid': 0,
    })
    for f in ('eligible', 'voters', 'valid', 'invalid'):
        st[f] += s[f]
    for p, v in s['parties'].items():
        st['parties'][p] = st['parties'].get(p, 0) + v
    st['kalpiot'].append({
        'kalpi': s['kalpi'], 'barzel': s['barzel'], 'eligible': s['eligible'],
        'voters': s['voters'], 'turnout': s['turnout'], 'valid': s['valid'],
        'invalid': s['invalid'], 'coalition': s['coalition'],
        'opposition': s['opposition'], 'other': s['other'], 'lead': s['lead'],
        'parties': s['parties'],
    })

def kalpi_key(k):
    return [int(x) for x in re.findall(r'\d+', k['kalpi'])]

out_sites = []
for i, ((name, addr), st) in enumerate(sorted(sites.items(), key=lambda kv: kalpi_key(kv[1]['kalpiot'][0]))):
    st['kalpiot'].sort(key=kalpi_key)
    st['id'] = i
    st['turnout'] = round(100 * st['voters'] / st['eligible'], 2) if st['eligible'] else 0
    b = bloc_totals(st['parties'])
    st.update(b)
    st['other'] = st['valid'] - b['coalition'] - b['opposition']
    top = max((('coalition', b['coalition']), ('opposition', b['opposition']), ('other', st['other'])), key=lambda x: x[1])
    st['lead'] = top[0] if st['valid'] else 'none'
    st['margin'] = round(100 * (b['coalition'] - b['opposition']) / st['valid'], 2) if st['valid'] else 0
    st['n_kalpi'] = len(st['kalpiot'])
    st['top_parties'] = sorted(((p, v) for p, v in st['parties'].items() if v > 0), key=lambda x: -x[1])[:8]
    out_sites.append(st)

# --- separate co-located sites so markers do not overlap exactly ---------
from collections import defaultdict
at_point = defaultdict(list)
for st in out_sites:
    if st['lat'] is not None:
        at_point[(round(st['lat'], 6), round(st['lon'], 6))].append(st)
import math
spread = 0
for pt, group in at_point.items():
    if len(group) > 1:
        spread += len(group)
        r = 0.00035
        for j, st in enumerate(group):
            a = 2 * math.pi * j / len(group)
            st['lat'] = round(pt[0] + r * math.cos(a), 7)
            st['lon'] = round(pt[1] + r * math.sin(a) / math.cos(math.radians(pt[0])), 7)
            st['jittered'] = True

city = {
    'eligible': sum(s['eligible'] for s in stations),
    'voters': sum(s['voters'] for s in stations),
    'valid': sum(s['valid'] for s in stations),
    'invalid': sum(s['invalid'] for s in stations),
    'n_kalpi': len(stations),
    'n_sites': len(out_sites),
    'name': config.CITY_HE,
    'parties': {},
}
_pts = [(s['lat'], s['lon']) for s in out_sites if s['lat'] is not None]
city['center'] = list(config.MAP_CENTER) if config.MAP_CENTER else (
    [round(sum(p[0] for p in _pts) / len(_pts), 5),
     round(sum(p[1] for p in _pts) / len(_pts), 5)] if _pts else [32.0, 35.0])
city['zoom'] = config.MAP_ZOOM
for s in stations:
    for p, v in s['parties'].items():
        city['parties'][p] = city['parties'].get(p, 0) + v
cb = bloc_totals(city['parties'])
city.update(cb)
city['other'] = city['valid'] - cb['coalition'] - cb['opposition']
city['turnout'] = round(100 * city['voters'] / city['eligible'], 2)

payload = {'city': city, 'sites': out_sites, 'party_names': PARTY_NAMES, 'blocs': BLOCS}
json.dump(payload, open('data/map_data.json', 'w'), ensure_ascii=False, separators=(',', ':'))

print('sites:', len(out_sites), '| kalpiot:', len(stations))
print('sites without coords:', sum(1 for s in out_sites if s['lat'] is None))
print('kalpiot without coords:', sum(1 for s in stations if s['lat'] is None))
from collections import Counter
print('precision:', Counter(s['geo_precision'] for s in out_sites))
print('co-located sites spread apart:', spread)
print('city turnout %:', city['turnout'], '| coalition', cb['coalition'], 'opp', cb['opposition'], 'other', city['other'])
print('json size KB:', round(len(open('data/map_data.json').read().encode())/1024))
