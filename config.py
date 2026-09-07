"""
Per-city / per-election configuration for the polling-station map pipeline.

ONE REPO, MANY CITIES. Every city is an entry in CITIES below; the one being
built is chosen by the CITY environment variable and defaults to Haifa:

    ./build.sh                        # Haifa
    CITY=beit_shemesh ./build.sh      # Beit Shemesh

Each city gets its own cache directory under data/ (data/<slug>/) so the
geocode, the Overpass snaps and the built map_data of one city never collide
with another's. The two official national inputs — data/expb.csv (per-station
results) and data/kalpiplaces_25.xlsx (per-station place and address) — are
shared by every city.

To ADD A CITY: add an entry to CITIES with its locality code, bounding box and
output filename, then run `CITY=<slug> ./build.sh`. Nothing else changes —
site names and addresses come out of the national CEC place file, so no
hand-built matching workbook is needed.

To build for a DIFFERENT ELECTION: also update BLOCS, CAMPS and PARTY_NAMES,
and point EXPB_CSV / KALPI_PLACES_XLSX at that election's files.

Every pipeline script imports from here — there are no other hard-coded city
constants.
"""
import os

# ------------------------------------------------------------ shared national inputs
# Central Elections Committee, Knesset 25 (1 Nov 2022).
EXPB_CSV           = 'data/expb.csv'             # results per polling station, all localities
KALPI_PLACES_XLSX  = 'data/kalpiplaces_25.xlsx'  # station -> site ("ריכוז"), place name, address

# ----------------------------------------------------------------------- the cities
# locality  — 'סמל ישוב' in expb.csv / 'סמל ישוב בחירות' in the place file.
# bbox      — (W, S, E, N); constrains Nominatim, rejects stray geocodes, scopes Overpass.
# center    — map center [lat, lon]; None means "the mean of the geocoded sites".
# extract   — where stations, site names and addresses come from:
#               'cec'      the national place file (the default; works for any city)
#               'workbook' a hand-built matching workbook, named by 'matching_xlsx'
#             Haifa was built from a workbook before the national place file was
#             found, and stays on it: the workbook carries a per-site match
#             confidence and method that the map displays. The two agree — see
#             "Provenance" in README.md.
CITIES = {
    'haifa': {
        'name_he':      'חיפה',
        'locality':     4000,
        'bbox':         (34.90, 32.74, 35.12, 32.87),
        'center':       None,
        'zoom':         12.4,
        'out_html':     'haifa_polling_map.html',
        'extract':      'workbook',
        'matching_xlsx': 'haifa_polling_station_matching.xlsx',
        'source_note':  'קובץ ההתאמות <code>haifa_polling_station_matching.xlsx</code>, '
                        'המבוסס בעיקר על הודעת הבחירות הרשמית של עיריית חיפה ועל שם אתר הקלפי',
        'match_note':   'ההתאמה בין קלפי לכתובת נשענת על מסמכי עירייה משנים סמוכות',
    },
    'beit_shemesh': {
        'name_he':      'בית שמש',
        'locality':     2610,
        'bbox':         (34.94, 31.67, 35.04, 31.79),
        'center':       None,
        'zoom':         13.2,
        'out_html':     'beit_shemesh_polling_map.html',
        'extract':      'cec',
        'source_note':  'קובץ מקומות הקלפי הרשמי של ועדת הבחירות המרכזית '
                        '(<code>kalpiplaces_kalpieslist_27-10.xlsx</code>), שבו לכל קלפי '
                        'רשומים מספר הריכוז, שם המקום והכתובת',
        'match_note':   'שיוך הקלפי לאתר ולכתובת לקוח מקובץ מקומות הקלפי של ועדת הבחירות '
                        'המרכזית עצמה, ולא מהתאמה שנעשתה בדיעבד',
    },
}

CITY_SLUG = os.environ.get('CITY', 'haifa')
if CITY_SLUG not in CITIES:
    raise SystemExit(f'unknown CITY={CITY_SLUG!r}; known: {", ".join(sorted(CITIES))}')
_c = CITIES[CITY_SLUG]

# ----------------------------------------------------------------- city identity
CITY_HE       = _c['name_he']      # Hebrew name — geocoder queries, QA checks, UI
LOCALITY_CODE = _c['locality']     # 'סמל ישוב' in the official files
SOURCE_NOTE   = _c['source_note']  # provenance line shown in the map's "על הנתונים" panel
MATCH_NOTE    = _c['match_note']   # how station->address was established, in the same panel

# --------------------------------------------------------------- inputs / outputs
EXTRACT       = _c['extract']                   # 'cec' | 'workbook'
MATCHING_XLSX = _c.get('matching_xlsx')         # only used when EXTRACT == 'workbook'
OUT_HTML      = _c['out_html']                  # generated single-file map

# Per-city cache directory. Every stage reads and writes here, so two cities
# never share a geocode or an Overpass reply.
DATA_DIR = os.path.join('data', CITY_SLUG)
os.makedirs(DATA_DIR, exist_ok=True)

def data(name):
    """Path to one of this city's pipeline files, e.g. data('geocache.json')."""
    return os.path.join(DATA_DIR, name)

# ----------------------------------------- geographic bounding box (W, S, E, N)
BBOX = _c['bbox']

# ------------------------------------------------- national turnout (baseline)
# The map's turnout-delta mode measures every site against the NATIONAL turnout of
# the same election, not against the city's own average: measured against the city
# mean half the sites sit above it by construction and nothing reads as low, which
# hides the thing the map exists to show. build_data.py recomputes this from
# EXPB_CSV when that file is present; this value is the documented fallback.
NATIONAL_TURNOUT = 70.63   # Knesset 25, all localities in expb.csv (4,794,593 / 6,788,804)

# The city average stays available as a secondary reference in the UI.

# ------------------------------------------------------------------- map view
# Fallback map center [lat, lon] and zoom. center = None lets build_data.py use
# the mean of all geocoded sites.
MAP_CENTER = _c['center']
MAP_ZOOM   = _c['zoom']

# ------------------------------------------------- blocs (Knesset 25, Nov 2022)
# Party letter codes as they appear in the official results. National, not
# city-specific: reuse as-is for any city in the same election.
BLOCS = {
    'coalition':   ['מחל', 'שס', 'ג', 'ט'],          # coalition formed after 2022
    'zionist_opp': ['פה', 'כן', 'ל', 'אמת', 'מרצ'],
    'arab':        ['ום', 'עם', 'ד'],
}

# ------------------------------------- camps (party groups that are not blocs)
# A CAMP is a group the map can count for that the bloc partition does not name.
# הדמוקרטים is a subset of the broad opposition (העבודה and מרצ ran as two separate
# lists in this election and merged into one party only in 2024), so it is carried
# ALONGSIDE the blocs — never instead of one — and it is always present: its own
# option in the potential-target select, header tile, sort, table columns and bars.
# The blocs stay exactly as they were; a camp is added to the list, not swapped in.
#
#   'parties'   — the letter codes to sum.
#   'inside'    — the bloc key this camp overlaps, so the UI can say which slice of
#                 the partition it is part of.
#   'note'      — the one-line caveat, shown under the select and in the site card.
#                 Keep it SHORT: the site card shares a phone screen with the map.
#   'note_long' — the full version, shown only in the "על הנתונים" panel.
#   'short'     — optional, for the header tile, whose label may not wrap.
CAMPS = {
    'dem': {'name': 'הדמוקרטים', 'parties': ['אמת', 'מרצ'], 'inside': 'opposition',
            'note': 'העבודה ומרצ, שהתאחדו למפלגה אחת ב-2024',
            'note_long': 'העבודה ומרצ רצו ב-2022 כשתי רשימות נפרדות, ומרצ לא עברה את '
                         'אחוז החסימה; הן התאחדו למפלגה אחת ב-2024'},
}
# Which group the potential points at when the map opens: a camp key above, a bloc
# ('coalition' / 'opposition' / 'other'), or 'none' for unattributed non-voters.
DEFAULT_POT_TARGET = 'dem'

PARTY_NAMES = {
    'מחל': 'הליכוד', 'שס': 'ש"ס', 'ג': 'יהדות התורה', 'ט': 'הציונות הדתית',
    'פה': 'יש עתיד', 'כן': 'המחנה הממלכתי', 'ל': 'ישראל ביתנו', 'אמת': 'העבודה',
    'מרצ': 'מרצ', 'ום': 'חד"ש-תע"ל', 'עם': 'רע"ם', 'ד': 'בל"ד',
    'י': 'הבית היהודי', 'ז': 'עצמה כלכלית', 'נר': 'כל ישראל אחים', 'ק': 'צומת',
}

# ------------------------------------------------------------- derived helpers
UA = f'{CITY_SLUG}-polling-map/1.0 (research)'

def viewbox_str():            # Nominatim viewbox order: "W,S,E,N"
    return ','.join(map(str, BBOX))

def overpass_bbox_str():      # Overpass bbox order: "S,W,N,E"
    w, s, e, n = BBOX
    return f'{s},{w},{n},{e}'

def in_bbox(lat, lon):
    w, s, e, n = BBOX
    return s <= lat <= n and w <= lon <= e
