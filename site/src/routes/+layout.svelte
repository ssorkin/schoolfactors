<script>
  import { page } from '$app/state';
  let { children } = $props();
</script>

<div class="shell" class:wide={page.url.pathname === '/'}>
  <header>
    <a class="brand" href="/">School<span>Factors</span></a>
    <nav>
      <a href="/best-for">Best for…</a>
      <a href="/insights">Insights</a>
      <a href="/methodology">Methodology</a>
      <a href="/glossary">Glossary</a>
      <a href="/data">Data</a>
      <a href="/about">About</a>
      <a href="https://github.com/ssorkin/schoolfactors">GitHub</a>
    </nav>
  </header>

  <main>
    {@render children()}
  </main>

  <footer>
    <p>
      SchoolFactors is 100% open source. Every number on this site can be reproduced
      from public data with the
      <a href="https://github.com/ssorkin/schoolfactors">published pipeline</a>.
      We show correlations between school averages — never causes, never bare ranks.
    </p>
  </footer>
</div>

<style>
  :global(*) {
    box-sizing: border-box;
  }
  :global(body) {
    margin: 0;
    background: #faf7f2;
    color: #2b2722;
    font-family:
      system-ui,
      -apple-system,
      'Segoe UI',
      sans-serif;
    line-height: 1.6;
  }
  :global(a) {
    color: #1c5cab;
  }
  :global(h1, h2, h3) {
    line-height: 1.25;
    color: #211d18;
  }
  .shell {
    max-width: 960px;
    margin: 0 auto;
    padding: 0 1.25rem;
  }
  /* The homepage table needs the room; header, intro, and footer follow so
     every block shares one width. Other pages stay at reading width. */
  .shell.wide {
    max-width: calc(1280px + 2.5rem);
  }
  header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.75rem;
    padding: 1.4rem 0 1rem;
    border-bottom: 1px solid #e8e1d5;
  }
  .brand {
    font-size: 1.45rem;
    font-weight: 750;
    text-decoration: none;
    color: #b0552f;
    letter-spacing: -0.02em;
  }
  .brand span {
    color: #2b2722;
  }
  nav {
    display: flex;
    gap: 1.2rem;
  }
  nav a {
    text-decoration: none;
    color: #52514e;
    font-weight: 550;
  }
  nav a:hover {
    color: #b0552f;
  }
  main {
    min-height: 70vh;
    padding: 1.5rem 0 3rem;
  }
  footer {
    border-top: 1px solid #e8e1d5;
    padding: 1.25rem 0 2.5rem;
    color: #6f6a61;
    font-size: 0.9rem;
  }
</style>
