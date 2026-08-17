<script module>
  let indexCache = null;

  function norm(s) {
    return (s ?? '')
      .toLowerCase()
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/[^a-z0-9\s]/g, ' ');
  }
</script>

<script>
  import { dataUrl } from '$lib/data.js';
  import { goto } from '$app/navigation';

  let {
    placeholder = 'Find any California school or district…',
    onselect = null,
    kinds = null
  } = $props();
  let query = $state('');
  let items = $state(null);
  let cursor = $state(-1);

  async function ensureIndex() {
    if (!indexCache) {
      const raw = await (await fetch(dataUrl('/data/index.json'))).json();
      // Precompute normalized haystacks once for fast multi-token matching.
      indexCache = raw.map((it) => {
        const name = norm(it.name);
        return {
          ...it,
          _name: name,
          _words: name.split(/\s+/).filter(Boolean),
          _extra: norm((it.district ?? '') + ' ' + (it.county ?? ''))
        };
      });
    }
    items = indexCache;
  }

  // Multi-token typeahead: every token must match somewhere; rank name-word
  // prefixes above name substrings above district/county matches.
  let matches = $derived.by(() => {
    if (!items || query.trim().length < 2) return [];
    const tokens = norm(query).split(/\s+/).filter(Boolean);
    if (!tokens.length) return [];
    const scored = [];
    for (const it of items) {
      if (kinds && !kinds.includes(it.kind)) continue;
      let score = 0;
      let ok = true;
      for (const t of tokens) {
        if (it._words.some((w) => w.startsWith(t))) score += 3;
        else if (it._name.includes(t)) score += 2;
        else if (it._extra.includes(t)) score += 1;
        else {
          ok = false;
          break;
        }
      }
      if (!ok) continue;
      if (it._name.startsWith(norm(query).trim())) score += 4;
      scored.push([score, it]);
    }
    scored.sort((a, b) => b[0] - a[0] || a[1]._name.length - b[1]._name.length);
    return scored.slice(0, 12).map(([, it]) => it);
  });

  $effect(() => {
    matches; // reset the keyboard cursor whenever results change
    cursor = -1;
  });

  function open(it) {
    query = '';
    cursor = -1;
    if (onselect) {
      onselect(it);
    } else {
      goto(`/${it.kind}/${it.cds}`);
    }
  }

  function onkeydown(ev) {
    if (!matches.length) return;
    if (ev.key === 'ArrowDown') {
      ev.preventDefault();
      cursor = (cursor + 1) % matches.length;
    } else if (ev.key === 'ArrowUp') {
      ev.preventDefault();
      cursor = (cursor - 1 + matches.length) % matches.length;
    } else if (ev.key === 'Enter') {
      ev.preventDefault();
      open(matches[cursor >= 0 ? cursor : 0]);
    } else if (ev.key === 'Escape') {
      query = '';
      cursor = -1;
    }
  }
</script>

<div class="search">
  <input
    {placeholder}
    bind:value={query}
    onfocus={ensureIndex}
    oninput={ensureIndex}
    {onkeydown}
    aria-label={placeholder}
    role="combobox"
    aria-expanded={matches.length > 0}
    aria-autocomplete="list"
  />
  {#if matches.length}
    <ul class="hits" role="listbox">
      {#each matches as m, i (m.cds)}
        <li role="option" aria-selected={i === cursor}>
          <button class:cursor={i === cursor} onclick={() => open(m)} onmouseenter={() => (cursor = i)}>
            {m.name}
            <span>{m.kind === 'district' ? `district · ${m.county} County` : m.kind === 'county' ? 'county' : `${m.district} · ${m.county}`}</span>
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
    z-index: 20;
    left: 0;
    right: 0;
    margin: 0.2rem 0 0;
    padding: 0.25rem;
    list-style: none;
    background: #fffdf9;
    border: 1px solid #d8d0c0;
    border-radius: 8px;
    box-shadow: 0 6px 18px rgba(43, 39, 34, 0.12);
    max-height: 22rem;
    overflow-y: auto;
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
  .hits button:hover,
  .hits button.cursor {
    background: #f3ede2;
  }
  .hits span {
    color: #898781;
    font-size: 0.85rem;
    margin-left: 0.4rem;
  }
</style>
