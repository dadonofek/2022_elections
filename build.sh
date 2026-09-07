#!/bin/sh
# Full pipeline: official election files -> geocoded data -> single-file HTML map.
#
#   ./build.sh                      # the default city (Haifa)
#   CITY=beit_shemesh ./build.sh    # any other city in config.CITIES
#
# All city/election constants are in config.py. Each city caches under
# data/<slug>/, so re-runs are offline and fast (delete a cache file to refetch).
set -e
python3 -c 'import config; print("building", config.CITY_SLUG, "->", config.OUT_HTML)'
python3 extract.py          # official inputs -> data/<city>/raw.json
python3 geocode.py          # addresses -> data/<city>/geocache.json   (cached; ~15 min cold)
python3 geocode_retry.py    # second pass for addresses the first pass missed
python3 qa_geo.py           # sanity report on the geocoding
python3 snap_osm.py         # named venues -> data/<city>/osm_snaps.json (cached Overpass reply)
python3 build_data.py       # join everything -> data/<city>/map_data.json
python3 build_map.py        # inline data + Leaflet -> config.OUT_HTML
