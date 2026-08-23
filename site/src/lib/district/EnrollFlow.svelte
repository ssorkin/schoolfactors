<script>
  /**
   * Two-column flow (Sankey-style) reconciliation for one geography and one ACS
   * vintage: resident children 5-17 by enrollment status (left) against
   * census-day public-school enrollment counted inside the geography (right).
   * The left "TK, 18+ & survey gap" node is the state-calibrated universe
   * mismatch; the violet "elsewhere" node is the apparent net flow of resident
   * public-school children counted outside the geography. Values are stocks
   * reconciled by accounting, not student-level flows.
   */
  let {
    title = '',
    unitLabel = '', // right-hand enrolled node, e.g. "LAUSD-authorized schools"
    // {publicK, privateK, notEnr, mismatchIn, toUnit, elsewhere, importsIn?}
    // importsIn: net students imported from other districts (importer pages) —
    // drawn as a left node flowing into the unit, since they are seated locally
    // but are not residents.
    f = null,
    scale = 0.0005 // px per child, shared across a pair for honest comparison
  } = $props();

  const W = 404;
  const PADT = 16;
  const PADB = 10;
  const GAP = 8; // px between stacked nodes
  const XL = 150; // left node column
  const XR = 224; // right node column
  const NODE_W = 12;

  const C = {
    public: '#2a78d6',
    private: '#8d8880',
    not: '#b5aea1',
    mismatch: '#d8d4cc',
    unit: '#eb6834',
    elsewhere: '#4a3aa7',
    imports: '#1c5cab',
    ribbon: '#9a958c'
  };

  const px = (v) => v * scale;
  const fmtK = (v) => `${Math.round(v / 1000).toLocaleString()}k`;
  const fmtN = (v) => Math.round(v).toLocaleString();

  // Node layout: [key, label, value, color]; left stack then right stack.
  let L = $derived.by(() => {
    if (!f) return null;
    const importsIn = f.importsIn ?? 0;
    const left = [
      ['imports', 'Other districts (net)', importsIn, C.imports],
      ['mismatch', 'TK, 18+ & survey gap', f.mismatchIn, C.mismatch],
      ['public', 'Public school', f.publicK, C.public],
      ['private', 'Private school', f.privateK, C.private],
      ['not', 'Not enrolled', f.notEnr, C.not]
    ];
    const right = [
      ['unit', unitLabel, f.toUnit + f.mismatchIn + importsIn, C.unit],
      ['elsewhere', 'Elsewhere (apparent)', f.elsewhere, C.elsewhere],
      ['private', 'Private school', f.privateK, C.private],
      ['not', 'Not enrolled', f.notEnr, C.not]
    ];
    const place = (nodes) => {
      let y = PADT;
      return nodes
        .filter(([, , v]) => v > 0.5)
        .map(([key, label, v, color]) => {
          const h = Math.max(px(v), 1.5);
          const n = { key, label, v, color, y0: y, y1: y + h };
          y += h + GAP;
          return n;
        });
    };
    const l = place(left);
    const r = place(right);
    const H = Math.max(...[...l, ...r].map((n) => n.y1)) + PADB;

    // Ribbons: (leftKey, rightKey, value); offsets tracked per node so spans nest.
    const specs = [
      ['imports', 'unit', importsIn],
      ['mismatch', 'unit', f.mismatchIn],
      ['public', 'unit', f.toUnit],
      ['public', 'elsewhere', f.elsewhere],
      ['private', 'private', f.privateK],
      ['not', 'not', f.notEnr]
    ];
    const offL = Object.fromEntries(l.map((n) => [n.key, n.y0]));
    const offR = Object.fromEntries(r.map((n) => [n.key, n.y0]));
    const mid = (XL + NODE_W + XR) / 2;
    const ribbons = [];
    for (const [lk, rk, v] of specs) {
      if (v <= 0.5 || !(lk in offL) || !(rk in offR)) continue;
      const h = Math.max(px(v), 1.5);
      const a0 = offL[lk];
      const b0 = offR[rk];
      offL[lk] += h;
      offR[rk] += h;
      const x0 = XL + NODE_W;
      ribbons.push({
        lk,
        rk,
        v,
        d:
          `M${x0},${a0} C${mid},${a0} ${mid},${b0} ${XR},${b0}` +
          `L${XR},${b0 + h} C${mid},${b0 + h} ${mid},${a0 + h} ${x0},${a0 + h}Z`
      });
    }
    return { l, r, H, ribbons };
  });

  let hover = $state(null);
  const RIBBON_TEXT = {
    'imports:unit':
      'net students seated in these schools beyond what resident children account ' +
      'for — apparent net import from other districts (modeled, not observed)',
    'mismatch:unit':
      'enrollment outside the census 5–17 universe: TK 4-year-olds, 18+ seniors, ' +
      'and survey error — sized by the statewide census-vs-CDE gap',
    'public:unit': 'resident children counted in these schools (apparent)',
    'public:elsewhere':
      'resident public-school children not counted in these schools — apparent net ' +
      'enrollment across the boundary',
    'private:private': 'resident children in private school',
    'not:not': 'resident children not enrolled in school'
  };
</script>

{#if L}
  <div class="wrap">
    <p class="title">{title}</p>
    <svg
      viewBox="0 0 {W} {L.H}"
      role="img"
      aria-label={title}
      onmouseleave={() => (hover = null)}
    >
      {#each L.ribbons as rb}
        <path
          d={rb.d}
          fill={rb.rk === 'elsewhere' ? C.elsewhere : C.ribbon}
          fill-opacity={rb.rk === 'elsewhere' ? 0.55 : hover === `${rb.lk}:${rb.rk}` ? 0.42 : 0.22}
          onmouseenter={() => (hover = `${rb.lk}:${rb.rk}`)}
        />
      {/each}
      {#each L.l as n}
        <rect
          x={XL}
          y={n.y0}
          width={NODE_W}
          height={n.y1 - n.y0}
          rx="2"
          fill={n.color}
          fill-opacity={n.key === 'mismatch' ? 0.7 : 1}
        />
        <text x={XL - 7} y={(n.y0 + n.y1) / 2 + 4} text-anchor="end" class="nlabel">
          <tspan class="nname">{n.label}</tspan>
          <tspan class="nval">&#8201;{fmtK(n.v)}</tspan>
        </text>
      {/each}
      {#each L.r as n}
        <rect x={XR} y={n.y0} width={NODE_W} height={n.y1 - n.y0} rx="2" fill={n.color} />
        <text x={XR + NODE_W + 7} y={(n.y0 + n.y1) / 2 + 4} class="nlabel">
          <tspan class="nname">{n.label}</tspan>
          <tspan class="nval">&#8201;{fmtK(n.v)}</tspan>
        </text>
      {/each}
    </svg>
    <p class="caption">
      {#if hover && RIBBON_TEXT[hover]}
        {@const rb = L.ribbons.find((r) => `${r.lk}:${r.rk}` === hover)}
        <b>{fmtN(rb?.v ?? 0)}</b> — {RIBBON_TEXT[hover]}
      {:else}
        Left: resident children 5–17 (census). Right: where public-school
        enrollment is counted (CDE). Hover a band for detail.
      {/if}
    </p>
  </div>
{/if}

<style>
  .wrap {
    min-width: 0;
  }
  .title {
    font-size: 0.9rem;
    font-weight: 600;
    color: #2b2722;
    margin: 0 0 0.25rem;
  }
  svg {
    width: 100%;
    height: auto;
    display: block;
    background: #fcfcfb;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
  }
  .nlabel {
    font-size: 11px;
  }
  .nname {
    fill: #2b2722;
    font-weight: 600;
  }
  .nval {
    fill: #6f6a61;
  }
  .caption {
    font-size: 0.8rem;
    color: #52514e;
    min-height: 2.4em;
    margin: 0.3rem 0 0;
  }
</style>
