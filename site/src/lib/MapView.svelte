<script>
  import { onMount } from 'svelte';
  import 'leaflet/dist/leaflet.css';
  import { TYPE_COLOR } from '$lib/maptypes.js';

  /**
   * Leaflet dot map. `points`: [{ll: [lat, lon], cds, kind, name, type, popup}].
   * Canvas renderer — ~10k circle markers redraw comfortably; redraws are
   * debounced because facet sliders stream input events.
   */
  let { points = [], visible = true } = $props();

  let el;
  let L, map, layer;
  let timer;

  onMount(async () => {
    L = (await import('leaflet')).default;
    map = L.map(el, { preferCanvas: true }).setView([37.4, -119.7], 6);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    layer = L.layerGroup().addTo(map);
    draw(points);
    return () => map.remove();
  });

  function draw(pts) {
    if (!layer) return;
    layer.clearLayers();
    for (const p of pts) {
      const m = L.circleMarker(p.ll, {
        radius: p.kind === 'school' ? 4 : p.kind === 'district' ? 5.5 : 8,
        color: '#ffffff',
        weight: 0.7,
        fillColor: TYPE_COLOR[p.type] ?? TYPE_COLOR.regular,
        fillOpacity: 0.85
      });
      m.bindPopup(p.popup, { maxWidth: 300 });
      layer.addLayer(m);
    }
  }

  $effect(() => {
    const pts = points;
    clearTimeout(timer);
    timer = setTimeout(() => draw(pts), 80);
  });

  $effect(() => {
    if (visible && map) setTimeout(() => map.invalidateSize(), 0);
  });
</script>

<div class="map" bind:this={el}></div>

<style>
  .map {
    flex: 1;
    min-width: 0;
    height: 72vh;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    background: #f6f1e7;
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
