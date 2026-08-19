<script>
  import { onMount } from 'svelte';
  import 'leaflet/dist/leaflet.css';
  import { NO_PCT_COLOR, entityType, pctColor } from '$lib/maptypes.js';
  import { levelShape, shapeMarker } from '$lib/mapshapes.js';
  import { METRICS, NO_DATA, ordinal } from './choropleth.js';
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
    showLegend = true,
    onmapready = null, // callback(map): lets a parent sync several instances
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
  // Markers follow the boundary toggle: the Elementary view shows elementary
  // schools, High shows high schools, etc. Schools spanning levels (K-12
  // combos, "other") show in every view, drawn as diamonds.
  let shownSchools = $derived.by(() => {
    if (!showSchools) return [];
    let out = schools.filter((s) => s.level === level || s.level === 'other');
    if (schoolFilter) out = out.filter(schoolFilter);
    return out;
  });

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

  // Compact metric line: "Similar Schools %ile: 24th" / "Child poverty: 32%".
  function metricLine(props, school) {
    const m = METRICS[metric];
    const v = m.value(props, school);
    if (metric === 'perf') {
      return `${esc(m.short)}: <b>${v == null ? 'no data' : ordinal(v)}</b>`;
    }
    return `${esc(m.short)}: <b>${m.fmt(v)}</b>`;
  }

  function statRows(rows) {
    const body = rows
      .filter(([, v]) => v != null)
      .map(([k, v]) => `<tr><td>${k}</td><td class="num">${v}</td></tr>`)
      .join('');
    return body ? `<table class="stats">${body}</table>` : '';
  }

  function polygonPopup(props) {
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
      lines.push(metricLine(props, school));
      const spct = (v) => (v == null ? null : `${v > 0 ? '+' : ''}${Math.round(v * 100)}%`);
      lines.push(
        statRows([
          ['Enrolled', school?.enrollment?.toLocaleString()],
          [
            props.ages ? `Residents ${props.ages[0]}–${props.ages[1]}` : null,
            props.students != null ? `~${Number(props.students).toLocaleString()}` : null
          ],
          ['All residents', props.pop != null ? Number(props.pop).toLocaleString() : null],
          ['School ’11→’21', spct(props.sch_chg)],
          ['Children ’10→’20', spct(props.kid_chg)]
        ])
      );
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
    if (s.adj_pct != null) {
      lines.push(`${METRICS.perf.short}: <b>${ordinal(s.adj_pct)}</b>`);
    }
    lines.push(statRows([['Enrolled', s.enrollment?.toLocaleString()]]));
    lines.push(`<a href="/school/${s.cds}">School page →</a>`);
    return lines.filter(Boolean).join('<br>');
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
        // Popup opens AT THE SCHOOL (not the click point), with a ring
        // highlighting which marker serves the clicked area.
        onEachFeature: (f, layer) =>
          layer.on('click', (e) => {
            const props = f.properties;
            const school = props.cds ? schoolByCds.get(props.cds) : null;
            const at = school?.ll ?? e.latlng;
            selectArea(layer);
            L.popup({ maxWidth: 300 })
              .setLatLng(at)
              .setContent(polygonPopup(props))
              .openOn(map);
          })
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

  // Clicking an attendance area darkens its border (the popup already opens at
  // the school, so no separate pin); clears when the popup closes.
  let selLayer = null;
  function clearSelection() {
    if (selLayer) {
      selLayer.setStyle(styleFeature(selLayer.feature));
      selLayer = null;
    }
  }
  function selectArea(layer) {
    clearSelection();
    selLayer = layer;
    layer.setStyle({ color: '#211d18', weight: 3 });
  }

  function drawMarkers() {
    if (!markerLayer) return;
    markerLayer.clearLayers();
    for (const s of shownSchools) {
      if (!s.ll) continue;
      // Fill = Similar Schools %ile (same ramp as the perf choropleth), so
      // choice schools with no attendance area show their score too; shape
      // still encodes level; type stays in the popup.
      const m = shapeMarker(
        L,
        s.ll,
        {
          radius: markerRadius(),
          color: '#ffffff',
          weight: 0.9,
          fillColor: s.adj_pct == null ? NO_PCT_COLOR : pctColor(s.adj_pct),
          fillOpacity: 0.95
        },
        levelShape(s.level)
      );
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
    el._leafletMap = map; // test hook: lets headless checks drive the view
    map.on('zoomstart movestart', () => {
      if (!fitting) locked = true;
    });
    map.on('zoomend', drawMarkers);
    map.on('popupclose', clearSelection);
    fit();
    ready = true; // the ready-gated $effect below performs the initial showLevel
    drawMarkers();
    onmapready?.(map);
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

{#if showLegend}
  <MapLegend {metric} {showSchools} {level} />
{/if}

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
