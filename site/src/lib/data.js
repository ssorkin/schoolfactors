import { version } from '$app/environment';

// Data files live at stable URLs but change every deploy, and the server
// caches them for an hour — so a client-side navigation could pair this
// build's page with a previous deploy's JSON (stale-cache bug: SPA clicks
// showed old payloads while full reloads, which inline the data at prerender
// time, were correct). Appending the build version busts the cache exactly
// once per release.
export const dataUrl = (path) => `${path}?v=${version}`;
