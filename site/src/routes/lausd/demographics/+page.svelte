<script>
  import DemoBars from '$lib/district/DemoBars.svelte';

  let { data } = $props();
  let demo = $derived(data.demographics);

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

<p>
  For the neighborhood-by-neighborhood view — resident poverty and race/ethnicity
  shaded over each attendance area — see the
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
</style>
