<script>
  /**
   * Admission/type badges. Selectivity changes what raw scores mean — an
   * exam-entry school's results reflect who gets in — so these flags travel
   * with the name wherever scores are shown.
   */
  let { flags = null } = $props();

  const BADGES = {
    selective: {
      label: 'selective',
      cls: 'sel',
      tip: 'Selective admission (entrance exam or academic criteria) — results largely reflect who is admitted. Community-curated flag; see curated/selective_admissions.yaml for sources.'
    },
    magnet: { label: 'magnet', cls: 'mag', tip: 'Magnet program — application-based admission (CDE directory).' },
    charter: { label: 'charter', cls: 'cha', tip: 'Charter school — admission by application, lottery if oversubscribed.' },
    'alt-choice': { label: 'alt', cls: 'alt', tip: 'Alternative school of choice (CDE EdOps).' },
    continuation: { label: 'contin.', cls: 'alt', tip: 'Continuation school — serves students recovering credits; compare with care.' },
    'community-day': { label: 'comm. day', cls: 'alt', tip: 'Community day school — serves referred students; compare with care.' },
    community: { label: 'county comm.', cls: 'alt', tip: 'County community school — serves referred students; compare with care.' },
    court: { label: 'court', cls: 'alt', tip: 'Juvenile court school; compare with care.' },
    'special-ed': { label: 'spec. ed', cls: 'alt', tip: 'Special education school; compare with care.' }
  };
</script>

{#if flags?.length}
  {#each flags as f (f)}
    {#if BADGES[f]}
      <span class="badge {BADGES[f].cls}" title={BADGES[f].tip}>{BADGES[f].label}</span>
    {/if}
  {/each}
{/if}

<style>
  .badge {
    display: inline-block;
    font-size: 0.66rem;
    font-weight: 650;
    letter-spacing: 0.02em;
    border-radius: 4px;
    padding: 0.05rem 0.32rem;
    margin-left: 0.35rem;
    vertical-align: 1px;
    cursor: help;
  }
  .sel {
    background: #fbe9e2;
    color: #a34317;
    border: 1px solid #eec4ad;
  }
  .mag {
    background: #e7f0fb;
    color: #1c5cab;
    border: 1px solid #c3d9f2;
  }
  .cha {
    background: #eaf6ef;
    color: #1e6b3a;
    border: 1px solid #c6e5d2;
  }
  .alt {
    background: #f3ede2;
    color: #6f6a61;
    border: 1px solid #e0d6c2;
  }
</style>
