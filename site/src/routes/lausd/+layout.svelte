<script>
  import StoryNav from '$lib/district/StoryNav.svelte';

  let { children } = $props();
</script>

<p class="kicker">
  District data story ·
  <a href="/district/19647330000000">standard district page →</a>
</p>
<h1>Los Angeles Unified</h1>
<StoryNav />

{@render children()}

<p class="note">
  Everything here is descriptive: we show how numbers move together across schools
  and neighborhoods — correlations between averages, never causes and never bare
  ranks. Percentiles always compare schools serving similar students.
</p>

<style>
  .kicker {
    margin: 0 0 -0.4rem;
    font-size: 0.85rem;
    color: #6f6a61;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .kicker a {
    text-transform: none;
    letter-spacing: normal;
  }
  h1 {
    margin: 0.4rem 0 0.2rem;
  }
  .note {
    margin-top: 2.5rem;
    padding-top: 0.9rem;
    border-top: 1px solid #e8e1d5;
    color: #6f6a61;
    font-size: 0.85rem;
  }
</style>
