<script>
  import { onMount } from 'svelte';
  import 'leaflet/dist/leaflet.css';
  import { TYPE_COLOR, entityType } from '$lib/maptypes.js';
  import { METRICS, NO_DATA } from './choropleth.js';
  import { getBoundaries } from './lausdData.js';
  import MapLegend from './MapLegend.svelte';

  /**
   * District attendance-area map: a choropleth over per-level boundary polygons
   * (E/M/H, lazily fetched and cached per level) with school points on top, styled
   * like the statewide MapView so markers read the same everywhere.
   *
   * `schools` are rows from /data/lausd/schools.json. The choropleth's `perf` metric
   * is NOT baked into the geojson — it joins each polygon to its school row by cds,
   * so polygon fills, marker colors, and popups always agree.
   */
  let {
    schools = [],
    level = $bindable('e'),
    metric = $bindable('perf'),
    metrics = ['perf'],
    showSchools = $bindable(true),
    schoolFilter = null,
    showControls = true,
    height = '68vh'
  } = $props();

  const LEVEL_LABEL = { e: 'Elementary', m: 'Middle', h: 'High' };

  let el;
  let L, map, markerLayer;
  const polyLayers = {}; // level -> L.geoJSON (cached across toggles)
  let ready = $state(false);
  let loadingLevel = $state(false);
  let locked = false;
  let fitting = false;

  let schoolByCds = $derived(new Map(schools.map((s) => [s.cds, s])));
  let shownSchools = $derived(
    showSchools ? (schoolFilter ? schools.filter(schoolFilter) : schools) : []
  );

  const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;');

  function fillFor(props) {
    const m = METRICS[metric];
    const school = props.cds ? schoolByCds.get(props.cds) : null;
    return m.color(m.value(props, school));
  }

  function styleFeature(feature) {
    return {
      fillColor: fillFor(feature.properties),
      fillOpacity: 0.55,
      color: '#ffffff',
      weight: 1
    };
  }

  function polygonPopup(props) {
    const m = METRICS[metric];
    const school = props.cds ? schoolByCds.get(props.cds) : null;
    const lines = [];
    if (props.name) {
      lines.push(`<b>${esc(props.name)}</b> attendance area`);
      if ((props.schools ?? []).length > 1) {
        const others = props.schools
          .slice(1)
          .map((s) => `<a href="/school/${s.cds}">${esc(s.name)}</a>`)
          .join(', ');
        lines.push(`Also serves: ${others}`);
      }
      lines.push(`${esc(m.label)}: ${m.fmt(m.value(props, school))}`);
      if (props.pop != null) lines.push(`${Number(props.pop).toLocaleString()} residents (2020)`);
      lines.push(`<a href="/school/${props.cds}">School page →</a>`);
    } else {
      lines.push('<b>Unassigned area</b> — no school resolves to this zone');
    }
    return lines.join('<br>');
  }

  function markerPopup(s) {
    const type = entityType({ kind: 'school', flags: s.flags });
    const lines = [`<b>${esc(s.name)}</b>`];
    const badges = [LEVEL_LABEL[s.level] ?? 'Other level'];
    if (type !== 'regular') badges.push(type);
    if (!s.has_boundary) badges.push('no attendance area');
    lines.push(badges.join(' · '));
    if (s.adj_pct != null) lines.push(METRICS.perf.fmt(s.adj_pct));
    if (s.enrollment != null) lines.push(`${s.enrollment.toLocaleString()} students`);
    lines.push(`<a href="/school/${s.cds}">School page →</a>`);
    return lines.join('<br>');
  }

  // One L.geoJSON per level, created exactly once even under concurrent calls
  // (a second concurrent create would orphan the first layer on the map).
  const layerPromises = {};
  let showToken = 0;

  async function showLevel(lvl) {
    if (!map) return;
    const token = ++showToken;
    loadingLevel = !polyLayers[lvl];
    layerPromises[lvl] ??= getBoundaries(lvl).then((fc) =>
      L.geoJSON(fc, {
        style: styleFeature,
        onEachFeature: (f, layer) =>
          layer.bindPopup(() => polygonPopup(f.properties), { maxWidth: 300 })
      })
    );
    polyLayers[lvl] = await layerPromises[lvl];
    if (token !== showToken) return; // superseded by a newer toggle
    loadingLevel = false;
    for (const [k, layer] of Object.entries(polyLayers)) {
      if (k === lvl) {
        if (!map.hasLayer(layer)) layer.addTo(map);
        layer.setStyle(styleFeature);
        layer.bringToBack();
      } else if (map.hasLayer(layer)) {
        map.removeLayer(layer);
      }
    }
  }

  function markerRadius() {
    return 4 * Math.min(3, Math.max(0.8, 1 + (map.getZoom() - 10) * 0.25));
  }

  function drawMarkers() {
    if (!markerLayer) return;
    markerLayer.clearLayers();
    for (const s of shownSchools) {
      if (!s.ll) continue;
      const m = L.circleMarker(s.ll, {
        radius: markerRadius(),
        color: '#ffffff',
        weight: 0.7,
        fillColor: TYPE_COLOR[entityType({ kind: 'school', flags: s.flags })],
        fillOpacity: 0.85
      });
      m.bindPopup(markerPopup(s), { maxWidth: 300 });
      markerLayer.addLayer(m);
    }
  }

  function fit() {
    if (!map) return;
    fitting = true;
    // LAUSD's extent (fixed: the boundary doesn't change with filters).
    map.fitBounds(
      [
        [33.7, -118.7],
        [34.4, -118.1]
      ],
      { animate: false, padding: [10, 10] }
    );
    setTimeout(() => (fitting = false), 0);
  }

  onMount(async () => {
    L = (await import('leaflet')).default;
    map = L.map(el, { preferCanvas: true });
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    markerLayer = L.layerGroup().addTo(map);
    map.on('zoomstart movestart', () => {
      if (!fitting) locked = true;
    });
    map.on('zoomend', drawMarkers);
    fit();
    ready = true; // the ready-gated $effect below performs the initial showLevel
    drawMarkers();
    return () => map.remove();
  });

  $effect(() => {
    if (ready) showLevel(level);
  });
  $effect(() => {
    metric;
    schoolByCds;
    if (ready) polyLayers[level]?.setStyle(styleFeature);
  });
  $effect(() => {
    shownSchools;
    if (ready) drawMarkers();
  });
</script>

{#if showControls}
  <div class="controls">
    <div class="seg" role="group" aria-label="Boundary level">
      {#each ['e', 'm', 'h'] as lvl}
        <button class:on={level === lvl} onclick={() => (level = lvl)}>
          {LEVEL_LABEL[lvl]}
        </button>
      {/each}
    </div>
    {#if metrics.length > 1}
      <label class="metric">
        Color areas by
        <select bind:value={metric}>
          {#each metrics as key}
            <option value={key}>{METRICS[key].label}</option>
          {/each}
        </select>
      </label>
    {/if}
    <label class="chk">
      <input type="checkbox" bind:checked={showSchools} /> Show schools
    </label>
    {#if loadingLevel}<span class="loading">loading boundaries…</span>{/if}
  </div>
{/if}

<div class="wrap">
  <div class="map" bind:this={el} style="height: {height}"></div>
  <button
    class="fitbtn"
    title="Zoom back to the whole district"
    onclick={() => {
      locked = false;
      fit();
    }}
  >
    ⤢ Fit
  </button>
</div>

<MapLegend {metric} {showSchools} />

<style>
  .controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.6rem 1.1rem;
    margin-bottom: 0.6rem;
    font-size: 0.88rem;
  }
  .seg {
    display: inline-flex;
    border: 1px solid #d7cfc0;
    border-radius: 8px;
    overflow: hidden;
  }
  .seg button {
    font: inherit;
    font-size: 0.85rem;
    font-weight: 550;
    border: none;
    background: #fff;
    color: #52514e;
    padding: 0.3rem 0.7rem;
    cursor: pointer;
  }
  .seg button + button {
    border-left: 1px solid #d7cfc0;
  }
  .seg button.on {
    background: #b0552f;
    color: #fff;
  }
  .metric select {
    font: inherit;
    font-size: 0.85rem;
    margin-left: 0.3rem;
    max-width: 320px;
  }
  .chk {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
  }
  .loading {
    color: #898781;
    font-size: 0.8rem;
  }
  .wrap {
    position: relative;
  }
  .map {
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    background: #f6f1e7;
  }
  .fitbtn {
    position: absolute;
    top: 82px;
    left: 11px;
    z-index: 1000;
    border: 2px solid rgba(0, 0, 0, 0.2);
    background: #fff;
    border-radius: 5px;
    font: inherit;
    font-size: 0.78rem;
    font-weight: 600;
    color: #333;
    padding: 0.2rem 0.45rem;
    cursor: pointer;
  }
  .fitbtn:hover {
    background: #f4f4f4;
  }
  .map :global(.leaflet-popup-content) {
    font-family: inherit;
    font-size: 0.82rem;
    line-height: 1.45;
    margin: 0.6rem 0.8rem;
  }
  .map :global(.leaflet-popup-content a) {
    color: #1c5cab;
  }
</style>
