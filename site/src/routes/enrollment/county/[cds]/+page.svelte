<script>
  import FlowMap from '$lib/enrollment/FlowMap.svelte';
  import FlowLegend from '$lib/enrollment/FlowLegend.svelte';
  import MethodNote from '$lib/enrollment/MethodNote.svelte';
  import ResidentsSeatsChart from '$lib/enrollment/ResidentsSeatsChart.svelte';
  import NetImportChart from '$lib/enrollment/NetImportChart.svelte';
  import ChannelStack from '$lib/enrollment/ChannelStack.svelte';
  import ModelBadge from '$lib/enrollment/ModelBadge.svelte';
  import { FLOW_METRICS } from '$lib/enrollment/metrics.js';
  import { COLTIP } from '$lib/glossary.js';

  let { data } = $props();
  let d = $derived(data.detail);
  let meta = $derived(d.meta);
  let band = $state('k8');
  let hoverGeoid = $state(null);
  let showPerf = $state(false);

  const DTYPE_WORD = { u: 'unified', e: 'elementary', h: 'high school' };
  const mNet = FLOW_METRICS.net_import;

  // Members are index-row arrays: [geoid, cds, name, dtype, net_rate, res].
  let memberGeoids = $derived((d.members ?? []).map((r) => r[0]));
  let latest = $derived.by(() => {
    const live = d.series.filter((r) => r.net != null);
    return live.length ? live[live.length - 1] : null;
  });
  let headline = $derived.by(() => {
    if (!latest) return null;
    return {
      dir: latest.net >= 0 ? 'importer' : 'exporter',
      n: Math.abs(Math.round(latest.net)),
      pct: Math.abs(latest.rate * 100).toFixed(1),
      window: `${latest.v - 4}–${latest.v}`
    };
  });
  // Conservation decomposition of the latest residual: matched adjacent-county
  // flow (real students, at most) vs the non-conserved remainder, which has no
  // counterparty anywhere in the legal footprint and cannot be students.
  let ledger = $derived.by(() => {
    if (!latest || latest.net >= 0 || latest.mis == null) return null;
    const mis = Math.max(-latest.mis, 0);
    if (mis < 500) return null;
    return {
      out: Math.round(-latest.net),
      flow: Math.round(Math.min(Math.max(-latest.flow, 0), -latest.net)),
      mis: Math.round(mis)
    };
  });
</script>

<svelte:head>
  <title>{meta.name} — enrollment flows | SchoolFactors</title>
  <meta
    name="description"
    content="Where {meta.name}'s students live vs. where they enroll: resident children, seats, and modeled net import/export by district, 2005–2024."
  />
</svelte:head>

<p class="crumb">
  <a href="/enrollment">← Statewide map</a> ·
  <a href="/county/{meta.cds}">standard county page →</a>
</p>
<h1>{meta.name}</h1>
<p class="subline">Where the county's public enrollment is administratively counted</p>
<ModelBadge />

{#if headline}
  <p class="headline">
    Net enrollment balance, {headline.window}:
    <b class:imp={headline.dir === 'importer'} class:exp={headline.dir === 'exporter'}>
      {headline.dir === 'importer' ? '+' : '−'}{headline.pct}%
    </b>
    ({headline.dir === 'importer' ? '+' : '−'}{headline.n.toLocaleString()} students,
    est.) — a modeled net <b>{headline.dir}</b> relative to resident
    public-school children, largely enrollment counted administratively in
    other counties or remote programs.
  </p>
{/if}

<div class="cols">
  <div class="mapcol">
    <div class="seg" role="group" aria-label="Grade band">
      <button class:on={band === 'k8'} onclick={() => (band = 'k8')}>Elementary grades</button>
      <button class:on={band === 'hs'} onclick={() => (band = 'hs')}>High school grades</button>
    </div>
    <FlowMap
      mode="detail"
      bind:band
      neighbors={memberGeoids}
      highlightGeoid={hoverGeoid}
      showControls={false}
      height="76vh"
    />
    <FlowLegend metric="net_import" />
    <p class="mapnote">
      The county's districts keep their own net-rate color; the rest of the state
      is muted. Toggle the band to see high-school districts.
    </p>
  </div>

  <div class="charts">
    <section>
      <h2>Residents vs. seats</h2>
      <ResidentsSeatsChart series={d.series} acs1={d.acs1} />
      <p class="mapnote">
        Seats are counted by administrative county, matching the county
        reconciliation in the LAUSD story.
      </p>
    </section>

    <section>
      <h2>Net balance per window</h2>
      <NetImportChart series={d.series} perf={showPerf ? d.perf : []} />
      <label class="perftoggle">
        <input type="checkbox" bind:checked={showPerf} />
        Show Similar Student %ile
      </label>
      {#if showPerf}
        <p class="mapnote">
          The green line is the county's Similar Student percentile (right axis)
          — descriptive co-movement, never cause or effect.
        </p>
      {/if}
    </section>

    <section>
      <h2>Where resident students are counted, by channel</h2>
      <ChannelStack series={d.series} m={d.m} county />
      {#if ledger}
        <p class="virtbased">
          Conservation test: of the −{ledger.out.toLocaleString()} residual,
          at most ~{ledger.flow.toLocaleString()} can be matched to unabsorbed
          surpluses in adjacent counties (real cross-border enrollment); the
          remaining ~{ledger.mis.toLocaleString()} has no counterparty anywhere
          in this county's <em>legal footprint</em> — it cannot be students,
          and reflects how the ACS and CDE universes align regionally
          (measurement, shown as its own band above).
        </p>
      {/if}
      {#if latest?.seats?.virt}
        <p class="virtbased">
          Separately, virtual &amp; non-classroom programs authorized in this county
          enroll ~{latest.seats.virt.toLocaleString()} students (window mean,
          observed) — drawn from their legal footprint (this county and its
          neighbors), so they are excluded from the physical accounting above.
        </p>
      {/if}
      <MethodNote
        extra="The virtual & non-classroom band is a balanced estimate: each remote program's observed enrollment is spread over its legal county footprint (Ed Code contiguous-county limit), iteratively scaled so no county supplies more remote students than its measured resident-vs-local-seat gap and every program's total stays at its administrative record. The 'counted in other counties' band is the remainder the balance could not attribute — non-classroom charters the classification misses (those under large authorizers) and genuine cross-border attendance."
      />
    </section>

    {#if d.remote?.length}
      <section>
        <h2>Virtual &amp; non-classroom programs authorized here</h2>
        <table class="members">
          <thead>
            <tr>
              <th>Program</th>
              <th>Basis</th>
              <th class="num">Students (observed)</th>
              <th class="num">From this county (balanced est.)</th>
              <th class="num" title={COLTIP.simstu_pct}>Similar Student %ile</th>
            </tr>
          </thead>
          <tbody>
            {#each d.remote as [name, seats, kind, est, cds, pct]}
              <tr>
                <td>
                  {#if cds}<a href="/school/{cds}">{name}</a>{:else}{name}{/if}
                </td>
                <td class="dtype"
                  >{kind === 'virtual'
                    ? 'CDE virtual flag'
                    : kind === 'ncb'
                      ? 'SBE non-classroom determination'
                      : 'enrollment ≫ authorizer residents'}</td
                >
                <td class="num">{seats?.toLocaleString() ?? '—'}</td>
                <td class="num">{est != null ? `~${est.toLocaleString()}` : '—'}</td>
                <td class="num">{pct ?? '—'}</td>
              </tr>
            {/each}
          </tbody>
        </table>
        <p class="mapnote">
          Observed census-day enrollment at named programs — these seats form the
          remote pool spread over each program's county footprint. Student
          residence within the footprint is not published; no per-district
          attribution is implied.
          <a href="/enrollment/programs">All remote programs statewide →</a>
        </p>
      </section>
    {/if}

    {#if d.remote_nearby?.length}
      <section>
        <h2>Nearby-authorized programs whose footprint includes this county</h2>
        <table class="members">
          <thead>
            <tr>
              <th>Program</th>
              <th>Authorized in</th>
              <th class="num">Students (observed)</th>
              <th class="num">From this county (balanced est.)</th>
              <th class="num" title={COLTIP.simstu_pct}>Similar Student %ile</th>
            </tr>
          </thead>
          <tbody>
            {#each d.remote_nearby as [name, seats, kind, cty, est, cds, pct]}
              <tr>
                <td>
                  {#if cds}<a href="/school/{cds}">{name}</a>{:else}{name}{/if}
                </td>
                <td class="dtype">{cty}</td>
                <td class="num">{seats?.toLocaleString() ?? '—'}</td>
                <td class="num">{est != null ? `~${est.toLocaleString()}` : '—'}</td>
                <td class="num">{pct ?? '—'}</td>
              </tr>
            {/each}
          </tbody>
        </table>
        <p class="mapnote">
          Programs authorized in adjacent counties may legally enroll this
          county's residents. The "from this county" estimate comes from the
          county-level balance: each program's observed enrollment is spread
          over its legal footprint, scaled so no county supplies more remote
          students than its measured resident-vs-local-seat gap. These
          estimates are already inside the virtual &amp; non-classroom band
          above; the "counted in other counties" band is what the balance
          could not attribute — non-classroom programs the classification
          misses and genuine cross-border attendance.
        </p>
      </section>
    {/if}

    <section>
      <h2>Districts in this county</h2>
      <table class="members">
        <thead>
          <tr>
            <th>District</th>
            <th>Type</th>
            <th class="num">Resident children</th>
            <th class="num">Net rate (est.)</th>
            <th class="num" title={COLTIP.simstu_pct}>Similar Student %ile</th>
          </tr>
        </thead>
        <tbody>
          {#each d.members ?? [] as [geoid, cds, name, dtype, rate, res, pct]}
            <tr
              onmouseenter={() => (hoverGeoid = geoid)}
              onmouseleave={() => (hoverGeoid = null)}
            >
              <td>
                {#if cds && rate != null}<a href="/enrollment/district/{cds}">{name}</a>{:else}{name}{/if}
              </td>
              <td class="dtype">{DTYPE_WORD[dtype]}</td>
              <td class="num">{res?.toLocaleString() ?? '—'}</td>
              <td class="num" class:impt={rate > 0} class:expt={rate < 0}>
                {mNet.fmt(rate)}
              </td>
              <td class="num">{pct ?? '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>
  </div>
</div>

<style>
  .crumb {
    margin: 0;
    font-size: 0.85rem;
  }
  .crumb a {
    color: #1c5cab;
    text-decoration: none;
  }
  h1 {
    margin: 0.3rem 0 0.1rem;
  }
  .subline {
    margin: 0 0 0.35rem;
    color: #6f6a61;
    font-size: 0.9rem;
  }
  .perftoggle {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.82rem;
    color: #52514e;
    margin-top: 0.3rem;
    cursor: pointer;
  }
  .mapnote a {
    color: #1c5cab;
    text-decoration: none;
  }
  .headline {
    max-width: 62rem;
    font-size: 1.02rem;
    color: #2b2722;
  }
  .headline .imp {
    color: #1c5cab;
  }
  .headline .exp {
    color: #9a3412;
  }
  .cols {
    display: grid;
    grid-template-columns: minmax(380px, 5fr) 7fr;
    gap: 1.4rem;
    align-items: start;
    margin-top: 0.8rem;
  }
  .mapcol {
    position: sticky;
    top: 1rem;
  }
  .mapnote {
    font-size: 0.78rem;
    color: #898781;
    margin: 0.3rem 0 0;
  }
  .seg {
    display: inline-flex;
    border: 1px solid #d7cfc0;
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 0.5rem;
  }
  .seg button {
    font: inherit;
    font-size: 0.85rem;
    font-weight: 550;
    border: none;
    background: #fff;
    color: #52514e;
    padding: 0.3rem 0.7rem;
    cursor: pointer;
  }
  .seg button + button {
    border-left: 1px solid #d7cfc0;
  }
  .seg button.on {
    background: #b0552f;
    color: #fff;
  }
  .charts section {
    margin-bottom: 1.6rem;
  }
  .charts h2 {
    font-size: 1.02rem;
    margin: 0 0 0.5rem;
  }
  .members {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.86rem;
  }
  .members th {
    text-align: left;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: #898781;
    padding: 0.3rem 0.5rem;
    border-bottom: 1px solid #e8e1d5;
  }
  .members td {
    padding: 0.28rem 0.5rem;
    border-bottom: 1px solid #f1ece1;
  }
  .members tbody tr:hover td {
    background: #f3ede2;
  }
  .members .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  .members a {
    color: #1c5cab;
    text-decoration: none;
  }
  .members a:hover {
    text-decoration: underline;
  }
  .members .dtype {
    color: #898781;
  }
  .members .impt {
    color: #1c5cab;
  }
  .members .expt {
    color: #9a3412;
  }
  .virtbased {
    font-size: 0.86rem;
    color: #2b2722;
    background: #f4f1fb;
    border-left: 3px solid #4a3aa7;
    padding: 0.4rem 0.7rem;
    border-radius: 0 6px 6px 0;
    margin: 0.5rem 0 0;
  }
  @media (max-width: 900px) {
    .cols {
      grid-template-columns: 1fr;
    }
    .mapcol {
      position: static;
    }
  }
</style>
