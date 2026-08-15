<script>
  /**
   * The headline chart: pass rate (met or exceeded standard, levels 3-4) and
   * exceeded rate (level 4) over time, with quick split toggles:
   *   Overall     — both rates, all grades combined
   *   By grade    — one rate per grade (sequential ramp: darker = higher grade)
   *   By group    — one rate for key student groups (categorical palette)
   * Lines break across the 2020-21 testing gap rather than bridging it.
   */
  let { subgroups = [], scores = [] } = $props();

  let subject = $state('ela');
  let split = $state('overall'); // 'overall' | 'grade' | 'group'
  let metric = $state('pct_met'); // used for grade/group splits
  let hover = $state(null);

  const GROUPS = [
    { id: 31, label: 'Econ. disadvantaged', color: '#2a78d6' },
    { id: 111, label: 'Not econ. disadv.', color: '#eb6834' },
    { id: 160, label: 'English learners', color: '#1baf7a' },
    { id: 128, label: 'With disabilities', color: '#eda100' }
  ];

  const W = 820;
  const H = 380;
  const M = { top: 18, right: 150, bottom: 40, left: 46 };

  function ramp(t) {
    const a = [0x86, 0xb6, 0xef];
    const b = [0x0d, 0x36, 0x6b];
    return `rgb(${a.map((av, i) => Math.round(av + (b[i] - av) * t)).join(',')})`;
  }

  // series: [{key, label, color, pts: [{year, v, n, extra}]}]
  let series = $derived.by(() => {
    if (split === 'overall') {
      const all = subgroups
        .filter((r) => r.subject === subject && r.group === 1)
        .sort((a, b) => a.year - b.year);
      return [
        {
          key: 'met',
          label: 'Met or exceeded (3–4)',
          color: '#2a78d6',
          pts: all.filter((r) => r.pct_met != null).map((r) => ({ year: r.year, v: r.pct_met, n: r.n }))
        },
        {
          key: 'exc',
          label: 'Exceeded (level 4)',
          color: '#eb6834',
          pts: all.filter((r) => r.pct_exc != null).map((r) => ({ year: r.year, v: r.pct_exc, n: r.n }))
        }
      ];
    }
    if (split === 'grade') {
      const rows = scores.filter((r) => r.subject === subject);
      const grades = [...new Set(rows.map((r) => r.grade))].sort((a, b) => a - b);
      return grades.map((g, i) => ({
        key: 'g' + g,
        label: 'Grade ' + g,
        color: ramp(grades.length === 1 ? 1 : i / (grades.length - 1)),
        pts: rows
          .filter((r) => r.grade === g && r[metric === 'pct_met' ? 'pct_met' : 'pct_exc'] != null)
          .sort((a, b) => a.year - b.year)
          .map((r) => ({ year: r.year, v: metric === 'pct_met' ? r.pct_met : r.pct_exc, n: r.n }))
      }));
    }
    return GROUPS.map((gr) => ({
      key: 'grp' + gr.id,
      label: gr.label,
      color: gr.color,
      pts: subgroups
        .filter(
          (r) =>
            r.subject === subject &&
            r.group === gr.id &&
            (metric === 'pct_met' ? r.pct_met : r.pct_exc) != null
        )
        .sort((a, b) => a.year - b.year)
        .map((r) => ({ year: r.year, v: metric === 'pct_met' ? r.pct_met : r.pct_exc, n: r.n }))
    })).filter((s) => s.pts.length > 1);
  });

  let years = $derived(
    [...new Set(series.flatMap((s) => s.pts.map((p) => p.year)))].sort((a, b) => a - b)
  );
  const sx = (yr) =>
    M.left +
    ((yr - (years[0] ?? 2015)) / Math.max(1, (years.at(-1) ?? 2025) - (years[0] ?? 2015))) *
      (W - M.left - M.right);
  const sy = (v) => M.top + (1 - v / 100) * (H - M.top - M.bottom);

  // split each series into runs of consecutive years so lines don't bridge 2020-21
  function runs(pts) {
    const out = [];
    let cur = [];
    for (const p of pts) {
      if (cur.length && p.year - cur.at(-1).year > 1) {
        out.push(cur);
        cur = [];
      }
      cur.push(p);
    }
    if (cur.length) out.push(cur);
    return out;
  }
</script>

<div class="chart">
  <div class="controls">
    <div role="group" aria-label="Subject">
      <button class:active={subject === 'ela'} onclick={() => (subject = 'ela')}>ELA</button>
      <button class:active={subject === 'math'} onclick={() => (subject = 'math')}>Math</button>
    </div>
    <div role="group" aria-label="Split">
      <button class:active={split === 'overall'} onclick={() => (split = 'overall')}>Overall</button>
      <button class:active={split === 'grade'} onclick={() => (split = 'grade')}>By grade</button>
      <button class:active={split === 'group'} onclick={() => (split = 'group')}>By group</button>
    </div>
    {#if split !== 'overall'}
      <div role="group" aria-label="Rate">
        <button class:active={metric === 'pct_met'} onclick={() => (metric = 'pct_met')}>
          Met or exceeded
        </button>
        <button class:active={metric === 'pct_exc'} onclick={() => (metric = 'pct_exc')}>
          Exceeded
        </button>
      </div>
    {/if}
  </div>

  <svg viewBox="0 0 {W} {H}" role="img" aria-label="Share of students meeting or exceeding the standard over time">
    {#each [0, 25, 50, 75, 100] as t (t)}
      <line x1={M.left} x2={W - M.right} y1={sy(t)} y2={sy(t)} stroke="#eee9df" />
      <text x={M.left - 6} y={sy(t) + 4} class="tick" text-anchor="end">{t}%</text>
    {/each}
    {#each years as yr (yr)}
      <text x={sx(yr)} y={H - M.bottom + 18} class="tick" text-anchor="middle">{yr}</text>
    {/each}
    {#if years.includes(2019) && years.includes(2022)}
      <text x={(sx(2019) + sx(2022)) / 2} y={M.top + 12} class="gap" text-anchor="middle">
        no data 2020–21
      </text>
    {/if}
    {#each series as s (s.key)}
      {#each runs(s.pts) as run, ri (ri)}
        <polyline
          fill="none"
          stroke={s.color}
          stroke-width="2"
          opacity={hover && hover.series !== s.key ? 0.3 : 0.95}
          points={run.map((p) => `${sx(p.year)},${sy(p.v)}`).join(' ')}
        />
      {/each}
      {#each s.pts as p (p.year)}
        <circle
          cx={sx(p.year)}
          cy={sy(p.v)}
          r={hover?.series === s.key && hover?.year === p.year ? 5.5 : 3.5}
          fill={s.color}
          stroke="#fffdf9"
          stroke-width="1.5"
          opacity={hover && hover.series !== s.key ? 0.3 : 1}
          onmouseenter={() => (hover = { series: s.key, label: s.label, year: p.year, v: p.v, n: p.n })}
          onmouseleave={() => (hover = null)}
        />
      {/each}
      {#if s.pts.length}
        <text x={sx(s.pts.at(-1).year) + 8} y={sy(s.pts.at(-1).v) + 4} class="lbl" fill="#52514e">
          {s.label}
        </text>
      {/if}
    {/each}
  </svg>

  <div class="tip" aria-live="polite">
    {#if hover}
      <strong>{hover.label}</strong>, {hover.year}: {hover.v.toFixed(0)}% ·
      {hover.n.toLocaleString()} students with scores
    {:else}
      &nbsp;
    {/if}
  </div>
</div>

<style>
  .chart {
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    padding: 0.8rem 1rem 0.3rem;
  }
  svg {
    width: 100%;
    height: auto;
  }
  .controls {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    margin-bottom: 0.4rem;
  }
  .controls button {
    border: 1px solid #d8d0c0;
    background: #faf7f2;
    border-radius: 6px;
    padding: 0.25rem 0.75rem;
    font-size: 0.88rem;
    cursor: pointer;
    margin-right: 0.25rem;
  }
  .controls button.active {
    background: #2a78d6;
    border-color: #2a78d6;
    color: #fff;
  }
  .tick {
    font-size: 12px;
    fill: #898781;
  }
  .lbl {
    font-size: 11.5px;
  }
  .gap {
    font-size: 11px;
    fill: #b8b2a5;
    font-style: italic;
  }
  circle {
    cursor: pointer;
  }
  .tip {
    font-size: 0.9rem;
    color: #52514e;
    padding: 0.25rem 0.2rem 0.45rem;
    min-height: 1.4rem;
  }
</style>
