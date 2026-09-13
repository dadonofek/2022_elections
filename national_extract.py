"""Nationwide stage 1 — flatten the two official CEC files into data/national/raw.json,
for ALL localities at once (the per-city extract.py handles one locality; this is its
country-wide counterpart, needed for the third tab — 'כל הארץ').

Two layers come out of it, matching the shape PRODUCT_DECISIONS.md §9 sketched before
the whole-country tab was scoped:

  'localities'  every locality in expb.csv (1,216), aggregated to one row each —
                results, turnout, blocs — with NO address/coordinate. This is the
                zoomed-out layer: one dot per town, drawable today with no geocoding.

  'sites'       one row per (locality, ריכוז) that the place file gives an address
                for — 4,205 of them, the same 'cec' extraction extract.py already
                uses for Beit Shemesh, just run over every locality instead of one.
                This is the zoom-in layer, and it is what needs coordinates.

Station-level rows that have results but no address (834 of 12,545, mostly small
localities the place file only partly covers, plus the 'מעטפות חיצוניות' — double
envelopes/external ballots, not a real place) are folded into their locality's
totals but do not produce a site.

Next step is geocoding the 3,762 unique (locality, address) pairs in 'sites' — see
geocode_national.py. That step needs Nominatim, which this sandboxed session's
network policy blocks (tested directly: 403/EGRESS_BLOCKED on nominatim, data.gov.il,
govmap, geoapify, odata.org.il). It is meant to run on a machine with normal internet
access; see README.md, 'Nationwide — in progress'.
"""
import json, re, csv, os, openpyxl, config

R_NUM   = re.compile(r'(-?[0-9]+\.?[0-9]*)')
R_SPACE = re.compile(r'\s{2,}')

def clean_address(a):
    a = str(a or '').replace(',', ' ')
    return R_SPACE.sub(' ', R_NUM.sub(r' \1 ', a)).strip()

def kalpi_str(v):
    return ('%g' % v) if isinstance(v, (int, float)) else str(v).strip()

def kalpi_sort(k):
    return [int(x) for x in re.findall(r'\d+', k)] or [0]

OUT_DIR = 'data/national'
os.makedirs(OUT_DIR, exist_ok=True)

# --------------------------------------------------------------- load both sources
with open(config.EXPB_CSV, encoding='utf-8-sig') as fh:
    exp_rows = list(csv.DictReader(fh))
skip = {'סמל ועדה', 'ברזל', 'שם ישוב', 'סמל ישוב', 'קלפי', 'ריכוז', 'שופט',
        'בזב', 'מצביעים', 'פסולים', 'כשרים'}
parties = [c for c in exp_rows[0] if c and c not in skip]

results, loc_names = {}, {}
for r in exp_rows:
    loc = int(r['סמל ישוב'])
    loc_names[loc] = r['שם ישוב']
    results[(loc, r['קלפי'].strip())] = {
        'barzel': int(r['ברזל']), 'rikuz': str(r['ריכוז']).strip(),
        'eligible': int(r['בזב']), 'voters': int(r['מצביעים']),
        'invalid': int(r['פסולים']), 'valid': int(r['כשרים']),
        'parties': {p: int(r[p] or 0) for p in parties},
    }

wb = openpyxl.load_workbook(config.KALPI_PLACES_XLSX, data_only=True)
ws = wb['DataSheet'] if 'DataSheet' in wb.sheetnames else wb.active
rows = list(ws.iter_rows(values_only=True))
hdr = {h: n for n, h in enumerate(rows[0])}
places = {}
for r in rows[1:]:
    if r[hdr['סמל ישוב בחירות']] is None:
        continue
    loc = int(r[hdr['סמל ישוב בחירות']])
    places[(loc, kalpi_str(r[hdr['סמל קלפי']]))] = {
        'rikuz': str(r[hdr['סמל רכוז']]).strip(),
        'site': str(r[hdr['מקום קלפי']] or '').strip(),
        'address': clean_address(r[hdr['כתובת קלפי']]),
    }

# ------------------------------------------------------------------ locality layer
loc_agg = {loc: {'code': loc, 'name': name, 'eligible': 0, 'voters': 0,
                  'invalid': 0, 'valid': 0, 'parties': {p: 0 for p in parties},
                  'n_stations': 0}
           for loc, name in loc_names.items()}
for (loc, _), res in results.items():
    a = loc_agg[loc]
    a['eligible'] += res['eligible']; a['voters'] += res['voters']
    a['invalid'] += res['invalid']; a['valid'] += res['valid']
    a['n_stations'] += 1
    for p, v in res['parties'].items(): a['parties'][p] += v
localities = sorted(loc_agg.values(), key=lambda a: -a['eligible'])

# ------------------------------------------------------------------------ site layer
# One row per (locality, rikuz) with an address; stations agree on rikuz->address
# within a locality the same way extract.py's extract_cec() asserts per-city.
sites, clashes, no_address = {}, [], 0
for (loc, kalpi), res in results.items():
    p = places.get((loc, kalpi))
    if not p or not p['address']:
        no_address += 1
        continue
    key = (loc, p['rikuz'])
    if key not in sites:
        sites[key] = {'locality': loc, 'locality_name': loc_names[loc],
                       'rikuz': p['rikuz'], 'name': p['site'], 'address': p['address'],
                       'kalpiot': [], 'eligible': 0, 'voters': 0, 'invalid': 0,
                       'valid': 0, 'parties': {pt: 0 for pt in parties}}
    s = sites[key]
    if (s['name'], s['address']) != (p['site'], p['address']):
        clashes.append((loc, p['rikuz']))
        continue
    s['kalpiot'].append(kalpi)
    s['eligible'] += res['eligible']; s['voters'] += res['voters']
    s['invalid'] += res['invalid']; s['valid'] += res['valid']
    for pt, v in res['parties'].items(): s['parties'][pt] += v

if clashes:
    print(f'skipped {len(clashes)} station(s) whose rikuz disagrees on name/address '
          f'within its locality (kept in locality totals, not in any site):', clashes[:10])

site_list = []
for i, ((loc, rikuz), s) in enumerate(sorted(sites.items(), key=lambda kv: (kv[0][0], kalpi_sort(kv[0][1]))), 1):
    s['id'] = i
    s['n_kalpi'] = len(s['kalpiot'])
    s['kalpi_list'] = ', '.join(sorted(s['kalpiot'], key=kalpi_sort))
    del s['kalpiot']
    site_list.append(s)

json.dump({'localities': localities, 'sites': site_list},
          open(os.path.join(OUT_DIR, 'raw.json'), 'w'), ensure_ascii=False, indent=1)

# ------------------------------------------------------------------------- report
tot_elig = sum(a['eligible'] for a in localities)
tot_vot = sum(a['voters'] for a in localities)
addr_pairs = {(s['locality_name'], s['address']) for s in site_list}
print('localities:', len(localities), '| stations:', len(results))
print('sites (with address):', len(site_list),
      '| unique (locality, address) pairs to geocode:', len(addr_pairs))
print('stations without a usable address (folded into locality totals only):', no_address)
print('eligible', tot_elig, 'voters', tot_vot, 'turnout', round(100 * tot_vot / tot_elig, 2))
print('->', os.path.join(OUT_DIR, 'raw.json'))
