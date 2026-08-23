<script>
  import { onMount } from 'svelte';
  import 'leaflet/dist/leaflet.css';
  import { CLASS_COLOR, CLASS_LABEL, FLOW_METRICS, NO_DATA } from './metrics.js';
  import { getBoundaries, getIndex } from './data.js';

  /**
   * Statewide district-polygon choropleth (state mode) / single-district focus map
   * (detail mode). Copies the proven DistrictMap idioms: layers cached per level
   * file with a create-once promise guard, metric values joined by geoid at render
   * time (never baked into the geojson), setStyle recolor on metric change,
   * canvas renderer, pan-lock with a Fit button.
   *
   * Band framing keeps the elementary/secondary overlap honest: "Elementary
   * grades" = unified + elementary layers (a true partition of the state),
   * "High school grades" = unified + secondary. The unified layer is built once
   * and shared by both bands.
   */
  let {
    mode = 'state', // 'state' | 'detail'
    metric = $bindable('net_import'),
    band = $bindable('k8'), // 'k8' -> u+e, 'hs' -> u+h
    yearIdx = $bindable(-1), // -1 = latest; index into index.vintages otherwise
    focusGeoid = null, // detail mode: highlighted district
    neighbors = [], // detail mode: geoids keeping full choropleth color
    schools = [], // detail mode: [[cds, name, class, lat, lon, enr, spark, sited]]
    showControls = true,
    height = '72vh',
    onmapready = null
  } = $props();

  const BAND_LEVELS = { k8: ['u', 'e'], hs: ['u', 'h'] };
  const BAND_LABEL = { k8: 'Elementary grades', hs: 'High school grades' };
  const DTYPE_WORD = { u: 'unified district', e: 'elementary district', h: 'high school district', c: 'county' };

  let el;
  let L, map, markerLayer;
  const polyLayers = {}; // level file -> L.geoJSON, cached across band toggles
  const layerPromises = {};
  let showToken = 0;
  let ready = $state(false);
  let loading = $state(false);
  let index = $state(null); // resolved getIndex()
  let locked = false;
  let fitting = false;

  let m = $derived(FLOW_METRICS[metric]);
  let neighborSet = $derived(new Set(neighbors));
  let vintageLabel = $derived.by(() => {
    if (!index || yearIdx < 0 || !m.series) return null;
    const v = index.vintages[yearIdx];
    return `${v - 4}–${v}`;
  });

  const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;');

  function rowFor(geoid) {
    return index?.byGeoid.get(geoid) ?? null;
  }

  function fillFor(geoid) {
    const row = rowFor(geoid);
    if (!row) return NO_DATA;
    if (m.moeGate?.(row)) return NO_DATA;
    return m.color(m.value(row, yearIdx));
  }

  function styleFeature(feature) {
    const g = feature.properties.g;
    if (mode === 'detail') {
      if (g === focusGeoid) {
        return { fillColor: fillFor(g), fillOpacity: 0.5, color: '#211d18', weight: 2.5 };
      }
      if (neighborSet.has(g)) {
        return { fillColor: fillFor(g), fillOpacity: 0.5, color: '#ffffff', weight: 1 };
      }
      return { fillColor: NO_DATA, fillOpacity: 0.12, color: '#c9c2b4', weight: 0.7 };
    }
    return { fillColor: fillFor(g), fillOpacity: 0.55, color: '#ffffff', weight: 1 };
  }

  function statRows(rows) {
    const body = rows
      .filter(([, v]) => v != null)
      .map(([k, v]) => `<tr><td>${k}</td><td class="num">${v}</td></tr>`)
      .join('');
    return body ? `<table class="stats">${body}</table>` : '';
  }

  function polygonPopup(geoid) {
    const row = rowFor(geoid);
    if (!row) return '<b>No data</b> for this area';
    const lines = [`<b>${esc(row.name)}</b>`, esc(DTYPE_WORD[row.dtype] ?? '')];
    const v = m.value(row, yearIdx);
    lines.push(`${esc(m.short)}: <b>${m.fmt(v)}</b>${m.moeGate?.(row) ? ' (est., wide margin)' : ''}`);
    const net = row.net_rate;
    lines.push(
      statRows([
        ['Resident public-school children', row.res?.toLocaleString()],
        ['Seats at schools located here', row.seats?.toLocaleString()],
        [
          'Net import rate (latest, est.)',
          net == null
            ? null
            : `${net > 0 ? '+' : ''}${(net * 100).toFixed(1)}% ± ${((row.net_moe ?? 0) * 100).toFixed(1)}`
        ]
      ])
    );
    if (row.cds && row.dtype !== 'c') {
      if (row.net_rate != null) {
        lines.push(`<a href="/enrollment/district/${row.cds}">Enrollment flows →</a>`);
      }
      if (row.std) lines.push(`<a href="/district/${row.cds}">Standard district page →</a>`);
    } else if (row.cds) {
      lines.push(`<a href="/enrollment/county/${row.cds}">County enrollment page →</a>`);
    }
    return lines.filter(Boolean).join('<br>');
  }

  async function showBand(b) {
    if (!map || !index) return;
    const token = ++showToken;
    const want = BAND_LEVELS[b];
    loading = want.some((lvl) => !polyLayers[lvl]);
    for (const lvl of want) {
      layerPromises[lvl] ??= getBoundaries(lvl).then((fc) =>
        L.geoJSON(fc, {
          style: styleFeature,
          onEachFeature: (f, layer) =>
            layer.on('click', (e) => {
              L.popup({ maxWidth: 300 })
                .setLatLng(e.latlng)
                .setContent(polygonPopup(f.properties.g))
                .openOn(map);
            })
        })
      );
    }
    const built = await Promise.all(want.map((lvl) => layerPromises[lvl]));
    if (token !== showToken) return; // superseded by a newer toggle
    want.forEach((lvl, i) => (polyLayers[lvl] = built[i]));
    loading = false;
    for (const [lvl, layer] of Object.entries(polyLayers)) {
      if (want.includes(lvl)) {
        if (!map.hasLayer(layer)) layer.addTo(map);
        layer.setStyle(styleFeature);
        layer.bringToBack();
      } else if (map.hasLayer(layer)) {
        map.removeLayer(layer);
      }
    }
    if (mode === 'detail') fitFocus();
  }

  function schoolPopup(s) {
    const [cds, name, cls, , , enr, , sited, hasPage] = s;
    const lines = [`<b>${esc(name ?? cds)}</b>`, esc(CLASS_LABEL[cls] ?? cls)];
    if (sited && sited !== 'pip' && sited !== 'admin') {
      lines.push(`sited by ${esc(sited)}`);
    }
    lines.push(statRows([['Enrolled (latest)', enr?.toLocaleString()]]));
    if (hasPage) lines.push(`<a href="/school/${cds}">School page →</a>`);
    return lines.filter(Boolean).join('<br>');
  }

  function drawMarkers() {
    if (!markerLayer) return;
    markerLayer.clearLayers();
    if (mode !== 'detail') return;
    for (const s of schools) {
      const [, , cls, lat, lon] = s;
      if (lat == null || lon == null) continue;
      const mk = L.circleMarker([lat, lon], {
        radius: 4.5,
        color: '#ffffff',
        weight: 0.9,
        fillColor: CLASS_COLOR[cls] ?? '#52514e',
        fillOpacity: 0.95
      });
      mk.bindPopup(schoolPopup(s), { maxWidth: 300 });
      markerLayer.addLayer(mk);
    }
  }

  function fitFocus() {
    // Fit the focus polygon, or (county pages: no focus) the highlighted set.
    let bounds = null;
    for (const layer of Object.values(polyLayers)) {
      if (!map.hasLayer(layer)) continue;
      for (const sub of layer.getLayers()) {
        const g = sub.feature?.properties?.g;
        if (focusGeoid ? g === focusGeoid : neighborSet.has(g)) {
          bounds = bounds ? bounds.extend(sub.getBounds()) : sub.getBounds();
          if (focusGeoid) break;
        }
      }
    }
    if (bounds) {
      fitting = true;
      map.fitBounds(bounds, { animate: false, padding: [16, 16] });
      setTimeout(() => (fitting = false), 0);
    }
  }

  function fit() {
    if (!map) return;
    fitting = true;
    if (mode === 'detail') {
      fitFocus();
    } else {
      map.setView([37.4, -119.7], 6, { animate: false });
    }
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
    el._leafletMap = map; // test hook: lets headless checks drive the view
    map.on('zoomstart movestart', () => {
      if (!fitting) locked = true;
    });
    map.setView([37.4, -119.7], 6);
    index = await getIndex();
    ready = true; // the ready-gated $effect below performs the initial showBand
    drawMarkers();
    onmapready?.(map);
    return () => map.remove();
  });

  $effect(() => {
    if (ready) showBand(band);
  });
  $effect(() => {
    metric;
    yearIdx;
    if (ready) {
      for (const layer of Object.values(polyLayers)) {
        if (map.hasLayer(layer)) layer.setStyle(styleFeature);
      }
    }
  });
  $effect(() => {
    schools;
    if (ready) drawMarkers();
  });
</script>

{#if showControls}
  <div class="controls">
    <div class="seg" role="group" aria-label="Grade band">
      {#each ['k8', 'hs'] as b}
        <button class:on={band === b} onclick={() => (band = b)}>
          {BAND_LABEL[b]}
        </button>
      {/each}
    </div>
    <label class="metric">
      Color districts by
      <select bind:value={metric}>
        {#each Object.entries(FLOW_METRICS) as [key, mm]}
          <option value={key}>{mm.label}</option>
        {/each}
      </select>
    </label>
    {#if m.series && index}
      <label class="year">
        Window
        <input
          type="range"
          min="0"
          max={index.vintages.length - 1}
          value={yearIdx < 0 ? index.vintages.length - 1 : yearIdx}
          oninput={(e) => {
            const i = +e.currentTarget.value;
            yearIdx = i === index.vintages.length - 1 ? -1 : i;
          }}
        />
        <span class="ylabel">{vintageLabel ?? 'latest'}</span>
      </label>
    {/if}
    {#if loading}<span class="loading">loading boundaries…</span>{/if}
  </div>
{/if}

<div class="wrap">
  <div class="map" bind:this={el} style="height: {height}"></div>
  <button
    class="fitbtn"
    title={mode === 'detail' ? 'Zoom back to the district' : 'Zoom back to California'}
    onclick={() => {
      locked = false;
      fit();
    }}
  >
    ⤢ Fit
  </button>
</div>

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
    max-width: 340px;
  }
  .year {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
  }
  .year input {
    width: 150px;
  }
  .ylabel {
    font-variant-numeric: tabular-nums;
    color: #52514e;
    min-width: 5.5em;
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
  .map :global(.leaflet-popup-content table.stats) {
    border-collapse: collapse;
    margin: 0.15rem 0;
  }
  .map :global(.leaflet-popup-content .stats td) {
    padding: 0 0 0.05rem;
    color: #52514e;
  }
  .map :global(.leaflet-popup-content .stats td.num) {
    text-align: right;
    padding-left: 0.9rem;
    font-variant-numeric: tabular-nums;
    color: #211d18;
    font-weight: 600;
  }
</style>
