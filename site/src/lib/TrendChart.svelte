<script>
  /**
   * The headline chart: pass rate (met or exceeded, levels 3-4) and exceeded rate
   * (level 4) over time. Controls live in a right rail: subject, view split
   * (overall / by grade / by group), rate, and group chips. Comparison schools
   * (checked in the Compare-with cards) overlay as dashed lines; when overlays are
   * active the overall view shows a single rate so lines are comparable.
   * Lines break across the 2020-21 testing gap rather than bridging it.
   */
  import {
    GROUP_LABELS,
    GROUP_CATEGORIES,
    GROUP_THEMES,
    GROUP_SHORT,
    SERIES_COLORS
  } from '$lib/groups.js';

  let {
    subgroups = [],
    scores = [],
    overlays = [],
    initial = {},
    onstate = null,
    name = 'This page'
  } = $props();

  const initGroups = (initial.groups?.length ? initial.groups : [31, 111, 160, 128]).slice(
    0,
    SERIES_COLORS.length
  );
  let subject = $state(initial.subject === 'math' ? 'math' : 'ela');
  let split = $state(['overall', 'grade', 'group'].includes(initial.split) ? initial.split : 'overall');
  let metric = $state(initial.metric === 'pct_exc' ? 'pct_exc' : 'pct_met');
  let hover = $state(null);

  let activeGroups = $state(initGroups);
  let colorAssign = $state(Object.fromEntries(initGroups.map((g, i) => [g, i])));

  // Report chart state upward so the page can permalink it.
  $effect(() => {
    onstate?.({
      subject,
      split,
      metric,
      layout: layoutChoice,
      groups: activeGroups
    });
  });

  let availableGroups = $derived.by(() => {
    const present = new Set(subgroups.map((r) => r.group));
    return GROUP_CATEGORIES.map((cat) => ({
      label: cat.label,
      ids: cat.ids.filter((id) => present.has(id))
    })).filter((cat) => cat.ids.length);
  });

  function toggleGroup(id) {
    if (activeGroups.includes(id)) {
      activeGroups = activeGroups.filter((g) => g !== id);
      const { [id]: _, ...rest } = colorAssign;
      colorAssign = rest;
    } else {
      if (activeGroups.length >= SERIES_COLORS.length) return;
      const used = new Set(Object.values(colorAssign));
      const slot = SERIES_COLORS.findIndex((_, i) => !used.has(i));
      colorAssign = { ...colorAssign, [id]: slot };
      activeGroups = [...activeGroups, id];
    }
  }

  const W = 680;
  const H = 400;
  const M = { top: 18, right: 130, bottom: 40, left: 46 };

  function ramp(t) {
    const a = [0x86, 0xb6, 0xef];
    const b = [0x0d, 0x36, 0x6b];
    return `rgb(${a.map((av, i) => Math.round(av + (b[i] - av) * t)).join(',')})`;
  }

  let showMetricToggle = $derived(split !== 'overall' || overlays.length > 0);
  let mval = $derived((r) => (metric === 'pct_met' ? r.pct_met : r.pct_exc));

  // Layout: one overlaid chart vs small multiples. The group split defaults to
  // themed rows (facets); the grade split defaults to small multiples only when
  // comparators are active.
  let layoutChoice = $state(
    initial.layout === 'one' || initial.layout === 'facets' ? initial.layout : null
  );
  let layout = $derived(
    layoutChoice ??
      (split === 'group' ? 'facets' : overlays.length && split !== 'overall' ? 'facets' : 'one')
  );

  // Dash pattern identifies WHICH school in split views (color carries the series).
  const DASHES = ['6 4', '2 3', '9 3 2 3', '1 5'];

  // Grade → color map over the union of this page's and the overlays' grades, so a
  // grade keeps its color whether or not both schools serve it.
  let gradeColor = $derived.by(() => {
    const gset = new Set(scores.filter((r) => r.subject === subject).map((r) => r.grade));
    for (const o of overlays) {
      for (const r of o.scores ?? []) if (r.subject === subject) gset.add(r.grade);
    }
    const grades = [...gset].sort((a, b) => a - b);
    const map = new Map();
    grades.forEach((g, i) =>
      map.set(g, ramp(grades.length === 1 ? 1 : i / (grades.length - 1)))
    );
    return map;
  });

  let series = $derived.by(() => {
    if (split === 'overall') {
      const all = subgroups
        .filter((r) => r.subject === subject && r.group === 1)
        .sort((a, b) => a.year - b.year);
      if (overlays.length) {
        return [
          {
            key: 'base',
            label: `${name} (${metric === 'pct_met' ? 'met+' : 'exceeded'})`,
            color: SERIES_COLORS[0],
            pts: all.filter((r) => mval(r) != null).map((r) => ({ year: r.year, v: mval(r), n: r.n }))
          }
        ];
      }
      return [
        {
          key: 'met',
          label: 'Met or exceeded (3–4)',
          color: SERIES_COLORS[0],
          pts: all.filter((r) => r.pct_met != null).map((r) => ({ year: r.year, v: r.pct_met, n: r.n }))
        },
        {
          key: 'exc',
          label: 'Exceeded (level 4)',
          color: SERIES_COLORS[1],
          pts: all.filter((r) => r.pct_exc != null).map((r) => ({ year: r.year, v: r.pct_exc, n: r.n }))
        }
      ];
    }
    if (split === 'grade') {
      const rows = scores.filter((r) => r.subject === subject);
      const grades = [...new Set(rows.map((r) => r.grade))].sort((a, b) => a - b);
      return grades.map((g) => ({
        key: 'g' + g,
        label: 'Grade ' + g,
        color: gradeColor.get(g),
        pts: rows
          .filter((r) => r.grade === g && mval(r) != null)
          .sort((a, b) => a.year - b.year)
          .map((r) => ({ year: r.year, v: mval(r), n: r.n }))
      }));
    }
    return activeGroups
      .map((id) => ({
        key: 'grp' + id,
        label: GROUP_LABELS[id] ?? 'Group ' + id,
        color: SERIES_COLORS[colorAssign[id] ?? 0],
        pts: subgroups
          .filter((r) => r.subject === subject && r.group === id && mval(r) != null)
          .sort((a, b) => a.year - b.year)
          .map((r) => ({ year: r.year, v: mval(r), n: r.n }))
      }))
      .filter((s) => s.pts.length > 0);
  });

  // Overlay series mirror the CURRENT view for each checked school: same series
  // (per group / per grade / overall), same colors, distinguished by dash pattern.
  let overlaySeries = $derived.by(() => {
    const out = [];
    overlays.forEach((o, oi) => {
      const dash = DASHES[oi % DASHES.length];
      const mkpts = (rows) =>
        rows
          .filter((r) => mval(r) != null)
          .sort((a, b) => a.year - b.year)
          .map((r) => ({ year: r.year, v: mval(r), n: r.n }));

      if (split === 'overall') {
        // color per school here (one series each); free slots after the base line
        const free = SERIES_COLORS.map((_, i) => i).filter((i) => i !== 0);
        out.push({
          key: `ov-${o.cds}`,
          label: o.name,
          school: o.name,
          color: SERIES_COLORS[free[oi % free.length]],
          dash,
          endLabel: true,
          pts: mkpts((o.rows ?? []).filter((r) => r.subject === subject && r.group === 1))
        });
      } else if (split === 'grade') {
        const rows = (o.scores ?? []).filter((r) => r.subject === subject);
        const grades = [...new Set(rows.map((r) => r.grade))].sort((a, b) => a - b);
        for (const g of grades) {
          out.push({
            key: `ov-${o.cds}-g${g}`,
            label: `${o.name} — Grade ${g}`,
            school: o.name,
            color: gradeColor.get(g),
            dash,
            endLabel: false,
            pts: mkpts(rows.filter((r) => r.grade === g))
          });
        }
      } else {
        for (const id of activeGroups) {
          const pts = mkpts(
            (o.rows ?? []).filter((r) => r.subject === subject && r.group === id)
          );
          if (!pts.length) continue;
          out.push({
            key: `ov-${o.cds}-grp${id}`,
            label: `${o.name} — ${GROUP_LABELS[id] ?? id}`,
            school: o.name,
            color: SERIES_COLORS[colorAssign[id] ?? 0],
            dash,
            endLabel: false,
            pts
          });
        }
      }
    });
    return out.filter((s) => s.pts.length > 0);
  });

  let allSeries = $derived([...series, ...overlaySeries]);

  // Small-multiples panels: one per visible series (group or grade); within a
  // panel, color identifies the SCHOOL (this page = slot 1, comparators next),
  // consistent across panels.
  const SCHOOL_COLORS = SERIES_COLORS;

  // Group panels come from the themes (not the pick-groups chips): every theme
  // member with data gets its own panel, capped at four per theme — kept in
  // canonical theme order, dropping the smallest groups by total tested n.
  let themedFacetIds = $derived.by(() => {
    if (split !== 'group') return [];
    const rows = (id) =>
      subgroups.filter((r) => r.subject === subject && r.group === id && mval(r) != null);
    const size = (id) => rows(id).reduce((s, r) => s + (r.n ?? 0), 0);
    const out = [];
    for (const theme of GROUP_THEMES) {
      const withData = theme.ids.filter((id) => rows(id).length >= 2);
      const keep = new Set(
        withData
          .slice()
          .sort((a, b) => size(b) - size(a))
          .slice(0, 4)
      );
      out.push(...theme.ids.filter((id) => keep.has(id)));
    }
    return out;
  });
  let facetPanels = $derived.by(() => {
    if (split === 'overall') return [];
    const mkpts = (rows) =>
      rows
        .filter((r) => mval(r) != null)
        .sort((a, b) => a.year - b.year)
        .map((r) => ({ year: r.year, v: mval(r), n: r.n }));

    const defs =
      split === 'grade'
        ? [...gradeColor.keys()].map((g) => ({
            key: 'g' + g,
            label: 'Grade ' + g,
            base: () => mkpts(scores.filter((r) => r.subject === subject && r.grade === g)),
            over: (o) =>
              mkpts((o.scores ?? []).filter((r) => r.subject === subject && r.grade === g))
          }))
        : themedFacetIds.map((id) => ({
            key: 'grp' + id,
            label: GROUP_LABELS[id] ?? 'Group ' + id,
            base: () =>
              mkpts(subgroups.filter((r) => r.subject === subject && r.group === id)),
            over: (o) =>
              mkpts((o.rows ?? []).filter((r) => r.subject === subject && r.group === id))
          }));

    return defs
      .map((d) => {
        const lines = [];
        const basePts = d.base();
        if (basePts.length) {
          lines.push({ school: name, color: SCHOOL_COLORS[0], pts: basePts });
        }
        overlays.forEach((o, oi) => {
          const pts = d.over(o);
          if (pts.length) {
            lines.push({
              school: o.name,
              color: SCHOOL_COLORS[(oi + 1) % SCHOOL_COLORS.length],
              pts
            });
          }
        });
        return { key: d.key, label: d.label, lines };
      })
      .filter((p) => p.lines.length);
  });

  // Themed rows: the default group view. One compact full-width row per theme
  // (economic, disability, language, race/ethnicity, parent education), at most
  // four series per row — themes with more members chunk into extra rows, never
  // leaving a singleton behind.
  function chunkIds(ids, max = 4) {
    if (ids.length <= max) return [ids];
    const rows = [];
    let i = 0;
    while (ids.length - i > max) {
      const take = ids.length - i - max === 1 ? max - 1 : max;
      rows.push(ids.slice(i, i + take));
      i += take;
    }
    rows.push(ids.slice(i));
    return rows;
  }

  let themedRows = $derived.by(() => {
    if (split !== 'group') return [];
    const mkpts = (rows, id) =>
      rows
        .filter((r) => r.subject === subject && r.group === id && mval(r) != null)
        .sort((a, b) => a.year - b.year)
        .map((r) => ({ year: r.year, v: mval(r), n: r.n }));
    const out = [];
    for (const theme of GROUP_THEMES) {
      const withData = theme.ids.filter((id) => mkpts(subgroups, id).length >= 2);
      const chunks = chunkIds(withData);
      chunks.forEach((chunk, ci) => {
        const lines = [];
        const legend = [];
        // Themed rows render only without comparators (the template switches
        // to per-group small multiples when overlays are active), so each
        // row's lines are this page's groups alone.
        chunk.forEach((id, i) => {
          const short = GROUP_SHORT[id] ?? GROUP_LABELS[id] ?? 'Group ' + id;
          legend.push({ id, label: short, color: SERIES_COLORS[i] });
          lines.push({
            key: `${id}-base`,
            full: `${name} — ${GROUP_LABELS[id] ?? id}`,
            color: SERIES_COLORS[i],
            dash: null,
            pts: mkpts(subgroups, id)
          });
        });
        if (lines.length) {
          out.push({
            key: theme.label + ci,
            label: theme.label + (chunks.length > 1 ? ` (${ci + 1}/${chunks.length})` : ''),
            lines,
            legend
          });
        }
      });
    }
    return out;
  });

  const RW = 680;
  const RH = 118;
  const RM = { top: 8, right: 14, bottom: 18, left: 34 };
  let tyears = $derived(
    [...new Set(themedRows.flatMap((r) => r.lines.flatMap((l) => l.pts.map((p) => p.year))))].sort(
      (a, b) => a - b
    )
  );
  const tsx = (yr) =>
    RM.left +
    ((yr - (tyears[0] ?? 2015)) / Math.max(1, (tyears.at(-1) ?? 2025) - (tyears[0] ?? 2015))) *
      (RW - RM.left - RM.right);
  const tsy = (v) => RM.top + (1 - v / 100) * (RH - RM.top - RM.bottom);

  const FW = 250;
  const FH = 160;
  const FM = { top: 8, right: 10, bottom: 20, left: 30 };
  const fsx = (yr) =>
    FM.left +
    ((yr - (years[0] ?? 2015)) / Math.max(1, (years.at(-1) ?? 2025) - (years[0] ?? 2015))) *
      (FW - FM.left - FM.right);
  const fsy = (v) => FM.top + (1 - v / 100) * (FH - FM.top - FM.bottom);

  let years = $derived(
    [...new Set(allSeries.flatMap((s) => s.pts.map((p) => p.year)))].sort((a, b) => a - b)
  );
  const sx = (yr) =>
    M.left +
    ((yr - (years[0] ?? 2015)) / Math.max(1, (years.at(-1) ?? 2025) - (years[0] ?? 2015))) *
      (W - M.left - M.right);
  const sy = (v) => M.top + (1 - v / 100) * (H - M.top - M.bottom);

  function runs(pts) {
    const out = [];
    let cur = [];
    for (const p of pts) {
      if (cur.length && p.year - cur.at(-1).year > 1) {
        out.push(cur);
        cur = [];
      }
      cur.push(p);
    }
    if (cur.length) out.push(cur);
    return out;
  }
</script>

<div class="chart">
  <div class="plot">
    {#if layout === 'facets' && split === 'group' && !overlays.length && themedRows.length}
      <div class="rows">
        {#each themedRows as row (row.key)}
          <div class="trow">
            <div class="trow-head">
              <span class="trow-title">{row.label}</span>
              {#each row.legend as g (g.id)}
                <span class="trow-key">
                  <span class="dot" style="background: {g.color}"></span>{g.label}
                </span>
              {/each}
            </div>
            <svg viewBox="0 0 {RW} {RH}" role="img" aria-label={row.label + ' over time'}>
              {#each [0, 50, 100] as t (t)}
                <line x1={RM.left} x2={RW - RM.right} y1={tsy(t)} y2={tsy(t)} stroke="#eee9df" />
                <text x={RM.left - 5} y={tsy(t) + 3} class="ftick" text-anchor="end">{t}</text>
              {/each}
              {#each tyears as yr (yr)}
                <text x={tsx(yr)} y={RH - 5} class="ftick" text-anchor="middle">{yr}</text>
              {/each}
              {#each row.lines as line (line.key)}
                {#each runs(line.pts) as run, ri (ri)}
                  <polyline
                    fill="none"
                    stroke={line.color}
                    stroke-width="2"
                    stroke-dasharray={line.dash ?? 'none'}
                    opacity={hover && hover.series !== row.key + line.key ? 0.35 : 0.95}
                    points={run.map((p) => `${tsx(p.year)},${tsy(p.v)}`).join(' ')}
                  />
                {/each}
                {#each line.pts as p (p.year)}
                  <circle
                    cx={tsx(p.year)}
                    cy={tsy(p.v)}
                    r={hover?.series === row.key + line.key && hover?.year === p.year ? 4.5 : 2.6}
                    fill={line.color}
                    stroke="#fffdf9"
                    stroke-width="1"
                    opacity={hover && hover.series !== row.key + line.key ? 0.35 : 1}
                    onmouseenter={() =>
                      (hover = {
                        series: row.key + line.key,
                        label: line.full,
                        year: p.year,
                        v: p.v,
                        n: p.n
                      })}
                    onmouseleave={() => (hover = null)}
                  />
                {/each}
              {/each}
            </svg>
          </div>
        {/each}
      </div>
      <div class="tip" aria-live="polite">
        {#if hover}
          <strong>{hover.label}</strong>, {hover.year}: {hover.v.toFixed(0)}% ·
          {hover.n.toLocaleString()} students with scores
        {:else}
          Groups with fewer than 11 students are suppressed at the source and absent here.
        {/if}
      </div>
    {:else if layout === 'facets' && facetPanels.length}
      <div class="facets">
        {#each facetPanels as panel (panel.key)}
          <div class="facet">
            <div class="facet-title">{panel.label}</div>
            <svg viewBox="0 0 {FW} {FH}" role="img" aria-label={panel.label + ' over time'}>
              {#each [0, 50, 100] as t (t)}
                <line x1={FM.left} x2={FW - FM.right} y1={fsy(t)} y2={fsy(t)} stroke="#eee9df" />
                <text x={FM.left - 4} y={fsy(t) + 3} class="ftick" text-anchor="end">{t}</text>
              {/each}
              {#if years.length}
                <text x={fsx(years[0])} y={FH - 6} class="ftick" text-anchor="middle">{years[0]}</text>
                <text x={fsx(years.at(-1))} y={FH - 6} class="ftick" text-anchor="middle">{years.at(-1)}</text>
              {/if}
              {#each panel.lines as line (line.school)}
                {#each runs(line.pts) as run, ri (ri)}
                  <polyline
                    fill="none"
                    stroke={line.color}
                    stroke-width="2"
                    points={run.map((p) => `${fsx(p.year)},${fsy(p.v)}`).join(' ')}
                  />
                {/each}
                {#each line.pts as p (p.year)}
                  <circle
                    cx={fsx(p.year)}
                    cy={fsy(p.v)}
                    r="2.8"
                    fill={line.color}
                    stroke="#fffdf9"
                    stroke-width="1"
                    onmouseenter={() =>
                      (hover = {
                        series: panel.key + line.school,
                        label: `${line.school} — ${panel.label}`,
                        year: p.year,
                        v: p.v,
                        n: p.n
                      })}
                    onmouseleave={() => (hover = null)}
                  />
                {/each}
              {/each}
            </svg>
          </div>
        {/each}
      </div>
      <div class="tip" aria-live="polite">
        {#if hover}
          <strong>{hover.label}</strong>, {hover.year}: {hover.v.toFixed(0)}% ·
          {hover.n.toLocaleString()} students with scores
        {:else}
          &nbsp;
        {/if}
      </div>
    {:else}
    <svg viewBox="0 0 {W} {H}" role="img" aria-label="Share of students meeting or exceeding the standard over time">
      {#each [0, 25, 50, 75, 100] as t (t)}
        <line x1={M.left} x2={W - M.right} y1={sy(t)} y2={sy(t)} stroke="#eee9df" />
        <text x={M.left - 6} y={sy(t) + 4} class="tick" text-anchor="end">{t}%</text>
      {/each}
      {#each years as yr (yr)}
        <text x={sx(yr)} y={H - M.bottom + 18} class="tick" text-anchor="middle">{yr}</text>
      {/each}
      {#if years.includes(2019) && years.includes(2022)}
        <text x={(sx(2019) + sx(2022)) / 2} y={M.top + 12} class="gap" text-anchor="middle">
          no data 2020–21
        </text>
      {/if}
      {#each allSeries as s (s.key)}
        {#each runs(s.pts) as run, ri (ri)}
          <polyline
            fill="none"
            stroke={s.color}
            stroke-width="2"
            stroke-dasharray={s.dash ?? 'none'}
            opacity={hover && hover.series !== s.key ? 0.3 : 0.95}
            points={run.map((p) => `${sx(p.year)},${sy(p.v)}`).join(' ')}
          />
        {/each}
        {#each s.pts as p (p.year)}
          <circle
            cx={sx(p.year)}
            cy={sy(p.v)}
            r={hover?.series === s.key && hover?.year === p.year ? 5.5 : 3.5}
            fill={s.color}
            stroke="#fffdf9"
            stroke-width="1.5"
            opacity={hover && hover.series !== s.key ? 0.3 : 1}
            onmouseenter={() => (hover = { series: s.key, label: s.label, year: p.year, v: p.v, n: p.n })}
            onmouseleave={() => (hover = null)}
          />
        {/each}
        {#if s.pts.length && s.endLabel !== false}
          <text x={sx(s.pts.at(-1).year) + 8} y={sy(s.pts.at(-1).v) + 4} class="lbl" fill="#52514e">
            {s.label.length > 18 ? s.label.slice(0, 17) + '…' : s.label}
          </text>
        {/if}
      {/each}
    </svg>
    <div class="tip" aria-live="polite">
      {#if hover}
        <strong>{hover.label}</strong>, {hover.year}: {hover.v.toFixed(0)}% ·
        {hover.n.toLocaleString()} students with scores
      {:else}
        &nbsp;
      {/if}
    </div>
    {/if}
  </div>

  <div class="rail">
    <div class="rail-sec">
      <span class="rail-label">Subject</span>
      <button class:active={subject === 'ela'} onclick={() => (subject = 'ela')}>ELA</button>
      <button class:active={subject === 'math'} onclick={() => (subject = 'math')}>Math</button>
    </div>
    <div class="rail-sec">
      <span class="rail-label">View</span>
      <button class:active={split === 'overall'} onclick={() => (split = 'overall')}>Overall</button>
      <button class:active={split === 'grade'} onclick={() => (split = 'grade')}>By grade</button>
      <button class:active={split === 'group'} onclick={() => (split = 'group')}>By group</button>
    </div>
    {#if showMetricToggle}
      <div class="rail-sec">
        <span class="rail-label">Rate</span>
        <button class:active={metric === 'pct_met'} onclick={() => (metric = 'pct_met')}>Met+</button>
        <button class:active={metric === 'pct_exc'} onclick={() => (metric = 'pct_exc')}>Exceeded</button>
      </div>
    {/if}
    {#if split !== 'overall'}
      <div class="rail-sec">
        <span class="rail-label">Layout</span>
        {#if split === 'group'}
          <button class:active={layout === 'facets'} onclick={() => (layoutChoice = 'facets')}>
            Themed rows
          </button>
          <button class:active={layout === 'one'} onclick={() => (layoutChoice = 'one')}>
            Pick groups
          </button>
        {:else}
          <button class:active={layout === 'one'} onclick={() => (layoutChoice = 'one')}>
            One chart
          </button>
          <button class:active={layout === 'facets'} onclick={() => (layoutChoice = 'facets')}>
            Small multiples
          </button>
        {/if}
      </div>
    {/if}
    {#if overlays.length}
      <div class="rail-sec">
        <span class="rail-label">Comparing</span>
        {#if layout === 'facets' && split !== 'overall'}
          <span class="ov-item">
            <span class="swatch" style="background: {SERIES_COLORS[0]}"></span>{name}
          </span>
          {#each overlays as o, oi (o.cds)}
            <span class="ov-item">
              <span class="swatch" style="background: {SERIES_COLORS[(oi + 1) % SERIES_COLORS.length]}"></span>
              {o.name}
            </span>
          {/each}
          <p class="chip-note">One panel per series; color identifies the school.</p>
        {:else}
          {#each overlays as o, oi (o.cds)}
            <span class="ov-item">
              <svg width="26" height="8" aria-hidden="true">
                <line
                  x1="0"
                  y1="4"
                  x2="26"
                  y2="4"
                  stroke="#52514e"
                  stroke-width="2"
                  stroke-dasharray={DASHES[oi % DASHES.length]}
                />
              </svg>
              {o.name}
            </span>
          {/each}
          <p class="chip-note">
            Dashes identify the school; colors keep meaning the series (rate, grade, or
            group).
          </p>
        {/if}
      </div>
    {/if}
    {#if split === 'group' && layout === 'one'}
      <div class="rail-sec chips">
        <span class="rail-label">Groups (up to {SERIES_COLORS.length})</span>
        {#each availableGroups as cat (cat.label)}
          <span class="cat-label">{cat.label}</span>
          {#each cat.ids as id (id)}
            <button
              class="chip"
              class:on={activeGroups.includes(id)}
              style={activeGroups.includes(id)
                ? `border-color: ${SERIES_COLORS[colorAssign[id]]}; background: ${SERIES_COLORS[colorAssign[id]]}18`
                : ''}
              onclick={() => toggleGroup(id)}
            >
              {#if activeGroups.includes(id)}<span
                  class="dot"
                  style="background: {SERIES_COLORS[colorAssign[id]]}"
                ></span>{/if}
              {GROUP_LABELS[id]}
            </button>
          {/each}
        {/each}
        <p class="chip-note">
          "Not …" groups are computed from counts; cells with fewer than 11 students
          are absent at the source.
        </p>
      </div>
    {/if}
  </div>
</div>

<style>
  .chart {
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    padding: 0.8rem 1rem 0.3rem;
    display: flex;
    gap: 1rem;
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .plot {
    flex: 1 1 420px;
    min-width: 0;
  }
  svg {
    width: 100%;
    height: auto;
  }
  .rail {
    flex: 0 1 215px;
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
    padding-top: 0.2rem;
  }
  .rail-sec {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
    align-items: center;
  }
  .rail-label {
    display: block;
    width: 100%;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #898781;
    margin-bottom: 0.1rem;
  }
  .rail button {
    border: 1px solid #d8d0c0;
    background: #faf7f2;
    border-radius: 6px;
    padding: 0.22rem 0.65rem;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .rail button.active {
    background: #2a78d6;
    border-color: #2a78d6;
    color: #fff;
  }
  .chips {
    max-height: 300px;
    overflow-y: auto;
  }
  .cat-label {
    display: block;
    width: 100%;
    font-size: 0.72rem;
    color: #b0aa9c;
    margin-top: 0.25rem;
  }
  .chip {
    border-radius: 999px !important;
    padding: 0.1rem 0.55rem !important;
    font-size: 0.76rem !important;
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    color: #52514e;
  }
  .chip.on {
    color: #211d18;
    font-weight: 600;
  }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    display: inline-block;
  }
  .chip-note {
    color: #898781;
    font-size: 0.74rem;
    margin: 0.4rem 0 0;
  }
  .ov-item {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.82rem;
    color: #52514e;
    width: 100%;
  }
  .facets {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 0.6rem;
  }
  .rows {
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
  }
  .trow {
    border: 1px solid #f0ead9;
    border-radius: 8px;
    padding: 0.3rem 0.4rem 0;
    background: #fffdf9;
  }
  .trow-head {
    display: flex;
    align-items: baseline;
    gap: 0.7rem;
    flex-wrap: wrap;
    padding: 0 0.2rem 0.1rem;
  }
  .trow-title {
    font-size: 0.8rem;
    font-weight: 650;
    color: #52514e;
  }
  .trow-key {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.74rem;
    color: #6f6a61;
  }
  .trow svg {
    width: 100%;
    height: auto;
  }
  .facet {
    border: 1px solid #f0ead9;
    border-radius: 8px;
    padding: 0.35rem 0.4rem 0.1rem;
    background: #fffdf9;
  }
  .facet-title {
    font-size: 0.8rem;
    font-weight: 650;
    color: #52514e;
    padding-left: 0.2rem;
  }
  .facet svg {
    width: 100%;
    height: auto;
  }
  .ftick {
    font-size: 9px;
    fill: #b0aa9c;
  }
  .swatch {
    width: 10px;
    height: 10px;
    border-radius: 3px;
    display: inline-block;
    flex-shrink: 0;
  }
  .tick {
    font-size: 12px;
    fill: #898781;
  }
  .lbl {
    font-size: 11.5px;
  }
  .gap {
    font-size: 11px;
    fill: #b8b2a5;
    font-style: italic;
  }
  circle {
    cursor: pointer;
  }
  .tip {
    font-size: 0.9rem;
    color: #52514e;
    padding: 0.25rem 0.2rem 0.45rem;
    min-height: 1.4rem;
  }
</style>
