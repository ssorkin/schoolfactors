// Marker shapes encode school level on every map: circle = elementary,
// square = middle, triangle = high, diamond = other (K-12 spans, preschool,
// adult). Color stays on school type / percentile — shape is an independent,
// CVD-safe channel.
//
// Both maps render markers on Leaflet's canvas renderer, whose CircleMarker
// only draws circles; shapeMarker() subclasses it and draws the polygon
// directly on the renderer's context (mirroring L.Canvas._updateCircle),
// keeping canvas performance and CircleMarker's hit-testing/popup behavior.

export const LEVEL_SHAPE = {
  e: 'circle',
  elementary: 'circle',
  m: 'square',
  middle: 'square',
  h: 'triangle',
  high: 'triangle'
};

export const SHAPE_GLYPH = { circle: '●', square: '■', triangle: '▲', diamond: '◆' };
export const SHAPE_LEVEL_LABEL = {
  circle: 'elementary',
  square: 'middle',
  triangle: 'high',
  diamond: 'other/K-12'
};

export function levelShape(level, kind = 'school') {
  if (kind !== 'school') return 'circle';
  return LEVEL_SHAPE[level] ?? 'diamond';
}

// Path builders sized so each shape's visual weight roughly matches a circle
// of the same radius.
const DRAW = {
  square(ctx, p, r) {
    const s = r * 0.92;
    ctx.rect(p.x - s, p.y - s, 2 * s, 2 * s);
  },
  triangle(ctx, p, r) {
    const s = r * 1.25;
    ctx.moveTo(p.x, p.y - s);
    ctx.lineTo(p.x + s * 0.9, p.y + s * 0.65);
    ctx.lineTo(p.x - s * 0.9, p.y + s * 0.65);
    ctx.closePath();
  },
  diamond(ctx, p, r) {
    const s = r * 1.2;
    ctx.moveTo(p.x, p.y - s);
    ctx.lineTo(p.x + s, p.y);
    ctx.lineTo(p.x, p.y + s);
    ctx.lineTo(p.x - s, p.y);
    ctx.closePath();
  }
};

const classCache = new WeakMap(); // Leaflet module -> {shape: MarkerClass}

export function shapeMarker(L, latlng, options, shape = 'circle') {
  if (shape === 'circle' || !DRAW[shape]) return L.circleMarker(latlng, options);
  let classes = classCache.get(L);
  if (!classes) {
    classes = {};
    classCache.set(L, classes);
  }
  if (!classes[shape]) {
    const draw = DRAW[shape];
    classes[shape] = L.CircleMarker.extend({
      _updatePath() {
        const renderer = this._renderer;
        const ctx = renderer && renderer._ctx;
        if (!ctx) {
          // SVG renderer fallback: plain circle rather than nothing.
          renderer._updateCircle(this);
          return;
        }
        if (!renderer._drawing || this._empty()) return;
        ctx.beginPath();
        draw(ctx, this._point, Math.max(Math.round(this._radius), 1));
        renderer._fillStroke(ctx, this);
      }
    });
  }
  return new classes[shape](latlng, options);
}
