<script>
  import DistrictMap from './DistrictMap.svelte';
  import { METRICS, NO_DATA } from './choropleth.js';

  /**
   * Small multiples: one map per metric (2 rows x 3 columns on wide screens),
   * pan/zoom synchronized across all panels. School markers render only on the
   * performance panel — the demographic panels stay clean choropleths.
   */
  let {
    schools = [],
    metrics = ['perf', 'p185', 'his', 'wht', 'blk', 'asn'],
    level = 'e',
    showSchools = true,
    schoolFilter = null,
    height = '340px'
  } = $props();

  const maps = [];
  let syncing = false;
  function register(map) {
    maps.push(map);
    map.on('move', () => {
      if (syncing) return;
      syncing = true;
      const c = map.getCenter();
      const z = map.getZoom();
      for (const other of maps) {
        if (other !== map) other.setView(c, z, { animate: false });
      }
      syncing = false;
    });
  }
</script>

<div class="grid">
  {#each metrics as key (key)}
    <div class="panel">
      <div class="head">
        <span class="name">{METRICS[key].label}</span>
        <span class="ramp" style="background: {METRICS[key].gradient()}"></span>
      </div>
      <DistrictMap
        {schools}
        {level}
        metric={key}
        metrics={[key]}
        showSchools={showSchools && key === 'perf'}
        {schoolFilter}
        showControls={false}
        showLegend={false}
        {height}
        onmapready={register}
      />
    </div>
  {/each}
</div>
<p class="note">
  Panels pan and zoom together. Gray areas
  <span class="swatch" style="background: {NO_DATA}"></span>
  have no attendance area or no data; school markers (performance panel only) are
  filled by Similar Schools %ile.
</p>

<style>
  .grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.9rem 0.8rem;
  }
  @media (max-width: 1050px) {
    .grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
  @media (max-width: 700px) {
    .grid {
      grid-template-columns: 1fr;
    }
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    margin-bottom: 0.25rem;
  }
  .name {
    font-size: 0.82rem;
    font-weight: 600;
    color: #2b2722;
    line-height: 1.25;
  }
  .ramp {
    flex: 0 0 56px;
    height: 8px;
    border-radius: 4px;
  }
  .note {
    font-size: 0.82rem;
    color: #6f6a61;
    margin-top: 0.6rem;
  }
  .swatch {
    display: inline-block;
    width: 11px;
    height: 11px;
    border-radius: 3px;
    vertical-align: -1px;
  }
</style>
