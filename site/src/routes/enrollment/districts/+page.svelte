<script>
  import { onMount } from 'svelte';
  import { goto, replaceState } from '$app/navigation';
  import SearchBox from '$lib/SearchBox.svelte';
  import FlowMap from '$lib/enrollment/FlowMap.svelte';
  import FlowLegend from '$lib/enrollment/FlowLegend.svelte';
  import { getIndex } from '$lib/enrollment/data.js';
  import { FLOW_METRICS } from '$lib/enrollment/metrics.js';

  let metric = $state('net_import');
  let band = $state('k8');
  let yearIdx = $state(-1);
  let enrollDistricts = $state(new Set());
  let enrollCounties = $state(new Set());
  let restored = false;

  // Shareable view state in the URL fragment (homepage pattern): restored once on
  // mount, kept current afterwards; the guard keeps the first effect run from
  // clobbering an incoming URL. Pre-restructure /enrollment links with district
  // params redirect here with the hash intact.
  onMount(async () => {
    const h = new URLSearchParams(location.hash.slice(1));
    if (h.get('m') && FLOW_METRICS[h.get('m')]) metric = h.get('m');
    if (['k8', 'hs'].includes(h.get('b'))) band = h.get('b');
    if (h.get('y') != null && h.get('y') !== '') yearIdx = +h.get('y');
    restored = true;
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

  $effect(() => {
    if (!restored) return;
    const h = new URLSearchParams();
    if (metric !== 'net_import') h.set('m', metric);
    if (band !== 'k8') h.set('b', band);
    if (yearIdx >= 0) h.set('y', String(yearIdx));
    const s = h.toString();
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
</script>

<svelte:head>
  <title>District enrollment map — modeled net balances | SchoolFactors</title>
  <meta
    name="description"
    content="Every California district area's modeled net enrollment balance — resident children vs. seats, within-county physical flows, 2005–2024."
  />
</svelte:head>

<h1>Every district's net enrollment balance</h1>
<p class="lede">
  Each district area, compared two ways: resident children attending public
  school (Census Bureau surveys) and the students its schools actually seat
  (state census-day counts). District balances are pure within-county physical
  flows — remote programs are removed from the geography and each county's
  measured remote &amp; out-of-county enrollment is allocated first, so
  district numbers sum to zero in every county. Cross-county and remote
  accounting lives on the <a href="/enrollment">statewide page</a> and each
  county page.
</p>

<div class="search">
  <SearchBox placeholder="Find a district or county…" kinds={['district', 'county']} {onselect} />
</div>

<FlowMap mode="state" bind:metric bind:band bind:yearIdx />
<FlowLegend {metric} />

<section class="how">
  <h2>Reading this map</h2>
  <ul>
    <li>
      <b>Blue = net importer</b> (more seats filled than resident public-school
      children), <b>rust = net exporter</b>. Both are modeled net rates with
      survey margins; gray areas are too small to estimate reliably.
    </li>
    <li>
      The <b>grade-band toggle</b> exists because part of the state is organized as
      separate elementary and high-school districts covering the same territory:
      each view tiles the state once, with unified districts appearing in both.
    </li>
    <li>
      5-year survey windows overlap, so <b>window-to-window changes are not annual
      signal</b>. District pages overlay true annual data where the Census Bureau
      publishes it.
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
  .lede a {
    color: #1c5cab;
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
</style>
