# Data Quality Report

Generated 2026-08-23 by `sf check`. This report is a first-class artifact of the pipeline: problems in the source data are surfaced here and in `known_issues/`, never silently patched.

## Known issues (documented registry)

### Pre-2010 ACS 1-year estimates overstate LA County children (Census-2000-based controls)

*measurement-bias, affects census 2005, 2006, 2007, 2008, 2009* — id `acs-pre2010-population-controls-la-county`

ACS 1-year estimates for survey years 2005-2009 were weighted to Census-2000-based intercensal population estimates that overstated Los Angeles County. In B14003 (children 5-17 enrolled in public school), LA County's share of the state runs 0.55-1.35 percentage points above the county's share of CDE census-day enrollment in 2005-2009; the gap shrinks monotonically toward the 2010 benchmark and sits within +/-0.1pp for every year 2011-2018 once 2010-census population controls take over. The statewide Census/CDE calibration used in the enrollment analyses cannot absorb a county-specific weighting bias, so pre-2010 county- and district-level residuals (apparent "net administrative export") are inflated by roughly 3-5% of the county's child count - up to ~80k phantom children at the 2006 peak.

**Handling:** Corrected by an explicit, named transform (lausd_export._acs1_control_factors): ACS 1-year levels for survey years 2005-2009 are rescaled by the ratio of the Census Bureau's 2010-census-consistent intercensal county estimate of children 5-17 to the same-year vintage postcensal estimate the ACS actually weighted to - LA County's factor applied to county and LAUSD-boundary levels, California's to state levels. Factors run 0.949 (2005) to 1.003 (2009) for LA County. Inputs are acquired with manifests (data/raw/census/popest_*.csv - the 2000-2010 intercensal county age/sex file and the vintage-2005..2009 CA county age/sex files; vintage year codes map July 1 of year y to code y-1997) and ingested to the popest_raw view. Ages 15-17 in the intercensal file's 5-year bins are approximated as 3/5 of the 15-19 group (<=0.3% effect on the ratio). The correction and its size are disclosed in the article's method notes; 2010+ levels are untouched (2010-census controls onward).

### ACS 5-year windows ending 2009-2013 mix Census-2000 and Census-2010 population controls

*measurement-bias, affects census 2009, 2010, 2011, 2012, 2013* — id `acs5-mixed-population-controls`

Each single survey year inside an ACS 5-year window was weighted to that year's own population controls: years 2005-2009 to Census-2000-based postcensal estimates (which overstated some counties, notably Los Angeles - see acs-pre2010-population-controls-la-county), years 2010+ to Census-2010-based controls. A 5-year window ending 2009-2013 therefore blends the two control regimes: vintage 2009 (window 2005-09) is fully affected, vintage 2013 (window 2009-13) only 1/5. Left uncorrected, early-window resident-children levels are inflated in the affected counties and the statewide enrollment-flow model would read the bias as apparent net export.

**Handling:** Explicit, named transform (enrollment_flows.apply_control_correction with enrollment_flows._window_factor): each acs5 observation is multiplied by the mean of its window's per-year factors, where a year's factor is the county's intercensal/postcensal children-5-17 ratio for years <= 2009 (from enrollment_flows.control_factors, the all-county generalization of lausd_export._acs1_control_factors) and exactly 1.0 for years >= 2010. County factors are applied to district areas through each district's administrative county - a per-district proxy, documented as a bias term in analysis/enrollment_flow_model.md. MOEs are scaled by the same factor. The applied factor is carried per row (residence and flows parquets, `factor`/`cf` in the site export) so corrected points are labelable on-page.

### ACS 5-year windows containing the 2020 collection year can overstate resident-children declines in small districts

*measurement-bias, affects census 2020, 2021, 2022, 2023, 2024* — id `acs5-pandemic-collection-resident-bias`

The 2020 ACS collection year suffered severe pandemic nonresponse (the Census Bureau withheld the 2020 1-year products entirely and applied experimental weighting to the 5-year files), and the 5-year series switched from Census-2010- to Census-2020-based population controls mid-decade. Every 5-year window that includes 2020 (vintages 2020-2024) carries some of this. In small districts the effect can materially overstate the decline in resident public-school children (B14003-derived); the enrollment-flow model then reads the too-fast resident decline as apparent net IMPORT, since local seats (CDE-observed, accurate) fall more slowly than the mismeasured resident base.

**Handling:** Documented, not patched: no statewide per-district ground truth exists to correct the pandemic windows (district facilities reports like SVUSD's cover only scattered districts). The published MOEs already reflect much of the uncertainty and are shown on district pages and in hover captions; the statewide map's MOE gate (net-rate margin over +-15pp uncolored) suppresses the least reliable districts. Pandemic-window (2020-2023) net flips of order one MOE in small districts should be read as noise unless corroborated; the flow model's district series carries res_moe per row so affected points are identifiable. Site methodology section 9 ("what this cannot say") covers the general ACS-uncertainty caveat.

### 2015 "number enrolled" counts all-subject eligibility, later years count per-subject

*definition-change, affects caaspp 2015* — id `caaspp-2015-enrollment-definition`

In the 2014-15 research file, the enrollment field counts all students who were eligible to take CAASPP in ANY subject. From 2015-16 onward it counts students eligible for the specific test (subject) in the row. CDE confirmed the 2015 file was never revised to the new definition ("we usually don't have funds available to ask our contractor to revise previous year data files").

**Handling:** Never compare students_enrolled across the 2015/2016 boundary. Participation-rate computations for 2015 use tested/enrolled with this caveat attached. Analyses use students_tested and mean_scale_score, which are unaffected.

### 2015 subgroup enrollment is identical across ALL subgroups (statewide)

*internal-inconsistency, affects caaspp 2015* — id `caaspp-2015-fluency-subgroup-sums`

Originally observed in district 70953 (Sonoma Valley Unified), where fluency subgroups 6/7/8 report identical enrollment in sb_ca2015_all_csv_v3.txt. Our checks show this is statewide and affects every subgroup, not just fluency: in 2015 every subgroup row carries the entity-level "eligible in any subject" count (e.g. LAUSD reports 285,954 enrolled for All Students, Male, Econ-Dis, and every fluency group alike). This is the row-level manifestation of caaspp-2015-enrollment-definition. Tested counts are NOT affected: even in 2015 they satisfy the true identity 6 = 7 + 8 + 180 (see caaspp-group6-definition).

**Handling:** Never use 2015 subgroup-level students_enrolled. Subgroup denominators for 2015 must come from students_tested / students_with_scores, or the series starts at 2016.

### Male + Female no longer partitions All Students from 2021

*definition-note, affects caaspp 2021, 2022, 2023, 2024, 2025* — id `caaspp-gender-nonbinary-2021`

From 2020-21 onward a handful of districts each year report male + female enrollment slightly below All Students. CALPADS added nonbinary gender markers, and CAASPP publishes only Male (3) and Female (4) groups, so students with other markers appear in neither. Violations are small (2-5 districts/year above the 2% tolerance) but the partition identity is no longer exact.

**Handling:** Treat gender groups as overlapping-incomplete, not a partition; never derive a "nonbinary" count by subtraction (n<11 suppression would make it unreliable anyway).

### Student group 6 includes English Only students (6 = 7 + 8 + 180)

*definition-note, affects caaspp 2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025* — id `caaspp-group6-definition`

Group 6 ("Fluent English proficient and English only") is the sum of groups 7 (IFEP) + 8 (RFEP) + 180 (English Only), not 7 + 8 as one might assume from the name "fluent". Verified empirically: the identity 6 = 7 + 8 + 180 holds exactly for enrollment in 2016+ and for tested counts in all years including 2015. Older CDE layout documents describe group 6 inconsistently ("IFEP and EO" in some years), so treat the empirical identity as authoritative.

**Handling:** Analyses that need "fluent but not English-only" must use groups 7 + 8 directly, never group 6 minus anything.

### Directory virtual flag is present-day and undercounts non-classroom-based enrollment

*coverage-limitation, affects directory 2005, 2026* — id `cde-virtual-flag-lower-bound`

The statewide enrollment-flow model classifies a school as virtual when the CDE directory currently flags it fully or primarily virtual (virtual in F/V). Two limitations follow. (1) The flag is a present-day attribute applied to the whole 1981-2026 enrollment history: schools that changed model, or closed before the flag existed, are classified by their last-known state. (2) Non-classroom-based charters that CDE does not flag virtual (independent-study, hybrid, resource-center models) are treated as physical schools at their directory coordinates even though their students need not live nearby. Both push in the same direction: the statewide virtual pool is a LOWER BOUND, and the flow model attributes some genuinely-remote enrollment to the school's host area, biasing that area toward apparent net import (and the students' home areas toward apparent export).

**Handling:** Documented in analysis/enrollment_flow_model.md and on the site methodology page; remote-pool quantities are labeled estimates and the flag's lower-bound nature is stated wherever the remote share is shown. The flag is complemented by an arithmetic criterion (enrollment_flows NC_RATIO): charters whose geographic authorizer's administered charter enrollment exceeds 1.5x the authorizer's own resident children are classified non-classroom statewide-draw and pooled with flagged-virtual seats (allocated over the authorizer county + adjacent counties, the Ed Code enrollment footprint; audited per vintage in the DQ report). The criterion is itself a lower bound: non-classroom programs under large authorizers pass the ratio test and remain in measured cross-county flows. No name-matching heuristics are applied - that would silently patch data. A future improvement is CDE's non-classroom-based funding determination list, which is not currently acquired.

### Current (ACS-2024) district polygons applied to all vintages 2009-2024

*coverage-limitation, affects tiger 2009, 2024* — id `district-boundary-vintage-mismatch`

The statewide enrollment-flow model sites schools and draws maps with one set of district polygons - TIGERweb's ACS-2024 school-district layers - while ACS residence attributes are keyed by as-of-vintage geoids. Districts that reorganized during 2009-2024 (unifications, consolidations, boundary transfers) therefore have residence rows in early vintages with no matching current polygon, and their territory's seats are attributed to the successor district's area for every vintage. Early-vintage series for affected areas mix predecessor and successor geography; the model's per-vintage closure absorbs the mismatch as a small residual rather than hiding it.

**Handling:** v1 accepts the mismatch: series rows exist only where the as-of-vintage geoid matches a current polygon; uncovered areas show no estimate (never zero) and their seats are absorbed by their county's pool. Coverage is reported per vintage in the DQ report. Documented in analysis/enrollment_flow_model.md ("boundary vintage" section) and on the site methodology page. A future version could carry per-vintage TIGER boundaries and a predecessor/successor crosswalk.

### One MP25 attendance-area key (E 11017) resolves to no school

*coverage_gap, affects lausd_gis 2025* — id `lausd-mp25-key-11017-unresolved`

LAUSD's MP25 layer partitions the district into 985 polygons keyed by the
elementary/middle/high school serving each (E_KEY/M_KEY/H_KEY). The Codes lookup
tables (Att{e,m,h}1112_Codes, dated 2016-17) resolve most keys; keys created since
resolve through the Attendance Boundary Info table (POLYID prefix match). Elementary
key 11017 — one polygon, P_KEY 110172048830201 — appears in neither source. The
11001-11016 series are all newer zones known only to the info table, so 11017 is
most likely a zone created after that table's last refresh.

**Handling:** The polygon keeps null e_cds/e_name in the polygon table and site exports (rendered
as "no data"); its middle/high keys resolve normally. Re-check after the next
acquisition snapshot — `check_lausd_resolution` will flag any change in the
unresolved set.

### Exam-admission magnets inside comprehensive schools cannot be separated

*structural-limitation, affects caaspp 2015, 2016, 2017, 2018, 2019, 2022, 2023, 2024, 2025* — id `magnet-within-school-selection`

CDE reports a comprehensive school and its co-located magnet program(s) as a single CDS, so school-level results blend a neighborhood population with a selectively admitted one. North Hollywood Senior High (19647331936350) is the canonical case: its Highly Gifted Magnet admits by gifted identification citywide, inflating both the school's raw level and every student group's rates (the magnet's students appear inside each group row), while the demographic adjustment cannot observe the academic selection. The school types as "magnet", but flagging it "selective" would misclassify its majority neighborhood enrollment. This is a boundary of school-level data, not a correctable error.

**Handling:** Documented, not patched. Candidate improvement (roadmap): ingest LAUSD's GATE annual school reports (ssr.lausd.net, GATE_AnnualSchoolReport), which count gifted-identified students per school and could support disaggregating or at least flagging magnet-within-school populations for LAUSD entities.

### CDE-NCES district crosswalk gaps between census geoids and CDE districts

*coverage-limitation, affects directory 2024* — id `nces-crosswalk-gaps`

The enrollment-flow model joins census school-district geography to CDE districts through the directory's ncesdist (NCES LEAID = ACS geoid). The join has gaps in both directions. (1) 22 current district polygons have no CDE district mapping to their geoid (stale or blank ncesdist in the directory, recently reorganized districts) - these areas appear on the statewide map with accounting values but get no linked district page. (2) 75 CDE geographic districts (doc 52/54/56) carry an ncesdist with no current polygon - predecessor districts from reorganizations; their historical schools are sited by coordinates, so their seats still land in the right area. Separately, 14 NCES pseudo secondary districts (GEOID 0699xxx, elementary territory whose high grades a unified district serves) have no CDE LEA by construction; they are modeled as areas but are not crosswalk gaps.

**Handling:** Gap counts are surfaced in the DQ report on every build. Areas without a CDE crosswalk stay in the accounting and on the map (their names come from TIGER) but are excluded from per-district pages and search routing. No manual geoid patching - fixes belong upstream in the directory data or an explicit curated crosswalk with per-entry sources if it ever becomes necessary.

### Central-cost allocation conventions vary by LEA and can shift between years

*reporting-inconsistency, affects ppe 2019, 2020, 2021, 2022, 2023* — id `ppe-central-allocation-conventions`

ESSA PPE splits each school's per-pupil figure into school-site and allocated central-office dollars, but each district chooses its own allocation method, and some changed methods mid-series. Berkeley Unified is a clear case: its 2019-20 through 2021-22 filings allocate $30k-$49k/pupil of "central" costs to Berkeley High (central federal alone reaches $30k/pupil in 2021-22 — several times the school-site total and far beyond any plausible spending), then from 2022-23 the same school's central allocation drops to a sane $0.3k-$15k/pupil. The inflated years pass the totals-reporter screen because the LEA's median stays under $100k/pupil. Statewide, roughly 4% of school rows in every file year carry central allocations more than twice their school-site spending — some legitimately (small schools in central-heavy districts), so a blanket screen would discard real data.

**Handling:** Not screened beyond the existing totals-reporter and implausible-value rules — a reliable detector for "allocation convention changed" that does not also discard legitimate central-heavy schools has not been designed yet. The spending history shown on entity pages is CDE's published figures after the documented normalizations, and the site copy notes that year-to-year level shifts can reflect filing conventions rather than actual spending changes. Candidate improvement: flag LEA-years whose median central-to-school-site ratio departs by more than ~3x from that LEA's own cross-year median.

### Some LEAs filed implausibly low ESSA PPE — state/local dollars missing

*reporting-inconsistency, affects ppe 2024, 2025* — id `ppe-implausibly-low-filings`

Nine LEAs (93 school rows, ~66,000 students) filed 2024-25 ESSA per-pupil expenditures with a median total under $5,000/pupil — below the LCFF base grant alone, and impossible as a real total. Mt. Diablo Unified is the largest clear case: every one of its 50 schools reports near-zero state/local dollars (max $487/pupil district-wide, central $0), leaving only stray federal amounts — e.g. Mt. Diablo High at $1,084/pupil. Prior years show the filing decayed: Mt. Diablo High totaled roughly $27k/pupil through 2022-23, then $2.7k in 2023-24 and $1.1k in 2024-25. Sweetwater Union High ($4,038 median across 29 schools) is the other large affected LEA. A further 108 individual school rows fall under $5,000 inside otherwise-normal LEAs.

**Handling:** Named transform in analysis/export.py alongside the totals-reporter normalization: an LEA whose median reported value is under $5,000/pupil is treated as a broken filing and ALL of its rows are dropped (a broken LEA's individually-plausible rows are not trusted either). Independently, any row under $5,000/pupil after normalization is dropped. (The upper bound is $500,000: legitimately expensive tiny SpEd/court/community-day programs reach $150k-$400k per pupil and are kept.) Affected schools and districts show no per-pupil spending rather than a wrong number; no substitution from prior years is attempted.

### Some LEAs file total dollars, not per-pupil amounts, in the ESSA PPE file

*reporting-inconsistency, affects ppe 2025* — id `ppe-totals-reporting`

The ESSA per-pupil expenditure file (essappe2425data.xlsx) mixes reporting conventions. Most LEAs report per-pupil dollars as specified, but roughly 5% of LEAs (98 of 1,926 with membership data) filed school-level TOTAL expenditures in the per-pupil columns. Example: Granada Hills Charter reports $99,223,734 with 5,927 students — dividing by membership yields a plausible $16,741/pupil. The convention is consistent within an LEA (all of Acalanes Union High's schools are totals), so detection is per-LEA, not per-row.

**Handling:** Named transform in analysis/export.py (normalize ppe totals-reporters): an LEA whose median reported value exceeds $100,000/pupil is treated as a totals-reporter and every one of its rows is divided by student membership (rows without membership become null). After normalization, values outside [$5,000, $500,000] per pupil are treated as unusable and dropped (see also ppe-implausibly-low-filings for the symmetric low-side LEA rule; the high ceiling deliberately keeps tiny SpEd/court/community-day programs that legitimately run $150k-$400k per pupil). District and county figures are rebuilt from school dollars (value x membership, summed, re-divided) — never by averaging per-pupil ratios.

### CAASPP's SED flag and FRPM eligibility disagree by ±5pp at ~30% of high schools

*definition-divergence, affects caaspp 2016, 2017, 2018, 2019, 2022, 2023, 2024, 2025* — id `sed-vs-frpm-measure-divergence`

CAASPP student group 31 uses CDE's socioeconomically-disadvantaged (SED) definition — FRPM-eligible, or neither parent a high-school graduate, or migrant/foster/homeless — nominally a superset of FRPM. In practice the two measures sit at parity on average and disagree in both directions: across 1,205 high schools with >= 100 grade-11 students in 2025, grade-11 SED share minus school-wide FRPM share has median +0.3pp, but 14% of schools show SED at least 5pp BELOW FRPM (a superset measuring under its subset) and 16% at least 5pp above. Candidate mechanisms: grade-composition differences (FRPM spans the school; SED here is grade 11 only), and divergent collection regimes — CEP/universal-meals districts count FRPM via direct certification and alternative income forms while the SED flag comes through CALPADS, and income-form collection weakens in upper high-school grades. John Marshall Senior High (19647331935568) illustrates the tail: grade-11 tested SED fell 77% -> 67% over the decade while school-wide FRPM held ~72%, with test participation 92-97% and uniform across groups (so participation skew is ruled out).

**Handling:** Not corrected — both measures are published as defined. Site handling: the glossary documents the SED / FRPM / unduplicated-count distinctions; the intake-shift warning on entity pages cross-checks tested-SED shifts against FRPM census history over the same span and says explicitly when school-wide FRPM moved much less (i.e., the shift reflects who is tested or how students are classified, not who enrolls). The adjustment model's covariates use tested-population shares consistently, so model comparisons are like-for-like even where the two measures diverge.

## Check findings

### enrollment_definition

- 🔴 **2015** 100.0% of 948 districts report IDENTICAL enrollment for All Students, Male, and Socioeconomically-Disadvantaged rows — the enrollment field carries entity-level counts, not subgroup counts (known 2015 definition issue, id caaspp-2015-enrollment-definition)
### participation

- 🔴 **2021** statewide ELA participation 23.7% — participation collapse; do not use for trends
### subgroup_sums

- 🔴 **2015** fluency 6 = 7 + 8 + 180 (IFEP + RFEP + English-only): 771 district(s) violate the identity by more than 2%
  - Los Angeles Unified (cds 1964733…): parent=285,954 vs children 857,862
  - San Diego Unified (cds 3768338…): parent=56,661 vs children 169,983
  - Long Beach Unified (cds 1964725…): parent=41,478 vs children 124,434
  - Fresno Unified (cds 1062166…): parent=37,901 vs children 113,703
  - Elk Grove Unified (cds 3467314…): parent=33,878 vs children 101,634
- 🔴 **2015** economic status (31 + 111 = all students): 948 district(s) violate the identity by more than 2%
  - Los Angeles Unified (cds 1964733…): parent=285,954 vs children 571,908
  - San Diego Unified (cds 3768338…): parent=56,661 vs children 113,322
  - Long Beach Unified (cds 1964725…): parent=41,478 vs children 82,956
  - Fresno Unified (cds 1062166…): parent=37,901 vs children 75,802
  - Elk Grove Unified (cds 3467314…): parent=33,878 vs children 67,756
- 🔴 **2015** gender (male 3 + female 4 = all students): 949 district(s) violate the identity by more than 2%
  - Los Angeles Unified (cds 1964733…): parent=285,954 vs children 571,908
  - San Diego Unified (cds 3768338…): parent=56,661 vs children 113,322
  - Long Beach Unified (cds 1964725…): parent=41,478 vs children 82,956
  - Fresno Unified (cds 1062166…): parent=37,901 vs children 75,802
  - Elk Grove Unified (cds 3467314…): parent=33,878 vs children 67,756
- 🔴 **2015** disability (128 + 99 = all students): 931 district(s) violate the identity by more than 2%
  - Los Angeles Unified (cds 1964733…): parent=285,954 vs children 571,908
  - San Diego Unified (cds 3768338…): parent=56,661 vs children 113,322
  - Long Beach Unified (cds 1964725…): parent=41,478 vs children 82,956
  - Fresno Unified (cds 1062166…): parent=37,901 vs children 75,802
  - Elk Grove Unified (cds 3467314…): parent=33,878 vs children 67,756
- 🔴 **2021** gender (male 3 + female 4 = all students): 3 district(s) violate the identity by more than 2%
  - Shasta County Office of Education (cds 4510454…): parent=95 vs children 93
  - Yolo County Office of Education (cds 5710579…): parent=48 vs children 47
  - Monte Rio Union Elementary (cds 4970813…): parent=48 vs children 47
- 🔴 **2022** gender (male 3 + female 4 = all students): 4 district(s) violate the identity by more than 2%
  - Humboldt County Office of Education (cds 1210124…): parent=62 vs children 59
  - Imperial County Office of Education (cds 1310132…): parent=49 vs children 48
  - Napa County Office of Education (cds 2810280…): parent=42 vs children 41
  - Monte Rio Union Elementary (cds 4970813…): parent=40 vs children 39
- 🔴 **2023** gender (male 3 + female 4 = all students): 5 district(s) violate the identity by more than 2%
  - West Sonoma County Union High (cds 4970607…): parent=419 vs children 409
  - Sebastopol Union Elementary (cds 4970938…): parent=293 vs children 286
  - Humboldt County Office of Education (cds 1210124…): parent=73 vs children 71
  - Dunsmuir Elementary (cds 4770243…): parent=46 vs children 45
  - Peninsula Union (cds 1262984…): parent=38 vs children 37
- 🔴 **2024** gender (male 3 + female 4 = all students): 2 district(s) violate the identity by more than 2%
  - SBE - Latitude 37.8 High (cds 0177180…): parent=93 vs children 91
  - SBE - Olive Grove Charter - Santa Barbar (cds 4277222…): parent=36 vs children 35
- 🔴 **2025** gender (male 3 + female 4 = all students): 5 district(s) violate the identity by more than 2%
  - Leggett Valley Unified (cds 2375218…): parent=68 vs children 65
  - Contra Costa County Office of Education (cds 0710074…): parent=90 vs children 87
  - SBE - Altus Schools East County (cds 3777099…): parent=76 vs children 74
  - Monte Rio Union Elementary (cds 4970813…): parent=44 vs children 43
  - SBE - Olive Grove Charter - Santa Barbar (cds 4277222…): parent=46 vs children 45
### enrollment_remote

- 🟡 **2024** classification churn vs prior vintage: ['4570169', '4970730', '5572413'] — check whether a borderline authorizer crossed the ratio cut
### entity_continuity

- 🟡 **2016** 18 schools report in 2015 and 2017 but not 2016 (closures/reopenings, code changes, or reporting gaps)
- 🟡 **2017** 13 schools report in 2016 and 2018 but not 2017 (closures/reopenings, code changes, or reporting gaps)
- 🟡 **2018** 27 schools report in 2017 and 2019 but not 2018 (closures/reopenings, code changes, or reporting gaps)
- 🟡 **2022** 19 schools report in 2021 and 2023 but not 2022 (closures/reopenings, code changes, or reporting gaps)
- 🟡 **2023** 41 schools report in 2022 and 2024 but not 2023 (closures/reopenings, code changes, or reporting gaps)
- 🟡 **2024** 17 schools report in 2023 and 2025 but not 2024 (closures/reopenings, code changes, or reporting gaps)
### suppression

- 🟡 **2015** 100.0% of 11,418 school-level All-Students ELA rows have suppressed scores
- 🟡 **2016** 100.0% of 9,990 school-level All-Students ELA rows have suppressed scores
- 🟡 **2017** 100.0% of 10,251 school-level All-Students ELA rows have suppressed scores
- 🟡 **2018** 100.0% of 10,250 school-level All-Students ELA rows have suppressed scores
- 🟡 **2019** 100.0% of 10,299 school-level All-Students ELA rows have suppressed scores
- 🟡 **2021** 100.0% of 10,099 school-level All-Students ELA rows have suppressed scores
- 🟡 **2022** 100.0% of 10,257 school-level All-Students ELA rows have suppressed scores
- 🟡 **2023** 100.0% of 10,223 school-level All-Students ELA rows have suppressed scores
- 🟡 **2024** 100.0% of 10,242 school-level All-Students ELA rows have suppressed scores
- 🟡 **2025** 100.0% of 10,221 school-level All-Students ELA rows have suppressed scores
### census_frpm

- ℹ️ ACS 2023 B17024 vs FRPM 2025-2026: 905/936 districts matched (97%), median FRPM/P185 rate ratio 1.86x (PPIC benchmark ~1.8x)
### enrollment_closure

- ℹ️ per-county netting exact: every county's district nets sum to <1 student across all 16 vintages
- ℹ️ county-level netting exact: county nets sum to <1 student statewide across all 16 vintages
- ℹ️ **2009** closure +0.000% of state enrollment (tolerance ±0.5%), m=5.43%, 923/974 areas covered
- ℹ️ **2010** closure -0.000% of state enrollment (tolerance ±0.5%), m=3.59%, 935/974 areas covered
- ℹ️ **2011** closure -0.000% of state enrollment (tolerance ±0.5%), m=3.27%, 935/974 areas covered
- ℹ️ **2012** closure -0.000% of state enrollment (tolerance ±0.5%), m=3.30%, 941/974 areas covered
- ℹ️ **2013** closure -0.000% of state enrollment (tolerance ±0.5%), m=3.77%, 941/974 areas covered
- ℹ️ **2014** closure +0.000% of state enrollment (tolerance ±0.5%), m=4.46%, 953/974 areas covered
- ℹ️ **2015** closure -0.000% of state enrollment (tolerance ±0.5%), m=4.82%, 953/974 areas covered
- ℹ️ **2016** closure -0.000% of state enrollment (tolerance ±0.5%), m=5.06%, 958/974 areas covered
- ℹ️ **2017** closure -0.000% of state enrollment (tolerance ±0.5%), m=5.48%, 958/974 areas covered
- ℹ️ **2018** closure -0.000% of state enrollment (tolerance ±0.5%), m=5.80%, 973/974 areas covered
- ℹ️ **2019** closure +0.000% of state enrollment (tolerance ±0.5%), m=5.97%, 973/974 areas covered
- ℹ️ **2020** closure -0.000% of state enrollment (tolerance ±0.5%), m=6.51%, 973/974 areas covered
- ℹ️ **2021** closure -0.000% of state enrollment (tolerance ±0.5%), m=4.83%, 973/974 areas covered
- ℹ️ **2022** closure +0.000% of state enrollment (tolerance ±0.5%), m=5.80%, 973/974 areas covered
- ℹ️ **2023** closure -0.000% of state enrollment (tolerance ±0.5%), m=4.95%, 973/974 areas covered
- ℹ️ **2024** closure -0.000% of state enrollment (tolerance ±0.5%), m=4.89%, 974/974 areas covered
### enrollment_definition

- ℹ️ **2016** subgroup enrollment varies normally (0.0% of 877 districts constant)
- ℹ️ **2017** subgroup enrollment varies normally (0.0% of 880 districts constant)
- ℹ️ **2018** subgroup enrollment varies normally (0.0% of 877 districts constant)
- ℹ️ **2019** subgroup enrollment varies normally (0.0% of 880 districts constant)
- ℹ️ **2021** subgroup enrollment varies normally (0.0% of 844 districts constant)
- ℹ️ **2022** subgroup enrollment varies normally (0.0% of 862 districts constant)
- ℹ️ **2023** subgroup enrollment varies normally (0.0% of 864 districts constant)
- ℹ️ **2024** subgroup enrollment varies normally (0.0% of 871 districts constant)
- ℹ️ **2025** subgroup enrollment varies normally (0.0% of 865 districts constant)
### enrollment_doc_validation

- ℹ️ **2023** observed DOC transfers: 7,920 students in matched pairs, 69% between ADJACENT districts — supports the nearby-draw premise
- ℹ️ **2023** model-vs-observed sign agreement: 22/24 DOC districts (>20 transfers) match the model's net direction (or sit within the model's margin); disagreements are expected where DOC is a small share of a district's total movement
- ℹ️ **2023** largest DOC importer: observed net +2,434 transfers vs model net +5,013 (model includes permits and charter draw beyond the DOC program)
### enrollment_lausd_regression

- ℹ️ **2014** resident public 651,638 vs LAUSD page 651,638 (+0; tolerance ±6,516)
- ℹ️ **2015** resident public 644,075 vs LAUSD page 644,075 (+0; tolerance ±6,441)
- ℹ️ **2016** resident public 642,388 vs LAUSD page 642,388 (+0; tolerance ±6,424)
- ℹ️ **2017** resident public 639,413 vs LAUSD page 639,413 (+0; tolerance ±6,394)
- ℹ️ **2018** resident public 633,618 vs LAUSD page 633,618 (+0; tolerance ±6,336)
- ℹ️ **2019** resident public 628,432 vs LAUSD page 628,432 (+0; tolerance ±6,284)
- ℹ️ **2020** resident public 617,918 vs LAUSD page 617,918 (+0; tolerance ±6,179)
- ℹ️ **2021** resident public 608,436 vs LAUSD page 608,436 (+0; tolerance ±6,084)
- ℹ️ **2022** resident public 584,275 vs LAUSD page 584,275 (+0; tolerance ±5,843)
- ℹ️ **2023** resident public 576,435 vs LAUSD page 576,435 (+0; tolerance ±5,764)
### enrollment_remote

- ℹ️ **2024** 22 geographic authorizers classified non-classroom (criterion: charter seats > 1.5x resident base, >= 50 seats); pooled seats 35,682
- ℹ️ **2024** authorizer 3675051: 5,944 charter seats vs 1,222 resident children (ratio 4.9)
- ℹ️ **2024** authorizer 3667827: 5,580 charter seats vs 89 resident children (ratio 62.6)
- ℹ️ **2024** authorizer 1975309: 5,246 charter seats vs 1,200 resident children (ratio 4.4)
- ℹ️ **2024** authorizer 3767983: 2,546 charter seats vs 147 resident children (ratio 17.3)
- ℹ️ **2024** authorizer 5171407: 2,509 charter seats vs 117 resident children (ratio 21.4)
- ℹ️ **2024** authorizer 3667736: 2,204 charter seats vs 835 resident children (ratio 2.6)
- ℹ️ **2024** authorizer 3968627: 1,348 charter seats vs 345 resident children (ratio 3.9)
- ℹ️ **2024** authorizer 4569948: 1,240 charter seats vs 780 resident children (ratio 1.6)
### enrollment_siting

- ℹ️ crosswalk gaps: 22 current polygons with no CDE district, 75 CDE geographic districts with no current polygon (reorganizations; see known_issues)
- ℹ️ **2026** UNSITED (import-only pool): 2,152 students (0.04%)
- ℹ️ **2026** admin: 5,231,539 students (91.28%)
- ℹ️ **2026** pip: 497,569 students (8.68%)
### lausd_resolution

- ℹ️ 985 MP25 polygons; 0 P_KEY/segment mismatches
- ℹ️ 820/821 distinct E/M/H keys resolved to schools; unresolved: [{'level': 'E', 'key5': '11017'}]
- ℹ️ all 697 resolved CDS codes exist in the CDE directory under district 1964733
### participation

- ℹ️ **2015** statewide ELA participation 96.0%
- ℹ️ **2016** statewide ELA participation 96.4%
- ℹ️ **2017** statewide ELA participation 97.1%
- ℹ️ **2018** statewide ELA participation 97.1%
- ℹ️ **2019** statewide ELA participation 97.2%
- ℹ️ **2022** statewide ELA participation 96.0%
- ℹ️ **2023** statewide ELA participation 96.9%
- ℹ️ **2024** statewide ELA participation 96.7%
- ℹ️ **2025** statewide ELA participation 97.1%
### row_counts

- ℹ️ **2015** 3,202,981 rows (era A)
- ℹ️ **2016** 3,116,795 rows (era A)
- ℹ️ **2017** 3,264,973 rows (era B)
- ℹ️ **2018** 3,269,730 rows (era B)
- ℹ️ **2019** 3,576,491 rows (era B)
- ℹ️ **2020** no file exists (COVID-19 testing cancellation) — trends must bridge this gap explicitly
- ℹ️ **2021** 3,586,711 rows (era C)
- ℹ️ **2022** 3,855,781 rows (era C)
- ℹ️ **2023** 4,052,594 rows (era C)
- ℹ️ **2024** 4,050,626 rows (era D)
- ℹ️ **2025** 4,036,521 rows (era D)
