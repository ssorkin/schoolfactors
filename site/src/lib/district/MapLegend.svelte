<script>
  import { METRICS, NO_DATA } from './choropleth.js';
  import { TYPE_COLOR, TYPE_LABEL } from '$lib/maptypes.js';
  import { SHAPE_GLYPH, levelShape } from '$lib/mapshapes.js';

  let { metric = 'perf', showSchools = true, level = 'e' } = $props();
  let m = $derived(METRICS[metric]);
  const LEVEL_WORD = { e: 'elementary', m: 'middle', h: 'high' };
</script>

<div class="legend">
  <div class="ramp">
    <span class="name">{m.label}</span>
    <div class="bar" style="background: {m.gradient()}"></div>
    <div class="ends"><span>{m.ends[0]}</span><span>{m.ends[1]}</span></div>
  </div>
  <div class="nodata">
    <span class="swatch" style="background: {NO_DATA}"></span>
    no attendance area or no data
  </div>
  {#if showSchools}
    <div class="types">
      {#each Object.keys(TYPE_COLOR) as t}
        <span class="type">
          <span class="dot" style="background: {TYPE_COLOR[t]}"></span>{TYPE_LABEL[t].split(' (')[0]}
        </span>
      {/each}
      <span class="shapes">
        {SHAPE_GLYPH[levelShape(level)]} {LEVEL_WORD[level]} schools · ◆ K-12 / other
      </span>
    </div>
  {/if}
</div>

<style>
  .legend {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    gap: 1rem 1.5rem;
    font-size: 0.8rem;
    color: #52514e;
    margin: 0.5rem 0 0.25rem;
  }
  .ramp {
    min-width: 220px;
  }
  .name {
    font-weight: 600;
    color: #2b2722;
  }
  .bar {
    height: 10px;
    border-radius: 5px;
    margin-top: 0.25rem;
  }
  .ends {
    display: flex;
    justify-content: space-between;
    font-size: 0.72rem;
    color: #898781;
  }
  .nodata {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }
  .swatch {
    width: 14px;
    height: 14px;
    border-radius: 4px;
    display: inline-block;
  }
  .types {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem 0.8rem;
  }
  .type {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    white-space: nowrap;
  }
  .dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;
    border: 1px solid #fff;
    box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.12);
  }
  .shapes {
    color: #898781;
    white-space: nowrap;
  }
</style>
