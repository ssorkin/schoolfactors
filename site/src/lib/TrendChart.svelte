<script>
  /**
   * The headline chart: pass rate (met or exceeded, levels 3-4) and exceeded rate
   * (level 4) over time. Controls live in a right rail: subject, view split
   * (overall / by grade / by group), rate, and group chips. Comparison schools
   * (checked in the Compare-with cards) overlay as dashed lines; when overlays are
   * active the overall view shows a single rate so lines are comparable.
   * Lines break across the 2020-21 testing gap rather than bridging it.
   */
  import { GROUP_LABELS, GROUP_CATEGORIES, SERIES_COLORS } from '$lib/groups.js';

  let { subgroups = [], scores = [], overlays = [] } = $props();

  let subject = $state('ela');
  let split = $state('overall');
  let metric = $state('pct_met');
  let hover = $state(null);

  let activeGroups = $state([31, 111, 160, 128]);
  let colorAssign = $state({ 31: 0, 111: 1, 160: 2, 128: 3 });

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

  let series = $derived.by(() => {
    if (split === 'overall') {
      const all = subgroups
        .filter((r) => r.subject === subject && r.group === 1)
        .sort((a, b) => a.year - b.year);
      if (overlays.length) {
        return [
          {
            key: 'base',
            label: metric === 'pct_met' ? 'This page (met+)' : 'This page (exceeded)',
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
      return grades.map((g, i) => ({
        key: 'g' + g,
        label: 'Grade ' + g,
        color: ramp(grades.length === 1 ? 1 : i / (grades.length - 1)),
        pts: rows
          .filter((r) => r.grade === g && (metric === 'pct_met' ? r.pct_met : r.pct_exc) != null)
          .sort((a, b) => a.year - b.year)
          .map((r) => ({ year: r.year, v: metric === 'pct_met' ? r.pct_met : r.pct_exc, n: r.n }))
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

  // Overlay series: dashed, colors from palette slots not used by the main series.
  let overlaySeries = $derived.by(() => {
    const used = new Set();
    if (split === 'overall') {
      used.add(0);
      if (!overlays.length) used.add(1);
    } else if (split === 'group') {
      for (const s of Object.values(colorAssign)) used.add(s);
    }
    const free = SERIES_COLORS.map((_, i) => i).filter((i) => !used.has(i));
    return overlays.map((o, oi) => ({
      key: 'ov' + o.cds,
      label: o.name,
      color: SERIES_COLORS[free[oi % free.length] ?? (oi % SERIES_COLORS.length)],
      dashed: true,
      pts: (o.rows ?? [])
        .filter((r) => r.subject === subject && r.group === 1 && mval(r) != null)
        .sort((a, b) => a.year - b.year)
        .map((r) => ({ year: r.year, v: mval(r), n: r.n }))
    }));
  });

  let allSeries = $derived([...series, ...overlaySeries]);

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
            stroke-dasharray={s.dashed ? '6 4' : 'none'}
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
        {#if s.pts.length}
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
    {#if overlays.length}
      <div class="rail-sec">
        <span class="rail-label">Comparing (dashed)</span>
        {#each overlaySeries as o (o.key)}
          <span class="ov-item"><span class="dash" style="border-color: {o.color}"></span>{o.label}</span>
        {/each}
      </div>
    {/if}
    {#if split === 'group'}
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
  .dash {
    width: 18px;
    border-top: 2px dashed;
    display: inline-block;
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
