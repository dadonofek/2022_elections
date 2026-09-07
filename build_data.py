"""Join every polling station to geocoded coordinates and aggregate to map sites."""
import json, re, unicodedata, config

BLOCS = config.BLOCS
CAMPS = config.CAMPS
PARTY_NAMES = config.PARTY_NAMES

# camps that are a party group of their own (not just an alias for a bloc total)
OWN_CAMPS = [k for k, v in CAMPS.items() if v.get('parties')]
# every key the potential is computed for: the three blocs of the partition, plus
# each camp that is narrower than a bloc (הדמוקרטים sits inside the opposition)
POT_KEYS = ('coalition', 'opposition', 'other', *OWN_CAMPS)

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
    # camps with their own party list are counted here too; they overlap a bloc by
    # design (dem ⊂ opposition) and so are never subtracted from anything.
    for k in OWN_CAMPS:
        t[k] = sum(parties.get(p, 0) for p in CAMPS[k]['parties'])
    return t

def potential(o):
    """Votes a bloc left on the table at this site, per the PM's formula:
    eligible x (1 - turnout) x that bloc's share of the valid votes cast here.

    eligible x (1 - turnout) IS the non-voter count, so this reads: if the people
    who did not vote here had voted the way their neighbours who did vote did, how
    many votes would each bloc have gained. That "if" is an assumption, not a
    forecast - the UI labels the field an estimate and states it in the about panel.
    """
    nv, valid = o['non_voters'], o['valid']
    if not valid:
        return {k: 0 for k in POT_KEYS}
    return {k: round(nv * o[k] / valid) for k in POT_KEYS}


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
    s['non_voters'] = s['eligible'] - s['voters']
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
        'invalid': s['invalid'], 'non_voters': s['non_voters'], 'coalition': s['coalition'],
        'opposition': s['opposition'], 'other': s['other'], 'lead': s['lead'],
        **{k: s[k] for k in OWN_CAMPS},
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
    st['non_voters'] = st['eligible'] - st['voters']
    st['pot'] = potential(st)
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
city['non_voters'] = city['eligible'] - city['voters']
city['pot'] = potential(city)

# National turnout is the map's primary delta baseline. Recompute it from the
# official national per-station file when it is available so the number is derived
# rather than asserted; fall back to the documented constant otherwise.
def national_turnout():
    import csv, os
    path = 'data/expb.csv'
    if not os.path.exists(path):
        return config.NATIONAL_TURNOUT, 'config.NATIONAL_TURNOUT'
    with open(path, encoding='utf-8-sig') as fh:
        rows = csv.reader(fh)
        hdr = next(rows)
        i_e, i_v = hdr.index('בזב'), hdr.index('מצביעים')
        e = v = 0
        for r in rows:
            e += int(r[i_e]); v += int(r[i_v])
    return (round(100 * v / e, 2), f'{path} ({v:,}/{e:,})') if e else (config.NATIONAL_TURNOUT, 'fallback')

city['national_turnout'], _nt_src = national_turnout()

payload = {'city': city, 'sites': out_sites, 'party_names': PARTY_NAMES, 'blocs': BLOCS,
           'camps': CAMPS, 'default_camp': config.DEFAULT_CAMP}
json.dump(payload, open('data/map_data.json', 'w'), ensure_ascii=False, separators=(',', ':'))

print('sites:', len(out_sites), '| kalpiot:', len(stations))
print('sites without coords:', sum(1 for s in out_sites if s['lat'] is None))
print('kalpiot without coords:', sum(1 for s in stations if s['lat'] is None))
from collections import Counter
print('precision:', Counter(s['geo_precision'] for s in out_sites))
print('co-located sites spread apart:', spread)
print('national turnout %:', city['national_turnout'], 'from', _nt_src)
print('city non-voters:', city['non_voters'], '| potential', city['pot'])
for k in OWN_CAMPS:
    print(f'camp {k} ({CAMPS[k]["name"]}):', city[k], 'votes |',
          round(100 * city[k] / city['valid'], 2), '% | potential', city['pot'][k],
          '| site max potential', max(s['pot'][k] for s in out_sites))
print('city turnout %:', city['turnout'], '| coalition', cb['coalition'], 'opp', cb['opposition'], 'other', city['other'])
print('json size KB:', round(len(open('data/map_data.json').read().encode())/1024))
