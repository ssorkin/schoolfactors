<script>
  // Legacy URL: this page moved to /student-groups. Client-side replace keeps
  // shared links' ?g= group selection; the meta refresh covers no-JS visitors.
  import { onMount } from 'svelte';
  onMount(() => {
    window.location.replace('/student-groups' + window.location.search);
  });
</script>

<svelte:head>
  <title>Student groups — SchoolFactors</title>
  <meta http-equiv="refresh" content="0; url=/student-groups" />
</svelte:head>

<p>This page has moved to <a href="/student-groups">Student Groups</a>.</p>
