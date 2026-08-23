import { readFileSync } from 'node:fs';

/** Prerender one page per district area with a CDE crosswalk in the enrollment
 *  index ({cols, rows} format; county rows are dtype 'c' and live under
 *  /enrollment/county/). */
export function entries() {
  const index = JSON.parse(readFileSync('static/data/enrollment/index.json', 'utf-8'));
  const cds = index.cols.indexOf('cds');
  const dtype = index.cols.indexOf('dtype');
  const rate = index.cols.indexOf('net_rate');
  // Pages exist exactly for crosswalked districts with at least one estimate
  // (the exporter's condition) — a non-null latest net rate implies both.
  return index.rows
    .filter((r) => r[dtype] !== 'c' && r[cds] && r[rate] != null)
    .map((r) => ({ cds: r[cds] }));
}
