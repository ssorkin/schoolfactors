<script>
  import { downloadCsv } from '$lib/csv.js';
  // build() is called on click and returns { headers, rows } for the CSV —
  // typically the table's current (filtered/sorted) view.
  let { filename, build, label = 'Download CSV' } = $props();
</script>

<button
  class="csv"
  onclick={() => {
    const { headers, rows } = build();
    downloadCsv(filename, headers, rows);
  }}>{label}</button
>

<style>
  .csv {
    border: none;
    background: none;
    padding: 0;
    font: inherit;
    font-size: 0.85rem;
    color: #1c5cab;
    cursor: pointer;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .csv:hover {
    color: #b0552f;
  }
</style>
