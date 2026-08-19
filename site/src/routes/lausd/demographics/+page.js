import { dataUrl } from '$lib/data.js';

export async function load({ fetch }) {
  const demographics = await fetch(dataUrl('/data/lausd/demographics.json')).then((r) =>
    r.ok ? r.json() : null
  );
  return { demographics };
}
