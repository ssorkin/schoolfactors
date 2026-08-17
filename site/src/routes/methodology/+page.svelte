<script>
  import { onMount } from 'svelte';

  const sections = [
    { id: 'scores', label: 'Standardized scores' },
    { id: 'three-numbers', label: 'Three numbers per school' },
    { id: 'similar-students', label: 'Similar students' },
    { id: 'overlapping-groups', label: 'Groups overlap' },
    { id: 'what-we-tried', label: 'What we have tried' },
    { id: 'refuse', label: 'What we refuse to do' },
    { id: 'lessons', label: 'Lessons we inherited' },
  ];
  let active = $state(sections[0].id);

  onMount(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) if (e.isIntersecting) active = e.target.id;
      },
      { rootMargin: '0px 0px -75% 0px' }
    );
    for (const s of sections) {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  });
</script>

<svelte:head><title>Methodology — SchoolFactors</title></svelte:head>

<div class="layout">
  <nav class="toc" aria-label="Section navigation">
    {#each sections as s}
      <a href="#{s.id}" class:active={active === s.id}>{s.label}</a>
    {/each}
  </nav>

  <article>
    <h1>How the numbers are made</h1>
    <p class="lede">
      Full details, code, and figures live in the
      <a href="https://github.com/ssorkin/schoolfactors/blob/main/analysis/first_analysis.md"
        >open analysis writeup</a
      >. This page is the plain-language version; the <a href="/glossary">glossary</a>
      defines each displayed metric and its calculation rule.
    </p>

    <h2 id="scores">1. Scores, standardized carefully</h2>
    <p>
      We use each school's <strong>mean scale score</strong> on the CAASPP Smarter Balanced
      tests (2015–2025) — never "percent proficient", which a school can move just by
      nudging students across a cut line. Scores are compared within the same grade,
      subject, and year, in units of student-level standard deviations. We exclude 2020
      (no testing) and 2021 (statewide participation collapsed to 24%).
    </p>

    <h2 id="three-numbers">2. Three numbers per school</h2>
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

    <h2 id="similar-students">3. Comparing schools that serve similar students</h2>
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

    <h2 id="overlapping-groups">4. Students belong to many groups at once</h2>
    <p>
      The adjustment above is built from <em>separate</em> group shares — the share of
      tested students who are economically disadvantaged, the share who are Black, and
      so on. But students belong to several groups at once, and the groups don't simply
      add: in the state's published cross-tabulations, the score gap associated with
      economic disadvantage is <strong>−0.48</strong> student SDs among White students
      but <strong>−0.34</strong> among Black students, measured within the same schools.
      An adjustment that treated "economically disadvantaged" and "Black" as
      independent, stackable discounts would get that combination wrong.
    </p>
    <p>
      We measured how much this matters for school-level comparisons, and the answer is:
      very little. Across schools, the share of students in an intersection (say,
      economically disadvantaged <em>and</em> Black) is almost perfectly predicted by
      the two separate shares (correlation 0.995), so intersections carry almost no
      information the separate shares don't already provide. Feeding the true
      intersection shares into the adjustment shifts a typical school's expected level
      by about 0.001 student SDs — two orders of magnitude smaller than the
      school-to-school differences the site reports — and rankings agree with the
      published ones at Spearman 0.96.
    </p>

    <h2 id="what-we-tried">5. What we have tried</h2>
    <p>
      Because "did the adjustment attribute correctly?" can't be answered by assumption,
      we test alternative models against held-out data and publish how much rankings
      move. So far:
    </p>
    <ul>
      <li>
        <strong>True intersection shares</strong> (the state's ethnicity ×
        economic-status cross-tabs): almost no change, for the reason above — and these
        cells are the worst-measured inputs we have, since privacy suppression hides
        nearly half the tested weight for the smaller intersections.
      </li>
      <li>
        <strong>A full interaction surface</strong> (every pairwise product of the ten
        shares, regularized): predicts held-out school levels genuinely better
        (residual spread 0.29 vs 0.32 student SDs), driven mostly by parental-education
        × ethnicity and parental-education × poverty combinations — the intersections
        the state does <em>not</em> publish, surfacing as curvature. Rankings move at
        Spearman 0.89 vs the published adjustment, within the specification-sensitivity
        band we already disclose.
      </li>
      <li>
        <strong>Factor analysis</strong> (compressing the ten shares into a few latent
        dimensions before adjusting): predicted held-out results <em>worse</em> than
        the simple model. The information lives in specific group combinations, not in
        one general "disadvantage" dimension.
      </li>
    </ul>
    <p>
      We have kept the simple additive adjustment as the default, and we treat the gap
      between it and the interaction surface as specification uncertainty — part of the
      error bar, disclosed rather than hidden. The reason we don't just switch to the
      better-predicting model: a more flexible surface predicts better partly because it
      can absorb real differences between schools that happen to pattern with
      demographics, and better prediction is not automatically a fairer comparison. The
      candidate replacement — a model fit jointly to all of the state's published group
      means, with explicit interactions and suppression-aware handling of missing cells
      — is on our roadmap in the
      <a
        href="https://github.com/ssorkin/schoolfactors/blob/main/analysis/first_analysis.md"
        >analysis writeup</a
      >.
    </p>

    <h2 id="refuse">6. What we refuse to do</h2>
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

    <h2 id="lessons">Why we're careful: lessons we inherited</h2>
    <p>
      The LA Times' 2010 teacher value-added project published quintile labels whose
      ratings flipped for half the teachers under an equally-defensible alternative model
      (Briggs &amp; Domingue, 2011). The Urban Institute's demographically adjusted NAEP
      work and Stanford's SEDA project showed the responsible alternative: precision
      weighting, shrinkage, reliability gates, and published sensitivity. We follow the
      second tradition, and our growth measure passes the falsification test the LA Times
      model failed (correlation with prior achievement: −0.01 here vs their 0.50).
    </p>
  </article>
</div>

<style>
  .layout {
    display: grid;
    grid-template-columns: 10.5rem minmax(0, 1fr);
    gap: 2.25rem;
    align-items: start;
  }
  .toc {
    position: sticky;
    top: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    padding: 1.4rem 0;
    font-size: 0.85rem;
  }
  .toc a {
    color: #6f6a61;
    text-decoration: none;
    padding: 0.1rem 0 0.1rem 0.7rem;
    border-left: 2px solid #e8e1d5;
    line-height: 1.35;
  }
  .toc a:hover {
    color: #b0552f;
  }
  .toc a.active {
    color: #b0552f;
    border-left-color: #b0552f;
    font-weight: 600;
  }
  @media (max-width: 760px) {
    .layout {
      display: block;
    }
    .toc {
      display: none;
    }
  }
  .lede {
    font-size: 1.08rem;
    color: #4a453d;
  }
  h2 {
    margin-top: 2rem;
    scroll-margin-top: 1rem;
  }
  p,
  li {
    max-width: 46rem;
  }
</style>
