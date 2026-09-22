"""Stage 3b — a street-level place for the addresses Nominatim could not answer.

Nominatim is the geocoder of record (geocode.py, geocode_retry.py). When it cannot be
reached, or an address is new since the last networked run, the address would have no
coordinates and build_data.py would refuse the city. This stage puts such an address
on its STREET instead:

  1. another address on the same street is already geocoded -> that point
     (Nominatim's own answer for the street), or else
  2. the middle of the named street in the street network of Overture Maps —
     OpenStreetMap road segments (ODbL), read from Overture's public release on S3.
     A street name can recur in a neighbouring locality, so of all the runs of that
     name the one nearest the station's own neighbourhood wins: the other geocoded
     sites of the same sub-quarter (a column of the observers' list), else of the city.

Either way the result is a street-level position — what a street-level Nominatim
answer is too — and it is written into geocache.json marked PROVISIONAL, which
geocode.py and geocode_retry.py replace the moment Nominatim answers.

Only parquet footers and the row groups that intersect config.BBOX are downloaded
(a few MB), and the named streets are cached in data/<city>/streets_overture.json, so
a rebuild stays offline. pyarrow and shapely are needed only when there is something
to place; with nothing missing this stage imports neither.
"""
import io, json, math, os, re, time, urllib.parse, urllib.request
from collections import defaultdict
import config

CACHE = config.data('geocache.json')
STREETS = config.data('streets_overture.json')
BUCKET = 'https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com'
W, S, E, N = config.BBOX
FAR_M = 3000        # a street run this far from the neighbourhood is someone else's street


# ---------------------------------------------------------------- street names
def norm_street(s):
    """'שד\\' האמוראים' -> 'שדרות האמוראים'; quotes and geresh dropped."""
    s = str(s or '').replace('״', '"').replace('׳', "'")
    s = re.sub(r'["\']', '', s)
    s = re.sub(r'^שד\s+', 'שדרות ', s)
    s = re.sub(r'^סמ\s+', 'סמטת ', s)
    s = re.sub(r'^רח\s+', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def forms(s):
    """Every spelling a street name is matched under: with and without its type word."""
    n = norm_street(s)
    return {n, re.sub(r'^(שדרות|רחוב|סמטת|דרך|שביל|כיכר) ', '', n)}


def split_address(addr):
    """'שד\\' האמוראים 29' -> ('שד\\' האמוראים', '29'); 'רב המנונא' -> ('רב המנונא', None)."""
    m = re.match(r'^(.*?)\s+(\d+)(?:\s*[א-ת])?$', addr.strip())
    return (m.group(1), m.group(2)) if m else (addr.strip(), None)


# ---------------------------------------------------------------- Overture on S3
def s3_list(prefix, delimiter=None):
    keys, prefixes, token = [], [], None
    while True:
        q = {'list-type': '2', 'prefix': prefix}
        if delimiter: q['delimiter'] = delimiter
        if token: q['continuation-token'] = token
        t = urllib.request.urlopen(f'{BUCKET}/?{urllib.parse.urlencode(q)}', timeout=60).read().decode()
        keys += [(k, int(z)) for k, z in zip(re.findall(r'<Key>([^<]+)</Key>', t),
                                             re.findall(r'<Size>([^<]+)</Size>', t))]
        prefixes += re.findall(r'<Prefix>([^<]+)</Prefix>', t)
        m = re.search(r'<NextContinuationToken>([^<]+)<', t)
        if not m:
            return keys, prefixes
        token = m.group(1)


class RangeFile(io.RawIOBase):
    """A read-only, seekable view of an HTTP object, fetched by byte range on demand —
    enough for pyarrow to read a parquet footer and then only the row groups asked for."""
    def __init__(self, url, size):
        self.url, self.size, self.pos = url, size, 0
    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos
    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos
    def read(self, n=-1):
        if n is None or n < 0: n = self.size - self.pos
        if n <= 0 or self.pos >= self.size: return b''
        req = urllib.request.Request(self.url, headers={'Range': f'bytes={self.pos}-{min(self.size, self.pos + n) - 1}'})
        for attempt in range(4):
            try:
                data = urllib.request.urlopen(req, timeout=120).read()
                break
            except Exception:
                if attempt == 3: raise
                time.sleep(2 * (attempt + 1))
        self.pos += len(data)
        return data
    def readinto(self, b):
        d = self.read(len(b)); b[:len(d)] = d; return len(d)


def fetch_streets():
    """Every named road segment intersecting the bbox, as {name: [[[lon, lat], ...], ...]}."""
    import pyarrow.parquet as pq, pyarrow.compute as pc, shapely
    release = os.environ.get('OVERTURE_RELEASE')
    if not release:
        _, rels = s3_list('release/', '/')
        release = sorted(p.split('/')[1] for p in rels if p.count('/') == 2)[-1]
    keys, _ = s3_list(f'release/{release}/theme=transportation/type=segment/')
    keys = [k for k in keys if k[0].endswith('.parquet')]
    print(f'Overture {release}: scanning {len(keys)} segment files for the bbox', flush=True)
    streets = defaultdict(list)
    for i, (key, size) in enumerate(keys, 1):
        pf = pq.ParquetFile(RangeFile(f'{BUCKET}/{key}', size))
        md = pf.metadata
        col = {md.schema.column(j).path: j for j in range(md.num_columns)}
        groups = []
        for g in range(md.num_row_groups):
            st = {k: md.row_group(g).column(col[f'bbox.{k}']).statistics for k in ('xmin', 'xmax', 'ymin', 'ymax')}
            if all(v is not None and v.has_min_max for v in st.values()) and (
                    st['xmin'].min > E or st['xmax'].max < W or st['ymin'].min > N or st['ymax'].max < S):
                continue
            groups.append(g)
        if not groups:
            continue
        t = pf.read_row_groups(groups, columns=['names', 'subtype', 'geometry', 'bbox'])
        bb = t.column('bbox')
        inside = pc.and_(pc.and_(pc.less_equal(pc.struct_field(bb, 'xmin'), E), pc.greater_equal(pc.struct_field(bb, 'xmax'), W)),
                         pc.and_(pc.less_equal(pc.struct_field(bb, 'ymin'), N), pc.greater_equal(pc.struct_field(bb, 'ymax'), S)))
        for r in t.filter(inside).select(['names', 'subtype', 'geometry']).to_pylist():
            name = (r['names'] or {}).get('primary')
            if r['subtype'] != 'road' or not name:
                continue
            g = shapely.from_wkb(r['geometry'])
            streets[name].append([[round(x, 6), round(y, 6)] for x, y in g.coords])
        print(f'  {i}/{len(keys)}: {sum(map(len, streets.values()))} named segments so far', flush=True)
    return {'release': release, 'source': 'Overture Maps Foundation, transportation/segment '
            '(OpenStreetMap contributors, ODbL)', 'bbox': [W, S, E, N], 'streets': dict(streets)}


# ---------------------------------------------------------------- geometry
def to_m(lon, lat, lat0):
    return (lon * 111320 * math.cos(math.radians(lat0)), lat * 111320)

def from_m(x, y, lat0):
    return (x / (111320 * math.cos(math.radians(lat0))), y / 111320)


def place_on_street(runs, ref, lat0):
    """The middle of the named street's run nearest `ref` (lon, lat); None if every run is FAR."""
    import shapely
    lines = [shapely.LineString([to_m(x, y, lat0) for x, y in seg]) for seg in runs if len(seg) > 1]
    merged = shapely.line_merge(shapely.union_all(lines))
    parts = list(getattr(merged, 'geoms', [merged]))
    # parts that (nearly) touch are one run of the street; distant ones are another street
    groups = []
    for p in parts:
        near = [g for g in groups if any(p.distance(q) < 60 for q in g)]
        groups = [g for g in groups if not any(g is n for n in near)] + [[p] + [q for g in near for q in g]]
    r = shapely.Point(to_m(*ref, lat0))
    best = min(groups, key=lambda g: min(q.distance(r) for q in g))
    dist = min(q.distance(r) for q in best)
    if dist > FAR_M:
        return None, dist
    run = max(best, key=lambda q: q.length)
    mid = run.interpolate(0.5, normalized=True)
    return from_m(mid.x, mid.y, lat0), dist


# ---------------------------------------------------------------- main
def main():
    raw = json.load(open(config.data('raw.json')))
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    # a provisional entry is already placed; only Nominatim may replace it
    todo = sorted({s['address'] for s in raw['stations'] if s['address'] and not cache.get(s['address'])})
    if not todo:
        print('geocode_overture: every address has coordinates — nothing to place')
        return

    # the neighbourhood of each address: the sub-quarter of its stations (volunteer
    # lists carry one), and the mean of the already-geocoded addresses sharing it
    def good(a): return cache.get(a) and not cache[a].get('provisional')
    area_of = {}
    for s in raw['stations']:
        area_of.setdefault(s['address'], (s.get('quarter') or '', s.get('sub_quarter') or ''))
    pts = defaultdict(list)
    for a, (q, sq) in area_of.items():
        if good(a):
            pts[('sq', sq)].append((cache[a]['lon'], cache[a]['lat']))
            pts[('q', q)].append((cache[a]['lon'], cache[a]['lat']))
            pts['all'].append((cache[a]['lon'], cache[a]['lat']))
    def ref_for(a):
        q, sq = area_of.get(a, ('', ''))
        for kind, key in (('sub-quarter', ('sq', sq)), ('quarter', ('q', q)), ('city', 'all')):
            p = pts.get(key) if key == 'all' or key[1] else None
            if p:
                return (sum(x for x, _ in p) / len(p), sum(y for _, y in p) / len(p)), kind
        return ((W + E) / 2, (S + N) / 2), 'bbox'

    # 1. the same street, already answered by Nominatim
    by_street = defaultdict(list)
    for a in cache:
        if good(a):
            for f in forms(split_address(a)[0]):
                by_street[f].append(a)
    left = []
    for a in todo:
        street, _ = split_address(a)
        same = next((b for f in forms(street) for b in by_street.get(f, [])), None)
        if same:
            g = cache[same]
            cache[a] = {'lat': g['lat'], 'lon': g['lon'],
                        'display': f'{street}, {config.CITY_HE} (לפי {same} באותו רחוב)',
                        'osm_type': g.get('osm_type'), 'addresstype': 'road',
                        'query_stage': 'same-street', 'provisional': True, 'same_street_as': same}
            print(f'SAME-STREET  {a} -> {same}')
        else:
            left.append(a)

    # 2. the middle of the named street, from Overture
    if left:
        if os.path.exists(STREETS):
            net = json.load(open(STREETS, encoding='utf-8'))
            print(f'streets (cached, Overture {net["release"]}): {len(net["streets"])} names')
        else:
            net = fetch_streets()
            json.dump(net, open(STREETS, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
            print(f'streets: {len(net["streets"])} names -> {STREETS}')
        names = defaultdict(list)
        for n in net['streets']:
            for f in forms(n):
                names[f].append(n)
        lat0 = (S + N) / 2
        for a in left:
            street, _ = split_address(a)
            hits = sorted({n for f in forms(street) for n in names.get(f, [])})
            if not hits:
                print(f'NO STREET    {a} — {street!r} is not a street name in Overture')
                continue
            runs = [seg for n in hits for seg in net['streets'][n]]
            ref, ref_kind = ref_for(a)
            p, dist = place_on_street(runs, ref, lat0)
            if p is None:
                print(f'TOO FAR      {a} — nearest {hits} run is {dist:.0f} m from its neighbourhood')
                continue
            cache[a] = {'lat': round(p[1], 7), 'lon': round(p[0], 7),
                        'display': f'{hits[0]}, {config.CITY_HE} (מרכז הרחוב — Overture Maps / OpenStreetMap)',
                        'osm_type': 'road', 'addresstype': 'road', 'query_stage': 'overture',
                        'provisional': True, 'source': f'overture {net["release"]}',
                        'neighbourhood_ref': ref_kind, 'dist_from_neighbourhood_m': round(dist)}
            print(f'OVERTURE     {a} -> {p[1]:.5f},{p[0]:.5f}  ({hits[0]}, {dist:.0f} m from '
                  f'the geocoded sites of its {ref_kind})')

    json.dump(cache, open(CACHE, 'w'), ensure_ascii=False, indent=1)
    missing = [a for a in todo if not cache.get(a)]
    print(f'placed {len(todo) - len(missing)} of {len(todo)}; still missing: {missing}')


if __name__ == '__main__':
    main()
