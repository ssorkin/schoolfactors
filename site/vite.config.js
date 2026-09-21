import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    watch: {
      // build/ (85k prerendered files) and static/data/ (12k exported JSON)
      // exhaust the inotify watch limit; neither needs hot reload.
      ignored: ['**/build/**', '**/static/data/**', '**/static/og/**']
    }
  }
});
