<script>
  /**
   * Small stacked-area chart for the enrollment decompositions: one band per
   * category, stacked so the top edge is the universe total. Hovering a year
   * shows every band's value. Missing years simply aren't drawn (ACS vintages
   * can skip).
   */
  let {
    data = [], // [[year, {key: value, ...}], ...] sorted by year
    series = [], // [{key, label, color}] bottom band first
    title = '',
    ymax = null // shared scale across charts when set
  } = $props();

  const W = 640;
  const H = 250;
  const M = { top: 12, right: 14, bottom: 26, left: 62 };

  let years = $derived(data.map(([y]) => y));
  let x0 = $derived(Math.min(...years));
  let x1 = $derived(Math.max(...years));
  let top = $derived(
    ymax ?? Math.max(...data.map(([, d]) => series.reduce((s, sr) => s + (d[sr.key] ?? 0), 0)))
  );
  const X = $derived((y) => M.left + ((y - x0) / Math.max(x1 - x0, 1)) * (W - M.left - M.right));
  const Y = $derived((v) => M.top + (1 - v / (top * 1.04)) * (H - M.top - M.bottom));

  // Cumulative stacks per year, bottom band first.
  let stacks = $derived.by(() => {
    return series.map((sr, si) => {
      const pts = data.map(([y, d]) => {
        let lo = 0;
        for (let i = 0; i < si; i++) lo += d[series[i].key] ?? 0;
        return { y, lo, hi: lo + (d[sr.key] ?? 0) };
      });
      const path =
        pts.map((p, i) => `${i ? 'L' : 'M'}${X(p.y)},${Y(p.hi)}`).join('') +
        [...pts].reverse().map((p) => `L${X(p.y)},${Y(p.lo)}`).join('') +
        'Z';
      return { ...sr, path };
    });
  });

  let hover = $state(null); // year
  let hoverRow = $derived(hover == null ? null : data.find(([y]) => y === hover));
  const fmtN = (v) => (v == null ? '—' : Math.round(v).toLocaleString());

  function onmove(e) {
    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    let best = null;
    for (const y of years) {
      if (best == null || Math.abs(X(y) - px) < Math.abs(X(best) - px)) best = y;
    }
    hover = best;
  }
</script>

<div class="wrap">
  <p class="title">{title}</p>
  <svg
    viewBox="0 0 {W} {H}"
    role="img"
    aria-label={title}
    onmousemove={onmove}
    onmouseleave={() => (hover = null)}
  >
    {#each [0.25, 0.5, 0.75, 1] as t}
      <line x1={M.left} y1={Y(top * t)} x2={W - M.right} y2={Y(top * t)} stroke="#e1e0d9" />
      <text x={M.left - 6} y={Y(top * t) + 4} text-anchor="end" class="tick">
        {Math.round((top * t) / 1000)}k
      </text>
    {/each}
    {#each stacks as s}
      <path d={s.path} fill={s.color} fill-opacity="0.85" stroke="#faf7f2" stroke-width="1" />
    {/each}
    {#each years as y}
      <text x={X(y)} y={H - 8} text-anchor="middle" class="tick">{String(y).slice(2)}</text>
    {/each}
    {#if hover != null}
      <line x1={X(hover)} y1={M.top} x2={X(hover)} y2={H - M.bottom} stroke="#52514e" stroke-dasharray="3 3" />
    {/if}
  </svg>
  <p class="caption">
    {#if hoverRow}
      <b>{hover}</b>:
      {#each [...series].reverse() as sr}
        <span class="k"><span class="sw" style="background:{sr.color}"></span>{sr.label}
          {fmtN(hoverRow[1][sr.key])}</span>
      {/each}
      · total {fmtN(series.reduce((s, sr) => s + (hoverRow[1][sr.key] ?? 0), 0))}
    {:else}
      {#each [...series].reverse() as sr}
        <span class="k"><span class="sw" style="background:{sr.color}"></span>{sr.label}</span>
      {/each}
    {/if}
  </p>
</div>

<style>
  .wrap {
    min-width: 0;
  }
  .title {
    font-size: 0.9rem;
    font-weight: 600;
    color: #2b2722;
    margin: 0 0 0.25rem;
  }
  svg {
    width: 100%;
    height: auto;
    display: block;
    background: #fcfcfb;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
  }
  .tick {
    font-size: 11px;
    fill: #898781;
  }
  .caption {
    font-size: 0.8rem;
    color: #52514e;
    min-height: 2.4em;
    margin: 0.3rem 0 0;
  }
  .k {
    display: inline-flex;
    align-items: center;
    gap: 0.28rem;
    margin-right: 0.7rem;
    white-space: nowrap;
  }
  .sw {
    width: 10px;
    height: 10px;
    border-radius: 3px;
    display: inline-block;
  }
</style>
