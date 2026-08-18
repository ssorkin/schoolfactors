<script>
  import { dataUrl } from '$lib/data.js';
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { replaceState } from '$app/navigation';
  import Badges from '$lib/Badges.svelte';
  import CsvButton from '$lib/CsvButton.svelte';
  import FacetFilter from '$lib/FacetFilter.svelte';
  import { matchNums, norm, parseQuery } from '$lib/facets.js';

  const CATEGORIES = [
    [128, 'Students with disabilities'],
    [31, 'Economically disadvantaged students'],
    [160, 'English learners'],
    [8, 'Reclassified English learners'],
    [74, 'Black students'],
    [78, 'Hispanic or Latino students'],
    [76, 'Asian students'],
    [77, 'Filipino students'],
    [80, 'White students'],
    [144, 'Students of two or more races'],
    [52, 'Homeless students'],
    [240, 'Foster youth'],
    [90, 'Students whose parents did not finish high school']
  ];
  const LABELS = Object.fromEntries(CATEGORIES);

  const EIL_LABEL = {
    ELEM: 'elementary',
    INTMIDJR: 'middle',
    HS: 'high',
    ELEMHIGH: 'k-12',
    PS: 'preschool',
    A: 'adult',
    UG: 'other'
  };

  let group = $state(128);
  let rows = $state(null);
  let query = $state('');
  let kindFilter = $state('school');
  let includeInactive = $state(false);
  let sortKey = $state('combined');
  let sortDir = $state(-1);
  let shown = $state(150);
  const cache = new Map();

  async function loadGroup(g) {
    group = g;
    rows = null;
    if (!cache.has(g)) {
      const raw = await (await fetch(dataUrl(`/data/groups/${g}.json`))).json();
      cache.set(
        g,
        raw.map((r) => ({
          ...r,
          level: r.eil ? (EIL_LABEL[r.eil] ?? 'other') : '',
          combined:
            r.pass_ela != null && r.pass_math != null
              ? (r.pass_ela + r.pass_math) / 2
              : (r.pass_ela ?? r.pass_math),
          _hay: norm(r.name + ' ' + (r.district ?? '') + ' ' + (r.county ?? ''))
        }))
      );
    }
    rows = cache.get(g);
  }

  onMount(() => {
    const q = new URLSearchParams(window.location.search);
    const g = Number(q.get('g'));
    loadGroup(LABELS[g] ? g : 128);
  });

  $effect(() => {
    if (!browser || !rows) return;
    const target = window.location.pathname + `?g=${group}`;
    if (target !== window.location.pathname + window.location.search) {
      replaceState(target, {});
    }
  });

  let parsed = $derived(parseQuery(query));

  let filtered = $derived.by(() => {
    if (!rows) return [];
    const { facets, free } = parsed;
    const kind = facets.kind ?? (kindFilter === 'all' ? null : kindFilter);
    const out = [];
    for (const r of rows) {
      if (!includeInactive && (r.last_year ?? 0) < 2024) continue;
      if (kind && !r.kind.startsWith(kind)) continue;
      if (facets.level && !(r.level ?? '').startsWith(facets.level)) continue;
      if (facets.county && !norm(r.county).includes(facets.county)) continue;
      if (facets.district && !norm(r.district ?? '').includes(facets.district)) continue;
      if (facets.is && !(r.flags ?? []).some((f) => f.startsWith(facets.is))) continue;
      if (!matchNums(parsed.nums, r)) continue;
      let ok = true;
      for (const t of free) {
        if (!r._hay.includes(t)) {
          ok = false;
          break;
        }
      }
      if (ok) out.push(r);
    }
    return out;
  });

  let sorted = $derived.by(() => {
    const arr = [...filtered];
    const k = sortKey;
    const d = sortDir;
    if (k === 'name' || k === 'county' || k === 'level') {
      arr.sort((a, b) => d * String(a[k] ?? '').localeCompare(String(b[k] ?? '')));
    } else {
      arr.sort((a, b) => {
        const av = a[k];
        const bv = b[k];
        if (av == null && bv == null) return 0;
        if (av == null) return 1;
        if (bv == null) return -1;
        return d * (av - bv);
      });
    }
    return arr;
  });

  function setSort(k, defaultDir = -1) {
    if (sortKey === k) sortDir = -sortDir;
    else {
      sortKey = k;
      sortDir = defaultDir;
    }
    shown = 150;
  }

  $effect(() => {
    query;
    kindFilter;
    includeInactive;
    group;
    shown = 150;
  });

  function onscroll(ev) {
    const el = ev.target;
    if (el.scrollTop + el.clientHeight > el.scrollHeight - 600 && shown < sorted.length) {
      shown += 200;
    }
  }

  const SPARK_YEARS = [2015, 2016, 2017, 2018, 2019, 2022, 2023, 2024, 2025];
  function sparkRuns(spark) {
    if (!spark) return [];
    const pts = spark.map((v, i) => ({ v, i })).filter((p) => p.v != null);
    if (pts.length < 2) return [];
    const vals = pts.map((p) => p.v);
    const lo = Math.min(...vals);
    const span = Math.max(Math.max(...vals) - lo, 8);
    const X = (i) => 3 + (i / 8) * 98;
    const Y = (v) => 21 - ((v - lo) / span) * 16;
    const runs = [[]];
    for (const p of pts) {
      const cur = runs[runs.length - 1];
      if (cur.length && p.i - cur[cur.length - 1].i > 1) runs.push([p]);
      else cur.push(p);
    }
    return runs
      .filter((r) => r.length > 1)
      .map((r) => r.map((p) => `${X(p.i).toFixed(1)},${Y(p.v).toFixed(1)}`).join(' '));
  }
  function sparkTitle(spark) {
    if (!spark) return '';
    return SPARK_YEARS.map((y, i) => (spark[i] == null ? null : `${y}: ${spark[i]}%`))
      .filter(Boolean)
      .join(', ');
  }
</script>

<svelte:head><title>Student groups: {LABELS[group]?.toLowerCase()} — SchoolFactors</title></svelte:head>

<h1>Where do <span class="hl">{LABELS[group]?.toLowerCase()}</span> meet standards?</h1>
<p class="lede">
  Raw pass rates for one student group, from the same public CAASPP data. High rates
  often travel with demographics and selection, not just schooling — these are
  outcomes, not ratings. Groups under 11 students are suppressed at the source, so
  small schools may be absent. <a href="/methodology">How to read this honestly.</a>
</p>

<div class="cats">
  {#each CATEGORIES as [g, label] (g)}
    <button class:on={group === g} onclick={() => loadGroup(g)}>{label}</button>
  {/each}
</div>

<div class="controls">
  <FacetFilter
    bind:query
    items={rows ?? []}
    placeholder={'Filter… try "students:<150 level:elementary", "frpm:>80", or "is:magnet"'}
  />
  <div class="chips" role="group" aria-label="Kind">
    {#each [['school', 'Schools'], ['district', 'Districts'], ['county', 'Counties'], ['all', 'All']] as [k, label] (k)}
      <button class:on={kindFilter === k} onclick={() => (kindFilter = k)}>{label}</button>
    {/each}
  </div>
  <label class="inactive">
    <input type="checkbox" bind:checked={includeInactive} />
    include inactive
  </label>
  {#if rows}
    <span class="count">{sorted.length.toLocaleString()} entities</span>
  {/if}
</div>

<div class="tablecard">
  {#if rows}
    <div class="tabletools">
      <span>{sorted.length.toLocaleString()} rows</span>
      <CsvButton
        filename="schoolfactors {LABELS[group]?.toLowerCase()}.csv"
        build={() => ({
          headers: [
            'Name', 'Kind', 'District', 'County', 'Level', 'ELA met+ %', 'Math met+ %',
            'vs all (pp)', 'In group', 'Enrollment', 'CDS'
          ],
          rows: sorted.map((r) => [
            r.name, r.kind, r.district, r.county, r.level, r.pass_ela, r.pass_math,
            r.gap, r.n, r.enrollment, r.cds
          ])
        })}
      />
    </div>
  {/if}
  <div class="tablewrap" {onscroll}>
    <table>
    <thead>
      <tr>
        <th class="sortable" onclick={() => setSort('name', 1)}>
          Name {sortKey === 'name' ? (sortDir > 0 ? '↑' : '↓') : ''}
        </th>
        <th class="sortable" onclick={() => setSort('county', 1)}>
          County {sortKey === 'county' ? (sortDir > 0 ? '↑' : '↓') : ''}
        </th>
        <th class="sortable" onclick={() => setSort('level', 1)}>
          Level {sortKey === 'level' ? (sortDir > 0 ? '↑' : '↓') : ''}
        </th>
        <th class="tnum sortable" title="% of this group meeting or exceeding the ELA standard, latest year" onclick={() => setSort('pass_ela')}>
          ELA<br />met+ {sortKey === 'pass_ela' ? (sortDir > 0 ? '↑' : '↓') : ''}
        </th>
        <th class="tnum sortable" title="% of this group meeting or exceeding the Math standard, latest year" onclick={() => setSort('pass_math')}>
          Math<br />met+ {sortKey === 'pass_math' ? (sortDir > 0 ? '↑' : '↓') : ''}
        </th>
        <th title="This group's combined pass rate across years">Trend</th>
        <th class="tnum sortable" title="Percentage-point difference between this group's combined pass rate and the school's all-students rate" onclick={() => setSort('gap')}>
          vs all {sortKey === 'gap' ? (sortDir > 0 ? '↑' : '↓') : ''}
        </th>
        <th class="tnum sortable" title="Students in this group with scores, latest year" onclick={() => setSort('n')}>
          In group {sortKey === 'n' ? (sortDir > 0 ? '↑' : '↓') : ''}
        </th>
        <th class="tnum sortable" title="Census-day enrollment, all students" onclick={() => setSort('enrollment')}>
          Students {sortKey === 'enrollment' ? (sortDir > 0 ? '↑' : '↓') : ''}
        </th>
      </tr>
    </thead>
    <tbody>
      {#if rows}
        {#each sorted.slice(0, shown) as r (r.cds)}
          <tr>
            <td class="name">
              <a href="/{r.kind}/{r.cds}">{r.name}</a><Badges flags={r.flags} />
              {#if r.kind === 'school'}<span class="sub">{r.district}</span>{/if}
            </td>
            <td class="dim">{r.county}</td>
            <td class="dim">{r.level}</td>
            <td class="tnum">{r.pass_ela == null ? '—' : r.pass_ela + '%'}</td>
            <td class="tnum">{r.pass_math == null ? '—' : r.pass_math + '%'}</td>
            <td class="spark">
              {#if sparkRuns(r.spark).length}
                <svg viewBox="0 0 104 24" width="104" height="24" role="img">
                  <title>{sparkTitle(r.spark)}</title>
                  {#each sparkRuns(r.spark) as run, ri (ri)}
                    <polyline fill="none" stroke="#2a78d6" stroke-width="1.6" points={run} />
                  {/each}
                </svg>
              {:else}<span class="dim">—</span>{/if}
            </td>
            <td class="tnum" class:pos={r.gap > 2} class:neg={r.gap < -2}>
              {r.gap == null ? '—' : (r.gap > 0 ? '+' : '') + r.gap + 'pp'}
            </td>
            <td class="tnum dim">{r.n?.toLocaleString() ?? '—'}</td>
            <td class="tnum dim">{r.enrollment?.toLocaleString() ?? '—'}</td>
          </tr>
        {/each}
      {:else}
        <tr><td colspan="9" class="loading">Loading…</td></tr>
      {/if}
    </tbody>
    </table>
    {#if rows && shown < sorted.length}
      <p class="more">Scroll for more — {(sorted.length - shown).toLocaleString()} rows below</p>
    {/if}
  </div>
</div>

<p class="foot">
  "vs all" compares the group with the same school's all-students rate — a school can
  rate well for everyone and still under-serve a group, or vice versa. Sorting is not
  ranking; differences of a few points are usually within noise.
</p>

<style>
  h1 {
    font-size: 1.7rem;
    margin: 0.8rem 0 0.4rem;
  }
  .hl {
    color: #b0552f;
  }
  .lede {
    max-width: 52rem;
    color: #4a453d;
    margin: 0 0 0.8rem;
  }
  .cats {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
    margin-bottom: 0.8rem;
  }
  .cats button {
    border: 1px solid #d8d0c0;
    background: #faf7f2;
    border-radius: 999px;
    padding: 0.28rem 0.8rem;
    font-size: 0.86rem;
    cursor: pointer;
    color: #52514e;
  }
  .cats button.on {
    background: #b0552f;
    border-color: #b0552f;
    color: #fff;
  }
  .controls {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    align-items: center;
    margin-bottom: 0.6rem;
  }
  .chips {
    display: flex;
    gap: 0.25rem;
  }
  .chips button {
    border: 1px solid #d8d0c0;
    background: #faf7f2;
    border-radius: 999px;
    padding: 0.25rem 0.75rem;
    font-size: 0.85rem;
    cursor: pointer;
    color: #52514e;
  }
  .chips button.on {
    background: #2a78d6;
    border-color: #2a78d6;
    color: #fff;
  }
  .inactive {
    color: #898781;
    font-size: 0.85rem;
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    cursor: pointer;
  }
  .count {
    color: #898781;
    font-size: 0.88rem;
    font-variant-numeric: tabular-nums;
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
    font-variant-numeric: tabular-nums;
  }
  .tablewrap {
    max-height: 68vh;
    overflow: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.88rem;
    min-width: 900px;
  }
  thead th {
    position: sticky;
    top: 0;
    background: #f6f1e7;
    z-index: 2;
    text-align: left;
    vertical-align: bottom;
    padding: 0.35rem 0.55rem;
    border-bottom: 1px solid #e8e1d5;
    white-space: nowrap;
    color: #52514e;
    line-height: 1.25;
  }
  th.sortable {
    cursor: pointer;
    user-select: none;
  }
  th.sortable:hover {
    color: #b0552f;
  }
  td {
    padding: 0.32rem 0.55rem;
    border-bottom: 1px solid #f0ead9;
    white-space: nowrap;
  }
  td.name a {
    font-weight: 600;
    text-decoration: none;
  }
  td.name a:hover {
    text-decoration: underline;
  }
  .sub {
    display: block;
    color: #898781;
    font-size: 0.76rem;
  }
  .dim {
    color: #6f6a61;
  }
  .tnum {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  td.pos {
    color: #006300;
    font-weight: 600;
  }
  td.neg {
    color: #d03b3b;
    font-weight: 600;
  }
  .spark {
    line-height: 0;
  }
  .loading {
    padding: 2rem;
    text-align: center;
    color: #898781;
  }
  .more {
    text-align: center;
    color: #898781;
    font-size: 0.85rem;
    padding: 0.5rem;
    margin: 0;
  }
  .foot {
    color: #898781;
    font-size: 0.85rem;
    max-width: 52rem;
    margin-top: 0.8rem;
  }
</style>
