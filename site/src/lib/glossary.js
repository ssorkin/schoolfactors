// Single source of truth for every metric term the site displays.
// `tip` is the one-or-two-sentence tooltip; `def` is the full dictionary entry
// (array of paragraphs) shown on /glossary. Keep language correlational —
// "correlated with", "schools serving similar students" — never causal.

export const GLOSSARY = [
  {
    id: 'mean-scale-score',
    term: 'Mean scale score',
    unit: 'CAASPP scale points',
    tip: 'Average CAASPP scale score of tested students in one grade, subject, and year — our primary achievement measure.',
    def: [
      'The average CAASPP Smarter Balanced scale score of a school’s tested students in one grade, subject, and year. This is the primary achievement measure behind every model number on the site — unlike "percent proficient", it doesn’t jump when a few students cross a cut line.',
      'Calculation: taken directly from CDE research files, filtered to the non-overlapping "All Students" rows. Cells CDE suppresses (fewer than 11 students) stay blank — they are never treated as zero.'
    ]
  },
  {
    id: 'met-plus',
    term: '% met or exceeded (Met+)',
    unit: '% of tests',
    tip: 'Share of tests at achievement Level 3 (standard met) or 4 (exceeded), latest year. Raw — not adjusted for the students served.',
    def: [
      'The share of tests scoring at achievement Level 3 ("standard met") or Level 4 ("standard exceeded"), in the most recent year with data. Shown because it’s the number CDE publishes and most families recognize; it is coarser than the mean scale score and moves when students cross a cut line.',
      'Calculation: percentages are never averaged directly — counts are reconstructed (percent × number tested), combined, and re-divided.'
    ]
  },
  {
    id: 'met-plus-by-year',
    term: 'Met+ by year (the small line chart)',
    unit: '% of tests, per year',
    tip: 'Raw Met+ by year, ELA and Math combined (2015–19, 2022–25). A rising line is mostly the state rising — for state-relative change, see Trend.',
    def: [
      'The raw Met+ rate for each year from 2015–2019 and 2022–2025, ELA and Math combined, weighted by the number of tests. 2020 had no testing; 2021 is excluded because statewide participation collapsed to 24%.',
      'This line is raw and un-adjusted: since 2022, pass rates have been recovering statewide, so most of a rising line is the state rising. Whether a school is gaining on the state is a different question — that’s Trend. Each chart is scaled to its own row, so slopes are not comparable across rows.'
    ]
  },
  {
    id: 'student-sd',
    term: 'Student SD (the unit)',
    unit: 'standard deviations',
    tip: 'The unit for all model numbers. Intuition: a student at +1 SD scores higher than about 84% of students statewide; +2 SD, higher than about 98%.',
    def: [
      'A standard deviation (SD) measures how spread out scores are. The everyday intuition: a student scoring +1 SD above average outscores about 84% of students statewide; +2 SD, about 98%; −1 SD means about 84% score higher. (Equivalently: about 68% of all students fall within ±1 SD of average, 95% within ±2.)',
      'Every model number (Level, Growth, Trend, and their adjusted versions) is expressed in student standard deviations: one SD of individual student scores statewide, within the same grade, subject, and year. A school at +0.20 means its average student sits a fifth of an SD above the comparison point — roughly outscoring 58% of students statewide instead of 50%.',
      'Behind this: each school-grade-subject-year mean scale score is standardized against the state — school mean minus state mean, divided by the student SD. The state average is therefore 0 in every year and grade by construction, and every model number is relative to the state.'
    ]
  },
  {
    id: 'level',
    term: 'Level',
    unit: 'student SDs',
    tip: 'Where a school’s students score vs the state average, weighted toward the most recent years. Negative = below the state.',
    def: [
      'Where a school’s students score relative to the state average, in student SDs, weighted toward the most recent years of data: each year’s weight halves for every 1.5 years of age, so the level mostly reflects the last two-to-three test years. A school that was strong a decade ago but ordinary today shows an ordinary level.',
      'Calculation: the intercept of a precision-weighted regression of each school’s standardized scores on year, grade, and subject, with the recency decay folded into the weights. In a holdout test, this recency-weighted level predicted schools’ next-year standing far better than the all-years average. Level is strongly correlated with the students a school serves (raw level vs share economically disadvantaged: −0.74), which is why the adjusted version exists.'
    ]
  },
  {
    id: 'growth',
    term: 'Growth (cohort growth)',
    unit: 'student SDs per grade',
    tip: 'How much a class gains per grade vs the state as it moves through the school. 0 = cohorts hold their standing vs the state as they age. Not change over calendar years — that’s Trend.',
    def: [
      'How much a cohort — a class of students moving through the school together — gains per grade, relative to the state. Because scores are state-relative, 0 does not mean flat scores: it means cohorts hold their standing versus the state as they age. Positive growth means students pull further ahead (or close a gap) each grade.',
      'Growth is not change over calendar time. A school’s Met+ line can rise steadily while growth is ≈0 — that combination means successive cohorts arrive scoring higher, but each cohort keeps its relative position as it moves up. Year-over-year change is Trend.',
      'Calculation: the grade slope of the same precision-weighted regression. Schools testing a single grade have no growth estimate. The table shows the adjusted, shrunken version (see those entries).'
    ]
  },
  {
    id: 'trend',
    term: 'Trend',
    unit: 'student SDs per year',
    tip: 'Change per calendar year at a fixed grade, vs the state — are successive cohorts scoring higher? 0 = moving exactly with the state.',
    def: [
      'How much scores change per calendar year at a fixed grade, relative to the state — equivalently, whether successive cohorts are arriving and scoring higher than the ones before them, versus the state.',
      'Because it’s state-relative, 0 means moving exactly with the state — and the state itself has been recovering since 2022, so a school with trend 0 can still show a rising raw Met+ line.',
      'Calculation: the year slope of the same precision-weighted regression. 2020 and 2021 are excluded throughout.'
    ]
  },
  {
    id: 'adjusted',
    term: 'Adjusted (adj)',
    unit: 'student SDs',
    tip: 'What remains after accounting for the students served (economic disadvantage, race/ethnicity, EL and disability shares, parental education, size) — i.e. vs schools serving similar students. Not a measure of school quality.',
    def: [
      'An adjusted number compares a school against schools serving similar students rather than against the state: it is what remains of Level (recency-weighted — see Level) or Growth after accounting for the tested population’s economic disadvantage, race/ethnicity, English-learner and students-with-disabilities shares, parental education, and school size.',
      'This residual is not a measure of school quality — it still contains everything the covariates miss (selection, attrition, unmeasured family factors, luck).',
      'Calculation: a precision-weighted regression of the unshrunken school estimates on those covariates; the school’s residual is reported, then shrunken for display. The Adj ELA / Adj Math columns split the adjusted level using each school’s fitted Math−ELA gap.'
    ]
  },
  {
    id: 'expected-level',
    term: 'Expected level (given students served)',
    unit: 'student SDs',
    tip: 'What the statewide model predicts a school at this demographic profile would score — the bar its performance is measured against. Computed from CAASPP tested-population shares.',
    def: [
      'What the demographic adjustment model predicts a school with this profile would score, in student SDs versus the state: the fitted value from regressing every school’s level on its tested population’s economic disadvantage, race/ethnicity, English-learner and disability shares, parental education, and size.',
      'It is the bar the school’s actual level is measured against — "performance vs expectation" is actual minus expected, and the Similar Schools percentile ranks that difference. A school serving many high-need students has a low expected level; clearing it by a wide margin is what a high percentile means.',
      'Source: covariates from CAASPP research-file student-group counts; the model is documented in the open analysis writeup.'
    ]
  },
  {
    id: 'expected-alike-band',
    term: 'Expected-alike band',
    unit: '',
    tip: 'All schools the model expects to score about the same (predicted level within ±0.15 SDs). Comparing a school’s pass rates against this pool shows its percentile in plain numbers.',
    def: [
      'The pool of schools the model expects to score about the same — predicted level within ±0.15 student SDs of this school’s (widened to the nearest 15 schools where that band is sparse). Unlike statewide group averages, this comparison holds the whole demographic profile fixed.',
      'Entity and compare pages show each school’s Met+ and Exceeded rates against its own band’s pooled rates. The Exceeded level matters: two schools can match on percent-meeting-standards while differing sharply in how many students exceed them.',
      'Source: CAASPP research files (latest year, both subjects, count-weighted), pooled across the band.'
    ]
  },
  {
    id: 'adj-percentile',
    term: 'Similar Schools %ile (adjusted percentile)',
    unit: 'percentile, 1–99',
    tip: 'Percentile of the adjusted recent level among entities of the same kind, ranked by the lower bound of each estimate’s 95% band — an unconfident high estimate ranks below a confident slightly-lower one. 50 = typical for the students served.',
    def: [
      'Where an entity’s adjusted recent score level falls among entities of the same kind — schools are ranked among schools, districts among districts, counties among counties. A 75 means the adjusted level is higher than about three-quarters of comparable entities; 50 is typical for the students served.',
      'School pools additionally separate alternative programs (continuation, community day, court, special-ed) from the general pool: student selection, not performance, would otherwise place them at the bottom of a shared ranking, and their own ranking would be meaningless. Selective (exam-admission) schools stay in the general pool and carry a badge: admissions alone should place them near the top, so read a high percentile as reflecting who is admitted — while a selective school that is not near the top is itself worth noticing. A pool smaller than 20 shows no percentile at all.',
      'This is a presentation of the adjusted level (see Adjusted), in the spirit of the Urban Institute’s demographically adjusted rankings, with two conservative choices. First, entities are ranked by the lower bound of the 95% band around their shrunken estimate, not the estimate itself — an imprecise high estimate (typically a small school) ranks below a precise, slightly lower one. Second, no percentile is shown when the estimate’s reliability falls below 0.70 or when the entity has no test data in the latest year. The underlying student-SD values remain on each entity’s page.',
      'Read it loosely: many entities are statistically indistinguishable, so a 55 and a 62 should be treated as the same. And like every adjusted number, it is not a measure of school quality — it contains everything the adjustment misses.'
    ]
  },
  {
    id: 'cohort-trajectory',
    term: 'Cohort trajectory (gaining / holding / slipping)',
    unit: 'category',
    tip: 'Whether classes gain on the state, hold their standing, or lose ground as they move up grades. "Holding" at a high level is a fine outcome — this is a trajectory, not a rank.',
    def: [
      'Whether an entity’s cohorts — classes moving through together — gain on the state, hold their standing, or lose ground as they move up grades. "Holding" means the class’s distribution against grade-level standards stays stable as it advances: the share meeting CAASPP standards moves with the state’s. "Gaining" or "slipping" is declared only when the 95% band around the shrunken within-cohort slope — the growth and trend components a class actually experiences, combined — clears zero AND the estimate exceeds ±0.02 student SDs per grade; everything else is "holding". A dash means the estimate didn’t pass the reliability gate (0.70) or the entity lacks current-year data.',
      'Why a category and not a percentile: the spread of true growth across schools is small (about 0.07 SDs per grade), so ranking it turns near-zero differences into misleading-looking grades — a school whose cohorts arrive high and stay high would rank mid-pack on "growth" despite doing exactly what one hopes. Holding is a fine outcome; slipping is the warning sign worth investigating in the cohort chart; gaining at an already-high level is uncommon and notable. Statewide, roughly a third of schools land in each category, and the category is uncorrelated with score level — high-scoring schools gain, hold, and slip in the same proportions as everyone else.',
      'This is judged against the state (raw growth). The demographically adjusted growth value still appears in the model tiles on entity pages; the peer scatter’s vertical axis is a different measure — absolute improvement per year, with a diamond marking California overall. Growth is essentially uncorrelated with prior achievement (−0.01), the falsification test single-number rankings have famously failed. As everywhere on this site: correlational, not causal.'
    ]
  },
  {
    id: 'shrinkage',
    term: 'Shrunken estimate & reliability',
    unit: '0–1 (reliability)',
    tip: 'Noisy estimates (small schools) are pulled toward the average in proportion to their noise; estimates below 0.70 reliability are not shown.',
    def: [
      'A 40-student grade tells us less than a 400-student one, so every displayed estimate is shrunken (empirical Bayes): pulled toward the average in proportion to its statistical noise. Reliability is the share of a school’s estimate that is signal rather than noise (0–1); below 0.70 the estimate is withheld entirely.',
      'Consequence: small schools’ displayed values are conservative — their true values are probably further from the average than shown, in an unknown direction. Many schools are statistically indistinguishable from one another; sorting is not ranking.'
    ]
  },
  {
    id: 'cohort',
    term: 'Cohort (Class of YYYY)',
    unit: '',
    tip: 'Students on track to graduate in year YYYY, followed along the diagonal of the year × grade table.',
    def: [
      'A class of students moving through school together, labeled by expected graduation year: grade 3 in spring of year Y is the Class of Y+9. Cohorts are followed along the diagonal of the year × grade table — the Class of 2025 is grade 3 in 2016, grade 4 in 2017, and so on.',
      'These are aggregate cohorts, not linked student records: students transfer in and out, so part of a cohort’s change can be composition change. Entity pages chart the expected effect of enrollment blend shifts separately.'
    ]
  },
  {
    id: 'ppe',
    term: 'Per-pupil spending ($/pupil)',
    unit: 'dollars per pupil per year',
    tip: 'Total ESSA per-pupil expenditure — school-site plus allocated central costs, federal plus state/local — latest available year (2024–25). District and county values are rebuilt from school dollars, weighted by membership.',
    def: [
      'Total expenditure per pupil from CDE’s ESSA per-pupil expenditure reports — the only school-level spending data California publishes. It sums four components: school-site and allocated central-office costs, each split into federal and state/local dollars, for the latest available year (currently 2024–25).',
      'District and county figures are reconstructed from school-level dollars (per-pupil value × student membership, summed, then re-divided) — per-pupil ratios are never averaged. Charter schools are included under their CDS-prefix district, matching how test-score rollups work on this site. A rollup is shown only when usable school reports cover at least 70% of the entity’s enrollment.',
      'Caveats: spending is largely need-driven — schools serving more high-need students receive more funding by design — so higher spending is neither praise nor criticism. Central costs are allocated to schools by each district’s own method, which limits fine-grained comparisons across districts. About 5% of LEAs filed total dollars instead of per-pupil amounts in the source file; we detect and normalize this (documented as a known issue), and drop implausible values rather than guessing.'
    ]
  },
  {
    id: 'econ-share',
    term: '% FRPM',
    unit: '% of students',
    tip: 'Share of enrolled students eligible for free or reduced-price meals (FRPM) — the standard economic-disadvantage measure. A dash means CDE published no FRPM data for this entity.',
    def: [
      'The share of all enrolled students eligible for free or reduced-price meals (FRPM census) — the standard school-level measure of economic disadvantage. A dash means CDE published no FRPM data for this entity; we never substitute the differently-defined tested-population share into this column.',
      'Note the two definitions differ slightly: FRPM covers the whole enrollment; the CAASPP flag covers tested students only. The adjustment model uses the tested-population share.',
      'CAASPP’s "economically disadvantaged" group is CDE’s socioeconomically-disadvantaged definition — FRPM-eligible, or neither parent a high-school graduate, or migrant/foster/homeless — so it typically runs a few points above FRPM alone, and it can move with test participation and classification, not only enrollment. It is also not the LCFF "unduplicated pupil count", which additionally folds in English learners.'
    ]
  },
  {
    id: 'enrollment',
    term: 'Students (enrollment)',
    unit: 'students',
    tip: 'Census-day enrollment in the latest school year. The small line shows the census trend since 2014–15, including the COVID years.',
    def: [
      'Census-day (early-October) enrollment from CDE, for the latest available school year. District and county rows are K–12 totals.',
      'The small line beside the number shows the census enrollment trend from 2014–15 through the current year, stitched from CDE’s historical enrollment-by-school files (through 2022–23) and the new-format census files (2023–24 on). Unlike test scores, the census ran right through 2020 and 2021, so the line has no COVID gap. District and county trends roll up school rows, with charter schools folded into their CDS-prefix district.'
    ]
  },
  {
    id: 'scores',
    term: 'Scores',
    unit: 'test scores',
    tip: 'Total test scores across all years, grades, and subjects — the sample size behind the estimates.',
    def: [
      'The total number of test scores across all years, grades, and subjects that feed an entity’s estimates. More scores mean tighter estimates and less shrinkage; it is a sample-size indicator, not an achievement measure.'
    ]
  },
  {
    id: 'suppression',
    term: 'Suppressed data (—)',
    unit: '',
    tip: 'CDE hides cells with fewer than 11 students. Suppressed values stay blank — a dash can mean "hidden", never "zero".',
    def: [
      'CDE suppresses any cell covering fewer than 11 students (shown as * in source files). We carry suppression through as missing data — a dash on this site can mean "too few students to report", and is never coerced to zero.'
    ]
  },
  {
    id: 'cds',
    term: 'CDS code',
    unit: '14 digits',
    tip: 'California’s school identifier: County (2) + District (5) + School (7). School code 0000000 = a district row; district 00000 = a county row.',
    def: [
      'California’s standard school identifier: two county digits, five district digits, seven school digits, zero-padded. A school code of 0000000 denotes a district-level row; a district code of 00000 denotes a county-level row. CDS codes are the join key across every dataset on this site and appear in page URLs.'
    ]
  }
];

// id → tooltip text, for table headers etc.
export const TIP = Object.fromEntries(GLOSSARY.map((g) => [g.id, g.tip]));

// Main-table column key → tooltip, composed from glossary terms so the
// definitions live in exactly one place.
export const COLTIP = {
  pass_ela: 'ELA — ' + TIP['met-plus'],
  pass_math: 'Math — ' + TIP['met-plus'],
  spark: TIP['met-plus-by-year'],
  adj_pct: TIP['adj-percentile'],
  growth_eb: TIP['cohort-trajectory'],
  ppe: TIP['ppe'],
  econ: TIP['econ-share'],
  enrollment: TIP['enrollment']
};
