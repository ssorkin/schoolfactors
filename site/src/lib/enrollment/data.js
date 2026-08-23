// Client-side cached fetchers for the /enrollment payloads. These must never run
// in a load function: prerendered universal loads get serialized into every page's
// HTML, and the statewide index + boundary geojson would bloat every page.
// Module-level memoization (lausdData.js pattern) fetches each file once per
// session as the reader moves between the landing map and detail pages.

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

/** The compact statewide join table, reshaped from {cols, rows} into objects.
 *  Resolves to { vintages, rows, byGeoid, byCds } — rows carry geoid, cds, name,
 *  dtype (u/e/h/c), county, ll, net_rate, net_moe, res, seats, virt_share, perf,
 *  spark (per-vintage net rates), res_chg, seats_chg. */
export const getIndex = () =>
  memo('index', async () => {
    const raw = await getJson('/data/enrollment/index.json');
    const rows = raw.rows.map((r) => Object.fromEntries(raw.cols.map((c, i) => [c, r[i]])));
    return {
      vintages: raw.vintages,
      rows,
      byGeoid: new Map(rows.map((r) => [r.geoid, r])),
      byCds: new Map(rows.filter((r) => r.cds).map((r) => [r.cds, r]))
    };
  });

/** Statewide simplified polygons for one level: 'u' unified, 'e' elementary,
 *  'h' secondary (high). Properties carry only the join key {g: geoid}. */
export const getBoundaries = (level) =>
  memo(`boundaries_${level}`, () => getJson(`/data/enrollment/boundaries_${level}.geojson`));
