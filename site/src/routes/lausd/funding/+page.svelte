<script>
  import SpendChart from '$lib/SpendChart.svelte';
  import FrpmCensusScatter from '$lib/district/FrpmCensusScatter.svelte';

  let { data } = $props();
  let d = $derived(data.district);
  let funding = $derived(data.funding);
  let census = $derived(data.censusFrpm?.meta ? data.censusFrpm : null);

  // enr slots are 12 gapless years with spring labels 2015..2026.
  const ENR_YEARS = Array.from({ length: 12 }, (_, i) => 2015 + i);

  let lcffYears = $derived(Object.keys(funding?.lcff ?? {}).sort());
  let lcffLatest = $derived(lcffYears.length ? funding.lcff[lcffYears[lcffYears.length - 1]] : null);

  const SERIES = [
    ['base', 'Base grant', '#7f93ad'],
    ['supplemental', 'Supplemental', '#2a78d6'],
    ['concentration', 'Concentration', '#eb6834']
  ];
  const BW = 680;
  const BH = 240;
  const BM = { top: 12, right: 16, bottom: 28, left: 46 };
  let lcffMax = $derived(
    Math.max(1, ...lcffYears.map((y) => funding.lcff[y].total ?? 0))
  );
  const bx = (i, n) => BM.left + (i / n) * (BW - BM.left - BM.right);
  const bw = (n) => ((BW - BM.left - BM.right) / n) * 0.62;
  const by = (v) => BM.top + (1 - v / lcffMax) * (BH - BM.top - BM.bottom);
  const fmtB = (v) =>
    v == null ? '—' : v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : `$${Math.round(v / 1e6)}M`;
  const CERT_LABEL = {
    p_1: 'first principal apportionment',
    p_2: 'second principal apportionment',
    an: 'annual',
    annual: 'annual',
    r1: 'annual, recertified',
    anr1: 'annual, recertified',
    anr2: 'annual, recertified',
    anr3: 'annual, recertified'
  };
  let lcffHover = $state(null);
</script>

<svelte:head>
  <title>LAUSD funding — SchoolFactors</title>
  <meta
    name="description"
    content="How LAUSD is funded: LCFF base, supplemental and concentration grants, per-student spending over time, and district poverty counts vs the census."
  />
</svelte:head>

<h2>Spending per student</h2>
<p>
  Per-student spending rose sharply while enrollment fell — the same dollars now
  follow fewer students. Spending and enrollment are drawn as separate panels on a
  shared timeline (never one chart with two value axes).
</p>
<SpendChart enr={d?.enr} enrYears={ENR_YEARS} ppe={d?.ppe_hist} ppeYears={d?.ppe_years} />

<h2>LCFF: how the state funds LAUSD</h2>
{#if lcffYears.length}
  <p>
    California's Local Control Funding Formula sends every district a base grant per
    student, then adds a <b>supplemental</b> grant for each low-income, English
    learner, or foster student, and a <b>concentration</b> grant where those
    students exceed 55% of enrollment. LAUSD's unduplicated share is
    {lcffLatest?.upp == null ? '—' : `${Math.round(lcffLatest.upp * 100)}%`}, so the
    equity add-ons are large:
    {fmtB(lcffLatest?.supplemental)} supplemental +
    {fmtB(lcffLatest?.concentration)} concentration on a
    {fmtB(lcffLatest?.base)} base in
    {Number(lcffYears[lcffYears.length - 1]) - 1}–{lcffYears[lcffYears.length - 1].slice(2)}
    ({CERT_LABEL[lcffLatest?.cert] ?? lcffLatest?.cert}).
  </p>
  <div class="chartwrap">
    <svg viewBox="0 0 {BW} {BH}" role="img" aria-label="LCFF entitlement by component and year">
      {#each [0.25, 0.5, 0.75, 1] as t}
        <line x1={BM.left} y1={by(lcffMax * t)} x2={BW - BM.right} y2={by(lcffMax * t)} stroke="#e1e0d9" />
        <text x={BM.left - 6} y={by(lcffMax * t) + 4} text-anchor="end" class="tick">
          {fmtB(lcffMax * t)}
        </text>
      {/each}
      {#each lcffYears as y, i}
        {@const row = funding.lcff[y]}
        {@const n = lcffYears.length}
        {@const x = bx(i + 0.19, n)}
        <!-- stacked with 2px surface gaps between segments -->
        {#each SERIES as [key, , color], si}
          {@const below = SERIES.slice(0, si).reduce((s, [k]) => s + (row[k] ?? 0), 0)}
          {@const v = row[key] ?? 0}
          <rect
            {x}
            y={by(below + v)}
            width={bw(n)}
            height={Math.max(0, by(below) - by(below + v) - 2)}
            rx="3"
            fill={color}
            onmouseenter={() => (lcffHover = { y, row })}
            onmouseleave={() => (lcffHover = null)}
          />
        {/each}
        <text x={x + bw(n) / 2} y={BH - 8} text-anchor="middle" class="tick">{y}</text>
      {/each}
    </svg>
    <p class="caption">
      {#if lcffHover}
        <b>{lcffHover.y}</b> ({CERT_LABEL[lcffHover.row.cert] ?? lcffHover.row.cert}):
        base {fmtB(lcffHover.row.base)} ·
        supplemental {fmtB(lcffHover.row.supplemental)} · concentration
        {fmtB(lcffHover.row.concentration)} · total {fmtB(lcffHover.row.total)}
      {:else}
        <span class="key">
          {#each SERIES as [, label, color]}
            <span class="k"><span class="sw" style="background:{color}"></span>{label}</span>
          {/each}
        </span>
        Total LCFF entitlement per year, by component. Source: CDE LCFF summary data.
      {/if}
    </p>
  </div>
{:else}
  <p class="pending">LCFF summary data hasn't been exported yet.</p>
{/if}

<h2>District poverty counts vs the census</h2>
<p>
  Districts report far higher poverty rates among their students (FRPM eligibility,
  which drives supplemental and concentration funding) than the Census Bureau
  measures among resident children under the same 185%-of-poverty line — statewide,
  the median district's FRPM rate is about
  {census?.meta?.median_ratio ? `${census.meta.median_ratio.toFixed(1)}×` : '1.8×'}
  the census poverty rate. That's a measurement difference, not an error: direct
  certification, categorical eligibility, and which resident families actually
  enroll all push the district's rate above the census rate. LAUSD reports 83% of
  students FRPM-eligible while the census counts 45% of resident children under the
  same line.
</p>
{#if census}
  <FrpmCensusScatter districts={census.districts} />
{:else}
  <p class="pending">
    The statewide census-vs-FRPM comparison appears here once the ACS acquisition
    runs (it needs a Census API key).
  </p>
{/if}

<h2>SENI: LAUSD's own equity index</h2>
<p>
  On top of LCFF, LAUSD allocates about $700M per year (≈3.8% of its budget)
  directly to schools through the
  <a href="https://www.lausd.org/Page/17238">Student Equity Needs Index</a> — a
  15-indicator formula spanning academics, chronic absence, and community factors
  like neighborhood gun violence and asthma rates.
</p>
{#if funding?.seni}
  {@const s = funding.seni}
  <p>
    In the {Number(s.year) - 1}–{String(s.year).slice(2)} allocation,
    {s.n.toLocaleString()} schools received
    ${(s.total_alloc / 1e6).toFixed(0)}M through SENI, concentrated by need:
  </p>
  <table>
    <thead><tr><th>SENI quintile</th><th>Schools</th><th>Allocation</th><th>Avg per school</th></tr></thead>
    <tbody>
      {#each Object.entries(s.by_quintile).filter(([q]) => q !== '?') as [q, row]}
        <tr>
          <td>{q}{q === '1' ? ' (highest need)' : q === '5' ? ' (lowest need)' : ''}</td>
          <td>{row.n}</td>
          <td>${(row.alloc / 1e6).toFixed(1)}M</td>
          <td>${Math.round(row.alloc / row.n / 1000)}k</td>
        </tr>
      {/each}
    </tbody>
  </table>
  <p class="src">
    Source: LAUSD Open Data Catalog, SENI school-level scores and allocations.
  </p>
{:else}
  <p class="pending">
    Per-school SENI scores will appear here once LAUSD's allocation data is added to
    the pipeline.
  </p>
{/if}

<style>
  .chartwrap {
    overflow-x: auto;
  }
  svg {
    width: 100%;
    max-width: 760px;
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
    font-size: 0.85rem;
    color: #52514e;
    min-height: 1.4em;
  }
  .key {
    margin-right: 0.8rem;
  }
  .k {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    margin-right: 0.8rem;
  }
  .sw {
    width: 11px;
    height: 11px;
    border-radius: 3px;
    display: inline-block;
  }
  .pending {
    color: #6f6a61;
    font-size: 0.88rem;
    background: #fff;
    border: 1px dashed #d7cfc0;
    border-radius: 8px;
    padding: 0.6rem 0.9rem;
  }
  table {
    border-collapse: collapse;
    font-size: 0.88rem;
  }
  th,
  td {
    text-align: right;
    padding: 0.3rem 0.9rem 0.3rem 0;
    border-bottom: 1px solid #eee7da;
  }
  th:first-child,
  td:first-child {
    text-align: left;
  }
  .src {
    font-size: 0.8rem;
    color: #898781;
  }
</style>
