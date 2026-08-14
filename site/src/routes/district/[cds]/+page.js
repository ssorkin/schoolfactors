import { error } from '@sveltejs/kit';

export async function load({ params, fetch }) {
  const resp = await fetch(`/data/districts/${params.cds}.json`);
  if (!resp.ok) error(404, 'district not found');
  const entity = await resp.json();
  return { entity, schools: entity.schools ?? [] };
}
