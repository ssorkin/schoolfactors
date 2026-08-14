<script>
  /**
   * Tested-population blend over time (shares of tested students), aggregated
   * across grades per year. Four direct-labeled categorical series; full detail
   * for all tracked groups in the table below.
   */
  let { blend = [] } = $props();

  const SERIES = [
    { key: 'share_econ_dis', label: 'Econ. disadvantaged', color: '#2a78d6' },
    { key: 'share_hispanic', label: 'Hispanic/Latino', color: '#eb6834' },
    { key: 'share_el', label: 'English learners', color: '#1baf7a' },
    { key: 'share_white', label: 'White', color: '#eda100' }
  ];
  const ALL = [
    ['share_econ_dis', 'Econ. disadvantaged'],
    ['share_el', 'English learners'],
    ['share_swd', 'Disabilities'],
    ['share_hispanic', 'Hispanic/Latino'],
    ['share_white', 'White'],
    ['share_asian', 'Asian'],
    ['share_black', 'Black']
  ];

  let hover = $state(null);

  let byYear = $derived.by(() => {
    const m = new Map();
    for (const r of blend) {
      if (!m.has(r.year)) m.set(r.year, []);
      m.get(r.year).push(r);
    }
    const out = [];
    for (const [year, rows] of [...m.entries()].sort((a, b) => a[0] - b[0])) {
      const n = rows.reduce((s, r) => s + r.n, 0);
      const rec = { year, n };
      for (const [k] of ALL) {
        let wsum = 0;
        let w = 0;
        for (const r of rows) {
          if (r[k] != null) {
            wsum += r[k] * r.n;
            w += r.n;
          }
        }
        rec[k] = w > 0 ? wsum / w : null;
      }
      out.push(rec);
    }
    return out;
  });

  const W = 820;
  const H = 340;
  const M = { top: 14, right: 150, bottom: 40, left: 46 };
  let years = $derived(byYear.map((r) => r.year));
  const sx = (yr) =>
    M.left +
    ((yr - (years[0] ?? 2015)) / Math.max(1, (years.at(-1) ?? 2025) - (years[0] ?? 2015))) *
      (W - M.left - M.right);
  const sy = (v) => M.top + (1 - v) * (H - M.top - M.bottom);
</script>

{#if byYear.length > 1}
  <div class="chart">
    <svg viewBox="0 0 {W} {H}" role="img" aria-label="Tested-population composition over time">
      {#each [0, 0.25, 0.5, 0.75, 1] as t (t)}
        <line x1={M.left} x2={W - M.right} y1={sy(t)} y2={sy(t)} stroke="#eee9df" />
        <text x={M.left - 6} y={sy(t) + 4} class="tick" text-anchor="end">{t * 100}%</text>
      {/each}
      {#each years as yr (yr)}
        <text x={sx(yr)} y={H - M.bottom + 18} class="tick" text-anchor="middle">{yr}</text>
      {/each}
      {#each SERIES as s (s.key)}
        {@const pts = byYear.filter((r) => r[s.key] != null)}
        {#if pts.length > 1}
          <polyline
            fill="none"
            stroke={s.color}
            stroke-width="2"
            points={pts.map((r) => `${sx(r.year)},${sy(r[s.key])}`).join(' ')}
          />
          {#each pts as r (r.year)}
            <circle
              cx={sx(r.year)}
              cy={sy(r[s.key])}
              r="3.5"
              fill={s.color}
              stroke="#fffdf9"
              stroke-width="1.5"
              onmouseenter={() => (hover = { ...r, series: s })}
              onmouseleave={() => (hover = null)}
            />
          {/each}
          <text x={sx(pts.at(-1).year) + 8} y={sy(pts.at(-1)[s.key]) + 4} class="lbl" fill="#52514e">
            {s.label}
          </text>
        {/if}
      {/each}
    </svg>
    {#if hover}
      <div class="tip">
        <strong>{hover.series.label}</strong>, {hover.year}:
        {Math.round(hover[hover.series.key] * 100)}% of {hover.n.toLocaleString()} tested
      </div>
    {/if}
    <details>
      <summary>All groups by year</summary>
      <table>
        <thead>
          <tr>
            <th>Year</th><th>Tested</th>
            {#each ALL as [, label] (label)}<th>{label}</th>{/each}
          </tr>
        </thead>
        <tbody>
          {#each byYear as r (r.year)}
            <tr>
              <td>{r.year}</td>
              <td class="num">{r.n.toLocaleString()}</td>
              {#each ALL as [k] (k)}
                <td class="num">{r[k] == null ? '—' : Math.round(r[k] * 100) + '%'}</td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </details>
  </div>
{/if}

<style>
  .chart {
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    padding: 0.8rem 1rem 0.6rem;
  }
  svg {
    width: 100%;
    height: auto;
  }
  .tick {
    font-size: 12px;
    fill: #898781;
  }
  .lbl {
    font-size: 11.5px;
  }
  circle {
    cursor: pointer;
  }
  .tip {
    font-size: 0.9rem;
    color: #52514e;
    padding: 0.3rem 0.2rem;
  }
  details {
    margin-top: 0.4rem;
    font-size: 0.85rem;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 0.4rem;
  }
  th,
  td {
    text-align: left;
    padding: 0.25rem 0.4rem;
    border-bottom: 1px solid #eee9df;
  }
  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
</style>
