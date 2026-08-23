<script>
  /**
   * Net import/export per ACS window: diverging bars around zero (blue up = net
   * importer, rust down = net exporter — the site-wide sign convention) with
   * ±90% margin whiskers. Rates, not counts, so districts are comparable.
   * Optional `perf` ([[year, pct]]) overlays the demographics-adjusted
   * performance percentile on a right-hand 0-100 axis — descriptive
   * co-movement, never a causal claim.
   */
  let { series = [], perf = [], height = 200 } = $props();

  const W = 640;
  const M = { t: 12, r: 40, b: 26, l: 46 };

  let pts = $derived(
    series
      .filter((r) => r.rate != null && r.res?.pub)
      .map((r) => ({ x: r.v, rate: r.rate, moe: (r.res.pub_moe ?? 0) / r.res.pub, net: r.net }))
  );
  let perfPts = $derived((perf ?? []).filter((p) => p[1] != null));
  let ext = $derived(Math.max(0.05, ...pts.map((p) => Math.abs(p.rate) + p.moe)) * 1.1);
  let x0 = $derived(Math.min(...pts.map((p) => p.x), ...perfPts.map((p) => p[0])));
  let x1 = $derived(Math.max(...pts.map((p) => p.x), ...perfPts.map((p) => p[0])));
  let bw = $derived(Math.min(22, ((W - M.l - M.r) / Math.max(1, x1 - x0 + 1)) * 0.62));
  let X = $derived((v) => M.l + ((v - x0 + 0.5) / Math.max(1, x1 - x0 + 1)) * (W - M.l - M.r));
  let Y = $derived((v) => M.t + ((ext - v) / (2 * ext)) * (height - M.t - M.b));

  let yTicks = $derived.by(() => {
    const step = ext > 0.3 ? 0.2 : ext > 0.15 ? 0.1 : ext > 0.06 ? 0.05 : 0.02;
    const out = [];
    for (let v = -Math.floor(ext / step) * step; v <= ext; v += step) out.push(+v.toFixed(4));
    return out;
  });
  const fmtPct = (v) => `${v > 0 ? '+' : ''}${Math.round(v * 100)}%`;
  const fmtN = (v) => (v == null ? '' : `${v > 0 ? '+' : ''}${Math.round(v).toLocaleString()}`);

  // Right-hand axis: performance percentile 0-100.
  let RY = $derived((v) => M.t + (1 - v / 100) * (height - M.t - M.b));
  let perfPath = $derived(
    perfPts
      .map(([y, p], i) => `${i ? 'L' : 'M'}${X(y).toFixed(1)},${RY(p).toFixed(1)}`)
      .join('')
  );
</script>

{#if pts.length > 1}
  {#if perfPts.length > 1}
    <p class="key">
      <span class="k"><span class="sw imp"></span>/<span class="sw exp"></span> net import / export (left)</span>
      <span class="k"><span class="perfline"></span> Similar Student %ile (right)</span>
    </p>
  {/if}
  <svg viewBox="0 0 {W} {height}" role="img" aria-label="Net import rate per window">
    {#each yTicks as t}
      <line x1={M.l} x2={W - M.r} y1={Y(t)} y2={Y(t)} class="grid" class:zero={t === 0} />
      <text x={M.l - 6} y={Y(t) + 3.5} text-anchor="end" class="tick">{fmtPct(t)}</text>
    {/each}
    {#if perfPts.length > 1}
      {#each [25, 50, 75] as t}
        <text x={W - M.r + 6} y={RY(t) + 3.5} class="tick perf">{t}</text>
      {/each}
    {/if}
    {#each pts as p}
      <rect
        x={X(p.x) - bw / 2}
        y={Math.min(Y(0), Y(p.rate))}
        width={bw}
        height={Math.abs(Y(p.rate) - Y(0))}
        class={p.rate >= 0 ? 'imp' : 'exp'}
      >
        <title>
          {p.x - 4}–{p.x}: {fmtPct(p.rate)} ({fmtN(p.net)} students, est. ±{Math.round(p.moe * 100)}pp)
        </title>
      </rect>
      <line x1={X(p.x)} x2={X(p.x)} y1={Y(p.rate - p.moe)} y2={Y(p.rate + p.moe)} class="whisker" />
      {#if p.x % 4 === 0}
        <text x={X(p.x)} y={height - 8} text-anchor="middle" class="tick">{p.x}</text>
      {/if}
    {/each}
    {#if perfPts.length > 1}
      <path d={perfPath} class="perfpath" />
      {#each perfPts as [y, p]}
        <circle cx={X(y)} cy={RY(p)} r="2.2" class="perfdot">
          <title>{y}: {Math.round(p)}th %ile vs schools serving similar students</title>
        </circle>
      {/each}
    {/if}
  </svg>
{/if}

<style>
  svg {
    width: 100%;
    height: auto;
    display: block;
  }
  .grid {
    stroke: #eee8db;
    stroke-width: 1;
  }
  .grid.zero {
    stroke: #b5aea1;
  }
  .tick {
    font-size: 10px;
    fill: #898781;
  }
  .imp {
    fill: #1c5cab;
    fill-opacity: 0.85;
  }
  .exp {
    fill: #9a3412;
    fill-opacity: 0.85;
  }
  .whisker {
    stroke: #211d18;
    stroke-opacity: 0.45;
    stroke-width: 1.2;
  }
  .key {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem 1rem;
    font-size: 0.78rem;
    color: #52514e;
    margin: 0 0 0.3rem;
  }
  .k {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
  }
  .sw {
    width: 10px;
    height: 10px;
    border-radius: 2px;
    display: inline-block;
  }
  .sw.imp {
    background: #1c5cab;
  }
  .sw.exp {
    background: #9a3412;
  }
  .perfline {
    width: 18px;
    border-top: 2px solid #1e6b3a;
    display: inline-block;
  }
  .perfpath {
    fill: none;
    stroke: #1e6b3a;
    stroke-width: 1.8;
  }
  .perfdot {
    fill: #1e6b3a;
    stroke: #fff;
    stroke-width: 0.7;
  }
  .tick.perf {
    fill: #1e6b3a;
  }
</style>
