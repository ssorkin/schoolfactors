<script>
  import { dataUrl } from '$lib/data.js';
  import CohortChart from '$lib/CohortChart.svelte';
  import BlendChart from '$lib/BlendChart.svelte';
  import SearchBox from '$lib/SearchBox.svelte';
  import PerfList from '$lib/PerfList.svelte';
  import ResultsTables from '$lib/ResultsTables.svelte';
  import TrendChart from '$lib/TrendChart.svelte';
  import SpendChart from '$lib/SpendChart.svelte';
  import CsvButton from '$lib/CsvButton.svelte';
  import PeerHistogram from '$lib/PeerHistogram.svelte';
  import PeerScatter from '$lib/PeerScatter.svelte';
  import { pctColor } from '$lib/maptypes.js';

  let { entity, subItems = null, subKind = 'school', subLabel = '' } = $props();

  let e = $derived(entity.effects ?? {});

  // Per-year Similar Schools %ile chips. pct_hist holds [year, pct] pairs,
  // each refit only on results from BEFORE that year (the chip labeled 2024
  // knew nothing about 2024's scores); tested years without a rankable
  // history render as empty chips so the row still shows the span of data.
  let pctByYear = $derived(new Map(entity.pct_hist ?? []));
  let chipYears = $derived.by(() => {
    if (!entity.pct_hist?.length) return [];
    const ys = new Set((entity.cohort_scores ?? []).map((r) => r.year));
    for (const [y] of entity.pct_hist) ys.add(y);
    return [...ys].sort((a, b) => a - b);
  });

  // ---- Head metadata + plain-language summary ----
  const SITE = 'https://schoolfactors.org';
  const ENR_YEARS = Array.from({ length: 12 }, (_, i) => 2015 + i);
  const KINDS_PLURAL = { school: 'schools', district: 'districts', county: 'counties' };

  const ord = (n) => {
    const v = n % 100;
    const suf = v >= 11 && v <= 13 ? 'th' : (['th', 'st', 'nd', 'rd'][n % 10] ?? 'th');
    return n + suf;
  };

  // Careful, non-judgemental phrasing: comparisons are against similar
  // populations, never bare "better/worse school" claims.
  function similarPhrase(p, kindS, kindP) {
    const plural = `California ${kindP} serving similar student populations`;
    const single = `the typical California ${kindS} serving a similar student population`;
    if (p >= 90) return `higher than nearly all ${plural}`;
    if (p >= 70) return `higher than most ${plural}`;
    if (p >= 55) return `a bit higher than ${single}`;
    if (p >= 45) return `about the same as ${single}`;
    if (p >= 30) return `a bit lower than ${single}`;
    if (p >= 10) return `lower than most ${plural}`;
    return `lower than nearly all ${plural}`;
  }
  const fmtGrowth = (g, se, rel) => {
    const half = 1.96 * Math.sqrt(rel ?? 1) * (se ?? 0);
    return `${g > 0 ? '+' : ''}${g.toFixed(2)} ± ${half.toFixed(2)} SDs per grade`;
  };

  // Band-language illustration of the trajectory verdict: the most recent
  // well-observed cohort's Met+ share at its first and latest grade, with the
  // state's same-grade shares. The verdict itself is measured in mean-score
  // SDs (percentages jump when students cross a cut line); this is the
  // plain-language evidence in the CAASPP tiers families know.
  let cohortExample = $derived.by(() => {
    const rows = (entity.cohort_scores ?? []).filter((r) => r.pct_met != null && r.n);
    const by = new Map();
    for (const r of rows) {
      if (!by.has(r.grad_year)) by.set(r.grad_year, []);
      by.get(r.grad_year).push(r);
    }
    let best = null;
    for (const [gy, rs] of by) {
      const grades = [...new Set(rs.map((r) => r.grade))];
      if (grades.length < 3) continue;
      const lastYear = Math.max(...rs.map((r) => r.year));
      const score = lastYear * 10 + grades.length;
      if (!best || score > best.score) best = { gy, rs, score };
    }
    if (!best) return null;
    const grades = [...new Set(best.rs.map((r) => r.grade))].sort((a, b) => a - b);
    const agg = (grade) => {
      const g = best.rs.filter((r) => r.grade === grade);
      let n = 0;
      let met = 0;
      let sn = 0;
      let smet = 0;
      for (const r of g) {
        met += r.pct_met * r.n;
        n += r.n;
        if (r.state_pct_met != null) {
          smet += r.state_pct_met * r.n;
          sn += r.n;
        }
      }
      return n ? { met: met / n, smet: sn ? smet / sn : null, year: g[0].year } : null;
    };
    const a = agg(grades[0]);
    const b = agg(grades[grades.length - 1]);
    if (!a || !b) return null;
    return { gy: best.gy, g0: grades[0], g1: grades[grades.length - 1], a, b };
  });

  import { GROUP_LABELS } from '$lib/groups.js';
  // Group deltas below ±5pp are treated as noise, not listed.
  const GROUP_NOTEWORTHY_PP = 5;

  let summary = $derived.by(() => {
    const kindS = entity.kind === 'county' ? 'county' : entity.kind;
    const kindP = KINDS_PLURAL[entity.kind] ?? 'schools';
    const parts = [];
    if (entity.adj_pct != null) {
      parts.push(
        `Students here score ${similarPhrase(entity.adj_pct, kindS, kindP)} ` +
          `(${ord(entity.adj_pct)} percentile).`
      );
    }
    if (entity.growth_cat != null && e.move_eb != null) {
      const high = (entity.adj_pct ?? 0) >= 70;
      const val = fmtGrowth(e.move_eb, e.move_se, e.move_reliability);
      parts.push(
        entity.growth_cat === 'gaining'
          ? `As classes move through, they gain on the state (${val})` +
              (high ? ` — uncommon for a ${kindS} already scoring high.` : '.')
          : entity.growth_cat === 'slipping'
            ? `As classes move through, they lose ground vs the state (${val}) — ` +
              `worth a look at the cohort chart below.`
            : `As classes move through, they hold their standing vs the state` +
              (high ? ' — cohorts arrive high and stay high.' : '.')
      );
      const ce = cohortExample;
      if (ce) {
        const st = (v) => (v == null ? '' : ` (state ${Math.round(v)}%)`);
        parts.push(
          `Class of ${ce.gy}, for example: ${Math.round(ce.a.met)}% met standards in ` +
            `grade ${ce.g0}${st(ce.a.smet)} and ${Math.round(ce.b.met)}% in ` +
            `grade ${ce.g1}${st(ce.b.smet)}.`
        );
      }
      // The cohort view (per grade) and the yearly view (the scatter) are
      // nearly independent and can point in opposite directions; when they
      // do, reconcile them explicitly instead of reading as a contradiction.
      const tr = e.trend_eb;
      if (entity.trend_abs != null && tr != null) {
        if (entity.growth_cat === 'slipping' && tr >= 0.02) {
          parts.push(
            `Both views are true at once: each entering class scores higher than the ` +
              `one before it, so overall results rise year over year (see "How results ` +
              `are trending") — even as each class loses some ground against ` +
              `grade-level standards while moving up (the scatter's vertical axis).`
          );
        } else if (entity.growth_cat === 'gaining' && tr <= -0.02) {
          parts.push(
            `Both views are true at once: classes gain ground against grade-level ` +
              `standards as they move up (the scatter's vertical axis) — even though ` +
              `each entering class starts lower than the one before it, so overall ` +
              `results fall year over year (see "How results are trending").`
          );
        }
      }
    }
    if (entity.pass_ela != null || entity.pass_math != null) {
      const bits = [];
      if (entity.pass_ela != null) bits.push(`${entity.pass_ela}% of tests met the standard in English`);
      if (entity.pass_math != null)
        bits.push(entity.pass_ela != null ? `${entity.pass_math}% in math` : `${entity.pass_math}% of tests met the standard in math`);
      parts.push(`In ${entity.pass_year}, ${bits.join(' and ')}.`);
    }
    // Sentence-friendly group names: the shared labels are column-style
    // ("With disabilities"), and casing must respect proper nouns.
    const SENTENCE_GROUP = {
      31: 'economically disadvantaged students',
      160: 'English learners',
      128: 'students with disabilities',
      74: 'Black students',
      76: 'Asian students',
      78: 'Hispanic or Latino students',
      80: 'White students',
      111: 'students not economically disadvantaged',
      93: 'students whose parents finished college',
      94: 'students whose parents completed graduate school'
    };
    const gname = (g) => SENTENCE_GROUP[g] ?? GROUP_LABELS[g] ?? 'group ' + g;
    const fmtGroups = (list) => list.map((x) => `${gname(x.g)} (${x.d > 0 ? '+' : '−'}${Math.abs(Math.round(x.d))} pp)`).join(', ');
    const above = (entity.group_vs_state ?? [])
      .filter((x) => x.d >= GROUP_NOTEWORTHY_PP)
      .sort((a, b) => b.d - a.d);
    const below = (entity.group_vs_state ?? [])
      .filter((x) => x.d <= -GROUP_NOTEWORTHY_PP)
      .sort((a, b) => a.d - b.d);
    if (above.length) {
      parts.push(`Groups scoring above their statewide rates: ${fmtGroups(above)}.`);
    }
    if (below.length) {
      parts.push(`Groups scoring below their statewide rates: ${fmtGroups(below)}.`);
    }
    // The group comparison is unconditional (each group vs the same group
    // statewide); the similar-{kind}s comparison conditions on the full
    // demographic profile. In strongly advantaged or disadvantaged
    // communities the two often point in opposite directions — reconcile
    // explicitly rather than reading as a contradiction.
    if (entity.adj_pct != null) {
      let fired = false;
      if (entity.adj_pct <= 40 && above.length >= 3 && below.length === 0) {
        parts.push(
          `These two comparisons ask different questions: each group here outscores ` +
            `the same group statewide — common in more advantaged communities, where ` +
            `every group's own families tend to be more advantaged than that group ` +
            `statewide — while the similar-${kindP} comparison sets the bar at ` +
            `${kindP} serving equally advantaged populations, and scores here fall ` +
            `short of that bar.`
        );
        fired = true;
      } else if (entity.adj_pct >= 60 && below.length >= 3 && above.length === 0) {
        parts.push(
          `These two comparisons ask different questions: each group here trails the ` +
            `same group statewide — common in less advantaged communities — while ` +
            `against ${kindP} serving similar populations, scores here exceed the ` +
            `typical bar.`
        );
        fired = true;
      }
      // Make the similar-entities bar concrete: pooled rates from the band of
      // entities the model expects to score alike, including the Exceeded
      // level — a gap can live entirely in the top band. Shown whenever the
      // group-vs-statewide view diverges from the placement, and always at
      // extreme percentiles: a 98 (or a 3) should arrive with its evidence,
      // since statewide group deltas are confounded by within-group
      // composition (corr with econ share: -0.58) and can't substantiate it.
      const vs = entity.vs_similar;
      const extreme = entity.adj_pct >= 90 || entity.adj_pct <= 10;
      if ((fired || extreme) && vs?.rows?.length) {
        const bits = [];
        const g1r = vs.rows.find((r) => r.g === 1);
        if (g1r && g1r.exc != null && g1r.p_exc != null && Math.abs(g1r.exc - g1r.p_exc) >= 2) {
          bits.push(
            `${Math.round(g1r.exc)}% of tests exceed standards here vs ${Math.round(g1r.p_exc)}% there`
          );
        }
        // The example group must match the direction being explained: the
        // biggest shortfall when placement is low, the biggest surplus when
        // high — not merely the biggest absolute difference.
        const dir = entity.adj_pct <= 40 ? -1 : 1;
        const adv = vs.rows
          .filter(
            (r) =>
              [111, 93, 94, 31].includes(r.g) &&
              r.met != null &&
              r.p_met != null &&
              (r.met - r.p_met) * dir >= 2
          )
          .sort((a, b) => (b.met - b.p_met) * dir - (a.met - a.p_met) * dir)[0];
        if (adv) {
          bits.push(
            `${gname(adv.g)} meet standards at ${Math.round(adv.met)}% vs ${Math.round(adv.p_met)}%`
          );
        }
        if (bits.length) {
          parts.push(
            `Concretely, against the ${vs.n} ${kindP} expected to score alike: ` +
              `${bits.join(', and ')}.`
          );
        }
      }
    }
    const pts = (entity.enr ?? [])
      .map((v, i) => ({ v, y: ENR_YEARS[i] }))
      .filter((q) => q.v != null);
    if (pts.length >= 2) {
      const a = pts[0];
      const b = pts[pts.length - 1];
      const chg = b.v / a.v - 1;
      parts.push(
        Math.abs(chg) < 0.03
          ? `Enrollment has held roughly steady since ${a.y} (${b.v.toLocaleString()} students).`
          : `Enrollment has ${chg < 0 ? 'declined' : 'grown'} ` +
              `${Math.abs(Math.round(chg * 100))}% since ${a.y}, to ${b.v.toLocaleString()} students.`
      );
    }
    return parts;
  });

  // ---- Intake-change detection ----
  // Compare the tested population's group shares in the first two data years
  // vs the last two (count-weighted). Any major group shifting >= 10pp gets a
  // prominent warning: time comparisons partly reflect who enrolls.
  const BLEND_KEYS = ['econ_dis', 'el', 'swd', 'hispanic', 'white', 'black', 'asian'];
  let intakeShifts = $derived.by(() => {
    const rows = entity.blend ?? [];
    const years = [...new Set(rows.map((r) => r.year))].sort((a, b) => a - b);
    if (years.length < 4) return [];
    const early = new Set(years.slice(0, 2));
    const late = new Set(years.slice(-2));
    const agg = (set, key) => {
      let num = 0;
      let den = 0;
      for (const r of rows) {
        if (!set.has(r.year) || r['share_' + key] == null || !r.n) continue;
        num += r['share_' + key] * r.n;
        den += r.n;
      }
      return den >= 60 ? num / den : null;
    };
    const out = [];
    for (const k of BLEND_KEYS) {
      const a = agg(early, k);
      const b = agg(late, k);
      if (a == null || b == null || Math.abs(b - a) < 0.1) continue;
      out.push({ k, a, b, d: b - a });
    }
    out.sort((x, y) => Math.abs(y.d) - Math.abs(x.d));
    return out.slice(0, 3).map((s) => ({ ...s, y0: years[0], y1: years[years.length - 1] }));
  });

  // Cross-check a tested-population econ shift against the FRPM census over
  // the same span: the tested share (CDE's socioeconomically-disadvantaged
  // flag among test takers) can move with participation and classification,
  // not only enrollment. When school-wide FRPM barely moved, say so.
  let econIntake = $derived(intakeShifts.find((s) => s.k === 'econ_dis') ?? null);
  let frpmShift = $derived.by(() => {
    const fh = entity.frpm_hist;
    if (!fh || !econIntake) return null;
    const years = Object.keys(fh)
      .map(Number)
      .filter((y) => y >= econIntake.y0 && y <= econIntake.y1 + 1)
      .sort((a, b) => a - b);
    if (years.length < 2) return null;
    return { a: fh[years[0]], b: fh[years[years.length - 1]] };
  });

  let scatterMode = $derived(
    entity.peer_key && e.level_adj_eb != null
      ? entity.growth_abs != null
        ? 'growth'
        : entity.trend_abs != null
          ? 'trend'
          : null
      : null
  );

  // Schools highlighted on the peer scatter: the active comparison overlays
  // plus the "nearby schools" card list, deduped (an overlay that is also
  // nearby shows once, as a comparison mark).
  let scatterHighlights = $derived.by(() => {
    if (entity.kind !== 'school') return [];
    const out = [];
    const seen = new Set([entity.cds]);
    for (const o of overlays) {
      if (seen.has(o.cds)) continue;
      seen.add(o.cds);
      out.push({
        cds: o.cds,
        name: o.name,
        x: o.x,
        y: scatterMode === 'growth' ? o.gy : o.ty,
        kind: 'overlay'
      });
    }
    for (const s of (entity.neighbors?.nearby ?? []).slice(0, 5)) {
      if (seen.has(s.cds)) continue;
      seen.add(s.cds);
      out.push({ cds: s.cds, name: s.name, kind: 'nearby' });
    }
    return out;
  });

  let pageTitle = $derived(`${entity.name}: Scores, Growth & Spending | SchoolFactors`);
  let pageDesc = $derived(
    summary.length
      ? summary.join(' ')
      : `CAASPP scores, cohort growth, demographics-adjusted comparisons, enrollment, ` +
          `and spending for ${entity.name} (${entity.county} County, California).`
  );
  let pageUrl = $derived(`${SITE}/${entity.kind}/${entity.cds}`);
  let shared = $state(false);

  import { browser } from '$app/environment';
  import { replaceState } from '$app/navigation';

  // Comparison overlays: checked schools' trends, fetched on demand and drawn
  // in the chart above. Reset (and restored from the URL) per entity.
  const MAX_OVERLAYS = 4;
  let overlays = $state([]);
  // Overlay cds restored from the URL whose payloads are still in flight.
  // The URL-writing effect includes these, so a reload never strips ?c=
  // while the comparison schools load.
  let pendingOverlays = $state([]);
  let isOverlaid = $derived((cds) => overlays.some((o) => o.cds === cds));

  async function addOverlay(cds, name = null) {
    try {
      if (cds === entity.cds) return;
      if (overlays.some((o) => o.cds === cds) || overlays.length >= MAX_OVERLAYS) return;
      const resp = await fetch(dataUrl(`/data/schools/${cds}.json`));
      if (!resp.ok) return;
      const j = await resp.json();
      overlays = [
        ...overlays,
        {
          cds,
          name: name ?? j.name,
          rows: j.subgroup_results ?? [],
          scores: j.cohort_scores ?? [],
          // Position on the peer scatter, when the compared school has one.
          x: j.effects?.level_adj_eb ?? null,
          gy: j.growth_abs ?? null,
          ty: j.trend_abs ?? null
        }
      ];
    } catch {
      /* comparison school payload unavailable — leave unchecked */
    } finally {
      pendingOverlays = pendingOverlays.filter((c) => c !== cds);
    }
  }
  function toggleOverlay(s) {
    if (overlays.some((o) => o.cds === s.cds)) {
      overlays = overlays.filter((o) => o.cds !== s.cds);
    } else {
      addOverlay(s.cds, s.name);
    }
  }

  // ---- URL state: ?s=math&v=group&r=exc&l=facets&g=31.111&c=cds1.cds2 ----
  let chartState = $state(null);
  let chartInitial = $state({});
  let restoredFor = $state(null);

  $effect(() => {
    const cds = entity.cds;
    if (!browser || restoredFor === cds) return;
    restoredFor = cds;
    const q = new URLSearchParams(window.location.search);
    chartInitial = {
      subject: q.get('s') ?? undefined,
      split: q.get('v') ?? undefined,
      metric: q.get('r') === 'exc' ? 'pct_exc' : q.get('r') === 'met' ? 'pct_met' : undefined,
      layout: q.get('l') ?? undefined,
      groups: q.get('g')?.split('.').map(Number).filter(Number.isFinite) ?? []
    };
    overlays = [];
    const want = (q.get('c')?.split('.') ?? [])
      .slice(0, MAX_OVERLAYS)
      .filter((c) => /^\d{14}$/.test(c) && c !== cds);
    pendingOverlays = want;
    for (const c of want) addOverlay(c);
  });

  $effect(() => {
    if (!browser || !chartState || restoredFor !== entity.cds) return;
    const q = new URLSearchParams();
    if (chartState.subject !== 'ela') q.set('s', chartState.subject);
    if (chartState.split !== 'overall') q.set('v', chartState.split);
    if (chartState.metric !== 'pct_met') q.set('r', 'exc');
    if (chartState.layout) q.set('l', chartState.layout);
    if (chartState.split === 'group' && chartState.groups?.length) {
      q.set('g', chartState.groups.join('.'));
    }
    const ovCds = [...new Set([...overlays.map((o) => o.cds), ...pendingOverlays])];
    if (ovCds.length) q.set('c', ovCds.join('.'));
    const qs = q.toString();
    const target = window.location.pathname + (qs ? '?' + qs : '');
    if (target !== window.location.pathname + window.location.search) {
      replaceState(target, {});
    }
  });
  let flaggedSteps = $derived((entity.blend_steps ?? []).filter((s) => s.flag));
  let slopes = $derived(
    [...(entity.cohort_slopes ?? [])].sort((a, b) => b.grad_year - a.grad_year).slice(0, 8)
  );

  const fmt = (v, plus = true) =>
    v == null ? '—' : (plus && v > 0 ? '+' : '') + v.toFixed(2);

  function slopeVerdict(s) {
    if (s.slope - 2 * s.slope_se > 0) return { word: 'gaining on the state', cls: 'up' };
    if (s.slope + 2 * s.slope_se < 0) return { word: 'losing ground', cls: 'down' };
    return { word: 'moving with the state', cls: 'flat' };
  }

  // Lookalike card: the most similar schools scoring above and below this one,
  // so "schools serving similar students" answers "who does better, who worse".
  // The neighbor list arrives ordered by demographic similarity; take the
  // closest few in each direction, then display each block by adjusted level.
  let lookalikeSplit = $derived.by(() => {
    // Distance cap: sparse peer groups (magnets, alternative programs) can
    // stretch their 12 nearest matches far in demographic space — beyond 2
    // z-units a "lookalike" is a match of necessity, not similarity.
    const list = (entity.neighbors?.lookalike ?? []).filter((s) => (s.dist ?? 0) <= 2);
    const own = e.level_adj_eb;
    if (own == null) return { better: list.slice(0, 5), worse: [], own: null };
    const better = list
      .filter((s) => s.level_adj_eb != null && s.level_adj_eb > own)
      .slice(0, 4)
      .sort((a, b) => b.level_adj_eb - a.level_adj_eb);
    const worse = list
      .filter((s) => s.level_adj_eb != null && s.level_adj_eb <= own)
      .slice(0, 4)
      .sort((a, b) => b.level_adj_eb - a.level_adj_eb);
    return { better, worse, own };
  });

  const groupLabels = {
    econ_dis: 'economically disadvantaged',
    el: 'English learners',
    swd: 'students with disabilities',
    black: 'Black',
    asian: 'Asian',
    hispanic: 'Hispanic/Latino',
    white: 'White'
  };
</script>

<svelte:head>
  <title>{pageTitle}</title>
  <meta name="description" content={pageDesc} />
  <link rel="canonical" href={pageUrl} />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="SchoolFactors" />
  <meta property="og:title" content={pageTitle} />
  <meta property="og:description" content={pageDesc} />
  <meta property="og:url" content={pageUrl} />
  <meta property="og:image" content="{SITE}/og/{entity.cds}.png" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />
</svelte:head>

<SearchBox />

<nav class="crumbs">
  <a href="/">California</a> ›
  {#if entity.kind === 'county'}
    <span>{entity.name}</span>
  {:else}
    {#if entity.county_has_page}
      <a href="/county/{entity.county_cds}">{entity.county} County</a> ›
    {:else}
      <span>{entity.county} County</span> ›
    {/if}
    {#if entity.kind === 'school'}
      {#if entity.district_has_page}
        <a href="/district/{entity.district_cds}">{entity.district}</a> ›
      {:else}
        <span>{entity.district}</span> ›
      {/if}
    {/if}
    <span>{entity.name}</span>
  {/if}
</nav>

<h1>{entity.name}</h1>
<p class="sub">
  {entity.kind === 'school' ? `${entity.district} · ` : ''}{entity.county} County
  {#if !chipYears.length}
    {#if e.n_years}· {e.n_years} test years · {e.total_scores?.toLocaleString()} scores{/if}
    {#if e.last_year}· data through {e.last_year}{/if}
  {/if}
</p>
{#if chipYears.length}
  <div class="pct-years">
    <a
      class="py-label"
      href="/glossary#adj-percentile"
      title="Each year's percentile is refit using only test results from before that year — the chip shown for a year was knowable before that year's tests. Stable chips mean the ranking held up out of sample."
      >Similar Schools %ile entering each year</a
    >
    {#each chipYears as y (y)}
      {@const p = pctByYear.get(y)}
      <span
        class="py-chip"
        class:empty={p == null}
        style:border-bottom-color={p == null ? 'transparent' : pctColor(p)}
        title={p == null
          ? `${y}: tested, but not enough earlier data to rank`
          : `Entering ${y}: ${ord(p)} percentile among ${
              entity.kind === 'school' ? 'schools' : KINDS_PLURAL[entity.kind]
            } serving similar students, using only pre-${y} results`}
      >
        <span class="py-year">’{String(y).slice(2)}</span>
        <span class="py-val">{p ?? '·'}</span>
      </span>
    {/each}
    {#if entity.adj_pct != null}
      <span
        class="py-chip now"
        style:border-bottom-color={pctColor(entity.adj_pct)}
        title="Now: {ord(entity.adj_pct)} percentile, using all years of data"
      >
        <span class="py-year">now</span>
        <span class="py-val">{entity.adj_pct}</span>
      </span>
    {/if}
  </div>
{/if}
{#if entity.address}
  <p class="addr">{entity.address}</p>
{/if}

<p class="utils">
  <button
    class="util"
    onclick={async () => {
      const data = { title: pageTitle, url: pageUrl };
      if (navigator.share) {
        try {
          await navigator.share(data);
        } catch {
          /* user dismissed the share sheet */
        }
      } else {
        await navigator.clipboard.writeText(pageUrl);
        shared = true;
        setTimeout(() => (shared = false), 2000);
      }
    }}>{shared ? 'Link copied' : 'Share'}</button>
  ·
  <a
    class="util"
    href="mailto:contact@schoolfactors.org?subject={encodeURIComponent(
      `Data issue: ${entity.name} (${entity.cds})`
    )}&body={encodeURIComponent(
      `Page: ${pageUrl}\n\nWhat looks wrong (please include which number and what you expected):\n\n`
    )}">Report a data issue</a
  >
  ·
  <a
    class="util"
    href="https://github.com/ssorkin/schoolfactors/issues/new?title={encodeURIComponent(
      `Data issue: ${entity.name} (${entity.cds})`
    )}&body={encodeURIComponent(
      `Page: ${pageUrl}\n\nWhat looks wrong (please include which number and what you expected):\n\n`
    )}"
    target="_blank"
    rel="noopener">GitHub issue</a
  >
</p>

{#if summary.length || (entity.peer_hist && e.level_adj_eb != null)}
  <div class="topgrid">
    {#if summary.length}
      <ul class="summary">
        {#each summary as s (s)}
          <li>{s}</li>
        {/each}
        <li class="gl"><a href="/glossary">What these terms mean.</a></li>
      </ul>
    {/if}
    {#if scatterMode === 'growth'}
      <PeerScatter
        peerKey={entity.peer_key}
        yMode="growth"
        own={{ cds: entity.cds, x: e.level_adj_eb, y: entity.growth_abs, ll: entity.ll }}
        ownLabel="This {entity.kind}"
        label={entity.peer_hist?.label ?? 'similar schools'}
        kind={entity.kind}
        stateY={entity.state_growth}
        highlights={scatterHighlights}
        refs={[
          { label: 'District avg', x: entity.district_ref, y: entity.district_ref_growth_abs, shape: 'square' },
          { label: 'County avg', x: entity.county_ref, y: entity.county_ref_growth_abs, shape: 'triangle' }
        ]}
      />
    {:else if scatterMode === 'trend'}
      <PeerScatter
        peerKey={entity.peer_key}
        yMode="trend"
        own={{ cds: entity.cds, x: e.level_adj_eb, y: entity.trend_abs, ll: entity.ll }}
        ownLabel="This {entity.kind}"
        label={entity.peer_hist?.label ?? 'similar schools'}
        kind={entity.kind}
        stateY={entity.state_trend}
        highlights={scatterHighlights}
        refs={[
          { label: 'District avg', x: entity.district_ref, y: entity.district_ref_trend_abs, shape: 'square' },
          { label: 'County avg', x: entity.county_ref, y: entity.county_ref_trend_abs, shape: 'triangle' }
        ]}
      />
    {:else if entity.peer_hist && e.level_adj_eb != null}
      <PeerHistogram
        hist={entity.peer_hist}
        own={e.level_adj_eb}
        kindLabel="this {entity.kind}"
        refs={[
          { label: 'district', v: entity.district_ref },
          { label: 'county', v: entity.county_ref }
        ]}
      />
    {/if}
  </div>
{/if}

{#if intakeShifts.length}
  <div class="intake-warn" role="note">
    <strong>The tested population has shifted.</strong>
    Between {intakeShifts[0].y0} and {intakeShifts[0].y1}:
    {#each intakeShifts as s, i (s.k)}{i > 0 ? '; ' : ''}{groupLabels[s.k]}
      {Math.round(s.a * 100)}% → {Math.round(s.b * 100)}%{/each}.
    {#if econIntake && frpmShift}
      {#if Math.abs(frpmShift.b - frpmShift.a) < Math.abs(econIntake.d) / 2}
        {entity.kind === 'school' ? 'School' : entity.kind === 'district' ? 'District' : 'County'}-wide FRPM eligibility moved much less over the same span
        ({Math.round(frpmShift.a * 100)}% → {Math.round(frpmShift.b * 100)}%), so
        much of this shift reflects who takes the tests, not who enrolls.
      {:else}
        {entity.kind === 'school' ? 'School' : entity.kind === 'district' ? 'District' : 'County'}-wide FRPM eligibility moved similarly
        ({Math.round(frpmShift.a * 100)}% → {Math.round(frpmShift.b * 100)}%).
      {/if}
    {/if}
    Changes over time on this page — trend, cohort tracks, the Met+ lines — partly
    reflect <em>who enrolls and who is tested</em>, not only how this
    {entity.kind} serves its students.
  </div>
{/if}

<h2>How results are trending</h2>
{#key restoredFor === entity.cds ? entity.cds : 'pending'}
  <TrendChart
    subgroups={entity.subgroup_results ?? []}
    scores={entity.cohort_scores ?? []}
    {overlays}
    initial={chartInitial}
    onstate={(s) => (chartState = s)}
    name={entity.name}
  />
{/key}

{#if entity.neighbors && (entity.neighbors.nearby?.length || entity.neighbors.lookalike?.length)}
  <h2>Compare with</h2>
  <div class="compare">
    {#if entity.neighbors.nearby?.length}
      <div class="cmp-card">
        <h3>Nearby schools</h3>
        <ul>
          {#each entity.neighbors.nearby.slice(0, 5) as s (s.cds)}
            <li>
              <input
                type="checkbox"
                title="Overlay on the chart above"
                checked={isOverlaid(s.cds)}
                onchange={() => toggleOverlay(s)}
              />
              <span class="cmp-name">
                <a href="/school/{s.cds}">{s.name}</a>
                {#if s.district !== entity.district}<span class="cmp-sub">{s.district}</span>{/if}
              </span>
              <span class="cmp-vals">
                <span class="cmp-meta">{s.miles} mi</span>
                <span class="cmp-adj" class:pos={s.level_adj_eb > 0} class:neg={s.level_adj_eb < 0}>
                  {s.level_adj_eb == null ? '—' : fmt(s.level_adj_eb)}
                </span>
              </span>
            </li>
          {/each}
        </ul>
      </div>
    {/if}
    {#if entity.neighbors.lookalike?.length}
      {#snippet lookalikeRow(s)}
        <li>
          <input
            type="checkbox"
            title="Overlay on the chart above"
            checked={isOverlaid(s.cds)}
            onchange={() => toggleOverlay(s)}
          />
          <span class="cmp-name">
            <a href="/school/{s.cds}">{s.name}</a>
            <span class="cmp-sub">{s.district}</span>
          </span>
          <span class="cmp-vals">
            <span class="cmp-meta">
              {s.share_econ_dis == null ? '' : Math.round(s.share_econ_dis * 100) + '% econ dis.'}
            </span>
            <span class="cmp-adj" class:pos={s.level_adj_eb > 0} class:neg={s.level_adj_eb < 0}>
              {s.level_adj_eb == null ? '—' : fmt(s.level_adj_eb)}
            </span>
          </span>
        </li>
      {/snippet}
      <div class="cmp-card">
        <h3>Schools serving similar students</h3>
        <ul>
          {#each lookalikeSplit.better as s (s.cds)}
            {@render lookalikeRow(s)}
          {/each}
          {#if lookalikeSplit.own != null}
            <li class="self">
              <span class="cmp-name">
                {entity.name}
                <span class="cmp-sub">this {entity.kind}</span>
              </span>
              <span class="cmp-vals">
                <span
                  class="cmp-adj"
                  class:pos={lookalikeSplit.own > 0}
                  class:neg={lookalikeSplit.own < 0}>{fmt(lookalikeSplit.own)}</span
                >
              </span>
            </li>
          {/if}
          {#each lookalikeSplit.worse as s (s.cds)}
            {@render lookalikeRow(s)}
          {/each}
        </ul>
      </div>
    {/if}
  </div>
  <div class="add-compare">
    <SearchBox
      placeholder="Add any school to the comparison…"
      kinds={['school']}
      onselect={(it) => addOverlay(it.cds, it.name)}
    />
    {#if overlays.length}
      <div class="ov-chips">
        {#each overlays as o (o.cds)}
          <button
            class="ov-chip"
            title="Remove from comparison"
            onclick={() => (overlays = overlays.filter((x) => x.cds !== o.cds))}
          >
            {o.name} <span aria-hidden="true">×</span>
          </button>
        {/each}
        <a
          class="ov-table"
          href="/compare?s={[entity.cds, ...overlays.map((o) => o.cds)].join('.')}"
          >Open comparison table →</a
        >
      </div>
    {/if}
  </div>
  <p class="note">
    Check a school (or search for any school statewide) to overlay its trend on the
    chart above — up to four at a time. Lookalikes are matched statewide on the
    demographics of tested students (poverty, language, race/ethnicity, disabilities,
    parent education, size), restricted to the same school level and type — a
    traditional school is never compared with continuation or other alternative
    programs, whose student selection differs even when demographics match. The
    highlighted row is this school, with the most similar schools scoring above and
    below it. The number on the right is each school's demographically-adjusted level.
    The Similar Schools percentile is <em>not</em> computed from this list — it comes
    from the statewide adjustment model, ranking this school among thousands. A school
    with an unusual demographic profile for its type may have only a few close matches
    here while still ranking against the full statewide pool.
  </p>
{/if}

{#if e.level_eb != null}
  <h2>Performance, growth and trend</h2>
  <section class="tiles">
    <div class="tile">
      <div class="num">
        {fmt(e.level_adj_eb)}
        {#if e.level_adj_lcb != null}
          <span class="ci">≥ {fmt(e.level_adj_lcb)}</span>
        {/if}
      </div>
      <div class="label">
        adjusted level — recent scores vs {KINDS_PLURAL[entity.kind] ?? 'schools'}
        serving similar students, in student standard deviations (+1 SD ≈ the average
        student outscoring 84% of students statewide); rankings use the low end of
        the 95% band
      </div>
    </div>
    <div class="tile">
      <div class="num">{fmt(e.level_eb)} <span class="ci">± {(1.96 * (e.level_se ?? 0)).toFixed(2)}</span></div>
      <div class="label">raw level vs state average, weighted toward the latest years</div>
    </div>
    <div class="tile">
      {#if e.growth_eb != null}
        <div class="num">{fmt(e.growth_eb)} <span class="ci">± {(1.96 * (e.growth_se ?? 0)).toFixed(2)}</span></div>
        <div class="label">growth per grade — how cohorts progress vs the state</div>
      {:else}
        <div class="num">n/a</div>
        <div class="label">
          growth needs results in multiple grades; this {entity.kind} tests one grade
        </div>
      {/if}
    </div>
    <div class="tile">
      <div class="num">{fmt(e.trend_eb)} <span class="ci">± {(1.96 * (e.trend_se ?? 0)).toFixed(2)}</span></div>
      <div class="label">trend per year — are successive cohorts scoring higher?</div>
    </div>
  </section>
{/if}

<h2>Cohorts</h2>
<CohortChart scores={entity.cohort_scores ?? []} />

{#if slopes.length}
  <h3>Recent graduating classes</h3>
  <ul class="cohort-list">
    {#each slopes as s (s.grad_year)}
      {@const v = slopeVerdict(s)}
      <li class={v.cls}>
        <strong>Class of {s.grad_year}</strong> — {v.word}
        ({fmt(s.slope)} ± {(2 * s.slope_se).toFixed(2)} SD/grade over {s.n_points} points)
      </li>
    {/each}
  </ul>
{/if}

{#if flaggedSteps.length}
  <h3>Cohort composition changes worth knowing about</h3>
  <p class="note">
    Following a cohort across grades only approximates following the same students.
    These grade-to-grade steps had population shifts larger than sampling noise —
    score changes across them may reflect who moved in or out, not instruction.
  </p>
  <ul class="flags">
    {#each flaggedSteps as s (s.grad_year + '-' + s.from_grade)}
      <li>
        <strong>Class of {s.grad_year}</strong>, grade {s.from_grade} ({s.year}) →
        {s.from_grade + 1} ({s.year + 1}):
        {#if Math.abs(s.n_change_frac) > 0.2}
          tested group {s.n_change_frac > 0 ? 'grew' : 'shrank'}
          {Math.abs(Math.round(s.n_change_frac * 100))}%{Object.keys(s.shifts).length ? ';' : '.'}
        {/if}
        {#each Object.entries(s.shifts) as [k, d], i (k)}
          {i > 0 ? ', ' : ''}% {groupLabels[k]} shifted {d > 0 ? '+' : ''}{Math.round(d * 100)}pp
        {/each}
        {#if s.expected_dz_from_blend && Math.abs(s.expected_dz_from_blend) >= 0.02}
          <span class="exp">
            (mix change alone predicts ≈ {fmt(s.expected_dz_from_blend)} SD)
          </span>
        {/if}
      </li>
    {/each}
  </ul>
{/if}

<h2>Who takes the tests here</h2>
<BlendChart blend={entity.blend ?? []} />

{#if (entity.enr ?? []).some((v) => v != null) || (entity.ppe_hist ?? []).some((v) => v != null)}
  <h2>Enrollment and spending</h2>
  <SpendChart
    enr={entity.enr}
    enrYears={ENR_YEARS}
    ppe={entity.ppe_hist}
    ppeYears={entity.ppe_years ?? []}
  />
{/if}

{#if subItems?.length}
  <h2>{subLabel}</h2>
  <PerfList items={subItems} kind={subKind} childPath={'/' + subKind} />
  <details>
    <summary>All {subItems.length} {subKind}s</summary>
    <table>
      <thead>
        <tr>
          <th style="text-transform: capitalize">{subKind}</th>
          <th>Adj. level</th><th>Raw level</th><th>Adj. growth</th><th>Scores</th>
        </tr>
      </thead>
      <tbody>
        {#each subItems as s (s.cds)}
          <tr>
            <td><a href="/{subKind}/{s.cds}">{s.name}</a></td>
            <td class="tnum">{s.level_adj_eb == null ? '—' : fmt(s.level_adj_eb)}</td>
            <td class="tnum">{s.level_eb == null ? '—' : fmt(s.level_eb)}</td>
            <td class="tnum">{s.growth_adj_eb == null ? '—' : fmt(s.growth_adj_eb)}</td>
            <td class="tnum">{s.total_scores == null ? '—' : s.total_scores.toLocaleString()}</td>
          </tr>
        {/each}
      </tbody>
    </table>
    <p class="dl">
      <CsvButton
        filename="{entity.name} {subKind}s.csv"
        build={() => ({
          headers: ['Name', 'CDS', 'Adjusted level', 'Raw level', 'Adjusted growth', 'Scores'],
          rows: subItems.map((s) => [
            s.name, s.cds, s.level_adj_eb, s.level_eb, s.growth_adj_eb, s.total_scores
          ])
        })}
      />
    </p>
  </details>
{/if}

<h2>The underlying numbers</h2>
<ResultsTables
  scores={entity.cohort_scores ?? []}
  subgroups={entity.subgroup_results ?? []}
  name={entity.name}
/>

<p class="caveat">
  These are relationships between {entity.kind} averages on one set of tests — not
  measures of quality, and not causal. Intervals are 95% sampling bands and exclude
  model-specification uncertainty. <a href="/methodology">How these numbers are made.</a>
</p>

<style>
  .crumbs {
    font-size: 0.9rem;
    color: #898781;
    margin-bottom: 0.4rem;
  }
  h1 {
    margin: 0.2rem 0 0.2rem;
  }
  .sub {
    color: #6f6a61;
    margin-top: 0;
  }
  .addr {
    color: #898781;
    font-size: 0.85rem;
    margin: -0.4rem 0 0.6rem;
  }
  .pct-years {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.3rem 0.35rem;
    margin: -0.2rem 0 0.6rem;
    max-width: 66rem;
  }
  .py-label {
    font-size: 0.85rem;
    color: #898781;
    margin-right: 0.15rem;
    text-decoration: none;
    border-bottom: 1px dotted #b8b2a7;
  }
  .py-label:hover {
    color: #6f6a61;
  }
  .py-chip {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    min-width: 2.1rem;
    padding: 0.12rem 0.3rem 0.06rem;
    border: 1px solid #e8e1d5;
    border-bottom-width: 3px;
    border-radius: 6px;
    background: #fffdf9;
    line-height: 1.2;
  }
  .py-chip.empty {
    opacity: 0.55;
  }
  .py-chip.now {
    border-color: #b0552f;
    border-bottom-width: 3px;
  }
  .py-year {
    font-size: 0.68rem;
    color: #898781;
  }
  .py-val {
    font-size: 0.95rem;
    font-variant-numeric: tabular-nums;
    color: #3f3a33;
  }
  .topgrid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(340px, 460px);
    gap: 0.8rem;
    align-items: start;
    max-width: 66rem;
    margin: 0.4rem 0 0.6rem;
  }
  @media (max-width: 880px) {
    .topgrid {
      grid-template-columns: 1fr;
    }
  }
  .summary {
    font-size: 1.02rem;
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-left: 3px solid #b0552f;
    border-radius: 8px;
    margin: 0;
    padding: 0.7rem 1rem 0.7rem 2.1rem;
  }
  .summary li {
    margin: 0.2rem 0;
  }
  .summary li.gl {
    list-style: none;
    margin-top: 0.45rem;
  }
  .summary a {
    font-size: 0.88rem;
    color: #898781;
  }
  .intake-warn {
    background: #fdf1df;
    border: 1px solid #e7bf8a;
    border-left: 4px solid #d97b29;
    border-radius: 8px;
    padding: 0.65rem 1rem;
    max-width: 66rem;
    margin: 0 0 0.8rem;
    font-size: 0.96rem;
  }
  .intake-warn strong {
    color: #9c5410;
  }
  .utils {
    margin: -0.3rem 0 0.6rem;
    font-size: 0.85rem;
    color: #898781;
  }
  .utils .util {
    border: none;
    background: none;
    padding: 0;
    font: inherit;
    color: #1c5cab;
    cursor: pointer;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .utils .util:hover {
    color: #b0552f;
  }
  .dl {
    margin: 0.5rem 0 0;
  }
  :global(main) h2 {
    margin: 1.8rem 0 0.6rem;
  }
  .tiles {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 0.7rem;
    margin: 0.4rem 0 1rem;
  }
  .tile {
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    padding: 0.7rem 0.9rem;
  }
  .num {
    font-size: 1.35rem;
    font-weight: 700;
    color: #b0552f;
  }
  .ci {
    font-size: 0.95rem;
    font-weight: 500;
    color: #898781;
  }
  .label {
    color: #6f6a61;
    font-size: 0.87rem;
  }
  .cohort-list {
    list-style: none;
    padding: 0;
  }
  .cohort-list li {
    padding: 0.28rem 0;
    border-bottom: 1px solid #f0ead9;
    max-width: 46rem;
  }
  .cohort-list li.up strong {
    color: #006300;
  }
  .cohort-list li.down strong {
    color: #d03b3b;
  }
  .flags li {
    max-width: 46rem;
    margin-bottom: 0.5rem;
  }
  .exp {
    color: #898781;
  }
  .note {
    color: #6f6a61;
    max-width: 46rem;
    font-size: 0.93rem;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.93rem;
  }
  th,
  td {
    text-align: left;
    padding: 0.35rem 0.5rem;
    border-bottom: 1px solid #eee9df;
  }
  .tnum {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  .caveat {
    margin-top: 2rem;
    color: #898781;
    font-size: 0.88rem;
    max-width: 46rem;
  }
  .compare {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 1rem;
  }
  .cmp-card {
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    padding: 0.7rem 1rem;
  }
  .cmp-card h3 {
    margin: 0.2rem 0 0.4rem;
    font-size: 1rem;
  }
  .cmp-card ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .cmp-card li {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 0.6rem;
    padding: 0.3rem 0;
    border-bottom: 1px solid #f0ead9;
    font-size: 0.92rem;
  }
  .cmp-card input[type='checkbox'] {
    accent-color: #2a78d6;
    flex-shrink: 0;
    position: relative;
    top: 2px;
    cursor: pointer;
  }
  .cmp-name {
    flex: 1;
    min-width: 0;
  }
  .cmp-card li:last-child {
    border-bottom: none;
  }
  .cmp-card li.self {
    background: #faf3e3;
    border-radius: 6px;
    padding-left: 0.4rem;
    padding-right: 0.4rem;
    font-weight: 650;
  }
  .cmp-sub {
    display: block;
    color: #898781;
    font-size: 0.78rem;
  }
  .cmp-vals {
    display: flex;
    gap: 0.7rem;
    align-items: baseline;
    flex-shrink: 0;
  }
  .cmp-meta {
    color: #898781;
    font-size: 0.82rem;
  }
  .cmp-adj {
    font-variant-numeric: tabular-nums;
    font-weight: 650;
  }
  .cmp-adj.pos {
    color: #006300;
  }
  .cmp-adj.neg {
    color: #d03b3b;
  }
  .add-compare {
    margin-top: 0.6rem;
    max-width: 28rem;
  }
  .ov-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-top: 0.3rem;
  }
  .ov-chip {
    border: 1px solid #d8d0c0;
    background: #fffdf9;
    border-radius: 999px;
    padding: 0.15rem 0.7rem;
    font-size: 0.84rem;
    cursor: pointer;
    color: #52514e;
  }
  .ov-chip:hover {
    border-color: #d03b3b;
    color: #d03b3b;
  }
  .ov-table {
    align-self: center;
    font-size: 0.85rem;
    font-weight: 600;
  }
</style>
