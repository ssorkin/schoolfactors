<script>
  /**
   * The detail page's headline chart: resident public-school children (ACS 5-year
   * windows, line + shaded 90% margin band) vs seats at physical schools located
   * in the area (converted to resident-children units), with annual ACS 1-year
   * dots ± margin where the Census Bureau publishes them (~119 large districts,
   * counties). X positions are the window END years; the smoothing is why the
   * line moves gently — window-to-window deltas are not annual signal.
   */
  let { series = [], acs1 = [], height = 240 } = $props();

  const W = 640;
  const M = { t: 14, r: 12, b: 26, l: 58 };

  // Seats in resident units via the accounting identity:
  // seats_adj = pub − virt − ooc + net (ooc is the county administrative
  // adjustment, absent on county-level series).
  let pts = $derived(
    series
      .filter((r) => r.res?.pub != null)
      .map((r) => ({
        x: r.v,
        pub: r.res.pub,
        moe: r.res.pub_moe ?? 0,
        seats:
          r.net != null && r.virt != null
            ? r.res.pub - r.virt - (r.ooc ?? 0) + r.net
            : null
      }))
  );
  let a1 = $derived((acs1 ?? []).filter((r) => r[1] != null).map(([y, pub, moe]) => ({ x: y, pub, moe: moe ?? 0 })));

  let xs = $derived([...pts.map((p) => p.x), ...a1.map((p) => p.x)]);
  let ys = $derived([
    ...pts.flatMap((p) => [p.pub + p.moe, p.seats ?? 0]),
    ...a1.map((p) => p.pub + p.moe)
  ]);
  let x0 = $derived(Math.min(...xs));
  let x1 = $derived(Math.max(...xs));
  let yMax = $derived(Math.max(...ys) * 1.06);
  let yMin = $derived(Math.max(0, Math.min(...pts.map((p) => p.pub - p.moe), ...pts.map((p) => p.seats ?? Infinity)) * 0.9));

  let X = $derived((v) => M.l + ((v - x0) / Math.max(1, x1 - x0)) * (W - M.l - M.r));
  let Y = $derived((v) => M.t + (1 - (v - yMin) / Math.max(1, yMax - yMin)) * (height - M.t - M.b));

  const path = (arr, key) =>
    arr
      .filter((p) => p[key] != null)
      .map((p, i) => `${i ? 'L' : 'M'}${X(p.x).toFixed(1)},${Y(p[key]).toFixed(1)}`)
      .join('');
  let band = $derived.by(() => {
    const up = pts.map((p) => `${X(p.x).toFixed(1)},${Y(p.pub + p.moe).toFixed(1)}`);
    const dn = [...pts].reverse().map((p) => `${X(p.x).toFixed(1)},${Y(p.pub - p.moe).toFixed(1)}`);
    return `M${[...up, ...dn].join('L')}Z`;
  });

  let yTicks = $derived.by(() => {
    const span = yMax - yMin;
    const step = span > 400000 ? 200000 : span > 150000 ? 50000 : span > 40000 ? 20000 : span > 15000 ? 5000 : span > 4000 ? 2000 : 500;
    const out = [];
    for (let v = Math.ceil(yMin / step) * step; v <= yMax; v += step) out.push(v);
    return out;
  });
  let xTicks = $derived.by(() => {
    const out = [];
    for (let v = Math.ceil(x0 / 4) * 4; v <= x1; v += 4) out.push(v);
    return out;
  });
  const fmtY = (v) => (v >= 1000 ? `${Math.round(v / 1000).toLocaleString()}k` : v);
</script>

{#if pts.length > 1}
  <figure>
    <figcaption>
      <span class="k"><span class="sw pub"></span>resident public-school children (5-yr windows, ±90% margin)</span>
      <span class="k"><span class="sw seats"></span>seats at schools located here (resident units)</span>
      {#if a1.length}<span class="k"><span class="dot"></span>annual survey (±margin)</span>{/if}
    </figcaption>
    <svg viewBox="0 0 {W} {height}" role="img" aria-label="Residents vs seats over time">
      {#each yTicks as t}
        <line x1={M.l} x2={W - M.r} y1={Y(t)} y2={Y(t)} class="grid" />
        <text x={M.l - 6} y={Y(t) + 3.5} text-anchor="end" class="tick">{fmtY(t)}</text>
      {/each}
      {#each xTicks as t}
        <text x={X(t)} y={height - 8} text-anchor="middle" class="tick">{t}</text>
      {/each}
      <path d={band} class="band" />
      <path d={path(pts, 'pub')} class="pub" />
      <path d={path(pts, 'seats')} class="seats" />
      {#each a1 as p}
        <line x1={X(p.x)} x2={X(p.x)} y1={Y(p.pub - p.moe)} y2={Y(p.pub + p.moe)} class="a1err" />
        <circle cx={X(p.x)} cy={Y(p.pub)} r="2.4" class="a1dot" />
      {/each}
    </svg>
  </figure>
{/if}

<style>
  figure {
    margin: 0;
  }
  figcaption {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem 1rem;
    font-size: 0.78rem;
    color: #52514e;
    margin-bottom: 0.3rem;
  }
  .k {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
  }
  .sw {
    width: 16px;
    height: 3px;
    display: inline-block;
    border-radius: 2px;
  }
  .sw.pub {
    background: #2a78d6;
  }
  .sw.seats {
    background: #eb6834;
  }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #2a78d6;
    display: inline-block;
  }
  svg {
    width: 100%;
    height: auto;
    display: block;
  }
  .grid {
    stroke: #eee8db;
    stroke-width: 1;
  }
  .tick {
    font-size: 10px;
    fill: #898781;
  }
  .band {
    fill: #2a78d6;
    fill-opacity: 0.12;
  }
  .pub {
    fill: none;
    stroke: #2a78d6;
    stroke-width: 2;
  }
  .seats {
    fill: none;
    stroke: #eb6834;
    stroke-width: 2;
  }
  .a1err {
    stroke: #2a78d6;
    stroke-opacity: 0.45;
    stroke-width: 1;
  }
  .a1dot {
    fill: #2a78d6;
    stroke: #fff;
    stroke-width: 0.8;
  }
</style>
