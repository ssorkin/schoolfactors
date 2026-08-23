import { error } from '@sveltejs/kit';
import { dataUrl } from '$lib/data.js';

export async function load({ params, fetch }) {
  const resp = await fetch(dataUrl(`/data/enrollment/districts/${params.cds}.json`));
  if (!resp.ok) error(404, 'no enrollment page for this district');
  return { detail: await resp.json() };
}
