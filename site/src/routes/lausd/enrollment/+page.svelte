<script>
  import { onMount } from 'svelte';
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

  let closures = $derived(
    [...(enrollment?.closures ?? [])].sort(
      (a, b) => b.year - a.year || (b.last_enr ?? 0) - (a.last_enr ?? 0)
    )
  );
  let nCharterClosed = $derived(closures.filter((c) => c.charter).length);
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
  LAUSD has lost roughly a quarter of its students since 2015 — falling birth rates,
  families leaving Los Angeles, and enrollment moving to charters all pull the same
  direction. The census line shows the area's resident children fell far less than
  enrollment did over the same years: most of the gap is families opting out of
  district schools, not disappearing from the neighborhoods. The decline is the
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
  {closures.length || '…'} LAUSD schools in the state directory closed since 2015 —
  {nCharterClosed} of them charters, whose closures reflect authorization and
  finances as much as enrollment. Closures cluster where enrollment fell hardest;
  schools with a page link to their full history. "Last enrollment" is the most
  recent census count on record before closure.
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
</style>
