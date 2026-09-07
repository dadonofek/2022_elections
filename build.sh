#!/bin/sh
# Full pipeline: matching spreadsheet -> geocoded data -> single-file HTML map.
# All city/election constants are in config.py. Geocoding and Overpass results are
# cached under data/, so re-runs are offline and fast (delete a cache file to refetch).
set -e
python3 extract.py          # config.MATCHING_XLSX -> data/raw.json
python3 geocode.py          # addresses -> data/geocache.json      (cached; ~15 min cold)
python3 geocode_retry.py    # second pass for addresses the first pass missed
python3 qa_geo.py           # sanity report on the geocoding
python3 snap_osm.py         # named venues -> data/osm_snaps.json  (uses cached Overpass reply)
python3 build_data.py       # join everything -> data/map_data.json
python3 build_map.py        # inline data + Leaflet -> config.OUT_HTML
