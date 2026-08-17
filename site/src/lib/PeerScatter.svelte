<script>
  import { dataUrl } from '$lib/data.js';
  /**
   * The signature context view: this entity among nearby peers (same kind —
   * for schools, same level and type). x = adjusted level ("scores vs. similar
   * schools"); y = ABSOLUTE improvement per year (state-relative trend plus
   * the state's own movement against a fixed benchmark), so California itself
   * appears as a labeled dot — a school above it is improving faster than the
   * state; below it, the state is catching up. The cloud narrows to the
   * nearest peers within ~25 miles (capped at 500); in sparse areas it widens
   * to the nearest 50 statewide. Peers fetch client-side from a shared
   * per-group file so the cloud is cached across pages.
   */
  import { goto } from '$app/navigation';

  let {
    peerKey,
    own = null, // { cds, x, y, ll }
    ownLabel = 'This school',
    label = 'similar schools',
    kind = 'school',
    refs = [],
    stateY = null,
    // 'growth': y = absolute cohort movement per year vs the fixed Standard
    // Met threshold (multi-grade entities). 'trend': y = absolute improvement
    // per year across successive cohorts (single-grade fallback).
    yMode = 'growth',
    // Extra highlighted schools: comparison overlays ({cds, name, x, y,
    // kind: 'overlay'}) and the nearby-schools list ({cds, name,
    // kind: 'nearby'} — position resolved from the peer file).
    highlights = []
  } = $props();

  const RADIUS_MI = 25;
  const MAX_PEERS = 500;
  const MIN_PEERS = 50;

  let peers = $state(null);
  $effect(() => {
    const key = peerKey;
    if (!key) return;
    let alive = true;
    fetch(dataUrl(`/data/peers/${key}.json`))
      .then((r) => (r.ok ? r.json() : []))
      .then((rows) => {
        if (alive) peers = rows;
      })
      .catch(() => {
        if (alive) peers = [];
      });
    return () => {
      alive = false;
    };
  });

  function miles(a, b) {
    const R = 3959;
    const toR = Math.PI / 180;
    const dLat = (b[0] - a[0]) * toR;
    const dLon = (b[1] - a[1]) * toR;
    const s =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(a[0] * toR) * Math.cos(b[0] * toR) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(s));
  }

  let yOf = $derived((p) => (yMode === 'growth' ? p[3] : p[4]));
  let byCds = $derived(new Map((peers ?? []).map((p) => [p[0], p])));
  let marks = $derived.by(() => {
    const out = [];
    for (const h of highlights) {
      if (h.cds === own?.cds) continue;
      let x = h.x;
      let y = h.y;
      if (x == null || y == null) {
        const p = byCds.get(h.cds);
        if (!p) continue;
        x = x ?? p[2];
        y = y ?? yOf(p);
      }
      if (x == null || y == null) continue;
      out.push({ cds: h.cds, name: h.name, x, y, kind: h.kind });
    }
    return out;
  });
  let marked = $derived(new Set(marks.map((m) => m.cds)));

  // Nearby cloud with rural adaptation: within RADIUS_MI, nearest-500 cap;
  // fewer than MIN_PEERS nearby → nearest MIN_PEERS regardless of distance.
  // Highlighted schools leave the faint cloud (they draw as marks instead).
  let nearby = $derived.by(() => {
    const all = (peers ?? []).filter(
      (p) => p[0] !== own?.cds && yOf(p) != null && !marked.has(p[0])
    );
    if (!own?.ll) return { rows: all.slice(0, MAX_PEERS), mode: 'statewide' };
    const withD = all
      .filter((p) => p[5])
      .map((p) => ({ p, d: miles(own.ll, p[5]) }))
      .sort((a, b) => a.d - b.d);
    const inRadius = withD.filter((x) => x.d <= RADIUS_MI);
    if (inRadius.length >= MIN_PEERS) {
      return { rows: inRadius.slice(0, MAX_PEERS).map((x) => x.p), mode: 'radius' };
    }
    return { rows: withD.slice(0, MIN_PEERS).map((x) => x.p), mode: 'nearest' };
  });
  let cloud = $derived(nearby.rows);

  const W = 560;
  const H = 430;
  const M = { t: 24, r: 16, b: 50, l: 56 };
  const DX = [-1.6, 1.6];
  const clamp = (v, [a, b]) => Math.max(a, Math.min(b, v));
  const X = (v) => M.l + ((clamp(v, DX) - DX[0]) / (DX[1] - DX[0])) * (W - M.l - M.r);
  let DY = $derived(yMode === 'growth' ? [-0.28, 0.28] : [-0.12, 0.12]);
  let Y = $derived((v) => M.t + ((DY[1] - clamp(v, DY)) / (DY[1] - DY[0])) * (H - M.t - M.b));
  let yTicks = $derived(yMode === 'growth' ? [-0.2, -0.1, 0.1, 0.2] : [-0.1, -0.05, 0.05, 0.1]);
  const fmt = (v) => (v > 0 ? '+' : '') + v.toFixed(2);

  let shownRefs = $derived(refs.filter((r) => r.x != null && r.y != null));

  let hoverPts = $derived([
    ...cloud.map((p) => ({ cds: p[0], name: p[1], x: p[2], y: yOf(p) })),
    ...marks
  ]);
  let hover = $state(null);
  function onmove(ev) {
    if (!hoverPts.length) return;
    const r = ev.currentTarget.getBoundingClientRect();
    const px = ((ev.clientX - r.left) / r.width) * W;
    const py = ((ev.clientY - r.top) / r.height) * H;
    let best = null;
    for (const p of hoverPts) {
      const dx = X(p.x) - px;
      const dy = Y(p.y) - py;
      const d2 = dx * dx + dy * dy;
      if (!best || d2 < best.d2) best = { p, d2 };
    }
    hover = best && best.d2 < 14 * 14 ? best.p : null;
  }

  let QUADS = $derived.by(() => {
    const [up, down] =
      yMode === 'growth'
        ? ['cohorts gaining', 'cohorts slipping']
        : ['improving', 'declining'];
    return [
      { x: 'end', px: W - M.r - 6, py: M.t + 13, text: `higher scores · ${up}` },
      { x: 'end', px: W - M.r - 6, py: H - M.b - 7, text: `higher scores · ${down}` },
      { x: 'start', px: M.l + 6, py: M.t + 13, text: `lower scores · ${up}` },
      { x: 'start', px: M.l + 6, py: H - M.b - 7, text: `lower scores · ${down}` }
    ];
  });
</script>

{#if own?.x != null && own?.y != null}
  <figure class="card">
    <figcaption>
      {ownLabel} among
      {#if cloud.length}{cloud.length.toLocaleString()}{/if}
      {nearby.mode === 'radius' ? 'nearby ' : nearby.mode === 'nearest' ? 'nearest ' : ''}{label}
    </figcaption>
    <div class="legend">
      <span>
        <svg width="13" height="13" aria-hidden="true"><circle cx="6.5" cy="6.5" r="5" class="own" /></svg>
        {ownLabel}
      </span>
      {#if stateY != null}
        <span>
          <svg width="13" height="13" aria-hidden="true">
            <path d="M 6.5 1 L 12 6.5 L 6.5 12 L 1 6.5 Z" class="statemark" />
          </svg>
          California avg
        </span>
      {/if}
      {#each shownRefs as r (r.label)}
        <span>
          <svg width="13" height="13" aria-hidden="true">
            {#if r.shape === 'triangle'}
              <path d="M 6.5 1 L 12 11.5 L 1 11.5 Z" class="refmark" />
            {:else}
              <rect x="2" y="2" width="9" height="9" class="refmark" />
            {/if}
          </svg>
          {r.label}
        </span>
      {/each}
      {#if marks.some((m) => m.kind === 'overlay')}
        <span>
          <svg width="13" height="13" aria-hidden="true"><circle cx="6.5" cy="6.5" r="4.5" class="ovmark" /></svg>
          Compared
        </span>
      {/if}
      {#if marks.some((m) => m.kind === 'nearby')}
        <span>
          <svg width="13" height="13" aria-hidden="true"><circle cx="6.5" cy="6.5" r="4" class="nearmark" /></svg>
          Nearby list
        </span>
      {/if}
    </div>
    <div class="plot">
      <!-- svelte-ignore a11y_no_noninteractive_element_interactions a11y_click_events_have_key_events -->
      <svg
        viewBox="0 0 {W} {H}"
        role="img"
        aria-label="Scatter of {label}: adjusted level vs absolute improvement per year, with this {kind} and the state marked"
        class:pointing={hover}
        onmousemove={onmove}
        onmouseleave={() => (hover = null)}
        onclick={() => hover && goto(`/${kind}/${hover.cds}`)}
      >
        <line x1={M.l} x2={W - M.r} y1={Y(0)} y2={Y(0)} class="zero" />
        <line x1={X(0)} x2={X(0)} y1={M.t} y2={H - M.b} class="zero" />
        {#each QUADS as q (q.text)}
          <text x={q.px} y={q.py} text-anchor={q.x} class="quad">{q.text}</text>
        {/each}
        {#each [-1, 1] as t (t)}
          <text x={X(t)} y={H - M.b + 16} class="tick" text-anchor="middle">{t > 0 ? '+' + t : t}</text>
        {/each}
        {#each yTicks as t (t)}
          <text x={M.l - 7} y={Y(t) + 3.5} class="tick" text-anchor="end">{t > 0 ? '+' + t : t}</text>
        {/each}
        <text x={(M.l + W - M.r) / 2} y={H - 8} class="axis" text-anchor="middle">
          Scores vs. similar {kind}s (student SDs) →
        </text>
        <text
          x={14}
          y={(M.t + H - M.b) / 2}
          class="axis"
          text-anchor="middle"
          transform="rotate(-90 14 {(M.t + H - M.b) / 2})"
        >
          {yMode === 'growth'
            ? 'Cohort movement per year vs grade-level standards (SDs) →'
            : 'Improvement per year (student SDs) →'}
        </text>
        {#each cloud as p (p[0])}
          <circle
            cx={X(p[2])}
            cy={Y(yOf(p))}
            r={hover?.cds === p[0] ? 4 : 2}
            class="peer"
            class:hot={hover?.cds === p[0]}
          />
        {/each}
        {#each marks as m (m.cds)}
          {#if m.kind === 'overlay'}
            <circle cx={X(m.x)} cy={Y(m.y)} r={hover?.cds === m.cds ? 6 : 5} class="ovmark" />
            <text
              x={X(m.x) + (X(m.x) > W - 130 ? -9 : 9)}
              y={Y(m.y) + 3.5}
              class="ovlbl"
              text-anchor={X(m.x) > W - 130 ? 'end' : 'start'}
              >{m.name.length > 18 ? m.name.slice(0, 17) + '…' : m.name}</text
            >
          {:else}
            <circle cx={X(m.x)} cy={Y(m.y)} r={hover?.cds === m.cds ? 5 : 4} class="nearmark" />
          {/if}
        {/each}
        {#if stateY != null}
          {@const sx = X(0)}
          {@const sy = Y(stateY)}
          <path d="M {sx} {sy - 6.5} L {sx + 6.5} {sy} L {sx} {sy + 6.5} L {sx - 6.5} {sy} Z" class="statemark" />
        {/if}
        {#each shownRefs as r (r.label)}
          {#if r.shape === 'triangle'}
            <path
              d="M {X(r.x)} {Y(r.y) - 6} L {X(r.x) + 5.5} {Y(r.y) + 4} L {X(r.x) - 5.5} {Y(r.y) + 4} Z"
              class="refmark"
            />
          {:else}
            <rect x={X(r.x) - 4.5} y={Y(r.y) - 4.5} width="9" height="9" class="refmark" />
          {/if}
        {/each}
        <circle cx={X(own.x)} cy={Y(own.y)} r="6.5" class="own" />
      </svg>
      {#if hover}
        <div class="tip" style:left="{(X(hover.x) / W) * 100}%" style:top="{(Y(hover.y) / H) * 100}%">
          <strong>{hover.name}</strong>
          <span>scores {fmt(hover.x)} · {yMode === 'growth' ? 'cohorts' : 'improving'} {fmt(hover.y)}/yr</span>
        </div>
      {/if}
    </div>
    <p class="note">
      {#if nearby.mode === 'radius'}
        Each faint dot is one of the {cloud.length.toLocaleString()}
        {label} within about {RADIUS_MI} miles{kind === 'school' ? ' (same level and type)' : ''}
        whose estimates pass the reliability gate.
      {:else if nearby.mode === 'nearest'}
        Few {label} sit within {RADIUS_MI} miles, so the cloud widens to the
        nearest {cloud.length} with reliable estimates.
      {:else}
        Each faint dot is one of the {label} whose estimates pass the
        reliability gate.
      {/if}
      Farther right = scores above what's typical for {kind}s serving similar
      students.
      {#if yMode === 'growth'}
        Higher = each class gains against grade-level standards as it moves up;
        at 0, a class holds its distribution against the standards. The
        California diamond is the typical state cohort — dots above it hold up
        better across grades than the state's classes do.
      {:else}
        Higher = improving faster in absolute terms; dots above the California
        diamond are outpacing the state, below it the state is catching up.
        Improvement across years can reflect changing enrollment as well as
        the {kind}.
      {/if}
      Hover for names; click to open that {kind}'s page.
    </p>
  </figure>
{/if}

<style>
  .card {
    margin: 0;
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 8px;
    padding: 0.6rem 0.8rem;
  }
  figcaption {
    font-size: 0.86rem;
    font-weight: 650;
    color: #52514e;
  }
  .plot {
    position: relative;
  }
  svg {
    width: 100%;
    height: auto;
    display: block;
  }
  svg.pointing {
    cursor: pointer;
  }
  .zero {
    stroke: #c3bcae;
  }
  .quad {
    font-size: 10px;
    fill: #b5aea1;
  }
  .tick {
    font-size: 10.5px;
    fill: #898781;
  }
  .axis {
    font-size: 11.5px;
    fill: #52514e;
  }
  .peer {
    fill: #8d8574;
    fill-opacity: 0.3;
  }
  .peer.hot {
    fill: #2a78d6;
    fill-opacity: 0.95;
  }
  .refmark {
    fill: none;
    stroke: #1c5cab;
    stroke-width: 1.8;
  }
  .statemark {
    fill: #2b2722;
    stroke: #fffdf9;
    stroke-width: 1.5;
  }
  .own {
    fill: #b0552f;
    stroke: #fffdf9;
    stroke-width: 2;
  }
  .ovmark {
    fill: #2a78d6;
    stroke: #fffdf9;
    stroke-width: 1.5;
  }
  .ovlbl {
    font-size: 10.5px;
    font-weight: 650;
    fill: #1c5cab;
  }
  .nearmark {
    fill: none;
    stroke: #2a78d6;
    stroke-width: 1.6;
  }
  .legend {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    font-size: 0.78rem;
    color: #52514e;
    margin: 0.2rem 0 0.1rem;
  }
  .legend span {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
  }
  .tip {
    position: absolute;
    transform: translate(-50%, -130%);
    background: #2b2722;
    color: #faf7f2;
    border-radius: 6px;
    font-size: 0.76rem;
    padding: 0.25rem 0.55rem;
    display: flex;
    flex-direction: column;
    pointer-events: none;
    white-space: nowrap;
    max-width: 20rem;
  }
  .note {
    margin: 0.4rem 0 0;
    font-size: 0.76rem;
    color: #898781;
  }
</style>
