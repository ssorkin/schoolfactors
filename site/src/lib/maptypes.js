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
