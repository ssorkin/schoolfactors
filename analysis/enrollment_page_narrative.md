# LAUSD enrollment page — narrative source

<!--
HOW THIS FILE WORKS
- PUBLISHED 2026-08-21 to /lausd/enrollment. REVISION DRAFT staged
  2026-08-22 at /lausd/enrollment-draft (ACS 1-year data through 2024);
  original archived at /lausd/enrollment-v1. On approval the draft replaces
  the live article. This file remains the prose source of truth. Edit prose freely; Claude compiles it
  into the page and wires numbers to the live export.
- {{slot}}        = a value Claude fills from data and keeps live (legend at bottom).
- [[TABLE: name]] = a rendered data table (specs at bottom; reorder/delete at will).
- <!-- CLAUDE: -->  = instruction to Claude. Claude answers with <!-- DATA: --> notes.
- Mark a paragraph <!-- polish --> if you want Claude to rework the wording;
  otherwise your text is preserved as written.
- Non-negotiables from CLAUDE.md: "correlated with"/"counted in", never causal
  language; residuals are apparent/net accounting, not measured student flows.
-->

## 0. A shrinking district

<!-- Hero chart, per revisions: LAUSD-authorized enrollment is now a stacked
     area subdivided into traditional / affiliated charter / independent
     charter (census-day, from spring 2002 so the 2003-04 peak era is
     visible; class split via directory charter/funding flags, approximate in
     early years). Hover shows the per-class values;
     resident children 5-17 from 2005 — ACS 1-year points (open dots) for
     2005-09, 5-year windows from 2010. No census product covers 2002-04 at
     district geography (first ACS 1-year release is 2005; the 2000 decennial
     school-district tables are not in the API). -->

We started this project to ground discussions about (public) school performance and
enrollment with actual data, with the idea that it might be possible to correlate these
two types of observations. A backdrop of this is the current budget crisis that LAUSD
is experiencing, presumably at least somewhat related to the marked decline in enrollment
at the district, from {{lausd-enr-2015}} in 2015 to {{lausd-enr-latest}} currently.

<!-- DATA: slots wired to census-day enrollment at LAUSD-authorized schools
     (traditional + both charter sectors): 646,683 (spring 2015) → 497,105
     (2025-26). Same series as the hero chart. -->

This decline can only partly be explained by population shifts.
<!-- DATA: your edit read "can only be explained by population shifts" — that
     inverts the paragraph's claim (the data show population explains less than
     half), so I compiled it as "can only partly be explained". Reword freely. --> Census data shows
that resident children inside the LAUSD boundary has fallen only by {{resident-children-decline}} =
{{resident-children-decline-pct}} ({{residents-2015-2023}}, ACS windows ending
2015→2023). On the same measurement windows, enrollment in LAUSD-authorized
schools fell {{enr-decline-windows-abs}} = {{enr-decline-windows}} ({{enrollment-2015-2023}}) — traditional
schools fell {{trad-delta}} ({{trad-2015-2023}}) and affiliated charters fell
{{aff-delta}} ({{aff-2015-2023}}), while independent charters *grew*
{{ind-delta}} ({{ind-2015-2023}}). That is, enrollment in the
district, both for traditional schools and LAUSD affiliated charters, has fallen
much faster than the school-aged population. Held against the resident children
who attend *public* school ({{public-residents-2015-2023}}), the gap this
article chases is already visible: LAUSD-authorized enrollment exceeded resident
public-school children by ~{{residual-2015}} in the 2015 window and trailed it
by ~{{residual-2023}} in the 2023 window.

<!-- DATA: window-mean values behind the new slots — residents 738,913→678,091;
     enrollment 651,496→557,694; traditional 512,499→406,725 (−106k);
     affiliated 57,652→42,048 (−16k); independent 81,345→108,920 (+28k);
     public-school residents 644,075→576,435; residual −7k (2015) → +19k (2023).
     Note the class decomposition: of the −94k enrollment decline, −106k is
     traditional and −16k affiliated, offset by +28k independent-charter
     growth. -->

<!-- DATA: resident children 5-17, ACS windows ending 2015 → 2023: 738,913 →
     678,091 = −8.2%. Enrollment over the same span fell −16.5% (and −23% through
     2025-26, past the census window). -->

The rest of this article will explore as precisely as possible an accounting of the difference
between these two rates.

<!-- DATA: per reviewer feedback (chronology): the class bullets are now
     2015→2023 single-year census-day (apples-to-apples with the ACS bullets),
     and a divider line beneath the list carries the through-today figures
     ("since the windows end … 497,105 in 2025-26, trad 353k / aff 37k / ind
     107k"). Your P1's "to 497,105 currently" stays as scene-setting. -->

<!-- DATA: per revisions — the deltas list now sits BEFORE the concluding
     paragraph, every bullet shows its year span, and the residence bullets are
     restricted to windows 2015-2023 so they match the prose anchor (the data
     reaches back to 2010 if you ever want the longer span). The prose now
     carries the like-for-like pair: residents -8.2% vs enrollment -14.4% on
     the same windows (the single-year series continues to -23% by 2025-26).
     The "not enrolled anywhere" bullet is footnoted: +8k children against a
     94k enrollment decline, with the young-child age detail folded in. -->

<!-- DATA: reviewer round 2, implemented:
     (1) Opener now leads with the divergence hook (-8% children vs -14%
         authorized vs -21% traditional on matched windows), provenance in a
         parenthetical; proposed prose, edit at will.
     (2) The bullets carry an explicit "MATCHED ACS WINDOWS, 2015-2023" label
         and the through-today line is labeled "Current enrollment (2025-26)".
     (3) Act I: "became a growing net exporter" -> "developed a growing
         apparent enrollment deficit ... (a 'net exporter' hereafter)".
     (4) NEW METRIC, reviewer's definition adopted: Expected Student %ile =
         percentile of the demographic prediction (level minus residual, OLS
         - deterministic given composition) among the same pools as the other
         percentiles. Identity: prediction + residual = observed, so the
         three-number vocabulary decomposes: expected-for-these-students ->
         actual -> vs-similar-schools. Shipped site-wide: entity pages show it
         under the percentile chips; index carries stu_pct. (The alternative
         within-school fixed-effects construction - expected outcome for a
         fixed student crediting peer environment; San Marino 94th under it -
         is documented in analysis/similar_student.py, unused.)
     (5) Appendix trio is now: Chart 5 net imports vs Expected Student %ile,
         Chart 6 vs raw %ile, Chart 7 vs Similar Schools %ile - the reviewer's
         three-panel design; the SED panel's data remains exported if you want
         it back. Appendix prose rewritten to the three-number reading
         (Walnut Valley: expected near top / actual near top / vs-similar
         unexceptional), which fixes the misreadable "19th percentile
         district" sentence.
     (6) Reviewer's Act II sentence and sign-convention concerns were against
         the previous deploy: the causal sentence already reads "The children
         need not have moved..." and the mixed-sign county tables were already
         replaced by the single positive-importer convention.
     (7) Conclusion alluvial frame widened per your note. -->

<!-- DATA: per your direction the metric ships as "Expected Student %ile"
     (reviewer's cleaner name), is the FIRST percentile column in the master
     table (home) and the compare table, gets its own out-of-sample chips row
     on every entity page above the Similar chips, and is documented at
     /methodology#expected-student (definition, three-number decomposition,
     what it is NOT, and why the fixed-student variant is unshipped). -->

<!-- DATA: final metric family, per your parent-measure direction + reviewer:
     THREE percentiles now ship, in table order Expected Student | Similar
     Student | Similar Schools.
     - Expected Student %ile = percentile of the demographic prediction (who
       the school serves); has out-of-sample chips.
     - Similar Student %ile = the parent decision question: for a fixed
       student profile, expected performance at this school vs all others
       (within-school race x SED fixed effects; ranking is profile-invariant
       under additivity, so no child inputs needed; ranked at the shrunken
       lower bound like other percentiles). San Marino High 94th / La Canada
       99th / Marshall 82nd. Entity pages carry a parent-phrased line
       ("students like this school's tend to perform better here than at N%
       of California schools"); conditional-association caveat everywhere.
     - Similar Schools %ile = unchanged accountability view.
     Methodology now documents all three at #expected-student and
     #similar-student. -->

<!-- DATA: per your direction, Expected Student %ile is demoted: removed from
     the master and compare tables (order now Similar Student | Similar
     Schools), its chips row removed, and it survives as a small muted
     "composition only" line under the Similar Schools chips plus its
     methodology section (relabeled "supporting"). Similar Student %ile is now
     the headline on entity pages — promoted above the chips, larger type,
     parent phrasing. The enrollment draft's Chart 5 still plots imports vs
     the Expected (composition) percentile deliberately: composition is the
     analytically right axis for what the flows chased. -->

<!-- DATA: Chart 5 now plots net imports vs the SIMILAR STUDENT percentile
     contemporaneous to the era (per your note): district level_eb refit on
     data through 2017 (stored in the history parquet) minus the
     era-restricted student-composition effect (student_effects(max_year=2017)),
     ranked among CA unified districts. Live r = +0.38 (vs +0.49 raw, -0.18
     Similar Schools): the flows tracked where students like the movers' would
     be expected to do well, and raw scores, but not value-add. Era values:
     San Marino 99th, Walnut Valley 90th, AADUSD 40th, Inglewood/Compton
     ~27-28th. The Expected(composition) panel's data stays exported (perf.stu)
     if you ever want it back. -->

<!-- DATA: PUBLISHED. Your conclusion merged with proofreading: numbers
     live-wired (101k decline; +54k/+6k/+11k; Act I physical +17k ~ doubling);
     "other in in-county" fixed; "flight to quality" rendered as "reads as a
     flight toward measured quality" with the metric named (raw + Similar
     Student — note Similar Schools showed no pull, r = -0.18, which the
     appendix carries); "flight of convenience" kept with your "we can only
     presume" hedge. Byline + date added under the first heading. Capacity,
     Closures, and the map crosslink merged back from the old page (now below
     the Conclusion, above the Appendix). LAUSD map choropleth + attendance-
     area school dots now color by Similar Student %ile. -->

<!-- DATA: post-publication fix (your catch): the "Matched ACS windows"
     bullet block mixed conventions — resident bullets were window-based but
     the class bullets were single census-day years (trad 502,564 -> 390,549 =
     -22.3%), disagreeing with the prose's window means (512,499 -> 406,725 =
     -20.6%). Both computations were correct; the block's label was not. The
     class bullets now use 5-yr window means (trad 512k -> 407k, -21%), so the
     whole block shares one convention with the prose; single-year figures
     remain only in the labeled "Current enrollment (2025-26)" line and
     Chart 1. -->

<!-- DATA: REVISION DRAFT (2026-08-22), per your direction, staged at
     /lausd/enrollment-draft with the original copied to /lausd/enrollment-v1
     (noindex, banner). What changed:
     - New data: ACS 1-year B14003 acquired 2005-2024 (no 2020; 65k-population
       floor) at state / county / unified-district geographies; exported as
       narrative.annual ([year, acs public 5-17, straddled CDE mean] per
       level). The state calibration holds annually (3-6.5%, trendless) — noted
       under Chart 2.
     - Chart 3 is now ANNUAL (2010-2024, gap at 2020): county balance within
       ±0.4% of zero 2011-2018, briefly positive 2016-17, then -29k (2019) →
       -47.4k (2024). The window-based county-trends table stays beneath it.
     - Act II staging paragraph extends with 2024 figures: county deficit
       47,422; LAUSD net export 58,378 = 11.2% of adjusted enrollment (record).
     - Conclusion gains a "Through 2024: the shift accelerates" postscript
       (proposed prose — edit at will): record export, traditional -4.7% in
       2025-26, virtual to 135k.
     - Chart 1's resident series extends to 2024 automatically (ACS1 point,
       open dot; residents 5-17 ~650k).
     - Byline reads "revised August 22, 2026"; a Revision note endnote links
       the archive; method caveats add the 1-year notes (65k floor, straddle
       convention, no 2020, pre-2010 noise). -->

## 1. The state is a closed system, and it's stable

The data we use here are from two different sources:
1. The U.S. Census Bureau and their American Community Survey (ACS) product which
tracks with great detail the population, demographics and school-types in a rigorous
manner centered on where people *live*.
2. The California Department of Education (CDE) which tracks with great detail
student enrollment and performance where students are *enrolled*.

Before any other analysis, we had to make sure that these two measures remain
consistent within a closed population universe (for any given year). That is,
we understand that students who live in the LAUSD boundary may attend school
outside that boundary (say with charters, privates, or inter-district attendance).
We did this by observing the data over time from both sources and found that they
remain remarkably consistent: state public school enrollment numbers from CDE
correspond to ACS public school enrollment numbers for the state as a whole over
the time period for this investigation.

[[CHART: state-stability]]

<!-- DATA: revised to a two-line chart at 1-year granularity (all 14 windows,
     2010-2023): CDE statewide enrollment (orange) vs ACS public 5-17 (blue),
     hover for per-window values and residual. The note is kept beneath it:
     CDE runs a steady 4-6% above ACS because it counts TK/4-year-olds and
     18-year-old seniors outside the census 5-17 bins; the slow drift tracks
     the TK phase-in and is absorbed by same-window calibration. -->

These two universes did not drift, so we can safely say that the movement has been
across administrative boundaries within California.

One definition carries the rest of this article. For any geography — a
district's attendance area, a county, the state — compare the two universes
after removing the mechanical offset:

> enrollment attributed to schools in the geography (CDE)
> − the normal statewide Census/CDE mismatch
> − resident public-school children (ACS)
> **= net administrative import**

Positive: the geography's schools are counted with more students than its
resident children can account for (a net importer). Negative: a net exporter.
Every table and chart below uses this one orientation.

<!-- DATA: per reviewer feedback — the equation box renders as a styled panel;
     ONE SIGN CONVENTION everywhere now: positive = importer. Chart 3 plots LA
     County's net import (diving to −41k); the county-trends and killer tables,
     the district table, and the LAUSD ledger all share the orientation; the
     county seat ledger's row is renamed "+ net administrative export (counted
     outside the county)". The old residual-decomposition table is now "The
     LAUSD ledger, every window": residents / adjusted enrollment / net
     administrative import. -->

## 2. Act I: movement within LA County

The decline in LAUSD enrollment started in the early 2000s, after the district
reached a peak enrollment of {{lausd-peak-enr}} students in {{lausd-peak-year}}
(our census-day series; LAUSD's own Fingertip Facts agree —
https://media.edlio.net/827d2fb9/7dad8703/ae7ca91e/de3f23eaed524ec192ff2468f1fa3771?_=Enrollment-1-6-2022.pdf).
This invites the first question of whether the county acted as a closed system.
The answer here is "yes," for the first decade and a half of the decline.

No ACS 5-year data exists before the window ending 2010, so the walk-back to the
peak splits in two. From the peak through 2010, enrollment alone is sufficient to see the dynamics.
LAUSD and the rest of LA County declined nearly in proportion, where LAUSD's share of
county enrollment moved only from {{lausd-county-share-2005}} to
{{lausd-county-share-2011}}. There is little evidence of a large net redistribution
between LAUSD and the rest of LA County during this early period, and LAUSD's
decline tracked the school-age population decline (in fact, LAUSD gained ~4pp
market share of resident children through its peak in 2014-15, see Chart 1).

<!-- DATA: per reviewer feedback, "no net movement occurred" softened to
     "little evidence of a large net redistribution" — offsetting flows could
     exist under a stable share. --> From the
2006–2010 window onward the census side exists, and the residual ledger can be read directly: LA County as a whole
tracked the state baseline to within about a point through the window ending
2019. The county was, to first order, a closed system.

<!-- DATA: county residual minus state baseline, by window end: 2010 +1.5pp,
     2013 +0.9pp, 2016 +0.6pp, 2019 +0.9pp — then 2021 +2.0pp, 2022 +2.5pp,
     2023 +3.0pp. "Within about a point through 2019" is the defensible line;
     the pre-2010 share numbers are 42.8% (2005) → 42.0% (2011) → 41.0% (2023). -->

Within the apparent stability of LA County's numbers, two fundamental, internal
shifts occured. First, under LAUSD's own authorization, seats shifted from traditional and affiliated-charter schools
({{lausd-tradaff-2011}} → {{lausd-tradaff-2020}}, windows ending 2011→2020) to
LAUSD-authorized independent charters ({{lausd-ind-2011}} → {{lausd-ind-2020}}).
This growth reached a peak of 110k independent charter students in 2020, but has been declining since.
And across district lines, the LAUSD boundary became a growing net exporter of
enrollments: resident public-school children counted somewhere other than
LAUSD-authorized schools grew from roughly {{lausd-export-2011}} to
{{lausd-export-2020}}, while the other unified districts of LA County went from
importing roughly {{otheruni-import-2011}} to {{otheruni-import-2020}} more
students than their own resident public-school children. One side's growing
surplus of children was the other side's growing surplus of seats. The two
tables below carry the full ledger.

<!-- DATA: revised per your reconciliation note. The old paragraph's "LAUSD
     excess" was measured against the state baseline while the old table showed
     raw residual pct — hence LAUSD looking flat there. Both are now in the
     same currency (net children, baseline-adjusted): LAUSD boundary exports
     ~29k → ~51k (2011→2020) while other unified districts' net imports grew
     ~2k → ~21k; the elem/HS-district areas and out-of-county leakage carry
     the rest, all visible in the county ledger, which sums exactly. -->

[[TABLE: county-seat-ledger]]

[[TABLE: district-net-imports]]

<!-- DATA: the single pct table is replaced by two tables per revision 5.
     county-seat-ledger: seats by authorizer group (LAUSD trad+affiliated,
     LAUSD independent charters, other unified districts, elem+HS districts,
     county office & other LEAs), then − TK/18+/survey adjustment, + counted
     outside the county, = ACS resident public-school children — every column
     sums exactly. Columns: windows 2011/2016/2020/2023. The out-of-county
     line is the second act in one row: +21k → +8k → +19k → +41k.
     district-net-imports: per-district net imports in children
     (seats·(1−m) − residents), same windows, plus 2023 seats & residents
     columns; LAUSD reference row now reads as a growing exporter (−29k →
     −51k), reconciling with the prose. LAUSD class split uses current
     directory funding flags (approximate early); cross-checks against FRPM
     within ~2% where both exist. -->

### Who absorbed enrollment within LA County?

Conventional importers tended to be relatively affluent, high-raw-scoring
districts such as Walnut Valley, San Marino, Torrance and Culver City — but
import growth was *not* correlated with SchoolFactors'
demographic-adjusted performance measure. Other large importers were charter
authorizers, including virtual-heavy Acton–Agua Dulce and West Covina. The
full performance and demographic detail is in the appendix.

<!-- DATA: per reviewer feedback (and your endorsement), the full performance
     subsection — your three paragraphs, the LEA-type paragraph, and the
     scatter trio — moved verbatim to "## Appendix: who gained, who lost" at
     the bottom of the page, with charts renumbered 4/5/6 (Act II's leakage
     chart is now Chart 3). This compressed paragraph replaces it inline. -->

<!-- DATA: peer-county check (San Diego, Fresno, Sacramento): the LAUSD pattern
     does NOT generalize cleanly, so per your instruction nothing goes on the
     page. San Diego USD sits at its baseline (−5%) with the REST of SD county
     importing heavily (−8→−11%, its small districts authorize statewide
     charters); Sacramento City USD is itself a net importer (−8/−9%); Fresno
     USD drifted exporter-ward (+2%→−4%). The big-district-exports /
     small-district-imports shape is LA's own story. -->

## 3. Act II: enrollment leaves the county — on paper

The neighboring districts stop explaining the gap. By 2023, the rest of LA
County has returned roughly to California's normal Census/CDE relationship —
but LAUSD has not. On net, the missing administrative enrollment has to appear
beyond those neighboring districts.

And LA County itself stops balancing. After the state-calibrated adjustment,
LA County has roughly {{county-leakage-latest}} more resident public-school
children than enrollment attributed to schools in the county — a net
administrative import of −3.0% of county enrollment, past any earlier point in
the data. The children need not have moved. Increasingly, the administrative
geography of their enrollment appears to have.

[[CHART: county-import (Chart 3)]]

[[TABLE: county-trends]]

Where does California show the opposite pattern? Statewide enrollment at
charter schools flagged fully or primarily virtual grew {{virtual-first}} →
{{virtual-latest}}, and the counties with extraordinary administrative imports
are disproportionately those where enrollment can be geographically decoupled
from physical attendance:

[[TABLE: virtual-bridge]]

<!-- DATA: per reviewer feedback — Act II is now staged as the detective
     sequence (neighbors stop explaining → county stops balancing → where's
     the opposite pattern), the causal-sounding sentence is replaced by the
     administrative-geography formulation, and the importer-counties table is
     replaced by the virtual-bridge table: county / net administrative import
     (children, % of enrollment) / flagged-virtual charter enrollment /
     virtual share. Quantified bridge across all 58 counties: corr(import
     rate, flagged-virtual share) = +0.62 enrollment-weighted, +0.20
     unweighted. Honest caveat rendered in the caption: the F/V directory flag
     is a LOWER BOUND on nonclassroom-based enrollment — Inyo's +33% import
     runs through YouthBuild Charter School of California and Placer's through
     Horizon Charter and the John Adams Academies, independent-study networks
     the flag does not mark. "Apparent, net accounting — not measured student
     flows" now repeats as an italic refrain under Chart 3 and the bridge
     table. -->

<!-- DATA: ACT II MATERIAL (your item 7). Chart 5 plots the single best
     series: LA County resident public-school children counted outside the
     county, every window 2010-2023 (net of the state-calibrated adjustment):
     24.7k (2010) -> 16.7k (2012) -> 9.6k (2014) -> 8.0k (2016) -> 8.1k (2018)
     -> 13.4k (2019) -> 18.7k (2020) -> 29.5k (2021) -> 35.2k (2022) -> 40.8k
     (2023). The arc IS the thesis: the county closes through the mid-2010s
     (leakage ~0.5% of enrollment), then reopens after 2019 to 3.0% — well past
     where the decade began. As shares of county enrollment: 1.5% (2010), 0.5%
     (2016), 1.3% (2020), 3.0% (2023).
     The counterparty table (same accounting per county, children absorbed from
     outside their borders, window avgs 2011/2016/2020/2023):
       El Dorado  -597 -> -236 -> +1,280 -> +4,844   (Charter University Prep
                  et al. — swings from balanced to major absorber, exactly on
                  the 2019+ timeline)
       Kern       +2,379 -> +413 -> +6,497 -> +10,169 (statewide virtual/NCB
                  authorizers; same timing)
       Sutter     +2,189 -> +3,592 -> +4,971 -> +5,559 (steady climb)
       Placer     +9,464 -> +9,263 -> +9,708 -> +11,003 (long-standing
                  absorber — Visions in Education etc. — predates Act II)
       Inyo       +703 -> +2,004 -> +1,424 -> +1,330
       San Diego  +14,850 -> +15,434 -> +15,067 -> +21,428 (mixed: virtual
                  authorizers in its small districts + conventional flows)
     Supporting stats already on page: statewide virtual charters 37k (2015) ->
     103k (2023) -> 135k (2025-26); LA county residual -1.9% vs state -4.9%
     (window 2023); virtual-heavy umbrellas INSIDE the county (AADUSD, West
     Covina/CAVA-LA) show the same mechanism ran within-county first.
     Caveats for your prose: windows 2020-21 lean on pandemic ACS; rows are
     net counterparties in aggregate, not measured LA-to-X student flows;
     phrasing should stay "counted in", never "chose". -->

<!-- DATA: slots filled: county residual −1.9% (window ending 2023) vs state
     −4.9%; leakage ≈ 41k children; virtual charters 37k (2015) → 135k
     (2025-26). Section 3 prose is still my stub — rewrite at will. -->

Meanwhile the channels one might guess first turn out to be small: non-LAUSD
charter campuses physically inside the LAUSD boundary hold only
{{inside-charter-enr}} students.

<!-- DATA: ~6,500 (2025-26), from 42 campuses located by directory coordinates
     inside the MP25 polygon union. -->

## Conclusion: the same children, counted somewhere else

The whole story can be seen clearly in Chart 4. We see over time the population
decline shrink the pie as a whole by 100k students, but also the market share go from LAUSD
affiliated schools (traditional and charter) to independent charters: 1. those
authorized by LAUSD (an increase of 54k students), 2. other classroom based schools,
both charter and USD (an increase of 6k students), and 3. virtual charters (an increase of 11k students).
Essentially all of the increase in LAUSD-authorized, independent charters occurred in the
first two time periods of investigation. The shift of LAUSD students to other in in-county
physical schools (17k students, a 100% increase) was a hallmark of the second time period (Act I).
This move is fairly clearly a flight to quality, with low performing districts (based on
both raw test scores and per-student, demographic adjusted scores) losing students to
higher performing ones. It wasn't until the most recent time period that virtual enrollment increased,
while the other enrollment types stayed flat or decreased (Act II). We can only presume that
this is a flight of convenience, as the virtual schools are largely not high performing.

[[CHART: conclusion-alluvial (Chart 4)]]

<!-- DATA: the "LAUSD ledger, every window" table is absorbed into this
     conclusion: the chart is a 4-column bottom-anchored alluvial (windows
     2007-11 / 2011-15 / 2015-19 / 2019-23), cells = trad / affiliated /
     independent / non-LAUSD physical / non-LAUSD virtual / private / not
     enrolled, with same-category ribbons between columns and gray
     population-decline wedges leaving the top. A matching 7-row table renders
     beneath as the accessible twin, and the assumptions are footnoted on-page:
     (1) LAUSD seats -> residents via the statewide adjustment, treated as
     boundary residents on net; (2) virtual band = boundary population share x
     (LA County flagged-virtual enrollment + county net administrative
     export), physical = remainder (permits + B&M charters); flagged-virtual
     is a lower bound so the virtual band is conservative; (3) population
     decline drawn off the top (growth would enter as an inflow).
     Values (window means): elsewhere splits phys/virt = 15.9k/13.0k (2011),
     15.9k/8.1k (2015), 33.1k/12.5k (2019), 22.0k/24.3k (2023). Conclusion
     prose above is a proposed stub — the phase-transition story — edit at
     will. Appendix charts renumbered 5/6/7. -->

<!-- DATA: site-wide additions from your notes: (a) every district mention on
     this page (prose + tables) now links to its /district page; (b) schools
     flagged F/V in the CDE directory get a violet "virtual" badge wherever
     names appear (main tables included) via the shared Badges component; (c)
     district pages open with a "virtual charter authorizer" notice when the
     district authorizes flagged-virtual charters (count, enrollment, share,
     latest year) and carry a left table-of-contents on wide screens. -->

<!-- DATA: caveats block drafted into the page (one paragraph): apparent/net
     accounting; windows ending 2020-21 lean on pandemic-weakened ACS
     collection; the virtual flag is present-day (early years approximate);
     CALPADS inter-district transfer data would be the student-level check. -->

<!-- Existing sections (Capacity, Closures, map crosslink) stay below unchanged. -->

## Appendix: who gained, who lost — and how they score

The obvious question to ask here is how parents choose the schools to send their
children, since there was a clear flight from attendance area schools.
For traditional school destinations, the answer is a clear yes, with high scoring
districts like Walnut Valley and San Marino becoming net importers of students.

<!-- DATA: specifics added (live-wired): Walnut Valley — 96th pctile raw
     2016-19 — net +5,161 by the 2020 window (~37% of enrollment); San Marino
     — 100th pctile — net +808 (~27%); Torrance/Culver City/Alhambra named at
     85th+. Also compiled your parenthetical claims after verification: the
     market-share peak is 87.5% in spring 2015 (school year 2014-15 ✓, +3.6pp
     from 2005 ~ your "~4pp"); independents peaked at 110,143 in spring 2021,
     rendered as "~110k in 2020-21". Typo fixes: occured -> occurred,
     paridoxically -> paradoxically. -->

However, readers who have explored our methodology will note that raw test scores
say a lot more about the demographic blend at a school and district. Normalizing
scores paints a different picture. San Marino is only a 61st percentile district
after normalizing for the demographics of their student population and Walnut Valley
is a 19th percentile district.

<!-- DATA: merited — per your follow-ups, all three scatters now sit side by
     side in one row after your third paragraph, ordered Chart 3 (SED), Chart 4
     (raw), Chart 5 (adjusted); leakage = Chart 6. Hovering a district
     highlights it in all three panels with a shared caption. "the two charts
     below" rendered as "the charts below":
     net imports vs FRPM-eligible share (2018-19), same marks/axes as Charts
     3-4; r = -0.42 live. Commentary line added beneath: importing districts
     are almost uniformly the lower-SED ones. Note your prose says Walnut
     Valley "19th" adjusted — the live wiring renders the as-of-2017 value,
     currently 18th; San Marino renders 61st as you wrote. -->

Net exporters tended to be uniformly low performing by raw numbers, though paridoxically
quite high performing given their demographic blend. This can be seen in the two charts below.
The exporting districts were, at the time, almost uniformly high on the adjusted measure (Inglewood,
Compton, Bassett, Bellflower, Monrovia all above the 89th percentile), while
the importers varied from low to high adjusted scores, fairly uniformly.
And the timing adds a caution against reading preference
into either panel: the *growth* of imports between 2016 and 2020 is
uncorrelated with performance on either measure (r ≈ 0). The flows are
correlated with district composition, not with measured value-add — and the
largest importer of all, Acton–Agua Dulce, ranks near the bottom of the
adjusted distribution as its virtual-charter enrollment dominates its tested
population.

The importers are also not one kind of LEA. Most import into their own
district-run schools — the permit pattern (Walnut Valley, ABC, Torrance,
Culver City, Alhambra). A second kind is a *charter umbrella*: the seats sit
in brick-and-mortar charters the district authorizes rather than in its own
schools (Duarte's California School of the Arts, Wiseburn's Da Vinci schools).
A third is virtual-heavy: Acton–Agua Dulce's imports run through the
iLEAD/Compass network — roughly half of its charter seats are fully-virtual
schools — and West Covina's largest import is California Virtual Academy @
Los Angeles outright. The second act was already running inside the county
during the first.

<!-- DATA: LEA-type differentiation per your note, one correction to it:
     Acton-Agua Dulce is not purely bricks-and-mortar — its window-2023 mix is
     984 district-run / 5,112 B&M charter / 6,047 virtual (iLEAD Hybrid 3.9k,
     Compass 1.2k, Mission Academy, CalPac, iLEAD Online, Method, SIATech).
     The clean B&M umbrellas are Duarte (CSArts-SGV; 3.2k own / 2.7k B&M / 0
     virtual) and Wiseburn (Da Vinci; 2.5k own / 2.3k B&M / 0). West Covina is
     the hidden virtual umbrella: 8.1k own / 1.3k B&M / 5.2k virtual — CAVA-LA
     alone was 5.4k in 2022-23, i.e. nearly all of West Covina's net imports.
     Classification thresholds (windows-2023 5-yr means, current-day directory
     virtual flags): virtual-heavy if virtual >= 25% of associated enrollment;
     charter umbrella if charters >= 30%; else district-run. Rendered as a Type
     column on the district table (hover for the exact mix) and as marker
     shape+color on the scatters (circle/square/triangle; palette validated
     all-pairs). Rowland (10% virtual) and Baldwin Park (4%) stay district-run
     under these thresholds. -->

[[CHART: perf-scatters]]

<!-- DATA: subsection compiled as a stub for your pass; correlations render
     live on the plotted set (y = net imports % at the 2020 window):
     currently raw r = +0.49, adjusted r = -0.18. Pairing the adjusted
     percentile with the 2016-window imports instead gives -0.30, and the
     recency-weighted adjusted snapshot gives -0.44 — negative under every
     pairing. The two source analyses are summarized in the notes below. -->

<!-- DATA: your Q "why does chart 1's independent count disagree with the
     table for 2020" — three sources were in play; now two, both from one
     series. Chart 1 hovers are SINGLE spring years (2020: 108,919); the ledger
     columns are 5-YEAR WINDOW MEANS matching each ACS window (window 2020 =
     springs 2017-21 avg = 105,664 — a growth era, so the mean trails the
     endpoint). The deltas bullets previously used a third source (FRPM K-12:
     113,703 at 2020 — its own per-year charter flags and K-12-only universe);
     they now compute from the same census-day/directory series as chart 1
     (2015 -> 2026 single years). Table headers now read "2016-20 avg" style so
     the convention is visible at the point of reading. -->

<!-- DATA: performance vs flows (your question, computed 2026-08): district
     percentile = mean scale score (All Students, grades 3-8 & 11, ELA+Math)
     ranked among all CA unified districts per year x grade x test, weighted by
     students with scores. Era 2016-19 (no statewide test before 2015 in repo;
     STAR/API era not ingested).
     - LEVELS line up strongly: net importers are high-percentile — Walnut
       Valley 95, San Marino 99, La Canada 99, South Pasadena 98, Palos Verdes
       95, Manhattan Beach 96, El Segundo 91, Torrance 87, Culver City 85 —
       while the big exporters are low-percentile: Inglewood 13, Montebello 21,
       Compton 24, Pomona 31, Azusa 31, Paramount 38, Lynwood 24. LAUSD sits at
       40 (2016-19). corr(net import % of enrollment, percentile) = +0.49
       across the 47 non-LAUSD unified districts.
     - The GLARING exception is the largest importer: Acton-Agua Dulce (+10.7k
       by 2020) is only 57th percentile in 2016-19 and falls to 31st in
       2022-25 as its virtual-charter enrollment becomes its tested population.
       The biggest single import channel is not a high-performance channel.
     - TIMING does not line up: corr(change in net imports 2016->2020,
       percentile) = -0.02. The import levels are long-standing (permits etc.);
       the era's growth at the margin was not performance-sorted.
     - DEMOGRAPHIC confound is near-total: corr(percentile, FRPM share) =
       -0.90, and corr(net import %, FRPM) = -0.42. "Importers are
       high-performing" and "importers are low-poverty" are the same sentence
       at this resolution — per site convention, phrase as correlated, and
       don't imply performance-chasing.
     - Footnote-worthy: Compton's percentile jumps 24 -> 54 (2022-25) as its
       exports shrink; composition effects and its publicized gains both
       plausible, untested. -->

<!-- DATA: SAME QUESTION on our demographic-adjusted percentiles (per-school
     level_adj_eb from index.json, score-weighted to districts, ranked among CA
     unified districts; recency-weighted toward ~2022-25, not era-specific;
     court/juvenile/alternative schools excluded). THE RELATIONSHIP FLIPS:
     corr(net import %, adjusted percentile) = -0.44 (vs +0.35 raw on the same
     aggregation). The marquee importers rank at or below the middle once
     demographics are netted out — Walnut Valley 15th, San Marino 49th, Temple
     City 7th, Las Virgenes 23rd, Palos Verdes 45th, Arcadia ~0th, Manhattan
     Beach 77th — while the big exporters rank high: Compton 98th, Bassett
     92nd, Inglewood 89th, Paramount 82nd, Azusa 78th, and LAUSD itself 87th.
     Acton-Agua Dulce, the largest importer, is 1st percentile adjusted.
     Reading (keep correlational): the within-county flows moved enrollment
     toward districts with higher raw scores and lower-poverty peers, but LOWER
     measured performance relative to schools serving similar students; the
     virtual-charter channel scores worst of all on that metric. Caveats: the
     adjusted level is one recency-weighted snapshot (can't be dated to the
     2016-19 era); permit-student selection cuts against importers here
     (positively-selected entrants would inflate, not deflate, their adjusted
     level); adjustment is strong (adj vs raw percentile corr = -0.19), so
     treat as "no evidence of value-add", not "harm".
     ADDENDUM — earliest refits: the repo's out-of-sample history
     (district_effects_history.parquet, full pipeline refit on data through
     each cutoff; earliest cutoff 2017 = CAASPP 2015-17, contemporaneous with
     the absorption era) gives the same answer: corr(net import % @2016,
     adjusted %ile as-of-2017) = -0.30; corr(import growth 2016->2020, adj
     %ile 2017) = -0.02; the measure is stable (corr of 2017 vs 2025
     percentiles = 0.82). Era-specific: exporters were ALREADY high-adjusted
     in 2017 (Inglewood 99, Compton 97, Bassett 97, Bellflower 95, Monrovia
     94, Paramount 89; LAUSD 67); importers split — several low (Walnut Valley
     18, Las Virgenes 8, Palos Verdes 9, Temple City 20, San Gabriel 20,
     Arcadia 16, Beverly Hills 25) but some high (Duarte 95, ABC 92, West
     Covina 90, Culver City 90, Santa Monica-Malibu 89, Downey 88). The
     exporters' uniformly high adjusted standing is what drives the negative
     correlation. Acton-Agua Dulce: 47th as-of-2017, 8th by 2025 — its
     adjusted standing collapsed as virtual enrollment became its tested
     population. -->


---

## Slot legend (Claude maintains — all wired live to /data/lausd/enrollment.json)

| slot | current value | source |
|---|---|---|
| lausd-enr-2015 / -latest | 646,683 / 497,105 | narrative.county_share_hist |
| resident-children-decline-pct | −8.2% (windows 2015→2023) | flows.levels.district |
| resident-children-decline | 60,822 children (windows 2015→2023) | flows.levels.district |
| enr-decline-windows | −14.4% (windows 2015→2023) | flows.levels.district |
| enr-decline-windows-abs | 93,802 students (windows 2015→2023) | flows.levels.district |
| residents-2015-2023 | 738,913 → 678,091 | flows.levels.district |
| enrollment-2015-2023 | 651,496 → 557,694 | flows.levels.district |
| trad/aff/ind-2015-2023 | 512k→407k / 58k→42k / 81k→109k | narrative.lausd_classes |
| trad/aff/ind-delta | −105,774 = −20.6% / −15,604 = −27.1% / +27,575 = +33.9% | narrative.lausd_classes |
| public-residents-2015-2023 | 644,075 → 576,435 | flows.levels.district |
| residual-2015 / -2023 | ~7k over / ~19k under | flows.levels.district |
| lausd-peak-enr / -year | 747,009 / 2003-04 | narrative.peak |
| lausd-county-share-2005 / -2011 | 42.8% / 42.0% | narrative.county_share_hist |
| lausd-tradaff-2011 / -2020 | 625k / 501k | narrative.ledger |
| lausd-ind-2011 / -2020 | 52k / 106k | narrative.ledger |
| lausd-export-2011 / -2020 | ~29k / ~51k | flows district vs state baseline |
| otheruni-import-2011 / -2020 | ~2k / ~21k | narrative.district_flows |
| la-county-residual-latest | −1.9% | flows.levels.county |
| county-leakage-latest | ~41k | flows county excess vs baseline |
| virtual-first / -latest | 37k (2015) / 135k (2025-26) | flows.virtual |
| inside-charter-enr | ~6,500 (2025-26) | narrative.inside_charters |

## Chart & table specs (Claude maintains)

- **Chart 2 — state-stability** — two lines, all 14 windows 2010-2023: CDE
  statewide enrollment (orange) vs ACS public 5-17 (blue); LEFT AXIS FROM
  ZERO per revision; dotted right-axis series redefined and renamed per
  revision: "public school enrollment as a fraction of 5-17-year-old
  population" (CDE / ACS total 5-17; ~93.5% -> ~91.3%, mildly declining as
  private + not-enrolled shares rose); hover shows values, residual, and the
  fraction. (RENDERED)
- **county-seat-ledger** — seats by authorizer group, − universe adjustment,
  + counted outside county, = ACS residents; columns 2011/2016/2020/2023; sums
  exactly. (RENDERED from narrative.ledger + flows)
- **district-net-imports** — net imports in children per unified district,
  same windows + 2023 seats/residents + LEA-type column (district-run /
  charter B&M / virtual, hover for exact mix); LAUSD reference row; sorted
  by the 2020 window; "all other unified (net)" catch-all row. (RENDERED
  from narrative.district_flows detail + mix)
- **importer-counties** — most-negative-residual counties, window ending 2023;
  LA for contrast. (RENDERED from narrative.county_flows)
- **lausd-residual-decomposition** — per window: residual, expected-from-state-
  baseline, unexplained excess. (RENDERED, spans 2010-2023)
- **Chart 1 — hero** — titled "LAUSD attendance area" per revision; stacked
  LAUSD-authorized enrollment by class, 2002+, vs residents 5-17 (blue) AND
  the new "of whom in public school (any LEA)" series (teal, per revision;
  ACS1 2005-09 as open dots); zero-based axes; dotted right-axis share of
  resident children in LAUSD-authorized schools. (RENDERED)
- **Charts 6-7 — perf-scatters (pair)** — net imports (% of enrollment, window 2020) vs
  raw score percentile 2016-19 (left) and vs demographic-adjusted percentile
  as-of-2017 (right); LAUSD as reference diamond, outliers labeled, dashed
  OLS fits, live correlations. (RENDERED from narrative.district_flows.perf)
- Sankeys: replaced by the tables/charts above on the draft; not carried over.
