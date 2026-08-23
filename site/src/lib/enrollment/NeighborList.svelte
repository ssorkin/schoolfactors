<script>
  import { onMount } from 'svelte';
  import { getIndex } from './data.js';
  import { FLOW_METRICS } from './metrics.js';

  /**
   * Neighboring districts with their OWN net rates — honest counterparty context
   * for a district's residual. Deliberately NOT a pairwise flow allocation: no
   * public data observes who exchanges students with whom, so we show where the
   * surrounding surpluses and deficits are and let the geography speak.
   */
  let { neighbors = [] } = $props();

  const DTYPE_WORD = { u: 'unified', e: 'elementary', h: 'high school' };
  const m = FLOW_METRICS.net_import;
  let rows = $state([]);

  onMount(async () => {
    const index = await getIndex();
    rows = neighbors
      .map((g) => index.byGeoid.get(g))
      .filter((r) => r && r.net_rate != null)
      .sort((a, b) => b.net_rate - a.net_rate);
  });

  const barW = (v) => Math.min(48, Math.abs(v) * 200);
</script>

{#if rows.length}
  <ul class="neigh">
    {#each rows as r}
      <li>
        <span class="name">
          {#if r.cds}
            <a href="/enrollment/district/{r.cds}">{r.name}</a>
          {:else}
            {r.name}
          {/if}
          <span class="dtype">{DTYPE_WORD[r.dtype]}</span>
        </span>
        <span class="bar">
          <span class="zero"></span>
          <span
            class="fill"
            class:imp={r.net_rate >= 0}
            class:exp={r.net_rate < 0}
            style="width: {barW(r.net_rate)}px; {r.net_rate >= 0
              ? 'left: 50%'
              : `right: 50%`}"
          ></span>
        </span>
        <span class="val" class:impt={r.net_rate >= 0} class:expt={r.net_rate < 0}>
          {m.fmt(r.net_rate)}
          {#if m.moeGate(r)}<span class="est">wide margin</span>{/if}
        </span>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .neigh {
    list-style: none;
    margin: 0.4rem 0 0;
    padding: 0;
    font-size: 0.86rem;
  }
  li {
    display: grid;
    grid-template-columns: 1fr 110px 110px;
    align-items: center;
    gap: 0.6rem;
    padding: 0.22rem 0;
    border-bottom: 1px solid #f1ece1;
  }
  .name a {
    color: #1c5cab;
    text-decoration: none;
  }
  .name a:hover {
    text-decoration: underline;
  }
  .dtype {
    color: #898781;
    font-size: 0.75rem;
    margin-left: 0.35rem;
  }
  .bar {
    position: relative;
    height: 10px;
    background: #f6f1e7;
    border-radius: 5px;
    overflow: hidden;
  }
  .zero {
    position: absolute;
    left: 50%;
    top: 0;
    bottom: 0;
    width: 1px;
    background: #d7cfc0;
  }
  .fill {
    position: absolute;
    top: 1px;
    bottom: 1px;
    border-radius: 3px;
  }
  .fill.imp {
    background: #1c5cab;
  }
  .fill.exp {
    background: #9a3412;
  }
  .val {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  .val.impt {
    color: #1c5cab;
  }
  .val.expt {
    color: #9a3412;
  }
  .est {
    display: block;
    color: #898781;
    font-size: 0.7rem;
  }
</style>
