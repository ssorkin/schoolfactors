# First analysis: level, growth, and demographically-adjusted performance of California schools

*SchoolFactors, August 2026. Reproduce with `sf acquire && sf ingest && sf check && sf analyze`.*

## What we did

From ten years of CAASPP Smarter Balanced research files (2015–2025, excluding the
2020 COVID cancellation and the 2021 participation collapse — statewide participation
was 23.7% that year, see DATA_QUALITY.md), we built a panel of **519,923 school ×
year × grade × subject observations across 10,162 schools**, using each school's
**mean scale score** — never percent-proficient, which distorts trends and gaps
(Ho 2008).

**Standardization.** Each mean is standardized within year × grade × subject against
the state mean, in units of student-level standard deviations. The research files do
not publish score SDs, so we estimate them with a probit identity: across schools,
Φ⁻¹(share meeting standard) is linear in the school mean with slope 1/σ. The method
recovers the published Smarter Balanced cut scores to within a few points (implied
grade-4 ELA cut 2467.6 vs the official 2473; R² ≈ 0.96), which validates both the
σ estimates and the within-school-normal approximation.

**Per-school model (SEDA-style).** For each of the 9,748 schools with ≥6 observations
across ≥3 years, a precision-weighted regression with sampling variance fixed at 1/n
yields three numbers:

| Parameter | Meaning | Between-school SD (τ) |
|---|---|---|
| **Level** | recent standing vs the state (recency-weighted) | 0.62 student SDs |
| **Growth** | within-cohort grade-to-grade progression vs the state | 0.066 SDs/grade |
| **Trend** | change across cohorts over years | 0.035 SDs/year |

**Recency weighting.** The level answers "where is this school *now*", not "where
has it averaged over a decade": each observation's precision weight is decayed with
a half-life of 1.5 years from the school's latest data year, so the level mostly
reflects the last two-to-three test years. The half-life was chosen by holdout —
fitting on 2015–2024 and predicting each school's held-out 2025 mean across ~9,100
schools, RMSE is 0.200 for the decade-average level, 0.168 for a linear-trend
extrapolation, 0.147–0.156 for recency-weighted averages (half-life 1–2y), and
0.143 for a last-year-only estimate. We take the recency-weighted average rather
than last-year-only because it keeps coverage for schools missing the latest year,
keeps small schools' variance machinery intact, and doesn't let one cohort's test
day define a school. Trend extrapolation is worse than no extrapolation — declines
flatten, and the linear forecast overshoots. Growth and trend keep the undecayed
weights: slopes need the full window.

Estimates are empirical-Bayes shrunken for display (small schools pulled toward the
mean), with a reliability gate of 0.70 (SEDA's rule): all schools pass for level,
97% for growth, 95% for trend. OLS versions with standard errors are retained for
any downstream regression use — shrunken estimates are never used as outcomes.

**Ranking rule.** Site percentiles are computed from the *lower bound* of the 95%
band around the shrunken adjusted estimate (posterior sd = √(λV) — using the raw
sampling SE would double-count noise the shrinkage already removed), so an
imprecise high estimate ranks below a precise, slightly lower one. Percentiles are
withheld below 0.70 reliability and from entities with no test data in the latest
year — a recency-weighted level for a school whose data stopped years ago describes
a school that may no longer exist in that form.

**Demographic adjustment (Urban Institute-style).** We regress the OLS level and
growth estimates, precision-weighted, on covariates computed from the CAASPP files
themselves: shares of tested students who are economically disadvantaged, Black,
Asian, Hispanic, White, English learners, students with disabilities, three
parent-education shares, and log school size. The residual is a school's performance
**relative to schools serving similar students** — not a measure of school quality,
and not causal.

## What we found

**The demography gradient is enormous, and adjustment removes it.** Raw school level
correlates **−0.74** with the share of economically disadvantaged students. After
adjustment the correlation is **−0.003** — ≈0 by construction for the linear term —
and the before/after scatter (`figures/adjustment_scatter.png`) is the clearest
picture of how much of a raw ranking is demography: most of it.

**Growth is nearly orthogonal to status.** Adjusted growth correlates **−0.012**
with raw level. This is the falsification test that the LA Times value-added model
failed badly (its teacher effects correlated 0.50 with classroom prior achievement;
Briggs & Domingue 2011). Schools that *score* high and schools where students
*progress* fast are substantially different sets — see `figures/quadrant.png`.

**Sampling noise is not the binding uncertainty — specification is.** With up to nine
years of data per school, 83% of schools are statistically distinguishable from their
demographic expectation at 95% (recency weighting widens the bands relative to a
decade-average level — that is honesty, not loss). But rankings move when the
covariate set changes: Spearman correlation between the economic-only and full
specifications is **0.84** (top-quintile agreement 88.8%). Any school whose
"outperformance" appears and disappears across reasonable specifications should not
be called an outlier. We publish all specifications, per the central lesson of the
LA Times episode.

## What this cannot tell you

- **These are correlations between school averages.** Nothing here says what any
  school *causes*, or what an individual child would experience. School-level
  aggregates cannot separate school effects from family, neighborhood, peer, and
  selection effects (the ecological fallacy is a hard constraint, not a caveat).
- **Adjustment is partial.** Covariates are shares of the tested population; they
  do not capture depth of poverty, wealth, home language detail, or selection into
  schools. Residual "outperformance" still contains unmeasured advantage. Suppressed
  subgroups (n<11) slightly understate small-group shares.
- **2015 subgroup enrollment is broken** (entity-level counts in every subgroup row;
  see known_issues/) — we therefore build covariates from tested counts, not
  enrollment, and never use 2015 subgroup enrollment.
- **Charter and small-school growth estimates are biased upward** by differential
  student mobility (Reardon et al.); stability-rate covariates land when CDE data
  acquisition completes.
- The within-school SD is approximated by the population SD in the precision
  weights; this modestly overstates sampling variance (ICC ≈ 0.2 ⇒ ~10% conservative),
  which makes our "distinguishable" counts, if anything, understatements.

## CDE administrative covariates (added after acquisition completed)

Joining CDE's administrative files gives an independent check and a first look at
non-demographic factors:

- **Cross-source validation.** CAASPP's tested-population economic-disadvantage
  share correlates **+0.984** with CDE's FRPM eligibility rate across 9,678 schools —
  two fully independent pipelines (test-file subgroup counts vs. meal-program
  administrative records) agree almost perfectly.
- **The adjustment is robust to the poverty measure.** Adjusting on CDE's FRPM/UPC
  instead of CAASPP-internal shares reproduces the rankings at Spearman **0.982**
  (top-quintile agreement 96%).
- **Factor correlations, conditional on demographics** (level, student-SD units;
  correlational, not causal): chronic absenteeism **−0.76** per unit (≈ −0.08 SD per
  10 pp), student stability rate **+1.24**, unduplicated-pupil-count share **−1.02**
  (depth of disadvantage carries signal beyond the binary econ-dis share), average
  teacher experience **+0.015 per year**.
- **A caution on "controlling for" attendance and stability**: these are partly
  mechanisms schools can influence, not fixed context. Including them changes the
  question from "does this school outperform schools with similar students?" to
  "…net of attendance and churn?" — rankings shift accordingly (Spearman 0.66 vs the
  economic-only spec). We therefore publish them as a separate analytical lens, not
  as part of the default demographic adjustment.

## Next

Validate our growth parameter against California's official growth model (Dashboard
files still pending CDE's rate limiting); teacher credential/assignment (TAMO) and
spending (ESSA PPE, SACS) factor analyses; district-level subgroup analyses
(school-level subgroup estimates are too imprecise to publish — SEDA's precedent).

## References

Briggs & Domingue (2011), *Due Diligence and the Evaluation of Teachers*, NEPC ·
Chingos (2024), *States' Demographically Adjusted Performance*, Urban Institute ·
Reardon et al., *SEDA v5.0 Technical Documentation* · Kane & Staiger (2002), *JEP* ·
Spiegelhalter (2005), *Statistics in Medicine* · Ho (2008), *Educational Researcher*.
