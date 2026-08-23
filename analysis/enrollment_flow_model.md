# The statewide enrollment flow model

How schoolfactors.org/enrollment models where California's public-school students
live versus where they attend — every district, ACS vintages 2009–2024. This is the
statewide generalization of the LAUSD reconciliation (`analysis/
residual_reconciliation.md`); code lives in `src/schoolfactors/analysis/
enrollment_geo.py`, `enrollment_flows.py`, `enrollment_export.py`.

**Sign convention: positive = net importer** (an area whose schools seat more
students than its resident public-school children account for). Every flow this
model produces is a **net accounting residual** — apparent, not observed transfers.
California publishes no student-level origin→destination data (that would be
CALPADS); nothing here should be read as "N students moved from district A to
district B."

## 1. Sources and windows

| Ingredient | Source | Coverage |
|---|---|---|
| Resident children 5–17 by enrollment status | ACS 5-year B14003, school-district geography (unified / elementary / secondary summary levels) + county | vintages 2009–2024, 16 windows (2005-09 … 2020-24, no gap) |
| Annual overlay | ACS 1-year B14003 | 2005–2024 (no 2020), unified districts ≥65k population (~119), all counties, state |
| Census-day seats per school | CDE enrollment files (historical 1981–2023 + current format 2023-24+), stitched, `enr_type='C'` | springs 2005–2026 |
| School attributes | CDE directory: charter, funding type, virtual flag, coordinates, NCES LEAID | current snapshot |
| District polygons | TIGERweb School MapServer, ACS-2024 layers | current geometry (see §10) |
| Population controls | Census popest intercensal 2000-2010 + vintage 2005-09 county age files | pre-2010 correction |

**Window correspondence.** ACS vintage v covers calendar years v−4…v. The CDE side
of every comparison is the **mean census-day enrollment over springs v−3…v+1** —
the five school years overlapping the window. This is the convention established in
`residual_reconciliation.md`; under end-of-window conventions the state-level
mismatch trends with enrollment decline and the calibration below would be invalid.
Overlapping windows share 4/5 of their sample: **window-to-window changes are not
annual signal**, which is why detail pages label the series "5-year windows" and
overlay true annual (ACS 1-year) data where it exists.

## 2. The residence measure

B14003 counts resident children 5–17 by sex × enrollment status (public / private /
not enrolled) × age band (5-9, 10-14, 15-17). We sum sexes; a geography missing any
cell reads as null, never as a partial sum. 90% margins of error combine
root-sum-square; the "controlled" sentinel (−555555555) contributes zero margin.

Each school-district summary level **partitions the state** (each carries a
Remainder-of-California row, geoid 0699999): unified districts cover their
territory; elementary and secondary districts tile the rest twice over (an
elementary resident is inside both an elementary and a secondary district). Raw
B14003 for a district geography counts **all** children living in the polygon
regardless of grade; the grade split is ours (§6). Two summary levels are never
summed — that double-counts.

## 3. Population-control correction (pre-2010 bias)

ACS years 2005–2009 were weighted to Census-2000-based county population estimates
that overstated some counties (documented for LA in
`known_issues/acs-pre2010-population-controls-la-county.yaml`). The correction
factor for county c, year y ≤ 2009 is

    f(c, y) = intercensal children 5-17 (2010-consistent) / vintage-y postcensal 5-17

computed for **all 58 counties** (`enrollment_flows.control_factors`). ACS 1-year
observations for 2005–2009 are multiplied by f directly. ACS 5-year windows ending
2009–2013 mix control regimes, so they get the **mean of per-year factors** with
f≡1 for years ≥ 2010 — vintage 2009 fully corrected, vintage 2013 at 1/5 weight
(`known_issues/acs5-mixed-population-controls.yaml`). District areas use their
administrative county's factor — a per-district proxy and therefore a bias term:
sub-county heterogeneity in the 2000s control error is not observable. MOEs scale
by the same factor; corrected points carry a `cf` flag in the site data.

## 4. The seats measure and universe calibration

Census-day enrollment per school comes from the historical school-level files
(`enr_type='C'` or null, adult enrollment excluded) stitched with the current
format (school rows, total reporting category). Grade columns (TK/K, 1–12,
ungraded elementary/secondary) ride along for the grade split.

ACS's "enrolled in public school" universe (residents 5–17) and CDE's census-day
headcount (TK 4-year-olds, 18+ seniors, adult-ed excluded but other adults not
fully) differ by a stable amount. Per vintage we measure

    m = (state CDE 5-spring mean − state ACS public residents) / state CDE

— 3.3–6.5% across the 16 vintages, no trend — and convert every CDE seat count to
resident-children units by multiplying (1−m). Because m is measured at the state
level, where inter-district flows net out, it absorbs only universe mismatch, not
real movement.

## 5. School classification and siting ("model the schools, not the district")

Districts are heterogeneous — a district's territory can host its own schools,
other agencies' charters, magnets drawing across boundaries, and virtual programs
counted administratively but not physically. So the model classifies and sites
**individual schools**:

- **Class** (directory): `charter='Y' AND virtual∈{F,V}` → charter-virtual;
  `charter='Y'` → charter brick-and-mortar; else district-run. The virtual flag is
  present-day and misses unflagged non-classroom-based programs — the virtual pool
  is a **lower bound** (`known_issues/cde-virtual-flag-lower-bound.yaml`).
- **Siting** follows the evidence for who a school serves:
  - **District-run and affiliated (locally funded) charter schools belong to
    their own district's area** (`admin`): their attendance is administrative,
    and point-in-polygon mis-sites boundary-adjacent campuses (La Cañada High
    stands on the Pasadena side of the TIGER line but serves La Cañada — the
    location rule read the district as exporting half its students).
  - **Independent charters** are point-in-polygon assigned to the area their
    building stands in (STRtree; unified wins boundary slivers; misses within
    ~2 km snap to the nearest polygon) — no attendance area, so location is the
    draw evidence. Schools of non-geographic districts (COE, SBE) site the same
    way.
  - Schools without usable coordinates fall back to their district's area via
    the NCES crosswalk; the small remainder is unsited (0.04% of enrollment) and
    joins the import-only pool.
- Virtual schools have no host area: they are **import-only**, drawn from
  everywhere (§7); their observed enrollment is also reported on their
  **authorizer's** page as "virtual programs based here" — visible but excluded
  from the physical accounting.

## 6. Grade bands: how elementary/secondary overlap is kept honest

Where the state is tiled by elementary + secondary districts, each child appears in
two polygons. The model splits by grade **at each secondary district's lowest
grade** (LOGRADE: 9 for 97 areas, 7 for 14, 6 for 1), inherited by the elementary
districts under it:

- an elementary area's seats = TK/K through grade cut−1 (+ ungraded elementary) of
  schools sited there; its residents = ages 5 through cut+4;
- the overlaying secondary area gets grades cut–12 (+ ungraded secondary) and ages
  cut+5 through 17;
- unified areas take whole schools and all ages 5–17.

Ages map to bands by splitting B14003's 10-14 band uniformly: the lower share is
(cut−5)/5 — 0.8 for a 9-12 secondary, 0.4 for 7-12 (`B01001` convention). Fourteen
NCES **pseudo secondary districts** (GEOID 0699xxx) — elementary territory whose
high grades a unified district serves — are real ACS observation units and modeled
as areas like any other.

With cuts consistent across each elementary/secondary pair, every resident child
and every seat is counted exactly once across the node set
{unified ∪ elementary ∪ secondary}, which is what makes closure (§8) meaningful.

## 7. The accounting identity — physical flows net out per county, virtual statewide

Each district area belongs to an administrative county (its CDE district's county;
NCES pseudo districts take the majority county of their sited schools). Per vintage
v, county c, and area d ∈ c, with both allocations proportional to resident
public-school population (the LAUSD Chart-4 assumption):

    V           = (flagged-virtual seats + unsited seats) × (1−m)      [statewide]
    virt_est(d) = V × resident_pub(d) / Σ_state resident_pub
    pool_c      = Σ_{d∈c} resident_pub(d) − Σ_{d∈c} seats_phys(d) × (1−m)
    ooc_adj(d)  = pool_c × resident_pub(d)/Σ_{d∈c} resident_pub − virt_est(d)
    net_import  = seats_phys(d) × (1−m) − (resident_pub(d) − virt_est(d) − ooc_adj(d))
    net_rate    = net_import / resident_pub(d)

Two separately-scoped netting constraints, both by construction:
- **Virtual enrollment nets out at the state level only** (Σ_state virt_est = V):
  virtual students cross county lines, so no county-level constraint is imposed on
  where they live. virt_est is always ≥ 0 and is what the "virtual share" metric
  shows.
- **Physical seats and physical resident-students net out exactly per county**
  (Σ_{d∈c} net_import = 0): ooc_adj — the county's signed administrative
  adjustment, its measured enrollment counted in other counties net of its
  statewide-virtual share — redistributes the county-level imbalance across the
  county's areas, so a district's net is pure within-county physical
  redistribution. Cross-county and virtual administrative flows appear at the
  county level (level 'c' rows: county residence vs administrative CDS-prefix
  seats, the same statewide pool V by population share), where they are measured
  rather than assumed.

Fitting these allocations (instead of assuming population-proportionality) is the
planned v2. In a county with a single district area (San Francisco), the
within-county net is exactly zero; that district's story is its county page.

MOEs: seats are administrative counts (exact); net_import's margin is the resident
base's margin (band splits scale the band margins by the same weights). Small
districts routinely have |net| < MOE — the site grays them out rather than
coloring noise.

## 8. Closure — the model checks itself

Per-county netting makes closure exact by construction: district nets sum to zero
within every county (verified to <1 student in `check_enrollment_closure` — a
violation means a bookkeeping bug, not data drift) and therefore ~zero statewide.
What remains informative is **coverage**: 923/974 areas have ACS residence data at
vintage 2009 (reorganized districts without current polygons), rising to 973+/974
by 2024. A second regression check requires the model to reproduce the shipped
LAUSD article's resident series — it currently matches to the student for every
overlapping vintage.

**Observed-transfer validation (District of Choice).** CDE publishes the one piece
of true district-pair flow data in California: District of Choice program
transfers (CALPADS; `sf acquire --dataset doc`, view `doc_raw`) — ~8k students/yr
across ~50 participating districts, pair-level with demographics, unsuppressed.
DOC is a small subset of inter-district movement (regular Ed Code 46600 permits
are not published), so the check (`check_enrollment_doc_validation`) is
directional, not a reconciliation: (1) 69% of observed DOC transfer students move
between ADJACENT districts (median distance ~12 km) — direct evidence for the
nearby-draw premise; (2) model nets agree in sign with observed DOC nets for
21/24 districts with >20 transfers, and the biggest DOC importers sit properly
above their observed DOC floors (Walnut Valley observed +2.4k vs model +5.3k;
West Covina observed +845 vs model +871). A hard floor test would be invalid — a
DOC importer can simultaneously export more via unpublished permits. For the v2
fit, these pairs are observed arcs that can pin the gravity/distance-decay
parameters instead of assuming them.

Net import is NOT compared against the LAUSD article's Chart-4 cells directly:
the article reports channel-level cells (in-boundary charters, virtual &
out-of-county, physical elsewhere) where this model reports one physical net —
same allocation assumption, different decomposition; the relationship is
documented here rather than asserted numerically.

## 9. Why nets only — no pairwise flows

A distance-preferring allocation of the nets into district-pair "exchange" numbers
was considered and rejected: it adds no information (any pairwise number would be
an artifact of the chosen cost function, not data), transportation solutions are
degenerate (partner lists would churn between vintages on noise), and pairwise
numbers would be the most quotable, least supported artifact on the page.

What district pages DO break down is the export by **channel** — classes of
schools, which are observable where destinations are not: per window, resident
public-school children split into (a) seats at district-run schools located in the
area and (b) seats at charter schools located in the area (both observed,
converted to resident units), (c) virtual & out-of-county (virt_est + ooc_adj,
estimated at the county-average share), and (d) "elsewhere" — the net export
residual, kept as ONE net number (in-person cross-district enrollment plus any
above-average virtual use; see §11). For "which districts, plausibly", each district page shows its
**neighbors' own residuals** (adjacency computed from the polygon partitions), and
the statewide choropleth makes surplus/deficit geography visible. Pairwise flows
belong to a future joint model that estimates them with uncertainty.

## 10. Boundary vintage

All 16 vintages are drawn and sited on ACS-2024 polygons; ACS attributes are keyed
by as-of-vintage geoids. Districts that reorganized 2009–2024 have early-vintage
residence rows with no current polygon (51 areas at vintage 2009 → 0 by 2024);
their seats attribute to successor areas. See
`known_issues/district-boundary-vintage-mismatch.yaml` and
`known_issues/nces-crosswalk-gaps.yaml` (22 polygons without a CDE district, 75
CDE districts without a current polygon, measured every build).

## 11. Limitations and bias register

- **Net, not gross**: offsetting in/out flows are invisible; a zero net is not "no
  movement."
- **Within-county virtual deviation**: the allocation removes each county's
  MEASURED virtual & out-of-county pool, but spreads it by population share — the
  county-average propensity. A district whose residents use virtual/out-of-area
  options more than that average shows the excess as net export; the "elsewhere"
  residual therefore mixes in-person cross-district enrollment with
  above-average virtual use, and no public data separates them. (Between
  counties, virtual is fully accounted: the pool is measured per county.)
- **Virtual lower bound** (§5) → host areas of unflagged non-classroom-based
  charters read as importers; students' home areas as exporters (within-county
  netting bounds the damage to the host county).
- **County factor as district proxy** (§3) → residual pre-2010 bias where control
  error varied within a county.
- **Age-split uniformity** (§6): the 10-14 band is split assuming flat single-year
  ages (≲1-2% of a band).
- **Boundary vintage** (§10).
- **Private-school and not-enrolled cells** are ACS-reported and carry their own
  response error (a parent of a publicly-funded NPS student may answer "private").
- **Window autocorrelation** (§1): adjacent windows share 4/5 of their sample.
- Directory coordinates are current; schools that moved sites are sited at their
  last-known location.

## 12. Reproduction

    uv run sf acquire --dataset census     # ACS + popest (needs CENSUS_API_KEY)
    uv run sf acquire --dataset tiger      # district polygons
    uv run sf acquire && uv run sf ingest  # CDE enrollment + directory + the rest
    uv run sf analyze                      # builds enrollment_* parquets
    uv run sf check                        # closure / siting / LAUSD regression
    uv run sf export                       # writes site/static/data/enrollment/*

Parquet outputs under `data/parquet/analysis/`: `enrollment_residence`,
`enrollment_school_siting`, `enrollment_area_cuts`, `enrollment_adjacency`,
`enrollment_school_seats`, `enrollment_district_flows`,
`enrollment_calibration`, `enrollment_acs1_overlay`.
