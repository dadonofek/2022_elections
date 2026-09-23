"""Import the observers' station list (xlsx) into config.STATION_LIST.

The list is the volunteer network's own spreadsheet of every polling station in the
coming election: one national sheet, plus one sheet per volunteering place ("בית שמש 1",
"בית שמש 2", ...) holding that place's stations. Every station sheet has the same
columns — Barzel, LocalityCode, Kalpi, KalpiAddress, KalpiLoc, Bazab, colorX, streets …
— and colorX is the network's risk classification of the station (Red / Orange /
Yellow / White / Gray).

    CITY=beit_shemesh python3 import_station_list.py "קלפיות ארצי מעודכן 150926 עם צבעים.xlsx"

Writes one CSV row per station of config.LOCALITY_CODE, and a small .meta.json beside
it. Only station facts are copied. The workbook also holds a status sheet with the
names of the people who run each volunteering place; it is never read, and the
workbook itself is not committed.

Rules, stated once here so the map can repeat them:
  * area  = the name of the per-place sheet the station appears in ('' if none).
  * risk  = that sheet's colorX. The per-place sheets are the working lists the
            volunteering places use, and where they disagree with the national sheet
            they were edited by hand; the national value is kept as risk_national.
"""
import csv, json, os, re, sys
import openpyxl
import config
from extract import clean_address, kalpi_str

STATION_HEADER = ('Barzel', 'LocalityCode', 'Kalpi', 'KalpiAddress', 'KalpiLoc', 'Bazab', 'colorX')
RISK = {'red': 'red', 'orange': 'orange', 'yellow': 'yellow', 'white': 'white', 'gray': 'gray', 'grey': 'gray'}
COLUMNS = ['kalpi', 'barzel', 'site', 'address', 'eligible', 'risk', 'risk_national',
           'area', 'streets', 'quarter', 'sub_quarter', 'stat_area']


def station_sheets(wb):
    """(title, header index, data rows) for every sheet laid out as a station list."""
    out = []
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        hdr = [str(h).strip() if h is not None else '' for h in rows[0]]
        if all(h in hdr for h in STATION_HEADER):
            idx = {h: i for i, h in enumerate(hdr) if h}
            out.append((ws.title, idx, [r for r in rows[1:] if r and r[idx['Barzel']] is not None]))
    return out


def risk_of(v, where):
    key = str(v or '').strip().lower()
    if key not in RISK:
        print(f'  ! unknown colorX {v!r} ({where}) — left blank')
        return ''
    return RISK[key]


def num(v):
    return '' if v in (None, '') else str(int(v))


def main(path):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    sheets = station_sheets(wb)
    if not sheets:
        raise SystemExit(f'{path}: no sheet has the station-list columns {STATION_HEADER}')
    # the national sheet spans many localities; every other station sheet is one place's
    def n_localities(s):
        return len({r[s[1]['LocalityCode']] for r in s[2]})
    national = max(sheets, key=lambda s: (n_localities(s), len(s[2])))
    places = [s for s in sheets if s is not national]
    loc = config.LOCALITY_CODE

    def mine(s):
        return [r for r in s[2] if r[s[1]['LocalityCode']] == loc]

    nat = {r[national[1]['Barzel']]: r for r in mine(national)}
    ni = national[1]
    area_of, row_of = {}, {}
    for title, idx, _ in places:
        for r in mine((title, idx, _)):
            b = r[idx['Barzel']]
            if b in area_of:
                raise SystemExit(f'station barzel {b} is in two sheets: {area_of[b]!r} and {title!r}')
            area_of[b], row_of[b] = title, (idx, r)

    # an empty per-place sheet named after the city is a place with no stations yet
    empty_areas = [t for t, idx, rows in places if not rows and t.startswith(config.CITY_HE)]

    out, differs = [], []
    for b in sorted(set(nat) | set(area_of)):
        idx, r = row_of.get(b, (ni, nat.get(b)))
        n = nat.get(b)
        risk_nat = risk_of(n[ni['colorX']], f'national {b}') if n is not None else ''
        risk = risk_of(r[idx['colorX']], f'{area_of.get(b, national[0])} {b}')
        kalpi = kalpi_str(r[idx['Kalpi']])
        if n is not None and risk != risk_nat:
            differs.append(kalpi)
        opt = lambda k: r[idx[k]] if k in idx else None
        out.append({
            'kalpi': kalpi, 'barzel': int(b),
            'site': str(r[idx['KalpiLoc']] or '').strip(),
            'address': clean_address(r[idx['KalpiAddress']]),
            'eligible': int(r[idx['Bazab']]),
            'risk': risk, 'risk_national': risk_nat,
            'area': area_of.get(b, ''),
            'streets': re.sub(r'\s+', ' ', str(opt('streets') or '')).strip(),
            'quarter': num(opt('Quarter')), 'sub_quarter': num(opt('SubQuarter')),
            'stat_area': num(opt('StatArea')),
        })
    if not out:
        raise SystemExit(f'{path}: no stations for locality {loc} ({config.CITY_HE})')
    out.sort(key=lambda s: [int(x) for x in re.findall(r'\d+', s['kalpi'])])

    os.makedirs(os.path.dirname(config.STATION_LIST), exist_ok=True)
    with open(config.STATION_LIST, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(out)

    base = os.path.basename(path)
    m = re.search(r'(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)', base)       # ...150926... = 15.9.26
    meta = {
        'source_file': base,
        'list_date': f'20{m.group(3)}-{m.group(2)}-{m.group(1)}' if m else None,
        'national_sheet': national[0],
        'area_sheets': {t: sum(1 for b in area_of if area_of[b] == t) for t, _, _ in places
                        if any(area_of[b] == t for b in area_of)},
        'empty_area_sheets': empty_areas,
        'risk_differs_from_national': sorted(differs, key=lambda k: [int(x) for x in re.findall(r'\d+', k)]),
    }
    json.dump(meta, open(meta_path(), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    from collections import Counter
    print(config.CITY_HE, '->', config.STATION_LIST, '|', len(out), 'stations')
    print('  areas:', dict(Counter(s['area'] or '(none)' for s in out)), '| empty sheets:', empty_areas)
    print('  risk:', dict(Counter(s['risk'] for s in out)))
    print('  risk differs from the national sheet at', len(differs), 'stations:', meta['risk_differs_from_national'])
    print('  list date:', meta['list_date'])


def meta_path():
    return os.path.splitext(config.STATION_LIST)[0] + '.meta.json'


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
