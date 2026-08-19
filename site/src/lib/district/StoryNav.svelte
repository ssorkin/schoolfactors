<script>
  import { page } from '$app/state';

  const TABS = [
    { path: '/lausd', label: 'Overview' },
    { path: '/lausd/map', label: 'Map & boundaries' },
    { path: '/lausd/funding', label: 'Funding' },
    { path: '/lausd/enrollment', label: 'Enrollment' },
    { path: '/lausd/demographics', label: 'Demographics' }
  ];

  let path = $derived(page.url.pathname.replace(/\/$/, '') || '/lausd');
</script>

<nav aria-label="LAUSD story sections">
  {#each TABS as t}
    <a href={t.path} class:active={path === t.path} aria-current={path === t.path ? 'page' : undefined}>
      {t.label}
    </a>
  {/each}
</nav>

<style>
  nav {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
    border-bottom: 1px solid #e8e1d5;
    margin: 0.75rem 0 1.25rem;
  }
  a {
    text-decoration: none;
    color: #52514e;
    font-weight: 550;
    font-size: 0.92rem;
    padding: 0.35rem 0.7rem;
    border-radius: 8px 8px 0 0;
    border-bottom: 2px solid transparent;
  }
  a:hover {
    color: #b0552f;
  }
  a.active {
    color: #b0552f;
    border-bottom-color: #b0552f;
  }
</style>
