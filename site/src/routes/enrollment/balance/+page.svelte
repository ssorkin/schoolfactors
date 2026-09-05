<script>
  import { onMount } from 'svelte';
  import { replaceState } from '$app/navigation';
  import { getIndex } from '$lib/enrollment/data.js';
  import { MOE_GATE } from '$lib/enrollment/metrics.js';

  let index = $state(null);
  let filter = $state('all'); // all | imp | exp | balanced | persist | persist-imp | persist-exp
  let county = $state('all');
  let kind = $state('districts'); // districts | counties
  let sort = $state('rate-desc'); // rate-desc | rate-asc | res-desc | name
  let q = $state('');
  let restored = false;

  // Runs on mount AND on hashchange: hash-only URL changes (pasted links,
  // back/forward) don't remount the page, so absent params reset to defaults.
  // Reads the event's newURL when given — the router can rewrite location
  // before hashchange dispatches, but the event keeps the incoming value.
  function restoreHash(ev) {
    const hash = ev?.newURL ? new URL(ev.newURL).hash : location.hash;
    const h = new URLSearchParams(hash.slice(1));
    const f = h.get('f');
    filter = ['imp', 'exp', 'balanced', 'persist', 'persist-imp', 'persist-exp'].includes(f)
      ? f
      : 'all';
    county = h.get('c') || 'all';
    kind = h.get('k') === 'counties' ? 'counties' : 'districts';
    restored = true;
  }

  $effect(() => {
    window.addEventListener('hashchange', restoreHash);
    return () => window.removeEventListener('hashchange', restoreHash);
  });

  onMount(async () => {
    restoreHash();
    index = await getIndex();
  });

  // `lastWritten` keeps a spurious re-run (the router touches the page store
  // on popstate) from "correcting" a freshly pasted hash back to stale state.
  let lastWritten = null;
  $effect(() => {
    if (!restored) return;
    const h = new URLSearchParams();
    if (filter !== 'all') h.set('f', filter);
    if (county !== 'all') h.set('c', county);
    if (kind !== 'districts') h.set('k', kind);
    const s = h.toString();
    if (s === lastWritten) return;
    lastWritten = s;
    const target = location.pathname + location.search + (s ? '#' + s : '');
    if (target !== location.pathname + location.search + location.hash) {
      replaceState(target, {});
    }
  });

  const DTYPE_WORD = { u: 'unified', e: 'elementary', h: 'high school' };

  // Status classification mirrors the findings computation: "importer"/
  // "exporter" only when the balance clears the row's own survey margin.
  function status(r) {
    if (r.net_rate == null || r.net_moe == null) return 'none';
    if (r.net_rate > r.net_moe) return 'imp';
    if (r.net_rate < -r.net_moe) return 'exp';
    return 'balanced';
  }

  let countyNames = $derived.by(() => {
    if (!index) return new Map();
    return new Map(index.rows.filter((r) => r.dtype === 'c').map((r) => [r.geoid, r.name]));
  });

  let rows = $derived.by(() => {
    if (!index) return [];
    const needle = q.trim().toLowerCase();
    let out = index.rows.filter((r) =>
      kind === 'counties' ? r.dtype === 'c' : r.dtype !== 'c' && r.net_rate != null
    );
    if (kind === 'districts' && county !== 'all') out = out.filter((r) => r.county === county);
    if (needle) out = out.filter((r) => (r.name ?? '').toLowerCase().includes(needle));
    if (filter !== 'all') {
      out = out.filter((r) => {
        const st = status(r);
        if (filter === 'imp') return st === 'imp';
        if (filter === 'exp') return st === 'exp';
        if (filter === 'balanced') return st === 'balanced';
        if (filter === 'persist') return r.persist != null;
        if (filter === 'persist-imp') return r.persist === 1;
        if (filter === 'persist-exp') return r.persist === -1;
        return true;
      });
    }
    const cmp = {
      'rate-desc': (a, b) => (b.net_rate ?? -9) - (a.net_rate ?? -9),
      'rate-asc': (a, b) => (a.net_rate ?? 9) - (b.net_rate ?? 9),
      'res-desc': (a, b) => (b.res ?? 0) - (a.res ?? 0),
      name: (a, b) => (a.name ?? '').localeCompare(b.name ?? '')
    }[sort];
    return out.sort(cmp);
  });

  const fmtRate = (r) =>
    r.net_rate == null
      ? '—'
      : `${r.net_rate > 0 ? '+' : ''}${(r.net_rate * 100).toFixed(1)}% ± ${((r.net_moe ?? 0) * 100).toFixed(1)}`;
  const STATUS_WORD = {
    imp: 'net importer',
    exp: 'net exporter',
    balanced: 'within margin',
    none: '—'
  };
</script>

<svelte:head>
  <title>Every balance, listed — modeled net enrollment balances | SchoolFactors</title>
  <meta
    name="description"
    content="Every California district and county's modeled net enrollment balance in one sortable table, with survey margins and the persistently imbalanced flagged."
  />
</svelte:head>

<h1>Every balance, listed</h1>
<p class="lede">
  The latest modeled net enrollment balance for every district area (and every
  county), with its survey margin. A district counts as a net importer or
  exporter only when its balance clears its own margin; "persistent" means the
  balance was significant with the same sign — and the margin stayed within
  the ±15pp reliability gate — in all three non-overlapping survey windows
  (2010–14, 2015–19, 2020–24). District balances are
  within-county physical flows; county balances include cross-county and
  remote accounting. Modeled net balances — never observed transfers.
</p>

{#if index}
  <div class="filters">
    <label>
      Show
      <select bind:value={kind}>
        <option value="districts">districts</option>
        <option value="counties">counties</option>
      </select>
    </label>
    <label>
      Status
      <select bind:value={filter}>
        <option value="all">all</option>
        <option value="imp">net importers</option>
        <option value="exp">net exporters</option>
        <option value="balanced">within margin</option>
        <option value="persist">persistent (either)</option>
        <option value="persist-imp">persistent importers</option>
        <option value="persist-exp">persistent exporters</option>
      </select>
    </label>
    {#if kind === 'districts'}
      <label>
        County
        <select bind:value={county}>
          <option value="all">all</option>
          {#each [...countyNames.entries()].sort((a, b) => a[1].localeCompare(b[1])) as [code, name]}
            <option value={code}>{name}</option>
          {/each}
        </select>
      </label>
    {/if}
    <label>
      Sort by
      <select bind:value={sort}>
        <option value="rate-desc">balance (importers first)</option>
        <option value="rate-asc">balance (exporters first)</option>
        <option value="res-desc">resident children</option>
        <option value="name">name</option>
      </select>
    </label>
    <input class="q" type="search" placeholder="Name…" bind:value={q} />
    <span class="tally">{rows.length.toLocaleString()} {kind}</span>
  </div>

  <table class="bal">
    <thead>
      <tr>
        <th>{kind === 'counties' ? 'County' : 'District'}</th>
        {#if kind === 'districts'}
          <th>Type</th>
          <th>County</th>
        {/if}
        <th class="num">Resident children</th>
        <th class="num">Net balance (est.)</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      {#each rows as r (r.geoid)}
        {@const st = status(r)}
        <tr class:gated={r.net_moe != null && r.net_moe > MOE_GATE}>
          <td>
            {#if r.dtype === 'c'}
              <a href="/enrollment/county/{r.cds}">{r.name}</a>
            {:else if r.cds}
              <a href="/enrollment/district/{r.cds}">{r.name}</a>
            {:else}{r.name}{/if}
          </td>
          {#if kind === 'districts'}
            <td class="dim">{DTYPE_WORD[r.dtype] ?? ''}</td>
            <td class="dim">{(countyNames.get(r.county) ?? '').replace(' County', '')}</td>
          {/if}
          <td class="num">{r.res?.toLocaleString() ?? '—'}</td>
          <td class="num" class:impt={st === 'imp'} class:expt={st === 'exp'}>{fmtRate(r)}</td>
          <td class="dim">
            {STATUS_WORD[st]}{#if r.persist != null}
              <span class="chip" class:cimp={r.persist === 1} class:cexp={r.persist === -1}>
                persistent {r.persist === 1 ? 'importer' : 'exporter'}
              </span>
            {/if}
            {#if r.net_moe != null && r.net_moe > MOE_GATE}
              <span class="wide">wide margin</span>
            {/if}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
  <p class="mapnote">
    Margins are ±90% survey margins as a share of resident children; rows whose
    margin exceeds ±{Math.round(MOE_GATE * 100)}pp are grayed (too small to
    estimate reliably — shown for completeness, not for reading).
  </p>
{:else}
  <p class="loading">Loading…</p>
{/if}

<style>
  h1 {
    margin: 0.4rem 0 0.2rem;
  }
  .lede {
    max-width: 62rem;
    color: #52514e;
  }
  .filters {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.6rem 1.1rem;
    margin: 0.8rem 0 0.6rem;
    font-size: 0.88rem;
  }
  .filters select,
  .filters input {
    font: inherit;
    font-size: 0.85rem;
    margin-left: 0.3rem;
  }
  .q {
    padding: 0.25rem 0.5rem;
    border: 1px solid #d7cfc0;
    border-radius: 6px;
    min-width: 10rem;
  }
  .tally {
    color: #6f6a61;
    font-size: 0.82rem;
  }
  .bal {
    width: 100%;
    max-width: 62rem;
    border-collapse: collapse;
    font-size: 0.86rem;
  }
  .bal th {
    text-align: left;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: #898781;
    padding: 0.3rem 0.5rem;
    border-bottom: 1px solid #e8e1d5;
  }
  .bal td {
    padding: 0.26rem 0.5rem;
    border-bottom: 1px solid #f1ece1;
  }
  .bal tbody tr:hover td {
    background: #f3ede2;
  }
  .bal .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .bal a {
    color: #1c5cab;
    text-decoration: none;
  }
  .bal a:hover {
    text-decoration: underline;
  }
  .bal .dim {
    color: #6f6a61;
  }
  .bal .impt {
    color: #1c5cab;
    font-weight: 600;
  }
  .bal .expt {
    color: #9a3412;
    font-weight: 600;
  }
  tr.gated td {
    color: #b5aea1;
  }
  tr.gated td a {
    color: #8fa8c4;
  }
  .chip {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 600;
    border-radius: 999px;
    padding: 0.05rem 0.5rem;
    margin-left: 0.4rem;
    white-space: nowrap;
  }
  .chip.cimp {
    background: #e3edf9;
    color: #1c5cab;
  }
  .chip.cexp {
    background: #f9e9e0;
    color: #9a3412;
  }
  .wide {
    font-size: 0.72rem;
    color: #b5aea1;
    margin-left: 0.4rem;
  }
  .mapnote {
    font-size: 0.78rem;
    color: #898781;
    margin: 0.4rem 0 0;
    max-width: 62rem;
  }
  .loading {
    color: #898781;
  }
</style>
