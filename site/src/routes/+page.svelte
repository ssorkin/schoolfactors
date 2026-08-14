<script>
  import { onMount } from 'svelte';
  let summary = $state(null);
  onMount(async () => {
    summary = await (await fetch('/data/summary.json')).json();
  });
</script>

<svelte:head><title>SchoolFactors — honest statistics about California schools</title></svelte:head>

<section class="hero">
  <h1>Public schools, public data,<br />honest statistics.</h1>
  <p class="lede">
    SchoolFactors gathers all the public data we can find about California's public
    schools — test scores, demographics, staffing, spending — and analyzes what
    actually travels with strong and improving results. Everything is open source,
    every transform is documented, and every finding comes with its uncertainty
    attached.
  </p>
  <p class="cta"><a href="/explore">Explore the pilot county →</a></p>
</section>

{#if summary}
  <section class="tiles">
    <div class="tile">
      <div class="num">{summary.n_schools_modeled.toLocaleString()}</div>
      <div class="label">schools modeled across {summary.years.length} test years</div>
    </div>
    <div class="tile">
      <div class="num">−0.76 → −0.00</div>
      <div class="label">
        correlation of school scores with student poverty, before → after demographic
        adjustment
      </div>
    </div>
    <div class="tile">
      <div class="num">+0.01</div>
      <div class="label">
        correlation of our <em>growth</em> measure with raw score levels — growth and
        status are different questions
      </div>
    </div>
  </section>
{/if}

<section>
  <h2>What makes this site different</h2>
  <ul class="principles">
    <li>
      <strong>Correlations, not causes.</strong> School-level data cannot say what a
      school <em>causes</em> — only how its students' results compare with schools
      serving similar students. Our language reflects that everywhere.
    </li>
    <li>
      <strong>Error margins always.</strong> Small schools are noisy by construction.
      We shrink estimates accordingly, show intervals, and say "not distinguishable
      from average" when that's the honest answer — no bare rankings.
    </li>
    <li>
      <strong>Data problems in the open.</strong> Official files contain real
      inconsistencies. We detect them with automated checks and publish them —
      <a href="/data">see the data-quality report</a> — rather than silently patching.
    </li>
    <li>
      <strong>Reproducible to the byte.</strong> The
      <a href="https://github.com/ssorkin/schoolfactors">pipeline</a> records the
      exact source URL and checksum of every file behind every number.
    </li>
  </ul>
</section>

<style>
  .hero h1 {
    font-size: 2.3rem;
    margin: 1rem 0 0.6rem;
  }
  .lede {
    font-size: 1.12rem;
    max-width: 44rem;
    color: #4a453d;
  }
  .cta {
    font-size: 1.05rem;
    font-weight: 600;
  }
  .tiles {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem;
    margin: 2rem 0;
  }
  .tile {
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    padding: 1.1rem 1.2rem;
  }
  .num {
    font-size: 1.7rem;
    font-weight: 700;
    color: #b0552f;
  }
  .label {
    color: #6f6a61;
    font-size: 0.92rem;
  }
  .principles li {
    margin-bottom: 0.8rem;
    max-width: 46rem;
  }
</style>
