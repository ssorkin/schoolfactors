<script>
  /**
   * Symmetric comparison builder: schools stand side by side as equals — no
   * school is the benchmark and none are subordinate. Each is measured
   * against ITS OWN model expectation and expected-alike band, so a
   * high-poverty school at the state average and a magnet well above it can
   * be read fairly in one table. Shareable via ?s=cds.cds.cds.
   */
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { replaceState } from '$app/navigation';
  import SearchBox from '$lib/SearchBox.svelte';
  import CsvButton from '$lib/CsvButton.svelte';
  import { dataUrl } from '$lib/data.js';

  const MAX = 6;
  let schools = $state([]);

  async function add(cds) {
    if (schools.some((s) => s.cds === cds) || schools.length >= MAX) return;
    try {
      const r = await fetch(dataUrl(`/data/schools/${cds}.json`));
      if (r.ok) {
        const j = await r.json();
        schools = [...schools, j];
      }
    } catch {
      /* unavailable school stays absent */
    }
  }

  // The URL-writing effect must stay silent until the ?s= list has been
  // fully restored — otherwise its first run (schools still empty, fetches
  // in flight) rewrites the permalink to a bare /compare. Sequential awaits
  // also keep column order matching the shared URL.
  let restored = $state(false);
  onMount(async () => {
    const q = new URLSearchParams(window.location.search);
    const want = (q.get('s') ?? '')
      .split('.')
      .filter((c) => /^\d{14}$/.test(c))
      .slice(0, MAX);
    for (const c of want) {
      await add(c);
    }
    restored = true;
  });

  $effect(() => {
    if (!browser || !restored) return;
    const qs = schools.length ? '?s=' + schools.map((s) => s.cds).join('.') : '';
    const target = window.location.pathname + qs;
    if (target !== window.location.pathname + window.location.search) {
      replaceState(target, {});
    }
  });

  const fmt2 = (v) => (v == null ? '—' : (v > 0 ? '+' : '') + v.toFixed(2));
  const CAT = { gaining: '▲ gaining', holding: '· holding', slipping: '▼ slipping' };
  const band = (s, key) => s.vs_similar?.rows?.find((r) => r.g === 1)?.[key];

  const ROWS = [
    { label: 'District', f: (s) => s.district ?? '—' },
    { label: 'Students (census)', f: (s) => s.enrollment?.toLocaleString() ?? '—' },
    {
      label: 'Econ. disadvantaged (tested)',
      f: (s) =>
        s.effects?.share_econ_dis == null
          ? '—'
          : Math.round(s.effects.share_econ_dis * 100) + '%'
    },
    { label: '$ per pupil', f: (s) => (s.ppe == null ? '—' : '$' + s.ppe.toLocaleString()) },
    { label: 'ELA met+ (latest)', f: (s) => (s.pass_ela == null ? '—' : s.pass_ela + '%') },
    { label: 'Math met+ (latest)', f: (s) => (s.pass_math == null ? '—' : s.pass_math + '%') },
    { label: 'Raw level (SDs vs state)', f: (s) => fmt2(s.effects?.level_eb) },
    {
      label: 'Expected level, given students served',
      f: (s) =>
        s.effects?.level_eb == null || s.effects?.level_adj_eb == null
          ? '—'
          : fmt2(s.effects.level_eb - s.effects.level_adj_eb)
    },
    {
      label: 'Performance vs expectation',
      f: (s) => fmt2(s.effects?.level_adj_eb),
      cls: (s) =>
        s.effects?.level_adj_eb > 0 ? 'pos' : s.effects?.level_adj_eb < 0 ? 'neg' : ''
    },
    { label: 'Similar Schools %ile', f: (s) => s.adj_pct ?? '—' },
    {
      label: 'Cohort trajectory',
      f: (s) => CAT[s.growth_cat] ?? '—',
      cls: (s) =>
        s.growth_cat === 'gaining' ? 'pos' : s.growth_cat === 'slipping' ? 'neg' : ''
    },
    {
      label: 'Met+ vs its own expected-alike band',
      f: (s) =>
        band(s, 'met') != null && band(s, 'p_met') != null
          ? `${Math.round(band(s, 'met'))}% vs ${Math.round(band(s, 'p_met'))}%`
          : '—'
    },
    {
      label: 'Exceeded vs its band',
      f: (s) =>
        band(s, 'exc') != null && band(s, 'p_exc') != null
          ? `${Math.round(band(s, 'exc'))}% vs ${Math.round(band(s, 'p_exc'))}%`
          : '—'
    }
  ];

  // ---- Small multiples: Met+ by year per school, SHARED 0-100 scale so
  // levels and slopes compare across panels; lines break at the COVID gap.
  const CW = 280;
  const CH = 150;
  const CM = { l: 30, r: 10, t: 10, b: 22 };
  const Y0 = 2015;
  const Y1 = 2025;
  const CX = (y) => CM.l + ((y - Y0) / (Y1 - Y0)) * (CW - CM.l - CM.r);
  const CY = (v) => CM.t + ((100 - v) / 100) * (CH - CM.t - CM.b);

  function metSeries(s, subject) {
    const pts = [];
    for (const r of s.subgroup_results ?? []) {
      if (r.group === 1 && r.subject === subject && r.pct_met != null) {
        pts.push({ year: r.year, v: r.pct_met });
      }
    }
    pts.sort((a, b) => a.year - b.year);
    const runs = [[]];
    for (const p of pts) {
      const cur = runs[runs.length - 1];
      if (cur.length && p.year - cur[cur.length - 1].year > 1) runs.push([p]);
      else cur.push(p);
    }
    return { pts, runs: runs.filter((r) => r.length > 1) };
  }
</script>

<svelte:head>
  <title>Compare schools side by side — SchoolFactors</title>
  <meta
    name="description"
    content="A symmetric school comparison: each school measured against its own model expectation and expected-alike band — no school is the benchmark."
  />
</svelte:head>

<h1>Compare schools</h1>
<p class="lede">
  Side by side as equals: each school is measured against <em>its own</em>
  expectation given the students it serves — no school here is the benchmark.
  A high-poverty school at the state average and a magnet well above it can
  both be exceptional, each against its own bar.
</p>

<div class="addbox">
  <SearchBox
    placeholder="Add a school to the comparison…"
    kinds={['school']}
    onselect={(it) => add(it.cds)}
  />
</div>

{#if schools.length}
  <div class="tablecard">
    <div class="tabletools">
      <span>{schools.length} of {MAX} schools</span>
      <CsvButton
        filename="schoolfactors comparison.csv"
        build={() => ({
          headers: ['Metric', ...schools.map((s) => s.name)],
          rows: ROWS.map((r) => [r.label, ...schools.map((s) => r.f(s))])
        })}
      />
    </div>
    <div class="tablewrap">
      <table>
        <thead>
          <tr>
            <th class="metric"></th>
            {#each schools as s (s.cds)}
              <th>
                <a href="/school/{s.cds}">{s.name}</a>
                <button
                  class="rm"
                  title="Remove from comparison"
                  onclick={() => (schools = schools.filter((x) => x.cds !== s.cds))}
                  >×</button
                >
              </th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each ROWS as r (r.label)}
            <tr>
              <td class="metric">{r.label}</td>
              {#each schools as s (s.cds)}
                <td class="val {r.cls ? r.cls(s) : ''}">{r.f(s)}</td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>
  <h2>Met+ by year</h2>
  <p class="chartlegend">
    <span class="sw ela"></span> ELA · <span class="sw math"></span> Math — % meeting
    or exceeding the standard, all panels on the same 0–100% scale. 2020–21 gap:
    no comparable testing.
  </p>
  <div class="panels">
    {#each schools as s (s.cds)}
      {@const ela = metSeries(s, 'ela')}
      {@const math = metSeries(s, 'math')}
      <figure class="panel">
        <figcaption><a href="/school/{s.cds}">{s.name}</a></figcaption>
        {#if ela.pts.length || math.pts.length}
          <svg viewBox="0 0 {CW} {CH}" role="img" aria-label="Met+ by year for {s.name}">
            {#each [0, 50, 100] as t (t)}
              <line x1={CM.l} x2={CW - CM.r} y1={CY(t)} y2={CY(t)} class="grid" />
              <text x={CM.l - 5} y={CY(t) + 3.5} class="tick" text-anchor="end">{t}</text>
            {/each}
            {#each [2015, 2019, 2022, 2025] as y (y)}
              <text x={CX(y)} y={CH - 6} class="tick" text-anchor="middle">{y}</text>
            {/each}
            {#each [['ela', ela], ['math', math]] as [cls, ser] (cls)}
              {#each ser.runs as run, ri (ri)}
                <polyline
                  fill="none"
                  class="line {cls}"
                  points={run.map((p) => `${CX(p.year).toFixed(1)},${CY(p.v).toFixed(1)}`).join(' ')}
                />
              {/each}
              {#each ser.pts as p (cls + p.year)}
                <circle cx={CX(p.year)} cy={CY(p.v)} r="2.2" class="dot {cls}">
                  <title>{p.year} {cls.toUpperCase()}: {p.v.toFixed(0)}% met+</title>
                </circle>
              {/each}
            {/each}
          </svg>
        {:else}
          <p class="note">No published results.</p>
        {/if}
      </figure>
    {/each}
  </div>

  <p class="note">
    "Expected level" is the demographic adjustment model's prediction from the
    students each school serves (poverty, language, race/ethnicity, disability,
    parent education, size); "performance vs expectation" is what remains, and
    the percentile ranks it statewide among comparable school types. "Its band"
    is the pool of schools the model expects to score alike. These are
    correlations between school averages — not measures of quality, and not
    causal. <a href="/methodology">How these numbers are made.</a>
  </p>
{:else}
  <p class="note">
    Search above to add up to {MAX} schools — or open a comparison from any
    school page's "Compare with" section.
  </p>
{/if}

<style>
  h1 {
    margin: 0.8rem 0 0.3rem;
  }
  .lede {
    font-size: 1.05rem;
    color: #4a453d;
    max-width: 46rem;
  }
  .addbox {
    max-width: 28rem;
    margin-bottom: 0.8rem;
  }
  .tablecard {
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    background: #fffdf9;
    overflow: hidden;
  }
  .tabletools {
    display: flex;
    justify-content: flex-end;
    align-items: baseline;
    gap: 0.9rem;
    padding: 0.3rem 0.8rem;
    background: #f6f1e7;
    border-bottom: 1px solid #e8e1d5;
    font-size: 0.82rem;
    color: #898781;
  }
  .tablewrap {
    overflow-x: auto;
  }
  table {
    border-collapse: collapse;
    font-size: 0.9rem;
    min-width: 100%;
  }
  th,
  td {
    padding: 0.45rem 0.7rem;
    border-bottom: 1px solid #f0ead9;
    text-align: left;
    vertical-align: top;
  }
  thead th {
    background: #f6f1e7;
    border-bottom: 1px solid #e8e1d5;
    min-width: 11rem;
  }
  thead th a {
    font-weight: 650;
    text-decoration: none;
  }
  thead th a:hover {
    text-decoration: underline;
  }
  .rm {
    border: none;
    background: none;
    color: #898781;
    cursor: pointer;
    font-size: 1rem;
    padding: 0 0.2rem;
  }
  .rm:hover {
    color: #d03b3b;
  }
  td.metric,
  th.metric {
    position: sticky;
    left: 0;
    background: #fffdf9;
    font-weight: 600;
    color: #52514e;
    max-width: 15rem;
    white-space: normal;
    z-index: 1;
  }
  thead th.metric {
    background: #f6f1e7;
  }
  td.val {
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  td.val.pos {
    color: #006300;
    font-weight: 600;
  }
  td.val.neg {
    color: #d03b3b;
    font-weight: 600;
  }
  .note {
    color: #6f6a61;
    font-size: 0.9rem;
    max-width: 46rem;
    margin-top: 0.7rem;
  }
  h2 {
    margin: 1.6rem 0 0.2rem;
  }
  .chartlegend {
    color: #52514e;
    font-size: 0.85rem;
    margin: 0 0 0.5rem;
  }
  .sw {
    display: inline-block;
    width: 14px;
    height: 3px;
    vertical-align: middle;
    border-radius: 2px;
  }
  .sw.ela {
    background: #2a78d6;
  }
  .sw.math {
    background: #d97b29;
  }
  .panels {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 0.8rem;
  }
  .panel {
    margin: 0;
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    padding: 0.5rem 0.7rem 0.3rem;
  }
  .panel figcaption {
    font-size: 0.85rem;
    font-weight: 650;
    margin-bottom: 0.2rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .panel figcaption a {
    text-decoration: none;
    color: #211d18;
  }
  .panel figcaption a:hover {
    color: #b0552f;
  }
  .panel svg {
    width: 100%;
    height: auto;
    display: block;
  }
  .grid {
    stroke: #f0ead9;
  }
  .tick {
    font-size: 10px;
    fill: #898781;
  }
  .line {
    stroke-width: 2;
  }
  .line.ela,
  .dot.ela {
    stroke: #2a78d6;
    fill: none;
  }
  .dot.ela {
    fill: #2a78d6;
    stroke: none;
  }
  .line.math {
    stroke: #d97b29;
  }
  .dot.math {
    fill: #d97b29;
  }
</style>
