import { readFileSync } from 'node:fs';

/** Prerender one page per district in the export index. */
export function entries() {
  const index = JSON.parse(readFileSync('static/data/index.json', 'utf-8'));
  return index.filter((e) => e.kind === 'district').map((e) => ({ cds: e.cds }));
}
