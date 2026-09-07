"""Stage 1 — flatten the official inputs into data/<city>/raw.json.

Two sources produce the same shape, chosen by config.EXTRACT:

  'cec'       the two national Central Elections Committee files. expb.csv gives
              every station's results, iron number and electorate; the place file
              (kalpiplaces) gives each station's site ("ריכוז"), place name and
              address. Works for any locality — no per-city preparation.

  'workbook'  a hand-built station<->address workbook (config.MATCHING_XLSX),
              which also carries a per-site match confidence and method. Haifa
              was built this way before the national place file was found and
              stays on it; the two agree on 421 of its 424 addresses and on all
              140 site groupings (see README, "Provenance").
"""
import json, re, csv, config

R_NUM   = re.compile(r'(-?[0-9]+\.?[0-9]*)')
R_SPACE = re.compile(r'\s{2,}')


def clean_address(a):
    """'הנורית,16 ' -> 'הנורית 16'. The place file separates street and house
    number with a comma and pads with stray spaces."""
    a = str(a or '').replace(',', ' ')
    return R_SPACE.sub(' ', R_NUM.sub(r' \1 ', a)).strip()


def kalpi_str(v):
    """Station numbers are '47.1' / '58' and arrive as floats from openpyxl."""
    return ('%g' % v) if isinstance(v, (int, float)) else str(v).strip()


# --------------------------------------------------------------------- sources
def read_expb(locality):
    """Official per-station results for one locality, keyed by station number."""
    with open(config.EXPB_CSV, encoding='utf-8-sig') as fh:
        rows = [r for r in csv.DictReader(fh) if int(r['סמל ישוב']) == locality]
    if not rows:
        raise SystemExit(f'no stations for locality {locality} in {config.EXPB_CSV}')
    skip = {'סמל ועדה', 'ברזל', 'שם ישוב', 'סמל ישוב', 'קלפי', 'ריכוז', 'שופט',
            'בזב', 'מצביעים', 'פסולים', 'כשרים'}
    parties = [c for c in rows[0] if c and c not in skip]
    return {r['קלפי'].strip(): {
        'kalpi': r['קלפי'].strip(),
        'barzel': int(r['ברזל']),
        'rikuz': str(r['ריכוז']).strip(),
        'eligible': int(r['בזב']),
        'voters': int(r['מצביעים']),
        'invalid': int(r['פסולים']),
        'valid': int(r['כשרים']),
        'parties': {p: int(r[p] or 0) for p in parties},
    } for r in rows}


def read_places(locality):
    """Official station -> (site number, place name, address) for one locality."""
    import openpyxl
    ws = openpyxl.load_workbook(config.KALPI_PLACES_XLSX, data_only=True)['DataSheet']
    rows = list(ws.iter_rows(values_only=True))
    i = {h: n for n, h in enumerate(rows[0])}
    out = {}
    for r in rows[1:]:
        if r[i['סמל ישוב בחירות']] != locality:
            continue
        out[kalpi_str(r[i['סמל קלפי']])] = {
            'rikuz': str(r[i['סמל רכוז']]).strip(),
            'site': str(r[i['מקום קלפי']] or '').strip(),
            'address': clean_address(r[i['כתובת קלפי']]),
        }
    if not out:
        raise SystemExit(f'no stations for locality {locality} in {config.KALPI_PLACES_XLSX}')
    return out


# ------------------------------------------------------------------ extractors
def extract_cec():
    results, places = read_expb(config.LOCALITY_CODE), read_places(config.LOCALITY_CODE)

    only_results = sorted(set(results) - set(places))
    only_places  = sorted(set(places) - set(results))
    if only_results:
        raise SystemExit(f'stations with results but no place: {only_results}')
    if only_places:
        print('stations listed as places but absent from the results (ignored):', only_places)

    # The two files carry the site grouping independently ('ריכוז' in the results,
    # 'סמל רכוז' in the place file). Disagreement means one of them is not the
    # election we think it is, so refuse rather than guess.
    clash = [k for k in results if results[k]['rikuz'] != places[k]['rikuz']]
    if clash:
        raise SystemExit(f'site number disagrees between the two files for: {clash[:10]}')

    stations = []
    for k, res in results.items():
        p = places[k]
        stations.append({
            'kalpi': k, 'barzel': res['barzel'], 'rikuz': p['rikuz'],
            'site': p['site'], 'address': p['address'],
            # The place file IS the Elections Committee's own station->place
            # table, not a match against one, so there is nothing to be unsure of.
            'confidence': 'גבוה מאוד',
            'eligible': res['eligible'], 'voters': res['voters'],
            'invalid': res['invalid'], 'valid': res['valid'],
            'parties': res['parties'],
        })

    # One site per 'ריכוז'. A site whose stations disagree on name or address
    # would break the aggregation in build_data.py, so assert they do not.
    sites, seen = [], {}
    for s in sorted(stations, key=kalpi_sort):
        key = s['rikuz']
        if key in seen:
            st = seen[key]
            if (st['name'], st['address']) != (s['site'], s['address']):
                raise SystemExit(f'site {key} has two names/addresses: '
                                 f'{(st["name"], st["address"])} vs {(s["site"], s["address"])}')
            st['kalpiot'].append(s['kalpi'])
            continue
        st = {'id': len(sites) + 1, 'name': s['site'], 'address': s['address'],
              'rikuz': key, 'kalpiot': [s['kalpi']], 'confidence': 'גבוה מאוד',
              'method': 'מספר הריכוז בקובץ מקומות הקלפי הרשמי',
              'source': 'ועדת הבחירות המרכזית — קובץ מקומות הקלפי לכנסת ה-25'}
        seen[key] = st
        sites.append(st)
    for st in sites:
        st['n_kalpi'] = len(st['kalpiot'])
        st['kalpi_list'] = ', '.join(st['kalpiot'])
        del st['kalpiot']
    return stations, sites


def extract_workbook():
    import openpyxl
    wb = openpyxl.load_workbook(config.MATCHING_XLSX, data_only=False)

    rows = list(wb['קלפיות'].iter_rows(values_only=True))
    hdr = rows[1]
    idx = {h: i for i, h in enumerate(hdr)}
    party_cols = [h for h in hdr if isinstance(h, str) and h.startswith('מפלגה ')]

    stations = []
    for r in rows[2:]:
        if not r or r[0] is None: continue
        stations.append({
            'kalpi': str(r[idx['מספר קלפי']]),
            'barzel': r[idx['מספר ברזל']],
            'site': r[idx['שם אתר']],
            'address': r[idx['כתובת מועמדת']],
            'confidence': r[idx['רמת ביטחון']],
            'eligible': r[idx['בעלי זכות']],
            'voters': r[idx['מצביעים']],
            'invalid': r[idx['פסולים']],
            'valid': r[idx['כשרים']],
            'parties': {h.replace('מפלגה ', ''): (r[idx[h]] or 0) for h in party_cols},
        })

    arows = list(wb['אתרים'].iter_rows(values_only=True))
    sites = [{'id': r[0], 'name': r[1], 'address': r[2], 'n_kalpi': r[3],
              'kalpi_list': r[4], 'confidence': r[6], 'method': r[7], 'source': r[8]}
             for r in arows[2:] if r and r[0] is not None]
    print('party cols', len(party_cols), party_cols[:5])
    return stations, sites


def kalpi_sort(s):
    return [int(x) for x in re.findall(r'\d+', s['kalpi'])]


# ------------------------------------------------------------------------ main
stations, sites = extract_cec() if config.EXTRACT == 'cec' else extract_workbook()
stations.sort(key=kalpi_sort)
json.dump({'stations': stations, 'sites': sites},
          open(config.data('raw.json'), 'w'), ensure_ascii=False, indent=1)

print(config.CITY_HE, '| source:', config.EXTRACT, '->', config.data('raw.json'))
print('stations', len(stations), 'sites', len(sites))
addrs = sorted({s['address'] for s in stations if s['address']})
print('unique addresses', len(addrs))
print('missing address', sum(1 for s in stations if not s['address']))
tot_elig = sum(s['eligible'] or 0 for s in stations)
tot_vot = sum(s['voters'] or 0 for s in stations)
print('eligible', tot_elig, 'voters', tot_vot, 'turnout', round(100 * tot_vot / tot_elig, 2))
