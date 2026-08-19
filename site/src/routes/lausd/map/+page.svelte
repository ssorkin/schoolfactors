<script>
  import { onMount } from 'svelte';
  import DistrictMap from '$lib/district/DistrictMap.svelte';
  import MapMultiples from '$lib/district/MapMultiples.svelte';
  import { getSchools } from '$lib/district/lausdData.js';
  import { entityType, TYPE_LABEL } from '$lib/maptypes.js';
  import { dataUrl } from '$lib/data.js';

  let schools = $state([]);
  let demographics = $state(null);
  onMount(async () => {
    try {
      schools = await getSchools();
    } catch {
      /* map shows without markers */
    }
    try {
      demographics = await (await fetch(dataUrl('/data/lausd/demographics.json'))).json();
    } catch {
      /* optional */
    }
  });

  let hasDemo = $derived(demographics != null && !demographics.census_pending);

  const LEVEL_LABEL = { e: 'Elementary', m: 'Middle', h: 'High' };
  let level = $state('e');
  let showSchools = $state(true);
  let onlyNoBoundary = $state(false);
  let filter = $derived(onlyNoBoundary ? (s) => !s.has_boundary : null);

  let noBoundary = $derived(schools.filter((s) => !s.has_boundary));
  let byType = $derived.by(() => {
    const counts = new Map();
    for (const s of noBoundary) {
      const t = entityType({ kind: 'school', flags: s.flags });
      counts.set(t, (counts.get(t) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  });
</script>

<svelte:head>
  <title>LAUSD attendance areas — SchoolFactors</title>
  <meta
    name="description"
    content="LAUSD's attendance-area boundaries mapped at every level, from the district's own GIS — and the ~300 schools that have no attendance area."
  />
</svelte:head>

<h2>Attendance areas</h2>
<p>
  LAUSD's cartographers maintain a single partition of the district into 985 zones;
  each zone carries the elementary, middle, and high school that serve it, so
  dissolving the partition per level yields the attendance areas below. Boundaries
  come straight from the district's public GIS
  (<a href="https://services3.arcgis.com/9QBcCnjxM5EBVdGe/ArcGIS/rest/services"
    >LAUSD ArcGIS</a
  >), resolved to state CDS codes against LAUSD's school lookup tables.
</p>

<div class="controls">
  <div class="seg" role="group" aria-label="Boundary level">
    {#each ['e', 'm', 'h'] as lvl}
      <button class:on={level === lvl} onclick={() => (level = lvl)}>
        {LEVEL_LABEL[lvl]}
      </button>
    {/each}
  </div>
  <label class="chk">
    <input type="checkbox" bind:checked={showSchools} /> Show schools
  </label>
  <label class="chk">
    <input type="checkbox" bind:checked={onlyNoBoundary} />
    Only schools <b>without</b> an attendance area
  </label>
</div>

{#if hasDemo}
  <MapMultiples {schools} {level} {showSchools} schoolFilter={filter} />
  <p class="divnote">
    The <b>divergence</b> panel subtracts each attendance area's change in resident
    children (2010→2020 census blocks) from its zoned school's enrollment change
    (2010-11→2020-21): rust areas lost students much faster than they lost children
    (enrollment flight), gray shrank with their neighborhood (demographic
    shrinkage), blue outgrew their area (magnets and choice programs drawing from
    elsewhere). It is not a capture rate — students cross boundaries in both
    directions. Divergence correlates only weakly with the Similar Schools
    percentile, consistent with our earlier finding that enrollment tracks raw
    scores (which track demographics) more than school contribution.
  </p>
{:else}
  <DistrictMap
    {schools}
    bind:level
    bind:showSchools
    metrics={['perf']}
    schoolFilter={filter}
    showControls={false}
    height="74vh"
  />
  <p class="pending">
    Neighborhood demographics per attendance area (resident child poverty,
    race/ethnicity from census block groups) will appear here once the census
    acquisition runs — the demographic panels extend automatically.
  </p>
{/if}

<h2>Schools without an attendance area</h2>
<p>
  {noBoundary.length ? noBoundary.length.toLocaleString() : '…'} of
  {schools.length ? schools.length.toLocaleString() : '…'} active LAUSD schools have
  no attendance area: nobody is assigned to them by address. They enroll by
  application, lottery, or referral — charters, magnets, and alternative/options
  schools. Toggle the checkbox above to see where they sit on the map: many cluster
  in the same neighborhoods whose zoned schools serve the district's
  highest-poverty areas.
</p>

{#if byType.length}
  <ul class="typelist">
    {#each byType as [t, n]}
      <li><b>{n}</b> {TYPE_LABEL[t]}</li>
    {/each}
  </ul>
{/if}

<details>
  <summary>All schools without an attendance area</summary>
  <ul class="schools">
    {#each noBoundary as s}
      <li><a href="/school/{s.cds}">{s.name}</a></li>
    {/each}
  </ul>
</details>

<style>
  .controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.6rem 1.1rem;
    margin-bottom: 0.7rem;
  }
  .seg {
    display: inline-flex;
    border: 1px solid #d7cfc0;
    border-radius: 8px;
    overflow: hidden;
  }
  .seg button {
    font: inherit;
    font-size: 0.85rem;
    font-weight: 550;
    border: none;
    background: #fff;
    color: #52514e;
    padding: 0.3rem 0.7rem;
    cursor: pointer;
  }
  .seg button + button {
    border-left: 1px solid #d7cfc0;
  }
  .seg button.on {
    background: #b0552f;
    color: #fff;
  }
  .chk {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.9rem;
  }
  .pending {
    color: #6f6a61;
    font-size: 0.88rem;
    background: #fff;
    border: 1px dashed #d7cfc0;
    border-radius: 8px;
    padding: 0.6rem 0.9rem;
  }
  .divnote {
    font-size: 0.88rem;
    color: #52514e;
    margin-top: 0.8rem;
  }
  .typelist {
    columns: 2;
    max-width: 40rem;
  }
  .schools {
    columns: 3;
    font-size: 0.85rem;
  }
  @media (max-width: 720px) {
    .schools {
      columns: 1;
    }
    .typelist {
      columns: 1;
    }
  }
</style>
