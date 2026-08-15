<script>
  import SearchBox from '$lib/SearchBox.svelte';
  import PerfList from '$lib/PerfList.svelte';

  let { data } = $props();
  let summary = $derived(data.summary);
  let counties = $derived(data.counties);
  const fmt = (v) => (v == null ? '—' : (v > 0 ? '+' : '') + v.toFixed(2));
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
  <SearchBox />
</section>

<section class="tiles">
  <div class="tile">
    <div class="num">{summary.n_schools_modeled.toLocaleString()}</div>
    <div class="label">schools modeled</div>
  </div>
  <div class="tile">
    <div class="num">{summary.n_districts_modeled.toLocaleString()}</div>
    <div class="label">districts</div>
  </div>
  <div class="tile">
    <div class="num">{summary.n_counties_modeled}</div>
    <div class="label">counties</div>
  </div>
  <div class="tile">
    <div class="num">−0.76 → −0.00</div>
    <div class="label">
      correlation of school scores with student poverty, before → after demographic
      adjustment
    </div>
  </div>
</section>

<section>
  <h2>Counties</h2>
  <p class="note">
    Start statewide and drill down: county → district → school. Every level shows the
    same three numbers — level, growth, trend — raw and adjusted for the students
    served.
  </p>
  <PerfList items={counties} kind="county" childPath="/county" />
  <details>
    <summary>All {counties.length} counties</summary>
    <table>
      <thead>
        <tr><th>County</th><th>Adj. level</th><th>Raw level</th><th>Adj. growth</th><th>Scores</th></tr>
      </thead>
      <tbody>
        {#each counties as c (c.cds)}
          <tr>
            <td><a href="/county/{c.cds}">{c.county}</a></td>
            <td class="tnum">{fmt(c.level_adj_eb)}</td>
            <td class="tnum">{fmt(c.level_eb)}</td>
            <td class="tnum">{fmt(c.growth_adj_eb)}</td>
            <td class="tnum">{c.total_scores?.toLocaleString() ?? '—'}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </details>
</section>

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
  .tiles {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
    margin: 1.6rem 0;
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
  .note {
    color: #6f6a61;
    max-width: 44rem;
  }
  .principles li {
    margin-bottom: 0.8rem;
    max-width: 46rem;
  }
  details {
    margin-top: 0.6rem;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.93rem;
    margin-top: 0.5rem;
  }
  th,
  td {
    text-align: left;
    padding: 0.32rem 0.5rem;
    border-bottom: 1px solid #eee9df;
  }
  .tnum {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
</style>
