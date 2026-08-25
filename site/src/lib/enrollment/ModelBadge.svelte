<script>
  /**
   * The one persistent "modeled, not observed" marker on enrollment detail
   * pages — replaces per-section boilerplate (which repeated until it became
   * noise). Section-specific caveats stay only where the assumptions actually
   * differ (the channel chart's allocation note).
   */
  let { text = 'Modeled net balance — not observed transfers' } = $props();
</script>

<p class="badge">
  <span class="pill">{text}</span>
  <a href="/enrollment/methodology">How this is modeled →</a>
</p>

<style>
  .badge {
    margin: 0.15rem 0 0.4rem;
    font-size: 0.8rem;
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
  }
  .pill {
    display: inline-block;
    background: #f4f1fb;
    border: 1px solid #d9d2ef;
    color: #4a3aa7;
    font-weight: 600;
    border-radius: 999px;
    padding: 0.12rem 0.6rem;
  }
  a {
    color: #6f6a61;
  }
</style>
