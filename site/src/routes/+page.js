export async function load({ fetch }) {
  const [summary, counties] = await Promise.all([
    (await fetch('/data/summary.json')).json(),
    (await fetch('/data/counties.json')).json()
  ]);
  return { summary, counties };
}
