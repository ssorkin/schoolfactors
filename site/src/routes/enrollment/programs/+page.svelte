<script>
  import { onMount } from 'svelte';
  import { getPrograms } from '$lib/enrollment/data.js';
  import { COLTIP } from '$lib/glossary.js';

  let data = $state(null);
  let kind = $state('all');
  let county = $state('all');
  let q = $state('');

  onMount(async () => {
    data = await getPrograms();
  });

  // Classification bases, ordered by epistemic strength (see intro).
  const KIND_LABEL = {
    ncb: 'SBE non-classroom determination',
    virtual: 'CDE virtual flag',
    nonclassroom: 'enrollment ≫ authorizer residents'
  };

  let rows = $derived.by(() => {
    if (!data) return [];
    const needle = q.trim().toLowerCase();
    return data.programs
      .map((r) => Object.fromEntries(data.cols.map((c, i) => [c, r[i]])))
      .filter(
        (r) =>
          (kind === 'all' || r.kind === kind) &&
          (county === 'all' || r.county === county) &&
          (!needle ||
            (r.name ?? '').toLowerCase().includes(needle) ||
            (r.auth_name ?? '').toLowerCase().includes(needle))
      );
  });
  let totalSeats = $derived(rows.reduce((s, r) => s + (r.seats ?? 0), 0));
  let counties = $derived.by(() => {
    if (!data) return [];
    const used = new Set(data.programs.map((r) => r[data.cols.indexOf('county')]));
    return [...used].sort().map((c) => [c, data.county_names[c] ?? c]);
  });

  function dests(r) {
    // The balanced county-of-residence split: the authorizer county's
    // footprint fractions applied to this program's observed enrollment.
    const fr = data?.xfrac?.[r.county] ?? [];
    return fr.map(([dst, f]) => [data.county_names[dst] ?? dst, Math.round(r.seats * f), f]);
  }

  // Inline enrollment-trend sparkline over the model's windows.
  function sparkPath(series) {
    const pts = series
      .map((v, i) => [i, v])
      .filter(([, v]) => v != null);
    if (pts.length < 2) return null;
    const max = Math.max(...pts.map(([, v]) => v));
    if (!max) return null;
    const n = series.length - 1;
    return pts
      .map(
        ([i, v], k) =>
          `${k ? 'L' : 'M'}${((i / n) * 76 + 2).toFixed(1)},${(20 - (v / max) * 16).toFixed(1)}`
      )
      .join('');
  }
</script>

<svelte:head>
  <title>Remote &amp; non-classroom programs | SchoolFactors</title>
  <meta
    name="description"
    content="Every classified virtual and non-classroom-based public-school program in California: authorizer, county, enrollment history, classification basis, and the district nonlocality table."
  />
</svelte:head>

<h1>Remote &amp; non-classroom programs</h1>
<p class="lede">
  The programs whose enrollment the flow model removes from physical geography:
  virtual charters and non-classroom-based (independent-study) programs, which
  legally enroll students across their authorizer's county and adjacent
  counties. Each program is classified by one of three routes, listed here from
  strongest to weakest evidence: a <b>State Board non-classroom-based funding
  determination</b> (an administrative funding record), the <b>CDE directory's
  virtual flag</b> (a documented lower bound — it misses some non-classroom
  programs), and an <b>arithmetic backstop</b> for charters whose enrollment
  is far beyond their authorizer's resident base. Enrollment is observed
  census-day data; only the county-of-residence split is a balanced estimate.
</p>

{#if data}
  <div class="filters">
    <label>
      Basis
      <select bind:value={kind}>
        <option value="all">all</option>
        {#each Object.entries(KIND_LABEL) as [k, lbl]}
          <option value={k}>{lbl}</option>
        {/each}
      </select>
    </label>
    <label>
      Authorized in
      <select bind:value={county}>
        <option value="all">all counties</option>
        {#each counties as [code, name]}
          <option value={code}>{name}</option>
        {/each}
      </select>
    </label>
    <input class="q" type="search" placeholder="Program or authorizer…" bind:value={q} />
    <span class="tally">
      {rows.length} programs · {totalSeats.toLocaleString()} students
      ({data.window[0]}–{data.window[1]} window mean)
    </span>
  </div>

  <table class="programs">
    <thead>
      <tr>
        <th>Program</th>
        <th>Authorizer</th>
        <th>County</th>
        <th>Basis</th>
        <th class="num">Students (observed)</th>
        <th>Trend</th>
        <th class="num" title="Counties in the program's legal footprint (authorizer county + adjacent)">Footprint</th>
        <th class="num" title={COLTIP.simstu_pct}>Similar Student %ile</th>
      </tr>
    </thead>
    <tbody>
      {#each rows as r (r.cds)}
        <tr>
          <td>
            <details>
              <summary>
                {#if r.link}<a href="/school/{r.link}">{r.name}</a>{:else}{r.name}{/if}
              </summary>
              <div class="dests">
                <p>
                  Balanced county-of-residence estimate (measured margins,
                  modeled split — not a residence record):
                </p>
                <ul>
                  {#each dests(r) as [name, est, f]}
                    <li>{name}: ~{est.toLocaleString()} ({Math.round(f * 100)}%)</li>
                  {/each}
                </ul>
              </div>
            </details>
          </td>
          <td class="dim">{r.auth_name ?? '—'}</td>
          <td class="dim">{data.county_names[r.county] ?? r.county}</td>
          <td class="dim">{KIND_LABEL[r.kind] ?? r.kind}</td>
          <td class="num">{r.seats?.toLocaleString() ?? '—'}</td>
          <td>
            {#if sparkPath(r.series)}
              <svg viewBox="0 0 80 22" class="spark"><path d={sparkPath(r.series)} /></svg>
            {/if}
          </td>
          <td class="num">{r.fp_n} counties</td>
          <td class="num">{r.perf ?? '—'}</td>
        </tr>
      {/each}
    </tbody>
  </table>

  <section class="nl">
    <h2>How nonlocal can a district's enrollment get?</h2>
    <p class="lede">
      For every district: administrative enrollment (its own schools plus every
      charter it authorizes, wherever students live) divided by its resident
      public-school children, window-matched ({data.nonlocal.window[0]}–{data.nonlocal.window[1]}).
      The median district administers <b>{data.nonlocal.median}×</b> its
      resident base — the tail below is what authorizing statewide-draw remote
      programs does to an LEA's books, and why the flow model separates
      administrative from physical enrollment. Observed enrollment over
      surveyed residents; no allocation involved.
    </p>
    <table class="programs">
      <thead>
        <tr>
          <th>District</th>
          <th>County</th>
          <th class="num">Resident children</th>
          <th class="num">Administrative enrollment</th>
          <th class="num">Ratio</th>
        </tr>
      </thead>
      <tbody>
        {#each data.nonlocal.rows as [cds, name, cty, res, admin, ratio, link] (cds)}
          <tr>
            <td>
              {#if link}<a href="/enrollment/district/{cds}">{name}</a>{:else}{name}{/if}
            </td>
            <td class="dim">{cty ?? '—'}</td>
            <td class="num">{res?.toLocaleString() ?? '—'}</td>
            <td class="num">{admin?.toLocaleString() ?? '—'}</td>
            <td class="num"><b>{ratio}×</b></td>
          </tr>
        {/each}
      </tbody>
    </table>
    <p class="mapnote">
      Districts with at least 200 resident children; top {data.nonlocal.rows.length}
      of {data.nonlocal.n} shown. Resident children are ACS survey estimates in
      resident units; administrative enrollment is census-day data converted with
      the statewide calibration.
    </p>
  </section>
{:else}
  <p class="loading">Loading program data…</p>
{/if}

<style>
  h1 {
    margin: 0.4rem 0 0.2rem;
  }
  .lede {
    max-width: 62rem;
    color: #52514e;
  }
  .filters {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.6rem 1.1rem;
    margin: 0.8rem 0 0.6rem;
    font-size: 0.88rem;
  }
  .filters select,
  .filters input {
    font: inherit;
    font-size: 0.85rem;
    margin-left: 0.3rem;
  }
  .q {
    padding: 0.25rem 0.5rem;
    border: 1px solid #d7cfc0;
    border-radius: 6px;
    min-width: 14rem;
  }
  .tally {
    color: #6f6a61;
    font-size: 0.82rem;
  }
  .programs {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.86rem;
  }
  .programs th {
    text-align: left;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: #898781;
    padding: 0.3rem 0.5rem;
    border-bottom: 1px solid #e8e1d5;
  }
  .programs td {
    padding: 0.28rem 0.5rem;
    border-bottom: 1px solid #f1ece1;
    vertical-align: top;
  }
  .programs tbody tr:hover td {
    background: #f3ede2;
  }
  .programs .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .programs a {
    color: #1c5cab;
    text-decoration: none;
  }
  .programs a:hover {
    text-decoration: underline;
  }
  .programs .dim {
    color: #6f6a61;
  }
  details summary {
    cursor: pointer;
    list-style: none;
  }
  details summary::before {
    content: '▸ ';
    color: #898781;
  }
  details[open] summary::before {
    content: '▾ ';
  }
  .dests {
    font-size: 0.8rem;
    color: #52514e;
    background: #f4f1fb;
    border-left: 3px solid #4a3aa7;
    border-radius: 0 6px 6px 0;
    padding: 0.3rem 0.6rem;
    margin: 0.3rem 0;
  }
  .dests p {
    margin: 0 0 0.2rem;
  }
  .dests ul {
    margin: 0;
    padding-left: 1.1rem;
  }
  .spark {
    width: 80px;
    height: 22px;
  }
  .spark path {
    fill: none;
    stroke: #4a3aa7;
    stroke-width: 1.5;
  }
  .nl {
    margin-top: 2rem;
    max-width: 62rem;
  }
  .nl h2 {
    font-size: 1.05rem;
    margin: 0 0 0.3rem;
  }
  .mapnote {
    font-size: 0.78rem;
    color: #898781;
    margin: 0.3rem 0 0;
  }
  .loading {
    color: #898781;
  }
</style>
