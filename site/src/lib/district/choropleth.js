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

export const ordinal = (v) => {
  const n = Math.round(v);
  const suf = n % 10 === 1 && n !== 11 ? 'st' : n % 10 === 2 && n !== 12 ? 'nd'
    : n % 10 === 3 && n !== 13 ? 'rd' : 'th';
  return `${n}${suf}`;
};
const pctile = (v) =>
  v == null ? 'no data' : `${ordinal(v)} %ile vs schools serving similar students`;
const pct = (v) => (v == null ? 'no data' : `${Math.round(v * 100)}%`);

// Each metric: where the value comes from (polygon properties + the joined school
// row), how to color it, and how the legend reads. Demographic metrics appear only
// once census block-group data is exported (feature props carry p185/race).
export const METRICS = {
  perf: {
    label: 'School performance (Similar Student %ile)',
    short: 'Similar Student %ile',
    legend: 'diverging',
    gradient: pctGradient,
    ends: ['lower for similar students', 'higher for similar students'],
    value: (props, school) => school?.simstu_pct ?? null,
    color: (v) => pctColor(v),
    fmt: pctile
  },
  diverge: {
    label: 'Enrollment divergence: school vs neighborhood children (2011→2021)',
    short: 'Divergence',
    legend: 'diverging',
    gradient: pctGradient,
    ends: ['school shrank faster', 'school outgrew area'],
    value: (props) => props.diverge ?? null,
    color: (v) => (v == null ? NO_DATA : pctColor(50 + v)),
    fmt: (v) => (v == null ? 'no data' : `${v > 0 ? '+' : ''}${v} pp`)
  },
  p185: {
    label: 'Resident child poverty (under 185% of poverty)',
    short: 'Child poverty',
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
  ba: {
    label: "Resident adults with a bachelor's degree or higher",
    short: "BA+ share",
    legend: 'sequential',
    gradient: seqGradient,
    ends: ['0%', '90%'],
    domain: 0.9,
    value: (props) => props.ba ?? null,
    color(v) {
      return seqColor(v == null ? null : v / this.domain);
    },
    fmt: pct
  },
  his: raceMetric('his', 'Residents Hispanic or Latino (share)', 'Hispanic share'),
  wht: raceMetric('wht', 'Residents white (share)', 'White share'),
  blk: raceMetric('blk', 'Residents Black (share)', 'Black share'),
  asn: raceMetric('asn', 'Residents Asian (share)', 'Asian share')
};

function raceMetric(key, label, short) {
  return {
    label,
    short,
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
