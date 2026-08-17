// Shared facet-query machinery for the filterable tables (homepage,
// student-groups): `level:middle county:los angeles ivanhoe` etc. Words after
// a facet keyword attach to that facet until the next facet keyword.
export function norm(s) {
  return (s ?? '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9\s-]/g, ' ');
}

export const FACET_KEYS = ['level', 'kind', 'county', 'district', 'type', 'is'];

export function parseQuery(query) {
  const facets = {};
  const free = [];
  let cur = null;
  for (const p of query.split(/\s+/).filter(Boolean)) {
    const m = p.match(/^(level|kind|county|district|type|is):(.*)$/i);
    if (m) {
      cur = m[1].toLowerCase() === 'type' ? 'level' : m[1].toLowerCase();
      if (m[2]) facets[cur] = norm(m[2]).trim();
      else facets[cur] = '';
    } else if (cur !== null) {
      facets[cur] = (facets[cur] + ' ' + norm(p)).trim();
    } else {
      free.push(norm(p).trim());
    }
  }
  return { facets, free: free.filter(Boolean) };
}
