import { dataUrl } from '$lib/data.js';

export async function load({ fetch }) {
  const [funding, censusFrpm] = await Promise.all([
    fetch(dataUrl('/data/lausd/funding.json')).then((r) => (r.ok ? r.json() : null)),
    fetch(dataUrl('/data/census_frpm.json')).then((r) => (r.ok ? r.json() : null))
  ]);
  return { funding, censusFrpm };
}
