<script>
  /**
   * Cohort trajectories: one line per graduating class, x = grade, y = state-relative
   * score (student SDs). Ordered series → sequential blue ramp (older → lighter,
   * newer → darker), per dataviz rules. For entities testing a single grade
   * (high schools), falls back to a results-over-time line for that grade.
   */
  let { scores = [], subjectDefault = 'ela' } = $props();

  let subject = $state(subjectDefault);
  let hover = $state(null);

  const W = 820;
  const H = 430;
  const M = { top: 18, right: 86, bottom: 44, left: 52 };

  let rows = $derived(scores.filter((r) => r.subject === subject));
  let grades = $derived([...new Set(rows.map((r) => r.grade))].sort((a, b) => a - b));
  let singleGrade = $derived(grades.length < 2);

  let cohorts = $derived.by(() => {
    const by = new Map();
    for (const r of rows) {
      if (!by.has(r.grad_year)) by.set(r.grad_year, []);
      by.get(r.grad_year).push(r);
    }
    for (const v of by.values()) v.sort((a, b) => a.grade - b.grade);
    return [...by.entries()].sort((a, b) => a[0] - b[0]);
  });

  let years = $derived([...new Set(rows.map((r) => r.year))].sort((a, b) => a - b));

  let ymax = $derived(
    Math.max(0.5, ...rows.map((r) => Math.abs(r.z))) * 1.15
  );

  let xDomain = $derived(singleGrade ? [years[0] ?? 2015, years.at(-1) ?? 2025] : [grades[0], grades.at(-1)]);
  const sx = (v, dom) => M.left + ((v - dom[0]) / Math.max(1e-9, dom[1] - dom[0])) * (W - M.left - M.right);
  const sy = (v, max) => M.top + ((max - v) / (2 * max)) * (H - M.top - M.bottom);

  // sequential ramp: #86b6ef (older) -> #0d366b (newer)
  function ramp(t) {
    const a = [0x86, 0xb6, 0xef];
    const b = [0x0d, 0x36, 0x6b];
    return `rgb(${a.map((av, i) => Math.round(av + (b[i] - av) * t)).join(',')})`;
  }
  let colorOf = $derived.by(() => {
    const ys = cohorts.map(([gy]) => gy);
    const lo = ys[0] ?? 0;
    const hi = ys.at(-1) ?? 1;
    return (gy) => ramp(hi === lo ? 1 : (gy - lo) / (hi - lo));
  });

  let labeled = $derived(new Set(cohorts.slice(-3).map(([gy]) => gy)));
</script>

<div class="chart">
  <div class="controls" role="group" aria-label="Subject">
    <button class:active={subject === 'ela'} onclick={() => (subject = 'ela')}>ELA</button>
    <button class:active={subject === 'math'} onclick={() => (subject = 'math')}>Math</button>
    <span class="hint">
      {#if singleGrade}
        This school tests one grade ({grades[0] ?? '—'}), so each point is a different
        cohort — the line shows results over time, not the same students.
      {:else}
        Follow a line to follow a graduating class across grades. 0 = state average
        for that grade and year. Darker = more recent class.
      {/if}
    </span>
  </div>

  <svg viewBox="0 0 {W} {H}" role="img" aria-label="Cohort score trajectories">
    <line x1={M.left} x2={W - M.right} y1={sy(0, ymax)} y2={sy(0, ymax)} stroke="#c3bcae" />
    <text x={W - M.right} y={sy(0, ymax) - 6} class="avg" text-anchor="end">state average</text>
    {#each [ymax * 0.75, -ymax * 0.75] as t (t)}
      <text x={M.left - 8} y={sy(t, ymax) + 4} class="tick" text-anchor="end">
        {(t > 0 ? '+' : '') + t.toFixed(1)}
      </text>
    {/each}
    {#if singleGrade}
      {#each years as yr (yr)}
        <text x={sx(yr, xDomain)} y={H - M.bottom + 20} class="tick" text-anchor="middle">{yr}</text>
      {/each}
      <polyline
        fill="none"
        stroke="#2a78d6"
        stroke-width="2"
        points={rows
          .slice()
          .sort((a, b) => a.year - b.year)
          .map((r) => `${sx(r.year, xDomain)},${sy(r.z, ymax)}`)
          .join(' ')}
      />
      {#each rows as r (r.year + r.subject)}
        <circle
          cx={sx(r.year, xDomain)}
          cy={sy(r.z, ymax)}
          r="4.5"
          fill="#2a78d6"
          stroke="#fcfcfb"
          stroke-width="1.5"
          onmouseenter={() => (hover = r)}
          onmouseleave={() => (hover = null)}
        />
      {/each}
    {:else}
      {#each grades as g (g)}
        <text x={sx(g, xDomain)} y={H - M.bottom + 20} class="tick" text-anchor="middle">gr {g}</text>
      {/each}
      {#each cohorts as [gy, pts] (gy)}
        <polyline
          fill="none"
          stroke={colorOf(gy)}
          stroke-width={hover?.grad_year === gy ? 3 : 2}
          opacity={hover && hover.grad_year !== gy ? 0.25 : 0.9}
          points={pts.map((r) => `${sx(r.grade, xDomain)},${sy(r.z, ymax)}`).join(' ')}
        />
        {#each pts as r (r.grade)}
          <circle
            cx={sx(r.grade, xDomain)}
            cy={sy(r.z, ymax)}
            r={hover?.grad_year === gy ? 5 : 3.5}
            fill={colorOf(gy)}
            stroke="#fcfcfb"
            stroke-width="1.5"
            opacity={hover && hover.grad_year !== gy ? 0.25 : 1}
            onmouseenter={() => (hover = r)}
            onmouseleave={() => (hover = null)}
          />
        {/each}
        {#if labeled.has(gy)}
          <text
            x={sx(pts.at(-1).grade, xDomain) + 8}
            y={sy(pts.at(-1).z, ymax) + 4}
            class="cohort-label"
            fill="#52514e">Class of {gy}</text
          >
        {/if}
      {/each}
    {/if}
  </svg>

  {#if hover}
    <div class="tip">
      <strong>Class of {hover.grad_year}</strong> — grade {hover.grade}, {hover.year}:
      {(hover.z > 0 ? '+' : '') + hover.z} SD vs state · {hover.n.toLocaleString()} tested
    </div>
  {/if}
</div>

<style>
  .chart {
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    padding: 0.8rem 1rem 0.4rem;
  }
  svg {
    width: 100%;
    height: auto;
  }
  .controls {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-bottom: 0.4rem;
  }
  .controls button {
    border: 1px solid #d8d0c0;
    background: #faf7f2;
    border-radius: 6px;
    padding: 0.25rem 0.8rem;
    font-size: 0.9rem;
    cursor: pointer;
  }
  .controls button.active {
    background: #2a78d6;
    border-color: #2a78d6;
    color: #fff;
  }
  .hint {
    color: #898781;
    font-size: 0.82rem;
    max-width: 34rem;
  }
  .tick {
    font-size: 12px;
    fill: #898781;
  }
  .avg {
    font-size: 11px;
    fill: #898781;
  }
  .cohort-label {
    font-size: 11px;
  }
  circle {
    cursor: pointer;
  }
  .tip {
    font-size: 0.9rem;
    color: #52514e;
    padding: 0.3rem 0.2rem 0.5rem;
  }
</style>
