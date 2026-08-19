import { dataUrl } from '$lib/data.js';

export async function load({ fetch }) {
  const overview = await fetch(dataUrl('/data/lausd/overview.json')).then((r) =>
    r.ok ? r.json() : null
  );
  return { overview };
}
