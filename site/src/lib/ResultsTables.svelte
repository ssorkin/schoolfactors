<script>
  /**
   * The underlying CAASPP numbers behind the charts: results by grade × year
   * (choice of metric) and percent met-or-exceeded by student group × year.
   * Suppressed cells (n < 11 at source) simply don't exist and render as —.
   */
  let { scores = [], subgroups = [] } = $props();

  let subject = $state('ela');
  let metric = $state('mean');

  const METRICS = {
    mean: { label: 'Mean scale score', fmt: (r) => r.mean?.toFixed(0) },
    z: { label: 'vs state (SDs)', fmt: (r) => (r.z > 0 ? '+' : '') + r.z?.toFixed(2) },
    pct_met: { label: '% met or exceeded', fmt: (r) => r.pct_met?.toFixed(0) + '%' },
    n: { label: 'Students with scores', fmt: (r) => r.n?.toLocaleString() }
  };

  import { GROUP_LABELS, GROUP_CATEGORIES } from '$lib/groups.js';

  const GROUP_ORDER = [1, ...GROUP_CATEGORIES.flatMap((c) => c.ids)];

  let rows = $derived(scores.filter((r) => r.subject === subject));
  let years = $derived([...new Set(rows.map((r) => r.year))].sort((a, b) => a - b));
  let grades = $derived([...new Set(rows.map((r) => r.grade))].sort((a, b) => a - b));
  let cell = $derived.by(() => {
    const m = new Map();
    for (const r of rows) m.set(r.grade + '-' + r.year, r);
    return m;
  });

  let srows = $derived(subgroups.filter((r) => r.subject === subject));
  let syears = $derived([...new Set(srows.map((r) => r.year))].sort((a, b) => a - b));
  let sgroups = $derived(
    GROUP_ORDER.filter((g) => srows.some((r) => r.group === g))
  );
  let scell = $derived.by(() => {
    const m = new Map();
    for (const r of srows) m.set(r.group + '-' + r.year, r);
    return m;
  });
</script>

{#if scores.length}
  <div class="wrap">
    <div class="controls">
      <div role="group" aria-label="Subject">
        <button class:active={subject === 'ela'} onclick={() => (subject = 'ela')}>ELA</button>
        <button class:active={subject === 'math'} onclick={() => (subject = 'math')}>Math</button>
      </div>
      <select bind:value={metric} aria-label="Metric">
        {#each Object.entries(METRICS) as [k, m] (k)}
          <option value={k}>{m.label}</option>
        {/each}
      </select>
    </div>

    <h3>By grade and year — {METRICS[metric].label.toLowerCase()}</h3>
    <div class="scroll">
      <table>
        <thead>
          <tr><th>Grade</th>{#each years as y (y)}<th class="tnum">{y}</th>{/each}</tr>
        </thead>
        <tbody>
          {#each grades as g (g)}
            <tr>
              <td>Grade {g}</td>
              {#each years as y (y)}
                {@const r = cell.get(g + '-' + y)}
                <td class="tnum" title={r ? `${r.n.toLocaleString()} students with scores` : 'suppressed or not tested'}>
                  {r ? METRICS[metric].fmt(r) : '—'}
                </td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    {#if sgroups.length}
      <h3>By student group — % met or exceeded standard (all grades combined)</h3>
      <div class="scroll">
        <table>
          <thead>
            <tr><th>Group</th>{#each syears as y (y)}<th class="tnum">{y}</th>{/each}</tr>
          </thead>
          <tbody>
            {#each sgroups as g (g)}
              <tr>
                <td>{GROUP_LABELS[g]}</td>
                {#each syears as y (y)}
                  {@const r = scell.get(g + '-' + y)}
                  <td class="tnum" title={r ? `${r.n.toLocaleString()} students with scores` : 'suppressed (fewer than 11 students) or not reported'}>
                    {r ? r.pct_met.toFixed(0) + '%' : '—'}
                  </td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <p class="note">
        Groups overlap (a student appears in several rows) and cells with fewer than
        11 students are suppressed at the source, so groups never sum to the total.
        2015 is directly comparable only with care and 2020–21 are excluded —
        <a href="/data">see the data notes</a>.
      </p>
    {/if}
  </div>
{/if}

<style>
  .wrap {
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    padding: 0.9rem 1.1rem;
  }
  .controls {
    display: flex;
    gap: 0.8rem;
    align-items: center;
    flex-wrap: wrap;
  }
  .controls button {
    border: 1px solid #d8d0c0;
    background: #faf7f2;
    border-radius: 6px;
    padding: 0.25rem 0.8rem;
    font-size: 0.9rem;
    cursor: pointer;
    margin-right: 0.3rem;
  }
  .controls button.active {
    background: #2a78d6;
    border-color: #2a78d6;
    color: #fff;
  }
  select {
    border: 1px solid #d8d0c0;
    background: #faf7f2;
    border-radius: 6px;
    padding: 0.28rem 0.5rem;
    font-size: 0.9rem;
  }
  h3 {
    margin: 1rem 0 0.4rem;
    font-size: 1.02rem;
  }
  .scroll {
    overflow-x: auto;
  }
  table {
    border-collapse: collapse;
    font-size: 0.88rem;
    min-width: 100%;
  }
  th,
  td {
    text-align: left;
    padding: 0.3rem 0.55rem;
    border-bottom: 1px solid #eee9df;
    white-space: nowrap;
  }
  .tnum {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  .note {
    color: #898781;
    font-size: 0.82rem;
    margin: 0.6rem 0 0;
    max-width: 46rem;
  }
</style>
