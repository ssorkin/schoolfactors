import { error } from '@sveltejs/kit';
import { dataUrl } from '$lib/data.js';

export async function load({ params, fetch }) {
  const resp = await fetch(dataUrl(`/data/districts/${params.cds}.json`));
  if (!resp.ok) error(404, 'district not found');
  const entity = await resp.json();
  return { entity, schools: entity.schools ?? [] };
}
