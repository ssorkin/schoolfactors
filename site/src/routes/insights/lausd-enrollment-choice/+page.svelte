<script>
  import { dataUrl } from '$lib/data.js';
  import { onMount } from 'svelte';
  import { POSTS, fmtDate, corr, clamp, fmt2 } from '$lib/insights.js';

  const post = POSTS.find((p) => p.slug === 'lausd-enrollment-choice');

  let items = $state(null);
  let loadError = $state(false);
  onMount(async () => {
    try {
      items = await (await fetch(dataUrl('/data/index.json'))).json();
    } catch {
      loadError = true;
    }
  });

  const W = 860;
  const H = 520;
  const M = { top: 18, right: 20, bottom: 48, left: 58 };

  // Change = census enrollment, 2014-15/2015-16 average -> 2024-25/2025-26
  // average (enr slots: 12 gapless years, 2015..2026 spring labels).
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

  const BX = [0, 80];
  const BY = [-0.8, 0.6];
  const bsx = (v) => M.left + ((v - BX[0]) / (BX[1] - BX[0])) * (W - M.left - M.right);
  const bsy = (v) => M.top + ((BY[1] - v) / (BY[1] - BY[0])) * (H - M.top - M.bottom);
</script>

<svelte:head>
  <title>{post.title} — SchoolFactors Insights</title>
  <meta name="description" content={post.blurb} />
</svelte:head>

<nav class="crumbs"><a href="/insights">← Insights</a></nav>
<h1>{post.title}</h1>
<p class="date">{fmtDate(post.date)}</p>

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
    lower-scoring schools shrank more. Notably, the correlation with the
    <em>demographically adjusted</em> level is much weaker: choice appears to
    respond to raw scores, which largely track demographics rather than school
    contribution.
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
  <p class="note">
    Cautions: LAUSD enrollment fell district-wide over this period — even large
    elementaries shrank ~25% at the median — so the pattern is "who shrank
    <em>more</em>", not "who shrank". Shrinking to critically small size itself
    changes a school (mixed-grade classrooms, fixed costs over fewer students),
    and correlation here does not establish that scores caused the moves. Every
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
