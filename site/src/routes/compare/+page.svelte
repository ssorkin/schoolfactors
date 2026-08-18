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
  import { GROUP_LABELS, GROUP_THEMES, SERIES_COLORS } from '$lib/groups.js';
  import { GLOSSARY } from '$lib/glossary.js';

  const glossaryById = Object.fromEntries(GLOSSARY.map((g) => [g.id, g]));

  // On-page info popovers for the row terms (no navigation away). Fixed
  // positioning so the popup escapes the table's scroll container; closes on
  // outside click, Escape, scroll, or the x.
  let info = $state(null); // { label, tip, gid, x, y }
  function toggleInfo(ev, r) {
    ev.stopPropagation();
    if (info?.label === r.label) {
      info = null;
      return;
    }
    const rect = ev.currentTarget.getBoundingClientRect();
    info = {
      label: r.label,
      tip: r.tip,
      gid: r.gid,
      x: Math.max(8, Math.min(rect.left, window.innerWidth - 400)),
      y: Math.min(rect.bottom + 6, window.innerHeight - 280)
    };
  }

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
    { label: 'Students (census)', gid: 'enrollment', tip: 'Census-day enrollment from CDE, latest school year.', f: (s) => s.enrollment?.toLocaleString() ?? '—' },
    {
      label: 'Econ. disadvantaged (tested)',
      gid: 'econ-share',
      tip:
        'Share of tested students CDE flags as economically disadvantaged (FRPM-eligible, ' +
        'parents without a high-school diploma, or foster/homeless). From CAASPP research files.',
      f: (s) =>
        s.effects?.share_econ_dis == null
          ? '—'
          : Math.round(s.effects.share_econ_dis * 100) + '%'
    },
    { label: '$ per pupil', gid: 'ppe', tip: 'Total ESSA per-pupil spending — school site plus allocated central costs, latest year, from CDE. Largely need-driven: higher is neither praise nor criticism.', f: (s) => (s.ppe == null ? '—' : '$' + s.ppe.toLocaleString()) },
    { label: 'ELA met+ (latest)', gid: 'met-plus', tip: 'Share of tests meeting or exceeding the standard, latest year. From CAASPP.', f: (s) => (s.pass_ela == null ? '—' : s.pass_ela + '%') },
    { label: 'Math met+ (latest)', gid: 'met-plus', tip: 'Share of tests meeting or exceeding the standard, latest year. From CAASPP.', f: (s) => (s.pass_math == null ? '—' : s.pass_math + '%') },
    { label: 'Raw level (SDs vs state)', gid: 'level', tip: 'Where students score vs the state average, in student-level standard deviations — at +1 SD, the average student here outscores about 84% of students statewide; at +2 SD, about 98%. Weighted toward recent years, from CAASPP mean scale scores.', f: (s) => fmt2(s.effects?.level_eb) },
    {
      label: 'Expected level, given students served',
      gid: 'expected-level',
      tip:
        'What the statewide model predicts a school with this demographic profile would ' +
        'score — the bar its performance is measured against.',
      f: (s) =>
        s.effects?.level_eb == null || s.effects?.level_adj_eb == null
          ? '—'
          : fmt2(s.effects.level_eb - s.effects.level_adj_eb)
    },
    {
      label: 'Performance vs expectation',
      gid: 'adjusted',
      tip:
        'Actual minus expected — what remains after accounting for the students served. ' +
        'Not a measure of school quality.',
      f: (s) => fmt2(s.effects?.level_adj_eb),
      cls: (s) =>
        s.effects?.level_adj_eb > 0 ? 'pos' : s.effects?.level_adj_eb < 0 ? 'neg' : ''
    },
    { label: 'Similar Schools %ile', gid: 'adj-percentile', tip: 'Where performance-vs-expectation ranks among comparable California schools, using the cautious end of each estimate\'s uncertainty band.', f: (s) => s.adj_pct ?? '—' },
    {
      label: 'Cohort trajectory',
      gid: 'cohort-trajectory',
      tip:
        'Whether classes gain on the state, hold their standing, or lose ground as they ' +
        'move up the grades. From CAASPP cohort tracking.',
      f: (s) => CAT[s.growth_cat] ?? '—',
      cls: (s) =>
        s.growth_cat === 'gaining' ? 'pos' : s.growth_cat === 'slipping' ? 'neg' : ''
    },
    {
      label: 'Met+ vs its own expected-alike band',
      gid: 'expected-alike-band',
      tip:
        'This school\'s pass rate against the pooled rate of all schools the model ' +
        'expects to score alike — its percentile in plain numbers.',
      f: (s) =>
        band(s, 'met') != null && band(s, 'p_met') != null
          ? `${Math.round(band(s, 'met'))}% vs ${Math.round(band(s, 'p_met'))}%`
          : '—'
    },
    {
      label: 'Exceeded vs its band',
      gid: 'expected-alike-band',
      tip:
        'Same comparison at the top band (standard exceeded) — two schools can match on ' +
        'meeting standards while differing sharply in how many students exceed them.',
      f: (s) =>
        band(s, 'exc') != null && band(s, 'p_exc') != null
          ? `${Math.round(band(s, 'exc'))}% vs ${Math.round(band(s, 'p_exc'))}%`
          : '—'
    }
  ];

  // ---- Small multiples: one panel per student group, all compared schools
  // overlaid in fixed colors (color follows the school across every panel),
  // SHARED 0-100 scale; lines break at the COVID gap.
  const CW = 280;
  const CH = 150;
  const CM = { l: 30, r: 10, t: 10, b: 22 };
  const Y0 = 2015;
  const Y1 = 2025;
  const CX = (y) => CM.l + ((y - Y0) / (Y1 - Y0)) * (CW - CM.l - CM.r);
  const CY = (v) => CM.t + ((100 - v) / 100) * (CH - CM.t - CM.b);

  const PANEL_THEMES = [{ label: 'Overall', ids: [1] }, ...GROUP_THEMES];

  function groupSeries(s, gid) {
    const by = {};
    for (const r of s.subgroup_results ?? []) {
      if (r.group === gid && r.pct_met != null && r.n) {
        by[r.year] ??= [0, 0];
        by[r.year][0] += r.pct_met * r.n;
        by[r.year][1] += r.n;
      }
    }
    const pts = Object.keys(by)
      .map((y) => ({ year: +y, v: by[y][0] / by[y][1] }))
      .sort((a, b) => a.year - b.year);
    const runs = [[]];
    for (const p of pts) {
      const cur = runs[runs.length - 1];
      if (cur.length && p.year - cur[cur.length - 1].year > 1) runs.push([p]);
      else cur.push(p);
    }
    return { pts, runs: runs.filter((r) => r.length > 1) };
  }

  let panelThemes = $derived.by(() => {
    const out = [];
    for (const t of PANEL_THEMES) {
      const panels = [];
      for (const gid of t.ids) {
        const per = schools.map((s, i) => ({ s, i, ser: groupSeries(s, gid) }));
        if (per.some((x) => x.ser.pts.length >= 2)) panels.push({ gid, per });
      }
      if (panels.length) out.push({ label: t.label, panels });
    }
    return out;
  });
</script>

<svelte:head>
  <title>Compare schools side by side — SchoolFactors</title>
  <meta
    name="description"
    content="A symmetric school comparison: each school measured against its own model expectation and expected-alike band — no school is the benchmark."
  />
</svelte:head>

<svelte:window
  onclick={() => (info = null)}
  onkeydown={(e) => e.key === 'Escape' && (info = null)}
  onscroll={() => (info = null)}
/>

{#if info}
  <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
  <div
    class="popover"
    role="dialog"
    aria-label="About {info.label}"
    style:left="{info.x}px"
    style:top="{info.y}px"
    onclick={(e) => e.stopPropagation()}
  >
    <button class="pclose" aria-label="Close" onclick={() => (info = null)}>×</button>
    <h4>{glossaryById[info.gid]?.term ?? info.label}</h4>
    <p class="ptip">{info.tip}</p>
    {#each (glossaryById[info.gid]?.def ?? []).slice(0, 2) as para (para)}
      <p class="pdef">{para}</p>
    {/each}
    <a href="/glossary#{info.gid}">Full glossary entry →</a>
  </div>
{/if}

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
              <td class="metric">
                {r.label}
                {#if r.gid}
                  <button
                    class="info"
                    title={r.tip}
                    aria-expanded={info?.label === r.label}
                    aria-label="What {r.label} means and where the data comes from"
                    onclick={(ev) => toggleInfo(ev, r)}>ⓘ</button
                  >
                {/if}
              </td>
              {#each schools as s (s.cds)}
                <td class="val {r.cls ? r.cls(s) : ''}">{r.f(s)}</td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>
  <h2>Met+ by year, by student group</h2>
  <div class="chartsgrid">
    <aside class="chartrail">
      <div class="railbox">
        <h4>Schools</h4>
        {#each schools as s, i (s.cds)}
          <div class="railitem">
            <span class="sw" style:background={SERIES_COLORS[i]}></span>
            <a href="/school/{s.cds}">{s.name}</a>
          </div>
        {/each}
        <p class="railnote">
          % meeting or exceeding the standard, ELA and math combined. All panels
          share the same 0–100% scale. Gaps: no comparable testing (2020–21) or
          fewer than 11 students in the group.
        </p>
      </div>
    </aside>
    <div class="chartcol">
  {#each panelThemes as t (t.label)}
    <h3>{t.label}</h3>
    <div class="panels">
      {#each t.panels as p (p.gid)}
        <figure class="panel">
          <figcaption>{GROUP_LABELS[p.gid] ?? 'Group ' + p.gid}</figcaption>
          <svg
            viewBox="0 0 {CW} {CH}"
            role="img"
            aria-label="Met+ by year for {GROUP_LABELS[p.gid]}, all compared schools"
          >
            {#each [0, 50, 100] as tk (tk)}
              <line x1={CM.l} x2={CW - CM.r} y1={CY(tk)} y2={CY(tk)} class="grid" />
              <text x={CM.l - 5} y={CY(tk) + 3.5} class="tick" text-anchor="end">{tk}</text>
            {/each}
            {#each [2015, 2019, 2022, 2025] as y (y)}
              <text x={CX(y)} y={CH - 6} class="tick" text-anchor="middle">{y}</text>
            {/each}
            {#each p.per as x (x.s.cds)}
              {#each x.ser.runs as run, ri (ri)}
                <polyline
                  fill="none"
                  stroke={SERIES_COLORS[x.i]}
                  stroke-width="2"
                  points={run.map((q) => `${CX(q.year).toFixed(1)},${CY(q.v).toFixed(1)}`).join(' ')}
                />
              {/each}
              {#each x.ser.pts as q (x.s.cds + q.year)}
                <circle cx={CX(q.year)} cy={CY(q.v)} r="2.2" fill={SERIES_COLORS[x.i]}>
                  <title>{x.s.name} — {q.year}: {q.v.toFixed(0)}% met+</title>
                </circle>
              {/each}
            {/each}
          </svg>
        </figure>
      {/each}
    </div>
  {/each}
    </div>
  </div>

  <p class="note">
    Levels are in student standard deviations (SDs): at +1 SD a school's average
    student outscores about 84% of students statewide; at +2 SD, about 98%.
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
  .sw {
    margin-right: 0.25rem;
  }
  h3 {
    margin: 1rem 0 0.4rem;
    font-size: 1rem;
    color: #52514e;
  }
  .chartcol h3:first-child {
    margin-top: 0;
  }
  .chartsgrid {
    display: grid;
    grid-template-columns: 15rem minmax(0, 1fr);
    gap: 1.2rem;
    align-items: start;
  }
  .chartrail {
    position: sticky;
    top: 1rem;
  }
  .railbox {
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    padding: 0.7rem 0.9rem;
  }
  .railbox h4 {
    margin: 0 0 0.4rem;
    font-size: 0.76rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #898781;
  }
  .railitem {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 0.35rem 0;
    font-size: 0.92rem;
    font-weight: 600;
    line-height: 1.25;
  }
  .railitem .sw {
    width: 14px;
    height: 14px;
    border-radius: 4px;
    flex: none;
    margin: 0;
  }
  .railitem a {
    text-decoration: none;
    color: #211d18;
  }
  .railitem a:hover {
    color: #b0552f;
  }
  .railnote {
    font-size: 0.76rem;
    color: #898781;
    margin: 0.7rem 0 0;
  }
  @media (max-width: 880px) {
    .chartsgrid {
      display: block;
    }
    .chartrail {
      position: static;
      margin-bottom: 0.8rem;
    }
  }
  .info {
    border: none;
    background: none;
    padding: 0;
    cursor: pointer;
    color: #1c5cab;
    font: inherit;
    font-size: 0.85em;
    margin-left: 0.25rem;
  }
  .info:hover {
    color: #b0552f;
  }
  .popover {
    position: fixed;
    z-index: 50;
    width: min(92vw, 24rem);
    max-height: 22rem;
    overflow-y: auto;
    background: #fffdf9;
    border: 1px solid #d8d0c0;
    border-radius: 10px;
    box-shadow: 0 10px 28px rgba(43, 39, 34, 0.18);
    padding: 0.8rem 1rem;
  }
  .popover h4 {
    margin: 0 1.2rem 0.3rem 0;
    font-size: 0.95rem;
  }
  .popover .ptip {
    margin: 0 0 0.4rem;
    font-size: 0.86rem;
    color: #2b2722;
    font-weight: 550;
  }
  .popover .pdef {
    margin: 0 0 0.4rem;
    font-size: 0.82rem;
    color: #52514e;
  }
  .popover a {
    font-size: 0.84rem;
    font-weight: 600;
  }
  .pclose {
    position: absolute;
    top: 0.35rem;
    right: 0.5rem;
    border: none;
    background: none;
    font-size: 1.1rem;
    color: #898781;
    cursor: pointer;
  }
  .pclose:hover {
    color: #d03b3b;
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
</style>
