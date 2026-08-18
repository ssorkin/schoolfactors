<script>
  /**
   * Dual-thumb min/max range slider for one map facet. min/max may tighten to
   * the data currently shown while lo/hi keep the user's wider selection (so
   * re-widening the other filters restores it); the readout and active state
   * use the clamped view, matching where the thumbs actually sit.
   */
  let {
    label,
    tip = '',
    min,
    max,
    step = 1,
    lo = $bindable(),
    hi = $bindable(),
    fmt = (v) => v
  } = $props();

  let dlo = $derived(Math.min(Math.max(lo, min), max));
  let dhi = $derived(Math.max(Math.min(hi, max), min));
  let active = $derived(dlo > min || dhi < max);
</script>

<div class="facet" class:active>
  <div class="head">
    <span class="label" title={tip}>{label}</span>
    <span class="vals">{fmt(dlo)} – {fmt(dhi)}</span>
  </div>
  <div class="sliders">
    <input
      type="range"
      {min}
      {max}
      {step}
      bind:value={lo}
      oninput={() => {
        if (lo > hi) hi = lo;
      }}
      aria-label="{label} minimum"
    />
    <input
      type="range"
      {min}
      {max}
      {step}
      bind:value={hi}
      oninput={() => {
        if (hi < lo) lo = hi;
      }}
      aria-label="{label} maximum"
    />
  </div>
</div>

<style>
  .facet {
    padding: 0.35rem 0 0.15rem;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 0.8rem;
    color: #52514e;
  }
  .facet.active .label {
    color: #b0552f;
    font-weight: 650;
  }
  .vals {
    font-variant-numeric: tabular-nums;
    color: #898781;
    font-size: 0.76rem;
  }
  .sliders {
    position: relative;
    height: 20px;
  }
  .sliders::before {
    content: '';
    position: absolute;
    left: 0;
    right: 0;
    top: 9px;
    height: 3px;
    border-radius: 2px;
    background: #d8d0c0;
  }
  input[type='range'] {
    position: absolute;
    left: 0;
    top: 0;
    width: 100%;
    height: 20px;
    margin: 0;
    background: none;
    pointer-events: none;
    -webkit-appearance: none;
    appearance: none;
  }
  input[type='range']::-webkit-slider-runnable-track {
    background: transparent;
    height: 20px;
  }
  input[type='range']::-moz-range-track {
    background: transparent;
    height: 20px;
  }
  input[type='range']::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    pointer-events: auto;
    width: 14px;
    height: 14px;
    margin-top: 3px;
    border-radius: 50%;
    background: #2a78d6;
    border: 2px solid #fffdf9;
    box-shadow: 0 0 2px rgba(0, 0, 0, 0.45);
    cursor: pointer;
  }
  input[type='range']::-moz-range-thumb {
    pointer-events: auto;
    width: 11px;
    height: 11px;
    border-radius: 50%;
    background: #2a78d6;
    border: 2px solid #fffdf9;
    box-shadow: 0 0 2px rgba(0, 0, 0, 0.45);
    cursor: pointer;
  }
</style>
