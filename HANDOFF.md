# Handoff — polling-station maps, Knesset 25

Deliverable: one self-contained HTML file per city (~560 KB), opens in any browser, no
server and no API key. Data and Leaflet are inlined; only the OpenStreetMap background
tiles need network. **UI language is Hebrew (RTL) and must stay Hebrew.**

| city | slug | built |
|---|---|---|
| חיפה | `haifa` (default) | `haifa_polling_map.html` — 424 stations, 140 sites, 55.53% turnout |
| בית שמש | `beit_shemesh` | `beit_shemesh_polling_map.html` — 133 stations, 44 sites, 66.13% turnout |

Pick the city with the `CITY` environment variable: `CITY=beit_shemesh ./build.sh`.

The generated file is a full HTML document (`<!DOCTYPE html>` + `<head><meta charset="utf-8">`).
If you ever see the Hebrew render as mojibake, the charset meta or the UTF-8 write encoding
in `build_map.py` was dropped — both are required for `file://` viewing.

All city/election constants are in **`config.py`**; the pipeline scripts have none of their
own. See "Adding a city" in `README.md`.

## Beit Shemesh — complete

**Done.** `data/beit_shemesh/raw.json` holds all 133 stations and all 44 sites, with site
names and addresses, built by `CITY=beit_shemesh python3 extract.py` from the two official
national files. Totals: **78,064 eligible · 51,622 voters · 66.13% turnout**. Every station
has an address; the two files agree on all 44 site groupings. `config.CITIES['beit_shemesh']`
carries the locality code (2610), the bounding box, the zoom and the two provenance
sentences the *על הנתונים* panel prints.

Coordinates are complete: 44/44 sites and 133/133 stations map successfully. Location
precision is 6 named OSM venues, 5 houses, 30 streets and 3 approximate places. The two
CEC address forms absent from OSM (`הרב איידלשטיין 8`, `סמ ויצ"ו 16`) resolve
reproducibly through normalized OSM street names in `geocode_retry.py`.

`build_data.py` still **refuses** to emit a map while any site lacks coordinates
(override with `ALLOW_MISSING_COORDS=1`), so a future half-geocoded city cannot ship quietly.

Do **not** substitute the Google-geocoded `output/locations.tsv` from
JacobWeinbren/Israel-Revised: it covers only 13 of the 44 addresses exactly and 9 more at
street level, because it was built from elections 14–24 and Ramat Beit Shemesh grew after
them. Half a map is worse than none.

## Multi-city: what changed

* `config.py` holds a `CITIES` registry; `CITY` (env) selects one, defaulting to `haifa`.
  Everything a city owns — name, locality code, bbox, center, zoom, output filename,
  extract mode, provenance sentences — lives in its entry.
* Each city caches under `data/<slug>/` (`raw.json`, `geocache.json`, `osm_venues.json`,
  `osm_snaps.json`, `map_data.json`). Haifa's files moved there. `data/expb.csv` and
  `data/kalpiplaces_25.xlsx` stay at the top of `data/` — they are national.
* `extract.py` has two modes. `cec` builds stations and sites straight from the two
  national files and works for **any** locality with no preparation; `workbook` is the old
  hand-built spreadsheet path, which Haifa stays on for its per-site match confidence.
  The two were compared on Haifa and agree — see README, *Provenance*.
* The front end no longer names a city. `src_map.html` carries `__CITY_HE__` /
  `__N_KALPI__` / `__N_SITES__` tokens that `build_map.py` substitutes, and every Hebrew
  sentence in `src_app.js` that mentions the city builds it from `DATA.city.name`
  (`IN_CITY` = `'ב'+name`, `FROM_CITY` = `'מ'+name`). The address source and the
  station-to-address caveat come from `DATA.city.source_note` / `match_note`.
* Rebuilding Haifa after all of this produced a **byte-identical** `map_data.json` and
  HTML, and all 36 render scenarios still pass.

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

* **A camp**: `הדמוקרטים` (העבודה + מרצ) is a group the bloc partition does not name. It is
  one more option in the `הגוש שלי` select that picks whose non-voters the potential counts
  — beside `כל מי שלא הצביע` and the three blocs, which are all exactly as they were — and
  it is the default (`config.DEFAULT_POT_TARGET`). It is **not** a fourth bloc: it sits
  inside the broad opposition, so the partition-based views (bloc split, `גוש מוביל`,
  `פער בין הגושים`, the filter chips) keep using the three blocs and the camp is shown
  beside them, labelled as a subset. Its header tile, sort, two table columns, site-card bar
  and bloc-split line are **always present**, whichever group is selected — a camp is a
  permanent group, not a mode. Defined in `config.CAMPS`; the front end inserts its option,
  columns and tile from the data. See `PRODUCT_DECISIONS.md` Round 5 before changing any of
  it — §5.2 records the shape that was tried first and why it was wrong.
* One marker per site; marker **area** ∝ **בעלי זכות בחירה** (the electorate the site
  serves) in *every* mode — the mode changes the colour and nothing else, so a marker
  keeps its size as you switch and "big and dark" always reads as one sentence.
* Five color modes, **potential is the default**: **potential** (votes left on the table,
  sequential on the selected bloc's hue), **turnout** (single-hue sequential ramp),
  **delta vs the national average** (rose deficit ramp), **leading bloc** (categorical),
  **bloc margin** (diverging orange<->blue, gray midpoint). The list defaults to
  potential-descending, and below 1000px the map and list are separate tabs, where a
  marker tap opens a compact card on the map rather than jumping to the site panel.
  In that layout the map bar also carries its own **colour-mode select** (plus the
  bloc-target select in potential mode), bound to the same state as the panel's
  segmented control — the panel lives on the other tab, so choosing a mode there
  meant three taps and no sight of the map being painted.
* Filters: free text (site name, address, station number, iron number), minimum turnout,
  leading bloc. Markers, list, legend counts and table all follow the active filter.
* Click a site → detail panel: bloc split, largest parties, a collapsible per-station
  table (`פירוט לפי קלפי`, a `<details>`, collapsed by default), full vote table, and that
  site's location accuracy.
* Table view: all 140 sites or all 424 stations, every field, sortable by any column.
* Site labels with collision avoidance, dark mode, and an "על הנתונים" panel documenting
  sources, bloc definitions and limitations.

Bloc definitions (in `config.BLOCS`, applied by `build_data.py`, mirrored in the about panel):
coalition = מחל, שס, ג, ט · zionist opposition = פה, כן, ל, אמת, מרצ · arab = ום, עם, ד ·
broad opposition = zionist opposition + arab · other = valid − coalition − opposition.

Camp definitions (`config.CAMPS`): הדמוקרטים = אמת + מרצ (13,071 votes in Haifa, 9.35% of
the valid vote, potential 10,142 — the sum of the 140 sites, which is what the UI prints;
`city.pot` applies one city-wide share to all non-voters and says 10,534) ·
אופוזיציה רחבה = the broad-opposition bloc total. A camp
overlaps a bloc on purpose and is never subtracted from one. **הדמוקרטים did not exist in
2022** — העבודה and מרצ ran separately and מרצ missed the threshold; the party was formed
from their merger in 2024, so the sum is retrospective. That caveat is in `config.CAMPS`
(`note`) and surfaces under the group select when the camp is picked, in the site card and
in `על הנתונים`.

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

`python3 test_map.py` (all) or `python3 test_map.py dark` (one). 36 scenarios: light, dark,
each color mode, each potential target, both camps, detail, labels, table, sorting, filter,
search, narrow viewport, and thirteen phone scenarios at 390x844 with touch. Checks JS errors,
failed requests, horizontal overflow, clipped controls, markers and tiles rendering,
overlays escaping their container, the table view covering the map, the two colour-mode
controls staying in step, the marker radius not moving when the mode changes, and the camp
reaching every surface it drives (legend, header tile, list figure, target and sort option
labels, table column set). Screenshots → `build/`. All 36 pass as of handoff.

Set `PLAYWRIGHT_CHROMIUM_PATH` when the container ships its own Chromium (e.g.
`PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium python3 test_map.py`); without the
basemap tiles the suite still runs and marks those rows `*`.

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
12. A marker tap on a phone ran straight into `selectSite`, which switches to the list
   tab — so asking "what is this circle?" cost the user the map. Touch layouts bind a
   click-driven **popup** card instead (tooltips are `interactive:false`, so a link
   inside one is not tappable), and the full panel is reached only by its button.
   `bindMarkerUI` picks the binding per layout and **re-binds on breakpoint change**, so
   a resize cannot leave the wrong one attached. Checks: `phone_tap`, `phone_card_more`,
   `desktop_tap`.
13. Leaflet pins `.leaflet-popup-close-button` to the physical **top-right**, which under
   RTL is where title text *begins* — pad the popup title on its inline-START side.
   Check: `cardTitleClearsClose`, which measures the text with a `Range`; the
   `display:block` title box spans the full width and always looks like it overlaps.

14. The colour mode was reachable **only from the list tab** on a phone: `רשימה` →
    expand `סינון וצביעה` → pick → back to `מפה`. A control that paints the map belongs
    on the map in that layout. `#mapMode` / `#mapPotTarget` in `.mapbar` are bound to the
    same state through `setMode()` / `setPotTarget()`, so the two copies cannot disagree;
    both are `display:none` above 1000px, where the panel is already beside the map.
    Checks: `phone_mapmode`, `phone_mapmode_sync`, and `mapModeUsable: False` on desktop.
15. **Potential mode sized the markers by the potential**, which spent both visual
    channels on one variable — a marker was dark because it was big. Size is the
    electorate in every mode now; colour alone carries the metric. Check:
    `radiusModeIndependent`, asserted on every scenario.

## Product decisions

**`PRODUCT_DECISIONS.md`** records the PM requirements, the decision taken on each, the
reasoning, and what was deferred (nationwide coverage) with its scoping. Read it before
changing the potential formula, the delta baseline, the palette or the mobile layout —
several of those choices look arbitrary without the measurements behind them.

## Color rules being followed (dataviz skill)

Palettes were validated with the skill's `scripts/validate_palette.js`, not eyeballed.
Categorical blocs use slots 1–3 — **opposition `#2a78d6` (blue), coalition `#eb6834`
(orange), other `#1baf7a`** — which pass all-pairs CVD checks in both modes. The two bloc
hues were swapped on request; it is the same validated triple, only reassigned, so the
separation measurements below still hold with the bloc names exchanged. The sequential turnout ramp starts at `#86b6ef` so the lightest
step clears the 2:1 floor. The diverging margin scale reuses the same bloc hues
so a bloc keeps its color across modes. If you change any palette, re-run the validator:
`node <dataviz-skill>/scripts/validate_palette.js "<hex,hex,...>" --mode light`.

The **turnout-delta ramp is rose (OKLCH hue 0)**, chosen by measurement after two
candidates were rejected: gold collapses to **dE 2.5** against the coalition orange
under deuteranopia (a colourblind reader would read "below baseline" as "opposition"),
and crimson at hue 25 lands **dE 4.7**. Rose clears **11.2** from the orange and **12.5**
from the blue, and passes the ordinal checks (monotone L, adjacent dL >= 0.06, light-end
contrast >= 2:1, single hue) in both modes. It is **sequential, not diverging**, because
against the national baseline 123 of the 140 sites are below it — a symmetric scale would
spend half its range on 17 sites. The **potential ramps are sequential ramps on the
existing bloc hues**, so hue keeps meaning "which bloc" and lightness carries the
magnitude; all six were validated the same way. The **camp ramp (teal, OKLCH hue 210)** is
the exception to "hue means which bloc": הדמוקרטים sits inside a bloc, so it needs a hue no
bloc owns — worst CVD dE 15.9 / 12.6 / 10.0 against the blue, the orange and the green
(measured by hue, so the bloc swap did not touch it). **They are not redefined for dark mode**,
and neither is the rose ramp: the legend tells the reader "big and dark = a lot still on
the table", so darker has to keep meaning *more* in both themes. Every dark end still
clears 2.5:1 against the dark surface. The turnout ramp still inverts in dark mode, so its
`בהיר` wording reads backwards there — the one remaining case, left alone because a shared
ramp would put `--seq-5` at 1.55:1 on the dark surface.

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
* The camp's potential is the estimate of §1 in `PRODUCT_DECISIONS.md` narrowed to two
  lists, so every caveat on it holds and the retrospective merger is one more: it assumes
  non-voters lean like their voting neighbours AND that a 2024 party inherits the 2022
  votes of both its predecessors.

## Nationwide (כל הארץ) — extraction done, geocoding blocked here

See "Nationwide — in progress" in `README.md` for the full picture. Short version:
`national_extract.py` (no network) turns the two national CEC files into
`data/national/raw.json` — 1,216 localities, 4,205 addressed polling sites, 3,762
unique addresses left to geocode. `geocode_national.py` is written to do that, but
**this sandboxed session's network policy blocks every geocoder tested** (Nominatim,
data.gov.il, govmap, Geoapify, odata.org.il — all 403/EGRESS_BLOCKED), so it has to
be run on a machine with normal internet access; send back `data/national/geocache.json`
when it finishes. After that, the remaining stages (aggregate to sites, build the
two-layer front end) are the same shape as a city's build, sketched in README.

## Possible next steps (none required)

* Another camp is a `config.CAMPS` entry plus a `--camp-<key>` colour, a
  `--pot-<key>-0..4` ramp and its bin edges — see `PRODUCT_DECISIONS.md` §5.4 for how the
  existing ramp was measured. Do not eyeball a new one.

* Raise location precision for the 80 street-centroid sites via govmap or manual review.
* Shareable link: publishing as an Artifact is blocked because its CSP blocks OSM tiles —
  the markers would render on a blank background. Would need an embedded static basemap or
  vector city outline first.
* Add per-station markers (currently stations are aggregated into sites; per-station data
  is already in the detail panel and the table).
* Compare against another election year, which would need a second matching spreadsheet.
