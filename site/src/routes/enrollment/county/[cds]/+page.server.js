import { readFileSync } from 'node:fs';

/** Prerender one page per county in the enrollment index (dtype 'c' rows). */
export function entries() {
  const index = JSON.parse(readFileSync('static/data/enrollment/index.json', 'utf-8'));
  const cds = index.cols.indexOf('cds');
  const dtype = index.cols.indexOf('dtype');
  return index.rows.filter((r) => r[dtype] === 'c').map((r) => ({ cds: r[cds] }));
}
