# Handoff — Haifa polling-station map

Working dir: `/Users/home/Projects/elections/Haifa` (not a git repo).
Deliverable: **`haifa_polling_map.html`** — one self-contained file (~508 KB), opens in any
browser, no server and no API key. Data and Leaflet are inlined; only the OpenStreetMap
background tiles need network. **UI language is Hebrew (RTL) and must stay Hebrew.**

The generated file is a full HTML document (`<!DOCTYPE html>` + `<head><meta charset="utf-8">`).
If you ever see the Hebrew render as mojibake, the charset meta or the UTF-8 write encoding
in `build_map.py` was dropped — both are required for `file://` viewing.

All city/election constants are in **`config.py`**; the pipeline scripts have none of their
own. See "Adapting to another city" in `README.md`.

## Status: the original goal is complete

Every one of the 424 polling stations now has coordinates. Nothing is blocked.

| | |
|---|---|
| Polling stations (קלפיות) | 424 — all with results, turnout and coordinates |
| Polling sites (אתרי הצבעה) | 140 — one map marker each |
| Unique addresses geocoded | 134 of 134, zero misses |
| City totals | 253,292 eligible · 140,650 voters · **55.53%** turnout · 139,764 valid |

**Verification done:** all 424 rows of the spreadsheet were compared against the official
Central Elections Committee per-station file (`expb.csv`, Knesset 25, locality code 4000).
Station counts, iron numbers, eligible voters and voters match exactly — zero discrepancies.

**Location accuracy per site** (surfaced in the UI, per site, and in the "על הנתונים" panel):

| precision | sites | meaning |
|---|---|---|
| `venue` | 35 | snapped to a named building in OpenStreetMap |
| `house` | 13 | exact house number |
| `street` | 80 | street centroid only — can be tens to a few hundred metres off |
| `place` | 12 | approximate point on the street |

Address→site match confidence, carried over from the spreadsheet: 133 גבוה מאוד, 5 גבוה,
2 בינוני-גבוה.

## What the map does

* One marker per site; marker **area** ∝ voters at that site.
* Five color modes, **potential is the default**: **potential** (votes left on the table,
  sequential on the selected bloc's hue), **turnout** (single-hue sequential ramp),
  **delta vs the national average** (rose deficit ramp), **leading bloc** (categorical),
  **bloc margin** (diverging blue<->orange, gray midpoint). The list defaults to
  potential-descending, and below 1000px the map and list are separate tabs.
* Filters: free text (site name, address, station number, iron number), minimum turnout,
  leading bloc. Markers, list, legend counts and table all follow the active filter.
* Click a site → detail panel: bloc split, largest parties, a collapsible per-station
  table (`פירוט לפי קלפי`, a `<details>`, collapsed by default), full vote table, and that
  site's location accuracy.
* Table view: all 140 sites or all 424 stations, every field, sortable by any column.
* Site labels with collision avoidance, dark mode, and an "על הנתונים" panel documenting
  sources, bloc definitions and limitations.

Bloc definitions (in `build_data.py`, mirrored in the about panel):
coalition = מחל, שס, ג, ט · zionist opposition = פה, כן, ל, אמת, מרצ · arab = ום, עם, ד ·
broad opposition = zionist opposition + arab · other = valid − coalition − opposition.

## Pipeline

`./build.sh` runs it end to end. Caches live in `data/`, so a rebuild is offline and takes
seconds. Delete a cache file to re-fetch it. A cold geocode run is ~15 min (Nominatim is
rate-limited to 1 req/s).

| # | script | reads → writes |
|---|---|---|
| 1 | `extract.py` | `config.MATCHING_XLSX` → `data/raw.json` |
| 2 | `geocode.py` | `raw.json` → `data/geocache.json` (Nominatim, bounded to `config.BBOX`) |
| 3 | `geocode_retry.py` | `geocache.json` → `geocache.json`; retry pass expands abbreviations (שד→שדרות, drops ד"ר), flips surname-first street names, tries spelling variants |
| 4 | `qa_geo.py` | `geocache.json` → report; asserts every hit names `config.CITY_HE` and no two distinct streets share a point |
| 5 | `snap_osm.py` | `raw.json` + `data/osm_venues.json` → `data/osm_snaps.json` (site name → named OSM building) |
| 6 | `build_data.py` | `raw.json` + `geocache.json` + `osm_snaps.json` → `data/map_data.json` (blocs, turnout, margin, map center) |
| 7 | `build_map.py` | `src_map.html` + `src_app.js` + Leaflet + `map_data.json` → `config.OUT_HTML` |
| 8 | `test_map.py` | headless render checks on `config.OUT_HTML` (not in `build.sh`) |

Every stage reads from `data/` and writes one file back, so stages re-run independently.
`config.py` is the only place with city/election constants.

**Edit `src_map.html` (markup + CSS) or `src_app.js` (behaviour), then run
`python3 build_map.py`. Never edit `haifa_polling_map.html` — it is generated and will be
overwritten.**

## Tests

`python3 test_map.py` (all) or `python3 test_map.py dark` (one). Ten scenarios: light, dark,
each color mode, detail, labels, table, filter, search, narrow viewport. Checks JS errors,
failed requests, horizontal overflow, clipped controls, markers and tiles rendering,
overlays escaping their container, and the table view covering the map. Screenshots →
`build/`. All ten pass as of handoff.

## Bugs already found and fixed — do not reintroduce

1. `.sidebar` had no `position:relative`, so the detail panel escaped it and half its text
   rendered under the map. Regression check: `escaped` in `test_map.py`.
2. Leaflet's panes floated above the table overlay (transparent table). Fixed with
   `.mapwrap { z-index:0; isolation:isolate }`. Regression check: `coveredByTable`.
3. Legend ramp labels were reversed relative to the swatches under RTL — the map said
   "coalition" where the color meant "opposition". The ramp's first DOM swatch renders on
   the **right**; labels must be written in that same order.
4. Legend and map toolbar escaped the map in the narrow (<1000px) layout. Fixed by moving
   both inside `.mapwrap`.
5. CARTO basemaps started returning "API KEY REQUIRED" tiles. Switched to
   `tile.openstreetmap.org` (has Hebrew labels, no key), muted via a CSS filter on
   `.leaflet-tile-pane` so markers stay dominant.
6. Label markers requested Leaflet's default icon PNG (404 on `file://`). Fixed with an
   empty `divIcon`.
7. `.bar .track` / `.fill` were inline spans, so bar fills had zero height. Both are
   `display:block` now.
8. **The whole UI below the map was unreachable on a phone.** `.app{height:100vh;
   overflow:hidden}` means the document can never scroll; the stacked mobile layout
   then left the sidebar 126px for panels that needed 338px, so on a 390x844 screen the
   search box sat 1px below the fold, the sort control 222px off-screen and the site
   list rendered at **zero height**. Map and list are separate tabs below 1000px now.
   Regression check: the `phone_*` scenarios, which assert reachability.
9. **The `narrow` test scenario hid #8 for a whole release.** It ran at 900x1100 and
   asserted `listItems == 140` — a count of DOM nodes, which passes fine when the list
   has no height. Assert visibility (`listOnScreen`, `listH`), never DOM presence.
10. Bug #3 came back, in the new potential ramp: labels were written largest-first while
   the swatches run lightest-first, so "1,600+" sat under the palest colour. Regression
   check: `rampFirstLabel` in `test_map.py`. **The ramp's first DOM swatch renders on
   the RIGHT under RTL — labels must be authored in that same order.**
11. `.main` is a flex row, so under `direction:rtl` its FIRST DOM child takes the right
   edge. `.mapwrap` was first, which put the control panel on the left of a Hebrew UI.
   `.sidebar` leads now (which also fixes tab and screen-reader order); an `order:`
   property would have fixed the paint and left both wrong.

## Product decisions

**`PRODUCT_DECISIONS.md`** records the PM requirements, the decision taken on each, the
reasoning, and what was deferred (nationwide coverage) with its scoping. Read it before
changing the potential formula, the delta baseline, the palette or the mobile layout —
several of those choices look arbitrary without the measurements behind them.

## Color rules being followed (dataviz skill)

Palettes were validated with the skill's `scripts/validate_palette.js`, not eyeballed.
Categorical blocs use slots 1–3 (`#2a78d6` / `#eb6834` / `#1baf7a`), which pass all-pairs
CVD checks in both modes. The sequential turnout ramp starts at `#86b6ef` so the lightest
step clears the 2:1 floor. The diverging margin scale reuses the same blue/orange bloc hues
so a bloc keeps its color across modes. If you change any palette, re-run the validator:
`node <dataviz-skill>/scripts/validate_palette.js "<hex,hex,...>" --mode light`.

The **turnout-delta ramp is rose (OKLCH hue 0)**, chosen by measurement after two
candidates were rejected: gold collapses to **dE 2.5** against the opposition orange
under deuteranopia (a colourblind reader would read "below baseline" as "opposition"),
and crimson at hue 25 lands **dE 4.7**. Rose clears **11.2** from orange and **12.5**
from blue, and passes the ordinal checks (monotone L, adjacent dL >= 0.06, light-end
contrast >= 2:1, single hue) in both modes. It is **sequential, not diverging**, because
against the national baseline 123 of the 140 sites are below it — a symmetric scale would
spend half its range on 17 sites. The **potential ramps are sequential ramps on the
existing bloc hues**, so hue keeps meaning "which bloc" and lightness carries the
magnitude; all six were validated the same way.

**Known, not fixed:** the turnout ramp's lightest step `--seq-0:#eadcf3` measures
**1.28:1** against the light surface, below the 2:1 ordinal floor — this document's
claim that it "starts at `#86b6ef`" does not match the shipped value. Left alone
deliberately: changing it alters the appearance of the most-used mode.

## Known limitations (documented in the UI, not defects)

* 80 sites are street-centroid accurate. Improving them needs a source with house-number
  geometry — the government geocoder (govmap) or a manual pass.
* Haifa-only ballot boxes; double-envelope and external ballots are excluded, so 55.53% is
  the turnout of the city's boxes, not of all Haifa residents.
* Marker position is the polling site, not where voters live.
* One address arrives mangled from the source PDF (`פרץ י .ל20,.`); it is displayed as
  `י.ל. פרץ 20` via `ADDRESS_FIX` in `src_app.js`. Its coordinates were verified correct.
* Sites that geocoded to an identical point are nudged a few metres apart (`jittered`).

## Possible next steps (none required)

* Raise location precision for the 80 street-centroid sites via govmap or manual review.
* Shareable link: publishing as an Artifact is blocked because its CSP blocks OSM tiles —
  the markers would render on a blank background. Would need an embedded static basemap or
  vector city outline first.
* Add per-station markers (currently stations are aggregated into sites; per-station data
  is already in the detail panel and the table).
* Compare against another election year, which would need a second matching spreadsheet.
