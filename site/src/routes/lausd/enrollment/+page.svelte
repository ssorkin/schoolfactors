<script>
  /**
   * STAGING DRAFT of the enrollment page, compiled from
   * analysis/enrollment_page_narrative.md. Prose is the author's; every number
   * is computed from the live export. Not linked from navigation.
   */
  import { onMount } from 'svelte';
  import { getSchools } from '$lib/district/lausdData.js';

  let { data } = $props();
  let enrollment = $derived(data.enrollment);

  let flows = $derived(enrollment?.flows ?? null);
  let nar = $derived(enrollment?.narrative ?? null);

  const fmtN = (v) => Math.round(v).toLocaleString();
  const fmtKk = (v) => `${Math.round(v / 1000)}k`;
  const fmtPct = (v, dp = 1) => `${v > 0 ? '+' : ''}${(v * 100).toFixed(dp)}%`;

  // ---- hero chart: LAUSD-authorized enrollment by class (stacked, 2002+)
  //      vs resident children 5-17 (2005+) ----
  const W = 680;
  const H = 270;
  const M = { top: 14, right: 44, bottom: 40, left: 60 };
  const X0 = 2002;
  const X1 = 2026;
  const CLS = [
    { i: 1, key: 'trad', label: 'Traditional LAUSD', color: '#eb6834' },
    { i: 2, key: 'aff', label: 'Affiliated charter', color: '#f0b28a' },
    { i: 3, key: 'ind', label: 'Independent charter', color: '#1e6b3a' }
  ];
  let cpts = $derived(
    (nar?.lausd_classes ?? [])
      .filter(([y]) => y >= X0)
      .map(([y, trad, aff, ind]) => ({ year: y, trad, aff, ind, total: trad + aff + ind }))
  );
  let rpts = $derived(
    (nar?.resident_517 ?? []).map(([year, v, survey, pub]) => ({ year, v, survey, pub }))
  );
  let allVals = $derived([...cpts.map((p) => p.total), ...rpts.map((p) => p.v)]);
  let hi = $derived(Math.max(...allVals) * 1.03);
  const X = $derived((y) => M.left + ((y - X0) / (X1 - X0)) * (W - M.left - M.right));
  const Y = $derived((v) => M.top + (1 - v / hi) * (H - M.top - M.bottom));
  let hover = $state(null);
  // stacked bands, bottom-up: trad, aff, ind
  let bands = $derived(
    CLS.map((s, si) => {
      const pts = cpts.map((p) => {
        let lo = 0;
        for (let i = 0; i < si; i++) lo += p[CLS[i].key];
        return { y: p.year, lo, hi: lo + p[s.key] };
      });
      const path =
        pts.map((p, i) => `${i ? 'L' : 'M'}${X(p.y)},${Y(p.hi)}`).join('') +
        [...pts].reverse().map((p) => `L${X(p.y)},${Y(p.lo)}`).join('') +
        'Z';
      return { ...s, path };
    })
  );
  function heroMove(e) {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    let best = null;
    for (const p of cpts) {
      if (best == null || Math.abs(X(p.year) - px) < Math.abs(X(best.year) - px)) best = p;
    }
    hover = best ? { year: best.year, kind: 'enr' } : null;
  }
  let hoverCls = $derived(
    hover?.kind === 'enr' ? cpts.find((p) => p.year === hover.year) : null
  );
  // dotted right-axis series: LAUSD-authorized enrollment as a share of
  // resident children 5-17 (years where both series exist)
  let sharePts = $derived.by(() => {
    const enrBy = Object.fromEntries(cpts.map((p) => [p.year, p.total]));
    return rpts
      .filter((p) => enrBy[p.year] != null)
      .map((p) => ({ year: p.year, s: enrBy[p.year] / p.v }));
  });
  // right axis is zero-based: the share line reads at its true altitude
  const YR = $derived((s) => M.top + (1 - s) * (H - M.top - M.bottom));
  let hoverShare = $derived(
    hoverCls ? sharePts.find((p) => p.year === hoverCls.year) : null
  );

  // ---- reconciliation accounting ----
  let stateBy = $derived(Object.fromEntries((flows?.levels?.state ?? []).map(([y, r]) => [y, r])));
  let countyBy = $derived(
    Object.fromEntries((flows?.levels?.county ?? []).map(([y, r]) => [y, r]))
  );
  let distBy = $derived(
    Object.fromEntries((flows?.levels?.district ?? []).map(([y, r]) => [y, r]))
  );
  // statewide universe mismatch for a window (positive fraction of CDE seats)
  let mOf = $derived((y) => (stateBy[y] ? (stateBy[y].cde - stateBy[y].public) / stateBy[y].cde : null));

  let shareHist = $derived(Object.fromEntries((nar?.county_share_hist ?? []).map(
    ([y, la, rest]) => [y, { la, rest }]
  )));

  // slots (section 0)
  let enr2015 = $derived(shareHist[2015]?.la);
  let latestSpring = $derived(Math.max(...(nar?.county_share_hist ?? [[0]]).map(([y]) => y)));
  let enrLatest = $derived(shareHist[latestSpring]?.la);
  let resDecline = $derived(
    distBy[2015] && distBy[2023] ? distBy[2023].total / distBy[2015].total - 1 : null
  );
  let enrDeclineWindows = $derived(
    distBy[2015] && distBy[2023] ? distBy[2023].cde / distBy[2015].cde - 1 : null
  );
  // per-class 5-yr means matching an ACS window (springs y-3 .. y+1)
  let clsYearBy = $derived(
    Object.fromEntries(
      (nar?.lausd_classes ?? []).map(([y, trad, aff, ind]) => [y, { trad, aff, ind }])
    )
  );
  let clsMean = $derived((y, k) => {
    const springs = [];
    for (let s = y - 3; s <= y + 1; s++) if (clsYearBy[s]) springs.push(clsYearBy[s][k]);
    return springs.length === 5 ? springs.reduce((a, b) => a + b, 0) / 5 : null;
  });

  // slots (sections 2-3)
  let share = $derived((y) =>
    shareHist[y] ? shareHist[y].la / (shareHist[y].la + shareHist[y].rest) : null
  );
  let countyResidLatest = $derived(
    countyBy[2023] ? (countyBy[2023].public - countyBy[2023].cde) / countyBy[2023].cde : null
  );
  let countyLeak = $derived(
    countyBy[2023] && mOf(2023) != null
      ? countyBy[2023].public - countyBy[2023].cde + mOf(2023) * countyBy[2023].cde
      : null
  );
  let virtual = $derived(flows?.virtual ?? []);
  let insideLatest = $derived(
    nar?.inside_charters?.length ? nar.inside_charters[nar.inside_charters.length - 1] : null
  );

  // deltas list, restricted to windows 2015+ so the years match the prose anchor
  let residence = $derived((enrollment?.residence ?? []).filter(([y]) => y >= 2015));
  let byClass = $derived(enrollment?.by_class ?? []);
  function chg(rows, key) {
    const vals = rows.map(([, r]) => r[key]).filter((v) => v != null);
    return vals.length < 2
      ? null
      : { from: vals[0], to: vals[vals.length - 1], y0: rows[0][0], y1: rows[rows.length - 1][0] };
  }
  // Class bullets use 5-yr window means (springs y-3..y+1) so the whole
  // "Matched ACS windows" block shares one convention with the prose; the
  // single-year census-day series appears only in the labeled
  // "Current enrollment" divider line and Chart 1.
  let clsWindow = $derived((k) => {
    const a = clsMean(2015, k);
    const b = clsMean(2023, k);
    return a != null && b != null
      ? { from: a, to: b, y0: 2015, y1: 2023 }
      : null;
  });
  let clsLatest = $derived.by(() => {
    const rows = nar?.lausd_classes ?? [];
    return rows.length ? rows[rows.length - 1] : null;
  });
  let deltas = $derived({
    children: chg(residence, 'total'),
    pub: chg(residence, 'public'),
    prv: chg(residence, 'private'),
    not: chg(residence, 'not_enrolled'),
    trad: clsWindow('trad'),
    aff: clsWindow('aff'),
    ind: clsWindow('ind')
  });
  const sgn = (dl) => {
    if (dl == null) return '—';
    const p = Math.round((dl.to / dl.from - 1) * 100);
    return `${fmtKk(dl.from)} → ${fmtKk(dl.to)} (${p > 0 ? '+' : ''}${p}%)`;
  };
  const yrs = (dl) => (dl == null ? '' : `${dl.y0}→${dl.y1}`);
  let notAges = $derived.by(() => {
    const rows = residence.filter(([, r]) => r.by_age);
    if (rows.length < 2) return null;
    return {
      first: rows[0][1].by_age.not_enrolled,
      last: rows[rows.length - 1][1].by_age.not_enrolled,
      y0: rows[0][0],
      y1: rows[rows.length - 1][0]
    };
  });
  const fmtK1 = (v) => `${(v / 1000).toFixed(1)}k`;

  // ---- state stability chart: every ACS window, both universes ----
  let stabAll = $derived(
    (flows?.levels?.state ?? []).map(([y, s]) => ({
      y, public: s.public, cde: s.cde, total: s.total,
      pct: (s.public - s.cde) / s.cde, frac: s.cde / s.total
    }))
  );
  const SW = 680;
  const SH = 240;
  const SM = { top: 14, right: 44, bottom: 36, left: 66 };
  let sx0 = $derived(Math.min(...stabAll.map((r) => r.y)));
  let sx1 = $derived(Math.max(...stabAll.map((r) => r.y)));
  let svals = $derived(stabAll.flatMap((r) => [r.public, r.cde]));
  const slo = 0; // zero-based left axis
  let shi = $derived(Math.max(...svals) * 1.04);
  const SX = $derived((y) => SM.left + ((y - sx0) / Math.max(sx1 - sx0, 1)) * (SW - SM.left - SM.right));
  const SY = $derived((v) => SM.top + (1 - (v - slo) / (shi - slo)) * (SH - SM.top - SM.bottom));
  let stabHover = $state(null);
  // dotted right-axis series: ACS public 5-17 as a share of CDE enrollment
  // (zero-based right axis)
  const SYR = $derived((r) => SM.top + (1 - r) * (SH - SM.top - SM.bottom));

  // County seat ledger: every column sums exactly to the ACS residents row.
  const LEDGER_YEARS = [2011, 2016, 2020, 2023];
  let ledgerBy = $derived(Object.fromEntries((nar?.ledger ?? []).map((r) => [r.y, r])));
  let ledgerCols = $derived(
    LEDGER_YEARS.map((y) => {
      const l = ledgerBy[y];
      const c = countyBy[y];
      const m = mOf(y);
      if (!l || !c || m == null) return null;
      const adj = -m * l.county;
      const inSeats = l.county + adj;
      const outside = c.public - inSeats;
      return { y, ...l, adj, inSeats, outside, residents: c.public };
    }).filter(Boolean)
  );
  const LEDGER_ROWS = [
    ['trad_aff', 'LAUSD traditional + affiliated charter'],
    ['ind', 'LAUSD independent charters'],
    ['other_uni', 'Other unified districts'],
    ['elemhs', 'Elementary & high-school districts'],
    ['remainder', 'County office & other LEAs']
  ];

  // LEA type from the composition of its associated seats (latest window):
  // a quarter of enrollment in fully/primarily-virtual charters marks a
  // virtual-heavy authorizer; a ~third in charters overall marks a
  // brick-and-mortar charter umbrella; otherwise seats are the district's own.
  const LEA_TYPES = {
    district: { label: 'district', long: 'District-run schools', color: '#2a78d6' },
    charter: { label: 'charter B&M', long: 'Charter authorizer (brick & mortar)', color: '#008300' },
    virtual: { label: 'virtual', long: 'Charter authorizer (virtual-heavy)', color: '#4a3aa7' }
  };
  function leaType(mix) {
    if (!mix) return 'district';
    const tot = (mix.dr ?? 0) + (mix.cb ?? 0) + (mix.cv ?? 0);
    if (!tot) return 'district';
    if ((mix.cv ?? 0) / tot >= 0.25) return 'virtual';
    if (((mix.cb ?? 0) + (mix.cv ?? 0)) / tot >= 0.3) return 'charter';
    return 'district';
  }
  const mixTitle = (mix) =>
    mix
      ? `district-run ${fmtN(mix.dr ?? 0)} · charter B&M ${fmtN(mix.cb ?? 0)} · ` +
        `virtual ${fmtN(mix.cv ?? 0)} (5-yr means, latest window)`
      : '';

  // Per-district net imports (children): seats·(1−m) − resident public children.
  let distNets = $derived.by(() => {
    const rows = (nar?.district_flows ?? []).map((r) => {
      const by = Object.fromEntries(r.detail.map(([v, acs, cde]) => [v, { acs, cde }]));
      const net = {};
      for (const y of LEDGER_YEARS) {
        const m = mOf(y);
        net[y] = by[y] && m != null ? by[y].cde * (1 - m) - by[y].acs : null;
      }
      return {
        name: r.name.replace(' Unified', ''),
        by,
        net,
        mix: r.mix,
        type: leaType(r.mix)
      };
    });
    const lausd = rows.find((r) => r.name.startsWith('Los Angeles'));
    const others = rows.filter((r) => r !== lausd && r.net[2020] != null);
    others.sort((a, b) => b.net[2020] - a.net[2020]);
    const importers = others.slice(0, 7);
    const exporters = others.slice(-4).reverse();
    const shown = new Set([...importers, ...exporters]);
    const restNet = {};
    for (const y of LEDGER_YEARS) {
      restNet[y] = others
        .filter((r) => !shown.has(r) && r.net[y] != null)
        .reduce((s, r) => s + r.net[y], 0);
    }
    return { lausd, importers, exporters, restNet };
  });

  // ---- performance vs flows scatters (raw era percentile / adjusted as-of-2017)
  function pearson(xs, ys) {
    const n = xs.length;
    const mx = xs.reduce((a, b) => a + b, 0) / n;
    const my = ys.reduce((a, b) => a + b, 0) / n;
    let sxy = 0, sxx = 0, syy = 0;
    for (let i = 0; i < n; i++) {
      sxy += (xs[i] - mx) * (ys[i] - my);
      sxx += (xs[i] - mx) ** 2;
      syy += (ys[i] - my) ** 2;
    }
    return { r: sxy / Math.sqrt(sxx * syy), slope: sxy / sxx, icpt: my - (sxy / sxx) * mx };
  }
  let perfScatter = $derived.by(() => {
    const rows = (nar?.district_flows ?? [])
      .map((r) => {
        const by = Object.fromEntries(r.detail.map(([v, a, c]) => [v, { a, c }]));
        const m = mOf(2020);
        if (!by[2020] || m == null || !r.perf) return null;
        const net = by[2020].c * (1 - m) - by[2020].a;
        return {
          name: r.name.replace(' Unified', ''),
          netpct: net / by[2020].c,
          raw: r.perf.raw,
          adj: r.perf.adj17,
          sed: r.perf.sed,
          stu: r.perf.stu,
          simstu: r.perf.simstu17,
          type: leaType(r.mix)
        };
      })
      .filter(Boolean);
    const lausd = rows.find((r) => r.name.startsWith('Los Angeles'));
    const sub = rows.filter((r) => r !== lausd && r.raw != null && r.adj != null);
    const sedSub = sub.filter((r) => r.sed != null);
    const stuSub = sub.filter((r) => r.stu != null);
    return {
      sub,
      lausd,
      raw: pearson(sub.map((r) => r.raw), sub.map((r) => r.netpct)),
      adj: pearson(sub.map((r) => r.adj), sub.map((r) => r.netpct)),
      sed: pearson(sedSub.map((r) => r.sed), sedSub.map((r) => r.netpct)),
      stu: pearson(stuSub.map((r) => r.stu), stuSub.map((r) => r.netpct)),
      simstu: (() => {
        const ss = sub.filter((r) => r.simstu != null);
        return pearson(ss.map((r) => r.simstu), ss.map((r) => r.netpct));
      })()
    };
  });
  // shared scatter geometry: x percentile 0-1, y net import % clamped to ±50%
  const PW = 330;
  const PH = 290;
  const PM = { top: 16, right: 10, bottom: 34, left: 46 };
  const YCAP = 0.5;
  const PX = (v) => PM.left + v * (PW - PM.left - PM.right);
  const PY = (v) =>
    PM.top + (1 - (Math.max(-YCAP, Math.min(YCAP, v)) + YCAP) / (2 * YCAP)) * (PH - PM.top - PM.bottom);
  const CALLOUTS = new Set([
    'Acton-Agua Dulce', 'Walnut Valley', 'Compton', 'Inglewood', 'San Marino'
  ]);
  let perfHover = $state(null);
  // district-page links: name -> /district/{cds} via the exported flows rows
  let dCdsBy = $derived(
    Object.fromEntries(
      (nar?.district_flows ?? [])
        .filter((r) => r.cds)
        .map((r) => [r.name.replace(' Unified', ''), r.cds])
    )
  );
  let dHref = $derived((name) => {
    const key = name.replace('\u2013', '-');
    const hit = Object.keys(dCdsBy).find((k) => k.startsWith(key) || key.startsWith(k));
    return hit ? `/district/${dCdsBy[hit]}` : null;
  });
  const ord = (n) => {
    const t = n % 10, h = n % 100;
    return `${n}${t === 1 && h !== 11 ? 'st' : t === 2 && h !== 12 ? 'nd' : t === 3 && h !== 13 ? 'rd' : 'th'}`;
  };
  let distPerf = $derived((name, key) => {
    const r = (nar?.district_flows ?? []).find((d) => d.name.startsWith(name));
    return r?.perf?.[key] != null ? ord(Math.round(r.perf[key] * 100)) : '…';
  });
  let namedNet = $derived((name) => {
    const r = (nar?.district_flows ?? []).find((d) => d.name.startsWith(name));
    const det = r?.detail?.find(([v]) => v === 2020);
    const m = mOf(2020);
    return det && m != null ? fmtN(det[2] * (1 - m) - det[1]) : '…';
  });

  // ---- Act II: LA County children counted outside the county, per window ----
  let leakSeries = $derived(
    Object.entries(countyBy)
      .map(([y, c]) => {
        const m = mOf(+y);
        return m == null ? null : { y: +y, v: c.public - c.cde + m * c.cde };
      })
      .filter(Boolean)
      .sort((a, b) => a.y - b.y)
  );
  const LW = 680;
  const LH = 230;
  const LM = { top: 16, right: 20, bottom: 34, left: 56 };
  let llo = 0;
  let lhi = $derived(Math.max(...leakSeries.map((p) => p.v)) * 1.12);
  const LX = $derived((y) =>
    LM.left + ((y - 2010) / 13) * (LW - LM.left - LM.right));
  const LY = $derived((v) => LM.top + (1 - v / lhi) * (LH - LM.top - LM.bottom));
  // import-oriented scale for Chart 3: 0 at top band, deficit grows downward
  const LYI = $derived(
    (v) => LM.top + ((3000 - v) / (3000 + lhi)) * (LH - LM.top - LM.bottom)
  );
  let killerRows = $derived.by(() => {
    const m = mOf(2023);
    if (m == null) return [];
    const rows = (nar?.county_flows?.rows ?? [])
      .map((r) => {
        const det = (r.detail ?? []).find(([v]) => v === 2023);
        if (!det) return null;
        const [, a, c] = det;
        const imp = c * (1 - m) - a;
        return { name: r.name, imp, impPct: imp / c, virt: r.virt ?? 0,
                 vshare: (r.virt ?? 0) / c, cde: c };
      })
      .filter(Boolean);
    return rows
      .filter((r) => r.impPct >= 0.04 && r.cde >= 3000)
      .sort((a, b) => b.impPct - a.impPct);
  });
  let killerLA = $derived.by(() => {
    const m = mOf(2023);
    const r = (nar?.county_flows?.rows ?? []).find((c) => c.name === 'Los Angeles');
    const det = r?.detail?.find(([v]) => v === 2023);
    if (!det || m == null) return null;
    const [, a, c] = det;
    const imp = c * (1 - m) - a;
    return { imp, impPct: imp / c, virt: r.virt ?? 0, vshare: (r.virt ?? 0) / c };
  });
  let leakHover = $state(null);
  const TREND_COUNTIES = ['El Dorado', 'Placer', 'Sutter', 'Kern', 'Inyo', 'San Diego'];
  let countyTrends = $derived.by(() => {
    const rows = [];
    for (const nm of TREND_COUNTIES) {
      const r = (nar?.county_flows?.rows ?? []).find((c) => c.name === nm);
      if (!r?.detail) continue;
      const det = Object.fromEntries(r.detail.map(([v, a, c]) => [v, { a, c }]));
      const cell = {};
      for (const y of LEDGER_YEARS) {
        const m = mOf(y);
        cell[y] = det[y] && m != null ? -(det[y].a - det[y].c + m * det[y].c) : null;
      }
      rows.push({ name: nm, cell });
    }
    return rows;
  });

  // ---- Conclusion alluvial: where LAUSD-boundary children are counted ----
  const CWINS = [2011, 2015, 2019, 2023];
  const CCATS = [
    { key: 'trad', label: 'LAUSD traditional', color: '#eb6834' },
    { key: 'aff', label: 'LAUSD affiliated', color: '#f0b28a' },
    { key: 'ind', label: 'LAUSD independent', color: '#1e6b3a' },
    { key: 'phys', label: 'Non-LAUSD physical', color: '#2a78d6' },
    { key: 'virt', label: 'Non-LAUSD virtual', color: '#4a3aa7' },
    { key: 'priv', label: 'Private school', color: '#b5aea1' },
    { key: 'noten', label: 'Not enrolled', color: '#d8d4cc' }
  ];
  let laVirtBy = $derived(
    Object.fromEntries((nar?.la_virtual ?? []).map(([y, v]) => [y, v]))
  );
  let concCols = $derived.by(() => {
    return CWINS.map((w) => {
      const r = distBy[w];
      const c = countyBy[w];
      const m = mOf(w);
      if (!r || !c || m == null || clsMean(w, 'trad') == null) return null;
      const trad = clsMean(w, 'trad') * (1 - m);
      const aff = clsMean(w, 'aff') * (1 - m);
      const ind = clsMean(w, 'ind') * (1 - m);
      const elsewhere = Math.max(r.public - trad - aff - ind, 0);
      const outside = Math.max(c.public - c.cde * (1 - m), 0);
      const share = r.public / c.public;
      const virt = Math.min(elsewhere, share * ((laVirtBy[w] ?? 0) + outside));
      return {
        w,
        total: r.total,
        cells: {
          trad, aff, ind,
          phys: elsewhere - virt, virt,
          priv: r.private, noten: r.not_enrolled
        }
      };
    }).filter(Boolean);
  });
  const AW = 900;
  const AH = 470;
  const AM = { top: 36, right: 200, bottom: 26, left: 200 };
  const AGAP = 3;
  const ACOLW = 16;
  let aScale = $derived.by(() => {
    const maxT = Math.max(...concCols.map((c) => c.total), 1);
    return (AH - AM.top - AM.bottom - AGAP * (CCATS.length - 1)) / maxT;
  });
  const AX = $derived((i) =>
    AM.left + (i / Math.max(concCols.length - 1, 1)) * (AW - AM.left - AM.right) - ACOLW / 2
  );
  // bottom-anchored stacks: column tops step down as the population declines
  let aCols = $derived(
    concCols.map((c, i) => {
      let y = AH - AM.bottom;
      const rects = {};
      for (let k = CCATS.length - 1; k >= 0; k--) {
        const key = CCATS[k].key;
        const h = c.cells[key] * aScale;
        y -= h;
        rects[key] = { y0: y, y1: y + h };
        y -= AGAP;
      }
      return { ...c, x: AX(i), rects, topY: y + AGAP };
    })
  );
  let aHover = $state(null);
  const aRibbon = (a, b, key) => {
    const x0 = a.x + ACOLW;
    const x1 = b.x;
    const mid = (x0 + x1) / 2;
    const r0 = a.rects[key];
    const r1 = b.rects[key];
    return (
      `M${x0},${r0.y0} C${mid},${r0.y0} ${mid},${r1.y0} ${x1},${r1.y0}` +
      `L${x1},${r1.y1} C${mid},${r1.y1} ${mid},${r0.y1} ${x0},${r0.y1}Z`
    );
  };
  // population-change wedge, drawn off the top of the source column
  const aWedge = (a, b) => {
    const d = a.total - b.total;
    if (d <= 0) return null;
    const x0 = a.x + ACOLW;
    const x1 = b.x;
    const mid = (x0 + x1) / 2;
    const h = d * aScale;
    return {
      d,
      path:
        `M${x0},${a.topY} C${mid},${a.topY} ${mid},${b.topY - 14} ${x1},${b.topY - 14}` +
        `C${mid},${b.topY - 14} ${mid},${a.topY + h} ${x0},${a.topY + h}Z`,
      lx: mid,
      ly: (a.topY + b.topY) / 2 - 4
    };
  };

  let schools = $state([]);
  onMount(async () => {
    try {
      schools = await getSchools();
    } catch {
      /* capacity section degrades */
    }
  });

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
  let closureCounts = $derived.by(() => {
    const K12 = new Set([
      'Elementary',
      'Intermediate/Middle/Junior High',
      'High School',
      'Elementary-High Combination'
    ]);
    const out = { charter: 0, campus: 0, other: 0 };
    for (const c of closures) {
      if (c.charter) out.charter++;
      else if (K12.has(c.eil)) out.campus++;
      else out.other++;
    }
    return out;
  });
  const EIL_SHORT = {
    Elementary: 'Elementary',
    'Intermediate/Middle/Junior High': 'Middle',
    'High School': 'High',
    'Elementary-High Combination': 'K-12',
    'Preschool/Early Learning': 'Preschool',
    Adult: 'Adult'
  };

  let residualRows = $derived(
    (flows?.levels?.district ?? [])
      .map(([y, r]) => {
        const m = mOf(y);
        if (m == null) return null;
        return {
          y, pub: r.public, cde: r.cde,
          resid: r.public - r.cde,
          expected: -m * r.cde,
          excess: r.public - r.cde + m * r.cde,
          adjEnr: r.cde * (1 - m)
        };
      })
      .filter(Boolean)
  );

  // prose numbers for the "inside that closed system" paragraph
  let clsWin = $derived((y, k) => ledgerBy[y]?.[k]);
  let lausdExport = $derived((y) => {
    const dd = distBy[y];
    const m = mOf(y);
    return dd && m != null ? dd.public - dd.cde + m * dd.cde : null;
  });
  let otherUniImport = $derived((y) => {
    const l = distNets.lausd;
    if (!l) return null;
    const imp = [...distNets.importers, ...distNets.exporters]
      .filter((r) => r.net[y] != null)
      .reduce((s, r) => s + r.net[y], 0);
    return imp + (distNets.restNet[y] ?? 0);
  });
</script>

<svelte:head>
  <title>LAUSD enrollment — SchoolFactors</title>
  <meta
    name="description"
    content="Where did LAUSD's students go? A three-level accounting — state, county, district — of enrollment vs resident children, ending at virtual charters authorized far from Los Angeles."
  />
</svelte:head>


<h2>A shrinking district</h2>
<p class="byline">August 21, 2026 · by Stephen Sorkin</p>
<p class="statewide-link">
  The accounting developed in this article now covers every California district:
  <a href="/enrollment">statewide enrollment-flow map →</a> ·
  <a href="/enrollment/district/19647330000000">LAUSD's flow page →</a>
</p>

{#if cpts.length > 1}
  <div class="chartwrap">
    <p class="title">Chart 1 · LAUSD attendance area: enrollment in
      LAUSD-authorized schools vs resident children 5–17</p>
    <svg viewBox="0 0 {W} {H}" role="img"
      aria-label="LAUSD-authorized enrollment by school class vs resident children by year"
      onmousemove={heroMove}
      onmouseleave={() => (hover = null)}>
      {#each [0.25, 0.5, 0.75, 1] as t}
        <line x1={M.left} y1={Y(hi * t)} x2={W - M.right} y2={Y(hi * t)} stroke="#e1e0d9" />
        <text x={M.left - 6} y={Y(hi * t) + 4} text-anchor="end" class="tick">
          {fmtN(hi * t)}
        </text>
      {/each}
      {#each bands as b}
        <path d={b.path} fill={b.color} fill-opacity="0.85" stroke="#fcfcfb"
          stroke-width="1" />
      {/each}
      {#if rpts.length > 1}
        <polyline points={rpts.map((p) => `${X(p.year)},${Y(p.v)}`).join(' ')} fill="none"
          stroke="#2a78d6" stroke-width="2" stroke-dasharray="5 4" />
        <polyline points={rpts.map((p) => `${X(p.year)},${Y(p.pub)}`).join(' ')} fill="none"
          stroke="#1baf7a" stroke-width="2" stroke-dasharray="5 4" />
      {/if}
      {#each rpts as p}
        <circle cx={X(p.year)} cy={Y(p.v)}
          r={hover?.year === p.year && hover?.kind === 'res' ? 5 : 3}
          fill={p.survey === 'acs1' ? '#fcfcfb' : '#2a78d6'}
          stroke="#2a78d6" stroke-width="1.5"
          onmouseenter={() => (hover = { year: p.year, kind: 'res', v: p.v, pub: p.pub, survey: p.survey })} />
        <circle cx={X(p.year)} cy={Y(p.pub)}
          r={hover?.year === p.year && hover?.kind === 'res' ? 5 : 3}
          fill={p.survey === 'acs1' ? '#fcfcfb' : '#1baf7a'}
          stroke="#1baf7a" stroke-width="1.5"
          onmouseenter={() => (hover = { year: p.year, kind: 'res', v: p.v, pub: p.pub, survey: p.survey })} />
      {/each}
      {#if sharePts.length > 1}
        <polyline points={sharePts.map((p) => `${X(p.year)},${YR(p.s)}`).join(' ')}
          fill="none" stroke="#52514e" stroke-width="1.8" stroke-dasharray="2 4" />
        {#each [0, 0.25, 0.5, 0.75, 1] as t}
          <text x={W - M.right + 4} y={YR(t) + 4} class="tick">{Math.round(t * 100)}%</text>
        {/each}
      {/if}
      {#if hoverCls}
        <line x1={X(hoverCls.year)} y1={M.top} x2={X(hoverCls.year)} y2={H - M.bottom}
          stroke="#52514e" stroke-dasharray="3 3" />
      {/if}
      {#each cpts as p}
        {#if p.year % 4 === 2}
          <text x={X(p.year)} y={H - 8} text-anchor="middle" class="tick">{p.year}</text>
        {/if}
      {/each}
    </svg>
    <p class="caption">
      {#if hover?.kind === 'res'}
        <b>{hover.survey === 'acs1' ? `ACS ${hover.year} (1-yr)` : `ACS ${hover.year} (5-yr window)`}</b>:
        {fmtN(hover.v)} resident children 5–17, of whom {fmtN(hover.pub)} in
        public school
      {:else if hoverCls}
        <b>{hoverCls.year - 1}–{String(hoverCls.year).slice(2)}</b>:
        {#each [...CLS].reverse() as s}
          <span class="k"><span class="sw" style="background:{s.color}"></span>{s.label}
            {fmtN(hoverCls[s.key])}</span>
        {/each}
        · total {fmtN(hoverCls.total)}
        {#if hoverShare}
          · {Math.round(hoverShare.s * 100)}% of resident children
        {/if}
      {:else}
        {#each [...CLS].reverse() as s}
          <span class="k"><span class="sw" style="background:{s.color}"></span>{s.label}</span>
        {/each}
        <span class="k"><span class="sw" style="background:#2a78d6"></span>Resident
          children 5–17 (ACS 5-yr; open dots = 1-yr estimates, 2005–09)</span>
        <span class="k"><span class="sw" style="background:#1baf7a"></span>… of whom in
          public school (any LEA)</span>
        <span class="k"><span class="dash"></span>Share of resident children in
          LAUSD-authorized schools (right axis)</span>
      {/if}
    </p>
  </div>
{/if}

<p>
  Since the ACS window ending in 2015, the number of children living inside
  LAUSD's attendance area has fallen about
  <b>{resDecline != null ? fmtPct(resDecline) : '…'}</b> — but enrollment in
  LAUSD-authorized schools has fallen
  <b>{enrDeclineWindows != null ? fmtPct(enrDeclineWindows) : '…'}</b>, and in
  LAUSD's traditional schools,
  <b>{clsMean(2015, 'trad') ? fmtPct(clsMean(2023, 'trad') / clsMean(2015, 'trad') - 1) : '…'}</b>.
  This article is an accounting of that difference — as precise as the public
  data allow. (We started SchoolFactors to ground discussions about public
  school performance and enrollment in actual data; the backdrop here is the
  budget crisis LAUSD attributes in part to its marked decline in enrollment,
  from {enr2015 ? fmtN(enr2015) : '…'} in 2015 to
  {enrLatest ? fmtN(enrLatest) : '…'} today.)
</p>
<p>
  This decline can only partly be explained by population shifts. Census data
  shows that resident children inside the LAUSD boundary has fallen only by
  <b>{distBy[2015] ? fmtN(distBy[2015].total - distBy[2023].total) : '…'}
  children = {resDecline != null ? fmtPct(resDecline) : '…'}</b>
  ({distBy[2015] ? `${fmtN(distBy[2015].total)} → ${fmtN(distBy[2023].total)}` : '…'},
  ACS windows ending 2015→2023). On the same measurement windows, enrollment in
  LAUSD-authorized schools fell
  <b>{distBy[2015] ? fmtN(distBy[2015].cde - distBy[2023].cde) : '…'} students =
  {enrDeclineWindows != null ? fmtPct(enrDeclineWindows) : '…'}</b>
  ({distBy[2015] ? `${fmtN(distBy[2015].cde)} → ${fmtN(distBy[2023].cde)}` : '…'}) —
  traditional schools fell
  <b>{clsMean(2015, 'trad') ? fmtN(clsMean(2015, 'trad') - clsMean(2023, 'trad')) : '…'} =
  {clsMean(2015, 'trad') ? fmtPct(clsMean(2023, 'trad') / clsMean(2015, 'trad') - 1) : '…'}</b>
  ({clsMean(2015, 'trad') ? `${fmtN(clsMean(2015, 'trad'))} → ${fmtN(clsMean(2023, 'trad'))}` : '…'})
  and affiliated charters fell
  <b>{clsMean(2015, 'aff') ? fmtN(clsMean(2015, 'aff') - clsMean(2023, 'aff')) : '…'} =
  {clsMean(2015, 'aff') ? fmtPct(clsMean(2023, 'aff') / clsMean(2015, 'aff') - 1) : '…'}</b>
  ({clsMean(2015, 'aff') ? `${fmtN(clsMean(2015, 'aff'))} → ${fmtN(clsMean(2023, 'aff'))}` : '…'}),
  while independent charters <em>grew</em>
  <b>{clsMean(2015, 'ind') ? fmtN(clsMean(2023, 'ind') - clsMean(2015, 'ind')) : '…'} =
  {clsMean(2015, 'ind') ? fmtPct(clsMean(2023, 'ind') / clsMean(2015, 'ind') - 1) : '…'}</b>
  ({clsMean(2015, 'ind') ? `${fmtN(clsMean(2015, 'ind'))} → ${fmtN(clsMean(2023, 'ind'))}` : '…'}).
  That is, enrollment
  in the district, both for traditional schools and LAUSD affiliated charters,
  has fallen much faster than the school-aged population. Held against the
  resident children who attend <em>public</em> school
  ({distBy[2015] ? `${fmtN(distBy[2015].public)} → ${fmtN(distBy[2023].public)}` : '…'}),
  the gap this article chases is already visible: LAUSD-authorized enrollment
  exceeded resident public-school children by
  ~{distBy[2015] ? fmtKk(distBy[2015].cde - distBy[2015].public) : '…'} in the
  2015 window and trailed it by
  ~{distBy[2023] ? fmtKk(distBy[2023].public - distBy[2023].cde) : '…'} in the
  2023 window.
</p>

{#if residence.length > 1 && byClass.length > 1}
  <p class="blocklabel">Matched ACS windows, 2015→2023</p>
  <ul class="deltas">
    <li>Resident children 5–17: <b>{sgn(deltas.children)}</b>
      <span class="yr">ACS {yrs(deltas.children)}</span></li>
    <li>… attending public school: <b>{sgn(deltas.pub)}</b>
      <span class="yr">ACS {yrs(deltas.pub)}</span></li>
    <li>… attending private school: <b>{sgn(deltas.prv)}</b>
      <span class="yr">ACS {yrs(deltas.prv)}</span></li>
    <li>… not enrolled anywhere<sup>1</sup>: <b>{sgn(deltas.not)}</b>
      <span class="yr">ACS {yrs(deltas.not)}</span></li>
    <li>Traditional LAUSD enrollment: <b>{sgn(deltas.trad)}</b>
      <span class="yr">{yrs(deltas.trad)}</span></li>
    <li>Affiliated charter enrollment: <b>{sgn(deltas.aff)}</b>
      <span class="yr">{yrs(deltas.aff)}</span></li>
    <li>Independent charter enrollment: <b>{sgn(deltas.ind)}</b>
      <span class="yr">{yrs(deltas.ind)}</span></li>
  </ul>
  <p class="footnote">
    {#if clsLatest}
      <b class="blocklabel-inline">Current enrollment (2025–26):</b> the
      contraction has continued past the census windows — census-day enrollment
      reached {fmtN(clsLatest[1] + clsLatest[2] + clsLatest[3])} in
      {clsLatest[0] - 1}–{String(clsLatest[0]).slice(2)} (traditional
      {fmtKk(clsLatest[1])}, affiliated {fmtKk(clsLatest[2])}, independent
      {fmtKk(clsLatest[3])}).
    {/if}
    <br /><sup>1</sup> The rise in "not enrolled" is real but small —
    {deltas.not ? `${fmtK1(deltas.not.to - deltas.not.from)} children` : '…'}
    against a {enrDeclineWindows != null && distBy[2015]
      ? fmtK1(distBy[2015].cde - distBy[2023].cde)
      : '…'} decline in LAUSD-authorized enrollment over the same windows — and it
    is a young-child phenomenon, not a dropout story:
    {#if notAges}
      ages 5–9 went {fmtK1(notAges.first['5_9'])} → {fmtK1(notAges.last['5_9'])} and
      10–14 went {fmtK1(notAges.first['10_14'])} → {fmtK1(notAges.last['10_14'])},
      while ages 15–17 were flat ({fmtK1(notAges.first['15_17'])} →
      {fmtK1(notAges.last['15_17'])}, ACS {notAges.y0}→{notAges.y1}) — a pattern
      more consistent with delayed kindergarten entry and homeschooling than with
      teens leaving school.
    {/if}
  </p>
{/if}

<p>
  The rest of this article will explore as precisely as possible an accounting of
  the difference between these two rates.
</p>

<h2>The state is a closed system, and it's stable</h2>
<p>The data we use here are from two different sources:</p>
<ol>
  <li>
    The U.S. Census Bureau and their American Community Survey (ACS) product,
    which tracks with great detail the population, demographics and school-types
    in a rigorous manner centered on where people <em>live</em>.
  </li>
  <li>
    The California Department of Education (CDE), which tracks with great detail
    student enrollment and performance where students are <em>enrolled</em>.
  </li>
</ol>
<p>
  Before any other analysis, we had to make sure that these two measures remain
  consistent within a closed population universe (for any given year). That is,
  we understand that students who live in the LAUSD boundary may attend school
  outside that boundary (say with charters, privates, or inter-district
  attendance). We did this by observing the data over time from both sources and
  found that they remain remarkably consistent: state public school enrollment
  numbers from CDE correspond to ACS public school enrollment numbers for the
  state as a whole over the time period for this investigation.
</p>

{#if stabAll.length > 1}
  <div class="chartwrap">
    <p class="title">Chart 2 · California: enrollment (CDE) vs resident
      public-school children (ACS), per 5-year window</p>
    <svg viewBox="0 0 {SW} {SH}" role="img"
      aria-label="Statewide ACS public-school children vs CDE enrollment by ACS window"
      onmouseleave={() => (stabHover = null)}>
      {#each [0, 0.25, 0.5, 0.75, 1] as f}
        <line x1={SM.left} y1={SY(shi * f)} x2={SW - SM.right} y2={SY(shi * f)}
          stroke="#e1e0d9" />
        <text x={SM.left - 6} y={SY(shi * f) + 4} text-anchor="end" class="tick">
          {(shi * f / 1e6).toFixed(1)}M
        </text>
      {/each}
      <polyline points={stabAll.map((r) => `${SX(r.y)},${SY(r.cde)}`).join(' ')} fill="none"
        stroke="#eb6834" stroke-width="2" />
      <polyline points={stabAll.map((r) => `${SX(r.y)},${SY(r.public)}`).join(' ')} fill="none"
        stroke="#2a78d6" stroke-width="2" />
      <polyline points={stabAll.map((r) => `${SX(r.y)},${SYR(r.frac)}`).join(' ')}
        fill="none" stroke="#52514e" stroke-width="1.8" stroke-dasharray="2 4" />
      {#each [0, 0.25, 0.5, 0.75, 1] as t}
        <text x={SW - SM.right + 4} y={SYR(t) + 4} class="tick">{Math.round(t * 100)}%</text>
      {/each}
      {#each stabAll as r}
        <circle cx={SX(r.y)} cy={SY(r.cde)} r={stabHover === r.y ? 5 : 3} fill="#eb6834"
          onmouseenter={() => (stabHover = r.y)} />
        <circle cx={SX(r.y)} cy={SY(r.public)} r={stabHover === r.y ? 5 : 3} fill="#2a78d6"
          onmouseenter={() => (stabHover = r.y)} />
        {#if r.y % 2 === 1}
          <text x={SX(r.y)} y={SH - 8} text-anchor="middle" class="tick">{r.y}</text>
        {/if}
      {/each}
    </svg>
    <p class="caption">
      {#if stabHover != null}
        {@const r = stabAll.find((s) => s.y === stabHover)}
        <b>Window ending {r.y}</b>: CDE {fmtN(r.cde)} · ACS public 5–17
        {fmtN(r.public)} · residual {fmtPct(r.pct)} · enrollment =
        {(r.frac * 100).toFixed(1)}% of the 5–17 population
      {:else}
        <span class="k"><span class="sw" style="background:#eb6834"></span>CDE statewide
          enrollment (5-yr mean per ACS window)</span>
        <span class="k"><span class="sw" style="background:#2a78d6"></span>ACS resident
          children 5–17 in public school</span>
        <span class="k"><span class="dash"></span>Public school enrollment as a
          fraction of 5–17-year-old population (right axis)</span>
      {/if}
    </p>
  </div>
  <p class="method">
    CDE enrollment runs a steady 4–6% above the census count in every window: the
    offset is mechanical — CDE counts TK and other 4-year-olds and 18-year-old
    seniors that the census 5–17 bins exclude. Its slow drift tracks the TK
    phase-in (2012–15); every comparison below is measured against the
    same-window state offset, so the drift is absorbed.
  </p>
{/if}

<p>
  These two universes did not drift, so we can safely say that the movement has
  been across administrative boundaries within California.
</p>

<p>
  One definition carries the rest of this article. For any geography — a
  district's attendance area, a county, the state — compare the two universes
  after removing the mechanical offset:
</p>
<div class="eqbox">
  <div>enrollment attributed to schools in the geography (CDE)</div>
  <div>− the normal statewide Census/CDE mismatch</div>
  <div>− resident public-school children (ACS)</div>
  <div class="eqresult">= net administrative import</div>
</div>
<p class="method">
  Positive: the geography's schools are counted with more students than its
  resident children can account for (a net importer). Negative: resident
  public-school children exceed the enrollment attributed locally (a net
  exporter). Every table and chart below uses this one orientation. Apparent,
  net accounting — not measured student flows.
</p>

<h2>Act I: movement within LA County</h2>
<p>
  The decline in LAUSD enrollment started in the early 2000s, after the district
  reached a peak enrollment of
  <b>{nar?.peak ? fmtN(nar.peak.enr) : '…'}</b> students in
  {nar?.peak ? `${nar.peak.spring - 1}–${String(nar.peak.spring).slice(2)}` : '…'}
  (our census-day series; LAUSD's own
  <a href="https://media.edlio.net/827d2fb9/7dad8703/ae7ca91e/de3f23eaed524ec192ff2468f1fa3771?_=Enrollment-1-6-2022.pdf">Fingertip
  Facts</a> agree). This invites the first question of whether the county acted
  as a closed system. The answer here is "yes," for the first decade and a half
  of the decline.
</p>
<p>
  No ACS 5-year data exists before the window ending 2010, so the walk-back to
  the peak splits in two. From the peak through 2010, enrollment alone is
  sufficient to see the dynamics. LAUSD and the rest of LA County declined
  nearly in proportion, where LAUSD's share of county enrollment moved only from
  <b>{share(2005) != null ? (share(2005) * 100).toFixed(1) + '%' : '…'}</b> to
  <b>{share(2011) != null ? (share(2011) * 100).toFixed(1) + '%' : '…'}</b>.
  There is little evidence of a large net redistribution between LAUSD and the
  rest of LA County during this early period, and LAUSD's decline tracked the
  school-age population decline (in fact, LAUSD
  gained ~4pp market share of resident children through its peak in 2014–15 —
  see Chart 1's dotted line). From the 2006–2010
  window onward the census side exists, and the residual ledger can be read
  directly: LA County as a whole tracked the state baseline to within about a
  point through the window ending 2019. The county was, to first order, a
  closed system.
</p>
<p>
  Within the apparent stability of LA County's numbers, two fundamental,
  internal shifts occurred. First, under LAUSD's own authorization, seats
  shifted from traditional and affiliated-charter schools
  ({clsWin(2011, 'trad_aff') ? fmtKk(clsWin(2011, 'trad_aff')) : '…'} →
  {clsWin(2020, 'trad_aff') ? fmtKk(clsWin(2020, 'trad_aff')) : '…'}, windows
  ending 2011→2020) to LAUSD-authorized independent charters
  ({clsWin(2011, 'ind') ? fmtKk(clsWin(2011, 'ind')) : '…'} →
  {clsWin(2020, 'ind') ? fmtKk(clsWin(2020, 'ind')) : '…'}). This growth reached
  a peak of ~110k independent-charter students in 2020–21, but has been
  declining since. And across district lines, the LAUSD boundary developed a
  growing apparent enrollment deficit — LAUSD-associated schools increasingly
  enrolled fewer students than the number of public-school children residing
  inside the boundary (a "net exporter" hereafter):
  resident public-school children counted somewhere other than LAUSD-authorized
  schools grew from roughly
  <b>{lausdExport(2011) != null ? fmtKk(lausdExport(2011)) : '…'}</b> to
  <b>{lausdExport(2020) != null ? fmtKk(lausdExport(2020)) : '…'}</b>, while the
  other unified districts of LA County went from importing roughly
  <b>{otherUniImport(2011) != null ? fmtKk(otherUniImport(2011)) : '…'}</b> to
  <b>{otherUniImport(2020) != null ? fmtKk(otherUniImport(2020)) : '…'}</b> more
  students than their own resident public-school children. One side's growing
  surplus of children was the other side's growing surplus of seats. The two
  tables below carry the full ledger.
</p>

{#if ledgerCols.length}
  <h3>Where LA County's seats are, and whose children fill them</h3>
  <div class="tablewrap">
    <table>
      <thead>
        <tr><th>Seats (census-day, 5-yr means)</th>
          {#each ledgerCols as c}<th>{c.y - 4}–{String(c.y).slice(2)} avg</th>{/each}</tr>
      </thead>
      <tbody>
        {#each LEDGER_ROWS as [key, label]}
          <tr>
            <td>{label}</td>
            {#each ledgerCols as c}<td>{fmtN(c[key])}</td>{/each}
          </tr>
        {/each}
        <tr class="sumrow">
          <td>= seats in LA County schools</td>
          {#each ledgerCols as c}<td>{fmtN(c.county)}</td>{/each}
        </tr>
        <tr>
          <td>− TK, 18+ &amp; survey adjustment (state-calibrated)</td>
          {#each ledgerCols as c}<td>{fmtN(c.adj)}</td>{/each}
        </tr>
        <tr class="sumrow">
          <td>= resident children in county seats (est.)</td>
          {#each ledgerCols as c}<td>{fmtN(c.inSeats)}</td>{/each}
        </tr>
        <tr>
          <td>+ net administrative export (counted outside the county)</td>
          {#each ledgerCols as c}<td>{fmtN(c.outside)}</td>{/each}
        </tr>
        <tr class="sumrow">
          <td>= resident public-school children (ACS)</td>
          {#each ledgerCols as c}<td>{fmtN(c.residents)}</td>{/each}
        </tr>
      </tbody>
    </table>
  </div>
  <p class="method">
    Every column sums exactly: county seats, less the mechanical universe
    adjustment (the state's same-window offset applied to county enrollment),
    plus the net counted outside the county, equals the ACS count of resident
    public-school children. Seats are grouped by <em>authorizer</em>: charters
    authorized by a district sit in that district's row; "county office &amp;
    other LEAs" carries LACOE-, SBE-, and other non-district-authorized schools.
    The LAUSD traditional/affiliated vs independent split uses current directory
    charter-funding flags, so early years are approximate.
  </p>

  <h3>Net imports and exports by district</h3>
  <div class="tablewrap">
    <table>
      <thead>
        <tr><th>Unified district</th><th>Type</th>
          {#each LEDGER_YEARS as y}<th>{y - 4}–{String(y).slice(2)} avg</th>{/each}
          <th>2023 seats</th><th>2023 residents</th></tr>
      </thead>
      <tbody>
        {#if distNets.lausd}
          <tr class="grouprow"><td colspan={LEDGER_YEARS.length + 4}>Reference</td></tr>
          <tr>
            <td>LAUSD (boundary, all authorized)</td>
            <td class="typecell" title={mixTitle(distNets.lausd.mix)}>district + charter</td>
            {#each LEDGER_YEARS as y}
              <td>{distNets.lausd.net[y] != null ? fmtN(distNets.lausd.net[y]) : '—'}</td>
            {/each}
            <td>{distNets.lausd.by[2023] ? fmtN(distNets.lausd.by[2023].cde) : '—'}</td>
            <td>{distNets.lausd.by[2023] ? fmtN(distNets.lausd.by[2023].acs) : '—'}</td>
          </tr>
        {/if}
        <tr class="grouprow"><td colspan={LEDGER_YEARS.length + 4}>Largest net importers</td></tr>
        {#each distNets.importers as r}
          <tr>
            <td>{@render dl(r.name)}</td>
            <td class="typecell" title={mixTitle(r.mix)}>
              <span class="typedot" style="background:{LEA_TYPES[r.type].color}"></span>{LEA_TYPES[r.type].label}
            </td>
            {#each LEDGER_YEARS as y}
              <td>{r.net[y] != null ? fmtN(r.net[y]) : '—'}</td>
            {/each}
            <td>{r.by[2023] ? fmtN(r.by[2023].cde) : '—'}</td>
            <td>{r.by[2023] ? fmtN(r.by[2023].acs) : '—'}</td>
          </tr>
        {/each}
        <tr class="grouprow"><td colspan={LEDGER_YEARS.length + 4}>Largest net exporters</td></tr>
        {#each distNets.exporters as r}
          <tr>
            <td>{@render dl(r.name)}</td>
            <td class="typecell" title={mixTitle(r.mix)}>
              <span class="typedot" style="background:{LEA_TYPES[r.type].color}"></span>{LEA_TYPES[r.type].label}
            </td>
            {#each LEDGER_YEARS as y}
              <td>{r.net[y] != null ? fmtN(r.net[y]) : '—'}</td>
            {/each}
            <td>{r.by[2023] ? fmtN(r.by[2023].cde) : '—'}</td>
            <td>{r.by[2023] ? fmtN(r.by[2023].acs) : '—'}</td>
          </tr>
        {/each}
        <tr class="grouprow"><td colspan={LEDGER_YEARS.length + 4}>Everything else</td></tr>
        <tr>
          <td>All other unified districts (net)</td>
          <td></td>
          {#each LEDGER_YEARS as y}
            <td>{distNets.restNet[y] != null ? fmtN(distNets.restNet[y]) : '—'}</td>
          {/each}
          <td colspan="2"></td>
        </tr>
      </tbody>
    </table>
  </div>
  <p class="method">
    Cells are net imported enrollments in children: seats (5-yr mean), less the
    state-calibrated universe adjustment, minus the district's own resident
    public-school children — positive = more students counted than resident
    children (net importer), negative = the reverse. Sorted by the window ending
    2020, the close of the within-county era. Unified districts only;
    elementary/high-school district areas and county-office LEAs appear in the
    county ledger above. Apparent, net accounting — not measured student flows.
  </p>
{/if}

{#snippet dl(name)}{#if dHref(name)}<a href={dHref(name)}>{name}</a>{:else}{name}{/if}{/snippet}

{#snippet perfPlot(title, xkey, fit)}
  <div class="wrap">
    <p class="title">{title}</p>
    <svg viewBox="0 0 {PW} {PH}" role="img" aria-label={title}
      onmouseleave={() => (perfHover = null)}>
      {#each [-0.5, -0.25, 0, 0.25, 0.5] as t}
        <line x1={PM.left} y1={PY(t)} x2={PW - PM.right} y2={PY(t)}
          stroke={t === 0 ? '#c9c4ba' : '#e8e6e0'} />
        <text x={PM.left - 5} y={PY(t) + 3.5} text-anchor="end" class="tick">
          {t > 0 ? '+' : ''}{Math.round(t * 100)}%
        </text>
      {/each}
      {#each [0, 0.25, 0.5, 0.75, 1] as t}
        <text x={PX(t)} y={PH - 10} text-anchor="middle" class="tick">
          {Math.round(t * 100)}
        </text>
      {/each}
      <line x1={PX(0)} y1={PY(fit.icpt)} x2={PX(1)} y2={PY(fit.icpt + fit.slope)}
        stroke="#898781" stroke-dasharray="4 4" />
      {#each perfScatter.sub.filter((q) => q[xkey] != null) as d}
        {#if d.type === 'charter'}
          <rect x={PX(d[xkey]) - (perfHover?.name === d.name ? 5.2 : 3.8)}
            y={PY(d.netpct) - (perfHover?.name === d.name ? 5.2 : 3.8)}
            width={perfHover?.name === d.name ? 10.4 : 7.6}
            height={perfHover?.name === d.name ? 10.4 : 7.6}
            fill={LEA_TYPES.charter.color}
            fill-opacity={perfHover?.name === d.name ? 1 : 0.8}
            stroke={perfHover?.name === d.name ? '#2b2722' : '#fcfcfb'} stroke-width="1.5"
            onmouseenter={() => (perfHover = d)}>
            <title>{d.name}: {fmtPct(d.netpct)} net imports, {Math.round(d[xkey] * 100)}th pctile</title>
          </rect>
        {:else if d.type === 'virtual'}
          {@const th = perfHover?.name === d.name ? 1.4 : 1}
          <path d="M {PX(d[xkey])} {PY(d.netpct) - 5 * th} L {PX(d[xkey]) + 4.6 * th} {PY(d.netpct) + 3.6 * th} L {PX(d[xkey]) - 4.6 * th} {PY(d.netpct) + 3.6 * th} Z"
            fill={LEA_TYPES.virtual.color}
            fill-opacity={perfHover?.name === d.name ? 1 : 0.85}
            stroke={perfHover?.name === d.name ? '#2b2722' : '#fcfcfb'} stroke-width="1.5"
            onmouseenter={() => (perfHover = d)}>
            <title>{d.name}: {fmtPct(d.netpct)} net imports, {Math.round(d[xkey] * 100)}th pctile</title>
          </path>
        {:else}
          <circle cx={PX(d[xkey])} cy={PY(d.netpct)}
            r={perfHover?.name === d.name ? 5.6 : 4} fill={LEA_TYPES.district.color}
            fill-opacity={perfHover?.name === d.name ? 1 : 0.75}
            stroke={perfHover?.name === d.name ? '#2b2722' : '#fcfcfb'} stroke-width="1.5"
            onmouseenter={() => (perfHover = d)}>
            <title>{d.name}: {fmtPct(d.netpct)} net imports, {Math.round(d[xkey] * 100)}th pctile</title>
          </circle>
        {/if}
        {#if CALLOUTS.has(d.name)}
          <text x={PX(d[xkey]) + (d[xkey] > 0.7 ? -7 : 7)}
            y={PY(d.netpct) + (d.netpct > YCAP ? 13 : 3.5)}
            text-anchor={d[xkey] > 0.7 ? 'end' : 'start'}
            class="ptlabel">{d.name}{d.netpct > YCAP ? ` (${fmtPct(d.netpct, 0)})` : ''}</text>
        {/if}
      {/each}
      {#if perfScatter.lausd && perfScatter.lausd[xkey] != null}
        <rect x={PX(perfScatter.lausd[xkey]) - 4.5} y={PY(perfScatter.lausd.netpct) - 4.5}
          width="9" height="9" transform="rotate(45 {PX(perfScatter.lausd[xkey])} {PY(perfScatter.lausd.netpct)})"
          fill="#eb6834" onmouseenter={() => (perfHover = perfScatter.lausd)} />
        <text x={PX(perfScatter.lausd[xkey]) + 7} y={PY(perfScatter.lausd.netpct) + 3.5}
          class="ptlabel">LAUSD</text>
      {/if}
      <text x={(PM.left + PW - PM.right) / 2} y={PH - 24} text-anchor="middle"
        class="tick">r = {fit.r.toFixed(2)}</text>
    </svg>
  </div>
{/snippet}

<h3>Who absorbed enrollment within LA County?</h3>
<p>
  Conventional importers tended to be relatively affluent, high-raw-scoring
  districts such as {@render dl('Walnut Valley')}, {@render dl('San Marino')}, {@render dl('Torrance')} and {@render dl('Culver City')} — but
  import growth was <em>not</em> correlated with SchoolFactors'
  demographic-adjusted performance measure. Other large importers were charter
  authorizers, including virtual-heavy {@render dl('Acton-Agua Dulce')} and {@render dl('West Covina')}. The
  full performance and demographic detail is in the
  <a href="#appendix">appendix</a>.
</p>

<h2>Act II: enrollment leaves the county — on paper</h2>

<p>
  The neighboring districts stop explaining the gap. By 2023, the rest of LA
  County has returned roughly to California's normal Census/CDE relationship —
  but LAUSD has not. On net, the missing administrative enrollment has to
  appear beyond those neighboring districts.
</p>
<p>
  And LA County itself stops balancing. After the state-calibrated adjustment,
  LA County has roughly <b>{countyLeak != null ? fmtN(countyLeak) : '…'}</b>
  more resident public-school children than enrollment attributed to schools in
  the county — a net administrative import of
  <b>{countyLeak != null && countyBy[2023] ? fmtPct(-countyLeak / countyBy[2023].cde) : '…'}</b>
  of county enrollment, past any earlier point in the data. The children need
  not have moved. Increasingly, the administrative geography of their
  enrollment appears to have.
</p>

{#if leakSeries.length > 2}
  <div class="chartwrap">
    <p class="title">Chart 3 · LA County net administrative import, per 5-year
      window</p>
    <svg viewBox="0 0 {LW} {LH}" role="img"
      aria-label="LA County net administrative import by ACS window"
      onmouseleave={() => (leakHover = null)}>
      {#each [0, -10000, -20000, -30000, -40000] as t}
        <line x1={LM.left} y1={LYI(t)} x2={LW - LM.right} y2={LYI(t)}
          stroke={t === 0 ? '#c9c4ba' : '#e1e0d9'} />
        <text x={LM.left - 6} y={LYI(t) + 4} text-anchor="end" class="tick">
          {t / 1000}k</text>
      {/each}
      <polyline points={leakSeries.map((p) => `${LX(p.y)},${LYI(-p.v)}`).join(' ')}
        fill="none" stroke="#4a3aa7" stroke-width="2" />
      {#each leakSeries as p}
        <circle cx={LX(p.y)} cy={LYI(-p.v)} r={leakHover === p.y ? 5 : 3}
          fill="#4a3aa7" onmouseenter={() => (leakHover = p.y)} />
        {#if p.y % 2 === 1}
          <text x={LX(p.y)} y={LH - 8} text-anchor="middle" class="tick">{p.y}</text>
        {/if}
      {/each}
    </svg>
    <p class="caption">
      {#if leakHover != null}
        {@const p = leakSeries.find((q) => q.y === leakHover)}
        <b>Window ending {p.y}</b>: net administrative import of
        {fmtN(-p.v)} — roughly {fmtN(p.v)} county-resident public-school
        children beyond the enrollment attributed to LA County schools
      {:else}
        The closed system, in one line: the county's balance approaches zero
        through the mid-2010s, then dives after 2019 to a deficit well beyond
        where the decade began.
      {/if}
    </p>
    <p class="refrain">Apparent, net accounting — not measured student flows.</p>
  </div>

  {#if countyTrends.length}
    <div class="tablewrap">
      <table>
        <thead>
          <tr><th>Net administrative import (children)</th>
            {#each LEDGER_YEARS as y}<th>{y - 4}–{String(y).slice(2)} avg</th>{/each}</tr>
        </thead>
        <tbody>
          <tr class="grouprow"><td colspan={LEDGER_YEARS.length + 1}>Net exporter</td></tr>
          <tr>
            <td>Los Angeles County</td>
            {#each LEDGER_YEARS as y}
              {@const p = leakSeries.find((q) => q.y === y)}
              <td>{p ? fmtN(-p.v) : '—'}</td>
            {/each}
          </tr>
          <tr class="grouprow"><td colspan={LEDGER_YEARS.length + 1}>Net importers</td></tr>
          {#each countyTrends as r}
            <tr>
              <td>{r.name}</td>
              {#each LEDGER_YEARS as y}
                <td>{r.cell[y] != null ? fmtN(r.cell[y]) : '—'}</td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <p class="method">
      The same definition, applied county by county. El Dorado and Kern swing
      to major importers exactly on the 2019-and-later timeline; Placer's
      import is long-standing and predates Act II; San Diego mixes mechanisms.
      Apparent, net accounting — these rows are counterparties in aggregate,
      not measured LA-to-X flows.
    </p>
  {/if}
{/if}

<p>
  Where does California show the opposite pattern? Statewide enrollment at
  charter schools flagged fully or primarily virtual grew
  <b>{virtual.length ? `${fmtKk(virtual[0][1])} (${virtual[0][0]})` : '…'}</b> →
  <b>{virtual.length ? `${fmtKk(virtual[virtual.length - 1][1])} (${virtual[virtual.length - 1][0]})` : '…'}</b>,
  and the counties with extraordinary administrative imports are
  disproportionately those where enrollment can be geographically decoupled
  from physical attendance:
</p>

{#if killerRows.length}
  <div class="tablewrap">
    <table>
      <thead>
        <tr><th>County</th><th>Net administrative import</th><th>as % of enrollment</th>
          <th>Flagged-virtual charter enrollment</th><th>Virtual share of enrollment</th></tr>
      </thead>
      <tbody>
        {#each killerRows as r}
          <tr>
            <td>{r.name}</td><td>{fmtN(r.imp)}</td><td>{fmtPct(r.impPct)}</td>
            <td>{fmtN(r.virt)}</td><td>{(r.vshare * 100).toFixed(1)}%</td>
          </tr>
        {/each}
        {#if killerLA}
          <tr class="grouprow"><td colspan="5">For contrast</td></tr>
          <tr>
            <td>Los Angeles</td><td>{fmtN(killerLA.imp)}</td><td>{fmtPct(killerLA.impPct)}</td>
            <td>{fmtN(killerLA.virt)}</td><td>{(killerLA.vshare * 100).toFixed(1)}%</td>
          </tr>
        {/if}
      </tbody>
    </table>
  </div>
  <p class="method">
    Counties with net administrative imports of at least +4% of enrollment
    (window ending 2023, enrollment ≥ 3,000). Across all 58 counties, the
    import rate and the flagged-virtual share correlate at
    <b>0.62 enrollment-weighted</b> (0.20 unweighted — small counties are
    noisy). The directory's virtual flag is a <em>lower bound</em> on
    nonclassroom-based enrollment: Inyo's import runs through YouthBuild
    Charter School of California and Placer's through Horizon Charter and the
    John Adams Academies — independent-study networks the flag does not mark.
    Apparent, net accounting — not measured student flows.
  </p>
{/if}

<p>
  Meanwhile the channels one might guess first turn out to be small: non-LAUSD
  charter campuses physically inside the LAUSD boundary hold only
  <b>{insideLatest ? `~${fmtKk(insideLatest[1])}` : '…'}</b> students.
</p>

<h2>Conclusion: the same children, counted somewhere else</h2>
<p>
  The whole story can be seen clearly in Chart 4. Over time, population decline
  shrinks the pie as a whole by
  {aCols.length >= 4 ? fmtKk(aCols[0].total - aCols[3].total) : '…'} students —
  but market share also moves from LAUSD-affiliated schools (traditional and
  affiliated charter) to alternatives: (1) independent charters authorized by
  LAUSD, an increase of
  {aCols.length >= 4 ? fmtKk(aCols[3].cells.ind - aCols[0].cells.ind) : '…'}
  students; (2) other classroom-based schools, both charter and district-run,
  an increase of
  {aCols.length >= 4 ? fmtKk(aCols[3].cells.phys - aCols[0].cells.phys) : '…'}
  students; and (3) virtual charters, an increase of
  {aCols.length >= 4 ? fmtKk(aCols[3].cells.virt - aCols[0].cells.virt) : '…'}
  students. Essentially all of the increase in LAUSD-authorized independent
  charters occurred in the first two periods. The shift of LAUSD students to
  other in-county physical schools
  ({aCols.length >= 4 ? fmtKk(aCols[2].cells.phys - aCols[1].cells.phys) : '…'}
  students, roughly a doubling) was the hallmark of the second period — Act I.
  That move reads as a flight toward measured quality: districts scoring lower
  on both raw tests and the per-student Similar Student measure lost students
  to districts scoring higher on both. Only in the most recent period did
  virtual enrollment surge while every other destination stayed flat or fell —
  Act II. We can only presume this is a flight of convenience rather than of
  measured quality: the virtual schools are largely not high-performing on
  either measure.
</p>

{#if aCols.length >= 4}
  <div class="chartwrap">
    <p class="title">Chart 4 · Where the LAUSD attendance area's children are
      counted, by 5-year window</p>
    <svg class="wide" viewBox="0 0 {AW} {AH}" role="img"
      aria-label="Where LAUSD-area resident children are counted, four windows"
      onmouseleave={() => (aHover = null)}>
      {#each aCols.slice(0, -1) as a, i}
        {@const b = aCols[i + 1]}
        {#each CCATS as cat}
          <path d={aRibbon(a, b, cat.key)} fill={cat.color}
            fill-opacity={aHover && aHover.key === cat.key ? 0.45 : 0.22}
            onmouseenter={() => (aHover = { key: cat.key, w: a.w })} />
        {/each}
        {#if aWedge(a, b)}
          {@const wdg = aWedge(a, b)}
          <path d={wdg.path} fill="#c9c4ba" fill-opacity="0.55" />
          <text x={wdg.lx} y={wdg.ly} text-anchor="middle" class="tick">
            population decline −{fmtKk(wdg.d)}</text>
        {/if}
      {/each}
      {#each aCols as c, i}
        {#each CCATS as cat}
          {@const r = c.rects[cat.key]}
          <rect x={c.x} y={r.y0} width={ACOLW} height={Math.max(r.y1 - r.y0, 1)}
            rx="2" fill={cat.color}
            onmouseenter={() => (aHover = { key: cat.key, w: c.w })} />
          {#if i === 0}
            <text x={c.x - 7} y={(r.y0 + r.y1) / 2 + 3.5} text-anchor="end"
              class="nlabel"><tspan class="nname">{cat.label}</tspan>
              <tspan class="nval">&#8201;{fmtKk(c.cells[cat.key])}</tspan></text>
          {:else if i === aCols.length - 1}
            <text x={c.x + ACOLW + 7} y={(r.y0 + r.y1) / 2 + 3.5}
              class="nlabel"><tspan class="nname">{cat.label}</tspan>
              <tspan class="nval">&#8201;{fmtKk(c.cells[cat.key])}</tspan></text>
          {/if}
        {/each}
        <text x={c.x + ACOLW / 2} y={c.topY - 8} text-anchor="middle" class="tick">
          {fmtKk(c.total)}</text>
        <text x={c.x + ACOLW / 2} y={AH - 8} text-anchor="middle" class="tick">
          {c.w - 4}–{String(c.w).slice(2)}</text>
      {/each}
    </svg>
    <p class="caption">
      {#if aHover}
        {@const cat = CCATS.find((k) => k.key === aHover.key)}
        <b>{cat.label}</b>:
        {#each aCols as c, i}{i ? ' → ' : ''}{fmtN(c.cells[aHover.key])}{/each}
        (windows {aCols[0].w}→{aCols[aCols.length - 1].w})
      {:else}
        Hover a band for its four-window series. Columns are bottom-anchored, so
        the stepping tops are the shrinking child population.
      {/if}
    </p>
    <p class="refrain">Apparent, net accounting — not measured student flows.</p>
  </div>

  <div class="tablewrap">
    <table>
      <thead>
        <tr><th>Children (5-yr window means)</th>
          {#each aCols as c}<th>{c.w - 4}–{String(c.w).slice(2)}</th>{/each}</tr>
      </thead>
      <tbody>
        {#each CCATS as cat}
          <tr>
            <td><span class="typedot" style="background:{cat.color}"></span>{cat.label}</td>
            {#each aCols as c}<td>{fmtN(c.cells[cat.key])}</td>{/each}
          </tr>
        {/each}
        <tr class="sumrow">
          <td>= resident children 5–17</td>
          {#each aCols as c}<td>{fmtN(c.total)}</td>{/each}
        </tr>
      </tbody>
    </table>
  </div>
  <p class="method">
    Assumptions, in the open: (1) LAUSD-sector seats are converted to resident
    children with the statewide Census/CDE adjustment and treated as boundary
    residents on net. (2) The non-LAUSD split is estimated: the virtual band is
    the boundary's population share of LA County's flagged-virtual charter
    enrollment plus the county's net administrative export (which Act II ties
    to virtual/independent-study counties); the physical band is the remainder
    — permits into other districts and brick-and-mortar charters
    ("Non-LAUSD physical"). The virtual
    flag is a lower bound on nonclassroom-based enrollment, so the virtual band
    is conservative. (3) Population decline is drawn off the top; in a growth
    period it would enter as an inflow. Apparent, net accounting — not measured
    student flows.
  </p>
{/if}


<p class="method">
  Method caveats: every cross-boundary number on this page is an apparent,
  <em>net</em> accounting residual, not a measured student flow — CALPADS
  inter-district transfer data would be the student-level check. The windows
  ending 2020–2021 lean on pandemic-weakened ACS collection, and the 2005–09
  resident points are single-year estimates, both noisier than the 5-year
  windows. The virtual-school flag is present-day, so early years of that series
  are approximate.
</p>

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
  The state directory records {closures.length || '…'} LAUSD closures since 2015,
  but they're not one thing: <b>{closureCounts.campus} district-operated K–12
  campuses</b> actually ceased operation, {closureCounts.charter} were charters
  (whose closures reflect authorization and finances as much as enrollment), and
  {closureCounts.other} were adult, preschool, special-education, or
  program/administrative entries. Schools with a page link to their full history;
  "last enrollment" is the most recent census count on record before closure.
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


<h2 id="appendix">Appendix: who gained, who lost — and how they score</h2>
{#if perfScatter?.sub?.length}
  <p>
    The obvious question to ask here is how parents choose the schools to send
    their children, since there was a clear flight from attendance-area
    schools. For traditional school destinations, the answer is a clear yes,
    with high-scoring districts like {@render dl('Walnut Valley')} and {@render dl('San Marino')} becoming net
    importers of students: {@render dl('Walnut Valley')} — {distPerf('Walnut Valley', 'raw')}
    percentile on raw scores in 2016–19 — absorbed a net
    {namedNet('Walnut Valley')} students by the 2020 window (over a third of
    its enrollment), and {@render dl('San Marino')} — {distPerf('San Marino', 'raw')}
    percentile — a net {namedNet('San Marino')}, more than a quarter of its
    enrollment. {@render dl('Torrance')}, {@render dl('Culver City')}, and {@render dl('Alhambra')} fit the same shape at the
    85th-plus percentiles.
  </p>
  <p>
    However, readers who have explored our methodology will note that raw test
    scores say a lot more about the demographic blend at a school and district.
    Normalizing scores paints a different picture. {@render dl('San Marino')} is only a
    {distPerf('San Marino', 'adj17')}-percentile district after normalizing
    for the demographics of its student population, and {@render dl('Walnut Valley')} is a
    {distPerf('Walnut Valley', 'adj17')}-percentile district.
  </p>
  <p>
    A third number completes the vocabulary. The <em>Expected Student
    percentile</em> asks: where would a district serving students like these be
    expected to score statewide, before knowing anything about its performance
    relative to expectation? Expected + residual = observed, so the three
    percentiles decompose one another. {@render dl('Walnut Valley')}'s students
    would be expected to score near the top of the state on composition alone
    ({distPerf('Walnut Valley', 'stu')} percentile expected); its raw scores do
    ({distPerf('Walnut Valley', 'raw')}); relative to districts serving
    similarly advantaged students, its performance is much less exceptional
    ({distPerf('Walnut Valley', 'adj17')}). {@render dl('San Marino')} reads
    the same way ({distPerf('San Marino', 'stu')} expected /
    {distPerf('San Marino', 'raw')} actual /
    {distPerf('San Marino', 'adj17')} vs similar). The exporters run the
    reverse pattern: {@render dl('Inglewood')} and {@render dl('Compton')}
    serve students whose expected levels sit low, score about where expected or
    above, and rank near the top once composition is accounted for.
  </p>
  <p>
    Net exporters tended to be uniformly low-performing by raw numbers, though
    paradoxically quite high-performing given their demographic blend. This can
    be seen in the charts below. The exporting districts were, at the time,
    almost uniformly high on the adjusted measure ({@render dl('Inglewood')}, {@render dl('Compton')}, {@render dl('Bassett')},
    {@render dl('Bellflower')}, {@render dl('Monrovia')} all above the 89th percentile), while the importers
    varied from low to high adjusted scores, fairly uniformly. And the timing
    adds a caution against reading preference into either panel: the
    <em>growth</em> of imports between 2016 and 2020 is uncorrelated with
    performance on either measure (r ≈ 0). The flows are correlated with
    district composition, not with measured value-add — and the largest
    importer of all, {@render dl('Acton-Agua Dulce')}, ranks near the bottom of the adjusted
    distribution as its virtual-charter enrollment dominates its tested
    population.
  </p>
  <p>
    The importers are also not one kind of LEA. Most import into their own
    district-run schools — the permit pattern ({@render dl('Walnut Valley')}, ABC, {@render dl('Torrance')},
    {@render dl('Culver City')}, {@render dl('Alhambra')}). A second kind is a <em>charter umbrella</em>: the
    seats sit in brick-and-mortar charters the district authorizes rather than
    in its own schools (Duarte's California School of the Arts, Wiseburn's
    Da Vinci schools). A third is virtual-heavy: Acton–Agua Dulce's imports run
    through the iLEAD/Compass network — roughly half of its charter seats are
    fully-virtual schools — and West Covina's largest import is California
    Virtual Academy @ Los Angeles outright. The second act was already running
    inside the county during the first.
  </p>
  <div class="trio">
    {@render perfPlot('Chart 5 · Net imports vs Similar Student percentile (as of 2017)', 'simstu', perfScatter.simstu)}
    {@render perfPlot('Chart 6 · Net imports vs raw score percentile (2016–19)', 'raw', perfScatter.raw)}
    {@render perfPlot('Chart 7 · Net imports vs Similar Schools percentile (as of 2017)', 'adj', perfScatter.adj)}
  </div>
  <p class="caption">
    {#if perfHover}
      <b>{perfHover.name}</b> — net imports {fmtPct(perfHover.netpct)} of
      enrollment · raw {Math.round(perfHover.raw * 100)}th pctile · adjusted
      {Math.round(perfHover.adj * 100)}th pctile{#if perfHover.stu != null}
        · expected {Math.round(perfHover.stu * 100)}th pctile{/if}{#if perfHover.simstu != null}
        · similar-student {Math.round(perfHover.simstu * 100)}th pctile (2017){/if} ·
      {LEA_TYPES[perfHover.type].long.toLowerCase()}
    {:else}
      Hover a mark for the district's name and values.
    {/if}
  </p>
  <p class="method">
    Each mark is an LA County unified district, shaped and colored by LEA type —
    <span class="k"><span class="typedot" style="background:#2a78d6"></span>district-run
    seats (circle)</span>
    <span class="k"><span class="typedot" style="background:#008300"></span>brick-and-mortar
    charter authorizer (square)</span>
    <span class="k"><span class="typedot" style="background:#4a3aa7"></span>virtual-heavy
    authorizer (triangle)</span> — with LAUSD as the orange diamond, excluded
    from the fit and correlations. Chart 5's horizontal axis is the Similar
    Student percentile contemporaneous to the era — for a fixed student
    profile, where expected performance at the district ranked statewide, refit
    on data through 2017 with era-restricted composition effects.
    Vertical axis: net imported
    enrollments as a share of the district's enrollment, window ending 2020,
    clamped at ±50% (Acton–Agua Dulce's actual value is labeled). Horizontal:
    left — percentile of mean scale score (All Students, grades 3–8 &amp; 11,
    ELA + Math) among all CA unified districts, 2016–19; right — percentile of
    the demographically-adjusted level from the out-of-sample refit through
    2017. Dashed lines are least-squares fits. Correlations, not student-level
    choice measures.
  </p>
{/if}


<style>
  .draftnote {
    background: #fdf3d7;
    border: 1px solid #e8d59a;
    border-radius: 8px;
    padding: 0.5rem 0.8rem;
    font-size: 0.85rem;
    color: #52514e;
  }
  .byline {
    font-size: 0.85rem;
    color: #8f8a80;
    margin: -0.4rem 0 1rem;
  }
  .stub {
    color: #8a6d1f;
    font-size: 0.85rem;
    font-style: italic;
  }
  .chartwrap {
    overflow-x: auto;
  }
  svg.wide {
    max-width: 1020px;
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
  .dash {
    width: 16px;
    border-top: 2px dashed #52514e;
    display: inline-block;
  }
  .wrap {
    min-width: 0;
  }
  .duo {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1rem;
    max-width: 760px;
  }
  .trio {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.8rem;
    max-width: 1020px;
  }
  @media (max-width: 900px) {
    .trio {
      grid-template-columns: 1fr;
      max-width: 520px;
    }
  }
  @media (max-width: 900px) {
    .duo {
      grid-template-columns: 1fr;
    }
  }
  .title {
    font-size: 0.9rem;
    font-weight: 600;
    color: #2b2722;
    margin: 0 0 0.25rem;
  }
  .ptlabel {
    font-size: 10px;
    fill: #52514e;
  }
  .typecell {
    text-align: left;
    font-size: 0.78rem;
    color: #6f6a61;
    white-space: nowrap;
  }
  .typedot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 0.3rem;
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
  .sumrow td {
    font-weight: 600;
    border-top: 1.5px solid #d8d0c2;
  }
  .grouprow td {
    font-weight: 600;
    color: #6f6a61;
    font-size: 0.8rem;
    text-align: left;
    padding-top: 0.6rem;
  }
  .tablewrap {
    overflow-x: auto;
  }
  .deltas {
    columns: 2;
    font-size: 0.9rem;
    margin: 0.8rem 0 0.3rem;
  }
  @media (max-width: 640px) {
    .deltas {
      columns: 1;
    }
  }
  .yr {
    color: #8f8a80;
    font-size: 0.78rem;
    white-space: nowrap;
  }
  .blocklabel {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: #8f8a80;
    margin: 0.7rem 0 0.1rem;
  }
  .blocklabel-inline {
    color: #6f6a61;
  }
  .footnote {
    font-size: 0.8rem;
    color: #6f6a61;
    margin: 0.4rem 0 1rem;
  }
  .method {
    font-size: 0.85rem;
    color: #6f6a61;
  }
  .refrain {
    font-size: 0.78rem;
    font-style: italic;
    color: #8f8a80;
    margin: 0.1rem 0 0.8rem;
  }
  .eqbox {
    background: #faf7f2;
    border: 1px solid #e8e1d5;
    border-radius: 8px;
    padding: 0.7rem 1rem;
    font-size: 0.92rem;
    color: #2b2722;
    max-width: 560px;
  }
  .eqbox .eqresult {
    font-weight: 600;
    border-top: 1px solid #d8d0c2;
    margin-top: 0.3rem;
    padding-top: 0.3rem;
  }
  .pending {
    color: #6f6a61;
    font-size: 0.88rem;
  }
</style>
