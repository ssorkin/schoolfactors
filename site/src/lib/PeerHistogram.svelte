<script>
  /**
   * Where this entity's adjusted level lands among its peers (same kind — and
   * for schools, same level and type), in student SDs. Bars are the peer
   * distribution; the rust line is this entity; dashed lines are parent
   * references (district, county). 0 = typical for the students served.
   */
  let { hist, own = null, kindLabel = 'this school', refs = [] } = $props();

  const W = 340;
  const H = 172;
  const M = { l: 10, r: 10, t: 40, b: 34 };
  const PW = W - M.l - M.r;

  let maxC = $derived(Math.max(...hist.bins, 1));
  let bw = $derived(PW / hist.bins.length);
  let x = $derived((v) => M.l + ((v - hist.lo) / (hist.w * hist.bins.length)) * PW);
  let y = $derived((c) => H - M.b - (c / maxC) * (H - M.t - M.b));
  const clampX = (px) => Math.min(W - M.r - 2, Math.max(M.l + 2, px));

  let markers = $derived.by(() => {
    const list = [];
    if (own != null) list.push({ label: kindLabel, v: own, own: true });
    for (const r of refs) {
      if (r.v != null) list.push({ label: r.label, v: r.v, own: false });
    }
    list.sort((a, b) => a.v - b.v);
    let lastX = -1e9;
    let row = 0;
    for (const m of list) {
      m.px = clampX(x(m.v));
      row = m.px - lastX < 78 ? row + 1 : 0;
      m.row = row;
      lastX = m.px;
    }
    return list;
  });

  const TICKS = [-1, 0, 1];
</script>

<figure class="card">
  <figcaption>
    Adjusted level among {hist.n.toLocaleString()}
    {hist.label}
  </figcaption>
  <svg viewBox="0 0 {W} {H}" role="img"
    aria-label="Histogram of adjusted level among {hist.label}, with this entity marked">
    {#each hist.bins as c, i (i)}
      {#if c > 0}
        <rect
          x={M.l + i * bw + 0.5}
          y={y(c)}
          width={bw - 1}
          height={H - M.b - y(c)}
          class="bar"
        />
      {/if}
    {/each}
    <line x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} class="base" />
    {#each TICKS as t (t)}
      <line x1={x(t)} x2={x(t)} y1={H - M.b} y2={H - M.b + 4} class="base" />
      <text x={x(t)} y={H - M.b + 15} class="tick" text-anchor="middle">
        {t > 0 ? `+${t}` : t}
      </text>
    {/each}
    <text x={W - M.r} y={H - 6} class="tick" text-anchor="end">student SDs, adjusted</text>
    {#each markers as m (m.label)}
      <line x1={m.px} x2={m.px} y1={12 + m.row * 11 + 3} y2={H - M.b} class={m.own ? 'own' : 'ref'} />
      <text
        x={m.px}
        y={10 + m.row * 11}
        class={m.own ? 'ownlbl' : 'reflbl'}
        text-anchor={m.px > W - 70 ? 'end' : m.px < 70 ? 'start' : 'middle'}
      >
        {m.label}
      </text>
    {/each}
  </svg>
  <p class="note">
    0 = typical for {hist.label} serving similar students; right of 0 = scores above
    that expectation.
  </p>
</figure>

<style>
  .card {
    margin: 0;
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 8px;
    padding: 0.6rem 0.8rem;
  }
  figcaption {
    font-size: 0.84rem;
    font-weight: 650;
    color: #52514e;
  }
  svg {
    width: 100%;
    height: auto;
    display: block;
  }
  .bar {
    fill: #2a78d6;
    fill-opacity: 0.32;
  }
  .base {
    stroke: #c3bcae;
  }
  .tick {
    font-size: 10.5px;
    fill: #898781;
  }
  .own {
    stroke: #b0552f;
    stroke-width: 2;
  }
  .ownlbl {
    font-size: 11px;
    font-weight: 700;
    fill: #b0552f;
  }
  .ref {
    stroke: #6f6a61;
    stroke-dasharray: 3 3;
  }
  .reflbl {
    font-size: 10.5px;
    fill: #6f6a61;
  }
  .note {
    margin: 0.35rem 0 0;
    font-size: 0.76rem;
    color: #898781;
  }
</style>
