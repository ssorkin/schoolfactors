// Choropleth metric registry for the statewide enrollment-flow map, following the
// district/choropleth.js shape. Rows are enrollment index rows (lib/enrollment/
// data.js). Sign convention everywhere: POSITIVE = NET IMPORTER, drawn toward the
// blue pole of the validated diverging ramp (rust = exporter), matching the site's
// established "positive = importer" convention.
//
// MOE gate: ACS-derived diverging metrics gray out districts whose margin exceeds
// MOE_GATE — a small district's ±20pp estimate is noise, and coloring it would
// invite reading it. Gated rows keep their values in popups, labeled "est.".

import { pctColor, pctGradient } from '$lib/maptypes.js';
import { NO_DATA, seqColor, seqGradient, ordinal } from '$lib/district/choropleth.js';

export { NO_DATA };

export const MOE_GATE = 0.15; // net-rate margin (fraction of resident children)

// School-class colors for detail-map markers. Distinct job from maptypes
// TYPE_COLOR (admission type): this encodes the flow model's seat classes.
export const CLASS_COLOR = {
  district_run: '#1c5cab',
  charter_aff: '#7aa5d8',
  charter_bm: '#d18a58',
  charter_virtual: '#4a3aa7'
};
export const CLASS_LABEL = {
  district_run: 'district-run',
  charter_aff: 'affiliated charter (locally funded)',
  charter_bm: 'charter (brick & mortar)',
  charter_virtual: 'virtual charter (import-only pool)'
};

const SAT = 0.25; // net rate that saturates the diverging ramp (±25pp)
const divergeColor = (v) =>
  v == null ? NO_DATA : pctColor(50 + Math.max(-49, Math.min(49, (v / SAT) * 49)));
const signedPct = (v) =>
  v == null ? 'no data' : `${v > 0 ? '+' : ''}${(v * 100).toFixed(1)}%`;
const pct = (v) => (v == null ? 'no data' : `${Math.round(v * 100)}%`);

const gated = (row) => row.net_moe != null && row.net_moe > MOE_GATE;

export const FLOW_METRICS = {
  net_import: {
    label: 'Net enrollment import rate (modeled)',
    short: 'Net import rate',
    legend: 'diverging',
    gradient: pctGradient,
    ends: ['net exporter −25%', 'net importer +25%'],
    // yearIdx -1 = latest published value; otherwise index into the spark series.
    value: (row, yearIdx = -1) =>
      yearIdx >= 0 ? (row.spark?.[yearIdx] ?? null) : (row.net_rate ?? null),
    series: true,
    moeGate: gated,
    color: divergeColor,
    fmt: signedPct
  },
  res_chg: {
    label: 'Resident public-school children, change 2009-13 → latest',
    short: 'Resident change',
    legend: 'diverging',
    gradient: pctGradient,
    ends: ['−25% fewer children', '+25% more children'],
    value: (row) => row.res_chg ?? null,
    moeGate: gated,
    color: divergeColor,
    fmt: signedPct
  },
  seats_chg: {
    label: 'Seats at schools located here, change 2009-13 → latest',
    short: 'Seats change',
    legend: 'diverging',
    gradient: pctGradient,
    ends: ['−25% fewer seats', '+25% more seats'],
    value: (row) => row.seats_chg ?? null,
    color: divergeColor,
    fmt: signedPct
  },
  virt_share: {
    label: 'Virtual & statewide-program enrollment share (est.)',
    short: 'Virtual share',
    legend: 'sequential',
    gradient: seqGradient,
    ends: ['0%', '10%+'],
    domain: 0.1,
    value: (row) => row.virt_share ?? null,
    color(v) {
      return seqColor(v == null ? null : v / this.domain);
    },
    fmt: pct
  },
  perf: {
    label: 'School performance (Similar Student %ile)',
    short: 'Similar Student %ile',
    legend: 'diverging',
    gradient: pctGradient,
    ends: ['lower for similar students', 'higher for similar students'],
    value: (row) => row.perf ?? null,
    color: (v) => pctColor(v),
    fmt: (v) =>
      v == null ? 'no data' : `${ordinal(v)} %ile vs schools serving similar students`
  }
};
