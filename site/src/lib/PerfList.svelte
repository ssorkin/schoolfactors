<script>
  /**
   * Highest / lowest performers among a set of child entities, with a toggle
   * between demographically-adjusted and raw levels. Deliberately NOT a numbered
   * ranking: values with intervals, and a standing caveat.
   */
  let { items = [], kind = 'school', childPath = '/school' } = $props();

  let mode = $state('adjusted'); // 'adjusted' | 'raw'
  let metric = $derived(mode === 'adjusted' ? 'level_adj_eb' : 'level_eb');

  let ranked = $derived(
    items
      .filter((s) => s[metric] != null)
      .slice()
      .sort((a, b) => b[metric] - a[metric])
  );
  let top = $derived(ranked.slice(0, 5));
  let bottom = $derived(ranked.slice(-5).reverse());

  const fmt = (v) => (v > 0 ? '+' : '') + v.toFixed(2);
</script>

{#if ranked.length >= 4}
  <div class="perf">
    <div class="head">
      <div class="toggle" role="group" aria-label="Comparison mode">
        <button class:active={mode === 'adjusted'} onclick={() => (mode = 'adjusted')}>
          Adjusted for demographics
        </button>
        <button class:active={mode === 'raw'} onclick={() => (mode = 'raw')}>Raw scores</button>
      </div>
      <p class="explain">
        {#if mode === 'adjusted'}
          Score levels relative to {kind}s serving <em>similar students</em> — the fairer
          comparison, though it still can't capture everything.
        {:else}
          Raw score levels vs the state average — these largely track student
          demographics, not what the {kind} contributes.
        {/if}
      </p>
    </div>
    <div class="cols">
      <div>
        <h4>Higher-performing</h4>
        <ul>
          {#each top as s (s.cds)}
            <li>
              <a href="{childPath}/{s.cds}">{s.name}</a>
              <span class="val pos">{fmt(s[metric])}</span>
            </li>
          {/each}
        </ul>
      </div>
      <div>
        <h4>Lower-performing</h4>
        <ul>
          {#each bottom as s (s.cds)}
            <li>
              <a href="{childPath}/{s.cds}">{s.name}</a>
              <span class="val neg">{fmt(s[metric])}</span>
            </li>
          {/each}
        </ul>
      </div>
    </div>
    <p class="caveat">
      Values in student-level SDs, shrunken for reliability. These are lists, not
      rankings — many {kind}s are statistically indistinguishable from one another,
      and results shift under reasonable modeling choices.
    </p>
  </div>
{/if}

<style>
  .perf {
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin: 1rem 0 1.4rem;
  }
  .toggle button {
    border: 1px solid #d8d0c0;
    background: #faf7f2;
    border-radius: 6px;
    padding: 0.3rem 0.8rem;
    font-size: 0.88rem;
    cursor: pointer;
    margin-right: 0.4rem;
  }
  .toggle button.active {
    background: #2a78d6;
    border-color: #2a78d6;
    color: #fff;
  }
  .explain {
    color: #6f6a61;
    font-size: 0.88rem;
    max-width: 44rem;
    margin: 0.5rem 0 0.4rem;
  }
  .cols {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 0.5rem 2rem;
  }
  h4 {
    margin: 0.4rem 0 0.3rem;
    color: #52514e;
  }
  ul {
    list-style: none;
    padding: 0;
    margin: 0;
  }
  li {
    display: flex;
    justify-content: space-between;
    gap: 0.8rem;
    padding: 0.28rem 0;
    border-bottom: 1px solid #f0ead9;
    font-size: 0.95rem;
  }
  .val {
    font-variant-numeric: tabular-nums;
    font-weight: 650;
  }
  .val.pos {
    color: #006300;
  }
  .val.neg {
    color: #d03b3b;
  }
  .caveat {
    color: #898781;
    font-size: 0.82rem;
    margin: 0.7rem 0 0;
    max-width: 44rem;
  }
</style>
