import { error } from '@sveltejs/kit';

export async function load({ params, fetch }) {
  const resp = await fetch(`/data/counties/${params.cds}.json`);
  if (!resp.ok) error(404, 'county not found');
  const entity = await resp.json();
  return { entity, districts: entity.districts ?? [] };
}
