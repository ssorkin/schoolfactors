<script>
  import { onMount } from 'svelte';
  import 'leaflet/dist/leaflet.css';
  import { TYPE_COLOR } from '$lib/maptypes.js';

  /**
   * Leaflet dot map. `points`: [{ll: [lat, lon], cds, kind, name, type, popup}].
   * Canvas renderer; redraws are throttled (leading edge) so the map tracks
   * facet sliders live while they're dragged. Marker radius scales with zoom.
   * Auto-fits to the shown points until the user pans/zooms by hand; the Fit
   * button (and a change of `fitKey`, e.g. switching kinds) re-engages it.
   */
  let { points = [], visible = true, fitKey = '' } = $props();

  let el;
  let L, map, layer;
  let cur = [];
  let timer;
  let lastDraw = 0;
  let locked = false; // user has panned/zoomed manually — stop auto-fitting
  let fitting = false; // ignore move/zoom events we cause ourselves

  onMount(async () => {
    L = (await import('leaflet')).default;
    map = L.map(el, { preferCanvas: true }).setView([37.4, -119.7], 6);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    layer = L.layerGroup().addTo(map);
    map.on('zoomstart movestart', () => {
      if (!fitting) locked = true;
    });
    map.on('zoomend', () => draw()); // re-radius markers for the new zoom
    cur = points;
    draw();
    maybeFit();
    return () => map.remove();
  });

  const BASE_RADIUS = { school: 4, district: 5.5, county: 8 };

  function radius(kind) {
    const mult = Math.min(3, Math.max(0.8, 1 + (map.getZoom() - 6) * 0.25));
    return (BASE_RADIUS[kind] ?? 4) * mult;
  }

  function draw() {
    if (!layer) return;
    layer.clearLayers();
    for (const p of cur) {
      const m = L.circleMarker(p.ll, {
        radius: radius(p.kind),
        color: '#ffffff',
        weight: 0.7,
        fillColor: TYPE_COLOR[p.type] ?? TYPE_COLOR.regular,
        fillOpacity: 0.85
      });
      m.bindPopup(p.popup, { maxWidth: 300 });
      layer.addLayer(m);
    }
  }

  function fit() {
    if (!map || !cur.length) return;
    fitting = true;
    map.fitBounds(L.latLngBounds(cur.map((p) => p.ll)), {
      animate: false,
      padding: [24, 24],
      maxZoom: 12
    });
    setTimeout(() => (fitting = false), 0);
  }

  function maybeFit() {
    if (!locked) fit();
  }

  // Leading-edge throttle: an idle map redraws immediately; during a slider
  // drag it redraws every ~120ms instead of waiting for the drag to pause.
  function schedule() {
    const wait = Math.max(0, 120 - (Date.now() - lastDraw));
    clearTimeout(timer);
    timer = setTimeout(() => {
      lastDraw = Date.now();
      draw();
      maybeFit();
    }, wait);
  }

  $effect(() => {
    cur = points;
    schedule();
  });

  $effect(() => {
    fitKey; // a new kind is a new map — re-engage auto-fit
    locked = false;
    schedule();
  });

  $effect(() => {
    if (visible && map) setTimeout(() => map.invalidateSize(), 0);
  });
</script>

<div class="wrap">
  <div class="map" bind:this={el}></div>
  <button
    class="fitbtn"
    title="Zoom to fit the shown entities (and keep auto-fitting as filters change)"
    onclick={() => {
      locked = false;
      fit();
    }}
  >
    ⤢ Fit
  </button>
</div>

<style>
  .wrap {
    position: relative;
    flex: 1;
    min-width: 0;
    display: flex;
  }
  .map {
    flex: 1;
    min-width: 0;
    height: 72vh;
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
