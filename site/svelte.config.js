import adapter from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  kit: {
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      fallback: null,
      precompress: true
    }),
    prerender: {
      // The district table-of-contents links to sections that only render
      // when an entity has the underlying data; a missing anchor on a sparse
      // page is expected, not a build error.
      handleMissingId: 'warn'
    }
  }
};

export default config;
