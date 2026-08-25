import { readFileSync } from 'node:fs';

/** Prerender ONLY the computed findings block into the landing HTML (it is the
 *  page's flagship content and must not wait on a client fetch). The full
 *  index stays client-fetched — serializing it here would bloat the page. */
export function load() {
  const index = JSON.parse(readFileSync('static/data/enrollment/index.json', 'utf-8'));
  return { findings: index.findings ?? null };
}
