<script>
  import EnrollNav from '$lib/enrollment/EnrollNav.svelte';

  let { children } = $props();
</script>

<p class="kicker">Enrollment flows · every California district</p>
<EnrollNav />

{@render children()}

<p class="note">
  Every flow on these pages is a net accounting residual, modeled from public
  census-day enrollment and Census Bureau residence data — likely, not observed,
  transfers (California publishes no student-level origin/destination data).
  Positive numbers always mean a net importer. Estimates from survey data carry
  margins of error and are labeled "est."
</p>

<style>
  .kicker {
    margin: 0 0 -0.4rem;
    font-size: 0.85rem;
    color: #6f6a61;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .note {
    margin-top: 2.5rem;
    padding-top: 0.9rem;
    border-top: 1px solid #e8e1d5;
    color: #6f6a61;
    font-size: 0.85rem;
  }
</style>
