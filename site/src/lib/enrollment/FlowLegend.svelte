<script>
  import { CLASS_COLOR, CLASS_LABEL, FLOW_METRICS, MOE_GATE, NO_DATA } from './metrics.js';

  let { metric = 'net_import', metrics = FLOW_METRICS, showClasses = false } = $props();
  let m = $derived(metrics[metric]);
</script>

<div class="legend">
  <div class="ramp">
    <span class="name">{m.label}</span>
    <div class="bar" style="background: {m.gradient()}"></div>
    <div class="ends"><span>{m.ends[0]}</span><span>{m.ends[1]}</span></div>
  </div>
  <div class="nodata">
    <span class="swatch" style="background: {NO_DATA}"></span>
    {#if m.moeGate}
      no data, or margin over ±{Math.round(MOE_GATE * 100)}pp (too small to estimate reliably)
    {:else}
      no data
    {/if}
  </div>
  {#if showClasses}
    <div class="types">
      {#each Object.entries(CLASS_COLOR) as [cls, color]}
        <span class="type"><span class="dot" style="background: {color}"></span>{CLASS_LABEL[cls]}</span>
      {/each}
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
</style>
