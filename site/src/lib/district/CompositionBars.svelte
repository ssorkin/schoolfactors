<script>
  /**
   * Then-vs-now composition bars for one population: per category, a light bar
   * (earlier) above a solid bar (now), shares on a fixed scale so the resident
   * and enrolled charts sit comparably side by side.
   */
  let {
    title = '',
    rows = [], // [{label, a, b}] shares 0-1
    aLabel = 'then',
    bLabel = 'now',
    color = '#2a78d6',
    tint = '#b9d2ee',
    max = 0.8
  } = $props();

  const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`);
</script>

<div class="comp">
  <p class="title">{title}</p>
  <div class="legend">
    <span class="k"><span class="sw" style="background:{tint}"></span>{aLabel}</span>
    <span class="k"><span class="sw" style="background:{color}"></span>{bLabel}</span>
  </div>
  {#each rows as r}
    <div class="row">
      <span class="lbl">{r.label}</span>
      <div class="pair">
        <div class="track">
          <div class="bar" style="width:{((r.a ?? 0) / max) * 100}%; background:{tint}"></div>
          <span class="val">{pct(r.a)}</span>
        </div>
        <div class="track">
          <div class="bar" style="width:{((r.b ?? 0) / max) * 100}%; background:{color}"></div>
          <span class="val">{pct(r.b)}</span>
        </div>
      </div>
    </div>
  {/each}
</div>

<style>
  .comp {
    min-width: 0;
  }
  .title {
    font-size: 0.9rem;
    font-weight: 600;
    color: #2b2722;
    margin: 0 0 0.2rem;
  }
  .legend {
    display: flex;
    gap: 0.9rem;
    font-size: 0.78rem;
    color: #52514e;
    margin-bottom: 0.5rem;
  }
  .k {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
  }
  .sw {
    width: 11px;
    height: 11px;
    border-radius: 3px;
    display: inline-block;
  }
  .row {
    display: grid;
    grid-template-columns: 8.5rem 1fr;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }
  .lbl {
    font-size: 0.84rem;
    color: #2b2722;
    text-align: right;
  }
  .pair {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .track {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }
  .bar {
    height: 12px;
    border-radius: 0 4px 4px 0;
    min-width: 2px;
  }
  .val {
    font-size: 0.75rem;
    color: #52514e;
    font-variant-numeric: tabular-nums;
  }
  @media (max-width: 560px) {
    .row {
      grid-template-columns: 1fr;
      gap: 0.1rem;
    }
    .lbl {
      text-align: left;
    }
  }
</style>
