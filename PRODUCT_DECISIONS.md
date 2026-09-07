# Product decisions — round 1 (PM feedback, Nov 2022 Haifa map)

Source: product-manager review of the shipped map. This records what was asked, what
was decided, **why**, and what was deliberately left out. It is the reference for the
next round — read it before changing the metrics, the palette or the mobile layout.

Status: **implemented**, except where marked *deferred*.

---

## 1. Potential — "כמה קולות יושבים באתר הזה ולא הגיעו"

**Asked:** a computed field `בעלי זכות בחירה × (1 − אחוז הצבעה) × נטיית הגוש`, to turn
the map from a description into a task list.

**Decided: build it, as the default view.**

`eligible × (1 − turnout)` is exactly the non-voter count, so the field reads: *if the
people who did not vote here had voted the way their voting neighbours did, how many
votes would each bloc have gained.*

It earns its place because the weighting changes the answer — ranked by raw non-voters
the list is just "big Carmel schools", but weighted by bloc it is a different list:

| by raw non-voters | by coalition potential | by opposition potential |
|---|---|---|
| הריאלי 2,310 | בית יעקב 1,208 | הריאלי 1,532 |
| דרור 2,116 | ת"ת תורת אמת 914 | שלווה 1,430 |
| למחוננים 1,856 | רמב"ם 871 | דרור 1,411 |

City-wide: **112,642 non-voters against 140,650 who voted** — the untapped pool is 80%
the size of the actual electorate. That number is now the first header tile.

**Decisions inside the decision**

- **Bloc selection is explicit, and neutral by default.** The metric is directional, so
  a `הגוש שלי` selector drives it. It defaults to `כל מי שלא הצביע` — raw non-voters,
  no attribution — so the map does not pick a side unless the reader does.
- **Hue says which bloc, lightness says how many.** Rather than invent new hues, the
  potential ramp is a sequential ramp built on the *existing* bloc hue: pick coalition
  and you get a blue ramp, opposition an orange one. Consistent with everything else on
  the map, and no new semantics to learn.
- **Marker area follows the potential in this mode**, not the electorate — otherwise the
  headline number is not the thing the eye is measuring.
- **Fixed bins, never quantiles of the filtered set.** A colour must not change meaning
  when the user filters. `רשימות אחרות` gets its own scale (site max 97, vs 1,532).
- **It is labelled an estimate, and the caveat is in `על הנתונים`.** Two reasons it is an
  **upper bound**, not a forecast: it assumes non-voters lean like voters at the same
  site, and the `בזב` register in big cities counts people registered but no longer
  living there. Worth defending — this is the number most likely to be quoted as fact.

## 2. Baseline — "55.5% נראה נמוך עד שמבינים שזה בדיוק ממוצע העיר"

**Asked:** show a delta so the colour says something stronger. PM suggested
`−12% מממוצע חיפה`.

**Decided: build the delta, but baseline it on the NATIONAL average, not the city's.**

Direction from the PM on this round: *"keep it. I want it to show low numbers."*
Against the city's own mean that is impossible by construction — half the sites sit
above it and every colour converges on zero:

| baseline | sites below | median delta | range |
|---|---|---|---|
| city 55.53% | 70 / 140 | −0.1 | −32.3 … +21.8 |
| **national 70.63%** | **123 / 140** | **−15.2** | **−47.4 … +6.7** |

Haifa is **15 points below the country**. That is the story, and only the national
baseline tells it. The city delta is still shown, as a secondary figure on every site
card and as its own table column, which answers the PM's original complaint directly.

**Consequence for the scale:** because the national delta is one-sided (123 of 140
below, and 15 of the 17 above are within 7 points), it is a **deficit ramp** —
sequential, with one neutral step for sites at or above the baseline — **not** a
diverging scale. A symmetric diverging scale would spend half its range on 17 sites.

The national figure is **derived, not asserted**: `build_data.py` recomputes it from
`data/expb.csv` (4,794,593 / 6,788,804 = 70.63%) and falls back to
`config.NATIONAL_TURNOUT` only when that file is absent.

## 3. Palette — decided by measurement, not by eye

*(PM delegated this one.)*

Blue, orange, green and purple are already spoken for (coalition, opposition, other
lists, turnout). The delta ramp must not read as a bloc. Two candidates were **measured
and rejected** with the dataviz skill's validator:

- **gold ↔ teal** — gold collapses to **ΔE 2.5** against opposition orange under
  deuteranopia. A colourblind reader would read "below baseline" as "opposition".
- **crimson (hue 25)** — one step lands **ΔE 4.7** from opposition orange.

**Chosen: rose, OKLCH hue 0.** Worst separation ΔE **11.2** from opposition orange and
**12.5** from coalition blue; passes all four ordinal checks (monotone lightness,
adjacent ΔL ≥ 0.06, light-end contrast ≥ 2:1, single hue) in **both** light and dark.

```
delta   light  #fe87af #e46f97 #ca5881 #b0416b #972956   neutral #b0ada4
delta   dark   #8f204f #a83964 #c1507a #db6890 #f57fa7   neutral #5b5b54
```

The potential ramps are sequential ramps on the existing bloc hues, all six validated
the same way (see `src_map.html` tokens). The rose ramp doubles as the "no bloc
selected" potential ramp — both encode *what is missing*.

**If you change any of these, re-run the validator. Do not eyeball it.**

## 4. RTL — the panel belongs on the right

**Asked:** header on the right, panel on the left; in a Hebrew UI the panel should be on
the right.

**Decided: fixed.** Root cause: `.main` is a flex row and under `direction:rtl` the
*first* DOM child takes the right — and `.mapwrap` was first. Fixed by moving
`.sidebar` ahead of it in the DOM, which also corrects tab order and screen-reader
order (an `order:` property would not have). Also flipped `border-inline-start` →
`border-inline-end`, and the selected-row accent bar, which was pinned to the physical
left. Regression check: `sidebarRightOfMap` in `test_map.py`.

## 5. Default sort

**Asked:** the default should not be `לפי מספר קלפי`.

**Decided:** default is now **`פוטנציאל — מהגבוה`**, which is what makes the list a task
list. `אחוז הצבעה — מהנמוך` and `פער מהארצי — מהגדול` follow it. `לפי מספר קלפי` stays
in the list, last — it is how someone looks up one specific box in the field.

The sort does **not** follow the colour mode. Implicit control changes are disorienting;
one default, explicit override.

## 6. Mobile — the outage

**Asked:** the page does not scroll, the map swallows the touch, and the whole panel
below it does not work.

**Measured on a 390×844 phone — it was worse than reported:**

| | before |
|---|---|
| header | **279px (33% of the screen)** |
| space left for the sidebar | 126px |
| space its panels needed | 338px |
| search box | 1px below the fold |
| sort dropdown | 222px off-screen |
| site list | height **0**, 258px off-screen |
| document scrollable | **false** |

The cause was not the map swallowing touch. `.app{height:100vh; overflow:hidden}` means
the document can never scroll on any device; the stacked mobile layout then squeezed the
sidebar to a third of what it needed. Every control below the map was unreachable.

**Decided: map and list become separate tabs below 1000px** (`מפה` / `רשימה`), each
getting the full pane. Chosen over letting the document scroll (a 50vh map means endless
scrolling, and pan-vs-scroll still fight) and over a drag-handle bottom sheet (nicest,
but the gesture conflicts are fiddly and it is the most work). Tapping a marker switches
to the list tab, where the detail panel lives.

Also: filters fold into a collapsible `<details>` on mobile so the list gets the screen,
and `map.invalidateSize()` runs on tab-switch since Leaflet cannot measure a hidden map.

**Why this shipped:** the old `narrow` test scenario was 900×1100 and asserted
`listItems == 140` — a count of DOM nodes. The list rendered at **zero height** and the
test passed. The suite now asserts controls are *on screen with real size*.

## 7. Header statistics

**Asked:** five tiles eat a quarter of the screen, and a long number wraps alone looking
like a bug. Cut to three, or put the rest behind a control.

**Decided:** seven tiles now exist, but mobile shows **three** with the rest behind
`עוד`. The three lead with the story rather than the bookkeeping:
`קולות שלא הגיעו` · `אחוז הצבעה` · `פער מהארצי`. `קולות כשרים` and the rest are
secondary. Tile labels are `white-space:nowrap`, and the brand subtitle is hidden on
mobile — together these cut the header from 279px to roughly a third of that.

## 8. Hamburger for the secondary controls

**Asked:** put `טבלה`, `מצב בהיר`, `על הנתונים` in a hamburger.

**Decided:** yes, **mobile only** — on desktop three visible buttons are more
discoverable than a menu.

Related, raised back to the PM and decided here: the table view is 15 nowrap columns and
was unusable on a phone even once reachable. Mobile now gets a **6-column subset**
(site, turnout, delta, non-voters, both potentials) rather than being hidden entirely.

## 9. Whole country — *deferred*

**Asked:** add all of Israel, with search to filter to a region.

**Decided: not this round** — direction from the PM was *"keep Haifa for now."*

Recorded because the scoping matters for whenever it comes back:

- `data/expb.csv` **already holds the whole country** — 12,545 stations across 1,216
  localities, with the full party breakdown. National turnout is already computed from
  it for the delta baseline.
- What does **not** exist nationally is **addresses**. The Haifa station→address
  workbook was hand-built from Haifa's municipal election notice; there is no national
  equivalent and there are 1,216 localities.
- So **locality-level national is feasible now** (1,216 points, ~75 KB, blocs already
  national in `config.BLOCS`). **Station-level national is not** — it is this project
  times 1,216, and the cost is data sourcing, not engineering.
- Suggested shape when it returns: a two-layer map — one marker per locality zoomed out,
  station-level markers on zoom-in for cities that have an address workbook.
- **Architectural fork to decide early:** at 1,216 locality points the single-file
  `file://` design still holds. Station-level data for more cities breaks it and forces
  per-city JSON fetched on demand — which ends the "no server, no build, opens anywhere"
  property the project is built around.

---

## Known issue, not fixed this round

The **existing turnout ramp** fails the same light-end contrast check the new ramps pass:
`--seq-0: #eadcf3` measures **1.28:1** against the light surface, below the 2:1 floor.
`HANDOFF.md` claims it "starts at `#86b6ef` so the lightest step clears the 2:1 floor" —
that is not the shipped value. Left alone deliberately: fixing it changes the appearance
of the map's most-used mode, which is not what this round was asked for. Worth a decision
next round.
