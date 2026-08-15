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
    tip: 'The unit for all model numbers: one standard deviation of individual student scores statewide, within the same grade, subject, and year.',
    def: [
      'Every model number (Level, Growth, Trend, and their adjusted versions) is expressed in student standard deviations: one SD of individual student scores statewide, within the same grade, subject, and year. A school at +0.20 sits a fifth of a student SD above its comparison point.',
      'Behind this: each school-grade-subject-year mean scale score is standardized against the state — school mean minus state mean, divided by the student SD. The state average is therefore 0 in every year and grade by construction, and every model number is relative to the state.'
    ]
  },
  {
    id: 'level',
    term: 'Level',
    unit: 'student SDs',
    tip: 'Where a school’s students score vs the state average, at the middle of its data. Negative = below the state.',
    def: [
      'Where a school’s students score relative to the state average, in student SDs, evaluated at the middle of the school’s data (its typical year and grade).',
      'Calculation: the intercept of a precision-weighted regression of each school’s standardized scores on year, grade, and subject. Level is strongly correlated with the students a school serves (raw level vs share economically disadvantaged: −0.76), which is why the adjusted version exists.'
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
      'An adjusted number compares a school against schools serving similar students rather than against the state: it is what remains of Level or Growth after accounting for the tested population’s economic disadvantage, race/ethnicity, English-learner and students-with-disabilities shares, parental education, and school size.',
      'This residual is not a measure of school quality — it still contains everything the covariates miss (selection, attrition, unmeasured family factors, luck).',
      'Calculation: a precision-weighted regression of the unshrunken school estimates on those covariates; the school’s residual is reported, then shrunken for display. The Adj ELA / Adj Math columns split the adjusted level using each school’s fitted Math−ELA gap.'
    ]
  },
  {
    id: 'adj-percentile',
    term: 'Adj %ile (adjusted percentile)',
    unit: 'percentile, 1–99',
    tip: 'Percentile of the adjusted score level among entities of the same kind (schools vs schools, districts vs districts). 50 = typical for the students served. Small differences are noise; shown only when the estimate is reliable.',
    def: [
      'Where an entity’s adjusted score level falls among entities of the same kind — schools are ranked among schools, districts among districts, counties among counties. A 75 means the adjusted level is higher than about three-quarters of comparable entities; 50 is typical for the students served.',
      'This is a presentation of the adjusted level (see Adjusted), in the spirit of the Urban Institute’s demographically adjusted rankings: estimates are shrunken first, and no percentile is shown when the estimate’s reliability falls below 0.70. The underlying student-SD values remain on each entity’s page.',
      'Read it loosely: many entities are statistically indistinguishable, so a 55 and a 62 should be treated as the same. And like every adjusted number, it is not a measure of school quality — it contains everything the adjustment misses.'
    ]
  },
  {
    id: 'growth-percentile',
    term: 'Growth %ile (cohort-growth percentile)',
    unit: 'percentile, 1–99',
    tip: 'Percentile of adjusted cohort growth among entities of the same kind. Above 50 = classes gain more per grade than comparable entities. Small differences are noise; shown only when the estimate is reliable.',
    def: [
      'Where an entity’s adjusted cohort growth (see Growth) falls among entities of the same kind. Above 50, classes gain more ground per grade — relative to the state, given the students served — than most comparable entities; below 50, less.',
      'Growth percentiles answer the closest thing to a "value-added" question this data can support: aggregate cohorts moving through a school, standardized against the state, adjusted for the population served, shrunken, and reliability-gated (below 0.70, no percentile is shown). Unlike teacher value-added models built on linked student records, it makes no claim about causation — and our growth measure is essentially uncorrelated with prior achievement (+0.01), the falsification test single-model rankings have famously failed.',
      'Read it loosely: growth is estimated with more noise than level, so treat mid-range differences as ties.'
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
    term: '% Econ',
    unit: '% of students',
    tip: 'Share of enrolled students eligible for free or reduced-price meals (FRPM); where FRPM is missing, the share of tested students CDE classifies as economically disadvantaged.',
    def: [
      'The share of all enrolled students eligible for free or reduced-price meals (FRPM census). Where FRPM data is missing, the share of tested students CDE classifies as economically disadvantaged is used instead.',
      'Note the two definitions differ slightly: FRPM covers the whole enrollment; the CAASPP flag covers tested students only. The adjustment model uses the tested-population share.'
    ]
  },
  {
    id: 'enrollment',
    term: 'Students (enrollment)',
    unit: 'students',
    tip: 'Census-day enrollment in the latest school year.',
    def: [
      'Census-day (early-October) enrollment from CDE, for the latest available school year. District and county rows are K–12 totals.'
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
  growth_pct: TIP['growth-percentile'],
  ppe: TIP['ppe'],
  econ: TIP['econ-share'],
  enrollment: TIP['enrollment']
};
