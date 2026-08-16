<script>
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { replaceState } from '$app/navigation';
  import Badges from '$lib/Badges.svelte';
  import MapView from '$lib/MapView.svelte';
  import RangeFacet from '$lib/RangeFacet.svelte';
  import { COLTIP } from '$lib/glossary.js';
  import { TYPE_COLOR, TYPE_LABEL, entityType } from '$lib/maptypes.js';

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

  // ---- Shareable URL state ----
  // The whole view lives in the fragment (#q=…&s=…&f=…) so any filtered/sorted
  // table or map can be shared by copying the address bar. Restored once on
  // load; kept current via replaceState (no history spam, no scroll jumps).
  // Facet slider ranges are data-dependent, so they are parked in initFacets
  // until the dataset arrives and bounds are real.
  const SORT_KEYS = new Set([
    'name', 'county', 'level',
    'pass_ela', 'pass_math', 'adj_pct', 'growth_pct', 'ppe', 'econ', 'enrollment'
  ]);
  let restored = $state(false);
  let initFacets = null;

  function restoreHash() {
    const p = new URLSearchParams(window.location.hash.slice(1));
    query = p.get('q') ?? '';
    const k = p.get('k');
    if (['school', 'district', 'county'].includes(k)) kindFilter = k;
    const lv = p.get('lv');
    if (['elementary', 'middle', 'high', 'k-12'].includes(lv)) levelFilter = lv;
    includeInactive = p.get('i') === '1';
    const s = p.get('s');
    if (s && SORT_KEYS.has(s)) {
      sortKey = s;
      sortDir = p.get('d') === '-1' ? -1 : 1;
    }
    for (const t of (p.get('t') ?? '').split('.')) {
      if (t in typeSel) typeSel[t] = false;
    }
    const f = p.get('f');
    if (f) {
      initFacets = {};
      for (const part of f.split(',')) {
        const m = part.match(/^(\w+):(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$/);
        if (m) initFacets[m[1]] = [parseFloat(m[2]), parseFloat(m[3])];
      }
    }
    if (p.get('v') === 'map') openMap();
    restored = true;
  }

  $effect(() => {
    if (!browser || !restored) return;
    const p = new URLSearchParams();
    if (query) p.set('q', query);
    if (kindFilter !== 'all') p.set('k', kindFilter);
    if (levelFilter !== 'all') p.set('lv', levelFilter);
    if (includeInactive) p.set('i', '1');
    if (sortKey !== 'name' || sortDir !== 1) {
      p.set('s', sortKey);
      if (sortDir === -1) p.set('d', '-1');
    }
    if (view === 'map') p.set('v', 'map');
    const hidden = Object.keys(typeSel).filter((t) => !typeSel[t]);
    if (hidden.length) p.set('t', hidden.join('.'));
    const narrowed = [];
    for (const f of FACETS) {
      const b = bounds[f.key];
      const sel = fsel[f.key];
      if (b && sel && (sel[0] > b[0] || sel[1] < b[1])) {
        narrowed.push(`${f.key}:${sel[0]}-${sel[1]}`);
      }
    }
    if (narrowed.length) p.set('f', narrowed.join(','));
    const h = p.toString();
    const target = window.location.pathname + window.location.search + (h ? '#' + h : '');
    if (target !== window.location.pathname + window.location.search + window.location.hash) {
      replaceState(target, {});
    }
  });

  let loadError = $state(false);
  onMount(async () => {
    restoreHash();
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

  // Underlying (non-integer) value that breaks ties within a percentile bucket.
  const TIEBREAK = { adj_pct: 'adj_lcb', growth_pct: 'growth_lcb' };

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
        if (av !== bv) return d * (av - bv);
        // Percentiles are integers, so whole buckets tie (147 schools shared
        // "99" once); order ties by the underlying confidence bound instead of
        // accidental index order.
        const t = TIEBREAK[k];
        const at = t && a[t];
        const bt = t && b[t];
        if (at == null || bt == null) return 0;
        return d * (at - bt);
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

  const pct = (v) => (v == null ? '—' : Math.round(v * 100) + '%');

  // Sparklines: Met+ has 9 slots (2015-19, 2022-25, gap at COVID); enrollment
  // has 12 gapless slots (2015-2026 — the census ran right through COVID).
  // Per-row scale; the span floor keeps near-flat lines from amplifying noise
  // into drama: 8 points for Met+ percentages, 15% of the peak for counts.
  const SPARK_YEARS = [2015, 2016, 2017, 2018, 2019, 2022, 2023, 2024, 2025];
  const ENR_YEARS = Array.from({ length: 12 }, (_, i) => 2015 + i);
  function sparkRuns(spark, relFloor = false) {
    if (!spark) return [];
    const pts = spark
      .map((v, i) => ({ v, i }))
      .filter((p) => p.v != null);
    if (pts.length < 2) return [];
    const vals = pts.map((p) => p.v);
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    const span = Math.max(hi - lo, relFloor ? Math.max(4, hi * 0.15) : 8);
    const X = (i) => 3 + (i / (spark.length - 1)) * 98;
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
  function sparkTitle(spark, unit = '%', years = SPARK_YEARS) {
    if (!spark) return '';
    return years.map((y, i) => (spark[i] == null ? null : `${y}: ${spark[i]}${unit}`))
      .filter(Boolean)
      .join(', ');
  }

  // Tooltip text lives in $lib/glossary.js — one source for headers and /glossary.
  const PASS_COLS = [
    ['pass_ela', 'ELA met+'],
    ['pass_math', 'Math met+']
  ];

  // ---- Map view ----
  let view = $state('table'); // table | map
  let mapOpened = $state(false); // lazy-mount leaflet on first visit
  function openMap() {
    view = 'map';
    mapOpened = true;
  }
  // The map shows one kind at a time; "all" falls back to schools.
  $effect(() => {
    if (view === 'map' && kindFilter === 'all') kindFilter = 'school';
  });
  let mapKind = $derived(kindFilter === 'all' ? 'school' : kindFilter);

  // One facet per numeric table column. `scale` maps stored value → slider
  // units (econ is stored as a 0-1 fraction).
  const FACETS = [
    { key: 'pass_ela', label: 'ELA met+', fmt: (v) => v + '%' },
    { key: 'pass_math', label: 'Math met+', fmt: (v) => v + '%' },
    { key: 'adj_pct', label: 'Adj %ile' },
    { key: 'growth_pct', label: 'Growth %ile' },
    { key: 'ppe', label: '$/Pupil', step: 250, fmt: (v) => '$' + (+v).toLocaleString() },
    { key: 'econ', label: '% FRPM', scale: 100, fmt: (v) => v + '%' },
    { key: 'enrollment', label: 'Students', step: 10, fmt: (v) => (+v).toLocaleString() }
  ];

  let bounds = $derived.by(() => {
    const out = {};
    for (const f of FACETS) {
      let mn = Infinity;
      let mx = -Infinity;
      for (const it of items ?? []) {
        if (it.kind !== mapKind) continue;
        let v = it[f.key];
        if (v == null) continue;
        if (f.scale) v = v * f.scale;
        if (v < mn) mn = v;
        if (v > mx) mx = v;
      }
      out[f.key] = mn <= mx ? [Math.floor(mn), Math.ceil(mx)] : [0, 1];
    }
    return out;
  });

  let typeSel = $state({
    selective: true,
    magnet: true,
    charter: true,
    alternative: true,
    regular: true
  });

  let fsel = $state({});
  function resetFacets() {
    for (const f of FACETS) fsel[f.key] = [...(bounds[f.key] ?? [0, 1])];
  }
  $effect(() => {
    bounds; // re-run when kind (or data) changes
    resetFacets();
    // Ranges restored from a shared URL are applied once, clamped to the real
    // data bounds, after the dataset arrives.
    if (items && initFacets) {
      for (const f of FACETS) {
        const r = initFacets[f.key];
        const b = bounds[f.key];
        if (!r || !b) continue;
        const lo = Math.min(Math.max(r[0], b[0]), b[1]);
        const hi = Math.max(Math.min(r[1], b[1]), lo);
        fsel[f.key] = [lo, hi];
      }
      initFacets = null;
    }
  });

  const esc = (s) =>
    String(s ?? '').replace(
      /[&<>"]/g,
      (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]
    );
  function popupHtml(it) {
    const rows = [];
    if (it.kind === 'school' && it.district) rows.push(esc(it.district));
    const s = [];
    if (it.pass_ela != null) s.push(`ELA ${it.pass_ela}%`);
    if (it.pass_math != null) s.push(`Math ${it.pass_math}%`);
    if (it.adj_pct != null) s.push(`Adj ${it.adj_pct}`);
    if (it.growth_pct != null) s.push(`Growth ${it.growth_pct}`);
    if (s.length) rows.push(s.join(' · '));
    const t = [];
    if (it.ppe != null) t.push('$' + it.ppe.toLocaleString() + '/pupil');
    if (it.econ != null) t.push(Math.round(it.econ * 100) + '% FRPM');
    if (it.enrollment != null) t.push(it.enrollment.toLocaleString() + ' students');
    if (t.length) rows.push(t.join(' · '));
    return `<a href="/${it.kind}/${it.cds}"><b>${esc(it.name)}</b></a><br>` + rows.join('<br>');
  }

  // Facet conjunction over the search/level-filtered list; an untouched facet
  // constrains nothing, a narrowed one also hides entities missing that value.
  let mapEligible = $derived(filtered.filter((it) => it.kind === mapKind && it.ll));
  let mapPoints = $derived.by(() => {
    const out = [];
    for (const it of mapEligible) {
      const type = entityType(it);
      if (mapKind === 'school' && !typeSel[type]) continue;
      let ok = true;
      for (const f of FACETS) {
        const b = bounds[f.key];
        const sel = fsel[f.key];
        if (!b || !sel || (sel[0] <= b[0] && sel[1] >= b[1])) continue;
        let v = it[f.key];
        if (v == null) {
          ok = false;
          break;
        }
        if (f.scale) v = v * f.scale;
        if (v < sel[0] || v > sel[1]) {
          ok = false;
          break;
        }
      }
      if (ok)
        out.push({
          ll: it.ll,
          cds: it.cds,
          kind: it.kind,
          type,
          popup: popupHtml(it)
        });
    }
    return out;
  });
  const NUM_COLS = [
    ['adj_pct', 'Adj %ile'],
    ['growth_pct', 'Growth %ile'],
    ['ppe', '$/Pupil'],
    ['econ', '% FRPM'],
    ['enrollment', 'Students']
  ];
</script>

<svelte:head><title>SchoolFactors — every California school, measured honestly</title></svelte:head>

<div class="intro">
  <h1>Every California publicly funded K-12 school.</h1>
  <p>
    {#if items}
      Detailed performance data from {items.length.toLocaleString()} schools, districts
      and counties.
    {:else}
      Loading the dataset…
    {/if}
    Both the raw data and adjustments for demographics at your fingertips.
    <a href="https://github.com/ssorkin/schoolfactors">100% open source</a>, with the
    <a href="/methodology">methodology fully documented</a>.
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

<div class="tabs" role="tablist" aria-label="View">
  <button role="tab" aria-selected={view === 'table'} class:on={view === 'table'} onclick={() => (view = 'table')}>
    Table
  </button>
  <button role="tab" aria-selected={view === 'map'} class:on={view === 'map'} onclick={openMap}>
    Map
  </button>
</div>

<div class="mappane" style:display={view === 'map' ? '' : 'none'}>
  <aside class="facets">
    <div class="fcount">
      {mapPoints.length.toLocaleString()} of {mapEligible.length.toLocaleString()}
      {mapKind === 'county' ? 'counties' : mapKind + 's'} shown
    </div>
    {#if mapKind === 'school'}
      <div class="legend">
        {#each Object.keys(TYPE_LABEL) as t (t)}
          <button
            class="lrow"
            class:off={!typeSel[t]}
            title="Click to show/hide {TYPE_LABEL[t].toLowerCase()} schools"
            onclick={() => (typeSel[t] = !typeSel[t])}
          >
            <span class="dot" style:background={TYPE_COLOR[t]}></span>
            <span class="ltext">{TYPE_LABEL[t]}</span>
          </button>
        {/each}
      </div>
    {/if}
    {#each FACETS as f (f.key)}
      {#if fsel[f.key] && bounds[f.key]}
        <RangeFacet
          label={f.label}
          tip={COLTIP[f.key] ?? ''}
          min={bounds[f.key][0]}
          max={bounds[f.key][1]}
          step={f.step ?? 1}
          bind:lo={fsel[f.key][0]}
          bind:hi={fsel[f.key][1]}
          fmt={f.fmt ?? ((v) => v)}
        />
      {/if}
    {/each}
    <button class="reset" onclick={resetFacets}>Reset filters</button>
    <p class="mapnote">
      Filters combine, and clicking a legend entry shows/hides that school type. Narrowing
      a filter also hides entities missing that value; entities without coordinates can't
      be mapped.
    </p>
  </aside>
  {#if mapOpened}
    <MapView points={mapPoints} visible={view === 'map'} fitKey={mapKind} />
  {/if}
</div>

<div class="tablewrap" style:display={view === 'table' ? '' : 'none'} {onscroll}>
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
            <td class="tnum" class:pos={it.adj_pct >= 75} class:neg={it.adj_pct <= 25}>{it.adj_pct ?? '—'}</td>
            <td class="tnum" class:pos={it.growth_pct >= 75} class:neg={it.growth_pct <= 25}>{it.growth_pct ?? '—'}</td>
            <td class="tnum">{it.ppe == null ? '—' : '$' + it.ppe.toLocaleString()}</td>
            <td class="tnum">{pct(it.econ)}</td>
            <td class="tnum students">
              {#if sparkRuns(it.enr, true).length}
                <svg viewBox="0 0 104 24" width="62" height="15" role="img">
                  <title>Census enrollment — {sparkTitle(it.enr, '', ENR_YEARS)}</title>
                  {#each sparkRuns(it.enr, true) as run, ri (ri)}
                    <polyline fill="none" stroke="#a89a80" stroke-width="2.4" points={run} />
                  {/each}
                </svg>
              {/if}
              {it.enrollment?.toLocaleString() ?? '—'}
            </td>
          </tr>
        {/each}
      {:else if loadError}
        <tr><td colspan="11" class="loading">
          Couldn't load the dataset — please reload the page.
        </td></tr>
      {:else}
        <tr><td colspan="11" class="loading">Loading the full dataset…</td></tr>
      {/if}
    </tbody>
  </table>
  {#if items && shown < sorted.length}
    <p class="more">Scroll for more — {(sorted.length - shown).toLocaleString()} rows below</p>
  {/if}
</div>

<p class="foot">
  Percentiles rank shrunken, demographically adjusted estimates among entities of the
  same kind; many are statistically indistinguishable, so small differences are noise.
  Sorting is not ranking —
  <a href="/glossary">what every column means</a> ·
  <a href="/methodology">how these numbers are made</a> ·
  <a href="/data">data sources and known issues</a> ·
  <a href="/insights">insights from the data</a>.
</p>

<style>
  .intro h1 {
    font-size: 1.8rem;
    margin: 0.8rem 0 0.4rem;
  }
  .intro p {
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
  .tabs {
    display: flex;
    gap: 0.15rem;
    border-bottom: 1px solid #e8e1d5;
    margin-bottom: 0.6rem;
  }
  .tabs button {
    border: none;
    background: none;
    font: inherit;
    font-weight: 600;
    color: #6f6a61;
    padding: 0.35rem 0.9rem;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
  }
  .tabs button.on {
    color: #b0552f;
    border-bottom-color: #b0552f;
  }
  .mappane {
    display: flex;
    gap: 0.8rem;
    align-items: stretch;
  }
  .facets {
    flex: 0 0 230px;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    background: #fffdf9;
    padding: 0.7rem 0.85rem;
    max-height: 72vh;
    overflow-y: auto;
  }
  .fcount {
    font-size: 0.82rem;
    color: #52514e;
    font-weight: 600;
    margin-bottom: 0.4rem;
    font-variant-numeric: tabular-nums;
  }
  .legend {
    margin-bottom: 0.5rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #f0ead9;
  }
  .lrow {
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
    font-size: 0.76rem;
    color: #6f6a61;
    line-height: 1.5;
    border: none;
    background: none;
    font-family: inherit;
    padding: 0;
    width: 100%;
    text-align: left;
    cursor: pointer;
  }
  .lrow:hover .ltext {
    color: #b0552f;
  }
  .lrow.off {
    opacity: 0.35;
  }
  .lrow.off .ltext {
    text-decoration: line-through;
  }
  .dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    flex: none;
    align-self: center;
  }
  .reset {
    margin-top: 0.6rem;
    border: 1px solid #d8d0c0;
    background: #faf7f2;
    border-radius: 999px;
    padding: 0.25rem 0.75rem;
    font-size: 0.82rem;
    cursor: pointer;
    color: #52514e;
  }
  .reset:hover {
    color: #b0552f;
  }
  .mapnote {
    font-size: 0.74rem;
    color: #898781;
    margin: 0.6rem 0 0;
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
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
    min-width: 950px;
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
  td.students svg {
    vertical-align: -2px;
    margin-right: 0.3rem;
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
    margin-top: 0.8rem;
  }
</style>
