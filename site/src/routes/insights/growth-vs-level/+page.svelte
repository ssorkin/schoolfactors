<script>
  import { dataUrl } from '$lib/data.js';
  import { onMount } from 'svelte';
  import { POSTS, fmtDate, corr, clamp, fmt2 } from '$lib/insights.js';

  const post = POSTS.find((p) => p.slug === 'growth-vs-level');

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
    falsification test single-number school ratings historically fail. These are
    correlations between school averages — starting points for questions, not
    verdicts.
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
</style>
