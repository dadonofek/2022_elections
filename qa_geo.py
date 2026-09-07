import json, collections, math, config
cache = json.load(open(config.data('geocache.json')))
raw = json.load(open(config.data('raw.json')))['stations']
addr_voters = collections.Counter()
for s in raw: addr_voters[s['address']] += s['voters']

bad_city, notes = [], []
for a, g in cache.items():
    if not g: notes.append(('NO GEO', a)); continue
    if config.CITY_HE not in g['display']: bad_city.append((a, g['display']))
# same coordinate reused by different street names -> likely wrong
by_pt = collections.defaultdict(list)
for a, g in cache.items():
    if g: by_pt[(round(g['lat'], 5), round(g['lon'], 5))].append(a)
collide = {p: v for p, v in by_pt.items() if len({x.rsplit(' ', 1)[0] for x in v}) > 1}

print('total addresses:', len(cache), '| geocoded:', sum(1 for v in cache.values() if v))
print(f'outside {config.CITY_HE} in display_name:', len(bad_city))
for a, d in bad_city: print('   ', a, '|', d[:80])
print('\nprecision:', collections.Counter((g.get('addresstype') if g else None) for g in cache.values()))
print('\ndistinct streets sharing one point:', len(collide))
for p, v in list(collide.items())[:10]: print('   ', p, v)
