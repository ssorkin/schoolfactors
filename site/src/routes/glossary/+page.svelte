<script>
  import { GLOSSARY } from '$lib/glossary.js';
</script>

<svelte:head><title>Glossary — SchoolFactors</title></svelte:head>

<h1>Glossary</h1>
<p class="lede">
  Every metric on this site, what it measures, and how it’s calculated. Hovering a
  column header in the <a href="/">main table</a> shows the short version; the
  <a href="/methodology">methodology page</a> explains why the numbers are made this
  way.
</p>

<div class="example">
  <h2>Reading the three model numbers together</h2>
  <p>
    <strong>Level</strong>, <strong>Growth</strong>, and <strong>Trend</strong> answer
    three different questions, all relative to the state: where do students score
    (level), does a class gain ground as it moves up the grades (growth), and are
    successive classes scoring higher than the ones before (trend)?
  </p>
  <p>
    A concrete example: Los Angeles Unified’s Met+ line rises steadily — but so does
    the state’s. Its level is about −0.2 (students score below the state average), its
    trend is about +0.02 SD/year (each entering class stands slightly higher against
    the state than the last — roughly a quarter SD of gap closed over the decade), and
    its growth is ≈0 (each class then holds that standing as it moves up the grades).
    All three are true at once. A rising raw line with growth ≈ 0 is not a
    contradiction — they measure different things against different baselines.
  </p>
</div>

<dl>
  {#each GLOSSARY as g (g.id)}
    <div class="entry" id={g.id}>
      <dt>
        <a class="anchor" href="#{g.id}">{g.term}</a>
        {#if g.unit}<span class="unit">{g.unit}</span>{/if}
      </dt>
      <dd>
        {#each g.def as para, i (i)}
          <p>{para}</p>
        {/each}
      </dd>
    </div>
  {/each}
</dl>

<h2>Rules behind every number</h2>
<ul class="rules">
  <li>
    <strong>Percentages are never averaged.</strong> Counts are reconstructed
    (percent × n), combined, and re-divided.
  </li>
  <li>
    <strong>Student groups are never summed.</strong> CAASPP groups overlap; totals
    always come from the "All Students" rows, filtered to non-duplicating aggregate
    levels.
  </li>
  <li>
    <strong>Suppressed values stay missing.</strong> Cells under 11 students are never
    coerced to zero.
  </li>
  <li>
    <strong>2020 and 2021 are excluded.</strong> No testing in 2020; 24% statewide
    participation in 2021.
  </li>
  <li>
    <strong>Mean scale score is primary.</strong> Met+ rates are shown for
    familiarity, but the models run on mean scale scores.
  </li>
  <li>
    <strong>Correlations, not causes.</strong> Adjusted numbers compare schools
    serving similar students; they are not quality ratings, and sorting is not
    ranking.
  </li>
  <li>
    <strong>Everything is reproducible.</strong> Data problems are documented, not
    silently patched; provenance (source URLs, versions, checksums) is recorded for
    every file.
  </li>
</ul>

<style>
  .lede {
    font-size: 1.08rem;
    color: #4a453d;
    max-width: 46rem;
  }
  .example {
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    background: #fffdf9;
    padding: 0.2rem 1.1rem 0.4rem;
    max-width: 46rem;
    margin: 1.2rem 0 1.8rem;
  }
  .example h2 {
    font-size: 1.05rem;
    margin: 0.8rem 0 0.2rem;
  }
  dl {
    margin: 0;
  }
  .entry {
    max-width: 46rem;
    padding: 0.9rem 0 0.2rem;
    border-top: 1px solid #f0ead9;
  }
  dt {
    font-weight: 700;
    font-size: 1.02rem;
  }
  dt .anchor {
    color: inherit;
    text-decoration: none;
  }
  dt .anchor:hover {
    color: #b0552f;
  }
  .entry:target dt .anchor {
    color: #b0552f;
  }
  .unit {
    font-weight: 400;
    font-size: 0.8rem;
    color: #898781;
    margin-left: 0.5rem;
  }
  dd {
    margin: 0.2rem 0 0.6rem;
  }
  dd p {
    margin: 0.35rem 0;
    color: #4a453d;
  }
  h2 {
    margin-top: 2rem;
  }
  .rules {
    max-width: 46rem;
  }
  .rules li {
    margin: 0.4rem 0;
  }
</style>
