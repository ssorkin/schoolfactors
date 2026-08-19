// Client-side cached fetchers for the big /lausd payloads. These must never run in
// a load function: prerendered universal loads get serialized into every page's
// HTML, and schools.json (~500KB) + boundary geojson would bloat all five pages.
// Module-level memoization means the files are fetched once per session even as the
// reader moves between story tabs.

import { dataUrl } from '$lib/data.js';

const cache = new Map();

function memo(key, make) {
  if (!cache.has(key)) {
    cache.set(
      key,
      make().catch((e) => {
        cache.delete(key); // let a transient failure retry on next call
        throw e;
      })
    );
  }
  return cache.get(key);
}

const getJson = (path) =>
  fetch(dataUrl(path)).then((r) => {
    if (!r.ok) throw new Error(`${path}: ${r.status}`);
    return r.json();
  });

export const getSchools = () => memo('schools', () => getJson('/data/lausd/schools.json'));

export const getBoundaries = (level) =>
  memo(`boundaries_${level}`, () => getJson(`/data/lausd/boundaries_${level}.geojson`));
