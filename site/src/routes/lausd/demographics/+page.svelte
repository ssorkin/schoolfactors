<script>
  import { onMount } from 'svelte';
  import DemoBars from '$lib/district/DemoBars.svelte';
  import StackedArea from '$lib/district/StackedArea.svelte';
  import { getBoundaries, getSchools } from '$lib/district/lausdData.js';
  import { corr, clamp, fmt2 } from '$lib/insights.js';

  let { data } = $props();
  let demo = $derived(data.demographics);

  // Race composition over time (stacked counts, matching series colors).
  const RACE_SERIES = [
    { key: 'his', label: 'Hispanic or Latino', color: '#2a78d6' },
    { key: 'wht', label: 'White', color: '#eb6834' },
    { key: 'blk', label: 'Black', color: '#1baf7a' },
    { key: 'asn', label: 'Asian', color: '#eda100' },
    { key: 'oth', label: 'Other / two or more', color: '#d8d4cc' }
  ];
  let residentHist = $derived(demo?.race_hist?.resident ?? []);
  let enrolledHist = $derived(demo?.race_hist?.enrolled ?? []);
  function raceChg(rows, key) {
    if (rows.length < 2) return null;
    const a = rows[0][1][key];
    const b = rows[rows.length - 1][1][key];
    if (!a) return null;
    return { a, b, pct: Math.round((b / a - 1) * 100) };
  }
  const fmtKk = (v) => `${Math.round(v / 1000)}k`;
  const rc = (d) =>
    d == null ? '—' : `${fmtKk(d.a)} → ${fmtKk(d.b)} (${d.pct > 0 ? '+' : ''}${d.pct}%)`;

  // SED measures over time (line chart).
  let sed = $derived(demo?.sed_hist ?? null);
  const SW = 680;
  const SH = 240;
  const SM = { top: 14, right: 16, bottom: 28, left: 46 };
  const SED_SERIES = [
    { key: 'frpm', label: 'FRPM-eligible (district-reported, 185% FPL)', color: '#eb6834', dash: '' },
    { key: 'upc', label: 'CALPADS UPC (FRPM ∪ EL ∪ foster — LCFF funding)', color: '#b0552f', dash: '2 3' },
    { key: 'p185', label: 'Resident children 6–17 under 185% FPL (census)', color: '#2a78d6', dash: '5 4' }
  ];
  let sedYears = $derived.by(() => {
    if (!sed) return [2015, 2026];
    const ys = SED_SERIES.flatMap((s) => (sed[s.key] ?? []).map(([y]) => y));
    return [Math.min(...ys), Math.max(...ys)];
  });
  const sx = $derived(
    (y) => SM.left + ((y - sedYears[0]) / Math.max(sedYears[1] - sedYears[0], 1)) * (SW - SM.left - SM.right)
  );
  const sy = (v) => SM.top + (1 - v) * (SH - SM.top - SM.bottom);
  let sedHover = $state(null);

  // Adult attainment vs school outcomes, per elementary attendance area.
  let attain = $state([]);
  onMount(async () => {
    try {
      const [b, schools] = await Promise.all([getBoundaries('e'), getSchools()]);
      const byCds = new Map(schools.map((s) => [s.cds, s]));
      const seen = new Set();
      const out = [];
      for (const f of b.features) {
        const p = f.properties;
        if (p.ba == null || !p.cds || seen.has(p.cds)) continue;
        seen.add(p.cds);
        const s = byCds.get(p.cds);
        if (!s || s.pass_ela == null || s.pass_math == null) continue;
        out.push({
          cds: p.cds,
          name: s.name,
          ba: p.ba,
          met: (s.pass_ela + s.pass_math) / 2,
          adj: s.adj_pct
        });
      }
      attain = out;
    } catch {
      /* section degrades to nothing */
    }
  });
  let rAttain = $derived(corr(attain.map((r) => r.ba), attain.map((r) => r.met)));
  let rAttainAdj = $derived.by(() => {
    const rows = attain.filter((r) => r.adj != null);
    return corr(rows.map((r) => r.ba), rows.map((r) => r.adj));
  });
  const AW = 760;
  const AH = 480;
  const AM = { top: 14, right: 16, bottom: 46, left: 56 };
  const ax = (v) => AM.left + (v / 0.9) * (AW - AM.left - AM.right);
  const ay = (v) => AM.top + (1 - v / 100) * (AH - AM.top - AM.bottom);

  const RACE_LABELS = {
    his: 'Hispanic or Latino',
    wht: 'White',
    blk: 'Black',
    asn: 'Asian',
    oth: 'Other / two or more'
  };

  let raceRows = $derived.by(() => {
    const enrolled = demo?.enrolled?.race;
    const resident = demo?.resident?.race;
    if (!enrolled) return [];
    return Object.keys(RACE_LABELS).map((k) => ({
      label: RACE_LABELS[k],
      a: resident?.[k] ?? null,
      b: enrolled[k] ?? null
    }));
  });

  let censusPending = $derived(demo == null || demo.census_pending);
  const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`);
</script>

<svelte:head>
  <title>LAUSD demographics — SchoolFactors</title>
  <meta
    name="description"
    content="Who lives inside LAUSD's boundary vs who enrolls in its schools: resident population against enrolled students, by race/ethnicity and poverty."
  />
</svelte:head>

<h2>Residents vs enrolled students</h2>
<p>
  About 4.6 million people live inside LAUSD's boundary, but the district enrolls
  {demo?.enrolled?.total ? demo.enrolled.total.toLocaleString() : '—'} students —
  and the two populations look different. Families with school-age children differ
  from the neighborhood average, private and charter schools enroll selectively from
  it, and enrollment follows residence only where families don't opt out. The gaps
  below are descriptive: they say who ends up in district schools, not why.
</p>

{#if raceRows.length}
  <DemoBars
    rows={raceRows}
    aLabel={censusPending ? 'Residents (census — pending)' : 'Residents (census)'}
    bLabel="Enrolled students ({demo.enrolled.year})"
  />
{/if}

{#if censusPending}
  <p class="pending">
    The resident side of this comparison (census block-group population inside
    LAUSD's boundary, apportioned to attendance areas) fills in automatically once
    the census acquisition runs. Enrolled-student shares are from CDE enrollment
    data and already shown above.
  </p>
{:else}
  <h2>Poverty: two measures of the same neighborhoods</h2>
  <p>
    {pct(demo?.district?.p185)} of resident <em>children 6–17</em> inside LAUSD live
    under 185% of the federal poverty line (census; among residents of all ages it's
    {pct(demo?.resident?.p185)} — children are poorer than the population overall).
    The district reports {pct(demo?.district?.frpm)} of its enrolled students as
    FRPM-eligible under the same threshold —
    {demo?.district?.ratio ? `${demo.district.ratio.toFixed(1)}× the census children's rate` : 'a substantially higher rate'}.
    The difference is how the two measures work, not an error; see
    <a href="/lausd/funding">Funding</a> for the statewide picture.
  </p>
{/if}

{#if residentHist.length > 1 && enrolledHist.length > 1}
  <h2>How the composition changed</h2>
  <p>
    Both populations are shifting, but not together. Since {enrolledHist[0][0]},
    enrolled Black students went {rc(raceChg(enrolledHist, 'blk'))}, white students
    {rc(raceChg(enrolledHist, 'wht'))}, Hispanic students
    {rc(raceChg(enrolledHist, 'his'))}, and Asian students
    {rc(raceChg(enrolledHist, 'asn'))} — while the boundary's residents (all ages,
    ACS {residentHist[0][0]}→{residentHist[residentHist.length - 1][0]}) changed far
    more slowly. Counts, not shares, so the district's overall shrinkage is visible
    in the right panel's height.
  </p>
  <div class="duo">
    <StackedArea
      data={residentHist}
      series={RACE_SERIES}
      title="Residents inside LAUSD, all ages (ACS 5-yr vintages)"
    />
    <StackedArea
      data={enrolledHist}
      series={RACE_SERIES}
      title="Students enrolled in LAUSD-authorized schools (CDE)"
    />
  </div>
{/if}

{#if sed}
  <h2>Three measures of "socioeconomically disadvantaged," over time</h2>
  <p>
    "SED" means different things in different datasets, and they are diverging. The
    census measure of resident child poverty has been <b>falling steadily</b>
    ({Math.round((sed.p185[0]?.[1] ?? 0) * 100)}% →
    {Math.round((sed.p185[sed.p185.length - 1]?.[1] ?? 0) * 100)}%), while the
    district-reported measures that drive funding have stayed flat above 80% —
    FRPM counts direct-certified and categorically eligible students, and the
    CALPADS unduplicated count adds English learners and foster youth on top.
    Falling neighborhood poverty with flat district poverty is the same
    residents-vs-enrolled gap this page is about, applied to income.
  </p>
  <div class="chartwrap">
    <svg viewBox="0 0 {SW} {SH}" role="img" aria-label="SED measures over time"
      onmouseleave={() => (sedHover = null)}>
      {#each [0.25, 0.5, 0.75, 1] as t}
        <line x1={SM.left} y1={sy(t)} x2={SW - SM.right} y2={sy(t)} stroke="#e1e0d9" />
        <text x={SM.left - 6} y={sy(t) + 4} text-anchor="end" class="tick">{Math.round(t * 100)}%</text>
      {/each}
      {#each SED_SERIES as s}
        {@const pts = sed[s.key] ?? []}
        <polyline
          points={pts.map(([y, v]) => `${sx(y)},${sy(v)}`).join(' ')}
          fill="none"
          stroke={s.color}
          stroke-width="2"
          stroke-dasharray={s.dash}
        />
        {#each pts as [y, v]}
          <circle cx={sx(y)} cy={sy(v)} r="3" fill={s.color}
            onmouseenter={() => (sedHover = { s, y, v })} />
        {/each}
      {/each}
      {#each [2016, 2018, 2020, 2022, 2024, 2026] as y}
        {#if y >= sedYears[0] && y <= sedYears[1]}
          <text x={sx(y)} y={SH - 8} text-anchor="middle" class="tick">{String(y).slice(2)}</text>
        {/if}
      {/each}
    </svg>
    <p class="caption">
      {#if sedHover}
        <b>{sedHover.y}</b> — {sedHover.s.label}: {Math.round(sedHover.v * 100)}%
      {:else}
        {#each SED_SERIES as s}
          <span class="k"><span class="sw" style="background:{s.color}"></span>{s.label}</span>
        {/each}
      {/if}
    </p>
  </div>
{/if}

{#if attain.length > 30}
  <h2>Adult attainment and school outcomes, area by area</h2>
  <p>
    Each dot is one of {attain.length} zoned LAUSD elementaries, placed by the share
    of adults (25+) in its own attendance area holding a bachelor's degree or higher
    (<b>horizontal</b>, census) and the school's current Met+ rate
    (<b>vertical</b>). The correlation is {rAttain == null ? '…' : fmt2(rAttain)} —
    raw school outcomes track neighborhood adult attainment tightly. Against the
    <em>demographically adjusted</em> percentile it drops to
    {rAttainAdj == null ? '…' : fmt2(rAttainAdj)}: most of what attainment
    "predicts" is who lives there, which is exactly what the adjustment removes.
  </p>
  <div class="chartwrap">
    <svg viewBox="0 0 {AW} {AH}" role="img" aria-label="School Met+ rate vs attendance-area adult educational attainment">
      {#each [0, 0.25, 0.5, 0.75] as t}
        <line x1={ax(t)} y1={AM.top} x2={ax(t)} y2={AH - AM.bottom} stroke="#e1e0d9" />
        <text x={ax(t)} y={AH - AM.bottom + 18} text-anchor="middle" class="tick">{Math.round(t * 100)}%</text>
      {/each}
      {#each [25, 50, 75] as t}
        <line x1={AM.left} y1={ay(t)} x2={AW - AM.right} y2={ay(t)} stroke="#e1e0d9" />
        <text x={AM.left - 8} y={ay(t) + 4} text-anchor="end" class="tick">{t}%</text>
      {/each}
      {#each attain as s (s.cds)}
        <a href="/school/{s.cds}">
          <circle
            cx={ax(clamp(s.ba, 0, 0.9))}
            cy={ay(clamp(s.met, 0, 100))}
            r="3.2"
            fill="#2a78d6"
            fill-opacity="0.45"
          >
            <title>{s.name} — BA+ {Math.round(s.ba * 100)}% of area adults; Met+ {Math.round(s.met)}%</title>
          </circle>
        </a>
      {/each}
      <text x={(AM.left + AW - AM.right) / 2} y={AH - 8} text-anchor="middle" class="axis">
        Attendance-area adults with bachelor's degree or higher →
      </text>
      <text x={16} y={(AM.top + AH - AM.bottom) / 2} text-anchor="middle" class="axis"
        transform="rotate(-90 16 {(AM.top + AH - AM.bottom) / 2})">
        School Met+ rate (raw)
      </text>
    </svg>
  </div>
  <p class="note">
    Every dot links to its school page; the same attainment layer is mapped on the
    <a href="/lausd/map">attendance-area panels</a>. Correlation between area
    averages, not causation — and attainment is measured over all resident adults,
    not just parents of enrolled students.
  </p>
{/if}

<p>
  For the neighborhood-by-neighborhood view — resident poverty, race/ethnicity, and
  adult attainment shaded over each attendance area — see the
  <a href="/lausd/map">map page's</a> side-by-side panels.
</p>

<style>
  .pending {
    color: #6f6a61;
    font-size: 0.88rem;
    background: #fff;
    border: 1px dashed #d7cfc0;
    border-radius: 8px;
    padding: 0.6rem 0.9rem;
  }
  .duo {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1rem;
  }
  @media (max-width: 900px) {
    .duo {
      grid-template-columns: 1fr;
    }
  }
  .chartwrap {
    overflow-x: auto;
  }
  svg {
    width: 100%;
    max-width: 820px;
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
  .axis {
    font-size: 12.5px;
    fill: #52514e;
    font-weight: 550;
  }
  .caption {
    font-size: 0.82rem;
    color: #52514e;
    min-height: 1.4em;
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
  .note {
    color: #6f6a61;
    font-size: 0.88rem;
  }
  a circle {
    cursor: pointer;
  }
  a:hover circle {
    fill-opacity: 1;
  }
</style>
