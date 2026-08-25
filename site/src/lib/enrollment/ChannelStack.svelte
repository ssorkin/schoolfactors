<script>
  import { CLASS_COLOR } from './metrics.js';

  /**
   * Channel decomposition per ACS window: where the area's resident
   * public-school children are counted. Stacked bands (bottom-up):
   *   the district's own schools / affiliated charters (observed seats)
   *   independent charters located here (observed seats — the local draw)
   *   virtual/non-classroom & out-of-county (allocated: the remote pool's
   *   legal-footprint share, spread within the county by population)
   *   elsewhere in county / counted in other counties (net export residual,
   *   est.) — for a district: in-person enrollment in other in-county
   *   districts mixed with above-pro-rata virtual/out-of-county use (the sum
   *   across a county's districts is zero by construction, so collectively
   *   this IS within-county redistribution, but per district the virtual
   *   deviation is inseparable); for a county (county=true): the measured
   *   cross-county administrative flow
   * A dashed line marks resident public-school children: for a net exporter the
   * stack meets the line; for a net importer the local bands overshoot it — the
   * overhang IS the net import. Channels are classes of schools, not observed
   * destinations; the neighbor list carries the "which districts" context.
   */
  let { series = [], m = [], height = 250, county = false } = $props();

  // 'stacked': cumulative bands meeting the resident line (composition).
  // 'lines': each channel on its own zero baseline (growth per channel,
  // without the stacking-order distortion). Same series, same colors.
  let mode = $state('stacked');

  const W = 640;
  const M = { t: 14, r: 12, b: 26, l: 58 };
  const C = {
    dr: CLASS_COLOR.district_run,
    aff: CLASS_COLOR.charter_aff,
    cbm: CLASS_COLOR.charter_bm,
    vooc: CLASS_COLOR.charter_virtual,
    other: '#8d8880',
    mis: '#cdc7bb'
  };
  let LABEL = $derived({
    dr: county ? "district-run schools" : "this district's schools",
    aff: 'affiliated charters',
    cbm: 'independent charters located here',
    vooc: county
      ? 'virtual & non-classroom (balanced est.)'
      : 'virtual/non-classroom & out-of-county (balanced est.)',
    other: county
      ? 'counted in adjacent counties (net, matched)'
      : 'elsewhere in county (net, est.)',
    mis: 'survey–administrative alignment (not students)'
  });

  let mMap = $derived(new Map(m));
  let pts = $derived(
    series
      .filter((r) => r.net != null && r.res?.pub)
      .map((r) => {
        const cal = 1 - (mMap.get(r.v) ?? 0.055);
        const vooc = (r.virt ?? 0) + (r.ooc ?? 0);
        // County residuals carry the conservation decomposition: the matched
        // adjacent-county flow first (capped by the residual), the remainder
        // is the survey-administrative misalignment — not students.
        const resid = Math.max(-r.net, 0);
        const flowPart =
          county && r.flow != null ? Math.min(Math.max(-r.flow, 0), resid) : resid;
        return {
          x: r.v,
          base: r.res.pub,
          moe: r.res.pub_moe ?? 0,
          net: r.net,
          bands: {
            dr: (r.seats?.dr ?? 0) * cal,
            aff: (r.seats?.aff ?? 0) * cal,
            cbm: (r.seats?.cbm ?? 0) * cal,
            vooc: Math.max(vooc, 0),
            other: flowPart,
            mis: resid - flowPart
          }
        };
      })
  );

  let x0 = $derived(Math.min(...pts.map((p) => p.x)));
  let x1 = $derived(Math.max(...pts.map((p) => p.x)));
  let yMax = $derived.by(() => {
    const top =
      mode === 'lines'
        ? Math.max(...pts.map((p) => Math.max(p.base, ...Object.values(p.bands))))
        : Math.max(
            ...pts.map((p) => Math.max(p.base, Object.values(p.bands).reduce((a, b) => a + b, 0)))
          );
    return top * 1.06;
  });
  let X = $derived((v) => M.l + ((v - x0) / Math.max(1, x1 - x0)) * (W - M.l - M.r));

  // Unstacked mode is log-scale (channels span orders of magnitude, so linear
  // pins the small ones to the axis). Log has no zero: the floor snaps to the
  // 1/2/5 step at or below the smallest plotted value, and zero-valued years
  // break the line instead of being clamped to the floor.
  let logDomain = $derived.by(() => {
    let lo = Infinity;
    for (const p of pts)
      for (const v of Object.values(p.bands)) if (v > 0.5 && v < lo) lo = v;
    if (!isFinite(lo)) lo = 1;
    const mag = Math.pow(10, Math.floor(Math.log10(lo)));
    const step = [5, 2, 1].find((s) => s * mag <= lo) ?? 1;
    return { lo: step * mag, hi: yMax };
  });
  let Y = $derived.by(() => {
    if (mode === 'lines') {
      const l0 = Math.log(logDomain.lo);
      const l1 = Math.log(logDomain.hi);
      return (v) =>
        M.t + (1 - (Math.log(Math.max(v, logDomain.lo)) - l0) / (l1 - l0)) * (height - M.t - M.b);
    }
    return (v) => M.t + (1 - v / yMax) * (height - M.t - M.b);
  });

  let KEYS = $derived(
    county ? ['dr', 'aff', 'cbm', 'vooc', 'other', 'mis'] : ['dr', 'aff', 'cbm', 'vooc', 'other']
  );
  let areas = $derived.by(() => {
    // Cumulative stack per band: area path between running lower and upper edges.
    const lows = pts.map(() => 0);
    const out = [];
    for (const k of KEYS) {
      const ups = pts.map((p, i) => lows[i] + p.bands[k]);
      const top = pts.map((p, i) => `${X(p.x).toFixed(1)},${Y(ups[i]).toFixed(1)}`);
      const bot = [...pts].reverse().map((p, i) => {
        const j = pts.length - 1 - i;
        return `${X(p.x).toFixed(1)},${Y(lows[j]).toFixed(1)}`;
      });
      out.push({ k, d: `M${[...top, ...bot].join('L')}Z` });
      for (let i = 0; i < lows.length; i++) lows[i] = ups[i];
    }
    return out;
  });
  // Unstacked mode: one 2px line per channel, log y. Channels that are ~zero
  // across the whole window are skipped (an empty band is invisible when
  // stacked; a flat line on the axis is just clutter); a zero year inside an
  // otherwise-live channel breaks the path (log has no zero to draw).
  let chanLines = $derived(
    KEYS.filter((k) => pts.some((p) => p.bands[k] > 0.5)).map((k) => {
      let live = false;
      const parts = [];
      for (const p of pts) {
        const v = p.bands[k];
        if (v > 0.5) {
          parts.push(`${live ? 'L' : 'M'}${X(p.x).toFixed(1)},${Y(v).toFixed(1)}`);
          live = true;
        } else {
          live = false;
        }
      }
      return { k, d: parts.join('') };
    })
  );
  let baseLine = $derived(
    pts.map((p, i) => `${i ? 'L' : 'M'}${X(p.x).toFixed(1)},${Y(p.base).toFixed(1)}`).join('')
  );
  let xTicks = $derived.by(() => {
    const out = [];
    for (let v = Math.ceil(x0 / 4) * 4; v <= x1; v += 4) out.push(v);
    return out;
  });
  let yTicks = $derived.by(() => {
    if (mode === 'lines') {
      // 1-2-5 ticks per decade, thinned to 1-5 then decades if crowded.
      for (const steps of [[1, 2, 5], [1, 5], [1]]) {
        const out = [];
        let mag = Math.pow(10, Math.floor(Math.log10(logDomain.lo)));
        for (; mag <= logDomain.hi; mag *= 10)
          for (const s of steps) {
            const v = s * mag;
            if (v >= logDomain.lo && v <= logDomain.hi) out.push(v);
          }
        if (out.length <= 8) return out;
      }
    }
    const step = yMax > 400000 ? 200000 : yMax > 150000 ? 50000 : yMax > 40000 ? 20000
      : yMax > 15000 ? 5000 : yMax > 4000 ? 2000 : 500;
    const out = [];
    for (let v = step; v <= yMax; v += step) out.push(v);
    return out;
  });
  const fmtY = (v) => (v >= 1000 ? `${Math.round(v / 1000).toLocaleString()}k` : v);
  const fmtN = (v) => Math.round(v).toLocaleString();

  let hover = $state(null);
  function onMove(e) {
    if (!pts.length) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const svgX = ((e.clientX - rect.left) / rect.width) * W;
    const vx = x0 + ((svgX - M.l) / (W - M.l - M.r)) * (x1 - x0);
    hover = pts.reduce((a, p) => (Math.abs(p.x - vx) < Math.abs(a.x - vx) ? p : a), pts[0]);
  }
</script>

{#if pts.length > 1}
  <figure>
    <figcaption>
      {#each KEYS as k}
        <span class="k"><span class="sw" style="background: {C[k]}"></span>{LABEL[k]}</span>
      {/each}
      <span class="k"><span class="dash"></span>resident public-school children</span>
      <div class="seg" role="group" aria-label="Chart mode">
        <button
          class:on={mode === 'stacked'}
          aria-pressed={mode === 'stacked'}
          onclick={() => (mode = 'stacked')}>stacked</button
        >
        <button
          class:on={mode === 'lines'}
          aria-pressed={mode === 'lines'}
          onclick={() => (mode = 'lines')}>unstacked</button
        >
      </div>
    </figcaption>
    <svg
      viewBox="0 0 {W} {height}"
      role="img"
      aria-label="Resident students by where they are counted, per window"
      onmousemove={onMove}
      onmouseleave={() => (hover = null)}
    >
      {#each yTicks as t}
        <line x1={M.l} x2={W - M.r} y1={Y(t)} y2={Y(t)} class="grid" />
        <text x={M.l - 6} y={Y(t) + 3.5} text-anchor="end" class="tick">{fmtY(t)}</text>
      {/each}
      {#if mode === 'stacked'}
        {#each areas as a}
          <path d={a.d} fill={C[a.k]} fill-opacity="0.75" />
        {/each}
      {:else}
        {#each chanLines as l}
          <path d={l.d} fill="none" stroke={C[l.k]} stroke-width="2" />
        {/each}
      {/if}
      <path d={baseLine} class="base" />
      {#if hover}
        <line x1={X(hover.x)} x2={X(hover.x)} y1={M.t} y2={height - M.b} class="cursor" />
        {#if mode === 'lines'}
          {#each chanLines as l}
            {#if hover.bands[l.k] > 0.5}
              <circle cx={X(hover.x)} cy={Y(hover.bands[l.k])} r="4" fill={C[l.k]} class="dot" />
            {/if}
          {/each}
        {/if}
      {/if}
      {#each xTicks as t}
        <text x={X(t)} y={height - 8} text-anchor="middle" class="tick">{t}</text>
      {/each}
    </svg>
    <p class="caption">
      {#if hover}
        <b>{hover.x - 4}–{hover.x}</b>:
        {fmtN(hover.bands.dr)} district-run here ·
        {#if hover.bands.aff > 0.5}{fmtN(hover.bands.aff)} affiliated charter ·{/if}
        {fmtN(hover.bands.cbm)} independent charter ·
        {fmtN(hover.bands.vooc)} virtual/non-classroom &amp; out-of-county (est.) ·
        {#if hover.net < 0}
          {#if county}
            {fmtN(hover.bands.other)} counted in adjacent counties (matched
            flow) · {fmtN(hover.bands.mis)} survey–administrative alignment —
            not students (net, est. ±{fmtN(hover.moe)})
          {:else}
            {fmtN(-hover.net)} elsewhere in the county — other districts in
            person and/or above-average remote use (net, est. ±{fmtN(hover.moe)})
          {/if}
        {:else}
          net importer: schools here also seat ~{fmtN(hover.net)} students from other
          districts (est. ±{fmtN(hover.moe)}) — the stack overshoots the resident line
        {/if}
      {:else if mode === 'lines'}
        Channels are classes of schools, not observed destinations — hover for values.
        One line per channel on a <b>log scale</b>, so equal slopes mean equal
        growth <em>rates</em> — small channels' trends read alongside large ones.
      {:else}
        Channels are classes of schools, not observed destinations — hover for values.
        Where the stack tops out above the dashed line, schools here seat more
        students than resident children account for (net import).
      {/if}
    </p>
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
    width: 12px;
    height: 12px;
    border-radius: 3px;
    display: inline-block;
    opacity: 0.85;
  }
  .dash {
    width: 18px;
    border-top: 2px dashed #211d18;
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
  .base {
    fill: none;
    stroke: #211d18;
    stroke-width: 1.6;
    stroke-dasharray: 5 4;
  }
  .cursor {
    stroke: #b5aea1;
    stroke-width: 1;
  }
  .dot {
    stroke: #faf7f2;
    stroke-width: 2;
  }
  .seg {
    display: inline-flex;
    border: 1px solid #d7cfc0;
    border-radius: 8px;
    overflow: hidden;
    margin-left: auto;
  }
  .seg button {
    font: inherit;
    font-size: 0.72rem;
    font-weight: 550;
    border: none;
    background: #fff;
    color: #52514e;
    padding: 0.15rem 0.55rem;
    cursor: pointer;
  }
  .seg button + button {
    border-left: 1px solid #d7cfc0;
  }
  .seg button.on {
    background: #b0552f;
    color: #fff;
  }
  .caption {
    font-size: 0.8rem;
    color: #52514e;
    min-height: 2.4em;
    margin: 0.3rem 0 0;
  }
</style>
