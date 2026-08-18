// Shared facet-query machinery for the filterable tables (homepage,
// student-groups): `level:middle county:los angeles ivanhoe` etc. Words after
// a facet keyword attach to that facet until the next facet keyword. Values
// may be double-quoted to group words explicitly: district:"Los Angeles
// Unified". Numeric fields take rudimentary comparators: students:<150,
// per_pupil:>20000, frpm:>80 (see NUM_FACETS for synonyms and units).
export function norm(s) {
  return (s ?? '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9\s-]/g, ' ');
}

export const FACET_KEYS = ['level', 'kind', 'county', 'district', 'type', 'is'];

// Numeric facets: query key → row field, with an optional scale from query
// units to stored units (FRPM is stored as a 0-1 fraction, queried in %).
export const NUM_FACETS = {
  students: { field: 'enrollment' },
  enrollment: { field: 'enrollment' },
  ppe: { field: 'ppe' },
  per_pupil: { field: 'ppe' },
  spending: { field: 'ppe' },
  similar_percentile: { field: 'adj_pct' },
  percentile: { field: 'adj_pct' },
  frpm: { field: 'econ', scale: 0.01 },
  econ: { field: 'econ', scale: 0.01 },
  growth: { field: 'growth_eb' },
  ela: { field: 'pass_ela' },
  math: { field: 'pass_math' }
};

// The keys offered by the typeahead (one per concept, not every synonym).
export const NUM_FACET_SUGGEST = [
  'students', 'per_pupil', 'similar_percentile', 'frpm', 'growth', 'ela', 'math'
];

const unquote = (s) => s.replace(/"/g, '');

export function parseQuery(query) {
  const facets = {};
  const nums = [];
  const free = [];
  let cur = null;
  // Tokenize keeping double-quoted spans intact: district:"Los Angeles Unified"
  const tokens = query.match(/[^\s"]*"[^"]*"[^\s"]*|[^\s"]+/g) ?? [];
  for (const p of tokens) {
    const nm = p.match(/^([a-z_]+):(>=|<=|>|<)?(-?\d+(?:\.\d+)?)$/i);
    const spec = nm && NUM_FACETS[nm[1].toLowerCase()];
    if (spec) {
      nums.push({
        field: spec.field,
        op: nm[2] ?? '=',
        value: parseFloat(nm[3]) * (spec.scale ?? 1)
      });
      cur = null;
      continue;
    }
    const m = p.match(/^(level|kind|county|district|type|is):(.*)$/i);
    if (m) {
      cur = m[1].toLowerCase() === 'type' ? 'level' : m[1].toLowerCase();
      const v = unquote(m[2]);
      if (v) facets[cur] = norm(v).trim();
      else facets[cur] = '';
    } else if (cur !== null) {
      facets[cur] = (facets[cur] + ' ' + norm(unquote(p))).trim();
    } else {
      free.push(norm(unquote(p)).trim());
    }
  }
  return { facets, nums, free: free.filter(Boolean) };
}

// Apply numeric comparators to a row; a missing value never matches.
export function matchNums(nums, it) {
  for (const f of nums) {
    const v = it[f.field];
    if (v == null) return false;
    if (f.op === '>') {
      if (!(v > f.value)) return false;
    } else if (f.op === '<') {
      if (!(v < f.value)) return false;
    } else if (f.op === '>=') {
      if (!(v >= f.value)) return false;
    } else if (f.op === '<=') {
      if (!(v <= f.value)) return false;
    } else if (v !== f.value) {
      return false;
    }
  }
  return true;
}
