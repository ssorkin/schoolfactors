// The insights blog: one entry per article, newest first. Add a post by
// creating site/src/routes/insights/<slug>/+page.svelte and listing it here.
export const POSTS = [
  {
    slug: 'lausd-enrollment-choice',
    title: 'Enrollment drains from low-scoring schools — but mostly, the children left first',
    date: '2026-08-17',
    updated: '2026-08-19',
    author: 'Stephen Sorkin',
    blurb:
      "LAUSD's enrollment decline fell hardest on elementaries with the lowest raw " +
      '2015–16 scores. Revisited with attendance-area census data: the neighborhoods ' +
      'of those schools lost children at nearly the same rate — subtract that, and ' +
      'most of the "flight" disappears.'
  },
  {
    slug: 'growth-vs-level',
    title: 'Scoring high and improving fast are different things',
    date: '2026-08-16',
    blurb:
      'Across nine thousand California schools, where students score and how fast ' +
      'cohorts progress are essentially unrelated — the falsification test ' +
      'single-number school ratings historically fail.'
  }
];

export const fmtDate = (iso) =>
  new Date(iso + 'T12:00:00').toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });

// Shared math for post charts.
export function corr(xs, ys) {
  const n = xs.length;
  if (n < 3) return null;
  const mx = xs.reduce((a, b) => a + b, 0) / n;
  const my = ys.reduce((a, b) => a + b, 0) / n;
  let sxy = 0;
  let sxx = 0;
  let syy = 0;
  for (let i = 0; i < n; i++) {
    sxy += (xs[i] - mx) * (ys[i] - my);
    sxx += (xs[i] - mx) ** 2;
    syy += (ys[i] - my) ** 2;
  }
  return sxx && syy ? sxy / Math.sqrt(sxx * syy) : null;
}
export const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
export const fmt2 = (v) => (v > 0 ? '+' : '') + v.toFixed(2);
