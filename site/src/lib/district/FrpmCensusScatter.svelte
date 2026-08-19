<script>
  /**
   * Statewide scatter: each dot is one CA district, placed by the share of its
   * resident children under 185% of poverty (census, horizontal) and the share of
   * its enrolled students who are FRPM-eligible (district-reported, vertical).
   * Dots above the y=x line report more poverty than the census counts — nearly all
   * of them, by design of the two measures. Dot area tracks enrollment; dots link
   * to district pages; hovering names the district.
   */
  let { districts = [], highlight = '19647330000000' } = $props();

  const W = 760;
  const H = 560;
  const M = { top: 16, right: 18, bottom: 46, left: 54 };

  let rows = $derived(
    districts.filter((d) => d.frpm != null && d.p185 != null && (d.enr_5_17 ?? 0) > 0)
  );
  const X = (v) => M.left + (v / 100) * (W - M.left - M.right);
  const Y = (v) => M.top + (1 - v / 100) * (H - M.top - M.bottom);
  const R = (enr) => Math.max(2, Math.min(24, Math.sqrt(enr) / 28));

  let hover = $state(null);
  let hl = $derived(rows.find((d) => d.cds === highlight));
</script>

<div class="scatterwrap">
  <svg viewBox="0 0 {W} {H}" role="img" aria-label="District FRPM rate vs census child poverty rate">
    {#each [0, 25, 50, 75, 100] as t}
      <line x1={X(t)} y1={M.top} x2={X(t)} y2={H - M.bottom} stroke="#e1e0d9" />
      <line x1={M.left} y1={Y(t)} x2={W - M.right} y2={Y(t)} stroke="#e1e0d9" />
      <text x={X(t)} y={H - M.bottom + 18} text-anchor="middle" class="tick">{t}%</text>
      <text x={M.left - 8} y={Y(t) + 4} text-anchor="end" class="tick">{t}%</text>
    {/each}
    <line x1={X(0)} y1={Y(0)} x2={X(100)} y2={Y(100)} stroke="#898781" stroke-dasharray="5 4" />
    <text x={X(88)} y={Y(88) + 16} class="anno">equal shares</text>

    {#each rows as d}
      {#snippet dot()}
        <circle
          cx={X(d.p185 * 100)}
          cy={Y(d.frpm * 100)}
          r={R(d.enr_5_17)}
          fill={d.cds === highlight ? '#eb6834' : '#2a78d6'}
          fill-opacity={d.cds === highlight ? 0.95 : 0.3}
          stroke={d.cds === highlight ? '#ffffff' : 'none'}
          stroke-width="2"
          style:cursor={d.has_page ? 'pointer' : 'default'}
          onmouseenter={() => (hover = d)}
          onmouseleave={() => (hover = null)}
        />
      {/snippet}
      {#if d.has_page}
        <a href="/district/{d.cds}">{@render dot()}</a>
      {:else}
        {@render dot()}
      {/if}
    {/each}
    {#if hl}
      <text x={X(hl.p185 * 100)} y={Y(hl.frpm * 100) - R(hl.enr_5_17) - 6}
        text-anchor="middle" class="hllabel">LAUSD</text>
    {/if}

    <text x={(M.left + W - M.right) / 2} y={H - 8} text-anchor="middle" class="axis">
      Resident children under 185% of poverty (census)
    </text>
    <text
      transform="rotate(-90 14 {(M.top + H - M.bottom) / 2})"
      x="14"
      y={(M.top + H - M.bottom) / 2}
      text-anchor="middle"
      class="axis"
    >
      Enrolled students FRPM-eligible (district-reported)
    </text>
  </svg>
  <p class="caption">
    {#if hover}
      <b>{hover.name}</b>: {Math.round(hover.frpm * 100)}% FRPM vs
      {Math.round(hover.p185 * 100)}% census poverty
      ({hover.ratio == null ? '—' : `${hover.ratio.toFixed(2)}× the census rate`}) ·
      {hover.enr_5_17.toLocaleString()} students 5–17
    {:else}
      {rows.length.toLocaleString()} districts · dot area tracks enrollment · click a
      dot for its district page
    {/if}
  </p>
</div>

<style>
  .scatterwrap {
    overflow-x: auto;
  }
  svg {
    width: 100%;
    max-width: 860px;
    height: auto;
    display: block;
    background: #fcfcfb;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
  }
  circle {
    cursor: pointer;
  }
  .tick {
    font-size: 11px;
    fill: #898781;
  }
  .axis {
    font-size: 12.5px;
    fill: #52514e;
    font-weight: 550;
  }
  .anno {
    font-size: 11px;
    fill: #898781;
  }
  .hllabel {
    font-size: 12px;
    font-weight: 700;
    fill: #b0552f;
  }
  .caption {
    font-size: 0.85rem;
    color: #52514e;
    min-height: 1.4em;
  }
</style>
