# מפת הקלפיות של חיפה — הכנסת ה-25

A single-file, self-contained HTML map of all **424 polling stations** in Haifa in the
November 2022 Knesset election, grouped into the **140 polling sites** where they operated,
with official results, turnout and a full per-party breakdown for every station.

Open **`haifa_polling_map.html`** in any browser — no server, no build step, no API key.
The file embeds Leaflet and the whole dataset; only the OpenStreetMap background tiles
need an internet connection.

**Live:** <https://dadonofek.github.io/2022_elections/>

![the map](screenshot.png)

## What the map shows

* **One marker per polling site.** Marker **area** is proportional to the number of voters
  at that site; marker **color** follows the selected mode.
* **Three color modes** (*אחוז הצבעה* is the default)
  * *אחוז הצבעה* — turnout, as a one-hue light→dark ramp.
  * *גוש מוביל* — which bloc led at the site (categorical: blue / orange / green).
  * *פער בין הגושים* — coalition-minus-opposition margin, a diverging blue↔orange
    scale with a neutral gray midpoint.
* **Filters** by free text (site name, address, station number or "iron" number),
  minimum turnout, and leading bloc. The list, the markers, the legend counts and the
  table all follow the active filter.
* **Site detail** (click a marker or a list row): bloc split, largest parties, a
  collapsible per-station breakdown (*פירוט לפי קלפי*, collapsed by default), the full
  vote table, and the location accuracy for that site.
* **Table view** — every field for all 140 sites or all 424 stations, sortable by any column.
* **Site labels**, dark mode, and an **על הנתונים** panel documenting sources, bloc
  definitions and limitations.

## Data and provenance

| Layer | Source |
|---|---|
| Votes, eligible voters, voters, valid/invalid per station | Central Elections Committee official per-station file (`expb.csv`, Knesset 25) |
| Station → address | `haifa_polling_station_matching.xlsx` (built from Haifa's official election notice and the station-site names) |
| Address → coordinates | OpenStreetMap Nominatim |
| Site → building | OpenStreetMap Overpass, for sites whose venue name matched a named school / community centre / hall nearby |

All 424 rows in the spreadsheet were re-verified against `expb.csv`: station counts,
eligible voters and voters match exactly. City totals: 253,292 eligible, 140,650 voters,
**55.53% turnout**, 139,764 valid votes.

**Location accuracy** (per site, also shown in the UI): 35 snapped to an identified OSM
building, 13 exact house numbers, 80 street-centroid only, 12 approximate. A street-centroid
marker can sit tens to a few hundred metres from the actual building. Sites that geocoded to
the identical point are nudged a few metres apart so their markers stay separable.

Turnout here is that of Haifa's own ballot boxes; double-envelope and external ballots are
not included, so it is not the turnout of all Haifa residents.

## The pipeline

```sh
pip install -r requirements.txt
./build.sh
```

`build.sh` runs seven stages in order. Each stage reads files from `data/` and writes one
file back to `data/`, so stages are independently re-runnable and the network is only
touched when a cache file is missing. Geocoding results (`data/geocache.json`) and the
Overpass reply (`data/osm_venues.json`) are committed, so a normal rebuild is **offline and
takes seconds**. Delete a cache file to force a re-fetch; a cold geocoding run takes
~15 minutes (Nominatim is rate-limited to 1 req/s).

| # | Stage | Reads | Writes | Role |
|---|---|---|---|---|
| 1 | `extract.py` | `config.MATCHING_XLSX` | `data/raw.json` | flatten the two spreadsheet tabs (`קלפיות`, `אתרים`) into stations + sites |
| 2 | `geocode.py` | `data/raw.json` | `data/geocache.json` | address → coordinates via Nominatim, constrained to `config.BBOX` |
| 3 | `geocode_retry.py` | `data/geocache.json` | `data/geocache.json` | second pass for misses: expand abbreviations (שד→שדרות), drop honorifics (ד"ר), flip surname-first names, try spelling variants |
| 4 | `qa_geo.py` | `data/geocache.json` | — (report only) | assert every hit names `config.CITY_HE` and no two distinct streets share a point |
| 5 | `snap_osm.py` | `data/raw.json`, `data/osm_venues.json` | `data/osm_snaps.json` | match site names (schools, community centres…) to named OSM buildings in the bbox, accepted only when near the geocoded address |
| 6 | `build_data.py` | `raw.json` + `geocache.json` + `osm_snaps.json` | `data/map_data.json` | join all three, aggregate stations → sites, compute turnout / blocs / margin / marker data / map center |
| 7 | `build_map.py` | `src_map.html`, `src_app.js`, `vendor/*`, `data/map_data.json` | `config.OUT_HTML` | inline everything into one self-contained HTML file |

`test_map.py` (stage 8, not in `build.sh`) renders `config.OUT_HTML` headlessly — see Tests.

**Front-end:** edit `src_map.html` (markup + styles) or `src_app.js` (behaviour), then
re-run `python3 build_map.py`. Never edit the generated HTML directly — it is overwritten.
The map view, turnout ramp bins and marker sizing live in `src_app.js`; the map center /
zoom come from `data/map_data.json` (set in `config.py`).

## Adapting to another city

All city- and election-specific constants live in **`config.py`** — the pipeline scripts
hold none of their own. To build the map for another city in the **same election**:

1. Copy the repo to a new folder.
2. Drop in that city's station↔address matching workbook (same two-tab layout: `קלפיות`
   with `מספר קלפי / מספר ברזל / שם אתר / כתובת מועמדת / רמת ביטחון / בעלי זכות / מצביעים /
   פסולים / כשרים / מפלגה …` columns, and `אתרים`).
3. In `config.py` set `CITY_HE`, `CITY_SLUG`, `MATCHING_XLSX`, `OUT_HTML` and `BBOX`
   (the city's bounding box, `W, S, E, N`). Optionally pin `MAP_CENTER` / `MAP_ZOOM`.
4. `rm -f data/geocache.json data/osm_snaps.json data/osm_venues.json` (they are Haifa's),
   then `./build.sh`. Expect a ~15-minute cold geocode.
5. `python3 test_map.py` to sanity-check the render.

For a **different election**, also update `BLOCS` and `PARTY_NAMES` in `config.py` with that
election's party letter codes. The Hebrew UI strings in `src_map.html` / `src_app.js` are
generic ("polling site", "turnout", …) and need no change; only the `<title>` and the
"על הנתונים" panel text mention specifics worth reviewing.

## Tests

```sh
python3 -m playwright install chromium   # once
python3 test_map.py                      # all scenarios
python3 test_map.py dark                 # one scenario
```

Ten scenarios (light, dark, each color mode, detail, labels, table, filter, search, narrow
viewport) are rendered headlessly and checked for JS errors, failed requests, horizontal
overflow, clipped controls, markers and tiles actually rendering, overlays escaping their
container, and the table view fully covering the map. Screenshots land in `build/`.
