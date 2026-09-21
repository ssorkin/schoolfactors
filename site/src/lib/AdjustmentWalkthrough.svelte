<script>
  /**
   * The Similar Schools percentile, worked step by step for one entity:
   * raw level → expected level from the student mix (term by term) →
   * residual → shrinkage and 95% lower bound → rank of that lower bound
   * among the pool it was ranked in, drawn on the pool's histogram.
   *
   * `calc` is the export's adj_calc (see _adj_calc in analysis/export.py);
   * `pool` is adj_pool (the ranked lower bounds of every member of this
   * entity's percentile pool). Every number here is the one the pipeline
   * used — nothing is re-estimated client-side.
   */
  let { calc, pool = null, pct = null, kind = 'school', lastYear = null } = $props();

  const LABELS = {
    share_econ_dis: 'economically disadvantaged',
    share_black: 'Black / African American',
    share_asian: 'Asian',
    share_hispanic: 'Hispanic / Latino',
    share_white: 'White',
    share_el: 'English learners',
    share_swd: 'students with disabilities',
    share_parent_not_hs: 'parents without a high-school diploma',
    share_parent_college: 'parents with a college degree',
    share_parent_gradschool: 'parents with a graduate degree',
    log_tested: 'size (log of tests scored)'
  };

  const sgn = (v, digits = 2) => {
    if (v == null) return '—';
    const r = Math.abs(v).toFixed(digits);
    const zero = Number(r) === 0;
    return (zero ? '' : v > 0 ? '+' : '−') + r;
  };
  const pctStr = (v) => `${Math.round(v * 100)}%`;
  let kindPlural = $derived(kind === 'county' ? 'counties' : `${kind}s`);

  let terms = $derived(
    calc.terms.map((t) => ({
      ...t,
      label: LABELS[t.k] ?? t.k,
      isLog: t.k === 'log_tested',
      xStr:
        t.k === 'log_tested'
          ? `${(calc.tested ?? Math.round(Math.exp(t.x))).toLocaleString()} (ln ${t.x.toFixed(2)})`
          : pctStr(t.x),
      mStr:
        t.k === 'log_tested'
          ? `${Math.round(Math.exp(t.m)).toLocaleString()} (ln ${t.m.toFixed(2)})`
          : pctStr(t.m)
    }))
  );
  let maxAbsD = $derived(Math.max(0.05, ...terms.map((t) => Math.abs(t.d))));
  let sumD = $derived(terms.reduce((a, t) => a + t.d, 0));
  let ci = $derived(1.96 * calc.level_se);
  let postSd = $derived(Math.sqrt(calc.lambda) * calc.level_se);

  // --- pool histogram ---
  const W = 520;
  const H = 190;
  const M = { l: 12, r: 12, t: 34, b: 34 };
  const PW = W - M.l - M.r;
  let bins = $derived(pool?.bins ?? []);
  let maxC = $derived(Math.max(1, ...bins));
  let bw = $derived(bins.length ? PW / bins.length : 0);
  let x = $derived((v) => M.l + ((v - (pool?.lo ?? 0)) / ((pool?.w ?? 1) * Math.max(1, bins.length))) * PW);
  let y = $derived((c) => H - M.b - (c / maxC) * (H - M.t - M.b));
  let ownBin = $derived(
    pool ? Math.min(bins.length - 1, Math.max(0, Math.floor((calc.lcb - pool.lo) / pool.w))) : -1
  );
  let ownPx = $derived(pool ? Math.min(W - M.r - 2, Math.max(M.l + 2, x(calc.lcb))) : 0);
  const TICKS = [-1.5, -1, -0.5, 0, 0.5, 1, 1.5];
  let midrank = $derived(pool ? (100 * (pool.below + pool.tied / 2)) / pool.n : null);
</script>

<details class="calc">
  <summary>
    Show the calculation behind this {kind}'s Similar
    {kind === 'district' ? 'Districts' : kind === 'county' ? 'Counties' : 'Schools'} percentile
  </summary>

  <div class="steps">
    <section class="step">
      <h4><span class="n">1</span> Start from the raw level</h4>
      <p>
        <b class="val">{sgn(calc.level)}</b>
        <span class="ci">± {ci.toFixed(2)}</span> student SDs vs the state average, from
        a precision-weighted fit of this {kind}'s standardized scores that leans toward
        its latest years. This is the unshrunken estimate the adjustment model regresses;
        the tile above shows the same number after shrinkage toward the state mean.
      </p>
    </section>

    <section class="step">
      <h4><span class="n">2</span> Compute the level expected from the students tested</h4>
      <p class="lead">
        One statewide regression of every {kind}'s raw level on the mix of students it
        tests gives one coefficient per characteristic. Each row multiplies the coefficient
        by how far this {kind}'s share sits from the average {kind}'s share.
      </p>
      <div class="tablewrap">
        <table>
          <thead>
            <tr>
              <th>Characteristic</th>
              <th class="num">This {kind}</th>
              <th class="num">Avg {kind}</th>
              <th class="num" title="Coefficient from the statewide regression: change in expected level (SDs) per unit of the share (0→1), or per unit of log size">Coef.</th>
              <th class="num" title="Coefficient × (this − average)">Contribution</th>
              <th class="bar"></th>
            </tr>
          </thead>
          <tbody>
            <tr class="base">
              <td>Average-mix {kind} (baseline)</td>
              <td class="num"></td>
              <td class="num"></td>
              <td class="num"></td>
              <td class="num">{sgn(calc.baseline)}</td>
              <td class="bar"></td>
            </tr>
            {#each terms as t (t.k)}
              <tr>
                <td>{t.label}</td>
                <td class="num">{t.xStr}</td>
                <td class="num muted">{t.mStr}</td>
                <td class="num">{sgn(t.g, t.isLog ? 3 : 2)}</td>
                <td class="num" class:pos={t.d > 0.005} class:neg={t.d < -0.005}>{sgn(t.d)}</td>
                <td class="bar">
                  <svg viewBox="0 0 100 12" preserveAspectRatio="none" aria-hidden="true">
                    <line x1="50" x2="50" y1="0" y2="12" class="zero" />
                    <rect
                      x={t.d < 0 ? 50 + (t.d / maxAbsD) * 50 : 50}
                      y="2"
                      width={Math.abs(t.d / maxAbsD) * 50}
                      height="8"
                      class={t.d < 0 ? 'neg' : 'pos'}
                    />
                  </svg>
                </td>
              </tr>
            {/each}
            <tr class="sum">
              <td>Expected level for this mix</td>
              <td class="num"></td>
              <td class="num"></td>
              <td class="num"></td>
              <td class="num">{sgn(calc.baseline)} {sgn(sumD)} = <b>{sgn(calc.expected)}</b></td>
              <td class="bar"></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="fine">
        Shares are of tests scored, averaged over this {kind}'s years in the model.
        Race/ethnicity shares are relative to the omitted groups (Filipino, Pacific
        Islander, Native American, two or more races, not reported), so no single
        coefficient stands alone; only the sum is meaningful. The same equation in raw
        form: {sgn(calc.intercept)}
        {#each calc.terms as t (t.k)}
          {' '}{sgn(t.g, t.k === 'log_tested' ? 3 : 2)} × {t.k === 'log_tested' ? t.x.toFixed(2) : t.x.toFixed(3)}{/each}
        = {sgn(calc.expected)}.
      </p>
    </section>

    <section class="step">
      <h4><span class="n">3</span> Take the difference, then discount for noise</h4>
      <dl class="eq">
        <dt>Adjusted level (residual)</dt>
        <dd>{sgn(calc.level)} − ({sgn(calc.expected)}) = <b>{sgn(calc.resid)}</b></dd>
        <dt>Reliability λ</dt>
        <dd>
          {calc.lambda.toFixed(2)}
          <span class="fine">
            — the share of variation across {kindPlural} in this residual that is real rather
            than sampling noise, given this {kind}'s standard error of {calc.level_se.toFixed(3)}
          </span>
        </dd>
        <dt>Shrunken residual</dt>
        <dd>{calc.lambda.toFixed(2)} × {sgn(calc.resid)} = <b>{sgn(calc.resid_eb)}</b> <span class="fine">(the adjusted-level tile)</span></dd>
        <dt>Lower bound of its 95% band</dt>
        <dd>
          {sgn(calc.resid_eb)} − 1.96 × √{calc.lambda.toFixed(2)} × {calc.level_se.toFixed(3)}
          = {sgn(calc.resid_eb)} − {(1.96 * postSd).toFixed(3)} = <b>{sgn(calc.lcb)}</b>
        </dd>
      </dl>
      <p class="fine">
        Rankings use the lower bound, not the estimate, so an imprecise high estimate
        (typically a small {kind}) ranks below a precise, slightly lower one.
      </p>
    </section>

    <section class="step">
      <h4><span class="n">4</span> Rank the lower bound among {kindPlural} ranked the same way</h4>
      {#if pool && pct != null}
        <figure class="hist">
          <svg viewBox="0 0 {W} {H}" role="img"
            aria-label="Histogram of ranked lower bounds among {pool.label}, with this {kind}'s marked">
            {#each bins as c, i (i)}
              {#if c > 0}
                <rect
                  x={M.l + i * bw + 0.5}
                  y={y(c)}
                  width={bw - 1}
                  height={H - M.b - y(c)}
                  class="bar"
                  class:below={i < ownBin}
                  class:here={i === ownBin}
                />
              {/if}
            {/each}
            <line x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} class="base" />
            {#each TICKS as t (t)}
              {#if t >= pool.lo && t <= pool.lo + pool.w * bins.length}
                <line x1={x(t)} x2={x(t)} y1={H - M.b} y2={H - M.b + 4} class="base" />
                <text x={x(t)} y={H - M.b + 15} class="tick" text-anchor="middle">
                  {t > 0 ? `+${t}` : t}
                </text>
              {/if}
            {/each}
            <text x={W - M.r} y={H - 6} class="tick" text-anchor="end">
              lower bound of adjusted level, student SDs
            </text>
            <line x1={ownPx} x2={ownPx} y1={M.t - 14} y2={H - M.b} class="own" />
            <text
              x={ownPx}
              y={M.t - 18}
              class="ownlbl"
              text-anchor={ownPx > W - 120 ? 'end' : ownPx < 120 ? 'start' : 'middle'}
            >
              this {kind}: {sgn(calc.lcb)} → {pct}th percentile
            </text>
          </svg>
          <figcaption>
            The pool this {kind} is ranked in: every one of the {pool.n.toLocaleString()}
            {pool.label} with results in {lastYear ?? 'the latest year'} and reliability
            ≥ 0.70, placed by the lower bound of its adjusted level. Darker bars are below
            this {kind}; the rust bar holds it.
          </figcaption>
        </figure>
        <dl class="eq">
          <dt>Pool</dt>
          <dd>{pool.n.toLocaleString()} {pool.label}</dd>
          <dt>Below this {kind}</dt>
          <dd>{pool.below.toLocaleString()}</dd>
          <dt>Tied with it</dt>
          <dd>{pool.tied} <span class="fine">(this {kind} included; ties count half)</span></dd>
          <dt>Midrank percentile</dt>
          <dd>
            100 × ({pool.below.toLocaleString()} + {pool.tied}/2) ÷ {pool.n.toLocaleString()}
            = {midrank.toFixed(1)} → <b>{pct}</b>
            <span class="fine">(rounded, and clamped to 1–99)</span>
          </dd>
        </dl>
      {:else}
        <p>
          No percentile is shown for this {kind}. A percentile requires reliability ≥ 0.70
          (this {kind}: {calc.lambda.toFixed(2)}), test results in the latest statewide
          year (this {kind}'s data runs through {lastYear ?? '—'}), and a pool of at
          least 20 {kindPlural} of the same kind. The adjusted level above still stands on
          its own.
        </p>
      {/if}
    </section>
  </div>
  <p class="fine closing">
    Full method, including what the adjustment can and cannot account for, on the
    <a href="/methodology#similar-students">methodology page</a>; definitions in the
    <a href="/glossary#adj-percentile">glossary</a>. Like every adjusted number, the result
    is a comparison with {kindPlural} serving similar students, not a measure of quality.
  </p>
</details>

<style>
  .calc {
    margin: 0 0 1.2rem;
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    padding: 0.55rem 0.9rem;
    max-width: 52rem;
  }
  summary {
    cursor: pointer;
    font-weight: 650;
    color: #52514e;
    font-size: 0.92rem;
  }
  summary:hover {
    color: #b0552f;
  }
  .steps {
    margin-top: 0.6rem;
  }
  .step {
    padding: 0.55rem 0 0.7rem;
    border-top: 1px solid #f0ead9;
  }
  h4 {
    margin: 0 0 0.35rem;
    font-size: 0.95rem;
    color: #3d3c39;
  }
  .n {
    display: inline-block;
    width: 1.35rem;
    height: 1.35rem;
    line-height: 1.35rem;
    border-radius: 50%;
    background: #b0552f;
    color: #fff;
    font-size: 0.8rem;
    text-align: center;
    margin-right: 0.35rem;
  }
  p {
    margin: 0.3rem 0;
    font-size: 0.9rem;
    color: #52514e;
    max-width: 46rem;
  }
  .lead {
    margin-bottom: 0.5rem;
  }
  .val {
    color: #b0552f;
    font-size: 1.1rem;
  }
  .ci {
    color: #898781;
  }
  .fine {
    font-size: 0.78rem;
    color: #898781;
  }
  .closing {
    margin-top: 0.4rem;
    border-top: 1px solid #f0ead9;
    padding-top: 0.5rem;
  }
  .tablewrap {
    overflow-x: auto;
  }
  table {
    border-collapse: collapse;
    font-size: 0.85rem;
    width: 100%;
    max-width: 46rem;
  }
  th,
  td {
    padding: 0.22rem 0.45rem;
    border-bottom: 1px solid #f0ead9;
    text-align: left;
    white-space: nowrap;
  }
  th {
    font-weight: 600;
    color: #6f6a61;
    font-size: 0.78rem;
  }
  td.num,
  th.num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  td.muted {
    color: #898781;
  }
  td.pos {
    color: #006300;
  }
  td.neg {
    color: #d03b3b;
  }
  tr.base td,
  tr.sum td {
    font-weight: 600;
    color: #3d3c39;
  }
  tr.sum td {
    border-top: 2px solid #c3bcae;
    border-bottom: none;
  }
  .bar {
    width: 6.5rem;
    padding-left: 0.2rem;
  }
  td.bar svg {
    width: 100%;
    height: 12px;
    display: block;
  }
  td.bar .zero {
    stroke: #c3bcae;
    stroke-width: 1;
  }
  td.bar rect.pos {
    fill: #2a8a4a;
    fill-opacity: 0.55;
  }
  td.bar rect.neg {
    fill: #d03b3b;
    fill-opacity: 0.5;
  }
  .eq {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.25rem 0.9rem;
    margin: 0.4rem 0;
    font-size: 0.88rem;
    color: #52514e;
    max-width: 46rem;
  }
  .eq dt {
    color: #6f6a61;
  }
  .eq dd {
    margin: 0;
    font-variant-numeric: tabular-nums;
  }
  .eq b {
    color: #b0552f;
  }
  .hist {
    margin: 0.4rem 0 0.6rem;
  }
  .hist svg {
    width: 100%;
    height: auto;
    display: block;
    max-width: 46rem;
  }
  .hist .bar {
    fill: #2a78d6;
    fill-opacity: 0.2;
  }
  .hist .bar.below {
    fill-opacity: 0.55;
  }
  .hist .bar.here {
    fill: #b0552f;
    fill-opacity: 0.55;
  }
  .hist .base {
    stroke: #c3bcae;
  }
  .hist .tick {
    font-size: 10.5px;
    fill: #898781;
  }
  .hist .own {
    stroke: #b0552f;
    stroke-width: 2;
  }
  .hist .ownlbl {
    font-size: 11.5px;
    font-weight: 700;
    fill: #b0552f;
  }
  figcaption {
    font-size: 0.78rem;
    color: #898781;
    max-width: 46rem;
  }
  @media (max-width: 560px) {
    .eq {
      grid-template-columns: 1fr;
      gap: 0.05rem;
    }
    .eq dd {
      margin-bottom: 0.35rem;
    }
  }
</style>
