# The unaccounted-for public-school children: a three-level reconciliation

*SchoolFactors, August 2026. Data: ACS 5-year B14003 (school-district and county
geographies, vintages 2015–2023) vs CDE census-day enrollment (school-level
historical files with `ENR_TYPE = 'C'` through 2022-23, current-format census
files after). The district/county/state computation ships in
`schoolfactors.analysis.lausd_export._flows`; the per-district and charter-location
tables below are one-off analyses reproducible with the queries described.*

## The question

The LAUSD enrollment page defines a residual: census-counted resident children
5–17 attending public school, minus enrollment at LAUSD-associated schools
(traditional + both charter sectors). It is positive and growing. Candidates were
(a) universe mismatch between the two data sets, (b) inter-district enrollment,
(c) non-LAUSD charters. This note pins each down.

**Convention.** ACS vintage *v* is a 5-year window over calendar years *v−4…v*.
Every comparison uses the mean census-day enrollment over the five school years
overlapping the window (springs *v−3…v+1*). Under end-of-window single-year
conventions the "mismatch" trends with the state's own enrollment decline and the
calibration below would be invalid; under the window-mean convention it is stable.

## 1. State level: the universe mismatch is real, constant, and ~−5.5%

Statewide, inter-district enrollment nets out, so ACS-public minus CDE isolates
the pure universe mismatch: CDE counts TK 4-year-olds and 18+ seniors that the
census 5–17 bins exclude, plus survey error. Summing B14003 over all 58 county
geographies (equivalently: any one school-district summary level — each file
carries a Remainder-of-California row and partitions the state):

| vintage | ACS public 5–17 | CDE 5-yr mean | residual | pct |
|---|---|---|---|---|
| 2015 | 5,928,150 | 6,228,141 | −299,991 | −4.8% |
| 2016 | 5,914,785 | 6,230,213 | −315,428 | −5.1% |
| 2017 | 5,888,245 | 6,229,307 | −341,062 | −5.5% |
| 2018 | 5,858,635 | 6,219,623 | −360,988 | −5.8% |
| 2019 | 5,834,485 | 6,205,108 | −370,623 | −6.0% |
| 2020 | 5,759,096 | 6,160,268 | −401,172 | −6.5% |
| 2021 | 5,798,502 | 6,093,066 | −294,564 | −4.8% |
| 2022 | 5,670,232 | 6,019,441 | −349,209 | −5.8% |
| 2023 | 5,655,435 | 5,949,662 | −294,227 | −4.9% |

Oscillates in −4.8…−6.5% with **no trend** (the 2020–21 wobble is the pandemic
ACS collection problem). Conclusion: the universe-mismatch hypothesis is
**confirmed as a level** (~−5.5% of enrollment) and **denied as an explanation
for growth** — a constant offset cannot produce a rising residual. It becomes the
calibration baseline for the levels below.

## 2. County level: LA County increasingly leaks enrollment out of county

Same subtraction per county (B14003 county geography; CA county FIPS = 2×CDE
county code − 1). Los Angeles County:

| vintage | ACS public | CDE 5-yr mean | residual pct |
|---|---|---|---|
| 2015 | 1,485,734 | 1,551,021 | −4.2% |
| 2018 | 1,426,890 | 1,506,160 | −5.3% |
| 2020 | 1,382,705 | 1,459,004 | −5.2% |
| 2021 | 1,384,741 | 1,424,039 | −2.8% |
| 2023 | 1,328,861 | 1,355,097 | −1.9% |

LA County started at the state baseline and drifted ~3 points toward zero —
≈ +39k children (2015→2023) counted as public-school students but not enrolled
in any LA County school. The counterparties are visible in the cross-county
distribution (vintage 2023): the counties whose enrollment most exceeds their
resident public-school children are Inyo (−38%), Sutter (−28%), Glenn (−24%),
El Dorado (−21%), Placer (−20%), Kern (−10%), San Diego (−9%) — the classic
authorizing counties for statewide non-classroom-based/virtual charters, whose
students are counted where the school is chartered, not where they live.
Statewide enrollment at charter schools the CDE directory currently flags fully
or primarily virtual (`Virtual` ∈ {F, V}): 37k (2015) → 103k (2023) → 135k
(2025-26). The flag is present-day, so early years are approximate.

## 3. District level: LAUSD's residual is real; absorption moved over time

LAUSD (census SD geoid 0622710 = `directory.ncesdist`) vs the rest of LA County
as a block (robust to elementary/secondary district overlap):

| vintage | LAUSD residual pct | Rest-of-county residual pct |
|---|---|---|
| 2015 | −1.1% | −6.4% |
| 2017 | +0.1% | −8.5% |
| 2020 | +1.8% | −10.2% |
| 2023 | +3.4% | −5.6% |

Against the −5.5% baseline, LAUSD's unexplained excess grew from ≈ +28k (2015)
to ≈ +49k (2023). The rest of the county *deepened* to −10.2% by 2020 —
absorbing — then returned to baseline by 2023 as the absorption moved
out of county (§2). Per-district (unified districts, residual pct 2015 → 2023):
the strong net importers adjacent to or near LAUSD include Acton-Agua Dulce
(−66% → −91%; authorizer of large non-classroom-based charters), Duarte
(−3% → −44%), Walnut Valley (−36% → −41%), West Covina (−37% → −45%),
Culver City (−25% → −33%), San Marino (−20% → −36%), El Segundo (≈−29%),
Alhambra (≈−20…−26%), Torrance (−19% → −11%) — patterns consistent with
inter-district permits and district-authorized charters drawing regionally.
Strong net exporters: Inglewood (+29% → +46%), Compton (+38% → +25%),
Azusa (+15% → +32%), Montebello (−7% → +15%).

Non-LAUSD-authorized charter campuses physically inside the LAUSD boundary
(directory coordinates vs the union of MP25 attendance polygons): 42 campuses,
total census-day enrollment ~5.0k (2015) → ~6.6k (2023) — a real but small
channel, nowhere near the ~49k excess.

## Conclusions

1. The state universe is stable and the flow is measurable: the residual method
   is sound once calibrated by the state baseline.
2. County stability does **not** follow from state stability — LA County's
   residual moved 3 points while the state held — and the movement itself is the
   finding: post-2020, LAUSD-resident students are increasingly counted outside
   the county, consistent with the virtual-charter boom.
3. Neighboring school districts (including their authorized charters, which
   behave like districts as LEAs) demonstrably absorbed LAUSD-resident students
   mid-decade; since 2020 the marginal absorber is out-of-county.
4. All flows here are accounting residuals (apparent, net), not student-level
   origin/destination measures; CALPADS inter-district transfer data would be
   required for student-level confirmation.

## Data notes

- The 2014+ historical enrollment files carry both `ENR_TYPE='P'` (primary) and
  `'C'` (combined) rows per school×race×gender; summing without filtering
  double-counts almost exactly 2× (P≈C for most schools). Repo views filter
  `enr_type = 'C'`.
- B14003 school-district files include a Remainder-of-California row (geoid
  0699999); each summary level partitions the state by itself. Never sum two
  summary levels.
- ACS vintages 2020–2021 carry pandemic collection weaknesses; treat those two
  points as noisier.
