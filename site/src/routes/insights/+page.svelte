<script>
  import { onMount } from 'svelte';

  let items = $state(null);
  let loadError = $state(false);
  onMount(async () => {
    try {
      items = await (await fetch('/data/index.json')).json();
    } catch {
      loadError = true;
    }
  });

  function corr(xs, ys) {
    const n = xs.length;
    if (n < 3) return null;
    const mx = xs.reduce((a, b) => a + b, 0) / n;
    const my = ys.reduce((a, b) => a + b, 0) / n;
    let sxy = 0;
    let sxx = 0;
    let syy = 0;
    for (let i = 0; i < n; i++) {
      sxy += (xs[i] - mx) * (ys[i] - my);
      sxx += (xs[i] - mx) ** 2;
      syy += (ys[i] - my) ** 2;
    }
    return sxx && syy ? sxy / Math.sqrt(sxx * syy) : null;
  }
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  // ---- Chart A: adjusted growth vs adjusted level, statewide ----
  const W = 860;
  const H = 520;
  const M = { top: 18, right: 20, bottom: 48, left: 58 };
  const AX = [-1.6, 1.6];
  const AY = [-0.28, 0.28];
  const asx = (v) => M.left + ((v - AX[0]) / (AX[1] - AX[0])) * (W - M.left - M.right);
  const asy = (v) => M.top + ((AY[1] - v) / (AY[1] - AY[0])) * (H - M.top - M.bottom);

  let glSchools = $derived(
    (items ?? []).filter(
      (e) => e.kind === 'school' && e.level_adj_eb != null && e.growth_adj_eb != null
    )
  );
  let glCorr = $derived(
    corr(glSchools.map((e) => e.level_adj_eb), glSchools.map((e) => e.growth_adj_eb))
  );

  // ---- Chart B: enrollment change vs early scores, LAUSD standard elementaries ----
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

  const fmt2 = (v) => (v > 0 ? '+' : '') + v.toFixed(2);
</script>

<svelte:head><title>Insights — SchoolFactors</title></svelte:head>

<h1>Insights</h1>
<p class="lede">
  Patterns in the statewide data, each with the hypothesis we bring to it and the
  caution it deserves. These are correlations between school averages — starting
  points for questions, not verdicts.
</p>

{#if items}
  <h2>Scoring high and improving fast are different things</h2>
  <p>
    Each dot is a school, placed by where its students score
    (<strong>horizontal</strong>) and how fast its cohorts progress grade-to-grade
    (<strong>vertical</strong>) — both relative to California schools serving
    similar students. If high scores mostly reflected what schools contribute,
    the two would move together. They are essentially unrelated
    (r&nbsp;=&nbsp;{glCorr == null ? '…' : fmt2(glCorr)} across
    {glSchools.length.toLocaleString()} schools): plenty of modest-scoring schools
    are where students progress fastest, and plenty of high-scoring schools coast.
    The shaded cross marks the zone not meaningfully different from expectation.
  </p>
  <svg viewBox="0 0 {W} {H}" role="img" aria-label="Scatter plot of adjusted growth versus adjusted level for all California schools">
    <rect x={asx(-0.1)} y={M.top} width={asx(0.1) - asx(-0.1)} height={H - M.top - M.bottom} fill="#eee9df" />
    <rect x={M.left} y={asy(0.02)} width={W - M.left - M.right} height={asy(-0.02) - asy(0.02)} fill="#eee9df" />
    <line x1={M.left} x2={W - M.right} y1={asy(0)} y2={asy(0)} stroke="#c3bcae" />
    <line x1={asx(0)} x2={asx(0)} y1={M.top} y2={H - M.bottom} stroke="#c3bcae" />
    {#each [-1.5, -1, -0.5, 0.5, 1, 1.5] as t (t)}
      <text x={asx(t)} y={H - M.bottom + 20} class="tick" text-anchor="middle">{t > 0 ? '+' + t : t}</text>
    {/each}
    {#each [-0.2, -0.1, 0.1, 0.2] as t (t)}
      <text x={M.left - 8} y={asy(t) + 4} class="tick" text-anchor="end">{t > 0 ? '+' + t : t}</text>
    {/each}
    <text x={(M.left + W - M.right) / 2} y={H - 8} class="axis" text-anchor="middle">
      Adjusted level (student SDs vs similar schools) →
    </text>
    <text x={16} y={(M.top + H - M.bottom) / 2} class="axis" text-anchor="middle"
      transform="rotate(-90 16 {(M.top + H - M.bottom) / 2})">
      Adjusted growth (SDs per grade) →
    </text>
    {#each glSchools as s (s.cds)}
      <circle
        cx={asx(clamp(s.level_adj_eb, AX[0], AX[1]))}
        cy={asy(clamp(s.growth_adj_eb, AY[0], AY[1]))}
        r="1.5"
        fill="#2a78d6"
        fill-opacity="0.25"
      />
    {/each}
  </svg>
  <p class="note">
    Schools testing a single grade (most high schools) have no growth estimate and
    are absent here. Both axes are shrunken estimates; the correlation is the
    falsification test single-number school ratings historically fail.
  </p>

  <h2>Where families have choice, enrollment drains from low-scoring schools</h2>
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
  .lede {
    font-size: 1.05rem;
    color: #4a453d;
    max-width: 46rem;
  }
  h2 {
    margin-top: 2.2rem;
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
