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
 *  Resolves to { vintages, rows, byGeoid, byCds, findings } — rows carry geoid,
 *  cds, name, dtype (u/e/h/c), county, ll, net_rate, net_moe, res, seats,
 *  virt_share, perf, spark (per-vintage net rates), res_chg, seats_chg, and
 *  (county rows) flow_rate, mis_rate. `findings` is the computed statewide
 *  takeaways block for the landing page. */
export const getIndex = () =>
  memo('index', async () => {
    const raw = await getJson('/data/enrollment/index.json');
    const rows = raw.rows.map((r) => Object.fromEntries(raw.cols.map((c, i) => [c, r[i]])));
    return {
      vintages: raw.vintages,
      rows,
      byGeoid: new Map(rows.map((r) => [r.geoid, r])),
      byCds: new Map(rows.filter((r) => r.cds).map((r) => [r.cds, r])),
      findings: raw.findings ?? null
    };
  });

/** Statewide simplified polygons for one level: 'u' unified, 'e' elementary,
 *  'h' secondary (high), 'c' county. Properties carry only the join key
 *  {g: geoid}. */
export const getBoundaries = (level) =>
  memo(`boundaries_${level}`, () => getJson(`/data/enrollment/boundaries_${level}.geojson`));

/** The statewide remote-program dataset (programs.json): program rows with
 *  classification basis and per-window history, balanced footprint fractions
 *  per authorizer county, county names, and the district nonlocality table. */
export const getPrograms = () => memo('programs', () => getJson('/data/enrollment/programs.json'));

/** This build's model-check numbers (validation.json) for the methodology page. */
export const getValidation = () =>
  memo('validation', () => getJson('/data/enrollment/validation.json'));
