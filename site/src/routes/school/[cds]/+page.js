import { error } from '@sveltejs/kit';
import { dataUrl } from '$lib/data.js';

export async function load({ params, fetch }) {
  const resp = await fetch(dataUrl(`/data/schools/${params.cds}.json`));
  if (!resp.ok) error(404, 'school not found');
  return { entity: await resp.json() };
}
