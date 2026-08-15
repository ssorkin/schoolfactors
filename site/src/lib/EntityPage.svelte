<script>
  import CohortChart from '$lib/CohortChart.svelte';
  import BlendChart from '$lib/BlendChart.svelte';
  import SearchBox from '$lib/SearchBox.svelte';
  import PerfList from '$lib/PerfList.svelte';
  import ResultsTables from '$lib/ResultsTables.svelte';
  import TrendChart from '$lib/TrendChart.svelte';

  let { entity, subItems = null, subKind = 'school', subLabel = '' } = $props();

  let e = $derived(entity.effects ?? {});

  import { browser } from '$app/environment';
  import { replaceState } from '$app/navigation';

  // Comparison overlays: checked schools' trends, fetched on demand and drawn
  // in the chart above. Reset (and restored from the URL) per entity.
  const MAX_OVERLAYS = 4;
  let overlays = $state([]);
  let isOverlaid = $derived((cds) => overlays.some((o) => o.cds === cds));

  async function addOverlay(cds, name = null) {
    if (overlays.some((o) => o.cds === cds) || overlays.length >= MAX_OVERLAYS) return;
    try {
      const resp = await fetch(`/data/schools/${cds}.json`);
      if (!resp.ok) return;
      const j = await resp.json();
      overlays = [
        ...overlays,
        {
          cds,
          name: name ?? j.name,
          rows: j.subgroup_results ?? [],
          scores: j.cohort_scores ?? []
        }
      ];
    } catch {
      /* comparison school payload unavailable — leave unchecked */
    }
  }
  function toggleOverlay(s) {
    if (overlays.some((o) => o.cds === s.cds)) {
      overlays = overlays.filter((o) => o.cds !== s.cds);
    } else {
      addOverlay(s.cds, s.name);
    }
  }

  // ---- URL state: ?s=math&v=group&r=exc&l=facets&g=31.111&c=cds1.cds2 ----
  let chartState = $state(null);
  let chartInitial = $state({});
  let restoredFor = $state(null);

  $effect(() => {
    const cds = entity.cds;
    if (!browser || restoredFor === cds) return;
    restoredFor = cds;
    const q = new URLSearchParams(window.location.search);
    chartInitial = {
      subject: q.get('s') ?? undefined,
      split: q.get('v') ?? undefined,
      metric: q.get('r') === 'exc' ? 'pct_exc' : q.get('r') === 'met' ? 'pct_met' : undefined,
      layout: q.get('l') ?? undefined,
      groups: q.get('g')?.split('.').map(Number).filter(Number.isFinite) ?? []
    };
    overlays = [];
    for (const c of (q.get('c')?.split('.') ?? []).slice(0, MAX_OVERLAYS)) {
      if (/^\d{14}$/.test(c)) addOverlay(c);
    }
  });

  $effect(() => {
    if (!browser || !chartState || restoredFor !== entity.cds) return;
    const q = new URLSearchParams();
    if (chartState.subject !== 'ela') q.set('s', chartState.subject);
    if (chartState.split !== 'overall') q.set('v', chartState.split);
    if (chartState.metric !== 'pct_met') q.set('r', 'exc');
    if (chartState.layout) q.set('l', chartState.layout);
    if (chartState.split === 'group' && chartState.groups?.length) {
      q.set('g', chartState.groups.join('.'));
    }
    if (overlays.length) q.set('c', overlays.map((o) => o.cds).join('.'));
    const qs = q.toString();
    const target = window.location.pathname + (qs ? '?' + qs : '');
    if (target !== window.location.pathname + window.location.search) {
      replaceState(target, {});
    }
  });
  let flaggedSteps = $derived((entity.blend_steps ?? []).filter((s) => s.flag));
  let slopes = $derived(
    [...(entity.cohort_slopes ?? [])].sort((a, b) => b.grad_year - a.grad_year).slice(0, 8)
  );

  const fmt = (v, plus = true) =>
    v == null ? '—' : (plus && v > 0 ? '+' : '') + v.toFixed(2);

  function slopeVerdict(s) {
    if (s.slope - 2 * s.slope_se > 0) return { word: 'gaining on the state', cls: 'up' };
    if (s.slope + 2 * s.slope_se < 0) return { word: 'losing ground', cls: 'down' };
    return { word: 'moving with the state', cls: 'flat' };
  }

  const groupLabels = {
    econ_dis: 'economically disadvantaged',
    el: 'English learners',
    swd: 'students with disabilities',
    black: 'Black',
    asian: 'Asian',
    hispanic: 'Hispanic/Latino',
    white: 'White'
  };
</script>

<SearchBox />

<nav class="crumbs">
  <a href="/">California</a> ›
  {#if entity.kind === 'county'}
    <span>{entity.name}</span>
  {:else}
    {#if entity.county_has_page}
      <a href="/county/{entity.county_cds}">{entity.county} County</a> ›
    {:else}
      <span>{entity.county} County</span> ›
    {/if}
    {#if entity.kind === 'school'}
      {#if entity.district_has_page}
        <a href="/district/{entity.district_cds}">{entity.district}</a> ›
      {:else}
        <span>{entity.district}</span> ›
      {/if}
    {/if}
    <span>{entity.name}</span>
  {/if}
</nav>

<h1>{entity.name}</h1>
<p class="sub">
  {entity.kind === 'school' ? `${entity.district} · ` : ''}{entity.county} County
  {#if e.n_years}· {e.n_years} test years · {e.total_scores?.toLocaleString()} scores{/if}
</p>

<h2>How results are trending</h2>
{#key restoredFor === entity.cds ? entity.cds : 'pending'}
  <TrendChart
    subgroups={entity.subgroup_results ?? []}
    scores={entity.cohort_scores ?? []}
    {overlays}
    initial={chartInitial}
    onstate={(s) => (chartState = s)}
  />
{/key}

{#if entity.neighbors && (entity.neighbors.nearby?.length || entity.neighbors.lookalike?.length)}
  <h2>Compare with</h2>
  <div class="compare">
    {#if entity.neighbors.nearby?.length}
      <div class="cmp-card">
        <h3>Nearby schools</h3>
        <ul>
          {#each entity.neighbors.nearby.slice(0, 5) as s (s.cds)}
            <li>
              <input
                type="checkbox"
                title="Overlay on the chart above"
                checked={isOverlaid(s.cds)}
                onchange={() => toggleOverlay(s)}
              />
              <span class="cmp-name">
                <a href="/school/{s.cds}">{s.name}</a>
                {#if s.district !== entity.district}<span class="cmp-sub">{s.district}</span>{/if}
              </span>
              <span class="cmp-vals">
                <span class="cmp-meta">{s.miles} mi</span>
                <span class="cmp-adj" class:pos={s.level_adj_eb > 0} class:neg={s.level_adj_eb < 0}>
                  {s.level_adj_eb == null ? '—' : fmt(s.level_adj_eb)}
                </span>
              </span>
            </li>
          {/each}
        </ul>
      </div>
    {/if}
    {#if entity.neighbors.lookalike?.length}
      <div class="cmp-card">
        <h3>Schools serving similar students</h3>
        <ul>
          {#each entity.neighbors.lookalike.slice(0, 5) as s (s.cds)}
            <li>
              <input
                type="checkbox"
                title="Overlay on the chart above"
                checked={isOverlaid(s.cds)}
                onchange={() => toggleOverlay(s)}
              />
              <span class="cmp-name">
                <a href="/school/{s.cds}">{s.name}</a>
                <span class="cmp-sub">{s.district}</span>
              </span>
              <span class="cmp-vals">
                <span class="cmp-meta">
                  {s.share_econ_dis == null ? '' : Math.round(s.share_econ_dis * 100) + '% econ dis.'}
                </span>
                <span class="cmp-adj" class:pos={s.level_adj_eb > 0} class:neg={s.level_adj_eb < 0}>
                  {s.level_adj_eb == null ? '—' : fmt(s.level_adj_eb)}
                </span>
              </span>
            </li>
          {/each}
        </ul>
      </div>
    {/if}
  </div>
  <p class="note">
    Check a school to overlay its trend (dashed) on the chart above — up to four at
    a time. Lookalikes are matched statewide on the demographics of tested students
    (poverty, language, race/ethnicity, disabilities, parent education, size), same
    school level. The number on the right is each school's demographically-adjusted
    level.
  </p>
{/if}

{#if e.level_eb != null}
  <h2>The three modeled numbers</h2>
  <section class="tiles">
    <div class="tile">
      <div class="num">{fmt(e.level_adj_eb)}</div>
      <div class="label">
        adjusted level — score level vs {entity.kind === 'school' ? 'schools' : 'districts'}
        serving similar students (student SDs)
      </div>
    </div>
    <div class="tile">
      <div class="num">{fmt(e.level_eb)} <span class="ci">± {(1.96 * (e.level_se ?? 0)).toFixed(2)}</span></div>
      <div class="label">raw level vs state average</div>
    </div>
    <div class="tile">
      {#if e.growth_eb != null}
        <div class="num">{fmt(e.growth_eb)} <span class="ci">± {(1.96 * (e.growth_se ?? 0)).toFixed(2)}</span></div>
        <div class="label">growth per grade — how cohorts progress vs the state</div>
      {:else}
        <div class="num">n/a</div>
        <div class="label">
          growth needs results in multiple grades; this {entity.kind} tests one grade
        </div>
      {/if}
    </div>
    <div class="tile">
      <div class="num">{fmt(e.trend_eb)} <span class="ci">± {(1.96 * (e.trend_se ?? 0)).toFixed(2)}</span></div>
      <div class="label">trend per year — are successive cohorts scoring higher?</div>
    </div>
  </section>
{/if}

<h2>Cohorts</h2>
<CohortChart scores={entity.cohort_scores ?? []} />

{#if slopes.length}
  <h3>Recent graduating classes</h3>
  <ul class="cohort-list">
    {#each slopes as s (s.grad_year)}
      {@const v = slopeVerdict(s)}
      <li class={v.cls}>
        <strong>Class of {s.grad_year}</strong> — {v.word}
        ({fmt(s.slope)} ± {(2 * s.slope_se).toFixed(2)} SD/grade over {s.n_points} points)
      </li>
    {/each}
  </ul>
{/if}

{#if flaggedSteps.length}
  <h3>Cohort composition changes worth knowing about</h3>
  <p class="note">
    Following a cohort across grades only approximates following the same students.
    These grade-to-grade steps had population shifts larger than sampling noise —
    score changes across them may reflect who moved in or out, not instruction.
  </p>
  <ul class="flags">
    {#each flaggedSteps as s (s.grad_year + '-' + s.from_grade)}
      <li>
        <strong>Class of {s.grad_year}</strong>, grade {s.from_grade} ({s.year}) →
        {s.from_grade + 1} ({s.year + 1}):
        {#if Math.abs(s.n_change_frac) > 0.2}
          tested group {s.n_change_frac > 0 ? 'grew' : 'shrank'}
          {Math.abs(Math.round(s.n_change_frac * 100))}%{Object.keys(s.shifts).length ? ';' : '.'}
        {/if}
        {#each Object.entries(s.shifts) as [k, d], i (k)}
          {i > 0 ? ', ' : ''}% {groupLabels[k]} shifted {d > 0 ? '+' : ''}{Math.round(d * 100)}pp
        {/each}
        {#if s.expected_dz_from_blend && Math.abs(s.expected_dz_from_blend) >= 0.02}
          <span class="exp">
            (mix change alone predicts ≈ {fmt(s.expected_dz_from_blend)} SD)
          </span>
        {/if}
      </li>
    {/each}
  </ul>
{/if}

<h2>Who takes the tests here</h2>
<BlendChart blend={entity.blend ?? []} />

{#if subItems?.length}
  <h2>{subLabel}</h2>
  <PerfList items={subItems} kind={subKind} childPath={'/' + subKind} />
  <details>
    <summary>All {subItems.length} {subKind}s</summary>
    <table>
      <thead>
        <tr>
          <th style="text-transform: capitalize">{subKind}</th>
          <th>Adj. level</th><th>Raw level</th><th>Adj. growth</th><th>Scores</th>
        </tr>
      </thead>
      <tbody>
        {#each subItems as s (s.cds)}
          <tr>
            <td><a href="/{subKind}/{s.cds}">{s.name}</a></td>
            <td class="tnum">{s.level_adj_eb == null ? '—' : fmt(s.level_adj_eb)}</td>
            <td class="tnum">{s.level_eb == null ? '—' : fmt(s.level_eb)}</td>
            <td class="tnum">{s.growth_adj_eb == null ? '—' : fmt(s.growth_adj_eb)}</td>
            <td class="tnum">{s.total_scores == null ? '—' : s.total_scores.toLocaleString()}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </details>
{/if}

<h2>The underlying numbers</h2>
<ResultsTables scores={entity.cohort_scores ?? []} subgroups={entity.subgroup_results ?? []} />

<p class="caveat">
  These are relationships between {entity.kind} averages on one set of tests — not
  measures of quality, and not causal. Intervals are 95% sampling bands and exclude
  model-specification uncertainty. <a href="/methodology">How these numbers are made.</a>
</p>

<style>
  .crumbs {
    font-size: 0.9rem;
    color: #898781;
    margin-bottom: 0.4rem;
  }
  h1 {
    margin: 0.2rem 0 0.2rem;
  }
  .sub {
    color: #6f6a61;
    margin-top: 0;
  }
  :global(main) h2 {
    margin: 1.8rem 0 0.6rem;
  }
  .tiles {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 0.7rem;
    margin: 0.4rem 0 1rem;
  }
  .tile {
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    padding: 0.7rem 0.9rem;
  }
  .num {
    font-size: 1.35rem;
    font-weight: 700;
    color: #b0552f;
  }
  .ci {
    font-size: 0.95rem;
    font-weight: 500;
    color: #898781;
  }
  .label {
    color: #6f6a61;
    font-size: 0.87rem;
  }
  .cohort-list {
    list-style: none;
    padding: 0;
  }
  .cohort-list li {
    padding: 0.28rem 0;
    border-bottom: 1px solid #f0ead9;
    max-width: 46rem;
  }
  .cohort-list li.up strong {
    color: #006300;
  }
  .cohort-list li.down strong {
    color: #d03b3b;
  }
  .flags li {
    max-width: 46rem;
    margin-bottom: 0.5rem;
  }
  .exp {
    color: #898781;
  }
  .note {
    color: #6f6a61;
    max-width: 46rem;
    font-size: 0.93rem;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.93rem;
  }
  th,
  td {
    text-align: left;
    padding: 0.35rem 0.5rem;
    border-bottom: 1px solid #eee9df;
  }
  .tnum {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  .caveat {
    margin-top: 2rem;
    color: #898781;
    font-size: 0.88rem;
    max-width: 46rem;
  }
  .compare {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 1rem;
  }
  .cmp-card {
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    padding: 0.7rem 1rem;
  }
  .cmp-card h3 {
    margin: 0.2rem 0 0.4rem;
    font-size: 1rem;
  }
  .cmp-card ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .cmp-card li {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 0.6rem;
    padding: 0.3rem 0;
    border-bottom: 1px solid #f0ead9;
    font-size: 0.92rem;
  }
  .cmp-card input[type='checkbox'] {
    accent-color: #2a78d6;
    flex-shrink: 0;
    position: relative;
    top: 2px;
    cursor: pointer;
  }
  .cmp-name {
    flex: 1;
    min-width: 0;
  }
  .cmp-card li:last-child {
    border-bottom: none;
  }
  .cmp-sub {
    display: block;
    color: #898781;
    font-size: 0.78rem;
  }
  .cmp-vals {
    display: flex;
    gap: 0.7rem;
    align-items: baseline;
    flex-shrink: 0;
  }
  .cmp-meta {
    color: #898781;
    font-size: 0.82rem;
  }
  .cmp-adj {
    font-variant-numeric: tabular-nums;
    font-weight: 650;
  }
  .cmp-adj.pos {
    color: #006300;
  }
  .cmp-adj.neg {
    color: #d03b3b;
  }
</style>
