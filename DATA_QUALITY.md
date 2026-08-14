# Data Quality Report

Generated 2026-08-14 by `sf check`. This report is a first-class artifact of the pipeline: problems in the source data are surfaced here and in `known_issues/`, never silently patched.

## Known issues (documented registry)

### 2015 "number enrolled" counts all-subject eligibility, later years count per-subject

*definition-change, affects caaspp 2015* — id `caaspp-2015-enrollment-definition`

In the 2014-15 research file, the enrollment field counts all students who were eligible to take CAASPP in ANY subject. From 2015-16 onward it counts students eligible for the specific test (subject) in the row. CDE confirmed the 2015 file was never revised to the new definition ("we usually don't have funds available to ask our contractor to revise previous year data files").

**Handling:** Never compare students_enrolled across the 2015/2016 boundary. Participation-rate computations for 2015 use tested/enrolled with this caveat attached. Analyses use students_tested and mean_scale_score, which are unaffected.

### 2015 subgroup enrollment is identical across ALL subgroups (statewide)

*internal-inconsistency, affects caaspp 2015* — id `caaspp-2015-fluency-subgroup-sums`

Originally observed in district 70953 (Sonoma Valley Unified), where fluency subgroups 6/7/8 report identical enrollment in sb_ca2015_all_csv_v3.txt. Our checks show this is statewide and affects every subgroup, not just fluency: in 2015 every subgroup row carries the entity-level "eligible in any subject" count (e.g. LAUSD reports 285,954 enrolled for All Students, Male, Econ-Dis, and every fluency group alike). This is the row-level manifestation of caaspp-2015-enrollment-definition. Tested counts are NOT affected: even in 2015 they satisfy the true identity 6 = 7 + 8 + 180 (see caaspp-group6-definition).

**Handling:** Never use 2015 subgroup-level students_enrolled. Subgroup denominators for 2015 must come from students_tested / students_with_scores, or the series starts at 2016.

### Student group 6 includes English Only students (6 = 7 + 8 + 180)

*definition-note, affects caaspp 2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025* — id `caaspp-group6-definition`

Group 6 ("Fluent English proficient and English only") is the sum of groups 7 (IFEP) + 8 (RFEP) + 180 (English Only), not 7 + 8 as one might assume from the name "fluent". Verified empirically: the identity 6 = 7 + 8 + 180 holds exactly for enrollment in 2016+ and for tested counts in all years including 2015. Older CDE layout documents describe group 6 inconsistently ("IFEP and EO" in some years), so treat the empirical identity as authoritative.

**Handling:** Analyses that need "fluent but not English-only" must use groups 7 + 8 directly, never group 6 minus anything.

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
