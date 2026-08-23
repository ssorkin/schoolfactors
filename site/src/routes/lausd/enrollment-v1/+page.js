import { dataUrl } from '$lib/data.js';

export async function load({ fetch }) {
  const enrollment = await fetch(dataUrl('/data/lausd/enrollment.json')).then((r) =>
    r.ok ? r.json() : null
  );
  return { enrollment };
}
