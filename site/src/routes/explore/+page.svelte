<script>
  import { onMount } from 'svelte';

  let data = $state(null);
  let query = $state('');
  let hovered = $state(null);
  let selected = $state(null);

  onMount(async () => {
    data = await (await fetch('/data/pilot_county.json')).json();
  });

  const W = 860;
  const H = 560;
  const M = { top: 20, right: 20, bottom: 48, left: 58 };
  const X = [-1.1, 1.1]; // adjusted level, student SDs
  const Y = [-0.2, 0.2]; // adjusted growth, student SDs / grade

  const sx = (v) => M.left + ((v - X[0]) / (X[1] - X[0])) * (W - M.left - M.right);
  const sy = (v) => M.top + ((Y[1] - v) / (Y[1] - Y[0])) * (H - M.top - M.bottom);

  let schools = $derived(
    (data?.schools ?? []).filter(
      (s) => s.level_adj_eb != null && s.growth_adj_eb != null && s.school_name
    )
  );
  let matches = $derived(
    query.length < 2
      ? []
      : schools
          .filter((s) => s.school_name.toLowerCase().includes(query.toLowerCase()))
          .slice(0, 8)
  );
  let active = $derived(hovered ?? selected);
</script>

<svelte:head><title>Explore — SchoolFactors</title></svelte:head>

<h1>Sonoma County pilot</h1>
<p class="lede">
  Each dot is a public school, placed by how its students score
  (<strong>horizontal</strong>) and how fast cohorts progress grade-to-grade
  (<strong>vertical</strong>) — both <em>relative to California schools serving
  similar students</em>, shrunken for reliability. The gray cross marks the zone not
  meaningfully different from expectation. Hover or search to identify a school.
</p>

{#if data}
  <div class="search">
    <input placeholder="Find a school…" bind:value={query} aria-label="Find a school" />
    {#if matches.length}
      <ul class="hits">
        {#each matches as m (m.cds)}
          <li>
            <button
              onclick={() => {
                selected = m;
                query = '';
              }}>{m.school_name} <span>{m.district_name}</span></button
            >
          </li>
        {/each}
      </ul>
    {/if}
  </div>

  <svg viewBox="0 0 {W} {H}" role="img" aria-label="Scatter plot of adjusted level versus adjusted growth for Sonoma County schools">
    <!-- indistinguishable band -->
    <rect x={sx(-0.1)} y={M.top} width={sx(0.1) - sx(-0.1)} height={H - M.top - M.bottom} fill="#eee9df" />
    <rect x={M.left} y={sy(0.02)} width={W - M.left - M.right} height={sy(-0.02) - sy(0.02)} fill="#eee9df" />
    <!-- axes -->
    <line x1={M.left} x2={W - M.right} y1={sy(0)} y2={sy(0)} stroke="#c3bcae" />
    <line x1={sx(0)} x2={sx(0)} y1={M.top} y2={H - M.bottom} stroke="#c3bcae" />
    {#each [-1, -0.5, 0.5, 1] as t (t)}
      <text x={sx(t)} y={H - M.bottom + 20} class="tick" text-anchor="middle">{t > 0 ? '+' + t : t}</text>
    {/each}
    {#each [-0.15, -0.05, 0.05, 0.15] as t (t)}
      <text x={M.left - 8} y={sy(t) + 4} class="tick" text-anchor="end">{t > 0 ? '+' + t : t}</text>
    {/each}
    <text x={(M.left + W - M.right) / 2} y={H - 8} class="axis" text-anchor="middle">
      Adjusted level (student SDs vs similar schools) →
    </text>
    <text
      x={16}
      y={(M.top + H - M.bottom) / 2}
      class="axis"
      text-anchor="middle"
      transform="rotate(-90 16 {(M.top + H - M.bottom) / 2})"
    >
      Adjusted growth (SDs per grade) →
    </text>
    <!-- dots -->
    {#each schools as s (s.cds)}
      <circle
        cx={sx(Math.max(X[0], Math.min(X[1], s.level_adj_eb)))}
        cy={sy(Math.max(Y[0], Math.min(Y[1], s.growth_adj_eb)))}
        r={active?.cds === s.cds ? 8 : 5}
        fill={active?.cds === s.cds ? '#b0552f' : '#2a78d6'}
        fill-opacity={active && active.cds !== s.cds ? 0.25 : 0.75}
        stroke="#fcfcfb"
        stroke-width="1.5"
        role="presentation"
        onmouseenter={() => (hovered = s)}
        onmouseleave={() => (hovered = null)}
        onclick={() => (selected = s)}
      />
    {/each}
  </svg>

  {#if active}
    <div class="card">
      <h3>{active.school_name}</h3>
      <p class="dname">{active.district_name} · {active.n_years} test years · {active.total_scores.toLocaleString()} scores</p>
      <div class="stats">
        <div>
          <span class="v">{active.level_adj_eb > 0 ? '+' : ''}{active.level_adj_eb}</span>
          <span class="k">adjusted level ± {(1.96 * active.level_se).toFixed(2)}</span>
        </div>
        <div>
          <span class="v">{active.growth_adj_eb > 0 ? '+' : ''}{active.growth_adj_eb}</span>
          <span class="k">adjusted growth ± {(1.96 * active.growth_se).toFixed(2)}</span>
        </div>
        <div>
          <span class="v">{Math.round(active.share_econ_dis * 100)}%</span>
          <span class="k">economically disadvantaged</span>
        </div>
      </div>
      <p class="note">
        Values in student-level SDs relative to schools with similar student
        populations. Intervals are 95% sampling bands; they do not include
        model-specification uncertainty. Not a quality rating.
      </p>
    </div>
  {/if}

  <details>
    <summary>All {schools.length} schools as a table</summary>
    <table>
      <thead>
        <tr><th>School</th><th>District</th><th>Adj. level</th><th>Adj. growth</th><th>Scores</th></tr>
      </thead>
      <tbody>
        {#each [...schools].sort((a, b) => a.school_name.localeCompare(b.school_name)) as s (s.cds)}
          <tr>
            <td>{s.school_name}</td>
            <td>{s.district_name}</td>
            <td class="num">{s.level_adj_eb}</td>
            <td class="num">{s.growth_adj_eb}</td>
            <td class="num">{s.total_scores.toLocaleString()}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </details>
{:else}
  <p>Loading…</p>
{/if}

<style>
  .lede {
    max-width: 46rem;
    color: #4a453d;
  }
  svg {
    width: 100%;
    height: auto;
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
  }
  circle {
    cursor: pointer;
    transition: r 80ms;
  }
  .tick {
    font-size: 12px;
    fill: #898781;
  }
  .axis {
    font-size: 13px;
    fill: #52514e;
  }
  .search {
    position: relative;
    margin: 0.6rem 0 1rem;
    max-width: 24rem;
  }
  input {
    width: 100%;
    padding: 0.55rem 0.8rem;
    font-size: 1rem;
    border: 1px solid #d8d0c0;
    border-radius: 8px;
    background: #fffdf9;
  }
  .hits {
    position: absolute;
    z-index: 5;
    left: 0;
    right: 0;
    margin: 0.2rem 0 0;
    padding: 0.25rem;
    list-style: none;
    background: #fffdf9;
    border: 1px solid #d8d0c0;
    border-radius: 8px;
    box-shadow: 0 6px 18px rgba(43, 39, 34, 0.12);
  }
  .hits button {
    display: block;
    width: 100%;
    text-align: left;
    padding: 0.4rem 0.6rem;
    border: 0;
    background: none;
    font-size: 0.95rem;
    cursor: pointer;
    border-radius: 6px;
  }
  .hits button:hover {
    background: #f3ede2;
  }
  .hits span {
    color: #898781;
    font-size: 0.85rem;
    margin-left: 0.4rem;
  }
  .card {
    margin-top: 1rem;
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    padding: 1rem 1.2rem;
  }
  .card h3 {
    margin: 0;
  }
  .dname {
    color: #6f6a61;
    margin: 0.15rem 0 0.8rem;
    font-size: 0.92rem;
  }
  .stats {
    display: flex;
    gap: 2rem;
    flex-wrap: wrap;
  }
  .v {
    display: block;
    font-size: 1.5rem;
    font-weight: 700;
    color: #b0552f;
  }
  .k {
    color: #6f6a61;
    font-size: 0.85rem;
  }
  .note {
    color: #898781;
    font-size: 0.85rem;
    margin-bottom: 0;
  }
  details {
    margin-top: 1.5rem;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.92rem;
    margin-top: 0.6rem;
  }
  th,
  td {
    text-align: left;
    padding: 0.35rem 0.5rem;
    border-bottom: 1px solid #eee9df;
  }
  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
</style>
