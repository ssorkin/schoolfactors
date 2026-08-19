<script>
  import { onMount } from 'svelte';
  import StackedArea from '$lib/district/StackedArea.svelte';
  import { getSchools } from '$lib/district/lausdData.js';

  let { data } = $props();
  let d = $derived(data.district);
  let enrollment = $derived(data.enrollment);

  const ENR_YEARS = Array.from({ length: 12 }, (_, i) => 2015 + i);

  let schools = $state([]);
  onMount(async () => {
    try {
      schools = await getSchools();
    } catch {
      /* capacity section degrades */
    }
  });

  // District enrollment vs resident children 6-17, shared axis (both are
  // counts of children). Colors match DemoBars: enrolled orange, residents blue.
  const W = 680;
  const H = 240;
  const M = { top: 14, right: 16, bottom: 40, left: 60 };
  let pts = $derived(
    (d?.enr ?? []).map((v, i) => ({ year: ENR_YEARS[i], v })).filter((p) => p.v != null)
  );
  let rpts = $derived(
    (enrollment?.resident_children ?? []).map(([year, v]) => ({ year, v }))
  );
  let allVals = $derived([...pts, ...rpts].map((p) => p.v));
  let lo = $derived(Math.min(...allVals) * 0.94);
  let hi = $derived(Math.max(...allVals) * 1.03);
  const X = $derived((y) => M.left + ((y - 2015) / 11) * (W - M.left - M.right));
  const Y = $derived((v) => M.top + (1 - (v - lo) / (hi - lo)) * (H - M.top - M.bottom));
  let hover = $state(null);
  const fmtN = (v) => Math.round(v).toLocaleString();

  // Capacity utilization from per-school OPCAP vs enrollment (2016-2022).
  let capYears = $derived.by(() => {
    const agg = new Map();
    for (const s of schools) {
      for (const [year, opcap, enr] of s.capacity ?? []) {
        if (opcap == null || enr == null) continue;
        const a = agg.get(year) ?? { opcap: 0, enr: 0, n: 0, under50: 0 };
        a.opcap += opcap;
        a.enr += enr;
        a.n += 1;
        if (opcap > 0 && enr / opcap < 0.5) a.under50 += 1;
        agg.set(year, a);
      }
    }
    return [...agg.entries()].sort((a, b) => a[0] - b[0]);
  });
  let capLatest = $derived(capYears.length ? capYears[capYears.length - 1] : null);

  // "Where did the students go?" decompositions.
  const RES_SERIES = [
    { key: 'public', label: 'Public school', color: '#2a78d6' },
    { key: 'private', label: 'Private school', color: '#9db9dd' },
    { key: 'not_enrolled', label: 'Not enrolled', color: '#d8d4cc' }
  ];
  const CLS_SERIES = [
    { key: 'traditional', label: 'Traditional LAUSD', color: '#eb6834' },
    { key: 'affiliated', label: 'Affiliated charter', color: '#f0b28a' },
    { key: 'independent', label: 'Independent charter', color: '#1e6b3a' }
  ];
  let residence = $derived(enrollment?.residence ?? []);
  let byClass = $derived(enrollment?.by_class ?? []);
  function chg(rows, key) {
    const vals = rows.map(([, d]) => d[key]).filter((v) => v != null);
    if (vals.length < 2) return null;
    return Math.round((vals[vals.length - 1] / vals[0] - 1) * 100);
  }
  let deltas = $derived({
    children: chg(residence, 'total'),
    pub: chg(residence, 'public'),
    prv: chg(residence, 'private'),
    not: chg(residence, 'not_enrolled'),
    trad: chg(byClass, 'traditional'),
    aff: chg(byClass, 'affiliated'),
    ind: chg(byClass, 'independent')
  });
  const sgn = (v) => (v == null ? '—' : `${v > 0 ? '+' : ''}${v}%`);

  let closures = $derived(
    [...(enrollment?.closures ?? [])].sort(
      (a, b) => b.year - a.year || (b.last_enr ?? 0) - (a.last_enr ?? 0)
    )
  );
  let closureCounts = $derived.by(() => {
    const K12 = new Set([
      'Elementary',
      'Intermediate/Middle/Junior High',
      'High School',
      'Elementary-High Combination'
    ]);
    const out = { charter: 0, campus: 0, other: 0 };
    for (const c of closures) {
      if (c.charter) out.charter++;
      else if (K12.has(c.eil)) out.campus++;
      else out.other++;
    }
    return out;
  });
  const EIL_SHORT = {
    Elementary: 'Elementary',
    'Intermediate/Middle/Junior High': 'Middle',
    'High School': 'High',
    'Elementary-High Combination': 'K-12',
    'Preschool/Early Learning': 'Preschool',
    Adult: 'Adult'
  };
</script>

<svelte:head>
  <title>LAUSD enrollment — SchoolFactors</title>
  <meta
    name="description"
    content="LAUSD's decade of enrollment decline: the district-wide trend, school capacity utilization, and school closures."
  />
</svelte:head>

<h2>A shrinking district</h2>
<p>
  LAUSD has lost roughly a quarter of its students since 2015, while the census
  shows the area's resident children fell far less over the same years. The
  decomposition below breaks both sides apart — who lives here and where they
  enroll, and which kinds of LAUSD-authorized schools shrank. The decline is the
  backdrop for every other story here: funding per student, small schools, and
  closures.
</p>

{#if pts.length > 1}
  <div class="chartwrap">
    <svg
      viewBox="0 0 {W} {H}"
      role="img"
      aria-label="LAUSD enrollment by year"
      onmouseleave={() => (hover = null)}
    >
      {#each [lo, (lo + hi) / 2, hi] as t}
        <line x1={M.left} y1={Y(t)} x2={W - M.right} y2={Y(t)} stroke="#e1e0d9" />
        <text x={M.left - 6} y={Y(t) + 4} text-anchor="end" class="tick">{fmtN(t)}</text>
      {/each}
      <polyline
        points={pts.map((p) => `${X(p.year)},${Y(p.v)}`).join(' ')}
        fill="none"
        stroke="#eb6834"
        stroke-width="2"
      />
      {#if rpts.length > 1}
        <polyline
          points={rpts.map((p) => `${X(p.year)},${Y(p.v)}`).join(' ')}
          fill="none"
          stroke="#2a78d6"
          stroke-width="2"
          stroke-dasharray="5 4"
        />
      {/if}
      {#each pts as p}
        <circle
          cx={X(p.year)}
          cy={Y(p.v)}
          r={hover?.year === p.year && hover?.kind === 'enr' ? 5 : 3}
          fill="#eb6834"
          onmouseenter={() => (hover = { ...p, kind: 'enr' })}
        />
        <text x={X(p.year)} y={H - 8} text-anchor="middle" class="tick">
          {String(p.year).slice(2)}
        </text>
      {/each}
      {#each rpts as p}
        <circle
          cx={X(p.year)}
          cy={Y(p.v)}
          r={hover?.year === p.year && hover?.kind === 'res' ? 5 : 3}
          fill="#2a78d6"
          onmouseenter={() => (hover = { ...p, kind: 'res' })}
        />
      {/each}
    </svg>
    <p class="caption">
      {#if hover}
        {#if hover.kind === 'res'}
          <b>ACS {hover.year}</b> (5-yr window): {fmtN(hover.v)} resident children 6–17
        {:else}
          <b>{hover.year - 1}–{String(hover.year).slice(2)}</b>: {fmtN(hover.v)} students enrolled
        {/if}
      {:else}
        <span class="k"><span class="sw" style="background:#eb6834"></span>Students
          enrolled (census-day count)</span>
        <span class="k"><span class="sw" style="background:#2a78d6"></span>Resident
          children 6–17 (ACS 5-yr, labeled by window end)</span>
      {/if}
    </p>
  </div>
{/if}

<h2>Where did the students go?</h2>
<p>
  Two decompositions of the same decline. The left side is <b>residence-based</b>
  (census): every child aged 5–17 living inside LAUSD's boundary, by where they go
  to school. The right side is <b>school-based</b> (CDE): every student enrolled in
  a school under LAUSD's CDS code, by school class. The two universes don't
  reconcile exactly — the census assigns children to where they <em>live</em>, not
  where they attend, so inter-district enrollment and independent charters drawing
  from outside the boundary sit in the gap. That non-reconciliation is informative,
  not a bug.
</p>

{#if residence.length > 1 && byClass.length > 1}
  <div class="duo">
    <StackedArea
      data={residence}
      series={RES_SERIES}
      title="Resident children 5–17, by enrollment (ACS 5-yr, {residence[0][0]}–{residence[residence.length - 1][0]})"
    />
    <StackedArea
      data={byClass}
      series={CLS_SERIES}
      title="Enrollment in LAUSD-authorized schools (CDE, {byClass[0][0]}–{byClass[byClass.length - 1][0]})"
    />
  </div>
  <ul class="deltas">
    <li>Resident children 5–17: <b>{sgn(deltas.children)}</b></li>
    <li>… attending public school: <b>{sgn(deltas.pub)}</b></li>
    <li>… attending private school: <b>{sgn(deltas.prv)}</b></li>
    <li>… not enrolled anywhere: <b>{sgn(deltas.not)}</b></li>
    <li>Traditional LAUSD enrollment: <b>{sgn(deltas.trad)}</b></li>
    <li>Affiliated charter enrollment: <b>{sgn(deltas.aff)}</b></li>
    <li>Independent charter enrollment: <b>{sgn(deltas.ind)}</b></li>
  </ul>
  <p class="method">
    Reading it: the resident child population shrank modestly and private-school
    share held roughly flat, while traditional LAUSD schools shrank far faster than
    either — independent charters barely shrank at all. The two panels cover
    different windows (ACS vintages vs school years) and different universes, so
    ratios between them are <em>apparent</em>, not student-level origin/destination
    measures. "Not enrolled" includes homeschooling and census reporting error.
  </p>
{:else}
  <p class="pending">The decomposition appears once the census B14003 series is exported.</p>
{/if}

<h2>Capacity</h2>
{#if capLatest}
  <p>
    LAUSD's own facilities data pairs each campus's operational capacity with its
    enrollment. In {capLatest[0]}, the {capLatest[1].n.toLocaleString()} campuses
    with both numbers enrolled {fmtN(capLatest[1].enr)} students against
    {fmtN(capLatest[1].opcap)} seats —
    <b>{Math.round((capLatest[1].enr / capLatest[1].opcap) * 100)}% utilization</b>,
    with {capLatest[1].under50.toLocaleString()} campuses under half full.
    The district's public GIS layer carries operational capacity only through
    {capLatest[0]}; later years exist only in LAUSD's Fingertip Facts PDFs, so the
    table below ends where the machine-readable record does. Enrollment has kept
    falling since, so current utilization is likely lower than the last row shows.
  </p>
  <table>
    <thead><tr><th>Year</th><th>Seats</th><th>Enrolled</th><th>Utilization</th><th>Campuses &lt;50% full</th></tr></thead>
    <tbody>
      {#each capYears as [year, a]}
        <tr>
          <td>{year}</td>
          <td>{fmtN(a.opcap)}</td>
          <td>{fmtN(a.enr)}</td>
          <td>{Math.round((a.enr / a.opcap) * 100)}%</td>
          <td>{a.under50}</td>
        </tr>
      {/each}
    </tbody>
  </table>
{:else}
  <p class="pending">Capacity data loads with the school list…</p>
{/if}

<h2>Closures</h2>
<p>
  The state directory records {closures.length || '…'} LAUSD closures since 2015,
  but they're not one thing: <b>{closureCounts.campus} district-operated K–12
  campuses</b> actually ceased operation, {closureCounts.charter} were charters
  (whose closures reflect authorization and finances as much as enrollment), and
  {closureCounts.other} were adult, preschool, special-education, or
  program/administrative entries. Schools with a page link to their full history;
  "last enrollment" is the most recent census count on record before closure.
</p>
{#if closures.length}
  <div class="tablewrap">
    <table>
      <thead>
        <tr>
          <th>Closed</th><th>School</th><th>Level</th><th>Type</th>
          <th>Opened</th><th>Last enrollment</th>
        </tr>
      </thead>
      <tbody>
        {#each closures as c}
          <tr>
            <td>{c.year}</td>
            <td>
              {#if c.has_page}<a href="/school/{c.cds}">{c.name}</a>{:else}{c.name}{/if}
            </td>
            <td>{EIL_SHORT[c.eil] ?? c.eil ?? '—'}</td>
            <td>{c.charter ? 'Charter' : c.magnet ? 'Magnet' : 'District'}</td>
            <td>{c.opened ?? '—'}</td>
            <td>
              {c.last_enr != null
                ? `${c.last_enr.toLocaleString()} (${c.last_enr_year})`
                : '—'}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<p class="crosslink">
  Related: <a href="/insights/lausd-enrollment-choice">Which LAUSD elementaries
  shrank — and what predicted it</a> — enrollment change correlates with early raw
  scores, which largely track demographics.
</p>

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
  .k {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    margin-right: 0.9rem;
  }
  .sw {
    width: 11px;
    height: 11px;
    border-radius: 3px;
    display: inline-block;
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
  .pending {
    color: #6f6a61;
    font-size: 0.88rem;
  }
  .crosslink {
    margin-top: 1.5rem;
  }
  .tablewrap {
    overflow-x: auto;
    max-height: 32rem;
    overflow-y: auto;
    border: 1px solid #eee7da;
    border-radius: 8px;
    padding: 0 0.6rem;
  }
  .tablewrap thead th {
    position: sticky;
    top: 0;
    background: #faf7f2;
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
  .deltas {
    columns: 2;
    font-size: 0.9rem;
    margin: 0.8rem 0 0.3rem;
  }
  @media (max-width: 640px) {
    .deltas {
      columns: 1;
    }
  }
  .method {
    font-size: 0.85rem;
    color: #6f6a61;
  }
</style>
