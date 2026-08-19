<script>
  import { onMount } from 'svelte';
  import DistrictMap from '$lib/district/DistrictMap.svelte';
  import { getSchools } from '$lib/district/lausdData.js';

  let { data } = $props();
  let d = $derived(data.district);
  let census = $derived(data.overview?.census ?? null);
  let childChange = $derived(
    census?.children && census?.children_prev
      ? census.children / census.children_prev - 1
      : null
  );

  let schools = $state([]);
  let loadError = $state(false);
  onMount(async () => {
    try {
      schools = await getSchools();
    } catch {
      loadError = true;
    }
  });

  let enrChange = $derived.by(() => {
    const enr = d?.enr ?? [];
    const first = enr.find((v) => v != null);
    const last = [...enr].reverse().find((v) => v != null);
    return first && last ? last / first - 1 : null;
  });
  let nBounded = $derived(schools.filter((s) => s.has_boundary).length);

  const fmtN = (v) => (v == null ? '—' : Math.round(v).toLocaleString());
  const fmtPct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`);
  let frpmLatest = $derived.by(() => {
    const hist = d?.frpm_hist ?? {};
    const years = Object.keys(hist).sort();
    return years.length ? hist[years[years.length - 1]] : null;
  });
</script>

<svelte:head>
  <title>LAUSD Explorer — SchoolFactors</title>
  <meta
    name="description"
    content="Los Angeles Unified, mapped: every school, attendance areas, performance, funding, enrollment, and the neighborhoods schools serve."
  />
</svelte:head>

<p class="lede">
  Los Angeles Unified is the second-largest school district in the country:
  {fmtN(d?.enrollment)} students across roughly a thousand schools, serving an area
  of about 4.6 million residents. This story maps the district — every school, every
  attendance area — and follows the numbers into funding, enrollment, and the gap
  between who lives here and who enrolls.
</p>

<div class="cards">
  <div class="card">
    <span class="big">{fmtN(d?.enrollment)}</span>
    <span class="lbl">students enrolled</span>
    {#if census?.children}
      <span class="sub">vs {fmtN(census.children)} resident children 6–17 (census)</span>
    {/if}
  </div>
  <div class="card">
    <span class="big">{enrChange == null ? '—' : `${Math.round(enrChange * 100)}%`}</span>
    <span class="lbl">enrollment since 2015</span>
    {#if childChange != null}
      <span class="sub">
        vs {childChange > 0 ? '+' : ''}{Math.round(childChange * 100)}% resident
        children (ACS {census.prev_vintage}→{census.vintage})
      </span>
    {/if}
  </div>
  <div class="card">
    <span class="big">{fmtPct(frpmLatest)}</span>
    <span class="lbl">students FRPM-eligible</span>
    {#if census?.p185 != null}
      <span class="sub">vs {fmtPct(census.p185)} resident children under 185% FPL</span>
    {/if}
  </div>
  <div class="card">
    <span class="big">{d?.ppe == null ? '—' : `$${fmtN(d.ppe)}`}</span>
    <span class="lbl">spending per student</span>
  </div>
</div>

<h2>The map</h2>
<p>
  Each colored area is an attendance zone — the neighborhood whose resident students
  a school serves by default. Areas are shaded by that school's performance
  percentile among <em>schools serving similar students</em>, so the shading reads
  as "compared to expectation," not raw scores. Dots are individual schools
  ({loadError ? 'failed to load' : nBounded ? `${fmtN(nBounded)} with attendance areas` : 'loading…'});
  schools without an attendance area — charters, magnets, options schools — appear
  as dots with no zone of their own.
</p>

<DistrictMap {schools} metrics={['perf']} />

<h2>Explore the story</h2>
<div class="teasers">
  <a href="/lausd/map">
    <b>Map &amp; boundaries</b>
    <span>
      All 985 attendance polygons, elementary through high school — and the ~300
      schools that have no attendance area at all.
    </span>
  </a>
  <a href="/lausd/funding">
    <b>Funding</b>
    <span>
      $18B+ in yearly spending: LCFF base, supplemental and concentration grants,
      per-student spending history, and how district poverty counts compare with
      the census.
    </span>
  </a>
  <a href="/lausd/enrollment">
    <b>Enrollment</b>
    <span>
      A district shrinking by design and demography: the decade-long decline,
      school capacity, and closures.
    </span>
  </a>
  <a href="/lausd/demographics">
    <b>Demographics</b>
    <span>
      Who lives in LAUSD vs who enrolls in it — resident population against
      enrolled students.
    </span>
  </a>
</div>

<style>
  .lede {
    font-size: 1.05rem;
    max-width: 62rem;
  }
  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 0.8rem;
    margin: 1rem 0 1.6rem;
  }
  .card {
    background: #fff;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    padding: 0.8rem 1rem;
    display: flex;
    flex-direction: column;
  }
  /* census counterpart, stacked under each district number */
  .sub {
    margin-top: 0.35rem;
    padding-top: 0.35rem;
    border-top: 1px dashed #e8e1d5;
    font-size: 0.8rem;
    color: #1c5cab;
  }
  .big {
    font-size: 1.6rem;
    font-weight: 700;
    color: #211d18;
    line-height: 1.2;
  }
  .lbl {
    font-size: 0.82rem;
    color: #6f6a61;
  }
  .teasers {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 0.8rem;
  }
  .teasers a {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    background: #fff;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    padding: 0.9rem 1rem;
    text-decoration: none;
    color: #2b2722;
  }
  .teasers a:hover {
    border-color: #b0552f;
  }
  .teasers b {
    color: #b0552f;
  }
  .teasers span {
    font-size: 0.88rem;
    color: #52514e;
  }
</style>
