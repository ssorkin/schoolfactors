<script>
  /**
   * Paired horizontal bars: resident population vs enrolled students, share by
   * share. Two fixed series colors (resident blue, enrolled orange — the site's
   * validated pair), value labels on every bar since there are few marks.
   */
  let {
    rows = [], // [{label, a, b}] shares 0-1; a = resident, b = enrolled
    aLabel = 'Residents',
    bLabel = 'Enrolled students'
  } = $props();

  const A = '#2a78d6';
  const B = '#eb6834';
  let max = $derived(Math.max(0.15, ...rows.flatMap((r) => [r.a ?? 0, r.b ?? 0])));
  const pct = (v) => (v == null ? 'n/a' : `${Math.round(v * 100)}%`);
</script>

<div class="bars">
  <div class="legend">
    <span class="k"><span class="sw" style="background:{A}"></span>{aLabel}</span>
    <span class="k"><span class="sw" style="background:{B}"></span>{bLabel}</span>
  </div>
  {#each rows as r}
    <div class="row">
      <span class="lbl">{r.label}</span>
      <div class="pair">
        <div class="track">
          <div class="bar" style="width:{((r.a ?? 0) / max) * 100}%; background:{A}"></div>
          <span class="val">{pct(r.a)}</span>
        </div>
        <div class="track">
          <div class="bar" style="width:{((r.b ?? 0) / max) * 100}%; background:{B}"></div>
          <span class="val">{pct(r.b)}</span>
        </div>
      </div>
    </div>
  {/each}
</div>

<style>
  .bars {
    max-width: 640px;
  }
  .legend {
    display: flex;
    gap: 1rem;
    font-size: 0.82rem;
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
    grid-template-columns: 9.5rem 1fr;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 0.55rem;
  }
  .lbl {
    font-size: 0.88rem;
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
    gap: 0.4rem;
  }
  .bar {
    height: 13px;
    border-radius: 0 4px 4px 0;
    min-width: 2px;
  }
  .val {
    font-size: 0.78rem;
    color: #52514e;
  }
  @media (max-width: 560px) {
    .row {
      grid-template-columns: 1fr;
      gap: 0.15rem;
    }
    .lbl {
      text-align: left;
    }
  }
</style>
