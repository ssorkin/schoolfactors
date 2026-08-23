import { error } from '@sveltejs/kit';
import { dataUrl } from '$lib/data.js';

export async function load({ params, fetch }) {
  const resp = await fetch(dataUrl(`/data/enrollment/counties/${params.cds}.json`));
  if (!resp.ok) error(404, 'no enrollment page for this county');
  return { detail: await resp.json() };
}
