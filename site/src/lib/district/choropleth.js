// Choropleth metric registry for district attendance-area maps.
//
// Two color jobs, per the dataviz rules: performance is DIVERGING (rust = below
// typical for similar students, gray = typical, blue = above — reuses the validated
// PCT_STOPS ramp from maptypes.js), demographic shares are SEQUENTIAL (one hue,
// light → dark rust, monotone lightness). Gray = no data / no attendance area.

import { pctColor, pctGradient, NO_PCT_COLOR } from '$lib/maptypes.js';

export const NO_DATA = NO_PCT_COLOR;

// Single-hue rust ramp (light → dark), stops share the brand rust hue.
const SEQ_STOPS = ['#f8ece1', '#e8bd9a', '#d18a58', '#ad5423', '#7c2d12'];

const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));

export function seqColor(t) {
  if (t == null || Number.isNaN(t)) return NO_DATA;
  const x = Math.min(1, Math.max(0, t)) * (SEQ_STOPS.length - 1);
  const i = Math.min(SEQ_STOPS.length - 2, Math.floor(x));
  const f = x - i;
  const a = rgb(SEQ_STOPS[i]);
  const b = rgb(SEQ_STOPS[i + 1]);
  return `rgb(${a.map((v, k) => Math.round(v + (b[k] - v) * f)).join(',')})`;
}

export function seqGradient() {
  return `linear-gradient(90deg, ${SEQ_STOPS.join(', ')})`;
}

const pctile = (v) => {
  if (v == null) return 'no data';
  const n = Math.round(v);
  const suf = n % 10 === 1 && n !== 11 ? 'st' : n % 10 === 2 && n !== 12 ? 'nd'
    : n % 10 === 3 && n !== 13 ? 'rd' : 'th';
  return `${n}${suf} %ile vs schools serving similar students`;
};
const pct = (v) => (v == null ? 'no data' : `${Math.round(v * 100)}%`);

// Each metric: where the value comes from (polygon properties + the joined school
// row), how to color it, and how the legend reads. Demographic metrics appear only
// once census block-group data is exported (feature props carry p185/race).
export const METRICS = {
  perf: {
    label: 'School performance (Similar Schools %ile)',
    legend: 'diverging',
    gradient: pctGradient,
    ends: ['below typical', 'above typical'],
    value: (props, school) => school?.adj_pct ?? null,
    color: (v) => pctColor(v),
    fmt: pctile
  },
  p185: {
    label: 'Resident child poverty (under 185% of poverty)',
    legend: 'sequential',
    gradient: seqGradient,
    ends: ['0%', '80%+'],
    domain: 0.8,
    value: (props) => props.p185 ?? null,
    color(v) {
      return seqColor(v == null ? null : v / this.domain);
    },
    fmt: pct
  },
  his: raceMetric('his', 'Residents Hispanic or Latino (share)'),
  wht: raceMetric('wht', 'Residents white (share)'),
  blk: raceMetric('blk', 'Residents Black (share)'),
  asn: raceMetric('asn', 'Residents Asian (share)')
};

function raceMetric(key, label) {
  return {
    label,
    legend: 'sequential',
    gradient: seqGradient,
    ends: ['0%', '100%'],
    domain: 1,
    value: (props) => props.race?.[key] ?? null,
    color(v) {
      return seqColor(v);
    },
    fmt: pct
  };
}
