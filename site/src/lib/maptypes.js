// School-type color coding for the map, keyed off the same admission-type
// flags the Badges component uses. Priority: what most changes how to read a
// school's numbers (selectivity first).

export const TYPE_COLOR = {
  selective: '#c2410c',
  magnet: '#1c5cab',
  charter: '#1e6b3a',
  alternative: '#8a6d3b',
  regular: '#7f93ad'
};

export const TYPE_LABEL = {
  selective: 'Selective',
  magnet: 'Magnet',
  charter: 'Charter',
  alternative: 'Alternative (continuation, community, court, spec. ed)',
  regular: 'Traditional'
};

// Diverging ramp for "color by Similar Schools %ile": rust = below typical,
// neutral gray = 50 (typical for the students served), blue = above. Stops are
// validated per arm (one hue each, monotone lightness, poles lightness-matched
// at OKLCH L 0.47/0.48) and the orange/blue pair is CVD-safe.
export const PCT_STOPS = [
  [1, '#9a3412'],
  [25, '#c0734a'],
  [50, '#a3a3a3'],
  [75, '#6c8fc4'],
  [99, '#1c5cab']
];
export const NO_PCT_COLOR = '#d8d4cc';

const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));

export function pctColor(p) {
  if (p == null) return NO_PCT_COLOR;
  let i = 0;
  while (i < PCT_STOPS.length - 2 && p > PCT_STOPS[i + 1][0]) i++;
  const [p0, c0] = PCT_STOPS[i];
  const [p1, c1] = PCT_STOPS[i + 1];
  const t = Math.min(1, Math.max(0, (p - p0) / (p1 - p0)));
  const a = rgb(c0);
  const b = rgb(c1);
  return `rgb(${a.map((v, k) => Math.round(v + (b[k] - v) * t)).join(',')})`;
}

export function pctGradient() {
  const lo = PCT_STOPS[0][0];
  const hi = PCT_STOPS[PCT_STOPS.length - 1][0];
  const stops = PCT_STOPS.map(
    ([p, c]) => `${c} ${(((p - lo) / (hi - lo)) * 100).toFixed(1)}%`
  );
  return `linear-gradient(90deg, ${stops.join(', ')})`;
}

const ALT_FLAGS = new Set([
  'alt-choice',
  'continuation',
  'community-day',
  'community',
  'court',
  'special-ed'
]);

export function entityType(it) {
  if (it.kind !== 'school' || !it.flags?.length) return 'regular';
  if (it.flags.includes('selective')) return 'selective';
  if (it.flags.includes('magnet')) return 'magnet';
  if (it.flags.includes('charter')) return 'charter';
  if (it.flags.some((f) => ALT_FLAGS.has(f))) return 'alternative';
  return 'regular';
}
