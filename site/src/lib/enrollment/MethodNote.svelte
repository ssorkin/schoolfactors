<script>
  // One shared footnote so the "modeled, not observed" framing can never drift
  // between charts. Rendered under every enrollment-flow chart and list.
  let { extra = '' } = $props();
</script>

<p class="methodnote">
  Modeled from public enrollment and census data — likely, not observed, transfers.
  {extra}
  <a href="/enrollment/methodology">How this is modeled →</a>
</p>

<style>
  .methodnote {
    margin: 0.35rem 0 0;
    font-size: 0.78rem;
    color: #898781;
  }
  .methodnote a {
    color: #6f6a61;
  }
</style>
