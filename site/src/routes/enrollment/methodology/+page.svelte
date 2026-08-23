<script>
  import { onMount } from 'svelte';

  const sections = [
    { id: 'universe', label: 'Who counts as a resident child' },
    { id: 'seats', label: 'Seats and the calibration' },
    { id: 'siting', label: 'Modeling attendance school by school' },
    { id: 'gradebands', label: 'Elementary / high school overlap' },
    { id: 'virtual', label: 'Virtual enrollment' },
    { id: 'netimport', label: 'The net import number' },
    { id: 'uncertainty', label: 'Uncertainty' },
    { id: 'nets-only', label: 'Why nets, not pairwise flows' },
    { id: 'limits', label: 'What this cannot say' }
  ];
  let active = $state(sections[0].id);

  onMount(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) if (e.isIntersecting) active = e.target.id;
      },
      { rootMargin: '0px 0px -75% 0px' }
    );
    for (const s of sections) {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  });
</script>

<svelte:head><title>How enrollment flows are modeled — SchoolFactors</title></svelte:head>

<div class="layout">
  <nav class="toc" aria-label="Section navigation">
    {#each sections as s}
      <a href="#{s.id}" class:active={active === s.id}>{s.label}</a>
    {/each}
  </nav>

  <article>
    <h1>How enrollment flows are modeled</h1>
    <p class="lede">
      Full details, exact formulas, and the bias register live in the
      <a href="https://github.com/ssorkin/schoolfactors/blob/main/analysis/enrollment_flow_model.md"
        >open model writeup</a
      >; every number can be reproduced from public data with the repository's
      pipeline. This page is the plain-language version. One convention to hold
      onto: <strong>positive always means net importer</strong>, and every flow
      shown is a <strong>net accounting residual</strong> — California publishes
      no student-level origin/destination data, so nothing here counts observed
      transfers.
    </p>

    <h2 id="universe">1. Who counts as a resident child</h2>
    <p>
      The residence side comes from the Census Bureau's American Community Survey
      (table B14003): children 5–17 living inside each school district's
      boundary, split by whether they attend public school, private school, or no
      school. We use every 5-year release from 2005–09 through 2020–24 — sixteen
      overlapping windows — so even small districts get usable estimates.
      Overlapping windows share four-fifths of their sample:
      <strong>window-to-window wiggles are not annual signal</strong>. For ~119
      large districts, all counties, and the state, the Bureau also publishes
      annual estimates, which district pages overlay as dots.
    </p>
    <p>
      Survey years 2005–2009 were weighted to population controls that overstated
      some counties. We correct those years with the Census Bureau's own revised
      county estimates, proportionally to how many affected years each window
      contains. Corrected points carry a flag in the data files.
    </p>

    <h2 id="seats">2. Seats, and converting them to resident units</h2>
    <p>
      The seats side is California's census-day enrollment count for every public
      school, 2004–05 through 2025–26, averaged over the five school years that
      overlap each survey window. The two sources count slightly different
      universes — census-day enrollment includes TK 4-year-olds and 18+ seniors
      the survey's 5–17 universe excludes. Statewide, where district-to-district
      movement nets out to zero, the gap measures exactly that universe mismatch:
      a stable 3–6% with no trend. We measure it each window and scale seat
      counts by it, so residents and seats are in the same units.
    </p>

    <h2 id="siting">3. Attendance is modeled school by school</h2>
    <p>
      Districts are not homogeneous: a district's territory can host its own
      schools, other agencies' charter schools, and programs whose students live
      nowhere nearby. So the model works at the school level, and siting follows
      the evidence for who a school serves. <strong>District-run and affiliated
      charter schools belong to their own district's area</strong> — their
      attendance is administrative, and a campus built just across a census
      boundary line still serves its district. <strong>Independent charters are
      placed where their building stands</strong> — they have no attendance
      area, so location is the evidence for who they draw — as are schools run
      by county offices and other non-geographic agencies. Schools without
      usable coordinates fall back to their district's area; the tiny remainder
      (0.04% of enrollment) joins the statewide pool (§5).
    </p>

    <h2 id="gradebands">4. Where elementary and high school districts overlap</h2>
    <p>
      Part of California is organized as separate elementary and high-school
      districts covering the same ground, so a child there lives in two districts
      at once. The model splits by grade at each high-school district's lowest
      grade (usually 9, sometimes 7): the elementary district gets the lower
      grades' seats and the matching ages of resident children, the high-school
      district the rest. The statewide map's two views — elementary grades and
      high-school grades — each tile the state exactly once, with unified
      districts appearing in both. A handful of areas are "pseudo districts"
      (elementary territory whose high schoolers attend a neighboring unified
      district); they are modeled like any other area.
    </p>

    <h2 id="virtual">5. Remote enrollment: virtual &amp; non-classroom, allocated
      over a legal county footprint</h2>
    <p>
      A remote program's census-day enrollment is counted wherever its
      authorizer sits, which says little about where its students live. Two
      classes of schools are therefore removed from the physical geography and
      pooled: schools the state directory flags as fully or primarily
      <strong>virtual</strong>, and <strong>non-classroom statewide-draw
      charters</strong> — identified arithmetically, as charters whose
      geographic authorizer's administered charter enrollment exceeds 1.5× the
      authorizer's own resident public-school children (the enrollment cannot
      be local: the local children don't exist; county offices of education,
      which have no resident base, are exempt from the test). The classified
      authorizers are listed in the data-quality report. Each pooled program's
      seats are attributed over its <em>legal enrollment footprint</em> — the
      authorizer's county plus adjacent counties, per the Education Code limit
      on non-classroom-based enrollment — by a <strong>capacity-constrained
      balance</strong>: seeded by each county's share of matching-age resident
      children, then iteratively scaled so that no county supplies more remote
      students than its own <em>measured</em> resident-vs-local-seat gap,
      while every program's total stays fixed at its administrative enrollment
      record. Both margins of this balance are measured; the footprint is law;
      only the split within them is estimated (it is the maximum-entropy
      solution consistent with all three). Within a county, the attributed
      total passes down to districts in proportion to each district's own
      measured grade-band gap — a district with no unexplained outflow
      receives none. What a county's ceiling refuses stays in its "counted in
      other counties" residual. Both classification criteria under-reach:
      non-classroom programs run by large authorizers pass the ratio test and
      stay in that measured residual. This is documented, not patched.
    </p>

    <h2 id="netimport">6. The net import number</h2>
    <p>
      For each area and window:
      <em>net import = seats at physical schools located there (in resident
      units) − (resident public-school children − the remote estimate − the
      county adjustment)</em>. The remote estimate is the area's population
      share of its county's footprint allocation (section 5); the county
      adjustment redistributes each county's remaining administrative imbalance
      (enrollment counted in another county) across its areas by population
      share — sized exactly so that <strong>physical seats and physical
      resident-students net out within every county</strong>. Positive: schools there seat more students than the
      area's own children account for — a net importer. Negative: a net
      exporter. A district's number is thus pure within-county redistribution;
      cross-county and virtual administrative flows appear on county pages,
      where they are measured rather than assumed. (In a county with a single
      district, the within-county net is zero — that district's story is its
      county page.) One caveat inside a county: the allocation removes an
      <em>average</em> remote &amp; out-of-county share, so a district whose
      residents use virtual/non-classroom or other out-of-area options more
      than that average shows the excess as net export — the residual is not
      purely in-person transfers, and no public data separates the two. A
      geographic consistency check helps read it: where a district's export
      exceeds its neighbors' combined surpluses (e.g. Compton), the excess is
      most consistent with remote-program use above the allocated share. The per-county
      and statewide closure checks run on every build, alongside a regression
      test that the model reproduces the LAUSD story's published resident series
      exactly — and a validation against California's one piece of
      <em>observed</em> pair-level transfer data, the District of Choice program:
      69% of its transfer students move between adjacent districts (supporting
      the nearby-draw premise), and model nets agree in direction with observed
      program nets for nearly all participating districts.
    </p>

    <h2 id="uncertainty">7. Uncertainty</h2>
    <p>
      Residence estimates are survey data and carry 90% margins of error, which
      propagate into every net. Where a district's margin exceeds ±15 percentage
      points of its resident base, the map shows gray rather than color — a small
      district's ±20pp estimate is noise, and coloring it would invite reading
      it. Values inside their own margin are labeled "not distinguishable from
      zero". Estimated quantities say "est." wherever they appear.
    </p>

    <h2 id="nets-only">8. Why nets, not pairwise flows</h2>
    <p>
      We considered publishing "district A exchanges N students with district B"
      style estimates from a distance-based allocation, and rejected it: such an
      allocation adds no information beyond the nets (any pairwise number would
      be an artifact of the assumed cost function), its solutions are unstable
      between windows, and it would be the page's most quotable, least supported
      number. The remote-sector balance in section 5 is a different kind of
      object: both of its margins are measured (program enrollment records and
      county-level gaps), its support is a legal constraint rather than a cost
      function, and its output is a program-to-county attribution — never a
      district-to-district transfer. What district pages break down instead is the export by
      <em>channel</em> — classes of schools, which are observable: seats at
      district-run and charter schools located in the area are counted data; the
      virtual &amp; out-of-county share is the model's county-average estimate;
      and "elsewhere in county" stays a single net residual (in-person
      enrollment in other in-county districts plus above-average virtual use,
      inseparable in public data; by construction these residuals sum to zero
      within each county). For destinations, each
      district page shows its <em>neighbors' own residuals</em> — where the
      surrounding surpluses and deficits actually are — and lets the geography
      speak. Pairwise flows would require a model that estimates them with
      uncertainty, or student-level data that is not public.
    </p>

    <h2 id="limits">9. What this cannot say</h2>
    <ul>
      <li>
        <strong>No causes.</strong> A net export is correlated with inter-district
        enrollment, charter draw, private-school shifts, and family moves; the
        accounting cannot attribute it to any one mechanism, and nothing here
        supports "families are fleeing X" claims.
      </li>
      <li>
        <strong>No gross flows.</strong> Offsetting in- and out-flows are
        invisible; a zero net is not "no movement".
      </li>
      <li>
        <strong>No individual tracking.</strong> Everything is computed from
        published aggregates — survey tables and school-level enrollment counts.
      </li>
      <li>
        <strong>Boundary vintage.</strong> Maps and siting use current (2024)
        boundaries for all windows; districts that reorganized show data only
        for the windows where they existed.
      </li>
    </ul>
  </article>
</div>

<style>
  .layout {
    display: grid;
    grid-template-columns: 220px 1fr;
    gap: 2rem;
    align-items: start;
  }
  .toc {
    position: sticky;
    top: 1.2rem;
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    font-size: 0.85rem;
  }
  .toc a {
    color: #52514e;
    text-decoration: none;
    padding: 0.25rem 0.6rem;
    border-left: 2px solid transparent;
  }
  .toc a:hover {
    color: #b0552f;
  }
  .toc a.active {
    color: #b0552f;
    border-left-color: #b0552f;
    background: #faf6ee;
  }
  article {
    max-width: 46rem;
  }
  h1 {
    margin: 0.2rem 0 0.6rem;
  }
  .lede {
    color: #52514e;
  }
  h2 {
    font-size: 1.08rem;
    margin: 1.6rem 0 0.5rem;
    scroll-margin-top: 1rem;
  }
  p,
  li {
    line-height: 1.6;
    color: #2b2722;
  }
  li {
    margin: 0.4rem 0;
  }
  @media (max-width: 800px) {
    .layout {
      grid-template-columns: 1fr;
    }
    .toc {
      position: static;
      flex-direction: row;
      flex-wrap: wrap;
    }
  }
</style>
