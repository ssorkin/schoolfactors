import { error } from '@sveltejs/kit';
import { dataUrl } from '$lib/data.js';

// The district payload is small enough to inline at prerender time and gives every
// story page SSR-visible headline stats. Big payloads (schools.json, boundary
// geojson) are fetched client-side via lausdData.js instead — never here.
export async function load({ fetch }) {
  const res = await fetch(dataUrl('/data/districts/19647330000000.json'));
  if (!res.ok) error(404, 'LAUSD district data not found');
  return { district: await res.json() };
}
