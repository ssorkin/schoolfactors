<script>
  import { onMount } from 'svelte';
  import { goto, replaceState } from '$app/navigation';
  import SearchBox from '$lib/SearchBox.svelte';
  import FlowMap from '$lib/enrollment/FlowMap.svelte';
  import FlowLegend from '$lib/enrollment/FlowLegend.svelte';
  import { getIndex } from '$lib/enrollment/data.js';
  import { COUNTY_METRICS } from '$lib/enrollment/metrics.js';

  let { data } = $props();
  let metric = $state('net_import');
  let yearIdx = $state(-1);
  let enrollDistricts = $state(new Set());
  let enrollCounties = $state(new Set());
  let restored = false;

  // Shareable view state in the URL fragment (homepage pattern): restored once
  // on mount, kept current afterwards. Links minted before the county-centric
  // landing carry district-map params (a band, or a district-only metric) —
  // those views now live at /enrollment/districts, hash intact.
  // Runs on mount AND on hashchange: hash-only URL changes (pasted links,
  // back/forward) don't remount the page, so absent params reset to defaults.
  // Reads the event's newURL when given — the router can rewrite location
  // before hashchange dispatches, but the event keeps the incoming value.
  function restoreHash(ev) {
    const hash = ev?.newURL ? new URL(ev.newURL).hash : location.hash;
    const h = new URLSearchParams(hash.slice(1));
    if (h.get('b') || ['seats_chg', 'perf'].includes(h.get('m'))) {
      goto(`/enrollment/districts${hash}`, { replaceState: true });
      return;
    }
    metric = h.get('m') && COUNTY_METRICS[h.get('m')] ? h.get('m') : 'net_import';
    yearIdx = h.get('y') != null && h.get('y') !== '' ? +h.get('y') : -1;
    restored = true;
  }

  $effect(() => {
    window.addEventListener('hashchange', restoreHash);
    return () => window.removeEventListener('hashchange', restoreHash);
  });

  onMount(async () => {
    restoreHash();
    if (!restored) return; // redirected to /enrollment/districts
    const index = await getIndex();
    enrollDistricts = new Set(
      index.rows
        .filter((r) => r.dtype !== 'c' && r.cds && r.net_rate != null)
        .map((r) => r.cds)
    );
    enrollCounties = new Set(
      index.rows.filter((r) => r.dtype === 'c').map((r) => r.cds)
    );
  });

  // `lastWritten` keeps a spurious re-run (the router touches the page store
  // on popstate) from "correcting" a freshly pasted hash back to stale state.
  let lastWritten = null;
  $effect(() => {
    if (!restored) return;
    const h = new URLSearchParams();
    if (metric !== 'net_import') h.set('m', metric);
    if (yearIdx >= 0) h.set('y', String(yearIdx));
    const s = h.toString();
    if (s === lastWritten) return;
    lastWritten = s;
    // Only touch the URL when it actually changes: an unconditional
    // replaceState here fires during hydration, before the router is ready,
    // and aborts hydration (orphaning this page's DOM on later navigations).
    const target = location.pathname + location.search + (s ? '#' + s : '');
    if (target !== location.pathname + location.search + location.hash) {
      replaceState(target, {});
    }
  });

  function onselect(it) {
    if (it.kind === 'county' && enrollCounties.has(it.cds)) {
      goto(`/enrollment/county/${it.cds}`);
    } else if (it.kind === 'district' && enrollDistricts.has(it.cds)) {
      goto(`/enrollment/district/${it.cds}`);
    } else {
      // COEs, SBE charters, and unmapped districts have no enrollment page.
      goto(`/${it.kind}/${it.cds}`);
    }
  }

  const n = (v) => (v == null ? '—' : Math.round(v).toLocaleString());
  const nK = (v) => (v == null ? '—' : `${Math.round(v / 1000).toLocaleString()},000`);
  const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`);
  const pct1 = (v) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`);
  let f = $derived(data.findings);
  let win = $derived(f ? `${f.window[0]}–${f.window[1]}` : '');
  let remoteLast = $derived(f?.remote?.series?.at(-1) ?? null);
  let remoteFirst = $derived(f?.remote?.series?.[0] ?? null);
  let nlTop = $derived(f?.nonlocal?.top?.[0] ?? null);
</script>

<svelte:head>
  <title>Enrollment flows — where students live vs. where they enroll | SchoolFactors</title>
  <meta
    name="description"
    content="California public-school enrollment as a statewide accounting: resident children vs. seats by county and district, the remote-program sector, and modeled net balances, 2005–2024."
  />
</svelte:head>

<h1>Where students live vs. where they enroll</h1>
<p class="lede">
  California's public-school enrollment does not map cleanly onto the geography
  of its children. Some of the gap is ordinary interdistrict attendance; some is
  charter draw; and a growing remote sector — virtual charters and
  non-classroom-based programs — can administratively count students in
  counties far from their homes. Once enrollment can be booked to a remote
  program elsewhere, no district or county's ledger closes on its own: the
  accounting only balances at the state line. These pages model the whole state
  as one constrained accounting system, separating those layers as far as
  public data allow — as modeled net balances with survey margins, never as
  observed individual transfers.
</p>

{#if f}
  <section class="findings">
    <h2>What the statewide accounting shows ({win})</h2>
    <ul>
      <li>
        <b>The remote sector roughly tripled.</b> Virtual charters and
        non-classroom programs enrolled ~{nK(remoteLast?.[1])} students in
        {win} — about {pct1(remoteLast?.[2])} of statewide enrollment, up from
        {pct1(remoteFirst?.[2])} in {f.remote.series[0][0] - 4}–{f.remote.series[0][0]}
        — and grew through every survey window, even as total enrollment fell.
        {#if f.remote.current}
          By census day {f.remote.current[0] - 1}–{String(f.remote.current[0]).slice(2)}
          it reached ~{nK(f.remote.current[1])} students
          ({pct1(f.remote.current[2])} of the state).
        {/if}
        <a href="/enrollment/programs">Browse the programs →</a>
      </li>
      <li>
        <b>Most places are near balance.</b>
        {pct(f.balance.within_moe_share)} of the {n(f.balance.n)} modeled
        district areas sit within their own survey margin of zero, and
        {pct(f.balance.res_within5_share)} of resident public-school children
        live in a district whose modeled balance is within ±5%. Counties are
        tighter still: {f.counties.within2} of {f.counties.n} are within ±2%.
        <a href="/enrollment/balance">Every district's balance →</a>
      </li>
      <li>
        <b>Some imbalances are chronic, not noise.</b> Among the
        {n(f.persistence.n)} districts estimated reliably across all three
        non-overlapping survey windows, {f.persistence.importers} were
        significant net importers in every window and
        {f.persistence.exporters} significant net exporters — persistent
        patterns that survive a decade of independent samples. (Many tiny
        rural districts also chronically seat far more students than their
        handful of resident children — real, but too small to state as rates.)
        <a href="/enrollment/balance#f=persist">See who they are →</a>
      </li>
      {#if nlTop}
        <li>
          <b>Administrative enrollment can dwarf a district's resident base.</b>
          {nlTop[0]} ({nlTop[1]}) administers ~{n(nlTop[4])} students against
          ~{n(nlTop[3])} resident children — {nlTop[2]}× — bookkeeping for the
          remote programs it authorizes, not local attendance. The model
          separates that administrative draw from physical enrollment; the
          median district administers {f.nonlocal.median}× its resident base.
          <a href="/enrollment/programs">The full table →</a>
        </li>
      {/if}
      <li>
        <b>Cross-county flows are few and stable.</b> The largest matched
        adjacent-county flows in {win}:
        {#each f.counties.pairs.slice(0, 3) as [e, i, est], idx}{idx ? '; ' : ''}{e.replace(' County', '')} → {i.replace(' County', '')} (~{n(est)}){/each}. Pairwise
        <i>district</i> flows are deliberately not published: no public data
        observes them, and a model's guesses would be its most quotable, least
        supported numbers.
        <a href="/enrollment/methodology#nets-only">Why nets only →</a>
      </li>
    </ul>
  </section>
{/if}

<div class="search">
  <SearchBox placeholder="Find a district or county…" kinds={['district', 'county']} {onselect} />
</div>

<FlowMap mode="state" geo="counties" metrics={COUNTY_METRICS} bind:metric bind:yearIdx />
<FlowLegend {metric} metrics={COUNTY_METRICS} />

<section class="how">
  <h2>Reading this map</h2>
  <ul>
    <li>
      <b>Blue = net importer</b> (more seats filled than resident public-school
      children), <b>rust = net exporter</b>. County balances are modeled net
      rates with survey margins and include cross-county administrative
      enrollment; click a county for its full ledger — remote programs,
      adjacent-county flows, and the survey-alignment remainder.
    </li>
    <li>
      District-level balances (within-county physical flows, elementary and
      high-school bands) live on the
      <a href="/enrollment/districts">district map</a> and on each county page.
    </li>
    <li>
      5-year survey windows overlap, so <b>window-to-window changes are not
      annual signal</b>. Detail pages overlay true annual data where the Census
      Bureau publishes it.
    </li>
  </ul>
</section>

<style>
  h1 {
    margin: 0.4rem 0 0.2rem;
  }
  .lede {
    max-width: 62rem;
    color: #52514e;
  }
  .findings {
    max-width: 62rem;
    background: #f7f3ea;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    padding: 0.9rem 1.2rem;
    margin: 1rem 0;
  }
  .findings h2 {
    font-size: 1.05rem;
    margin: 0 0 0.5rem;
  }
  .findings li {
    margin: 0.45rem 0;
    color: #2b2722;
  }
  .findings a {
    color: #1c5cab;
    text-decoration: none;
    white-space: nowrap;
  }
  .search {
    max-width: 30rem;
    margin: 0.8rem 0 1rem;
  }
  .how {
    margin-top: 1.6rem;
    max-width: 62rem;
  }
  .how h2 {
    font-size: 1.05rem;
  }
  .how li {
    margin: 0.35rem 0;
    color: #52514e;
  }
  .how a {
    color: #1c5cab;
  }
</style>
