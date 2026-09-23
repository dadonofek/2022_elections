"""Stage 6 for the volunteer profile — data/<city>/map_data.json for a map that
election-day volunteers use to choose where to register.

Joins the coming election's stations (the observers' list, via extract.py) to their
coordinates and groups them into sites, one marker per building. Each site carries:

  * area  — the volunteering place whose list the station is on ("בית שמש 1" ...);
  * risk  — the observers' risk colour of the station, and for the site the most
            severe colour among its stations (a building with one red station needs
            the red station's volunteers);
  * h22   — when the same building was a polling site in 2022 (same address, or the
            same place name nearby), what it recorded then: turnout and the three
            largest lists. Plain background facts — nothing on this map is coloured
            by a party, and stations were renumbered since, so this is per BUILDING.

Called by build_data.py when config.PROFILE == 'volunteer'.
"""
import json, math, os, re
from collections import Counter
import config
from sitegeo import (load, precision, site_geo, spread_colocated, map_center,
                     refuse_missing_coords, national_turnout, write_map_data)

RISK_ORDER = ('red', 'orange', 'yellow', 'white', 'gray')     # most severe first
RANK = {r: i for i, r in enumerate(RISK_ORDER)}
NAME_MATCH_M = 600      # a 2022 site matched by place name alone must be this close


def kalpi_key(k):
    return [int(x) for x in re.findall(r'\d+', k)]


def dist_m(a, b):
    dy = (a[0] - b[0]) * 111320
    dx = (a[1] - b[1]) * 111320 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def history_sites(history):
    """The 2022 sites of the locality, each aggregated from its stations."""
    by = {}
    for s in history['stations']:
        st = by.setdefault((s['site'], s['address']), {
            'name': s['site'], 'address': s['address'], 'kalpiot': [],
            'eligible': 0, 'voters': 0, 'valid': 0, 'parties': Counter()})
        st['kalpiot'].append(s['kalpi'])
        for f in ('eligible', 'voters', 'valid'):
            st[f] += s[f]
        st['parties'].update(s['parties'])
    return list(by.values())


def match_2022(name, address, here, h_sites, geo):
    """The 2022 site in the same building: same address, else the same place name at a
    nearby address (renamed streets and re-worded addresses are common; a generic name
    such as "גן ילדים" recurring elsewhere in the city is not the same building)."""
    same_addr = [h for h in h_sites if h['address'] == address]
    if len(same_addr) == 1:
        return same_addr[0], 'address+name' if same_addr[0]['name'] == name else 'address'
    same_name = [h for h in h_sites if h['name'] == name]
    if len(same_name) == 1 and here:
        g = geo.get(same_name[0]['address'])
        if g and dist_m(here, (g['lat'], g['lon'])) <= NAME_MATCH_M:
            return same_name[0], 'name'
    return None, None


def h22_summary(h, match):
    top = sorted(((p, v) for p, v in h['parties'].items() if v > 0), key=lambda x: -x[1])[:3]
    return {
        'name': h['name'], 'address': h['address'], 'match': match,
        'kalpiot': sorted(h['kalpiot'], key=kalpi_key),
        'eligible': h['eligible'], 'voters': h['voters'], 'valid': h['valid'],
        'turnout': round(100 * h['voters'] / h['eligible'], 2) if h['eligible'] else None,
        'top': [[p, v, round(100 * v / h['valid'], 1)] for p, v in top] if h['valid'] else [],
    }


def geo_source(g):
    if not g: return None
    if g.get('snapped'): return 'osm-venue'
    return {'same-street': 'same-street', 'overture': 'overture'}.get(g.get('query_stage'), 'nominatim')


def main():
    raw = load('raw.json')
    geo = load('geocache.json', {})
    snaps = load('osm_snaps.json', {})
    meta_file = os.path.splitext(config.STATION_LIST)[0] + '.meta.json'     # import_station_list.py
    meta = json.load(open(meta_file, encoding='utf-8')) if os.path.exists(meta_file) else {}
    stations, history = raw['stations'], raw['history']
    h_sites = history_sites(history)

    # --- sites: one per (place name, address), in station-number order ------------
    grouped = {}
    for s in sorted(stations, key=lambda s: kalpi_key(s['kalpi'])):
        grouped.setdefault((s['site'], s['address']), []).append(s)

    sites, matched = [], set()
    for i, ((name, address), group) in enumerate(grouped.items()):
        g = site_geo(name, address, geo, snaps)
        here = (g['lat'], g['lon']) if g else None
        risks = Counter(s['risk'] for s in group)
        h, how = match_2022(name, address, here, h_sites, geo)
        if h is not None:
            matched.add((h['name'], h['address']))
        sites.append({
            'id': i, 'name': name, 'address': address,
            'lat': here[0] if here else None, 'lon': here[1] if here else None,
            'geo_precision': precision(g), 'geo_display': g['display'] if g else None,
            'geo_source': geo_source(g),
            'osm_venue': (g or {}).get('osm_venue'),
            'area': group[0]['area'],
            'risk': min((s['risk'] for s in group if s['risk'] in RANK), key=RANK.get, default=''),
            'risk_counts': {r: risks[r] for r in RISK_ORDER if risks[r]},
            'eligible': sum(s['eligible'] for s in group),
            'n_kalpi': len(group),
            'kalpiot': [{
                'kalpi': s['kalpi'], 'barzel': s['barzel'], 'eligible': s['eligible'],
                'risk': s['risk'], 'streets': s['streets'],
                # only where the area's list overrides the national list's colour
                **({'risk_national': s['risk_national']}
                   if s['risk_national'] and s['risk_national'] != s['risk'] else {}),
            } for s in group],
            'h22': h22_summary(h, how) if h is not None else None,
        })

    spread = spread_colocated(sites)

    # --- the city ----------------------------------------------------------------
    area_keys = sorted({s['area'] for s in sites if s['area']}, key=kalpi_key)
    def tally(ss):
        rk = Counter(k['risk'] for s in ss for k in s['kalpiot'])
        return {'n_kalpi': sum(s['n_kalpi'] for s in ss), 'n_sites': len(ss),
                'eligible': sum(s['eligible'] for s in ss),
                'risk_kalpi': {r: rk[r] for r in RISK_ORDER if rk[r]}}
    h_elig = sum(s['eligible'] for s in history['stations'])
    h_vot = sum(s['voters'] for s in history['stations'])
    nat, nat_src = national_turnout()
    city = {
        'name': config.CITY_HE, 'election': config.ELECTION_HE,
        'list_date': meta.get('list_date'), 'list_source': meta.get('source_file'),
        'center': map_center(sites), 'zoom': config.MAP_ZOOM,
        **tally(sites),
        'risk_sites': {r: n for r in RISK_ORDER if (n := sum(1 for s in sites if s['risk'] == r))},
        'areas': [{'key': a, 'desc': config.AREAS.get(a, ''),
                   **tally([s for s in sites if s['area'] == a])} for a in area_keys],
        'empty_areas': [{'key': a, 'desc': config.AREAS.get(a, '')}
                        for a in meta.get('empty_area_sheets', [])],
        'unassigned': tally([s for s in sites if not s['area']]),
        'risk_differs': meta.get('risk_differs_from_national', []),
        'h22': {
            'election': history['election'],
            'turnout': round(100 * h_vot / h_elig, 2) if h_elig else None,
            'national_turnout': nat,
            'n_kalpi': len(history['stations']), 'n_sites': len(h_sites),
            'sites_matched': sum(1 for s in sites if s['h22']),
            'sites_gone': [f"{h['name']} ({h['address']})" for h in h_sites
                           if (h['name'], h['address']) not in matched],
        },
    }
    payload = {'profile': 'volunteer', 'city': city, 'sites': sites,
               'party_names': config.PARTY_NAMES}

    print('profile: volunteer |', config.CITY_HE, '|', config.ELECTION_HE, '| list of', city['list_date'])
    print('sites:', len(sites), '| kalpiot:', city['n_kalpi'], '| eligible:', city['eligible'])
    print('areas:', {a['key']: (a['n_kalpi'], a['n_sites']) for a in city['areas']},
          '| empty:', [a['key'] for a in city['empty_areas']], '| unassigned:', city['unassigned']['n_kalpi'])
    print('risk (kalpiot):', city['risk_kalpi'], '| risk (sites):', city['risk_sites'])
    print('precision:', Counter(s['geo_precision'] for s in sites),
          '| source:', Counter(s['geo_source'] for s in sites))
    print('co-located sites spread apart:', spread)
    print('2022 history:', city['h22']['sites_matched'], 'of', len(sites), 'sites matched',
          Counter(s['h22']['match'] for s in sites if s['h22']),
          '| 2022 sites with no 2026 site:', city['h22']['sites_gone'])
    print('2022 turnout %:', city['h22']['turnout'], '| national', nat, 'from', nat_src)
    refuse_missing_coords(sites)
    write_map_data(payload)


if __name__ == '__main__':
    main()
