import { readFileSync } from 'node:fs';

/** Prerender one page per county in the export index. */
export function entries() {
  const index = JSON.parse(readFileSync('static/data/index.json', 'utf-8'));
  return index.filter((e) => e.kind === 'county').map((e) => ({ cds: e.cds }));
}
