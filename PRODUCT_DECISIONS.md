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
  and you get its ramp — orange for the coalition, blue for the opposition. Consistent with everything else on
  the map, and no new semantics to learn.
- ~~**Marker area follows the potential in this mode**, not the electorate — otherwise the
  headline number is not the thing the eye is measuring.~~ **Superseded in Round 3:** it
  put both channels on the same variable and cost the map its second one. See Round 3.
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

Blue, orange, green and purple are already spoken for (the two blocs, other
lists, turnout). The delta ramp must not read as a bloc. Two candidates were **measured
and rejected** with the dataviz skill's validator:

- **gold ↔ teal** — gold collapses to **ΔE 2.5** against the bloc orange under
  deuteranopia. A colourblind reader would read "below baseline" as "opposition".
- **crimson (hue 25)** — one step lands **ΔE 4.7** from the bloc orange.

**Chosen: rose, OKLCH hue 0.** Worst separation ΔE **11.2** from the bloc orange and
**12.5** from the bloc blue; passes all four ordinal checks (monotone lightness,
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

# Round 2 — marker interaction on mobile

**Reported:** tapping a circle on a phone jumps straight to the data, which feels bad.
Suggestion: a small hover instead, with a link to the full data inside it.

**Decided: a two-step tap.** A marker tap now opens a compact card *in place on the map*;
the full site panel is reached only by an explicit `כל הנתונים באתר` button on that card.

**Why it behaved that way.** Round 1 routed a marker tap through `selectSite`, which on a
narrow layout switches to the list tab — so the answer to "what is this circle?" cost the
user the map and a trip to another tab. On a pointer device this was never visible: the
sidebar sits beside the map, so a click just fills a panel already on screen.

**The mechanism, and why a tooltip could not do it.** There is no hover on touch, so
Leaflet opens tooltips on tap — but tooltips are `interactive: false`, so a link inside
one is not tappable. The card is a Leaflet **popup**, which is click-driven and can hold
real controls. Bindings are chosen per layout (`bindMarkerUI`) and **re-bound when the
viewport crosses the breakpoint**, so a resize never leaves the wrong one attached:

| layout | tap / click a marker |
|---|---|
| pointer (>1000px) | hover tooltip; click opens the panel already beside the map |
| touch (<=1000px) | compact card on the map; the panel only via its button |

The card carries the four things that identify a site — name and address, the active
potential figure, turnout with its national delta, and the leading bloc — and nothing
else. List rows are unchanged: tapping one still opens the panel directly, because that
is already a list interaction and costs no context.

**Regression checks:** `phone_tap` asserts a marker tap leaves `view == 'map'` with the
card open and the detail panel closed; `phone_card_more` asserts the button is what
reaches the panel; `desktop_tap` asserts the pointer path is untouched.

`cardTitleClearsClose` guards a smaller thing worth keeping: Leaflet pins its close
button to the physical **top-right**, which under RTL is where the title text *begins*,
so the gap belongs on the inline-start side. The check measures the text with a `Range`
rather than the element box — a `display:block` title spans the full width and would
always look like it overlaps.

---

## Known issue, not fixed this round

The **existing turnout ramp** fails the same light-end contrast check the new ramps pass:
`--seq-0: #eadcf3` measures **1.28:1** against the light surface, below the 2:1 floor.
`HANDOFF.md` claims it "starts at `#86b6ef` so the lightest step clears the 2:1 floor" —
that is not the shipped value. Left alone deliberately: fixing it changes the appearance
of the map's most-used mode, which is not what this round was asked for. Worth a decision
next round.

---

# Round 3 — the mode control, and what the marker size is for

Two things, both about the map saying more per glance.

## 3.1 The colour mode was three taps away, on the wrong screen

**Reported:** on a phone, changing what the map is coloured by costs
`רשימה` → expand `סינון וצביעה` → pick the mode → back to `מפה`.

**Decided: put the control on the map, in that layout only.** A compact
`<select>` sits in `.mapbar` beside `מבט על כל העיר`, with the bloc-target select
next to it whenever the mode is `potential`. Both are `display:none` above 1000px,
where the filter panel is already beside the map and a second copy would just be
noise.

**Why a select and not the segmented control.** Five modes as a segment needs ~280px
and two rows; a select is one tap to open, shows the current mode as its own label,
and leaves room on the bar for the two buttons that were already there. The bar wraps
below the zoom control's reserved 52px, so nothing is ever pushed off the map.

**The state, not a second state.** Both copies go through `setMode()` / `setPotTarget()`,
which write the state and then sync *every* control, so the panel's segment and the
map's select cannot drift apart. That is the whole point: the same control in two
places, not two controls.

**Regression checks:** `phone_mapmode` asserts that changing the mode from the map bar
leaves `view == 'map'` and moves the panel's segment too; `phone_mapmode_sync` asserts
the reverse direction; the desktop `light` scenario asserts `mapModeUsable: False`, so
the duplicate never appears where it is not wanted.

## 3.2 Potential mode was spending two channels on one variable

**Reported:** in potential mode the size should go back to `בעלי זכות בחירה` and let the
colour carry the potential.

**Decided: yes — size is the electorate in every mode now.** Round 1 sized potential mode
by the potential so "the headline number is the thing the eye measures". In practice the
two encodings were the same number twice over: potential is
`eligible × (1 − turnout) × bloc share`, so a big marker was dark *because* it was big,
and the map carried one variable where it has room for two.

With area on the electorate and colour on the potential, all four combinations mean
something again:

| | pale | dark |
|---|---|---|
| **large** | a big electorate that mostly turned out | a big electorate with a lot still on the table — the target |
| **small** | a small site, little to gain | a small electorate that barely voted — invisible under the old scheme |

Two things fall out of it. Marker size is now **stable across modes**: switching the
colour no longer resizes the map, so the modes are comparable and the eye keeps its
anchor. And the `על הנתונים` panel's claim that *"the marker's **area** is proportional
to the number of **בעלי זכות בחירה**"* — written in round 1 and quietly false in the
default mode ever since — is true again.

The per-target radius normalisation (`sizeK`, `_kCache`, `POT_SIZES`) went with it: one
scale, one size legend, `700 / 1,600 / 3,500` בעלי זכות in every mode.

**Regression check:** `radiusModeIndependent` evaluates `radiusOf()` for the same site
under all five modes and asserts the radius does not move — run on every scenario, not
just the potential ones.

---

# Round 4 — palette, and a legend that told the truth in only one theme

Three small things, reported off one screenshot of the phone in dark mode.

## 4.1 Opposition is blue, coalition is orange

**Asked:** opposition blue, everywhere in the project.

**Done as a swap of the two bloc values, not a new palette.** `--bloc-coalition` and
`--bloc-opposition` exchange hexes, and so do the pairs built on them: the diverging
margin scale (`--div-opp-*` ↔ `--div-coal-*`) and the potential ramps
(`--pot-coal-*` ↔ `--pot-opp-*`), in both themes. Nothing in the JS refers to a hue — it
reads `BLOC_VAR` — so the swap is entirely in the tokens.

It is the **same validated triple**, only reassigned, so every all-pairs CVD measurement
still holds with the bloc names exchanged; the rose delta ramp keeps its ΔE 11.2 / 12.5
clearance from both. A bloc still keeps one colour across every mode. `--accent` stays
`#2a78d6`, which now matches the opposition rather than the coalition — it is UI chrome
(buttons, focus rings, party bars), and it was equally tied to a bloc hue before.

## 4.2 "Big and dark" was only true in light mode

**Reported:** the legend note and the colour scale contradict each other.

They did, in dark mode only. Every sequential ramp was inverted for dark mode — light =
high, the usual "more ink on a dark ground" convention — but the note says
`סמן גדול וכהה = ציבור בוחרים גדול שהרבה ממנו לא הגיע לקלפי`. In dark mode the darkest
markers were the sites with the *least* potential, i.e. exactly backwards.

**Decided: the words win.** The potential ramps and the rose ramp are no longer redefined
for dark mode — one ramp, both themes, darker always meaning *more*. Their dark ends were
checked against the dark surface and clear **2.5:1**, above the 2:1 ordinal floor, so the
deepest step stays readable. The cost is real and accepted: on a dark ground a dark marker
recedes, so the highest-potential sites are no longer the most luminous ones. A rule the
reader can trust is worth more than the extra pop.

**Not fixed:** the turnout ramp still inverts in dark mode, so its own note
(`סמן גדול ובהיר…`) reads backwards there. Sharing the light ramp would put `--seq-5`
(`#4a2465`) at **1.55:1** against the dark surface — it needs a new dark-mode ramp
authored in the same direction, not a deletion. Left for a decision.

## 4.3 The potential legend said too much

The note carried the reading rule, the filtered total, and the estimate caveat — six lines
in a 190px box on a phone. Trimmed to the reading rule alone. Nothing is lost: the city
total is the first header tile, the filtered count is in the list header above the list,
and the estimate caveat is in both the site panel and `על הנתונים`.

---

# Round 5 — the map picks a side: הדמוקרטים

**Asked:** *"I want to specifically support הדמוקרטים. I want a selector
אופוזיציה / הדמוקרטים (default הדמוקרטים), and when it is set, potential and everything
else should point to הדמוקרטים (קולות של העבודה ומרצ)."*

**Decided: build it as a `camp`, not as a fourth bloc — and let it repoint the map.**

## 5.1 Why a camp and not a bloc

הדמוקרטים is **inside** the broad opposition, not beside it. The three blocs partition the
valid vote (`coalition + opposition + other = valid`) and everything built on that
partition — the bloc split, `גוש מוביל`, `פער בין הגושים`, the filter chips — stays true
only while it is a partition. אמת (6,654) + מרצ (6,417) = **13,071 votes, 9.35% of Haifa's
valid vote**, and every one of them is already counted inside the opposition's 88,413.

So the camp is carried **alongside** the blocs, never instead of one:

| the blocs keep | the camp adds |
|---|---|
| bloc split stack, `גוש מוביל`, `פער בין הגושים`, the filter chips, and every bloc option, column and sort they always had | one more option in the group select (the default), one header tile, one sort, two table columns, one bar in the site card and one line under the bloc split — all of them permanent, none of them replacing a bloc's |

Everywhere the camp appears next to the partition — the site card's bloc split and the
potential bars — it is **labelled as a subset** (`הדמוקרטים — מתוך האופוזיציה`) and its bar
is scaled against the blocs, so it can never be read as a fourth slice of the same pie.

## 5.2 One selector — the group select that was always there

**First attempt, and the correction.** The `הגוש שלי` select already picked whose
non-voters to count. I replaced its `אופוזיציה רחבה` option with `המחנה שלי`, resolving to
whichever camp a second, new select had chosen — so that picking a camp would repoint the
sort, the table and the header tile too, not only the potential.

**Reported immediately: "I lost the opposition now."** And that was the whole of it. The
broad opposition had stopped being a thing you could point the map at without first
changing a control on another panel — on a phone, another *tab*. Two controls where there
had been one, and the one that was already there had lost an option. The ask was never for
a mode; it was *"add הדמוקרטים"*.

**Decided: the camp is an option in that select, beside the blocs, and nothing else
changes.** The select is the original four again — `כל מי שלא הצביע`, the 2022 coalition,
the broad opposition, the other lists — with `הדמוקרטים` inserted after the first, and it
is the default. One control, five options, no second state to get wrong. The map-bar copy
on a phone gets the same five, so every group is one tap away there too.

**What the camp keeps, now unconditionally.** The things a second control was invented to
drive are simply always present, because a camp is a permanent group and not a mode: its
own header tile, its `שיעור הדמוקרטים` sort beside `שיעור אופוזיציה רחבה`, its two table
columns, its bar in the site card and its line under the bloc split. They no longer appear
and disappear with a setting, and the blocs' own columns and sorts came back untouched.

**The rule this leaves behind:** adding a group to a map is adding an option. Do not
convert an existing control into a pointer at a new one — the reader loses a choice they
had, and gains a concept they did not ask for.

## 5.3 The camp is `config.py` data, not code

`config.CAMPS` names each camp, its party letter codes, the bloc it sits inside and its
caveat; `DEFAULT_POT_TARGET` picks the group the map opens on — a camp key, a bloc, or
`none`. `build_data.py` totals it at station, site and city level and adds
it to `pot`; the front end reads `DATA.camps` and inserts each camp's option into the two
group selects and the sort, its columns into the table, its bar into the site card and its
tile into the header. Another camp, or another election's camps, is a config edit — no JS
change. The blocs are untouched by any of it.

## 5.4 The colour — measured, per Round 1 §3

הדמוקרטים sits inside the opposition, so it **cannot borrow the opposition's hue**: the map
would say "opposition" while the legend said "הדמוקרטים", and the two are 6.8x apart in size.
It needs a hue of its own, and blue, orange, green, purple and rose are all spoken for.

**Chosen: teal, OKLCH hue 210.** Measured with the dataviz validator against the three bloc
colours, worst CVD ΔE (min of protan/deutan) **15.9 / 12.6 / 10.0** against the blue, the
orange and the green at the deep end — better separation than the shipped rose ramp manages
against the same three (3.5, on green). Deliberately stated by hue and not by bloc: Round 4
swapped which bloc wears the blue and which the orange, and the measurement is of the hues,
so it survived that swap untouched — as would the next one.

```
dem   both themes  #00bed5 #00a7bc #0090a2 #007a8a #006572
```

**One ramp, both themes**, per Round 4.2 — darker has to keep meaning "more" everywhere, so
the ramp is not redefined for dark mode. Its dark end clears **2.57:1** against the dark
surface, the widest margin of any ramp in the file (the others sit at 2.30–2.46), and the
light end 2.19:1 against the light one. Monotone lightness, adjacent ΔL ≥ 0.06, single hue.
The camp's **categorical** colour does still get a dark value (`#00707e`), exactly as the
bloc colours do: it is a dot beside a label, not a step on a scale.

**One accepted failure, recorded so it is not "fixed" blind:** at hue 210 the sRGB gamut
tops out at C ≈ 0.08, below the validator's 0.10 categorical chroma floor. Raising the
chroma means moving the hue toward 240, the blue's neighbourhood — a camp that reads as one
of the blocs is the worse error, whichever bloc is wearing blue this round. Every categorical use of the
colour (the camp's dot, its bar) ships with its label beside it.

**Its own bins.** The camp's per-site potential tops out at **364**, against 1,532 for the
opposition. Reusing the opposition's `100 / 250 / 450 / 700` would paint 126 of 140 sites in
the palest step. The camp scale is `50 / 100 / 175 / 260` — 64 / 43 / 22 / 8 / 3 sites per
step, the same shape the other ramps have.

## 5.5 The caveat, and where it lives

הדמוקרטים **did not exist in November 2022**. העבודה and מרצ ran as two separate lists and
מרצ did not clear the threshold; the party was formed from their merger in 2024. Summing
them is a retrospective construct, and it is stated in three places: under the group select
when הדמוקרטים is the one selected, in the site card, and in `על הנתונים`, which also gives the city totals. **Not** in the
potential legend — Round 4.3 cut that box down to the reading rule alone, and a caveat that
costs six lines of a 190px box on a phone is exactly what it cut. Everything
in Round 1's estimate caveat still applies on top of it.

## 5.6 The header tile sums the sites

The camp's header tile is the **sum of the 140 site potentials**, not `city.pot` — the
city-level figure applies one city-wide vote share to all 112,642 non-voters, and comes out
**10,534** against the sites' **10,142**. Both are defensible; only one of them agrees with
the legend total sitting directly below it and with every number in the list. `build_data.py`
still emits `city.pot` (it is in the build log), so this is written down: do not "simplify"
the tile back to it.

**Regression checks:** `light` asserts the map opens on the camp and pins the **full option
list of both group selects and of the sort** — the check that would have caught the missing
`אופוזיציה רחבה` the moment it went; `pot_opp` asserts the opposition is still one pick;
`table` and `table_opp` assert the camp's columns are there whichever group is selected;
`phone_table` asserts the phone's six columns spend one slot on the camp.

---

# Round 6 — Beit Shemesh: a map for the volunteers, not a campaign

**Asked** (the coordinator of the city's election-day observers, 8–22 Sept 2026, after
seeing the first Beit Shemesh build — which was the Haifa analysis map pointed at Beit
Shemesh):

* *"Mark the leading parties in each station — don't colour them, election law says it
  may not be associated with a specific party — and colour in red the stations whose
  turnout is abnormal."* *"There can't be any party leaning if I send it to everyone"* —
  and, election law aside, it is something to be careful about.
* What it is for: help people understand the city, help the coordinator put volunteers
  who want to be together at stations close to each other, and advise them where to
  register — volunteers ask for a station themselves.
* On the first build (voice note): it will help the older volunteers *"who will need to
  understand where they are registering"* — e.g. colour one area's stations.
* Then the updated station list, *"with colours"*, *"to update what we talked about — the
  stations and how they are shown"*.

**Decided: a second profile, not a mode of the analysis map.**

## 6.1 Why a profile

The analysis map is a campaign tool and says so — its default is the potential of
הדמוקרטים. A neutral *mode* on it would still ship the campaign to every volunteer in the
same file, one tap away. So `config.PROFILES` names what a map is for, and the Beit Shemesh
build (`volunteer`) has none of it: no potential, no blocs, no camp, no colour for a party.
What the two share is the shell — map, markers, labels, list, card, table, phone layout —
now `src_core.js`, with each product in its own script and the template's
profile-specific markup in `<!--@profile-->` blocks. The split moved Haifa's code
verbatim; Haifa's data rebuilds byte-identical and its 36 scenarios render
pixel-identical screenshots.

## 6.2 Colour: the observers' risk level — which is what "red = abnormal turnout" asks

The list's colours are the observers' own national mapping of at-risk stations, built —
in the coordinator's words — from signs in past elections: turnout that makes no sense
(*"97–98% where it used to be 70%"*), ballots in the names of the dead. That is the
judgement "red = abnormal turnout" asks for, made by the people who run the observers,
with more than turnout behind it. Computing our own flag as well would put a second red
on the map meaning something else, and the signal it describes is a jump *between*
elections — the repo holds 2022 only. So the markers wear the list's colours, and the
2022 turnout is shown per building as a number, against the city and the country.

**Palette, measured.** The list names its categories by colour — אדום, כתום, צהוב — so the
hues are literal: the dataviz palette's status steps, critical `#d03b3b`, serious
`#ec835a`, warning `#fab219`, the same in both themes (status colours are mode-invariant).
All-pairs, CVD separation passes (worst ΔE 11.3, orange↔yellow) but the normal-vision
floor does not (13.6 against 15, the same pair). Accepted, with the mitigation the status
palette prescribes: the colour never appears without its word — legend, list row, card,
panel, table and filter chips all name it — and yellow is one building of 57.

**Area** is categorical: blue and aqua (slots 1 and 3), all-pairs CVD ΔE 23.1 light / 19.6
dark. Slot 2 is skipped on purpose — an orange area would read as the orange risk level.
A third area gets violet, which passes in light only (dark ΔE 1.9 against the blue); its
label is always beside it. HTML marks reference the tokens themselves (`var(--risk-red)`),
so a theme switch repaints them without a re-render.

## 6.3 A building takes its most severe station's colour

A marker is a building, and a building is where a volunteer stands. One red station in it
is a red posting. The card lists every station with its own colour, a mixed building says
so wherever its colour is named (`2 אדום, 1 צהוב`), and the legend states the rule.

## 6.4 Area is a colour mode and a filter

The voice-note ask — show a place's stations so a volunteer sees where they are
registering — is the `אזור התנדבות` mode (each place its own colour) plus the area
chips (one place alone). The area is the name of the list's sheet a station is on;
the list's status sheet gives each place's part of the city (`בית שמש 1` = רמת בית שמש,
`בית שמש 2` = the old city), kept in `config.CITIES[...]['areas']`.

## 6.5 2022 as text, per building

The leading lists are the building's three largest in 2022 with their share, in plain
text; turnout sits beside the city's and the country's. It is per **building**, not per
station: 93 of the 156 station numbers are new, and even a station that kept its number
changed its voters (641 → 555 eligible at one). A 2026 building is matched to its 2022 one
by address, else by the same place name within 600 m (a renamed street, a re-worded
address); 43 of 57 match and the other 14 say *אתר חדש*.

## 6.6 Made for finding a station

* Search covers the **streets whose voters each station serves** (a column of the list),
  so a volunteer can find their own street's station — or a friend's.
* The card has **navigation by address** (Google Maps, Waze): a street-level marker can
  sit a few hundred metres from the building, and the address is what a phone's map app
  resolves best.
* The list opens **red first**, then by station number.

## 6.7 Neutrality is a test, not a promise

Every volunteer scenario asserts that no bloc, potential or camp word is on screen and
that every marker's fill is in the risk or area palette. The about panel says it in words:
*המפה אינה מזוהה עם אף מפלגה*.

## 6.8 The list, and what stays out of the repo

The workbook also names the people who run each volunteering place. It is never
committed (`*.xlsx` is ignored), and `import_station_list.py` reads only the station
sheets. Where the per-place sheet and the national sheet disagree on a colour (7
stations), the per-place sheet wins — it is the working list — and the national colour is
shown beside it in the card and listed in the about panel.

## 6.9 Deferred

* **Our own cross-election turnout flag** — needs Knesset 21–24 per-station results and a
  station match across renumbering; the list's colours already carry the judgement.
* **Who is at which station**, and matching volunteers by preference — the volunteer data
  stays in the network's own system; this map holds none.
* **`בית שמש 3`** — the list has the sheet but no stations yet; filling it is a list
  update, no code.
* **Sixteen provisional positions** — new addresses placed at street level while Nominatim
  was unreachable; a networked rebuild replaces them (see `HANDOFF.md`).
* The phone legend is as large as Haifa's; making it collapsible would serve both maps.
