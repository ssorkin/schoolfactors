<script>
  import { CLASS_COLOR, CLASS_LABEL } from './metrics.js';

  /**
   * Schools whose seats the flow model attributes to this area, sorted by latest
   * enrollment. Rows are the export's compact arrays:
   * [cds, name, class, lat, lon, enr_latest, spark, sited, has_page].
   */
  let { schools = [], sparkSprings = [] } = $props();

  const CHIP_WORD = {
    district_run: 'district',
    charter_aff: 'affiliated',
    charter_bm: 'charter',
    charter_virtual: 'virtual'
  };
  const SITED_NOTE = {
    nearest: 'sited to nearest area (coastal/precision gap)',
    crosswalk: 'sited by district record (no usable coordinates)'
  };

  function sparkPath(spark) {
    const vals = (spark ?? []).map((v, i) => [i, v]).filter(([, v]) => v != null);
    if (vals.length < 2) return null;
    const max = Math.max(...vals.map(([, v]) => v), 1);
    const X = (i) => 2 + (i / (spark.length - 1)) * 116;
    const Y = (v) => 26 - (v / max) * 22;
    return vals.map(([i, v], k) => `${k ? 'L' : 'M'}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join('');
  }
</script>

{#if schools.length}
  <table class="schools">
    <thead>
      <tr>
        <th>School</th>
        <th>Class</th>
        <th class="num">Enrolled</th>
        <th>{sparkSprings[0]}–{sparkSprings[sparkSprings.length - 1]}</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each schools as s}
        {@const [cds, name, cls, , , enr, spark, sited, hasPage] = s}
        <tr class:closed={enr == null}>
          <td>
            {#if hasPage}<a href="/school/{cds}">{name ?? cds}</a>{:else}{name ?? cds}{/if}
          </td>
          <td>
            <span class="chip" style="--c: {CLASS_COLOR[cls]}" title={CLASS_LABEL[cls]}>
              {CHIP_WORD[cls] ?? cls}
            </span>
          </td>
          <td class="num">{enr == null ? '—' : enr.toLocaleString()}</td>
          <td>
            {#if sparkPath(spark)}
              <svg viewBox="0 0 120 28" class="spark"><path d={sparkPath(spark)} /></svg>
            {/if}
          </td>
          <td class="note">{SITED_NOTE[sited] ?? ''}{enr == null ? 'no longer reporting' : ''}</td>
        </tr>
      {/each}
    </tbody>
  </table>
{/if}

<style>
  .schools {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.86rem;
  }
  th {
    text-align: left;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: #898781;
    padding: 0.3rem 0.5rem;
    border-bottom: 1px solid #e8e1d5;
  }
  td {
    padding: 0.28rem 0.5rem;
    border-bottom: 1px solid #f1ece1;
  }
  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  a {
    color: #1c5cab;
    text-decoration: none;
  }
  a:hover {
    text-decoration: underline;
  }
  .chip {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--c);
    border: 1px solid color-mix(in srgb, var(--c) 45%, #fff);
    border-radius: 999px;
    padding: 0.05rem 0.5rem;
    background: color-mix(in srgb, var(--c) 8%, #fff);
  }
  .spark {
    width: 120px;
    height: 28px;
    display: block;
  }
  .spark path {
    fill: none;
    stroke: #8d8880;
    stroke-width: 1.5;
  }
  .note {
    color: #898781;
    font-size: 0.75rem;
  }
  tr.closed td {
    color: #898781;
  }
</style>
