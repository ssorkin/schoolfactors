<script module>
  let indexCache = null;
</script>

<script>
  import { goto } from '$app/navigation';

  let {
    placeholder = 'Find any California school or district…',
    onselect = null,
    kinds = null
  } = $props();
  let query = $state('');
  let items = $state(null);

  async function ensureIndex() {
    if (!indexCache) {
      indexCache = await (await fetch('/data/index.json')).json();
    }
    items = indexCache;
  }

  let matches = $derived.by(() => {
    if (!items || query.length < 2) return [];
    const q = query.toLowerCase();
    const starts = [];
    const contains = [];
    for (const it of items) {
      if (kinds && !kinds.includes(it.kind)) continue;
      const n = it.name?.toLowerCase() ?? '';
      if (n.startsWith(q)) starts.push(it);
      else if (n.includes(q) || it.district?.toLowerCase().includes(q)) contains.push(it);
      if (starts.length > 12) break;
    }
    return [...starts, ...contains].slice(0, 10);
  });

  function open(it) {
    query = '';
    if (onselect) {
      onselect(it);
    } else {
      goto(`/${it.kind}/${it.cds}`);
    }
  }
</script>

<div class="search">
  <input
    {placeholder}
    bind:value={query}
    onfocus={ensureIndex}
    aria-label="Search schools and districts"
  />
  {#if matches.length}
    <ul class="hits">
      {#each matches as m (m.cds)}
        <li>
          <button onclick={() => open(m)}>
            {m.name}
            <span>{m.kind === 'district' ? `district · ${m.county} County` : m.district}</span>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .search {
    position: relative;
    margin: 0.6rem 0 1rem;
    max-width: 28rem;
  }
  input {
    width: 100%;
    padding: 0.55rem 0.8rem;
    font-size: 1rem;
    border: 1px solid #d8d0c0;
    border-radius: 8px;
    background: #fffdf9;
  }
  .hits {
    position: absolute;
    z-index: 5;
    left: 0;
    right: 0;
    margin: 0.2rem 0 0;
    padding: 0.25rem;
    list-style: none;
    background: #fffdf9;
    border: 1px solid #d8d0c0;
    border-radius: 8px;
    box-shadow: 0 6px 18px rgba(43, 39, 34, 0.12);
  }
  .hits button {
    display: block;
    width: 100%;
    text-align: left;
    padding: 0.4rem 0.6rem;
    border: 0;
    background: none;
    font-size: 0.95rem;
    cursor: pointer;
    border-radius: 6px;
  }
  .hits button:hover {
    background: #f3ede2;
  }
  .hits span {
    color: #898781;
    font-size: 0.85rem;
    margin-left: 0.4rem;
  }
</style>
