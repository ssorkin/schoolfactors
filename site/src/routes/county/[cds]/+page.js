import { error } from '@sveltejs/kit';
import { dataUrl } from '$lib/data.js';

export async function load({ params, fetch }) {
  const resp = await fetch(dataUrl(`/data/counties/${params.cds}.json`));
  if (!resp.ok) error(404, 'county not found');
  const entity = await resp.json();
  return { entity, districts: entity.districts ?? [] };
}
