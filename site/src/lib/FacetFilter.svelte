<script>
  /**
   * Filter input with facet typeahead: suggests facet keys while a bare word
   * is being typed ("dis" → "district:"), and values once a facet is active
   * ("district:sono" → "sonoma valley unified"). Facet values may contain
   * spaces — every word after "key:" belongs to that facet until the next key,
   * so the suggestion fragment is everything after the LAST facet key.
   * Pools are built from `items` rows ({county, district, kind, name, flags}).
   */
  import { NUM_FACETS, NUM_FACET_SUGGEST, norm } from '$lib/facets.js';

  let { items = [], query = $bindable(''), placeholder = 'Filter…' } = $props();

  const FACET_KEY_RE = new RegExp(
    `(^|\\s)(level|kind|county|district|type|is|${Object.keys(NUM_FACETS).join('|')}):`,
    'gi'
  );
  let sugOpen = $state(false);
  let sugIdx = $state(0);

  let facetPools = $derived.by(() => {
    const county = new Set();
    const district = new Set();
    const is = new Set();
    for (const it of items ?? []) {
      if (it.county) county.add(it.county);
      if (it.kind === 'school' && it.district) district.add(it.district);
      else if (it.kind === 'district') district.add(it.name);
      for (const f of it.flags ?? []) is.add(f);
    }
    const mk = (vals) => [...vals].sort().map((v) => ({ raw: v, n: norm(v).trim() }));
    return {
      county: mk(county),
      district: mk(district),
      is: mk(is),
      level: mk(['elementary', 'middle', 'high', 'k-12', 'preschool', 'adult', 'other']),
      kind: mk(['school', 'district', 'county'])
    };
  });

  let suggestions = $derived.by(() => {
    if (!items?.length) return [];
    const q = query;
    FACET_KEY_RE.lastIndex = 0;
    let last = null;
    let m;
    while ((m = FACET_KEY_RE.exec(q))) last = m;
    if (last) {
      const key = last[2].toLowerCase() === 'type' ? 'level' : last[2].toLowerCase();
      if (NUM_FACETS[key]) return []; // numeric facet: user types >n / <n
      const head = q.slice(0, last.index + last[1].length) + key + ':';
      const frag = norm(q.slice(last.index + last[0].length)).trim();
      const pool = facetPools[key] ?? [];
      if (pool.some((v) => v.n === frag)) return []; // value fully typed
      return pool
        .filter((v) => v.n.includes(frag))
        .slice(0, 8)
        .map((v) => ({ label: v.n, next: head + v.n + ' ' }));
    }
    const t = q.match(/(^|\s)([a-z_]{2,})$/i);
    if (t) {
      const frag = t[2].toLowerCase();
      return [
        ...Object.keys(facetPools)
          .filter((k) => k.startsWith(frag) && k !== frag)
          .map((k) => ({
            label: k + ':',
            hint: 'filter by ' + k,
            next: q.slice(0, t.index + t[1].length) + k + ':'
          })),
        ...NUM_FACET_SUGGEST.filter((k) => k.startsWith(frag) && k !== frag).map((k) => ({
          label: k + ':',
          hint: `numeric — e.g. ${k}:<150 or ${k}:>20`,
          next: q.slice(0, t.index + t[1].length) + k + ':'
        }))
      ];
    }
    return [];
  });

  function pickSuggestion(s) {
    query = s.next;
    sugIdx = 0;
  }

  function onFilterKey(e) {
    if (!sugOpen || !suggestions.length) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      sugIdx = (sugIdx + 1) % suggestions.length;
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      sugIdx = (sugIdx - 1 + suggestions.length) % suggestions.length;
    } else if (e.key === 'Enter') {
      e.preventDefault();
      pickSuggestion(suggestions[Math.min(sugIdx, suggestions.length - 1)]);
    } else if (e.key === 'Escape') {
      sugOpen = false;
    }
  }
</script>

<div class="filterwrap">
  <input
    class="filter"
    {placeholder}
    bind:value={query}
    aria-label="Filter table"
    aria-expanded={sugOpen && suggestions.length > 0}
    oninput={() => {
      sugOpen = true;
      sugIdx = 0;
    }}
    onfocus={() => (sugOpen = true)}
    onblur={() => (sugOpen = false)}
    onkeydown={onFilterKey}
  />
  {#if sugOpen && suggestions.length}
    <ul class="sugs" role="listbox" aria-label="Filter suggestions">
      {#each suggestions as s, i (s.label)}
        <li role="option" aria-selected={i === sugIdx}>
          <button
            class:sel={i === sugIdx}
            tabindex="-1"
            onmousedown={(e) => {
              e.preventDefault();
              pickSuggestion(s);
            }}
          >
            {s.label}{#if s.hint}<span class="sughint">{s.hint}</span>{/if}
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .filterwrap {
    position: relative;
    flex: 1 1 380px;
  }
  .filter {
    width: 100%;
    padding: 0.55rem 0.8rem;
    font-size: 0.97rem;
    border: 1px solid #d8d0c0;
    border-radius: 8px;
    background: #fffdf9;
  }
  .sugs {
    position: absolute;
    top: calc(100% + 3px);
    left: 0;
    right: 0;
    z-index: 20;
    margin: 0;
    padding: 0.25rem;
    list-style: none;
    background: #fffdf9;
    border: 1px solid #d8d0c0;
    border-radius: 8px;
    box-shadow: 0 6px 18px rgba(43, 39, 34, 0.12);
    max-height: 280px;
    overflow-y: auto;
  }
  .sugs button {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 0.8rem;
    width: 100%;
    text-align: left;
    border: none;
    background: none;
    font: inherit;
    font-size: 0.92rem;
    padding: 0.35rem 0.6rem;
    border-radius: 6px;
    cursor: pointer;
    color: #2b2722;
  }
  .sugs button.sel,
  .sugs button:hover {
    background: #f0e8d9;
  }
  .sughint {
    color: #898781;
    font-size: 0.8rem;
  }
</style>
