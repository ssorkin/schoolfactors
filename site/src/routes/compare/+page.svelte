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

  onMount(() => {
    const q = new URLSearchParams(window.location.search);
    for (const c of (q.get('s') ?? '')
      .split('.')
      .filter((c) => /^\d{14}$/.test(c))
      .slice(0, MAX)) {
      add(c);
    }
  });

  $effect(() => {
    if (!browser) return;
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
</style>
