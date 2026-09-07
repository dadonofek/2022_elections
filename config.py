"""
Per-city / per-election configuration for the polling-station map pipeline.

To build the map for a DIFFERENT CITY (same election): copy this repo, drop in
that city's station<->address matching workbook, and edit the "city identity",
"inputs / outputs" and "bounding box" sections below. Nothing else should change.

To build for a DIFFERENT ELECTION: also update BLOCS and PARTY_NAMES.

Every pipeline script imports from here — there are no other hard-coded city
constants.
"""

# ----------------------------------------------------------------- city identity
CITY_HE   = 'חיפה'      # Hebrew name — used in geocoder queries and QA checks
CITY_SLUG = 'haifa'     # ascii slug — output filenames and the HTTP User-Agent

# --------------------------------------------------------------- inputs / outputs
MATCHING_XLSX = 'haifa_polling_station_matching.xlsx'  # station<->address workbook
OUT_HTML      = 'haifa_polling_map.html'               # generated single-file map

# ----------------------------------------- geographic bounding box (W, S, E, N)
# Constrains Nominatim, rejects stray geocodes, and scopes the Overpass query.
BBOX = (34.90, 32.74, 35.12, 32.87)

# ------------------------------------------------- national turnout (baseline)
# The map's turnout-delta mode measures every site against the NATIONAL turnout of
# the same election, not against the city's own average: measured against the city
# mean half the sites sit above it by construction and nothing reads as low, which
# hides the thing the map exists to show. build_data.py recomputes this from
# data/expb.csv when that file is present; this value is the documented fallback.
NATIONAL_TURNOUT = 70.63   # Knesset 25, all localities in expb.csv (4,794,593 / 6,788,804)

# The city average stays available as a secondary reference in the UI.

# ------------------------------------------------------------------- map view
# Fallback map center [lat, lon] and zoom. Leave MAP_CENTER = None to let
# build_data.py use the mean of all geocoded sites.
MAP_CENTER = None
MAP_ZOOM   = 12.4

# ------------------------------------------------- blocs (Knesset 25, Nov 2022)
# Party letter codes as they appear in the official results. National, not
# city-specific: reuse as-is for any city in the same election.
BLOCS = {
    'coalition':   ['מחל', 'שס', 'ג', 'ט'],          # coalition formed after 2022
    'zionist_opp': ['פה', 'כן', 'ל', 'אמת', 'מרצ'],
    'arab':        ['ום', 'עם', 'ד'],
}
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
