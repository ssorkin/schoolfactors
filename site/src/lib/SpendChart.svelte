<script>
  /**
   * Enrollment and per-pupil spending over time, as two stacked panels sharing
   * the year axis (never one panel with two y-scales — the classic dual-axis
   * chart invites false correlation reading). Spending is drawn dotted; each
   * panel is a single series named by its title, with a shared crosshair
   * tooltip. Missing years break the line — a gap can mean "not reported".
   */
  let { enr = null, enrYears = [], ppe = null, ppeYears = [] } = $props();

  const W = 680;
  const PH = 128; // per-panel plot height
  const GAP = 44;
  const M = { top: 26, right: 74, bottom: 26, left: 58 };
  const H = M.top + PH + GAP + PH + M.bottom;

  // One shared x domain covering both series' years.
  let years = $derived.by(() => {
    const ys = new Set();
    (enr ?? []).forEach((v, i) => v != null && ys.add(enrYears[i]));
    (ppe ?? []).forEach((v, i) => v != null && ys.add(ppeYears[i]));
    return [...ys].sort((a, b) => a - b);
  });
  let x0 = $derived(years[0]);
  let x1 = $derived(years[years.length - 1]);
  let X = $derived((y) => M.left + ((y - x0) / Math.max(x1 - x0, 1)) * (W - M.left - M.right));

  function series(vals, yrs) {
    if (!vals) return [];
    return vals.map((v, i) => ({ year: yrs[i], v })).filter((p) => p.v != null);
  }
  let enrPts = $derived(series(enr, enrYears));
  let ppePts = $derived(series(ppe, ppeYears));

  function panel(pts, top) {
    if (pts.length < 2) return null;
    const vals = pts.map((p) => p.v);
    let lo = Math.min(...vals);
    let hi = Math.max(...vals);
    const span = Math.max(hi - lo, hi * 0.08, 1);
    lo = Math.max(0, lo - span * 0.15);
    hi = hi + span * 0.15;
    const Y = (v) => top + PH - ((v - lo) / (hi - lo)) * PH;
    // Break the polyline where years are missing (suppressed/unreported).
    const runs = [[]];
    for (const p of pts) {
      const cur = runs[runs.length - 1];
      if (cur.length && p.year - cur[cur.length - 1].year > 1) runs.push([p]);
      else cur.push(p);
    }
    const mid = (lo + hi) / 2;
    return { Y, runs: runs.filter((r) => r.length > 1), pts, ticks: [lo, mid, hi], top };
  }
  let enrPanel = $derived(panel(enrPts, M.top));
  let ppePanel = $derived(panel(ppePts, M.top + PH + GAP));

  const fmtN = (v) => Math.round(v).toLocaleString();
  const fmtD = (v) => '$' + Math.round(v).toLocaleString();

  let hover = $state(null); // hovered year
  function onmove(ev) {
    const svg = ev.currentTarget;
    const r = svg.getBoundingClientRect();
    const px = ((ev.clientX - r.left) / r.width) * W;
    let best = null;
    for (const y of years) {
      const d = Math.abs(X(y) - px);
      if (best == null || d < best.d) best = { y, d };
    }
    hover = best && best.d < 40 ? best.y : null;
  }
  let hoverVals = $derived.by(() => {
    if (hover == null) return null;
    return {
      enr: enrPts.find((p) => p.year === hover)?.v,
      ppe: ppePts.find((p) => p.year === hover)?.v
    };
  });

  let xTicks = $derived(years.filter((y, i) => years.length <= 8 || i % 2 === (years.length - 1) % 2));
</script>

{#if enrPanel || ppePanel}
  <div class="wrap">
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <svg
      viewBox="0 0 {W} {H}"
      role="img"
      aria-label="Enrollment and per-pupil spending by year"
      onmousemove={onmove}
      onmouseleave={() => (hover = null)}
    >
      {#each [enrPanel, ppePanel].filter(Boolean) as p (p.top)}
        <text class="ptitle" x={M.left} y={p.top - 10}>
          {p === enrPanel ? 'Census enrollment (students)' : 'Spending ($ per pupil, ESSA)'}
        </text>
        {#each p.ticks as t (t)}
          <line x1={M.left} x2={W - M.right} y1={p.Y(t)} y2={p.Y(t)} class="grid" />
          <text class="tick" x={M.left - 7} y={p.Y(t) + 4} text-anchor="end">
            {p === enrPanel ? fmtN(t) : fmtD(t)}
          </text>
        {/each}
        {#each p.runs as run, ri (ri)}
          <polyline
            fill="none"
            class={p === enrPanel ? 'enr' : 'ppe'}
            points={run.map((q) => `${X(q.year).toFixed(1)},${p.Y(q.v).toFixed(1)}`).join(' ')}
          />
        {/each}
        {#each p.pts as q (q.year)}
          <circle
            cx={X(q.year)}
            cy={p.Y(q.v)}
            r={hover === q.year ? 4 : 2.4}
            class={p === enrPanel ? 'denr' : 'dppe'}
          />
        {/each}
        {#if p.pts.length}
          {@const last = p.pts[p.pts.length - 1]}
          <text class="endlbl" x={X(last.year) + 8} y={p.Y(last.v) + 4}>
            {p === enrPanel ? fmtN(last.v) : fmtD(last.v)}
          </text>
        {/if}
      {/each}
      {#each xTicks as y (y)}
        <text class="tick" x={X(y)} y={H - 6} text-anchor="middle">{y}</text>
      {/each}
      {#if hover != null}
        <line x1={X(hover)} x2={X(hover)} y1={M.top - 4} y2={H - M.bottom} class="cross" />
      {/if}
    </svg>
    {#if hover != null && hoverVals}
      <div class="tip" style:left="{(X(hover) / W) * 100}%">
        <strong>{hover}</strong>
        {#if hoverVals.enr != null}<span>{fmtN(hoverVals.enr)} students</span>{/if}
        {#if hoverVals.ppe != null}<span>{fmtD(hoverVals.ppe)}/pupil</span>{/if}
      </div>
    {/if}
  </div>
  <p class="note">
    Enrollment is the census-day count (collected every year, including 2020–21).
    Spending is CDE's ESSA per-pupil expenditure — school-site plus allocated central
    costs — which is largely need-driven: more high-need students bring more funding
    by design, so higher spending is neither praise nor criticism. Gaps mean a year
    wasn't reported or didn't pass our data-quality screens, and sharp year-to-year
    level shifts can reflect a district changing how it allocates central costs,
    not actual spending changes — see the
    <a href="/data">documented data issues</a>.
  </p>
{/if}

<style>
  .wrap {
    position: relative;
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    padding: 0.6rem 0.6rem 0.2rem;
    max-width: 46rem;
  }
  svg {
    width: 100%;
    height: auto;
    display: block;
  }
  .ptitle {
    font-size: 12.5px;
    font-weight: 600;
    fill: #52514e;
  }
  .grid {
    stroke: #f0ead9;
  }
  .tick {
    font-size: 11px;
    fill: #898781;
  }
  .enr {
    stroke: #7d6f52;
    stroke-width: 2;
  }
  .ppe {
    stroke: #b0552f;
    stroke-width: 2;
    stroke-dasharray: 2 5;
    stroke-linecap: round;
  }
  .denr {
    fill: #7d6f52;
  }
  .dppe {
    fill: #b0552f;
  }
  .endlbl {
    font-size: 11.5px;
    font-weight: 650;
    fill: #52514e;
  }
  .cross {
    stroke: #c3bcae;
    stroke-dasharray: 3 3;
  }
  .tip {
    position: absolute;
    top: 0.4rem;
    transform: translateX(-50%);
    background: #2b2722;
    color: #faf7f2;
    border-radius: 6px;
    font-size: 0.78rem;
    padding: 0.25rem 0.55rem;
    display: flex;
    gap: 0.6rem;
    pointer-events: none;
    white-space: nowrap;
  }
</style>
