import { readFileSync } from 'node:fs';
import { POSTS } from '$lib/insights.js';

/**
 * Prerendered sitemap covering every static page and every exported entity
 * page, from the same index.json that drives prerender entries — the two can't
 * drift. Regenerated on each build.
 */
export const prerender = true;

const SITE = 'https://schoolfactors.org';

const STATIC_PAGES = [
  { path: '/', priority: '1.0' },
  { path: '/student-groups', priority: '0.8' },
  { path: '/compare', priority: '0.7' },
  { path: '/insights', priority: '0.8' },
  { path: '/methodology', priority: '0.8' },
  { path: '/glossary', priority: '0.6' },
  { path: '/data', priority: '0.6' },
  { path: '/about', priority: '0.5' }
];

const KIND_PRIORITY = { school: '0.7', district: '0.6', county: '0.5' };

export function GET() {
  const index = JSON.parse(readFileSync('static/data/index.json', 'utf-8'));
  const today = new Date().toISOString().slice(0, 10);
  const urls = [
    ...STATIC_PAGES.map((p) => ({ loc: SITE + p.path, priority: p.priority })),
    ...POSTS.map((p) => ({ loc: `${SITE}/insights/${p.slug}`, priority: '0.7' })),
    ...index.map((e) => ({
      loc: `${SITE}/${e.kind}/${e.cds}`,
      priority: KIND_PRIORITY[e.kind] ?? '0.5'
    }))
  ];
  const body =
    '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    urls
      .map(
        (u) =>
          `  <url><loc>${u.loc}</loc><lastmod>${today}</lastmod>` +
          `<priority>${u.priority}</priority></url>`
      )
      .join('\n') +
    '\n</urlset>\n';
  return new Response(body, {
    headers: { 'Content-Type': 'application/xml' }
  });
}
