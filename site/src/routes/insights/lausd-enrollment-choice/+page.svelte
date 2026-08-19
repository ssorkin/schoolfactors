<script>
  import { dataUrl } from '$lib/data.js';
  import { onMount } from 'svelte';
  import { POSTS, fmtDate, corr, clamp, fmt2 } from '$lib/insights.js';

  const post = POSTS.find((p) => p.slug === 'lausd-enrollment-choice');

  let items = $state(null);
  let boundaries = $state(null);
  let loadError = $state(false);
  onMount(async () => {
    try {
      items = await (await fetch(dataUrl('/data/index.json'))).json();
    } catch {
      loadError = true;
    }
    try {
      boundaries = await (await fetch(dataUrl('/data/lausd/boundaries_e.geojson'))).json();
    } catch {
      /* part two degrades to text */
    }
  });

  const W = 860;
  const H = 520;
  const M = { top: 18, right: 20, bottom: 48, left: 58 };

  // Part 1 (original analysis, unchanged): census enrollment change,
  // 2014-15/2015-16 average -> 2024-25/2025-26 average, vs early raw Met+.
  const LAUSD = '19647330000000';
  const SMALL = 200;
  let shrinkRows = $derived.by(() => {
    const out = [];
    for (const e of items ?? []) {
      if (e.kind !== 'school' || e.district_cds !== LAUSD) continue;
      if (e.eil !== 'ELEM' || (e.flags ?? []).length) continue;
      const early = (e.spark ?? []).slice(0, 2).filter((v) => v != null);
      const a = (e.enr ?? []).slice(0, 2).filter((v) => v);
      const b = (e.enr ?? []).slice(10, 12).filter((v) => v);
      if (!early.length || !a.length || !b.length) continue;
      out.push({
        cds: e.cds,
        name: e.name,
        met: early.reduce((s, v) => s + v, 0) / early.length,
        chg: (b.reduce((s, v) => s + v, 0) / b.length) / (a.reduce((s, v) => s + v, 0) / a.length) - 1,
        small: (e.enrollment ?? Infinity) < SMALL,
        enrollment: e.enrollment
      });
    }
    return out;
  });
  let shrinkCorr = $derived(
    corr(shrinkRows.map((r) => r.met), shrinkRows.map((r) => r.chg))
  );
  let nSmall = $derived(shrinkRows.filter((r) => r.small).length);

  // Part 2 (the revisit): per-attendance-area divergence — the zoned school's
  // enrollment change (2010-11 -> 2020-21) minus its own neighborhood's change
  // in resident children (2010 -> 2020 decennial blocks) — joined to the same
  // early raw scores.
  let divRows = $derived.by(() => {
    if (!boundaries || !items) return [];
    const byCds = new Map(
      items.filter((e) => e.kind === 'school').map((e) => [e.cds, e])
    );
    const out = [];
    const seen = new Set(); // a school can be primary for two zones — one dot each school
    for (const f of boundaries.features) {
      const p = f.properties;
      if (p.diverge == null || !p.cds || seen.has(p.cds)) continue;
      seen.add(p.cds);
      const e = byCds.get(p.cds);
      if (!e) continue;
      const early = (e.spark ?? []).slice(0, 2).filter((v) => v != null);
      if (!early.length) continue;
      out.push({
        cds: p.cds,
        name: e.name,
        met: early.reduce((s, v) => s + v, 0) / early.length,
        div: p.diverge,
        sch: p.sch_chg,
        kid: p.kid_chg,
        small: (e.enrollment ?? Infinity) < SMALL
      });
    }
    return out;
  });
  let rSch = $derived(corr(divRows.map((r) => r.met), divRows.map((r) => r.sch)));
  let rKid = $derived(corr(divRows.map((r) => r.met), divRows.map((r) => r.kid)));
  let rDiv = $derived(corr(divRows.map((r) => r.met), divRows.map((r) => r.div)));

  const BX = [0, 80];
  const BY = [-0.8, 0.6];
  const bsx = (v) => M.left + ((v - BX[0]) / (BX[1] - BX[0])) * (W - M.left - M.right);
  const bsy = (v) => M.top + ((BY[1] - v) / (BY[1] - BY[0])) * (H - M.top - M.bottom);

  const DY = [-80, 80]; // divergence, percentage points
  const dsy = (v) => M.top + ((DY[1] - v) / (DY[1] - DY[0])) * (H - M.top - M.bottom);
</script>

<svelte:head>
  <title>{post.title} — SchoolFactors Insights</title>
  <meta name="description" content={post.blurb} />
</svelte:head>

<nav class="crumbs"><a href="/insights">← Insights</a></nav>
<h1>{post.title}</h1>
<p class="date">
  {fmtDate(post.date)}{post.updated ? ` · updated ${fmtDate(post.updated)}` : ''}
  {#if post.author}· by {post.author}{/if}
</p>

{#if items}
  <p>
    Hypothesis: parents act on raw test scores. Los Angeles Unified — a district
    with abundant school choice and a decade of declining enrollment — is a natural
    place to look. Each dot is one of {shrinkRows.length} standard (non-charter,
    non-magnet) LAUSD elementary schools, placed by its raw Met+ rate in 2015–16
    (<strong>horizontal</strong>) and how its census enrollment changed from
    2014–15/2015–16 to 2024–25/2025–26 (<strong>vertical</strong>).
    <span class="hl">Orange</span> dots are schools now critically small
    (under {SMALL} students; {nSmall} of them). Enrollment change correlates
    {shrinkCorr == null ? '…' : fmt2(shrinkCorr)} with those early raw scores —
    lower-scoring schools shrank more.
  </p>
  <svg viewBox="0 0 {W} {H}" role="img" aria-label="Scatter plot of enrollment change versus early test scores for LAUSD standard elementary schools">
    <line x1={M.left} x2={W - M.right} y1={bsy(0)} y2={bsy(0)} stroke="#c3bcae" />
    {#each [0, 20, 40, 60, 80] as t (t)}
      <text x={bsx(t)} y={H - M.bottom + 20} class="tick" text-anchor="middle">{t}%</text>
    {/each}
    {#each [-0.6, -0.4, -0.2, 0.2, 0.4] as t (t)}
      <text x={M.left - 8} y={bsy(t) + 4} class="tick" text-anchor="end">{Math.round(t * 100) > 0 ? '+' : ''}{Math.round(t * 100)}%</text>
    {/each}
    <text x={(M.left + W - M.right) / 2} y={H - 8} class="axis" text-anchor="middle">
      Met+ rate, 2015–16 (raw) →
    </text>
    <text x={16} y={(M.top + H - M.bottom) / 2} class="axis" text-anchor="middle"
      transform="rotate(-90 16 {(M.top + H - M.bottom) / 2})">
      Census enrollment change, 2015–16 → 2025–26
    </text>
    {#each shrinkRows as s (s.cds)}
      <a href="/school/{s.cds}">
        <circle
          cx={bsx(clamp(s.met, BX[0], BX[1]))}
          cy={bsy(clamp(s.chg, BY[0], BY[1]))}
          r={s.small ? 4.5 : 3}
          fill={s.small ? '#d97b29' : '#2a78d6'}
          fill-opacity={s.small ? 0.85 : 0.4}
        >
          <title>{s.name} — Met+ {Math.round(s.met)}% in 2015–16, enrollment {s.chg > 0 ? '+' : ''}{Math.round(s.chg * 100)}%, now {s.enrollment?.toLocaleString() ?? '?'} students</title>
        </circle>
      </a>
    {/each}
  </svg>

  <h2>The revisit: what if the children simply left?</h2>
  <p>
    When we first published this, we read the pattern as choice responding to raw
    scores. But a shrinking school has two very different explanations: families
    <em>opting out</em>, or families <em>no longer living there</em>. Telling them
    apart requires knowing how many children live in each school's attendance area
    — which we can now measure, using LAUSD's own attendance-boundary GIS joined to
    exact census block counts (2010 → 2020).
  </p>
  {#if divRows.length}
    <p>
      The result changes the story. Across {divRows.length} zoned LAUSD
      elementaries, the school's enrollment change (2010-11 → 2020-21) correlates
      {rSch == null ? '…' : fmt2(rSch)} with its early raw scores — the original
      finding, reproduced. But the change in <em>resident children in the school's
      own attendance area</em> correlates {rKid == null ? '…' : fmt2(rKid)} with
      those same scores: the neighborhoods of low-scoring schools lost children at
      almost exactly the rate their schools lost students. Subtract the
      neighborhood from the school — <strong>enrollment divergence</strong>, below
      — and the relationship with early scores mostly disappears
      ({rDiv == null ? '…' : fmt2(rDiv)}).
    </p>
    <svg viewBox="0 0 {W} {H}" role="img" aria-label="Scatter plot of enrollment divergence versus early test scores for zoned LAUSD elementary schools">
      <line x1={M.left} x2={W - M.right} y1={dsy(0)} y2={dsy(0)} stroke="#c3bcae" />
      {#each [0, 20, 40, 60, 80] as t (t)}
        <text x={bsx(t)} y={H - M.bottom + 20} class="tick" text-anchor="middle">{t}%</text>
      {/each}
      {#each [-60, -30, 30, 60] as t (t)}
        <text x={M.left - 8} y={dsy(t) + 4} class="tick" text-anchor="end">{t > 0 ? '+' : ''}{t}pp</text>
      {/each}
      <text x={(M.left + W - M.right) / 2} y={H - 8} class="axis" text-anchor="middle">
        Met+ rate, 2015–16 (raw) →
      </text>
      <text x={16} y={(M.top + H - M.bottom) / 2} class="axis" text-anchor="middle"
        transform="rotate(-90 16 {(M.top + H - M.bottom) / 2})">
        Divergence: school change − neighborhood children change (pp)
      </text>
      {#each divRows as s (s.cds)}
        <a href="/school/{s.cds}">
          <circle
            cx={bsx(clamp(s.met, BX[0], BX[1]))}
            cy={dsy(clamp(s.div, DY[0], DY[1]))}
            r={s.small ? 4.5 : 3}
            fill={s.small ? '#d97b29' : '#2a78d6'}
            fill-opacity={s.small ? 0.85 : 0.4}
          >
            <title>{s.name} — Met+ {Math.round(s.met)}% in 2015–16; school {s.sch > 0 ? '+' : ''}{Math.round(s.sch * 100)}% vs neighborhood children {s.kid > 0 ? '+' : ''}{Math.round(s.kid * 100)}% = {s.div > 0 ? '+' : ''}{s.div}pp</title>
          </circle>
        </a>
      {/each}
    </svg>
    <p>
      So the honest reading of the first chart is mostly <em>demographic
      geography</em>: the neighborhoods around low-scoring schools — poorer, more
      exposed to rising housing costs and falling birth rates — lost school-age
      children fastest, and their schools shrank with them. What remains after the
      subtraction is a weak residual in the hypothesized direction: schools with
      lower early scores did shrink somewhat faster than their own neighborhoods,
      but far less than the raw chart suggests. The wider context points the same
      way: inside LAUSD's boundary, resident children fell 8% while traditional
      LAUSD enrollment fell 24%, charters didn't grow, private-school share held
      flat — and the census count of resident public-school children not accounted
      for by LAUSD-associated schools tripled. The full decomposition is on the
      <a href="/lausd/enrollment">LAUSD enrollment page</a>, and divergence is
      mapped area by area on the <a href="/lausd/map">attendance-area map</a>.
    </p>
  {:else}
    <p class="note">Loading the attendance-area data…</p>
  {/if}
  <p class="note">
    Cautions: the two charts use different windows (the original uses 2015–16 →
    2025–26 enrollment; divergence uses 2010-11 → 2020-21 to match the decennial
    census), and the 2015–16 scores sit mid-window for the divergence measure.
    Divergence is not a capture rate — schools enroll across boundary lines in both
    directions — and none of this establishes what caused any family's move. Every
    dot links to that school's page.
  </p>
{:else if loadError}
  <p class="note">Couldn't load the dataset — please reload the page.</p>
{:else}
  <p class="note">Loading the dataset…</p>
{/if}

<style>
  .crumbs {
    font-size: 0.9rem;
    margin-bottom: 0.4rem;
  }
  .crumbs a {
    text-decoration: none;
    color: #898781;
  }
  .crumbs a:hover {
    color: #b0552f;
  }
  h1 {
    margin: 0.2rem 0 0.1rem;
  }
  .date {
    color: #898781;
    font-size: 0.88rem;
    margin-top: 0;
  }
  p {
    max-width: 46rem;
  }
  svg {
    width: 100%;
    height: auto;
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
  }
  .tick {
    font-size: 12px;
    fill: #898781;
  }
  .axis {
    font-size: 13px;
    fill: #52514e;
  }
  .note {
    color: #6f6a61;
    font-size: 0.9rem;
    max-width: 46rem;
  }
  .hl {
    color: #d97b29;
    font-weight: 650;
  }
  a circle {
    cursor: pointer;
  }
  a:hover circle {
    fill-opacity: 1;
  }
</style>
