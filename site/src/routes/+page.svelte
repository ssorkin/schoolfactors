<script>
  import { onMount } from 'svelte';
  import Badges from '$lib/Badges.svelte';
  import { COLTIP } from '$lib/glossary.js';

  let items = $state(null);
  let query = $state('');
  let kindFilter = $state('all'); // all | school | district | county
  let levelFilter = $state('all'); // all | elementary | middle | high | k-12
  let includeInactive = $state(false); // entities with no data since 2024 (closures)
  let sortKey = $state('name');
  let sortDir = $state(1); // 1 asc, -1 desc
  let shown = $state(150);

  const EIL_LABEL = {
    ELEM: 'elementary',
    INTMIDJR: 'middle',
    HS: 'high',
    ELEMHIGH: 'k-12',
    PS: 'preschool',
    A: 'adult',
    UG: 'other'
  };

  function norm(s) {
    return (s ?? '')
      .toLowerCase()
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/[^a-z0-9\s-]/g, ' ');
  }

  let loadError = $state(false);
  onMount(async () => {
    try {
      const raw = await (await fetch('/data/index.json')).json();
      items = raw.map((it) => ({
        ...it,
        level: it.eil ? (EIL_LABEL[it.eil] ?? 'other') : it.kind !== 'school' ? '' : 'other',
        _name: norm(it.name),
        _extra: norm((it.district ?? '') + ' ' + (it.county ?? ''))
      }));
    } catch {
      loadError = true;
    }
  });

  // Facet-aware query parsing: `level:middle county:los angeles ivanhoe` etc.
  // Words after a facet keyword attach to that facet until the next facet.
  const FACET_KEYS = ['level', 'kind', 'county', 'district', 'type', 'is'];
  let parsed = $derived.by(() => {
    const facets = {};
    const free = [];
    let cur = null;
    for (const p of query.split(/\s+/).filter(Boolean)) {
      const m = p.match(/^(level|kind|county|district|type|is):(.*)$/i);
      if (m) {
        cur = m[1].toLowerCase() === 'type' ? 'level' : m[1].toLowerCase();
        if (m[2]) facets[cur] = norm(m[2]).trim();
        else facets[cur] = '';
      } else if (cur !== null) {
        facets[cur] = (facets[cur] + ' ' + norm(p)).trim();
      } else {
        free.push(norm(p).trim());
      }
    }
    return { facets, free: free.filter(Boolean) };
  });

  let filtered = $derived.by(() => {
    if (!items) return [];
    const { facets, free } = parsed;
    const kind = facets.kind ?? (kindFilter === 'all' ? null : kindFilter);
    const level = facets.level ?? (levelFilter === 'all' ? null : levelFilter);
    const out = [];
    for (const it of items) {
      if (!includeInactive && (it.last_year ?? 0) < 2024) continue;
      if (kind && !it.kind.startsWith(kind)) continue;
      if (level && !(it.level ?? '').startsWith(level)) continue;
      if (facets.county && !norm(it.county).includes(facets.county)) continue;
      if (facets.district && !norm(it.district ?? '').includes(facets.district)) continue;
      if (facets.is && !(it.flags ?? []).some((f) => f.startsWith(facets.is))) continue;
      let ok = true;
      for (const t of free) {
        if (!it._name.includes(t) && !it._extra.includes(t)) {
          ok = false;
          break;
        }
      }
      if (ok) out.push(it);
    }
    return out;
  });

  let sorted = $derived.by(() => {
    const arr = [...filtered];
    const k = sortKey;
    const d = sortDir;
    if (k === 'name' || k === 'district' || k === 'county' || k === 'level' || k === 'kind') {
      arr.sort((a, b) => d * String(a[k] ?? '').localeCompare(String(b[k] ?? '')));
    } else {
      arr.sort((a, b) => {
        const av = a[k];
        const bv = b[k];
        if (av == null && bv == null) return 0;
        if (av == null) return 1; // nulls last regardless of direction
        if (bv == null) return -1;
        return d * (av - bv);
      });
    }
    return arr;
  });

  function setSort(k, defaultDir = 1) {
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
    levelFilter;
    includeInactive;
    shown = 150;
  });

  function onscroll(ev) {
    const el = ev.target;
    if (el.scrollTop + el.clientHeight > el.scrollHeight - 600 && shown < sorted.length) {
      shown += 200;
    }
  }

  const fmt = (v) => (v == null ? '—' : (v > 0 ? '+' : '') + v.toFixed(2));
  const pct = (v) => (v == null ? '—' : Math.round(v * 100) + '%');

  // Sparkline: 9 slots (2015-19, 2022-25), per-row scale, gap between runs.
  const SPARK_YEARS = [2015, 2016, 2017, 2018, 2019, 2022, 2023, 2024, 2025];
  function sparkRuns(spark) {
    if (!spark) return [];
    const pts = spark
      .map((v, i) => ({ v, i }))
      .filter((p) => p.v != null);
    if (pts.length < 2) return [];
    const vals = pts.map((p) => p.v);
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    const span = Math.max(hi - lo, 8); // avoid amplifying noise into drama
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

  // Tooltip text lives in $lib/glossary.js — one source for headers and /glossary.
  const PASS_COLS = [
    ['pass_ela', 'ELA met+'],
    ['pass_math', 'Math met+']
  ];
  const NUM_COLS = [
    ['adj_ela', 'Adj ELA'],
    ['adj_math', 'Adj Math'],
    ['growth_adj_eb', 'Growth'],
    ['ppe', '$/Pupil'],
    ['econ', '% Econ'],
    ['enrollment', 'Students'],
    ['total_scores', 'Scores']
  ];
</script>

<svelte:head><title>SchoolFactors — every California school, measured honestly</title></svelte:head>

<div class="intro">
  <h1>Every California school, in one honest table.</h1>
  <p>
    {#if items}
      {items.length.toLocaleString()} schools, districts, and counties from ten years of
      public data.
    {:else}
      Loading the dataset…
    {/if}
    Adjusted columns compare against entities serving similar students; raw columns
    against the state average — <a href="/methodology">correlations, not causes, with
    error margins</a>. Reproducible from
    <a href="https://github.com/ssorkin/schoolfactors">source</a>.
  </p>
</div>

<div class="controls">
  <input
    class="filter"
    placeholder={'Filter… try "county:sonoma level:high", "is:magnet", or "is:selective"'}
    bind:value={query}
    aria-label="Filter table"
  />
  <div class="chips" role="group" aria-label="Kind">
    {#each [['all', 'All'], ['school', 'Schools'], ['district', 'Districts'], ['county', 'Counties']] as [k, label] (k)}
      <button class:on={kindFilter === k} onclick={() => (kindFilter = k)}>{label}</button>
    {/each}
  </div>
  <div class="chips" role="group" aria-label="School level">
    {#each [['all', 'Any level'], ['elementary', 'Elementary'], ['middle', 'Middle'], ['high', 'High']] as [k, label] (k)}
      <button class:on={levelFilter === k} onclick={() => (levelFilter = k)}>{label}</button>
    {/each}
  </div>
  <label class="inactive">
    <input type="checkbox" bind:checked={includeInactive} />
    include inactive
  </label>
  {#if items}
    <span class="count">{sorted.length.toLocaleString()} of {items.length.toLocaleString()}</span>
  {/if}
</div>

<div class="tablewrap" {onscroll}>
  <table>
    <thead>
      <tr>
        <th class="name sortable" onclick={() => setSort('name')}>
          Name {sortKey === 'name' ? (sortDir > 0 ? '↑' : '↓') : ''}
        </th>
        <th class="sortable" onclick={() => setSort('county')}>
          County {sortKey === 'county' ? (sortDir > 0 ? '↑' : '↓') : ''}
        </th>
        <th class="sortable" onclick={() => setSort('level')}>
          Level {sortKey === 'level' ? (sortDir > 0 ? '↑' : '↓') : ''}
        </th>
        {#each PASS_COLS as [k, label] (k)}
          <th class="tnum sortable" title={COLTIP[k]} onclick={() => setSort(k, -1)}>
            <span class="deft">{label}</span> {sortKey === k ? (sortDir > 0 ? '↑' : '↓') : ''}
          </th>
        {/each}
        <th title={COLTIP.spark}><span class="deft">Met+ by year</span></th>
        {#each NUM_COLS as [k, label] (k)}
          <th class="tnum sortable" title={COLTIP[k]} onclick={() => setSort(k, -1)}>
            <span class="deft">{label}</span> {sortKey === k ? (sortDir > 0 ? '↑' : '↓') : ''}
          </th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#if items}
        {#each sorted.slice(0, shown) as it (it.cds)}
          <tr>
            <td class="name">
              <a href="/{it.kind}/{it.cds}">{it.name}</a><Badges flags={it.flags} />
              {#if it.kind === 'school'}
                <span class="sub">{it.district}</span>
              {:else if it.kind === 'district'}
                <span class="sub">district</span>
              {/if}
            </td>
            <td class="dim">{it.county}</td>
            <td class="dim">{it.level}</td>
            <td class="tnum">{it.pass_ela == null ? '—' : it.pass_ela + '%'}</td>
            <td class="tnum">{it.pass_math == null ? '—' : it.pass_math + '%'}</td>
            <td class="spark">
              {#if sparkRuns(it.spark).length}
                <svg viewBox="0 0 104 24" width="104" height="24" role="img">
                  <title>Met+ by year — {sparkTitle(it.spark)}</title>
                  {#each sparkRuns(it.spark) as run, ri (ri)}
                    <polyline fill="none" stroke="#2a78d6" stroke-width="1.6" points={run} />
                  {/each}
                </svg>
              {:else}
                <span class="dim">—</span>
              {/if}
            </td>
            <td class="tnum" class:pos={it.adj_ela > 0.1} class:neg={it.adj_ela < -0.1}>{fmt(it.adj_ela)}</td>
            <td class="tnum" class:pos={it.adj_math > 0.1} class:neg={it.adj_math < -0.1}>{fmt(it.adj_math)}</td>
            <td class="tnum">{fmt(it.growth_adj_eb)}</td>
            <td class="tnum">{it.ppe == null ? '—' : '$' + it.ppe.toLocaleString()}</td>
            <td class="tnum">{pct(it.econ)}</td>
            <td class="tnum">{it.enrollment?.toLocaleString() ?? '—'}</td>
            <td class="tnum dim">{it.total_scores?.toLocaleString() ?? '—'}</td>
          </tr>
        {/each}
      {:else if loadError}
        <tr><td colspan="13" class="loading">
          Couldn't load the dataset — please reload the page.
        </td></tr>
      {:else}
        <tr><td colspan="13" class="loading">Loading the full dataset…</td></tr>
      {/if}
    </tbody>
  </table>
  {#if items && shown < sorted.length}
    <p class="more">Scroll for more — {(sorted.length - shown).toLocaleString()} rows below</p>
  {/if}
</div>

<p class="foot">
  Values are empirical-Bayes shrunken student-SD units; many entities are statistically
  indistinguishable from one another. Sorting is not ranking —
  <a href="/glossary">what every column means</a> ·
  <a href="/methodology">how these numbers are made</a> ·
  <a href="/data">data sources and known issues</a> ·
  <a href="/explore">the Sonoma pilot scatter</a>.
</p>

<style>
  .intro h1 {
    font-size: 1.8rem;
    margin: 0.8rem 0 0.4rem;
  }
  .intro p {
    max-width: 52rem;
    color: #4a453d;
    margin: 0 0 0.8rem;
  }
  .controls {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    align-items: center;
    margin-bottom: 0.6rem;
  }
  .filter {
    flex: 1 1 380px;
    padding: 0.55rem 0.8rem;
    font-size: 0.97rem;
    border: 1px solid #d8d0c0;
    border-radius: 8px;
    background: #fffdf9;
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
  .count {
    color: #898781;
    font-size: 0.88rem;
    font-variant-numeric: tabular-nums;
  }
  .inactive {
    color: #898781;
    font-size: 0.85rem;
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    cursor: pointer;
  }
  .inactive input {
    accent-color: #2a78d6;
  }
  .tablewrap {
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    background: #fffdf9;
    max-height: 72vh;
    overflow: auto;
    /* Break out of the 960px shell so all columns fit without inner scrolling;
       the shell is viewport-centered, so centering on it centers on the page. */
    --tw: min(1280px, 100vw - 2.5rem);
    width: var(--tw);
    margin-left: calc((100% - var(--tw)) / 2);
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
    min-width: 1060px;
  }
  thead th {
    position: sticky;
    top: 0;
    background: #f6f1e7;
    z-index: 2;
    text-align: left;
    padding: 0.45rem 0.5rem;
    border-bottom: 1px solid #e8e1d5;
    white-space: nowrap;
    color: #52514e;
  }
  th.sortable {
    cursor: pointer;
    user-select: none;
  }
  th.sortable:hover {
    color: #b0552f;
  }
  th .deft {
    text-decoration: underline dotted #c4bba8;
    text-underline-offset: 3px;
  }
  td {
    padding: 0.32rem 0.5rem;
    border-bottom: 1px solid #f0ead9;
    white-space: nowrap;
  }
  td.name {
    /* The one column allowed to wrap — with every cell nowrap, long school
       names push the table's natural width past any reasonable breakout. */
    white-space: normal;
    min-width: 15rem;
    line-height: 1.35;
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
