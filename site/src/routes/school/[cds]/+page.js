import { error } from '@sveltejs/kit';

export async function load({ params, fetch }) {
  const resp = await fetch(`/data/schools/${params.cds}.json`);
  if (!resp.ok) error(404, 'school not found');
  return { entity: await resp.json() };
}
