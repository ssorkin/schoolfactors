<svelte:head><title>Methodology — SchoolFactors</title></svelte:head>

<h1>How the numbers are made</h1>
<p class="lede">
  Full details, code, and figures live in the
  <a href="https://github.com/ssorkin/schoolfactors/blob/main/analysis/first_analysis.md"
    >open analysis writeup</a
  >. This page is the plain-language version; the <a href="/glossary">glossary</a>
  defines each displayed metric and its calculation rule.
</p>

<h2>1. Scores, standardized carefully</h2>
<p>
  We use each school's <strong>mean scale score</strong> on the CAASPP Smarter Balanced
  tests (2015–2025) — never "percent proficient", which a school can move just by
  nudging students across a cut line. Scores are compared within the same grade,
  subject, and year, in units of student-level standard deviations. We exclude 2020
  (no testing) and 2021 (statewide participation collapsed to 24%).
</p>

<h2>2. Three numbers per school</h2>
<p>
  A precision-weighted model gives each school a <strong>level</strong> (how its
  students score vs the state), a <strong>growth rate</strong> (how much a cohort
  progresses from one grade to the next vs the state), and a <strong>trend</strong>
  (whether results are improving across years). Small schools' estimates are
  shrunk toward the average — a 40-student grade simply tells us less than a
  400-student one — and estimates that stay unreliable after shrinkage are not shown.
</p>
<p>
  The level answers "where is this school <em>now</em>", not "where has it averaged
  over a decade": each year's weight in the level halves for every 1.5 years of age,
  so a school that was strong in 2016 but ordinary today shows an ordinary level. We
  chose that half-life by holdout — fitting on earlier years and predicting each
  school's held-out latest year, the recency-weighted level beat both the all-years
  average and a linear-trend extrapolation. Growth and trend still use the full
  window: slopes need it.
</p>

<h2>3. Comparing schools that serve similar students</h2>
<p>
  Raw score levels correlate <strong>−0.74</strong> with the share of economically
  disadvantaged students — demography, not schooling, dominates raw comparisons. So we
  also report performance <em>relative to schools serving similar students</em>:
  what remains after accounting for the tested population's economic disadvantage,
  race/ethnicity, English-learner and disability shares, parental education, and
  school size. This residual is <strong>not</strong> a measure of school quality —
  it still contains everything our covariates miss.
</p>
<p>
  Where the site shows percentiles, they are computed from the <em>lower bound</em> of
  the 95% band around each shrunken estimate, not the point estimate — an imprecise
  high estimate ranks below a precise, slightly lower one. Percentiles are also
  withheld from entities with no test data in the latest year: a recency-weighted
  level for a school whose data stopped years ago describes a school that may no
  longer exist in that form.
</p>

<h2>4. What we refuse to do</h2>
<ul>
  <li>No single composite rating, and no bare integer rankings.</li>
  <li>No causal claims — these are relationships between school averages.</li>
  <li>
    No school-level subgroup estimates where suppression and small counts make them
    unreliable.
  </li>
  <li>
    No hiding of specification sensitivity: when reasonable modeling choices move a
    school's result, we say so. Rankings agree between our demographic
    specifications at Spearman 0.84–0.98 — good, but far from perfect — and drop to
    0.66 when school-influenced factors like attendance are added. That
    disagreement <em>is</em> the error bar that matters most.
  </li>
</ul>

<h2>Why we're careful: lessons we inherited</h2>
<p>
  The LA Times' 2010 teacher value-added project published quintile labels whose
  ratings flipped for half the teachers under an equally-defensible alternative model
  (Briggs &amp; Domingue, 2011). The Urban Institute's demographically adjusted NAEP
  work and Stanford's SEDA project showed the responsible alternative: precision
  weighting, shrinkage, reliability gates, and published sensitivity. We follow the
  second tradition, and our growth measure passes the falsification test the LA Times
  model failed (correlation with prior achievement: −0.01 here vs their 0.50).
</p>

<style>
  .lede {
    font-size: 1.08rem;
    color: #4a453d;
  }
  h2 {
    margin-top: 2rem;
  }
  p,
  li {
    max-width: 46rem;
  }
</style>
