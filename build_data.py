"""Join every polling station to geocoded coordinates and aggregate to map sites."""
import re, config
from sitegeo import (load, precision, site_geo, spread_colocated, map_center,
                     refuse_missing_coords, national_turnout, write_map_data)

if config.PROFILE == 'volunteer':
    # the volunteer map joins a different station list — the coming election's — and
    # builds its own payload; see that file
    import build_volunteer_data
    build_volunteer_data.main()
    raise SystemExit(0)

BLOCS = config.BLOCS
CAMPS = config.CAMPS
PARTY_NAMES = config.PARTY_NAMES

# every key the potential is computed for: the three blocs of the partition, plus
# each camp, which is narrower than a bloc (הדמוקרטים sits inside the opposition)
POT_KEYS = ('coalition', 'opposition', 'other', *CAMPS)

raw = load('raw.json')
geo = load('geocache.json', {})
snaps = load('osm_snaps.json', {})   # sites matched to a named OSM venue
stations, site_rows = raw['stations'], raw['sites']

def bloc_totals(parties):
    t = {k: sum(parties.get(p, 0) for p in ps) for k, ps in BLOCS.items()}
    t['opposition'] = t['zionist_opp'] + t['arab']
    # camps with their own party list are counted here too; they overlap a bloc by
    # design (dem ⊂ opposition) and so are never subtracted from anything.
    for k, v in CAMPS.items():
        t[k] = sum(parties.get(p, 0) for p in v['parties'])
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
    g = site_geo(s['site'], s['address'], geo, snaps)
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
        **{k: s[k] for k in CAMPS},
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
spread = spread_colocated(out_sites)

city = {
    'eligible': sum(s['eligible'] for s in stations),
    'voters': sum(s['voters'] for s in stations),
    'valid': sum(s['valid'] for s in stations),
    'invalid': sum(s['invalid'] for s in stations),
    'n_kalpi': len(stations),
    'n_sites': len(out_sites),
    'name': config.CITY_HE,
    # provenance sentences for the "על הנתונים" panel — per city, since the
    # address source and how it was matched differ between them
    'source_note': config.SOURCE_NOTE,
    'match_note': config.MATCH_NOTE,
    'parties': {},
}
city['center'] = map_center(out_sites)
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

# National turnout is the map's primary delta baseline (derived, see sitegeo.py).
city['national_turnout'], _nt_src = national_turnout()

payload = {'city': city, 'sites': out_sites, 'party_names': PARTY_NAMES, 'blocs': BLOCS,
           'camps': CAMPS, 'default_pot_target': config.DEFAULT_POT_TARGET}

print('sites:', len(out_sites), '| kalpiot:', len(stations))
print('sites without coords:', sum(1 for s in out_sites if s['lat'] is None))
print('kalpiot without coords:', sum(1 for s in stations if s['lat'] is None))
from collections import Counter
print('precision:', Counter(s['geo_precision'] for s in out_sites))
print('co-located sites spread apart:', spread)
print('national turnout %:', city['national_turnout'], 'from', _nt_src)
print('city non-voters:', city['non_voters'], '| potential', city['pot'])
for k in CAMPS:
    print(f'camp {k} ({CAMPS[k]["name"]}):', city[k], 'votes |',
          round(100 * city[k] / city['valid'], 2), '% | potential', city['pot'][k],
          '| site max potential', max(s['pot'][k] for s in out_sites))
print('city turnout %:', city['turnout'], '| coalition', cb['coalition'], 'opp', cb['opposition'], 'other', city['other'])
refuse_missing_coords(out_sites)
write_map_data(payload)
