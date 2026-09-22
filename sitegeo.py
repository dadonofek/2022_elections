"""What every map's data stage shares: reading a city's pipeline files, placing a site
on the map, and the checks no map may skip. Used by build_data.py (the analysis
profile) and build_volunteer_data.py (the volunteer profile)."""
import csv, json, math, os
from collections import defaultdict
import config


def load(name, default=None):
    """A city part-way through the pipeline is missing later stages' files; treat
    them as empty so the no-coordinates check below reports what is actually
    wrong instead of a traceback."""
    path = config.data(name)
    if not os.path.exists(path):
        if default is None:
            raise SystemExit(f'{path} is missing — run extract.py for {config.CITY_SLUG} first')
        print(f'note: {path} is missing, treating it as empty')
        return default
    return json.load(open(path))


def precision(g):
    if not g: return 'none'
    if g.get('snapped'): return 'venue'
    at = (g.get('addresstype') or '') + '|' + (g.get('osm_type') or '')
    if 'house_number' in at or 'building' in at: return 'house'
    if 'road' in at or 'residential' in at or 'tertiary' in at or 'secondary' in at or 'primary' in at or 'unclassified' in at or 'living_street' in at or 'pedestrian' in at:
        return 'street'
    return 'place'


def site_geo(site, address, geo, snaps):
    """The geocode of one site: the named OSM building it snapped to when there is one,
    else its address's geocode (None when it has neither)."""
    g = geo.get(address)
    sn = snaps.get(f'{site}||{address}')
    if sn:
        g = dict(g or {}, lat=sn['lat'], lon=sn['lon'], snapped=True,
                 display=sn['osm_name'] + ' · ' + (g or {}).get('display', ''),
                 osm_venue=sn['osm_name'])
    return g


def spread_colocated(sites):
    """Sites that geocoded to the identical point are nudged a few metres apart so
    their markers stay separable. Returns how many were moved."""
    at_point = defaultdict(list)
    for st in sites:
        if st['lat'] is not None:
            at_point[(round(st['lat'], 6), round(st['lon'], 6))].append(st)
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
    return spread


def map_center(sites):
    """config.MAP_CENTER, else the mean of the geocoded sites."""
    pts = [(s['lat'], s['lon']) for s in sites if s['lat'] is not None]
    return list(config.MAP_CENTER) if config.MAP_CENTER else (
        [round(sum(p[0] for p in pts) / len(pts), 5),
         round(sum(p[1] for p in pts) / len(pts), 5)] if pts else [32.0, 35.0])


def refuse_missing_coords(sites):
    """A site with no coordinates has no marker, so a partly-geocoded city renders as a
    map that quietly omits part of itself. Refuse to WRITE that, so build_map.py cannot
    pick up a stale half-built file either. ALLOW_MISSING_COORDS=1 builds one anyway."""
    no_coords = [s['name'] for s in sites if s['lat'] is None]
    if no_coords and not os.environ.get('ALLOW_MISSING_COORDS'):
        raise SystemExit(
            f'\n{len(no_coords)} of {len(sites)} sites have no coordinates, so they would '
            f'have no marker:\n  ' + '\n  '.join(no_coords[:15]) +
            ('\n  ...' if len(no_coords) > 15 else '') +
            f'\nNothing was written. Run geocode.py / geocode_retry.py for {config.CITY_SLUG} '
            'first, or set ALLOW_MISSING_COORDS=1 to build the map anyway.')


def national_turnout():
    """National turnout is the analysis map's primary delta baseline. Recompute it from
    the official national per-station file when it is available so the number is
    derived rather than asserted; fall back to the documented constant otherwise."""
    path = config.EXPB_CSV
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


def write_map_data(payload):
    blob = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    open(config.data('map_data.json'), 'w', encoding='utf-8').write(blob)
    print('json size KB:', round(len(blob.encode())/1024))
