# Data Quality Report

Generated 2026-08-19 by `sf check`. This report is a first-class artifact of the pipeline: problems in the source data are surfaced here and in `known_issues/`, never silently patched.

## Known issues (documented registry)

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
  - Monte Rio Union Elementary (cds 4970813…): parent=48 vs children 47
  - Yolo County Office of Education (cds 5710579…): parent=48 vs children 47
- 🔴 **2022** gender (male 3 + female 4 = all students): 4 district(s) violate the identity by more than 2%
  - Humboldt County Office of Education (cds 1210124…): parent=62 vs children 59
  - Imperial County Office of Education (cds 1310132…): parent=49 vs children 48
  - Napa County Office of Education (cds 2810280…): parent=42 vs children 41
  - Monte Rio Union Elementary (cds 4970813…): parent=40 vs children 39
- 🔴 **2023** gender (male 3 + female 4 = all students): 5 district(s) violate the identity by more than 2%
  - West Sonoma County Union High (cds 4970607…): parent=419 vs children 409
  - Sebastopol Union Elementary (cds 4970938…): parent=293 vs children 286
  - Humboldt County Office of Education (cds 1210124…): parent=73 vs children 71
  - Peninsula Union (cds 1262984…): parent=38 vs children 37
  - Dunsmuir Elementary (cds 4770243…): parent=46 vs children 45
- 🔴 **2024** gender (male 3 + female 4 = all students): 2 district(s) violate the identity by more than 2%
  - SBE - Latitude 37.8 High (cds 0177180…): parent=93 vs children 91
  - SBE - Olive Grove Charter - Santa Barbar (cds 4277222…): parent=36 vs children 35
- 🔴 **2025** gender (male 3 + female 4 = all students): 5 district(s) violate the identity by more than 2%
  - Contra Costa County Office of Education (cds 0710074…): parent=90 vs children 87
  - Leggett Valley Unified (cds 2375218…): parent=68 vs children 65
  - SBE - Altus Schools East County (cds 3777099…): parent=76 vs children 74
  - SBE - Olive Grove Charter - Santa Barbar (cds 4277222…): parent=46 vs children 45
  - Monte Rio Union Elementary (cds 4970813…): parent=44 vs children 43
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
