<script>
  import FlowMap from '$lib/enrollment/FlowMap.svelte';
  import FlowLegend from '$lib/enrollment/FlowLegend.svelte';
  import MethodNote from '$lib/enrollment/MethodNote.svelte';
  import ResidentsSeatsChart from '$lib/enrollment/ResidentsSeatsChart.svelte';
  import NetImportChart from '$lib/enrollment/NetImportChart.svelte';
  import ChannelStack from '$lib/enrollment/ChannelStack.svelte';
  import NeighborList from '$lib/enrollment/NeighborList.svelte';
  import SchoolsTable from '$lib/enrollment/SchoolsTable.svelte';
  import EnrollFlow from '$lib/district/EnrollFlow.svelte';

  let { data } = $props();
  let d = $derived(data.detail);
  let meta = $derived(d.meta);

  const DTYPE_WORD = { u: 'Unified district', e: 'Elementary district', h: 'High school district' };
  // The map band a district's own polygon lives in.
  let band = $derived(meta.dtype === 'h' ? 'hs' : 'k8');

  let latest = $derived.by(() => {
    const live = d.series.filter((r) => r.net != null);
    return live.length ? live[live.length - 1] : null;
  });
  let mRate = $derived(new Map(d.m));

  // EnrollFlow reconciliation cells via the accounting identity (see methodology):
  // elsewhere = pool (virtual + county adjustment) + net export — residents
  // counted beyond these schools; importers instead get a left-side "Other
  // districts (net)" node flowing into the local schools.
  let flowCells = $derived.by(() => {
    if (!latest?.res?.pub) return null;
    const pool = Math.max((latest.virt ?? 0) + (latest.ooc ?? 0), 0);
    const elsewhere = pool + Math.max(-latest.net, 0);
    const toUnit = Math.max(latest.res.pub - elsewhere, 0);
    const m = mRate.get(latest.v) ?? 0.055;
    return {
      publicK: latest.res.pub,
      privateK: latest.res.priv ?? 0,
      notEnr: latest.res.noten ?? 0,
      mismatchIn: (toUnit * m) / (1 - m),
      toUnit,
      elsewhere,
      importsIn: Math.max(latest.net, 0)
    };
  });
  let flowScale = $derived(latest?.res?.total ? 230 / latest.res.total : 0.0005);

  let headline = $derived.by(() => {
    if (!latest) return null;
    const n = Math.abs(Math.round(latest.net));
    const pct = Math.abs(latest.rate * 100).toFixed(1);
    const moe = latest.res.pub_moe && latest.res.pub
      ? ((latest.res.pub_moe / latest.res.pub) * 100).toFixed(1)
      : null;
    return {
      dir: latest.net >= 0 ? 'importer' : 'exporter',
      n,
      pct,
      moe,
      window: `${latest.v - 4}–${latest.v}`
    };
  });
</script>

<svelte:head>
  <title>{meta.name} — enrollment flows | SchoolFactors</title>
  <meta
    name="description"
    content="Where {meta.name}'s students live vs. where they enroll: resident children, seats, and modeled net import/export, 2005–2024."
  />
</svelte:head>

<p class="crumb">
  <a href="/enrollment">← Statewide map</a>
  {#if meta.county_name}
    · <a href="/enrollment/county/{meta.county}000000000000">{meta.county_name}</a>
  {/if}
  · {meta.name}
  {#if meta.std_page}
    · <a href="/district/{meta.cds}">standard district page →</a>
  {/if}
</p>
<h1>{meta.name}</h1>
<p class="subline">
  {DTYPE_WORD[meta.dtype]}
  {#if meta.dtype !== 'u' && meta.cut}
    · grades split at grade {meta.cut} with the overlapping
    {meta.dtype === 'e' ? 'high school' : 'elementary'} district(s)
  {/if}
</p>

{#if headline}
  {#if Math.abs(latest?.rate ?? 0) < 0.001}
    <p class="headline">
      In {headline.window}, schools located here were <b>roughly balanced</b> with
      resident public-school children within {meta.name}'s county — cross-county
      and virtual enrollment shows on the
      <a href="/enrollment/county/{meta.county}{'0'.repeat(12)}">county page</a>.
    </p>
  {:else}
    <p class="headline">
      In {headline.window}, schools located here seated a net
      <b class:imp={headline.dir === 'importer'} class:exp={headline.dir === 'exporter'}>
        {headline.dir === 'importer' ? '+' : '−'}{headline.n.toLocaleString()}
      </b>
      students relative to resident public-school children — a net
      <b>{headline.dir}</b> of {headline.pct}% of its resident base within its
      county {#if headline.moe}(est., margin ±{headline.moe}pp){/if}.
    </p>
  {/if}
{/if}

<div class="cols">
  <div class="mapcol">
    <FlowMap
      mode="detail"
      {band}
      focusGeoid={meta.geoid}
      neighbors={d.neighbors}
      schools={d.schools}
      showControls={false}
      height="76vh"
    />
    <FlowLegend metric="net_import" showClasses={true} />
    <p class="mapnote">
      Bold outline = this district. Neighboring areas keep their own net-rate
      color; everything else is muted.
    </p>
  </div>

  <div class="charts">
    <section>
      <h2>Residents vs. seats</h2>
      <ResidentsSeatsChart series={d.series} acs1={d.acs1} />
      <MethodNote extra="Seats are converted to resident-children units with the statewide calibration." />
    </section>

    <section>
      <h2>Net import / export per window</h2>
      <NetImportChart series={d.series} perf={d.perf} />
      <MethodNote
        extra="The green line is the district's Similar Student percentile (right axis) — how students with a fixed demographic profile tend to do here vs. elsewhere, as parents would have seen it each year. Shown for descriptive co-movement, never as cause or effect of the flows."
      />
    </section>

    <section>
      <h2>Where resident students are counted, by channel</h2>
      <ChannelStack series={d.series} m={d.m} />
      {#if d.bandsplit && (d.bandsplit.lo > 0 || d.bandsplit.up > 0)}
        <p class="bandnote">
          Grade-band diagnostic ({d.bandsplit.v - 4}–{d.bandsplit.v}): resident
          students counted beyond local schools and allocations — K-8
          ≈ {Math.max(d.bandsplit.lo, 0).toLocaleString()}
          ({(d.bandsplit.lo_pct * 100).toFixed(1)}% of K-8 residents), grades 9–12
          ≈ {Math.max(d.bandsplit.up, 0).toLocaleString()}
          ({(d.bandsplit.up_pct * 100).toFixed(1)}% of high-school-age residents).
          A concentration in high-school ages is consistent with the
          non-classroom recovery sector, which skews 9–12; the split uses
          band-specific calibration and precedes the county adjustment.
        </p>
      {/if}
      {#if latest?.seats?.virt}
        <p class="virtbased">
          Separately, virtual &amp; non-classroom programs authorized here enroll
          ~{latest.seats.virt.toLocaleString()} students (window mean, observed) —
          drawn from this county and its neighbors (their legal footprint), so
          they are excluded from the local accounting above.
        </p>
      {/if}
      <MethodNote
        extra="Seats in the district's own schools and local charters are observed; the virtual/non-classroom & out-of-county band is a balanced estimate — the county's remote attribution (programs' observed enrollment spread over legal footprints, capped by each county's measured gap) passed down in proportion to each district's own measured band gap, so districts with no unexplained outflow receive none. It is an estimate, not a residence record: the 'elsewhere in county' residual still mixes in-person enrollment in other in-county districts with any remote use beyond the attributed share (the neighbor list below shows where the surrounding surpluses are)."
      />
    </section>

    {#if flowCells}
      <section>
        <h2>The latest window, reconciled</h2>
        <EnrollFlow
          title="Resident children 5–17 ({headline?.window}) vs where enrollment is counted"
          unitLabel="Schools located here"
          f={flowCells}
          scale={flowScale}
        />
        <MethodNote extra="The violet band is an accounting residual: resident public-school children not counted at schools located here (other districts, virtual, statewide programs)." />
      </section>
    {/if}

    {#if d.neighbors?.length}
      <section>
        <h2>Neighboring districts</h2>
        <NeighborList neighbors={d.neighbors} />
        <MethodNote extra="Shown instead of pairwise flows: no public data observes who exchanges students with whom." />
      </section>
    {/if}

  </div>
</div>

<section class="schools">
  <h2>Schools whose seats count toward this area</h2>
  <p class="note">
    The district's own schools and affiliated charters (administrative
    attendance), plus independent charters whose buildings stand inside the area
    (locational draw). Virtual charters are excluded from the physical accounting
    (import-only statewide pool) and shown with a virtual chip.
  </p>
  <SchoolsTable schools={d.schools} sparkSprings={d.school_spark_springs} />
</section>

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
    margin: 0 0 0.6rem;
    color: #6f6a61;
    font-size: 0.9rem;
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
  .charts section {
    margin-bottom: 1.6rem;
  }
  .charts h2,
  .schools h2 {
    font-size: 1.02rem;
    margin: 0 0 0.5rem;
  }
  .schools {
    margin-top: 1.8rem;
  }
  .schools .note {
    color: #52514e;
    font-size: 0.86rem;
    max-width: 62rem;
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
  .bandnote {
    font-size: 0.86rem;
    color: #2b2722;
    background: #f7f3ea;
    border-left: 3px solid #b0552f;
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
